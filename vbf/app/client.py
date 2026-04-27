"""
VBF Client - Smart Modeling Control System (Four Layers)

This is a COMPLETE REWRITE of the original client.py implementing:
1. Checkpoint/Resume - Config errors save state, not terminate
2. Enhanced Recovery - Physical rollback + state preservation
3. Active Replanning - User can trigger replanning from any step
4. Real-time Feedback - Optional per-step LLM analysis

Key design changes:
- _save_path defined at method start to ensure save even on config errors
- All ValueError exceptions replaced with TaskInterruptedError for resumability
- SceneState integrated for feedback and replanning
- LLM calls via vbf.adapters (OpenAICompatAdapter), replacing llm_integration.py

Migration: All LLM calls now use the adapter via:
  - _ensure_adapter() -> OpenAICompatAdapter (lazy, singleton per client)
  - _adapter_call(messages) -> parsed response (rate-limited)
  - adapter.format_messages(prompt) -> system+user messages
"""

import asyncio
import json
import os
import copy
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple

from ..transport.jsonrpc_ws import JsonRpcWebSocketClient, JsonRpcError
from ..adapters import get_adapter
from ..config_runtime import load_llm_section, load_project_paths, load_project_scene_config
from ..llm.rate_limiter import call_llm_with_throttle
from ..core.plan_normalization import extract_skills_plan
from ..core.task_state import TaskState, TaskInterruptedError
from ..core.scene_state import SceneState, FeedbackContext
from ..runtime.memory_manager import MemoryManager
from ..runtime.run_logging import (
    append_run_event,
    create_task_log_context,
    summarize_task_result,
    tee_console_to_task_log,
    write_task_result_log,
)

from ..runtime.style_templates import get_style_manager
from .plan_gate import (
    auto_fix_known_plan_gate_issue,
    build_plan_repair_prompt,
    extract_plan_gate_missing_required,
    guess_python_type_name,
    is_recoverable_plan_error,
    matches_expected_type,
    validate_plan_with_schema_autofix,
    validate_plan_with_skill_schemas,
)
from .planning_context import (
    build_adaptive_stage_prompt,
    build_error_signature,
    build_json_format_retry_prompt,
    build_geometry_stage_prompt,
    build_nonempty_steps_rescue_prompt,
    build_presentation_stage_prompt,
    capability_skill_map,
    classify_skills_for_two_stage,
    default_planning_context,
    default_requirement_assessment_config,
    derive_capability_covered_skill_subset,
    derive_skill_subset,
    filter_skills_for_adaptive_stage,
    get_core_skills,
    get_planning_context,
    get_planning_mode,
    get_requirement_assessment_config,
    global_safety_skills,
    global_safety_skills_for_stage,
    high_risk_skills,
    high_risk_skills_for_stage,
    has_nonempty_steps,
    is_tool_calls_payload,
    merge_two_stage_plans,
    rank_skills_for_prompt,
    reindex_steps,
    remap_ref_text,
    remap_ref_value,
    required_capabilities_for_stage,
    scene_to_prompt_text,
    should_use_two_stage_planning,
    stage_irrelevant_skill,
    tokenize_prompt_for_skills,
)
from .planning_service import (
    assess_adaptive_stage_intent,
    call_plan_with_format_retry,
    inject_scene_context,
    plan_skill_task,
    plan_skill_task_adaptive_staged,
    plan_skill_task_auto,
    plan_skill_task_two_stage,
    replan_from_step,
    request_replan,
)
from .scene_capture import capture_scene_state as capture_scene_state_impl
from .stage_intent import (
    StageIntent,
    analyze_stage_intent,
    build_requirement_assessment_prompt,
    extract_stage_selection_text,
    infer_planning_stage,
    normalize_assessed_stage_intent,
    regex_any,
    select_adaptive_planning_stages,
    valid_planning_stages,
)
from .task_execution import run_task as run_task_impl, run_task_with_feedback as run_task_with_feedback_impl


class VBFClient:
    """Smart modeling client with four-layer control system (adapter-powered)."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        blender_path: Optional[str] = None,
        start_script_path: Optional[str] = None,
        memory_limit_mb: Optional[int] = None,
    ):
        self.host = host or os.getenv("VBF_WS_HOST", "127.0.0.1")
        self.port = int(port) if port is not None else int(os.getenv("VBF_WS_PORT", "8006"))
        self.blender_path = blender_path or os.getenv("BLENDER_PATH", "blender")

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.start_script_path = start_script_path or os.path.join(
            repo_root, "blender_provider", "start_vbf_blender.py"
        )

        self._ws = JsonRpcWebSocketClient(f"ws://{self.host}:{self.port}")
        self._runtime_paths = load_project_paths()
        self._scene_config = load_project_scene_config()
        self._default_save_path = self._runtime_paths["task_state_file"]
        self._task_scene_policy = str(
            self._scene_config.get("task_scene_policy", "isolate")
        ).strip().lower()
        self._task_include_environment_objects = bool(
            self._scene_config.get("include_environment_objects", True)
        )
        self._task_object_names: Set[str] = set()
        self._task_initial_object_names: Set[str] = set()

        # Initialize memory manager
        memory_threshold = memory_limit_mb or int(os.getenv("VBF_MEMORY_THRESHOLD_MB", "512"))
        self._memory_manager = MemoryManager(
            memory_threshold_mb=memory_threshold,
            step_results_limit=int(os.getenv("VBF_STEP_RESULTS_LIMIT", "100")),
            auto_cleanup=True,
        )
        self._adapter = None  # LLM adapter (lazy init via _ensure_adapter)
        self._capabilities_cache: Optional[Dict[str, Any]] = None
        self._capabilities_logged = False

    # --- LLM adapter helpers (v2 - replaces llm_integration.py) ---

    def _is_llm_enabled(self) -> bool:
        """Check if LLM is configured."""
        try:
            from ..llm.openai_compat import load_openai_compat_config
            cfg = load_openai_compat_config()
            return cfg is not None and cfg.use_llm
        except Exception:
            return False

    def _load_adapter_config(self) -> Optional[Dict]:
        """Load llm config section for adapter initialization."""
        llm_config = load_llm_section()
        return llm_config or None

    def _get_llm_model_name(self) -> str:
        """Determine which model key to use in get_adapter()."""
        env_model = os.getenv("VBF_LLM_MODEL")
        if env_model:
            return env_model
        # Infer from base_url patterns
        base_url = os.getenv("VBF_LLM_BASE_URL", "")
        if "openai" in base_url.lower():
            return "gpt-4o"
        if "bigmodel" in base_url.lower() or "glm" in base_url.lower():
            return "glm-4"
        if "moonshot" in base_url.lower() or "kimi" in base_url.lower():
            return "kimi"
        if "dashscope" in base_url.lower() or "qwen" in base_url.lower():
            return "qwen"
        if "ollama" in base_url.lower():
            return "ollama"
        return "default"

    async def _ensure_adapter(self):
        """Get or create the LLM adapter (singleton per client).

        The adapter wraps OpenAICompatLLM with:
        - Configurable response paths (response_content_path)
        - Skill loading via SkillRegistry (RPC from Blender)
        - Unified error handling and JSON parsing
        """
        if self._adapter is not None:
            return self._adapter
        config_override = self._load_adapter_config() or {}
        model_name = self._get_llm_model_name()
        adapter = get_adapter(model_name, client=self, config_override=config_override)
        # init() loads skills from Blender via SkillRegistry (cached globally)
        await adapter.init()
        self._adapter = adapter
        return adapter

    async def _adapter_call(self, messages: List[Dict]) -> Dict[str, Any]:
        """Call LLM via adapter with rate limiting.

        adapter.call_llm() raises TimeoutError / ConnectionError on HTTP errors
        and returns error dicts on JSON parse failures. We convert error dicts
        to ValueError so the retry loop in run_task can detect them.
        """
        adapter = await self._ensure_adapter()

        async def _call():
            response = await adapter.call_llm(messages)
            if isinstance(response, dict) and "error" in response:
                self._record_llm_parse_failure(response)
                parse_stage = response.get("parse_stage", "unknown")
                raw = str(response.get("raw_content", str(response)))
                excerpt = raw[:500]
                raise ValueError(
                    f"LLM parse error (parse_stage={parse_stage}): {excerpt}"
                )
            return response

        return await call_llm_with_throttle(_call)

    def _record_llm_parse_failure(self, payload: Dict[str, Any]) -> None:
        """Persist the latest parse failure with full context for debugging."""
        try:
            save_path = self._runtime_paths["last_gen_fail_file"]
            content = {
                "error": payload.get("error"),
                "parse_stage": payload.get("parse_stage"),
                "parse_detail": payload.get("parse_detail"),
                "fallback_mode": payload.get("fallback_mode"),
                "raw_content": payload.get("raw_content"),
                "extracted_json": payload.get("extracted_json"),
            }
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(content, ensure_ascii=False, indent=2))
        except Exception:
            # Parse-failure logging must not crash the main control flow.
            pass

    def _record_plan_shape_failure(
        self,
        error_message: str,
        raw_plan: Any,
        stage: str = "normalize_plan",
    ) -> None:
        """Persist non-parse plan failures (e.g. missing steps wrappers)."""
        try:
            save_path = self._runtime_paths["last_plan_fail_file"]
            payload = {
                "error": error_message,
                "stage": stage,
                "raw_plan_type": type(raw_plan).__name__,
                "raw_plan": raw_plan,
            }
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        except Exception:
            pass

    @staticmethod
    def _snapshot_payload(payload: Any) -> Any:
        """Best-effort deep snapshot to preserve pre-normalization raw payload."""
        try:
            return copy.deepcopy(payload)
        except Exception:
            return payload

    def _record_pre_normalize_plan_snapshot(self, raw_plan: Any, stage: str) -> None:
        """Persist the latest raw plan exactly before normalize_plan()."""
        try:
            save_path = self._runtime_paths["last_plan_raw_file"]
            payload = {
                "stage": stage,
                "raw_plan_type": type(raw_plan).__name__,
                "raw_plan": raw_plan,
            }
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        except Exception:
            pass

    @staticmethod
    def _is_llm_parse_error(exc: Exception) -> bool:
        return "LLM parse error" in str(exc)

    # --- WebSocket / Blender RPC ---

    async def ensure_connected(self, timeout_s: float = 30.0) -> None:
        deadline = asyncio.get_event_loop().time() + timeout_s
        last_err = None
        while asyncio.get_event_loop().time() < deadline:
            try:
                await self._ws.connect()
                await self._probe_server_capabilities_once()
                return
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.5)
        await self._start_blender_headless()
        deadline2 = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline2:
            try:
                await self._ws.connect()
                await self._probe_server_capabilities_once()
                return
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.5)
        raise TimeoutError(f"Unable to connect to Blender VBF WS") from last_err

    async def execute_skill(self, skill: str, args: Optional[Dict] = None, step_id: Optional[str] = None) -> Dict:
        return await self._ws.call(
            method="vbf.execute_skill",
            params={"skill": skill, "args": args or {}, "step_id": step_id},
        )

    async def list_skills(self) -> List[str]:
        resp = await self._ws.call(method="vbf.list_skills", params={})
        if not isinstance(resp, dict):
            return []
        data = resp.get("data") or {}
        skills = data.get("skills") or []
        return skills if isinstance(skills, list) else []

    async def describe_skills(self, skill_names: List[str]) -> Optional[Dict[str, Any]]:
        try:
            resp = await self._ws.call(method="vbf.describe_skills", params={"skill_names": skill_names})
            if not isinstance(resp, dict):
                return None
            data = resp.get("data") or {}
            return data.get("skills")
        except Exception:
            return None

    async def get_server_capabilities(self, refresh: bool = False) -> Dict[str, Any]:
        """Get server capability descriptor (feature negotiation)."""
        if self._capabilities_cache is not None and not refresh:
            return {"ok": True, "data": self._capabilities_cache, "cached": True}

        try:
            resp = await self._ws.call(method="vbf.get_capabilities", params={})
            if not isinstance(resp, dict):
                return {"ok": False, "error": "Invalid capability response"}
            data = resp.get("data")
            if isinstance(data, dict):
                self._capabilities_cache = data
            return resp
        except JsonRpcError as e:
            return {
                "ok": False,
                "error": str(e),
                "method_not_found": e.code == -32601,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_scene_delta(self, since_seq: int = 0) -> Dict[str, Any]:
        """Get aggregated scene delta from depsgraph event stream."""
        if self._feature_supported("scene_delta") is False:
            return {
                "ok": False,
                "method_not_found": True,
                "error": "Server capability reports scene_delta unsupported",
            }
        try:
            resp = await self._ws.call(
                method="vbf.get_scene_delta",
                params={"since_seq": int(since_seq)},
            )
            if not isinstance(resp, dict):
                return {"ok": False, "error": "Invalid scene delta response"}
            return resp
        except JsonRpcError as e:
            return {
                "ok": False,
                "error": str(e),
                "method_not_found": e.code == -32601,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_scene_snapshot(self) -> Dict[str, Any]:
        """Get full lightweight scene snapshot for cache bootstrap/resync."""
        if self._feature_supported("scene_snapshot") is False:
            return {
                "ok": False,
                "method_not_found": True,
                "error": "Server capability reports scene_snapshot unsupported",
            }
        try:
            resp = await self._ws.call(
                method="vbf.get_scene_snapshot",
                params={},
            )
            if not isinstance(resp, dict):
                return {"ok": False, "error": "Invalid scene snapshot response"}
            return resp
        except JsonRpcError as e:
            return {
                "ok": False,
                "error": str(e),
                "method_not_found": e.code == -32601,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _feature_supported(self, feature_name: str) -> Optional[bool]:
        if not isinstance(self._capabilities_cache, dict):
            return None
        features = self._capabilities_cache.get("features")
        if not isinstance(features, dict):
            return None
        flag = features.get(feature_name)
        if isinstance(flag, bool):
            return flag
        return None

    async def _probe_server_capabilities_once(self) -> None:
        """Best-effort probe; never fail connection flow if unsupported."""
        if self._capabilities_logged:
            return
        try:
            resp = await self.get_server_capabilities(refresh=True)
            if resp.get("ok") and isinstance(resp.get("data"), dict):
                self._log_capabilities(resp["data"])
            elif resp.get("method_not_found"):
                print("[VBF] Server capabilities RPC unavailable; using compatibility fallback mode")
                self._capabilities_logged = True
        except Exception:
            pass

    def _log_capabilities(self, caps: Dict[str, Any]) -> None:
        """Emit a concise capabilities summary once per client session."""
        if self._capabilities_logged:
            return
        features = caps.get("features", {}) if isinstance(caps, dict) else {}
        if not isinstance(features, dict):
            features = {}

        def _flag(name: str) -> str:
            value = features.get(name)
            return "on" if value is True else "off" if value is False else "unknown"

        print(
            "[VBF] Server capabilities: "
            f"snapshot={_flag('scene_snapshot')}, "
            f"delta={_flag('scene_delta')}, "
            f"rollback={_flag('rollback_to_step')}, "
            f"cap_rpc={_flag('capabilities_rpc')}"
        )
        self._capabilities_logged = True

    async def rollback_to_step(self, step_id: str) -> Dict[str, Any]:
        try:
            return await self._ws.call(method="vbf.rollback_to_step", params={"step_id": step_id})
        except Exception as e:
            print(f"[VBF] Rollback to {step_id} failed: {e}")
            return {"ok": False, "error": str(e)}

    async def capture_scene_state(self) -> SceneState:
        return await capture_scene_state_impl(self)

    def _remember_task_initial_scene(self, scene: SceneState) -> None:
        """Remember pre-existing objects so task-scoped prompts can ignore them."""
        try:
            self._task_initial_object_names = {
                obj.get("name")
                for obj in scene.get_objects()
                if isinstance(obj.get("name"), str)
            }
        except Exception:
            self._task_initial_object_names = set()

    def _record_task_result_objects(self, result: Any) -> None:
        """Track objects created/returned during this task for scene isolation."""
        if not isinstance(result, dict):
            return
        data = result.get("data")
        if not isinstance(data, dict):
            return
        candidates: Set[str] = set()
        for key in ("object_name", "name", "child"):
            value = data.get(key)
            if isinstance(value, str) and value:
                candidates.add(value)
        post_state = data.get("_post_state")
        if isinstance(post_state, dict):
            candidates.update(name for name in post_state.keys() if isinstance(name, str))
        for name in candidates:
            if name:
                self._task_object_names.add(name)

    def _filter_scene_for_task_context(self, scene: SceneState) -> SceneState:
        """Return scene context visible to LLM for the active task."""
        if self._task_scene_policy not in {"isolate", "isolated", "task"}:
            return scene
        if not hasattr(scene, "filtered_copy") or not hasattr(scene, "get_objects"):
            return scene
        env_types = {"CAMERA", "LIGHT"} if self._task_include_environment_objects else set()
        include_names = set(self._task_object_names)
        filtered = scene.filtered_copy(
            include_names=include_names,
            include_types=env_types,
            warning=(
                "Task scene isolation is active; pre-existing objects are hidden from "
                "planning/feedback context unless created or referenced by this task."
            ),
            statistics={
                "task_scene_policy": "isolate",
                "original_object_count": len(scene.get_objects()),
                "task_object_count": len(include_names),
            },
        )
        filtered.set_statistics(context_object_count=len(filtered.get_objects()))
        return filtered
    def _create_interrupt(self, reason: str, prompt: str, save_path: str,
                          plan: Dict = None, steps: List = None,
                          step_results: Dict = None, current_index: int = 0,
                          allowed_skills: List = None,
                          diagnostics: Dict[str, Any] = None,
                          cause: Exception = None) -> TaskInterruptedError:
        """Create and return a TaskInterruptedError with saved state."""
        state = TaskState(
            prompt=prompt,
            plan=plan or {},
            steps=steps or [],
            step_results=step_results or {},
            current_step_index=current_index,
            allowed_skills=allowed_skills or [],
            diagnostics=diagnostics or {},
        )
        state.save(save_path)
        print(f"[VBF] {reason}")
        print(f"[VBF] State saved: {save_path}")
        print(f"[VBF] Resume: --resume \"{save_path}\"")
        return TaskInterruptedError(
            f"{reason}: {cause}" if cause else reason,
            state=state,
            state_path=save_path
        )

    @staticmethod
    def _build_json_format_retry_prompt(prompt: str) -> str:
        return build_json_format_retry_prompt(prompt)

    @staticmethod
    def _build_nonempty_steps_rescue_prompt(prompt: str) -> str:
        return build_nonempty_steps_rescue_prompt(prompt)

    @staticmethod
    def _has_nonempty_steps(payload: Any) -> bool:
        return has_nonempty_steps(payload, extract_skills_plan)

    @staticmethod
    def _is_tool_calls_payload(payload: Any) -> bool:
        return is_tool_calls_payload(payload)

    async def _call_plan_with_format_retry(
        self,
        adapter: Any,
        prompt: str,
        skills_subset: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await call_plan_with_format_retry(self, adapter, prompt, skills_subset)

    @staticmethod
    def _build_error_signature(error_text: Any) -> str:
        return build_error_signature(error_text)

    def _build_replan_fingerprint(self, reason: str, skill: str, error_text: Any) -> str:
        return "|".join(
            [
                str(reason or "unknown"),
                str(skill or "unknown"),
                self._build_error_signature(error_text),
            ]
        )

    @staticmethod
    def _tokenize_prompt_for_skills(prompt: str) -> Set[str]:
        return tokenize_prompt_for_skills(prompt)

    @staticmethod
    def _get_core_skills() -> Set[str]:
        return get_core_skills()

    @staticmethod
    def _default_planning_context() -> Dict[str, Any]:
        return default_planning_context()

    def _get_planning_context(self) -> Dict[str, Any]:
        return get_planning_context(load_llm_section)

    @staticmethod
    def _default_requirement_assessment_config() -> Dict[str, Any]:
        return default_requirement_assessment_config()

    def _get_requirement_assessment_config(self) -> Dict[str, Any]:
        return get_requirement_assessment_config(load_llm_section)

    def _get_planning_mode(self) -> str:
        return get_planning_mode(load_llm_section)

    @staticmethod
    def _infer_planning_stage(prompt: str) -> str:
        return infer_planning_stage(prompt)

    @staticmethod
    def _modeling_quality_contract() -> str:
        return """## Modeling Planning Contract
- Complete workflow: blockout proportions -> separate components -> boolean/cutout helpers -> bevel/chamfer support -> topology cleanup -> normals/sharp edges -> hierarchy/origin cleanup.
- Transform precision: every creation step must include explicit `name`, `size`/dimensions, `location`, and `rotation_euler` when orientation matters. Do not rely on defaults for production geometry.
- Coordinate frame: keep one consistent world/local basis. For phone-like products, center the chassis near world origin, use one axis for length, one for width, one for thickness, and place all parts by relative offsets from the chassis.
- Scale hygiene: use realistic relative proportions, apply/freeze transforms when a later bevel, boolean, UV, or material operation depends on uniform scale.
- Topology: prefer quad-friendly construction, avoid unnecessary triangles/ngons, keep edge loops around cutouts/fillets, remove doubles, fill holes, and recalculate outward normals before final cleanup.
- Surface quality: bevel all real-world hard edges with explicit widths/segments, mark sharp/crease edges when available, and avoid absolute razor edges.
- Object identity: use semantic names such as GEO_Phone_Chassis, GEO_Rear_Camera_Island, GEO_Lens_Ring_UL. Avoid generic Cube/Circle names.
- Relationships: create root/parent objects first, then parent child components with `$ref` from creation step outputs. Do not reference objects before creation.
- Modifier stack: plan boolean helpers before boolean operations, bevel after major booleans, cleanup after destructive/apply operations. Delete helper cutters only after their operation succeeds.
- Pivot/origin intent: root product origin should support alignment/animation; child origins should make sense for buttons, lenses, doors, hinges, or rotating parts.
- UV/material readiness: even in geometry-only planning, preserve clean seams, normals, and scale so later UVs/PBR materials will not stretch or shade incorrectly."""

    @staticmethod
    def _capability_skill_map() -> Dict[str, List[str]]:
        return capability_skill_map()

    @staticmethod
    def _high_risk_skills() -> Set[str]:
        return high_risk_skills()

    @staticmethod
    def _high_risk_skills_for_stage(stage: str) -> Set[str]:
        return high_risk_skills_for_stage(stage)

    @staticmethod
    def _global_safety_skills() -> Set[str]:
        return global_safety_skills()

    @staticmethod
    def _global_safety_skills_for_stage(stage: str) -> Set[str]:
        return global_safety_skills_for_stage(stage)

    def _required_capabilities_for_stage(self, stage: str, prompt: str) -> List[str]:
        return required_capabilities_for_stage(stage, prompt)
        text = (prompt or "").lower()
        caps: List[str] = []
        if stage == "geometry_modeling":
            caps.extend(["primitive_creation", "transform_alignment", "assembly_parenting"])
            if any(
                token in text
                for token in ("phone", "smartphone", "chassis", "hard surface", "手机", "机身")
            ):
                caps.append("beveled_chassis")
            if any(
                token in text
                for token in (
                    "cutout",
                    "hole",
                    "usb",
                    "camera",
                    "lens",
                    "boolean",
                    "island",
                    "grille",
                    "开孔",
                    "镜头",
                )
            ):
                caps.append("boolean_cutouts")
            caps.append("mesh_cleanup")
        elif stage == "uv_texture_material":
            caps.extend(["uv_unwrap", "pbr_materials"])
        elif stage == "animation":
            caps.extend(["keyframe_animation", "transform_alignment", "camera_tracking"])
        elif stage in {"environment_lighting", "camera_render"}:
            caps.extend(["environment_lighting", "camera_render"])
        else:
            caps.extend(["primitive_creation", "transform_alignment"])

        deduped: List[str] = []
        for cap in caps:
            if cap not in deduped:
                deduped.append(cap)
        return deduped

    @staticmethod
    def _stage_irrelevant_skill(skill: str, stage: str) -> bool:
        return stage_irrelevant_skill(skill, stage)
        if stage == "geometry_modeling":
            irrelevant_prefixes = (
                "bake_", "cloth_", "fluid_", "gpencil_", "paint_", "sequencer_",
                "insert_keyframe", "delete_keyframe", "nla_", "set_render_", "render_",
                "create_light", "set_light", "create_material", "assign_material",
                "compositor_", "add_compositor", "create_shader",
            )
            return skill.startswith(irrelevant_prefixes)
        if stage == "animation":
            irrelevant_prefixes = ("cloth_", "fluid_", "paint_", "sequencer_", "compositor_")
            return skill.startswith(irrelevant_prefixes)
        if stage in {"uv_texture_material", "environment_lighting", "camera_render"}:
            irrelevant_prefixes = ("armature_", "cloth_", "fluid_", "gpencil_", "sculpt_")
            return skill.startswith(irrelevant_prefixes)
        return False

    def _derive_capability_covered_skill_subset(
        self,
        adapter: Any,
        prompt: str,
        allowed_skills: List[str],
        size: int,
    ) -> List[str]:
        return derive_capability_covered_skill_subset(
            adapter,
            prompt,
            allowed_skills,
            size,
            stage=self._infer_planning_stage(prompt),
            context=self._get_planning_context(),
        )

    def _rank_skills_for_prompt(
        self,
        adapter: Any,
        prompt: str,
        allowed_skills: List[str],
    ) -> List[str]:
        return rank_skills_for_prompt(adapter, prompt, allowed_skills)

    def _derive_skill_subset(
        self,
        adapter: Any,
        prompt: str,
        allowed_skills: List[str],
        size: int,
    ) -> List[str]:
        return derive_skill_subset(
            adapter,
            prompt,
            allowed_skills,
            size,
            stage=self._infer_planning_stage(prompt),
            context=self._get_planning_context(),
        )

    @staticmethod
    def _guess_python_type_name(value: Any) -> str:
        return guess_python_type_name(value)

    @staticmethod
    def _matches_expected_type(expected_hint: str, value: Any) -> bool:
        return matches_expected_type(expected_hint, value)

    def _validate_plan_with_skill_schemas(
        self,
        plan: Dict[str, Any],
        adapter: Any,
        allowed_skills: List[str],
    ) -> None:
        validate_plan_with_skill_schemas(plan, adapter, allowed_skills)

    @staticmethod
    def _extract_plan_gate_missing_required(
        message: str,
    ) -> Optional[Tuple[int, str, str]]:
        return extract_plan_gate_missing_required(message)

    def _auto_fix_known_plan_gate_issue(self, plan: Dict[str, Any], error_message: str) -> bool:
        return auto_fix_known_plan_gate_issue(plan, error_message)

    def _validate_plan_with_schema_autofix(
        self,
        plan: Dict[str, Any],
        adapter: Any,
        allowed_skills: List[str],
    ) -> List[Dict[str, Any]]:
        return validate_plan_with_schema_autofix(plan, adapter, allowed_skills)

    @staticmethod
    def _is_recoverable_plan_error(message: str) -> bool:
        return is_recoverable_plan_error(message)

    @staticmethod
    def _build_plan_repair_prompt(prompt: str, error_message: str) -> str:
        return build_plan_repair_prompt(
            prompt,
            error_message,
            VBFClient._modeling_quality_contract(),
        )

    def _should_use_two_stage_planning(
        self,
        prompt: str,
        allowed_skills: List[str],
    ) -> bool:
        return should_use_two_stage_planning(prompt, allowed_skills)

    @staticmethod
    def _classify_skills_for_two_stage(
        allowed_skills: List[str],
    ) -> Tuple[List[str], List[str]]:
        return classify_skills_for_two_stage(allowed_skills)

    @staticmethod
    def _build_geometry_stage_prompt(prompt: str) -> str:
        return build_geometry_stage_prompt(prompt)

    @staticmethod
    def _build_presentation_stage_prompt(prompt: str) -> str:
        return build_presentation_stage_prompt(prompt)

    @staticmethod
    def _remap_ref_value(value: Any, id_map: Dict[str, str]) -> Any:
        return remap_ref_value(value, id_map)

    @staticmethod
    def _remap_ref_text(ref: str, id_map: Dict[str, str]) -> str:
        return remap_ref_text(ref, id_map)

    def _reindex_steps(
        self,
        steps: List[Dict[str, Any]],
        start_index: int,
    ) -> List[Dict[str, Any]]:
        return reindex_steps(steps, start_index)

    def _merge_two_stage_plans(
        self,
        geom_plan: Dict[str, Any],
        geom_steps: List[Dict[str, Any]],
        pres_plan: Dict[str, Any],
        pres_steps: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        return merge_two_stage_plans(
            geom_plan,
            geom_steps,
            pres_plan,
            pres_steps,
        )

    @staticmethod
    def _extract_stage_selection_text(prompt: str) -> str:
        return extract_stage_selection_text(prompt)

    @staticmethod
    def _regex_any(text: str, patterns: Tuple[str, ...]) -> bool:
        return regex_any(text, patterns)

    @staticmethod
    def _analyze_stage_intent(text: str) -> StageIntent:
        return analyze_stage_intent(text)

    @staticmethod
    def _valid_planning_stages() -> List[str]:
        return valid_planning_stages()

    @staticmethod
    def _build_requirement_assessment_prompt(
        prompt: str,
        fallback: Optional[StageIntent] = None,
    ) -> str:
        return build_requirement_assessment_prompt(prompt, fallback)

    @staticmethod
    def _normalize_assessed_stage_intent(
        payload: Any,
        fallback: Optional[StageIntent],
        low_confidence_threshold: float = 0.7,
    ) -> StageIntent:
        return normalize_assessed_stage_intent(payload, fallback, low_confidence_threshold)

    @staticmethod
    def _select_adaptive_planning_stages(prompt: str) -> List[str]:
        return select_adaptive_planning_stages(prompt)

    async def _assess_adaptive_stage_intent(self, prompt: str) -> StageIntent:
        return await assess_adaptive_stage_intent(self, prompt)

    def _build_adaptive_stage_prompt(self, prompt: str, stage: str) -> str:
        return build_adaptive_stage_prompt(
            prompt,
            stage,
            self._modeling_quality_contract(),
        )

    @staticmethod
    def _filter_skills_for_adaptive_stage(allowed_skills: List[str], stage: str) -> List[str]:
        return filter_skills_for_adaptive_stage(allowed_skills, stage)

    async def _plan_skill_task_adaptive_staged(
        self,
        prompt: str,
        allowed_skills: List[str],
        save_path: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        return await plan_skill_task_adaptive_staged(self, prompt, allowed_skills, save_path)

    async def _plan_skill_task_two_stage(
        self,
        prompt: str,
        allowed_skills: List[str],
        save_path: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        return await plan_skill_task_two_stage(self, prompt, allowed_skills, save_path)

    async def _plan_skill_task_auto(
        self,
        prompt: str,
        allowed_skills: List[str],
        save_path: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        return await plan_skill_task_auto(self, prompt, allowed_skills, save_path)

    @staticmethod
    def _scene_to_prompt_text(scene: SceneState, max_objects: Optional[int] = None) -> str:
        return scene_to_prompt_text(scene, max_objects=max_objects)

    # --- Layer 4: Real-time Feedback ---

    async def analyze_step_result(self, step_id: str, skill: str, args: Dict,
                                  result: Dict, plan: Dict, steps: List,
                                  step_index: int, prompt: str) -> Optional[Dict]:
        """Optional: Ask LLM to analyze step result and suggest plan adjustments."""
        try:
            adapter = await self._ensure_adapter()
        except Exception:
            return None

        scene = await self.capture_scene_state()
        scene = self._filter_scene_for_task_context(scene)
        context = FeedbackContext(
            step_id=step_id,
            skill=skill,
            args=args,
            result=result,
            scene_after=scene,
        )

        analysis_prompt = context.to_plan_analysis_prompt()
        messages = [
            {"role": "system", "content": "You are a 3D modeling assistant analyzing step results."},
            {"role": "user", "content": analysis_prompt + f"\n\nRemaining steps: {steps[step_index:]}"},
        ]

        try:
            return await self._adapter_call(messages)
        except Exception:
            return None

    # --- Layer 3: Active Replanning ---

    async def request_replan(self, prompt: str, from_step_id: str, current_plan: Dict,
                            step_results: Dict, save_path: str) -> Tuple[Dict, List]:
        return await request_replan(self, prompt, from_step_id, current_plan, step_results, save_path)

    # --- Main Execution with Layer 2: Enhanced Recovery ---

    async def run_task(self, prompt: str, resume_state_path: Optional[str] = None,
                       save_state_path: Optional[str] = None,
                       style: Optional[str] = None,
                       enable_step_feedback: bool = False,
                       display_mode: str = "console") -> Dict[str, Any]:
        if not getattr(self, "_task_logging_managed", False):
            log_context = create_task_log_context(self._runtime_paths["logs_dir"])
            self._task_id = log_context.task_id
            self._task_log_path = str(log_context.transcript_path)
            with tee_console_to_task_log(log_context):
                print(f"[VBF] Task ID: {log_context.task_id}")
                print(f"[VBF] Task created: {log_context.created_at}")
                print(f"[VBF] Task log: {log_context.transcript_path}")
                result = await run_task_impl(
                    self,
                    prompt,
                    resume_state_path=resume_state_path,
                    save_state_path=save_state_path,
                    style=style,
                    enable_step_feedback=enable_step_feedback,
                    display_mode=display_mode,
                )
                result_path = write_task_result_log(
                    result,
                    self._runtime_paths["logs_dir"],
                    task_id=log_context.task_id,
                )
                summary = summarize_task_result(result)
                event_path = append_run_event(
                    "task_result_saved",
                    {
                        "task_id": log_context.task_id,
                        "mode": "legacy",
                        "steps": summary["steps"],
                        "ok": summary["ok"],
                        "failed": summary["failed"],
                        "unknown": summary["unknown"],
                        "plan_steps": summary["plan_steps"],
                        "result_file": str(result_path),
                        "task_log_file": str(log_context.transcript_path),
                    },
                    self._runtime_paths["logs_dir"],
                )
                print(f"[VBF] Result saved: {result_path}")
                print(f"[VBF] Event log: {event_path}")
                print(
                    "[VBF] Summary: "
                    f"steps={summary['steps']} "
                    f"ok={summary['ok']} "
                    f"failed={summary['failed']} "
                    f"unknown={summary['unknown']} "
                    f"plan_steps={summary['plan_steps']}"
                )
                return result
        return await run_task_impl(
            self,
            prompt,
            resume_state_path=resume_state_path,
            save_state_path=save_state_path,
            style=style,
            enable_step_feedback=enable_step_feedback,
            display_mode=display_mode,
        )

    async def _start_blender_headless(self) -> None:
        """Start Blender in headless mode with VBF server."""
        import subprocess

        blender_executable = shutil.which(self.blender_path)
        if blender_executable is None and os.path.exists(self.blender_path):
            blender_executable = self.blender_path
        if blender_executable is None:
            raise FileNotFoundError(
                "Blender executable not found: "
                f"{self.blender_path}. Set BLENDER_PATH or pass --blender-path."
            )
        if not os.path.exists(self.start_script_path):
            raise FileNotFoundError(
                "Blender start script not found: "
                f"{self.start_script_path}."
            )

        env = os.environ.copy()
        env["VBF_WS_HOST"] = self.host
        env["VBF_WS_PORT"] = str(self.port)
        subprocess.Popen(
            [blender_executable, "-b", "-P", self.start_script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

    # --- Plan generation (via adapter) ---

    async def _plan_skill_task(self, prompt: str, allowed_skills: List[str],
                                save_path: str) -> Tuple[Dict, List]:
        return await plan_skill_task(self, prompt, allowed_skills, save_path)

    # --- Closed-loop task execution (Phase 1) ---

    async def run_task_with_feedback(
        self,
        prompt: str,
        resume_state_path: Optional[str] = None,
        save_state_path: Optional[str] = None,
        style: Optional[str] = None,
        enable_auto_check: bool = True,
        enable_llm_feedback: bool = True,
    ) -> Dict[str, Any]:
        if not getattr(self, "_task_logging_managed", False):
            log_context = create_task_log_context(self._runtime_paths["logs_dir"])
            self._task_id = log_context.task_id
            self._task_log_path = str(log_context.transcript_path)
            with tee_console_to_task_log(log_context):
                print(f"[VBF] Task ID: {log_context.task_id}")
                print(f"[VBF] Task created: {log_context.created_at}")
                print(f"[VBF] Task log: {log_context.transcript_path}")
                result = await run_task_with_feedback_impl(
                    self,
                    prompt,
                    resume_state_path=resume_state_path,
                    save_state_path=save_state_path,
                    style=style,
                    enable_auto_check=enable_auto_check,
                    enable_llm_feedback=enable_llm_feedback,
                )
                result_path = write_task_result_log(
                    result,
                    self._runtime_paths["logs_dir"],
                    task_id=log_context.task_id,
                )
                summary = summarize_task_result(result)
                event_path = append_run_event(
                    "task_result_saved",
                    {
                        "task_id": log_context.task_id,
                        "mode": "feedback",
                        "steps": summary["steps"],
                        "ok": summary["ok"],
                        "failed": summary["failed"],
                        "unknown": summary["unknown"],
                        "plan_steps": summary["plan_steps"],
                        "result_file": str(result_path),
                        "task_log_file": str(log_context.transcript_path),
                    },
                    self._runtime_paths["logs_dir"],
                )
                print(f"[VBF] Result saved: {result_path}")
                print(f"[VBF] Event log: {event_path}")
                print(
                    "[VBF] Summary: "
                    f"steps={summary['steps']} "
                    f"ok={summary['ok']} "
                    f"failed={summary['failed']} "
                    f"unknown={summary['unknown']} "
                    f"plan_steps={summary['plan_steps']}"
                )
                return result
        return await run_task_with_feedback_impl(
            self,
            prompt,
            resume_state_path=resume_state_path,
            save_state_path=save_state_path,
            style=style,
            enable_auto_check=enable_auto_check,
            enable_llm_feedback=enable_llm_feedback,
        )

    async def _replan_from_step(
        self,
        prompt: str,
        fail_idx: int,
        steps: List[Dict],
        step_results: Dict,
        allowed_skills: List[str],
        save_path: str,
        feedback_detail: Optional[Dict[str, Any]] = None,
        replan_fingerprint: Optional[str] = None,
        forced_corrective: bool = False,
    ) -> Tuple[Dict, List]:
        return await replan_from_step(
            self,
            prompt,
            fail_idx,
            steps,
            step_results,
            allowed_skills,
            save_path,
            feedback_detail=feedback_detail,
            replan_fingerprint=replan_fingerprint,
            forced_corrective=forced_corrective,
        )

    def _inject_scene_context(
        self,
        prompt: str,
        scene: SceneState,
        max_objects: Optional[int] = None,
    ) -> str:
        scene = self._filter_scene_for_task_context(scene)
        return inject_scene_context(self, prompt, scene, max_objects=max_objects)
