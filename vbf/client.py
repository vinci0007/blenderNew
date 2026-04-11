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
- Removed ALL RadioTask code completely
"""

import asyncio
import json
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple

from .jsonrpc_ws import JsonRpcWebSocketClient, JsonRpcError
from .llm_openai_compat import load_openai_compat_config
from .llm_integration import (
    load_llm, call_llm_json, generate_skill_plan,
    build_skill_plan_messages, build_skill_repair_messages, is_llm_enabled
)
from .plan_normalization import normalize_plan
from .vibe_protocol import resolve_refs, merge_step_results_for_prompt
from .task_state import TaskState, TaskInterruptedError
from .scene_state import SceneState, FeedbackContext
from .memory_manager import MemoryManager, MemoryStats
from .progress import ProgressVisualizer, DisplayMode


class VBFClient:
    """Smart modeling client with four-layer control system."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        blender_path: Optional[str] = None,
        start_script_path: Optional[str] = None,
        memory_limit_mb: Optional[int] = None,  # Memory optimization
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

    async def ensure_connected(self, timeout_s: float = 30.0) -> None:
        deadline = asyncio.get_event_loop().time() + timeout_s
        last_err = None
        while asyncio.get_event_loop().time() < deadline:
            try:
                await self._ws.connect()
                return
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.5)
        await self._start_blender_headless()
        # Retry after starting Blender
        deadline2 = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline2:
            try:
                await self._ws.connect()
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

    async def rollback_to_step(self, step_id: str) -> Dict[str, Any]:
        try:
            return await self._ws.call(method="vbf.rollback_to_step", params={"step_id": step_id})
        except Exception as e:
            print(f"[VBF] Rollback to {step_id} failed: {e}")
            return {"ok": False, "error": str(e)}

    async def capture_scene_state(self) -> SceneState:
        """Capture current Blender scene state via py_get calls."""
        state = SceneState()
        try:
            # Get scene info
            scene_info = await self.execute_skill("py_get", {"path": "bpy.context.scene", "attrs": ["name", "frame_current", "frame_start", "frame_end"]})
            if scene_info.get("ok"):
                data = scene_info.get("data", {})
                state.scene_name = data.get("name")
                state.frame_current = data.get("frame_current", 1)
                state.frame_start = data.get("frame_start", 1)
                state.frame_end = data.get("frame_end", 250)

            # Get objects
            objects_resp = await self.execute_skill("data_collections_list", {"collection": "objects"})
            if objects_resp.get("ok"):
                for obj_name in objects_resp.get("data", []):
                    try:
                        obj_data = await self.execute_skill("py_get", {
                            "path": f'bpy.data.objects["{obj_name}"]',
                            "attrs": ["type", "location", "dimensions"]
                        })
                        if obj_data.get("ok"):
                            d = obj_data.get("data", {})
                            state.add_object(
                                name=obj_name,
                                obj_type=d.get("type", "MESH"),
                                location=d.get("location", [0, 0, 0]),
                                size=d.get("dimensions", [0, 0, 0])
                            )
                    except Exception:
                        pass
        except Exception as e:
            state.add_error(f"Failed to capture scene: {e}")
        return state

    # === Layer 1: Checkpoint/Resume ===

    def _create_interrupt(self, reason: str, prompt: str, save_path: str,
                         plan: Dict = None, steps: List = None,
                         step_results: Dict = None, current_index: int = 0,
                         allowed_skills: List = None,
                         cause: Exception = None) -> TaskInterruptedError:
        """Create and return a TaskInterruptedError with saved state."""
        state = TaskState(
            prompt=prompt,
            plan=plan or {},
            steps=steps or [],
            step_results=step_results or {},
            current_step_index=current_index,
            allowed_skills=allowed_skills or [],
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

    async def _plan_skill_task(self, prompt: str, allowed_skills: List[str], save_path: str) -> Tuple[Dict, List]:
        """Generate skill plan with checkpoint on failure."""
        try:
            plan, steps = await generate_skill_plan(
                prompt=prompt,
                allowed_skills=allowed_skills,
                describe_skills_func=self.describe_skills,
            )
            return plan, steps
        except ValueError as e:
            if "LLM is not configured" in str(e):
                raise self._create_interrupt(
                    "LLM not configured. Set VBF_LLM_BASE_URL/API_KEY/MODEL",
                    prompt, save_path,
                    allowed_skills=allowed_skills, cause=e
                )
            raise self._create_interrupt(
                f"Plan generation failed: {e}",
                prompt, save_path, allowed_skills=allowed_skills, cause=e
            )

    # === Layer 4: Real-time Feedback (optional) ===

    async def analyze_step_result(self, step_id: str, skill: str, args: Dict,
                                   result: Dict, plan: Dict, steps: List,
                                   step_index: int, prompt: str) -> Optional[Dict]:
        """Optional: Ask LLM to analyze step result and suggest plan adjustments."""
        llm = load_llm()
        if not llm:
            return None

        # Capture scene before feedback
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
            {"role": "user", "content": analysis_prompt + f"\n\nRemaining steps: {steps[step_index:]}",}
        ]

        try:
            analysis = await call_llm_json(llm, messages)
            # Return analysis that caller can use to adjust plan
            return analysis
        except Exception:
            return None

    # === Layer 3: Active Replanning ===

    async def request_replan(self, prompt: str, from_step_id: str, current_plan: Dict,
                            step_results: Dict, save_path: str) -> Tuple[Dict, List]:
        """Request LLM to regenerate plan from given step with current scene context."""
        llm = load_llm()
        if not llm:
            raise self._create_interrupt("Cannot replan: LLM not available", prompt, save_path)

        allowed_skills = await self.list_skills()
        scene = await self.capture_scene_state()
        skill_schemas = await self.describe_skills(allowed_skills)

        # Build replan message with scene context
        replan_prompt = f"""
        Replanning request from step: {from_step_id}
        Original prompt: {prompt}

        Current scene state:
        {scene.to_prompt_text()}

        Completed steps:
        {json.dumps(step_results, indent=2, ensure_ascii=False)}

        Please generate a new plan starting from step "{from_step_id}".
        Consider the current scene state when planning.
        """

        messages = build_skill_plan_messages(
            prompt=replan_prompt,
            allowed_skills=allowed_skills,
            skill_schemas=skill_schemas
        )

        raw_plan = await call_llm_json(llm, messages)
        try:
            plan = normalize_plan(raw_plan)
            steps = plan.get("steps", [])
            if not steps:
                raise ValueError("No steps in replan")
            return plan, steps
        except ValueError as e:
            raise self._create_interrupt(f"Replan failed: {e}", prompt, save_path, cause=e)

    # === Main Execution with Layer 2: Enhanced Recovery ===

    async def run_task(self, prompt: str, resume_state_path: Optional[str] = None,
                      save_state_path: Optional[str] = None,
                      enable_step_feedback: bool = False,
                      display_mode: str = "console") -> Dict[str, Any]:
        """Execute modeling task with full checkpoint/replan/recovery support."""
        await self.ensure_connected()

        # CRITICAL: _save_path defined EARLY so we can save even on config errors
        _save_path = save_state_path or self._default_save_path
        os.makedirs(os.path.dirname(_save_path), exist_ok=True)

        # Layer 1: Config checks with checkpoint save
        if not is_llm_enabled():
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

        llm = load_llm()
        if llm is None:
            raise self._create_interrupt(
                "LLM initialization failed after configuration check",
                prompt, _save_path, allowed_skills=allowed_skills
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
            plan, steps = await self._plan_skill_task(prompt, allowed_skills, _save_path)
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
                raise self._create_interrupt(f"Invalid step_id at index {i}", prompt, _save_path, plan, steps, step_results, i, allowed_skills)

            if skill not in allowed_skills:
                raise self._create_interrupt(f"Skill not allowed: {skill}", prompt, _save_path, plan, steps, step_results, i, allowed_skills)

            attempt_counts[step_id] = attempt_counts.get(step_id, 0) + 1
            if attempt_counts[step_id] > max_retries:
                # Layer 3: Replan on max retries exceeded
                print(f"[VBF] Step {step_id} exceeded max retries, requesting replan...")
                new_plan, new_steps = await self.request_replan(
                    prompt, step_id, plan, step_results, _save_path
                )
                # Replace remaining steps
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
                        # Adjust remaining steps based on feedback
                        pass  # Can implement dynamic step adjustment here

                i += 1

            except JsonRpcError as e:
                step_results[step_id] = {"ok": False, "error": {"message": str(e)}}

                # Layer 2: Enhanced Recovery - physical rollback + replan
                if attempt_counts[step_id] <= max_retries:
                    # Request repair plan from LLM
                    try:
                        repair_msgs = build_skill_repair_messages(
                            prompt, step_id, str(e), "",
                            plan, step_results, allowed_skills
                        )
                        repair_plan = await call_llm_json(llm, repair_msgs)

                        if repair_plan and "steps" in repair_plan:
                            repair_steps = repair_plan.get("steps", [])
                            replace_from = repair_plan.get("repair", {}).get("replace_from_step_id", step_id)

                            # Physical rollback
                            await self.rollback_to_step(replace_from)

                            # Replace steps
                            replace_idx = next((j for j, s in enumerate(steps) if s.get("step_id") == replace_from), i)
                            steps = steps[:replace_idx] + repair_steps
                            i = replace_idx
                            print(f"[VBF] Repair: rolling back to {replace_from}, {len(repair_steps)} replacement steps")
                            continue
                    except Exception as repair_err:
                        print(f"[VBF] Repair request failed: {repair_err}")

                # Repair failed or max retries, save checkpoint
                raise self._create_interrupt(
                    f"Step {step_id} failed after retries",
                    prompt, _save_path, plan, steps, step_results, i, allowed_skills, e
                )

            except Exception as e:
                raise self._create_interrupt(
                    f"Unexpected error at step {step_id}",
                    prompt, _save_path, plan, steps, step_results, i, allowed_skills, e
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
