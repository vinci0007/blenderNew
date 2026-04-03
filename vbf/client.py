import asyncio
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple

from .jsonrpc_ws import JsonRpcWebSocketClient
from .jsonrpc_ws import JsonRpcError
from .llm_openai_compat import OpenAICompatLLM, load_openai_compat_config, LLMError
from .vibe_protocol import resolve_refs, merge_step_results_for_prompt
from .task_state import TaskState, TaskInterruptedError


class VBFClient:
    """
    Reusable client module for other Python projects.
    - Connect to Blender Addon WS server (JSON-RPC)
    - Execute High-Level Skills (no direct bmesh/bpy complex ops)
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        blender_path: Optional[str] = None,
        start_script_path: Optional[str] = None,
    ):
        self.host = host or os.getenv("VBF_WS_HOST", "127.0.0.1")
        env_port = os.getenv("VBF_WS_PORT", "8006")
        self.port = int(port) if port is not None else int(env_port)
        self.blender_path = blender_path or os.getenv("BLENDER_PATH") or "blender"

        # Default: /blender_provider/start_vbf_blender.py relative to repo root.
        if start_script_path:
            self.start_script_path = start_script_path
        else:
            repo_root = os.path.dirname(os.path.dirname(__file__))
            self.start_script_path = os.path.join(repo_root, "blender_provider", "start_vbf_blender.py")

        self._ws = JsonRpcWebSocketClient(f"ws://{self.host}:{self.port}")

    async def ensure_connected(self, timeout_s: float = 30.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_s
        last_err: Optional[BaseException] = None

        while asyncio.get_running_loop().time() < deadline:
            try:
                await self._ws.connect()
                return
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.5)

        # If not reachable, start Blender in background and retry.
        await self._start_blender_headless()
        deadline2 = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline2:
            try:
                await self._ws.connect()
                return
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.5)

        raise TimeoutError(f"Unable to connect to Blender VBF WS at {self.host}:{self.port}") from last_err

    async def execute_skill(self, skill: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = await self._ws.call(
            method="vbf.execute_skill",
            params={"skill": skill, "args": args or {}},
        )
        # Expected: {"ok": true/false, "data": {...}} OR raises JsonRpcError on error.
        return result

    def _load_llm(self) -> Optional[OpenAICompatLLM]:
        cfg = load_openai_compat_config()
        if not cfg:
            return None
        # Explicit opt-out: use_llm=false in config disables LLM entirely.
        if not cfg.use_llm:
            return None
        return OpenAICompatLLM(cfg)

    def _llm_enabled(self) -> bool:
        """Return True if LLM is configured AND use_llm is not disabled."""
        cfg = load_openai_compat_config()
        if not cfg:
            return False
        return bool(cfg.use_llm)

    async def _llm_json(self, llm: OpenAICompatLLM, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        # urllib-based implementation is blocking; run in a thread.
        return await asyncio.to_thread(llm.chat_json, messages)

    def _build_radio_skill_plan_messages(self, prompt: str) -> List[Dict[str, str]]:
        # Important: enforce JSON-only output from the model.
        skills = [
            "create_beveled_box",
            "spatial_query",
            "create_nested_cones",
            "create_primitive",
            "boolean_tool",
            "apply_transform",
            "api_validator",
        ]

        schema = {
            "vbf_version": "string",
            "plan_id": "string",
            "execution": {"max_retries_per_step": "number"},
            "steps": [
                {
                    "step_id": "string",
                    "skill": "string",
                    "args": {"any": "json-serializable"},
                    "on_success": {"store_as": {"alias_name": "step_return_json_path"}}
                }
            ],
        }

        user = {
            "prompt": prompt,
            "task_type": "radio_task",
            "required_skills": skills,
            "instructions": [
                "Decompose the task into atomic skill steps using ONLY Blender skills.",
                "Never output bpy/bmesh code; only output skills_plan JSON.",
                "Use $ref to reference previous step outputs, e.g. {\"$ref\":\"body.data.object_name\"}.",
                "Use EXACT step_id values for the RadioTask: body, top_center, antenna, cutter, trimmed.",
                "For spatial_query, use query_type=\"top_center\" and use its returned location as base for antenna.",
                "For boolean trimming, create a small cube cutter above the antenna top, then boolean_tool difference.",
            ],
            "skills_plan_schema": schema,
            "must_return_only_json": True,
        }

        system_msg = (
            "You are the Vibe Protocol planner for Vibe-Blender-Flow. "
            "You MUST return a single valid JSON object that matches the provided skills_plan_schema exactly. "
            "Return JSON only (no markdown, no surrounding text). "
            "Validate step.skill names against required_skills."
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json_dumps(user)},
        ]

    def _build_radio_repair_messages(
        self,
        prompt: str,
        failed_step_id: str,
        error_message: str,
        error_traceback: str,
        original_plan: Dict[str, Any],
        step_results: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        schema = {
            "vbf_version": "string",
            "plan_id": "string",
            "repair": {"replace_from_step_id": "string"},
            "execution": {"max_retries_per_step": "number"},
            "steps": [
                {"step_id": "string", "skill": "string", "args": {"any": "json-serializable"}}
            ],
        }
        compact_steps = merge_step_results_for_prompt(step_results)

        user = {
            "prompt": prompt,
            "task_type": "radio_task",
            "failed_step_id": failed_step_id,
            "error_message": error_message,
            "error_traceback": error_traceback,
            "original_plan": {"plan_id": original_plan.get("plan_id"), "steps": original_plan.get("steps")},
            "executed_step_outputs": compact_steps,
            "repair_plan_schema": schema,
            "instructions": [
                "Return a single JSON object that matches repair_plan_schema exactly.",
                "Keep step_id for the replace_from_step_id equal to failed_step_id, and start steps from that point.",
                "Fix args to resolve the cause of the failure. You may adjust object names, dimensions, or query types, "
                "but keep the overall RadioTask structure.",
                "Use $ref wherever you need coordinates/object names from previous successful steps.",
            ],
            "must_return_only_json": True,
        }
        system_msg = (
            "You are the Vibe Protocol auto-repair planner. "
            "You MUST return JSON only that matches the provided repair_plan_schema exactly."
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json_dumps(user)},
        ]

    async def _plan_radio_task(self, prompt: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        llm = self._load_llm()
        if not llm:
            # fallback: not using LLM
            return {}, self._deterministic_radio_steps()

        messages = self._build_radio_skill_plan_messages(prompt)
        plan = await self._llm_json(llm, messages)
        if not isinstance(plan, dict) or "steps" not in plan:
            raise ValueError("LLM plan missing 'steps'")
        steps = plan["steps"]
        if not isinstance(steps, list):
            raise ValueError("LLM plan 'steps' must be a list")
        return plan, steps

    async def list_skills(self) -> List[str]:
        """
        Ask Blender addon for the current allowed skills.
        """
        resp = await self._ws.call(method="vbf.list_skills", params={})
        if not isinstance(resp, dict):
            return []
        data = resp.get("data") or {}
        skills = data.get("skills") or []
        return skills if isinstance(skills, list) else []

    async def describe_skills(self, skill_names: List[str]) -> Optional[Dict[str, Any]]:
        """
        Ask Blender addon for skill parameter schemas.
        Returns None if addon doesn't support vbf.describe_skills (fallback).
        """
        try:
            resp = await self._ws.call(method="vbf.describe_skills", params={"skill_names": skill_names})
            if not isinstance(resp, dict):
                return None
            data = resp.get("data") or {}
            return data.get("skills") or None
        except Exception:
            return None

    def _build_skill_plan_messages(self, prompt: str, allowed_skills: List[str], skill_schemas: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        # Generic plan schema for user-controlled modeling.
        schema = {
            "vbf_version": "string",
            "plan_id": "string",
            "execution": {"max_retries_per_step": "number"},
            "controls": {
                "max_steps": "number",
                "allow_low_level_gateway": "boolean",
                "require_ops_introspect_before_invoke": "boolean"
            },
            "steps": [
                {
                    "step_id": "string",
                    "stage": "discover|blockout|boolean|detail|bevel|normal_fix|accessories|material|finalize",
                    "skill": "string",
                    "args": {"any": "json-serializable"},
                    "on_success": {
                        "store_as": {
                            "alias_name": "string",
                            "step_return_json_path": "string"
                        }
                    },
                }
            ],
        }

        user = {
            "prompt": prompt,
            "task_type": "user_modeling_task",
            "allowed_skills": [
                {"name": name, **skill_schemas[name]} if skill_schemas is not None and name in skill_schemas else {"name": name}
                for name in allowed_skills
            ] if skill_schemas is not None else allowed_skills,
            "skills_plan_schema": schema,
            "must_return_only_json": True,
            "instructions": [
                "Decompose the user request into atomic Blender skills steps.",
                "ONLY use skills from allowed_skills; never invent skills.",
                "Never output any bpy/bmesh code. ONLY output the skills_plan JSON.",
                "Use $ref to reference prior step outputs: {\"$ref\":\"<step_id>.data.<key>\"}.",
                "If you use on_success.store_as, then later you may reference by alias name as: {\"$ref\":\"<alias_name>.data.<key>\"}.",
                "If the stored value is not an object/dict, reference it as {\"$ref\":\"<alias_name>.data.value\"}.",
                "Prefer coordinate alignment by using move_object_anchor_to_point rather than doing arithmetic in $ref.",
                "For unknown operators, first use ops_search; then use ops_introspect on candidate operator_id; then call ops_invoke.",
                "Stage order must be monotonic: discover -> blockout -> boolean -> detail -> bevel -> normal_fix -> accessories -> material -> finalize.",
            ],
        }

        system_msg = (
            "You are the Vibe Protocol planner for Vibe-Blender-Flow. "
            "You MUST return a single valid JSON object that matches the provided skills_plan_schema exactly. "
            "Return JSON only (no markdown, no surrounding text)."
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json_dumps(user)},
        ]

    def _build_skill_repair_messages(
        self,
        prompt: str,
        failed_step_id: str,
        error_message: str,
        error_traceback: str,
        original_plan: Dict[str, Any],
        step_results: Dict[str, Dict[str, Any]],
        allowed_skills: List[str],
        skill_schemas: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        schema = {
            "vbf_version": "string",
            "plan_id": "string",
            "repair": {"replace_from_step_id": "string"},
            "execution": {"max_retries_per_step": "number"},
            "steps": [
                {"step_id": "string", "skill": "string", "args": {"any": "json-serializable"}}
            ],
        }
        compact_steps = merge_step_results_for_prompt(step_results)
        user = {
            "prompt": prompt,
            "task_type": "user_modeling_task",
            "failed_step_id": failed_step_id,
            "error_message": error_message,
            "error_traceback": error_traceback,
            "allowed_skills": [
                {"name": name, **skill_schemas[name]} if skill_schemas is not None and name in skill_schemas else {"name": name}
                for name in allowed_skills
            ] if skill_schemas is not None else allowed_skills,
            "original_plan": {"plan_id": original_plan.get("plan_id"), "steps": original_plan.get("steps")},
            "executed_step_outputs": compact_steps,
            "repair_plan_schema": schema,
            "must_return_only_json": True,
            "instructions": [
                "Return a single JSON object that matches repair_plan_schema exactly.",
                "Set repair.replace_from_step_id equal to failed_step_id and start steps from that point.",
                "Fix the args to resolve the failure cause (dimensions, object names, query_type, etc.).",
                "Use ONLY skills from allowed_skills.",
                "Use $ref wherever you need coordinates/object names from previous successful steps.",
            ],
        }
        system_msg = (
            "You are the Vibe Protocol auto-repair planner. "
            "You MUST return JSON only that matches the provided repair_plan_schema exactly."
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json_dumps(user)},
        ]

    async def _plan_skill_task(
        self,
        prompt: str,
        allowed_skills: List[str],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        llm = self._load_llm()
        if not llm:
            # fallback: deterministic radio-like demo
            return {}, self._deterministic_radio_steps()

        skill_schemas = await self.describe_skills(allowed_skills)
        messages = self._build_skill_plan_messages(prompt, allowed_skills, skill_schemas=skill_schemas)
        plan = await self._llm_json(llm, messages)
        if not isinstance(plan, dict) or "steps" not in plan:
            raise ValueError("LLM plan missing 'steps'")
        steps = plan["steps"]
        if not isinstance(steps, list):
            raise ValueError("LLM plan 'steps' must be a list")

        # Basic validation early to avoid sending garbage to Blender.
        for idx, st in enumerate(steps):
            if not isinstance(st, dict):
                raise ValueError(f"LLM plan step[{idx}] must be an object")
            if "step_id" not in st or "skill" not in st or "args" not in st:
                raise ValueError(f"LLM plan step[{idx}] missing required fields")
            if st.get("skill") not in allowed_skills:
                raise ValueError(f"LLM plan step[{idx}] uses unknown skill: {st.get('skill')}")
        return plan, steps

    @staticmethod
    def _extract_json_path_from_step(step_out: Dict[str, Any], json_path: str) -> Any:
        """
        step_out is {"ok": bool, "data": {...}}.
        json_path is usually like "data.location" or "data.object_name".
        """
        if not isinstance(json_path, str) or not json_path.strip():
            raise ValueError("step_return_json_path must be a non-empty string")

        path = json_path.strip()
        parts = [p for p in path.split(".") if p]
        if not parts:
            raise ValueError("Invalid json_path")

        node: Any = step_out
        # Allow roots: data/result
        if parts[0] in ("data", "result"):
            node = step_out.get("data", {}) if parts[0] in ("data", "result") else step_out
            parts = parts[1:]
        for p in parts:
            if not isinstance(node, dict):
                raise KeyError(f"Cannot access '{p}' on non-dict node")
            if p not in node:
                raise KeyError(f"Key '{p}' not found in step_out")
            node = node[p]
        return node

    def _deterministic_radio_steps(self) -> List[Dict[str, Any]]:
        # For fallback mode: use the same structure as the LLM plan.
        return [
            {
                "step_id": "body",
                "skill": "create_beveled_box",
                "args": {
                    "name": "radio_body",
                    "size": [1.0, 0.6, 0.5],
                    "location": [0.0, 0.0, 0.25],
                    "bevel_width": 0.04,
                    "bevel_segments": 3,
                },
            },
            {
                "step_id": "top_center",
                "skill": "spatial_query",
                "args": {"object_name": {"$ref": "body.data.object_name"}, "query_type": "top_center"},
            },
            {
                "step_id": "antenna",
                "skill": "create_nested_cones",
                "args": {
                    "name_prefix": "radio_antenna",
                    "base_location": {"$ref": "top_center.data.location"},
                    "layers": 4,
                    "base_radius": 0.06,
                    "top_radius": 0.006,
                    "height": 0.24,
                    "z_jitter": 0.0,
                },
            },
            {
                "step_id": "cutter",
                "skill": "create_primitive",
                "args": {
                    "primitive_type": "cube",
                    "name": "radio_antenna_cutter",
                    "size": [0.15, 0.15, 0.03],
                    # We can't do arithmetic in $ref; keep explicit values via apply_transform in future.
                    # For now, cutter is created near the antenna top using location from top_center + z offset.
                    # We'll approximate by adding 0.015 to z in a separate step if needed later.
                    "location": {"$ref": "top_center.data.location"},
                },
            },
            {
                "step_id": "trimmed",
                "skill": "boolean_tool",
                "args": {
                    "target_name": {"$ref": "antenna.data.object_name"},
                    "tool_name": {"$ref": "cutter.data.object_name"},
                    "operation": "difference",
                    "apply": True,
                    "delete_tool": True,
                },
            },
        ]

    async def run_radio_task(self, prompt: str = "复古收音机") -> Dict[str, Any]:
        await self.ensure_connected()

        # If no LLM is configured, fall back to deterministic RadioTask.
        # This keeps the project runnable without any external API keys.
        if self._load_llm() is None:
            body = await self.execute_skill(
                "create_beveled_box",
                {
                    "name": "radio_body",
                    "size": [1.0, 0.6, 0.5],
                    "location": [0.0, 0.0, 0.25],
                    "bevel_width": 0.04,
                    "bevel_segments": 3,
                },
            )
            body_name = body["data"]["object_name"]

            top = await self.execute_skill(
                "spatial_query",
                {"object_name": body_name, "query_type": "top_center"},
            )
            top_loc = top["data"]["location"]

            antenna = await self.execute_skill(
                "create_nested_cones",
                {
                    "name_prefix": "radio_antenna",
                    "base_location": top_loc,
                    "layers": 4,
                    "base_radius": 0.06,
                    "top_radius": 0.006,
                    "height": 0.24,
                    "z_jitter": 0.0,
                },
            )
            antenna_name = antenna["data"]["object_name"]

            cut_thickness = 0.03
            cutter_loc = [top_loc[0], top_loc[1], top_loc[2] + cut_thickness * 0.5]
            cutter = await self.execute_skill(
                "create_primitive",
                {
                    "primitive_type": "cube",
                    "name": "radio_antenna_cutter",
                    "size": [0.15, 0.15, cut_thickness],
                    "location": cutter_loc,
                },
            )
            cutter_name = cutter["data"]["object_name"]

            trimmed = await self.execute_skill(
                "boolean_tool",
                {
                    "target_name": antenna_name,
                    "tool_name": cutter_name,
                    "operation": "difference",
                    "apply": True,
                    "delete_tool": True,
                },
            )

            return {
                "prompt": prompt,
                "body": body_name,
                "antenna": antenna_name,
                "trimmed": trimmed.get("data", {}),
            }

        plan, steps = await self._plan_radio_task(prompt)

        # Keep only the plan-level retry configuration.
        max_retries_per_step = 2
        try:
            max_retries_per_step = int(plan.get("execution", {}).get("max_retries_per_step", 2))
        except Exception:
            pass

        step_results: Dict[str, Dict[str, Any]] = {}
        attempt_counts: Dict[str, int] = {}

        i = 0
        while i < len(steps):
            step = steps[i]
            step_id = step.get("step_id")
            skill = step.get("skill")
            args = step.get("args") or {}
            if not step_id or not isinstance(step_id, str):
                raise ValueError("Invalid step_id in plan")
            if not skill or not isinstance(skill, str):
                raise ValueError("Invalid skill in plan")

            attempt_counts[step_id] = attempt_counts.get(step_id, 0) + 1
            if attempt_counts[step_id] > 1 + max_retries_per_step:
                raise RuntimeError(f"Step {step_id} exceeded max retries ({max_retries_per_step})")

            try:
                resolved_args = resolve_refs(args, step_results)
                if not isinstance(resolved_args, dict):
                    raise ValueError(f"Resolved args must be an object/dict. step_id={step_id} skill={skill}")
                out = await self.execute_skill(skill, resolved_args)
                step_results[step_id] = out
                i += 1
            except JsonRpcError as e:
                err_trace = ""
                if e.data and isinstance(e.data, dict):
                    tb = e.data.get("traceback")
                    if tb:
                        err_trace = tb

                step_results[step_id] = {"ok": False, "error": {"message": str(e), "traceback": err_trace}}

                if attempt_counts[step_id] > 1 + max_retries_per_step:
                    raise

                repair_messages = self._build_radio_repair_messages(
                    prompt=prompt,
                    failed_step_id=step_id,
                    error_message=e.message,
                    error_traceback=err_trace or "No traceback field",
                    original_plan=plan,
                    step_results=step_results,
                )

                llm = self._load_llm()
                if not llm:
                    raise

                repair_plan = await self._llm_json(llm, repair_messages)
                if not isinstance(repair_plan, dict) or "steps" not in repair_plan:
                    raise ValueError("LLM repair_plan missing 'steps'")
                repair_steps = repair_plan["steps"]
                if not isinstance(repair_steps, list):
                    raise ValueError("LLM repair_plan 'steps' must be a list")

                replace_from = repair_plan.get("repair", {}).get("replace_from_step_id")
                if replace_from and replace_from != step_id:
                    # Still allow, but reset to i = index of replace_from if possible.
                    # For now, enforce equality to keep references stable.
                    raise ValueError(f"LLM repair replace_from_step_id mismatch: got {replace_from}, expected {step_id}")

                # Replace the remaining steps starting from current failed step.
                steps = steps[:i] + repair_steps
                # Keep i unchanged so we retry with repaired step_id at the same index.
            except Exception as e:
                step_results[step_id] = {"ok": False, "error": {"message": str(e)}}
                raise

        def _get(step_id: str) -> Optional[str]:
            payload = step_results.get(step_id) or {}
            data = payload.get("data") or {}
            v = data.get("object_name")
            return v if isinstance(v, str) else None

        return {
            "prompt": prompt,
            "body": _get("body"),
            "antenna": _get("antenna"),
            "cutter": _get("cutter"),
            "trimmed": (step_results.get("trimmed") or {}).get("data", {}),
            "step_results": step_results,
        }

    async def run_task(self, prompt: str, resume_state_path: Optional[str] = None, save_state_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Generic user-controlled modeling task.

        Args:
            prompt: Natural language modeling request.
            resume_state_path: Path to a previously saved .json state file to resume from.
            save_state_path: Path to save interrupted state when LLM fails. Defaults to
                             vbf/config/task_state.json.
        """
        await self.ensure_connected()

        # Check LLM availability upfront — do NOT silently fall back to radio demo.
        if not self._llm_enabled():
            print("[VBF] LLM not configured or disabled. Set VBF_LLM_BASE_URL/API_KEY/MODEL or vbf/config/llm.json.")
            print("[VBF] Falling back to RadioTask demo.")
            return await self.run_radio_task(prompt)

        allowed_skills = await self.list_skills()
        if not allowed_skills:
            print("[VBF] No skills returned from Blender addon. Falling back to RadioTask demo.")
            return await self.run_radio_task(prompt)

        llm = self._load_llm()
        # llm should not be None here since _llm_enabled() passed, but guard anyway.
        if llm is None:
            print("[VBF] LLM init failed. Falling back to RadioTask demo.")
            return await self.run_radio_task(prompt)

        _save_path = save_state_path or os.path.join(os.path.dirname(__file__), "config", "task_state.json")

        # --- Resume from saved state ---
        if resume_state_path and os.path.exists(resume_state_path):
            print(f"[VBF] Resuming from: {resume_state_path}")
            saved = TaskState.load(resume_state_path)
            plan = saved.plan
            steps = saved.steps
            step_results = saved.step_results
            start_index = saved.current_step_index
            allowed_skills = saved.allowed_skills
            skill_schemas = saved.skill_schemas
            print(f"[VBF] Step {start_index}/{len(steps)}, completed: {list(step_results.keys())}")
        else:
            skill_schemas = await self.describe_skills(allowed_skills)
            try:
                plan, steps = await self._plan_skill_task(prompt, allowed_skills)
            except LLMError as e:
                print(f"[VBF] LLM planning failed: {e}")
                raise
            step_results: Dict[str, Dict[str, Any]] = {}
            start_index = 0

        max_retries_per_step = 2
        try:
            max_retries_per_step = int(plan.get("execution", {}).get("max_retries_per_step", 2))
        except Exception:
            pass

        controls = plan.get("controls", {}) if isinstance(plan, dict) else {}
        max_steps = int(controls.get("max_steps", 80)) if isinstance(controls, dict) else 80
        allow_low_level_gateway = bool(controls.get("allow_low_level_gateway", False)) if isinstance(controls, dict) else False
        require_ops_introspect = bool(controls.get("require_ops_introspect_before_invoke", True)) if isinstance(controls, dict) else True

        attempt_counts: Dict[str, int] = {}
        introspected_ops: set[str] = set()
        stage_order = {
            "discover": 0,
            "blockout": 1,
            "boolean": 2,
            "detail": 3,
            "bevel": 4,
            "normal_fix": 5,
            "accessories": 6,
            "material": 7,
            "finalize": 8,
        }
        current_stage_rank = -1

        i = start_index
        while i < len(steps):
            if len(steps) > max_steps:
                raise RuntimeError(f"Plan exceeds max_steps control: {len(steps)} > {max_steps}")

            step = steps[i]
            step_id = step.get("step_id")
            skill = step.get("skill")
            args = step.get("args") or {}
            stage = step.get("stage", "detail")

            if not step_id or not isinstance(step_id, str):
                raise ValueError("Invalid step_id in plan")
            if not skill or not isinstance(skill, str):
                raise ValueError("Invalid skill in plan")
            if skill not in allowed_skills:
                raise ValueError(f"Skill not allowed: {skill}")
            if not isinstance(args, dict):
                raise ValueError(f"Plan args must be an object for step_id={step_id}")
            if not isinstance(stage, str) or stage not in stage_order:
                raise ValueError(f"Invalid stage for step_id={step_id}. Must be one of {list(stage_order.keys())}")
            if stage_order[stage] < current_stage_rank:
                raise ValueError(
                    f"Stage order violation at step_id={step_id}: "
                    f"{stage} cannot go backwards."
                )

            if skill in {"py_call", "py_set"} and not allow_low_level_gateway:
                raise ValueError(
                    f"Skill {skill} is blocked by controls.allow_low_level_gateway=false. "
                    "Use high-level skills / ops_* first."
                )

            attempt_counts[step_id] = attempt_counts.get(step_id, 0) + 1
            if attempt_counts[step_id] > 1 + max_retries_per_step:
                raise RuntimeError(f"Step {step_id} exceeded max retries ({max_retries_per_step})")

            try:
                resolved_args = resolve_refs(args, step_results)
                if not isinstance(resolved_args, dict):
                    raise ValueError(f"Resolved args must be an object/dict. step_id={step_id} skill={skill}")

                if skill == "ops_invoke" and require_ops_introspect:
                    operator_id = resolved_args.get("operator_id")
                    if not isinstance(operator_id, str):
                        raise ValueError("ops_invoke requires string operator_id")
                    if operator_id not in introspected_ops:
                        raise ValueError(
                            f"ops_invoke blocked: operator_id '{operator_id}' was not introspected first. "
                            "Call ops_introspect before ops_invoke."
                        )

                out = await self.execute_skill(skill, resolved_args)
                step_results[step_id] = out
                current_stage_rank = max(current_stage_rank, stage_order[stage])

                if skill == "ops_introspect":
                    op_id = resolved_args.get("operator_id")
                    if isinstance(op_id, str):
                        introspected_ops.add(op_id)

                on_success = step.get("on_success") or {}
                store_as = on_success.get("store_as") if isinstance(on_success, dict) else None
                if isinstance(store_as, dict):
                    alias_name = store_as.get("alias_name")
                    step_return_json_path = store_as.get("step_return_json_path")
                    if isinstance(alias_name, str) and isinstance(step_return_json_path, str) and step_return_json_path.strip():
                        extracted = self._extract_json_path_from_step(out, step_return_json_path)
                        alias_payload: Dict[str, Any]
                        if isinstance(extracted, dict):
                            alias_payload = {"ok": True, "data": extracted}
                        else:
                            alias_payload = {"ok": True, "data": {"value": extracted}}
                        step_results[alias_name] = alias_payload

                i += 1

            except JsonRpcError as e:
                err_trace = e.data.get("traceback") if isinstance(e.data, dict) else None
                step_results[step_id] = {"ok": False, "error": {"message": str(e), "traceback": err_trace or ""}}

                if attempt_counts[step_id] > 1 + max_retries_per_step:
                    raise

                try:
                    repair_messages = self._build_skill_repair_messages(
                        prompt=prompt,
                        failed_step_id=step_id,
                        error_message=e.message,
                        error_traceback=err_trace or "No traceback field",
                        original_plan=plan,
                        step_results=step_results,
                        allowed_skills=allowed_skills,
                        skill_schemas=skill_schemas,
                    )
                    repair_plan = await self._llm_json(llm, repair_messages)
                except LLMError as llm_err:
                    raise self._interrupt(
                        "LLM repair failed", step_id, i, _save_path,
                        prompt, plan, steps, step_results, allowed_skills, skill_schemas, llm_err,
                    ) from llm_err

                if not isinstance(repair_plan, dict) or "steps" not in repair_plan:
                    raise ValueError("LLM repair_plan missing 'steps'")

                repair_steps = repair_plan["steps"]
                if not isinstance(repair_steps, list):
                    raise ValueError("LLM repair_plan 'steps' must be a list")

                replace_from = repair_plan.get("repair", {}).get("replace_from_step_id")
                if replace_from and replace_from != step_id:
                    raise ValueError(f"LLM repair replace_from_step_id mismatch: got {replace_from}, expected {step_id}")

                steps = steps[:i] + repair_steps

            except LLMError as llm_err:
                raise self._interrupt(
                    "LLM failed", step_id, i, _save_path,
                    prompt, plan, steps, step_results, allowed_skills, skill_schemas, llm_err,
                ) from llm_err

            except Exception as e:
                err_trace = traceback.format_exc()
                step_results[step_id] = {"ok": False, "error": {"message": str(e), "traceback": err_trace}}

                if attempt_counts[step_id] > 1 + max_retries_per_step:
                    raise

                try:
                    repair_messages = self._build_skill_repair_messages(
                        prompt=prompt,
                        failed_step_id=step_id,
                        error_message=str(e),
                        error_traceback=err_trace,
                        original_plan=plan,
                        step_results=step_results,
                        allowed_skills=allowed_skills,
                        skill_schemas=skill_schemas,
                    )
                    repair_plan = await self._llm_json(llm, repair_messages)
                except LLMError as llm_err:
                    raise self._interrupt(
                        "LLM repair failed", step_id, i, _save_path,
                        prompt, plan, steps, step_results, allowed_skills, skill_schemas, llm_err,
                    ) from llm_err

                if not isinstance(repair_plan, dict) or "steps" not in repair_plan:
                    raise ValueError("LLM repair_plan missing 'steps'")
                repair_steps = repair_plan["steps"]
                if not isinstance(repair_steps, list):
                    raise ValueError("LLM repair_plan 'steps' must be a list")

                replace_from = repair_plan.get("repair", {}).get("replace_from_step_id")
                if replace_from and replace_from != step_id:
                    raise ValueError(f"LLM repair replace_from_step_id mismatch: got {replace_from}, expected {step_id}")

                steps = steps[:i] + repair_steps

        return {"prompt": prompt, "step_results": step_results, "plan": plan}

        plan, steps = await self._plan_skill_task(prompt, allowed_skills)

        # Fetch skill schemas for repair messages (same call as inside _plan_skill_task,
        # but we need the result here for repair context).
        skill_schemas = await self.describe_skills(allowed_skills)

        max_retries_per_step = 2
        try:
            max_retries_per_step = int(plan.get("execution", {}).get("max_retries_per_step", 2))
        except Exception:
            pass

        controls = plan.get("controls", {}) if isinstance(plan, dict) else {}
        max_steps = int(controls.get("max_steps", 80)) if isinstance(controls, dict) else 80
        allow_low_level_gateway = bool(controls.get("allow_low_level_gateway", False)) if isinstance(controls, dict) else False
        require_ops_introspect = bool(controls.get("require_ops_introspect_before_invoke", True)) if isinstance(controls, dict) else True

        step_results: Dict[str, Dict[str, Any]] = {}
        attempt_counts: Dict[str, int] = {}
        introspected_ops: set[str] = set()
        stage_order = {
            "discover": 0,
            "blockout": 1,
            "boolean": 2,
            "detail": 3,
            "bevel": 4,
            "normal_fix": 5,
            "accessories": 6,
            "material": 7,
            "finalize": 8,
        }
        current_stage_rank = -1

        i = 0
        while i < len(steps):
            if len(steps) > max_steps:
                raise RuntimeError(f"Plan exceeds max_steps control: {len(steps)} > {max_steps}")

            step = steps[i]
            step_id = step.get("step_id")
            skill = step.get("skill")
            args = step.get("args") or {}
            stage = step.get("stage", "detail")

            if not step_id or not isinstance(step_id, str):
                raise ValueError("Invalid step_id in plan")
            if not skill or not isinstance(skill, str):
                raise ValueError("Invalid skill in plan")
            if skill not in allowed_skills:
                raise ValueError(f"Skill not allowed: {skill}")
            if not isinstance(args, dict):
                raise ValueError(f"Plan args must be an object for step_id={step_id}")
            if not isinstance(stage, str) or stage not in stage_order:
                raise ValueError(f"Invalid stage for step_id={step_id}. Must be one of {list(stage_order.keys())}")
            if stage_order[stage] < current_stage_rank:
                raise ValueError(
                    f"Stage order violation at step_id={step_id}: "
                    f"{stage} cannot go backwards."
                )

            # Safety gates for low-level skills.
            if skill in {"py_call", "py_set"} and not allow_low_level_gateway:
                raise ValueError(
                    f"Skill {skill} is blocked by controls.allow_low_level_gateway=false. "
                    "Use high-level skills / ops_* first."
                )

            attempt_counts[step_id] = attempt_counts.get(step_id, 0) + 1
            if attempt_counts[step_id] > 1 + max_retries_per_step:
                raise RuntimeError(f"Step {step_id} exceeded max retries ({max_retries_per_step})")

            try:
                resolved_args = resolve_refs(args, step_results)
                if not isinstance(resolved_args, dict):
                    raise ValueError(f"Resolved args must be an object/dict. step_id={step_id} skill={skill}")

                # Enforce ops_introspect before ops_invoke for controllability.
                if skill == "ops_invoke" and require_ops_introspect:
                    operator_id = resolved_args.get("operator_id")
                    if not isinstance(operator_id, str):
                        raise ValueError("ops_invoke requires string operator_id")
                    if operator_id not in introspected_ops:
                        raise ValueError(
                            f"ops_invoke blocked: operator_id '{operator_id}' was not introspected first. "
                            "Call ops_introspect before ops_invoke."
                        )

                out = await self.execute_skill(skill, resolved_args)
                step_results[step_id] = out
                current_stage_rank = max(current_stage_rank, stage_order[stage])

                if skill == "ops_introspect":
                    op_id = resolved_args.get("operator_id")
                    if isinstance(op_id, str):
                        introspected_ops.add(op_id)

                # Handle alias storing for later $ref usage.
                on_success = step.get("on_success") or {}
                store_as = on_success.get("store_as") if isinstance(on_success, dict) else None
                if isinstance(store_as, dict):
                    alias_name = store_as.get("alias_name")
                    step_return_json_path = store_as.get("step_return_json_path")
                    if isinstance(alias_name, str) and isinstance(step_return_json_path, str) and step_return_json_path.strip():
                        extracted = self._extract_json_path_from_step(out, step_return_json_path)
                        alias_payload: Dict[str, Any]
                        if isinstance(extracted, dict):
                            alias_payload = {"ok": True, "data": extracted}
                        else:
                            alias_payload = {"ok": True, "data": {"value": extracted}}
                        step_results[alias_name] = alias_payload

                i += 1
            except JsonRpcError as e:
                err_trace = e.data.get("traceback") if isinstance(e.data, dict) else None
                step_results[step_id] = {"ok": False, "error": {"message": str(e), "traceback": err_trace or ""}}

                if attempt_counts[step_id] > 1 + max_retries_per_step:
                    raise

                repair_messages = self._build_skill_repair_messages(
                    prompt=prompt,
                    failed_step_id=step_id,
                    error_message=e.message,
                    error_traceback=err_trace or "No traceback field",
                    original_plan=plan,
                    step_results=step_results,
                    allowed_skills=allowed_skills,
                    skill_schemas=skill_schemas,
                )

                repair_plan = await self._llm_json(llm, repair_messages)
                if not isinstance(repair_plan, dict) or "steps" not in repair_plan:
                    raise ValueError("LLM repair_plan missing 'steps'")

                repair_steps = repair_plan["steps"]
                if not isinstance(repair_steps, list):
                    raise ValueError("LLM repair_plan 'steps' must be a list")

                replace_from = repair_plan.get("repair", {}).get("replace_from_step_id")
                if replace_from and replace_from != step_id:
                    raise ValueError(f"LLM repair replace_from_step_id mismatch: got {replace_from}, expected {step_id}")

                steps = steps[:i] + repair_steps
            except Exception as e:
                err_trace = traceback.format_exc()
                step_results[step_id] = {"ok": False, "error": {"message": str(e), "traceback": err_trace}}

                if attempt_counts[step_id] > 1 + max_retries_per_step:
                    raise

                repair_messages = self._build_skill_repair_messages(
                    prompt=prompt,
                    failed_step_id=step_id,
                    error_message=str(e),
                    error_traceback=err_trace,
                    original_plan=plan,
                    step_results=step_results,
                    allowed_skills=allowed_skills,
                    skill_schemas=skill_schemas,
                )

                repair_plan = await self._llm_json(llm, repair_messages)
                if not isinstance(repair_plan, dict) or "steps" not in repair_plan:
                    raise ValueError("LLM repair_plan missing 'steps'")
                repair_steps = repair_plan["steps"]
                if not isinstance(repair_steps, list):
                    raise ValueError("LLM repair_plan 'steps' must be a list")

                replace_from = repair_plan.get("repair", {}).get("replace_from_step_id")
                if replace_from and replace_from != step_id:
                    raise ValueError(f"LLM repair replace_from_step_id mismatch: got {replace_from}, expected {step_id}")

                steps = steps[:i] + repair_steps

        return {"prompt": prompt, "step_results": step_results, "plan": plan}

    def _interrupt(
        self,
        reason: str,
        step_id: str,
        step_index: int,
        save_path: str,
        prompt: str,
        plan: Dict[str, Any],
        steps: List[Dict[str, Any]],
        step_results: Dict[str, Dict[str, Any]],
        allowed_skills: List[str],
        skill_schemas: Optional[Dict[str, Any]],
        cause: Exception,
    ) -> "TaskInterruptedError":
        state = TaskState(
            prompt=prompt, plan=plan, steps=steps,
            step_results=step_results, current_step_index=step_index,
            allowed_skills=allowed_skills, skill_schemas=skill_schemas,
        )
        state.save(save_path)
        print(f"[VBF] {reason}: {cause}")
        print(f"[VBF] Interrupted at step '{step_id}'. State saved: {save_path}")
        print(f"[VBF] Resume: vbf --prompt \"{prompt}\" --resume \"{save_path}\"")
        return TaskInterruptedError(f"{reason} at step '{step_id}': {cause}", state=state, state_path=save_path)

    async def _start_blender_headless(self) -> None:
        # Start Blender process. Controller is responsible for lifecycle.
        # The Blender addon will start WS server and keep running while model tasks are processed.
        import subprocess

        env = os.environ.copy()
        env["VBF_WS_HOST"] = str(self.host)
        env["VBF_WS_PORT"] = str(self.port)

        # -b (background) + -P (python script)
        try:
            proc = subprocess.Popen(
                [self.blender_path, "-b", "-P", self.start_script_path],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "找不到 Blender 可执行文件。请设置环境变量 `BLENDER_PATH` 或在 CLI 使用 `--blender-path` 指定。\n"
                f"当前 blender_path={self.blender_path!r}"
            ) from e
        # Give Blender some time to start server.
        await asyncio.sleep(1.0)

        # If the process exits immediately, surface it.
        rc = proc.poll()
        if rc is not None and rc != 0:
            raise RuntimeError(f"Blender failed to start (exit code {rc}). Ensure BLENDER_PATH and addon deps are correct.")


def json_dumps(obj: Any) -> str:
    # Ensure non-ascii is allowed for Chinese prompts; keep JSON compact.
    import json as _json

    return _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

