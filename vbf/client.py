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
import re
import copy
from typing import Any, Dict, List, Optional, Set, Tuple

from .jsonrpc_ws import JsonRpcWebSocketClient, JsonRpcError
from .adapters import get_adapter
from .llm_rate_limiter import call_llm_with_throttle
from .plan_normalization import normalize_plan, validate_plan_structure
from .vibe_protocol import resolve_refs
from .task_state import TaskState, TaskInterruptedError
from .scene_state import SceneState, FeedbackContext
from .memory_manager import MemoryManager

from .style_templates import get_style_manager


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

        repo_root = os.path.dirname(os.path.dirname(__file__))
        self.start_script_path = start_script_path or os.path.join(
            repo_root, "blender_provider", "start_vbf_blender.py"
        )

        self._ws = JsonRpcWebSocketClient(f"ws://{self.host}:{self.port}")
        self._default_save_path = os.path.join(
            os.path.dirname(__file__), "config", "task_state.json"
        )

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
            from .llm_openai_compat import load_openai_compat_config
            cfg = load_openai_compat_config()
            return cfg is not None and cfg.use_llm
        except Exception:
            return False

    def _load_adapter_config(self) -> Optional[Dict]:
        """Load raw config dict for adapter from llm_config.json."""
        config_path = os.path.join(os.path.dirname(__file__), "config", "llm_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

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
            save_path = os.path.join(os.path.dirname(__file__), "config", "last_gen_fail.txt")
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
        """Capture current Blender scene state with snapshot-first fallback."""
        state = SceneState()

        async def _get_value(path_steps: list):
            """Call py_get and return the value."""
            resp = await self.execute_skill("py_get", {"path_steps": path_steps})
            if resp.get("ok"):
                return resp.get("data", {}).get("value")
            return None

        def _vec3(value: Any, default: Optional[List[float]] = None) -> List[float]:
            fallback = default or [0.0, 0.0, 0.0]
            if not isinstance(value, list) or len(value) < 3:
                return list(fallback)
            out: List[float] = []
            for idx in range(3):
                try:
                    out.append(float(value[idx]))
                except Exception:
                    out.append(float(fallback[idx]))
            return out

        def _to_int(value: Any, default: int = 0) -> int:
            try:
                return int(value)
            except Exception:
                return default

        async def _capture_scene_meta() -> None:
            # Query scene attrs individually; this is stable across Blender versions.
            state.scene_name = (
                await _get_value([{"attr": "context"}, {"attr": "scene"}, {"attr": "name"}])
                or "Scene"
            )
            state.frame_current = _to_int(
                await _get_value([{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_current"}]),
                1,
            )
            state.frame_start = _to_int(
                await _get_value([{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_start"}]),
                1,
            )
            state.frame_end = _to_int(
                await _get_value([{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_end"}]),
                250,
            )

        try:
            # Fast path for closed-loop flow: use depsgraph-backed scene snapshot.
            snapshot_resp = await self.get_scene_snapshot()
            if snapshot_resp.get("ok"):
                data = snapshot_resp.get("data", {}) or {}
                objects = data.get("objects")
                if isinstance(objects, dict):
                    await _capture_scene_meta()
                    for obj_name, obj_state in objects.items():
                        if not isinstance(obj_name, str) or not isinstance(obj_state, dict):
                            continue
                        state.add_object(
                            name=obj_name,
                            obj_type=str(obj_state.get("type", "UNKNOWN")),
                            location=_vec3(obj_state.get("location")),
                            size=_vec3(obj_state.get("dimensions")),
                            vertices=_to_int(obj_state.get("vertices"), 0),
                            polygons=_to_int(obj_state.get("polygons"), 0),
                            edges=_to_int(obj_state.get("edges"), 0),
                            materials=_to_int(obj_state.get("materials"), 0),
                        )
                    state.set_statistics(
                        object_count=len(state.get_objects()),
                        capture_source="scene_snapshot",
                        snapshot_seq=_to_int(data.get("seq"), 0),
                    )
                    state.finalize()
                    return state
            elif not snapshot_resp.get("method_not_found"):
                state.add_warning(
                    f"Scene snapshot unavailable ({snapshot_resp.get('error', 'unknown')}); fallback to py_get"
                )
        except Exception as e:
            # Keep capture resilient: snapshot issues should not block fallback capture.
            state.add_warning(f"Scene snapshot failed: {e}")

        try:
            await _capture_scene_meta()

            object_names: List[str] = []

            # Preferred fallback path: bpy.data.objects.keys() via py_call.
            names_resp = await self.execute_skill(
                "py_call",
                {
                    "callable_path_steps": [{"attr": "data"}, {"attr": "objects"}, {"attr": "keys"}],
                    "args": [],
                    "kwargs": {},
                },
            )
            if names_resp.get("ok"):
                names_data = names_resp.get("data", {}) or {}
                maybe_names = names_data.get("result")
                if isinstance(maybe_names, list):
                    object_names = [name for name in maybe_names if isinstance(name, str) and name]

            # Legacy fallback: iterate object collection by index if keys() path fails.
            if not object_names:
                count = _to_int(
                    await _get_value([{"attr": "data"}, {"attr": "objects"}, {"len": True}]),
                    0,
                )
                for idx in range(max(count, 0)):
                    obj_name = await _get_value(
                        [{"attr": "data"}, {"attr": "objects"}, {"index": idx}, {"attr": "name"}]
                    )
                    if isinstance(obj_name, str) and obj_name:
                        object_names.append(obj_name)

            # Deduplicate while preserving order.
            seen = set()
            unique_names: List[str] = []
            for obj_name in object_names:
                if obj_name in seen:
                    continue
                seen.add(obj_name)
                unique_names.append(obj_name)

            for obj_name in unique_names:
                try:
                    obj_type = await _get_value(
                        [{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "type"}]
                    )
                    obj_loc = await _get_value(
                        [{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "location"}]
                    )
                    obj_dim = await _get_value(
                        [{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "dimensions"}]
                    )
                    state.add_object(
                        name=obj_name,
                        obj_type=str(obj_type) if obj_type else "MESH",
                        location=_vec3(obj_loc),
                        size=_vec3(obj_dim),
                    )
                except Exception:
                    # Best-effort: keep other objects even if one fails.
                    continue

            state.set_statistics(
                object_count=len(state.get_objects()),
                capture_source="py_get_fallback",
            )
            state.finalize()
        except Exception as e:
            state.add_error(f"Failed to capture scene: {e}")
        return state
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
        return (
            f"{prompt}\n\n"
            "FORMAT REQUIREMENT (must follow exactly):\n"
            "- Return plain JSON only (no markdown fences).\n"
            "- Output must be a single JSON object.\n"
            "- Keep the same user intent; do not change task semantics.\n"
            "- Include top-level `steps` array with executable Blender skills."
        )

    async def _call_plan_with_format_retry(
        self,
        adapter: Any,
        prompt: str,
        skills_subset: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Call planner once, then retry once with strict-format constraints on parse errors."""
        def _format(p: str) -> List[Dict[str, Any]]:
            try:
                return adapter.format_messages(p, skills_subset=skills_subset)
            except TypeError:
                # Backward compatibility for test doubles / older adapters.
                return adapter.format_messages(p)

        try:
            return await self._adapter_call(_format(prompt))
        except ValueError as e:
            if not self._is_llm_parse_error(e):
                raise
            match = re.search(r"parse_stage=([^)]+)", str(e))
            stage = match.group(1) if match else "unknown"
            print(f"[VBF] parse_stage={stage} retry_mode=structured_json_retry")
            retry_prompt = self._build_json_format_retry_prompt(prompt)
            return await self._adapter_call(_format(retry_prompt))

    @staticmethod
    def _build_error_signature(error_text: Any) -> str:
        text = str(error_text or "").strip().lower()
        if not text:
            return "none"
        text = re.sub(r"\s+", " ", text)
        return text[:160]

    def _build_replan_fingerprint(self, reason: str, skill: str, error_text: Any) -> str:
        return "|".join(
            [
                str(reason or "unknown"),
                str(skill or "unknown"),
                self._build_error_signature(error_text),
            ]
        )

    def _should_use_two_stage_planning(
        self,
        prompt: str,
        allowed_skills: List[str],
    ) -> bool:
        """Decide whether to use geometry->presentation two-stage planning."""
        mode = os.getenv("VBF_TWO_STAGE_PLANNING", "auto").strip().lower()
        if mode in {"1", "true", "on", "always"}:
            return True
        if mode in {"0", "false", "off", "never"}:
            return False
        # Auto mode: trigger on long prompts or very large skill sets.
        return len(prompt) >= 700 or len(allowed_skills) >= 180

    @staticmethod
    def _classify_skills_for_two_stage(
        allowed_skills: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Split skills into geometry-first and presentation-first subsets."""
        presentation_prefixes = (
            "create_camera",
            "set_camera",
            "camera_",
            "create_light",
            "set_light",
            "set_render",
            "set_cycles",
            "set_eevee",
            "render_",
            "create_material",
            "assign_material",
            "add_shader_",
            "set_material_",
            "add_texture",
            "attach_texture",
            "create_image_texture",
            "compositor_",
            "create_compositor",
            "set_compositor",
            "enable_pass",
        )
        presentation_exact = {
            "object_shade_smooth",
            "shade_smooth",
            "shade_flat",
            "object_shade_flat",
        }
        presentation: List[str] = []
        geometry: List[str] = []
        for skill in allowed_skills:
            if skill in presentation_exact or skill.startswith(presentation_prefixes):
                presentation.append(skill)
            else:
                geometry.append(skill)
        # Ensure each phase has enough baseline skills; fallback handled by caller.
        return geometry, presentation

    @staticmethod
    def _build_geometry_stage_prompt(prompt: str) -> str:
        return (
            f"{prompt}\n\n"
            "PLANNING MODE: STAGE 1 / GEOMETRY ONLY.\n"
            "- Focus on topology, proportions, booleans, bevel/chamfer, assembly geometry.\n"
            "- Do not spend steps on final rendering polish.\n"
            "- Camera/light/material/compositor steps are allowed only if strictly required for geometry inspection.\n"
            "- Return executable VBF skills JSON only."
        )

    @staticmethod
    def _build_presentation_stage_prompt(prompt: str) -> str:
        return (
            f"{prompt}\n\n"
            "PLANNING MODE: STAGE 2 / PRESENTATION ONLY.\n"
            "- Reuse existing geometry in scene.\n"
            "- Focus on camera, lights, materials, render, compositor.\n"
            "- Keep geometry edits minimal and local.\n"
            "- Do not use $ref to steps from stage 1. If relationships are needed, use existing object names "
            "or create local helper objects in this stage first.\n"
            "- Return executable VBF skills JSON only."
        )

    @staticmethod
    def _remap_ref_value(value: Any, id_map: Dict[str, str]) -> Any:
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                if k == "$ref" and isinstance(v, str):
                    out[k] = VBFClient._remap_ref_text(v, id_map)
                else:
                    out[k] = VBFClient._remap_ref_value(v, id_map)
            return out
        if isinstance(value, list):
            return [VBFClient._remap_ref_value(v, id_map) for v in value]
        if isinstance(value, str) and value.startswith("$ref:"):
            ref = value[len("$ref:") :].strip()
            remapped = VBFClient._remap_ref_text(ref, id_map)
            return f"$ref: {remapped}"
        return value

    @staticmethod
    def _remap_ref_text(ref: str, id_map: Dict[str, str]) -> str:
        match = re.match(r"^(step_)?([A-Za-z0-9_-]+)(\..+)$", ref)
        if not match:
            return ref
        prefix, step_id, suffix = match.groups()
        mapped = id_map.get(step_id)
        if not mapped:
            return ref
        return f"{'step_' if prefix else ''}{mapped}{suffix}"

    def _reindex_steps(
        self,
        steps: List[Dict[str, Any]],
        start_index: int,
    ) -> List[Dict[str, Any]]:
        remapped_steps = copy.deepcopy(steps)
        id_map: Dict[str, str] = {}
        for idx, step in enumerate(remapped_steps, start=start_index):
            old_id = step.get("step_id", f"{idx:03d}")
            old_id_str = str(old_id)
            normalized_old = old_id_str[len("step_") :] if old_id_str.startswith("step_") else old_id_str
            new_id = f"{idx:03d}"
            id_map[old_id_str] = new_id
            id_map[normalized_old] = new_id
            step["step_id"] = new_id

        for step in remapped_steps:
            for key, value in list(step.items()):
                step[key] = self._remap_ref_value(value, id_map)
        return remapped_steps

    def _merge_two_stage_plans(
        self,
        geom_plan: Dict[str, Any],
        geom_steps: List[Dict[str, Any]],
        pres_plan: Dict[str, Any],
        pres_steps: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        remapped_geom = self._reindex_steps(geom_steps, 1)
        remapped_pres = self._reindex_steps(pres_steps, len(remapped_geom) + 1)
        merged_steps = remapped_geom + remapped_pres

        merged_plan: Dict[str, Any] = {
            "vbf_version": geom_plan.get("vbf_version", pres_plan.get("vbf_version", "2.1")),
            "plan_type": "skills_plan",
            "steps": merged_steps,
            "execution": {
                "max_replans": max(
                    int(geom_plan.get("execution", {}).get("max_replans", 5)),
                    int(pres_plan.get("execution", {}).get("max_replans", 5)),
                )
            },
            "metadata": {
                "planning_mode": "two_stage",
                "geometry_steps": len(remapped_geom),
                "presentation_steps": len(remapped_pres),
            },
        }
        return merged_plan, merged_steps

    async def _plan_skill_task_two_stage(
        self,
        prompt: str,
        allowed_skills: List[str],
        save_path: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        geometry_skills, presentation_skills = self._classify_skills_for_two_stage(allowed_skills)
        if not geometry_skills or not presentation_skills:
            # Fallback when classifier cannot split meaningfully.
            return await self._plan_skill_task(prompt, allowed_skills, save_path)

        print(
            "[VBF] planning_mode=two_stage "
            f"geometry_skills={len(geometry_skills)} "
            f"presentation_skills={len(presentation_skills)}"
        )

        geometry_prompt = self._build_geometry_stage_prompt(prompt)
        geom_plan, geom_steps = await self._plan_skill_task(
            geometry_prompt,
            geometry_skills,
            save_path,
        )

        presentation_prompt = self._build_presentation_stage_prompt(prompt)
        try:
            pres_plan, pres_steps = await self._plan_skill_task(
                presentation_prompt,
                presentation_skills,
                save_path,
            )
        except TaskInterruptedError:
            raise
        except Exception as e:
            print(f"[VBF] Stage-2 planning failed, keeping geometry-only plan: {e}")
            return geom_plan, geom_steps

        merged_plan, merged_steps = self._merge_two_stage_plans(
            geom_plan,
            geom_steps,
            pres_plan,
            pres_steps,
        )
        # Re-validate merged output for refs and structure.
        merged_plan = normalize_plan(merged_plan)
        merged_steps = validate_plan_structure(merged_plan)
        return merged_plan, merged_steps

    async def _plan_skill_task_auto(
        self,
        prompt: str,
        allowed_skills: List[str],
        save_path: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        if self._should_use_two_stage_planning(prompt, allowed_skills):
            try:
                return await self._plan_skill_task_two_stage(prompt, allowed_skills, save_path)
            except TaskInterruptedError:
                raise
            except Exception as e:
                print(f"[VBF] two_stage planning fallback to single-stage: {e}")
        return await self._plan_skill_task(prompt, allowed_skills, save_path)

    @staticmethod
    def _scene_to_prompt_text(scene: SceneState, max_objects: Optional[int] = None) -> str:
        try:
            return scene.to_prompt_text(max_objects=max_objects)
        except TypeError:
            # Backward compatibility for test doubles / older SceneState implementations.
            return scene.to_prompt_text()

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
        """Request LLM to regenerate plan from given step with current scene context."""
        try:
            adapter = await self._ensure_adapter()
        except Exception as e:
            raise self._create_interrupt("Cannot replan: LLM not available", prompt, save_path) from e

        allowed_skills = await self.list_skills()
        scene = await self.capture_scene_state()

        # Build replan prompt with scene context
        replan_prompt = f"""Replanning request from step: {from_step_id}
Original prompt: {prompt}

Current scene state:
{self._scene_to_prompt_text(scene, max_objects=20)}

Completed steps:
{json.dumps(step_results, indent=2, ensure_ascii=False)}

Please generate a new plan starting from step "{from_step_id}".
Consider the current scene state when planning.
"""
        try:
            raw_plan = await self._call_plan_with_format_retry(
                adapter,
                replan_prompt,
                skills_subset=allowed_skills,
            )
            plan = normalize_plan(raw_plan)
            steps = validate_plan_structure(plan)
            if not steps:
                raise ValueError("No steps in replan")
            return plan, steps
        except ValueError as e:
            raise self._create_interrupt(f"Replan failed: {e}", prompt, save_path, cause=e)

    # --- Main Execution with Layer 2: Enhanced Recovery ---

    async def run_task(self, prompt: str, resume_state_path: Optional[str] = None,
                       save_state_path: Optional[str] = None,
                       style: Optional[str] = None,
                       enable_step_feedback: bool = False,
                       display_mode: str = "console") -> Dict[str, Any]:
        """Execute modeling task with full checkpoint/replan/recovery support.

        LLM calls now route through:
          adapter = await self._ensure_adapter()   # OpenAICompatAdapter
          messages = adapter.format_messages(prompt)  # system + user
          raw_plan = await self._adapter_call(messages)  # rate-limited, parsed
        """
        await self.ensure_connected()

        # CRITICAL: _save_path defined EARLY so we can save even on config errors
        _save_path = save_state_path or self._default_save_path
        os.makedirs(os.path.dirname(_save_path), exist_ok=True)

        # Layer 1: Config checks with checkpoint save
        if not self._is_llm_enabled():
            raise self._create_interrupt(
                "LLM not configured. Set VBF_LLM_BASE_URL, VBF_LLM_API_KEY, VBF_LLM_MODEL",
                prompt, _save_path
            )

        allowed_skills = await self.list_skills()
        if not allowed_skills:
            raise self._create_interrupt(
                "No skills returned from Blender addon. Check if VBF addon is enabled",
                prompt, _save_path
            )

        # Resume or generate plan
        if resume_state_path and os.path.exists(resume_state_path):
            print(f"[VBF] Resuming from: {resume_state_path}")
            saved = TaskState.load(resume_state_path)
            plan = saved.plan
            steps = saved.steps
            step_results = saved.step_results
            start_index = saved.current_step_index
            print(f"[VBF] Resuming at step {start_index}/{len(steps)}")
        else:
            # Apply style template
            if style:
                style_manager = get_style_manager()
                if style_manager.style_exists(style):
                    styled_prompt = style_manager.apply_style_to_prompt(style, prompt)
                    print(f"[VBF] Using style: {style}")
                else:
                    available = ", ".join(style_manager.list_styles()[:5])
                    print(f"[VBF] Warning: Unknown style '{style}'. Available: {available}...")
                    styled_prompt = prompt
            else:
                styled_prompt = prompt

            plan, steps = await self._plan_skill_task_auto(styled_prompt, allowed_skills, _save_path)
            step_results = {}
            start_index = 0
            print(f"[VBF] Generated plan with {len(steps)} steps")

        # Execution controls
        max_retries = int(plan.get("execution", {}).get("max_retries_per_step", 2))
        max_steps = int(plan.get("controls", {}).get("max_steps", 80))

        if len(steps) > max_steps:
            raise self._create_interrupt(
                f"Plan too large: {len(steps)} > {max_steps}",
                prompt, _save_path, plan=plan, steps=steps, allowed_skills=allowed_skills
            )

        # Stage tracking
        stage_order = {k: i for i, k in enumerate([
            "discover", "blockout", "boolean", "detail", "bevel",
            "normal_fix", "accessories", "material", "finalize"
        ])}
        current_stage_rank = -1
        attempt_counts: Dict[str, int] = {}

        i = start_index
        while i < len(steps):
            step = steps[i]
            step_id = step.get("step_id")
            skill = step.get("skill")
            args = step.get("args") or {}
            stage = step.get("stage", "detail")

            # Validation
            if not step_id or not isinstance(step_id, str):
                raise self._create_interrupt(f"Invalid step_id at index {i}", prompt, _save_path,
                                             plan, steps, step_results, i, allowed_skills)

            if skill not in allowed_skills:
                raise self._create_interrupt(f"Skill not allowed: {skill}", prompt, _save_path,
                                             plan, steps, step_results, i, allowed_skills)

            attempt_counts[step_id] = attempt_counts.get(step_id, 0) + 1
            if attempt_counts[step_id] > max_retries:
                # Layer 3: Replan on max retries exceeded
                print(f"[VBF] Step {step_id} exceeded max retries, requesting replan...")
                new_plan, new_steps = await self.request_replan(
                    prompt, step_id, plan, step_results, _save_path
                )
                steps = steps[:i] + new_steps
                continue

            # Stage monotonicity check
            if stage in stage_order and stage_order[stage] < current_stage_rank:
                print(f"[VBF] Warning: Stage regression at {step_id} ({stage})")
            current_stage_rank = max(current_stage_rank, stage_order.get(stage, current_stage_rank))

            # Execute skill
            try:
                resolved_args = resolve_refs(args, step_results)
                result = await self.execute_skill(skill, resolved_args, step_id)
                step_results[step_id] = result

                # Layer 4: Optional step feedback
                if enable_step_feedback and i + 1 < len(steps):
                    feedback = await self.analyze_step_result(
                        step_id, skill, resolved_args, result, plan, steps, i + 1, prompt
                    )
                    if feedback and feedback.get("should_adjust_plan"):
                        pass  # Can implement dynamic step adjustment here

                i += 1

            except JsonRpcError as e:
                step_results[step_id] = {"ok": False, "error": {"message": str(e)}}

                # Layer 2: Enhanced Recovery - repair plan via adapter
                if attempt_counts[step_id] <= max_retries:
                    try:
                        adapter = await self._ensure_adapter()
                        repair_prompt = (
                            f"Failed step: {step_id} (skill={skill})\n"
                            f"Error: {e}\n"
                            f"Original prompt: {prompt}\n"
                            f"Completed steps: {json.dumps(step_results, indent=2, ensure_ascii=False)}\n"
                            f"Generate a repair plan starting from step {step_id}. "
                            f"Use ONLY skills from: {allowed_skills}"
                        )
                        repair_messages = adapter.format_messages(repair_prompt)
                        repair_plan = await self._adapter_call(repair_messages)

                        if repair_plan and "steps" in repair_plan:
                            repair_steps = repair_plan.get("steps", [])
                            replace_from = repair_plan.get("repair", {}).get("replace_from_step_id", step_id)

                            await self.rollback_to_step(replace_from)

                            replace_idx = next(
                                (j for j, s in enumerate(steps) if s.get("step_id") == replace_from), i
                            )
                            steps = steps[:replace_idx] + repair_steps
                            i = replace_idx
                            print(f"[VBF] Repair: rolling back to {replace_from}, {len(repair_steps)} steps")
                            continue
                    except Exception as repair_err:
                        print(f"[VBF] Repair request failed: {repair_err}")

                # Repair failed or max retries, save checkpoint
                raise self._create_interrupt(
                    f"Step {step_id} failed after retries",
                    prompt, _save_path, plan, steps, step_results, i, allowed_skills, cause=e
                )

            except Exception as e:
                raise self._create_interrupt(
                    f"Unexpected error at step {step_id}",
                    prompt, _save_path, plan, steps, step_results, i, allowed_skills, cause=e
                )

        print(f"[VBF] Task completed: {len(step_results)} steps executed")
        return {"prompt": prompt, "step_results": step_results, "plan": plan}

    async def _start_blender_headless(self) -> None:
        """Start Blender in headless mode with VBF server."""
        import subprocess
        env = os.environ.copy()
        env["VBF_WS_HOST"] = self.host
        env["VBF_WS_PORT"] = str(self.port)
        subprocess.Popen(
            [self.blender_path, "-b", "-P", self.start_script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

    # --- Plan generation (via adapter) ---

    async def _plan_skill_task(self, prompt: str, allowed_skills: List[str],
                                save_path: str) -> Tuple[Dict, List]:
        """Generate skill plan via adapter with checkpoint on failure."""
        try:
            # The adapter's build_system_prompt() includes all skills from
            # SkillRegistry (loaded via Blender RPC). format_messages() wraps
            # it with the user's modeling prompt.
            adapter = await self._ensure_adapter()
            raw_plan = await self._call_plan_with_format_retry(
                adapter,
                prompt,
                skills_subset=allowed_skills,
            )

            # First pass normalization.
            try:
                plan = normalize_plan(raw_plan)
                steps = validate_plan_structure(plan)
            except ValueError as e:
                # Common model failure: returns only planning-time pseudo tool steps
                # (e.g., load_skill) or invalid refs. Retry once with stricter constraints.
                msg = str(e).lower()
                if not any(
                    token in msg
                    for token in [
                        "no executable steps",
                        "invalid_ref_schema",
                        "unknown_ref_step",
                        "forward_ref_step",
                    ]
                ):
                    raise
                repair_prompt = (
                    f"{prompt}\n\n"
                    "IMPORTANT:\n"
                    "- Return ONLY executable Blender skills in steps[].\n"
                    "- Do NOT use load_skill as a step skill.\n"
                    "- Every step must have a valid skill name and args object.\n"
                    "- Ensure at least one executable step is present.\n"
                    "- Use ONLY $ref paths in this format: step_<id>.data.<field> or <id>.data.<field>.\n"
                    "- Never use scene.objects[...] as a $ref target.\n"
                    "- For set_parent and other relationship steps, NEVER hardcode object names; use $ref from previous creation step results.\n"
                    "- If an object is referenced, it must be created in an earlier step."
                )
                repaired_raw_plan = await self._call_plan_with_format_retry(
                    adapter,
                    repair_prompt,
                    skills_subset=allowed_skills,
                )
                plan = normalize_plan(repaired_raw_plan)
                steps = validate_plan_structure(plan)

            return plan, steps
        except ValueError as e:
            if "not configured" in str(e):
                raise self._create_interrupt(
                    "LLM not configured. Set VBF_LLM_BASE_URL/API_KEY/MODEL",
                    prompt, save_path,
                    allowed_skills=allowed_skills, cause=e
                )
            raise self._create_interrupt(
                f"Plan generation failed: {e}",
                prompt, save_path, allowed_skills=allowed_skills, cause=e
            )

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
        """Execute task with closed-loop feedback control.

        Key differences from run_task():
        1. Capture scene state BEFORE planning and inject into prompt
        2. Validate each skill execution with lightweight GeometryDelta rules
        3. Trigger LLM analysis at stage boundaries
        4. Replan locally from failure point when quality/validation fails
        """
        from .feedback_control import ClosedLoopControl
        from .geometry_capture import IncrementalSceneCapture, CaptureLevel

        await self.ensure_connected()

        _save_path = save_state_path or self._default_save_path
        os.makedirs(os.path.dirname(_save_path), exist_ok=True)

        if not self._is_llm_enabled():
            raise self._create_interrupt(
                "LLM not configured. Set VBF_LLM_BASE_URL/API_KEY/MODEL",
                prompt, _save_path
            )

        allowed_skills = await self.list_skills()
        if not allowed_skills:
            raise self._create_interrupt(
                "No skills returned from Blender addon. Check if VBF addon is enabled",
                prompt, _save_path
            )

        if resume_state_path and os.path.exists(resume_state_path):
            print(f"[VBF-Feedback] Resuming from: {resume_state_path}")
            saved = TaskState.load(resume_state_path)
            plan = saved.plan
            steps = saved.steps
            step_results = saved.step_results
            i = saved.current_step_index
        else:
            # Apply style template to prompt (same behavior as run_task)
            if style:
                style_manager = get_style_manager()
                if style_manager.style_exists(style):
                    styled_prompt = style_manager.apply_style_to_prompt(style, prompt)
                    print(f"[VBF-Feedback] Using style: {style}")
                else:
                    available = ", ".join(style_manager.list_styles()[:5])
                    print(f"[VBF-Feedback] Warning: Unknown style '{style}'. Available: {available}...")
                    styled_prompt = prompt
            else:
                styled_prompt = prompt

            print("[VBF-Feedback] Capturing current scene state...")
            scene = await self.capture_scene_state()
            print(f"[VBF-Feedback] Scene has {len(scene._objects)} objects")
            two_stage_mode = self._should_use_two_stage_planning(styled_prompt, allowed_skills)
            scene_aware_prompt = self._inject_scene_context(
                styled_prompt,
                scene,
                max_objects=15 if two_stage_mode else None,
            )
            plan, steps = await self._plan_skill_task_auto(
                scene_aware_prompt,
                allowed_skills,
                _save_path,
            )
            step_results = {}
            i = 0
            print(f"[VBF-Feedback] Generated plan with {len(steps)} steps")

        max_replans = int(plan.get("execution", {}).get("max_replans", 5))
        replan_count = 0
        loop_guard_repeat_threshold = 2
        last_replan_fingerprint: Optional[str] = None
        consecutive_replan_hits = 0
        forced_retry_used: Dict[str, bool] = {}

        loop = ClosedLoopControl(
            client=self,
            enable_auto_check=enable_auto_check,
            enable_llm_feedback=enable_llm_feedback,
            capture_level=CaptureLevel.LIGHT,
            task_prompt=prompt,
        )
        scene_capture = IncrementalSceneCapture(self)

        while i < len(steps):
            step = steps[i]
            step_id = step.get("step_id", f"step_{i:03d}")

            decision, post_state = await loop.execute_with_feedback(step, step_results, scene_capture)

            if post_state:
                # Keep capture cache warm for next-step delta computation.
                scene_capture._cache.update(post_state)

            if decision.action in {"replan", "checkpoint"}:
                replan_count += 1
                if replan_count > max_replans:
                    raise self._create_interrupt(
                        f"Exceeded max replans ({max_replans}) at step {step_id}",
                        prompt,
                        _save_path,
                        plan=plan,
                        steps=steps,
                        step_results=step_results,
                        current_index=i,
                        allowed_skills=allowed_skills,
                    )

                reason = decision.detail.get("reason", decision.action)
                replan_from_idx = i
                feedback_detail = dict(decision.detail or {})
                failing_skill = feedback_detail.get("skill") or step.get("skill") or "unknown"
                validation = getattr(decision, "validation", None)
                error_signature = feedback_detail.get("error") or (
                    validation.message if validation else ""
                )
                replan_fingerprint = self._build_replan_fingerprint(
                    reason=reason,
                    skill=failing_skill,
                    error_text=error_signature,
                )

                if replan_fingerprint == last_replan_fingerprint:
                    consecutive_replan_hits += 1
                else:
                    last_replan_fingerprint = replan_fingerprint
                    consecutive_replan_hits = 1

                # For stage-boundary quality failures, roll back to the beginning of the
                # poor-quality stage so draft artifacts do not leak into subsequent stages.
                if decision.action == "checkpoint":
                    rollback_step_id = decision.detail.get("rollback_step_id")
                    if rollback_step_id:
                        rollback_resp = await self.rollback_to_step(rollback_step_id)
                        if rollback_resp.get("ok"):
                            rollback_idx = next(
                                (idx for idx, s in enumerate(steps) if s.get("step_id") == rollback_step_id),
                                None,
                            )
                            if rollback_idx is not None and rollback_idx <= i:
                                rolled_back_steps = steps[rollback_idx:i]
                                for rolled_step in rolled_back_steps:
                                    sid = rolled_step.get("step_id")
                                    if sid:
                                        step_results.pop(sid, None)
                                scene_capture.invalidate_cache()
                                replan_from_idx = rollback_idx
                                feedback_detail["rolled_back_to_step"] = rollback_step_id
                                feedback_detail["rolled_back_to_index"] = rollback_idx
                                feedback_detail["rolled_back_count"] = len(rolled_back_steps)
                                print(
                                    f"[VBF-Feedback] Checkpoint rollback to {rollback_step_id} "
                                    f"(cleared {len(rolled_back_steps)} steps)"
                                )
                            else:
                                print(
                                    f"[VBF-Feedback] Rollback step {rollback_step_id} not found in current plan, "
                                    "replanning without rollback index shift"
                                )
                        else:
                            print(
                                f"[VBF-Feedback] Rollback to {rollback_step_id} failed: "
                                f"{rollback_resp.get('error', 'unknown')}"
                            )

                force_corrective_retry = False
                loop_guard_hit = consecutive_replan_hits >= loop_guard_repeat_threshold
                if loop_guard_hit:
                    if not forced_retry_used.get(replan_fingerprint, False):
                        forced_retry_used[replan_fingerprint] = True
                        force_corrective_retry = True
                    else:
                        diagnostics = {
                            "loop_guard": {
                                "hit": True,
                                "replan_fingerprint": replan_fingerprint,
                                "replan_reason": reason,
                                "failing_skill": failing_skill,
                                "error_signature": self._build_error_signature(error_signature),
                                "consecutive_hits": consecutive_replan_hits,
                            }
                        }
                        raise self._create_interrupt(
                            f"Loop guard interrupted repeated replans at step {step_id}",
                            prompt,
                            _save_path,
                            plan=plan,
                            steps=steps,
                            step_results=step_results,
                            current_index=i,
                            allowed_skills=allowed_skills,
                            diagnostics=diagnostics,
                        )

                feedback_detail["replan_reason"] = reason
                feedback_detail["replan_fingerprint"] = replan_fingerprint
                feedback_detail["loop_guard_hit"] = loop_guard_hit
                feedback_detail["loop_guard_force_corrective"] = force_corrective_retry
                print(
                    "[VBF] "
                    f"replan_reason={reason} "
                    f"replan_fingerprint={replan_fingerprint} "
                    f"loop_guard_hit={str(loop_guard_hit).lower()}"
                )
                print(
                    f"[VBF-Feedback] Triggering local replan at {step_id} "
                    f"(reason={reason}, from_index={replan_from_idx})"
                )
                plan, new_steps = await self._replan_from_step(
                    prompt=prompt,
                    fail_idx=replan_from_idx,
                    steps=steps,
                    step_results=step_results,
                    allowed_skills=allowed_skills,
                    save_path=_save_path,
                    feedback_detail=feedback_detail,
                    replan_fingerprint=replan_fingerprint,
                    forced_corrective=force_corrective_retry,
                )
                steps = steps[:replan_from_idx] + new_steps
                i = replan_from_idx
                print(f"[VBF-Feedback] Replan produced {len(new_steps)} steps ({len(steps)} total)")
                continue

            # Default advance for continue or unknown actions
            last_replan_fingerprint = None
            consecutive_replan_hits = 0
            i += 1

        print(f"[VBF-Feedback] Task completed: {len(step_results)} steps")
        return {"prompt": prompt, "step_results": step_results, "plan": plan}

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
        """Generate a new local plan from failure/checkpoint boundary."""
        import json

        adapter = await self._ensure_adapter()
        scene = await self.capture_scene_state()

        failed_step = steps[fail_idx] if fail_idx < len(steps) else {}
        failed_step_id = failed_step.get("step_id", "unknown")
        failed_skill = failed_step.get("skill", "unknown")
        failed_result = step_results.get(failed_step_id, {})
        failure_signature = (feedback_detail or {}).get("error", "")

        corrective_block = ""
        if forced_corrective:
            corrective_block = f"""
7) LOOP-GUARD: The prior replans repeated the same failure fingerprint: {replan_fingerprint}.
   You MUST avoid repeating that failure mode.
8) Keep this replan compact (<= 12 steps), prioritize object creation + valid refs first.
9) If you need relationships (set_parent/constraints), ensure all referenced objects are created earlier in this same replan.
10) Return plain JSON only, no markdown code fences.
"""

        replan_prompt = f"""REPLAN FROM CURRENT SCENE STATE

User goal (must be satisfied semantically):
{prompt}

Current scene state:
{self._scene_to_prompt_text(scene, max_objects=20)}

Current index: {fail_idx}
Current step id: {failed_step_id}
Current skill: {failed_skill}
Current step result:
{json.dumps(failed_result, indent=2, ensure_ascii=False)[:2000]}

Current failure signature:
{failure_signature[:1200]}

Feedback trigger details:
{json.dumps(feedback_detail or {}, indent=2, ensure_ascii=False)[:2000]}

Completed steps so far:
{json.dumps(step_results, indent=2, ensure_ascii=False)[:3000]}

Remaining old steps (for reference only):
{json.dumps(steps[fail_idx + 1:], indent=2, ensure_ascii=False)[:1200]}

Allowed skills:
{json.dumps(allowed_skills[:200], ensure_ascii=False)}

Instructions:
1) Continue from the current scene state (do not restart from scratch).
2) Ensure final output matches the user goal. Example failure to avoid: returning only a cube when goal is a smartphone.
3) Prefer local corrective steps first, then continue normal modeling flow.
4) Return valid plan JSON with a `steps` array.
5) For relationship steps (set_parent/constraints/material assignment), NEVER hardcode object names (e.g. "CameraModule"). Use `$ref` to previous step outputs.
6) If an object is referenced, ensure it is explicitly created earlier in the same plan.
{corrective_block}
"""
        replan_subset = allowed_skills[:140] if len(allowed_skills) > 140 else allowed_skills
        raw_plan = await self._call_plan_with_format_retry(
            adapter,
            replan_prompt,
            skills_subset=replan_subset,
        )
        plan = normalize_plan(raw_plan)
        new_steps = validate_plan_structure(plan)
        return plan, new_steps

    def _inject_scene_context(
        self,
        prompt: str,
        scene: SceneState,
        max_objects: Optional[int] = None,
    ) -> str:
        """Inject scene state into planning prompt."""
        scene_text = self._scene_to_prompt_text(scene, max_objects=max_objects)
        return f"""Current Blender scene state:
{scene_text}

--- USER REQUEST ---
{prompt}

Planning constraints:
- The final model must satisfy the user request semantically, not just produce arbitrary primitives.
- Generate coherent, connected modeling steps toward a complete result.
"""
