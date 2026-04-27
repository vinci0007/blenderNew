from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from ..core.scene_state import SceneState
from ..core.task_state import TaskInterruptedError, TaskState
from ..core.vibe_protocol import resolve_refs
from ..runtime.run_logging import append_run_event, append_task_event, summarize_task_result
from ..runtime.style_templates import get_style_manager


def _log_run_event(client: Any, event: str, payload: Dict[str, Any] | None = None) -> None:
    """Best-effort runtime event logging for monitoring; never affects execution."""
    try:
        payload = dict(payload or {})
        task_id = getattr(client, "_task_id", None)
        if task_id:
            payload.setdefault("task_id", task_id)
        task_log_path = getattr(client, "_task_log_path", None)
        if task_log_path:
            append_task_event(task_log_path, event, payload)
        runtime_paths = getattr(client, "_runtime_paths", {}) or {}
        logs_dir = runtime_paths.get("logs_dir")
        if logs_dir:
            append_run_event(event, payload or {}, logs_dir)
    except Exception:
        pass


def _step_event_payload(
    *,
    mode: str,
    index: int,
    total_steps: int,
    step: Dict[str, Any],
    result: Any = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "mode": mode,
        "step_id": step.get("step_id"),
        "skill": step.get("skill"),
        "stage": step.get("stage"),
        "step_index": index,
        "total_steps": total_steps,
    }
    if isinstance(result, dict):
        payload["ok"] = result.get("ok")
        error = result.get("error")
        if error is not None:
            payload["error"] = str(error)[:500]
    return payload


def _record_task_result_objects(client: Any, result: Any) -> None:
    try:
        recorder = getattr(client, "_record_task_result_objects", None)
        if callable(recorder):
            recorder(result)
    except Exception:
        pass


async def run_task(
    client: Any,
    prompt: str,
    resume_state_path: Optional[str] = None,
    save_state_path: Optional[str] = None,
    style: Optional[str] = None,
    enable_step_feedback: bool = False,
    display_mode: str = "console",
) -> Dict[str, Any]:
    await client.ensure_connected()

    _save_path = save_state_path or client._default_save_path
    os.makedirs(os.path.dirname(_save_path), exist_ok=True)
    _log_run_event(
        client,
        "task_started",
        {
            "mode": "legacy",
            "style": style,
            "resume": bool(resume_state_path),
            "save_state_path": _save_path,
        },
    )

    if not client._is_llm_enabled():
        raise client._create_interrupt(
            "LLM not configured. Set VBF_LLM_BASE_URL, VBF_LLM_API_KEY, VBF_LLM_MODEL",
            prompt, _save_path
        )

    allowed_skills = await client.list_skills()
    if not allowed_skills:
        raise client._create_interrupt(
            "No skills returned from Blender addon. Check if VBF addon is enabled",
            prompt, _save_path
        )

    if resume_state_path and os.path.exists(resume_state_path):
        print(f"[VBF] Resuming from: {resume_state_path}")
        saved = TaskState.load(resume_state_path)
        plan = saved.plan
        steps = saved.steps
        step_results = saved.step_results
        start_index = saved.current_step_index
        print(f"[VBF] Resuming at step {start_index}/{len(steps)}")
        _log_run_event(
            client,
            "task_resumed",
            {
                "mode": "legacy",
                "state_path": resume_state_path,
                "current_step_index": start_index,
                "total_steps": len(steps),
                "completed_steps": len(step_results),
            },
        )
    else:
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

        plan, steps = await client._plan_skill_task_auto(styled_prompt, allowed_skills, _save_path)
        step_results = {}
        start_index = 0
        print(f"[VBF] Generated plan with {len(steps)} steps")
        _log_run_event(
            client,
            "plan_generated",
            {
                "mode": "legacy",
                "total_steps": len(steps),
                "plan_type": plan.get("plan_type") if isinstance(plan, dict) else None,
                "vbf_version": plan.get("vbf_version") if isinstance(plan, dict) else None,
            },
        )

    max_retries = int(plan.get("execution", {}).get("max_retries_per_step", 2))
    max_steps = int(plan.get("controls", {}).get("max_steps", 80))

    if len(steps) > max_steps:
        raise client._create_interrupt(
            f"Plan too large: {len(steps)} > {max_steps}",
            prompt, _save_path, plan=plan, steps=steps, allowed_skills=allowed_skills
        )

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

        if not step_id or not isinstance(step_id, str):
            raise client._create_interrupt(f"Invalid step_id at index {i}", prompt, _save_path,
                                           plan, steps, step_results, i, allowed_skills)

        if skill not in allowed_skills:
            raise client._create_interrupt(f"Skill not allowed: {skill}", prompt, _save_path,
                                           plan, steps, step_results, i, allowed_skills)

        attempt_counts[step_id] = attempt_counts.get(step_id, 0) + 1
        if attempt_counts[step_id] > max_retries:
            print(f"[VBF] Step {step_id} exceeded max retries, requesting replan...")
            _log_run_event(
                client,
                "replan_requested",
                {
                    "mode": "legacy",
                    "step_id": step_id,
                    "skill": skill,
                    "reason": "max_retries_exceeded",
                    "attempts": attempt_counts[step_id],
                },
            )
            _new_plan, new_steps = await client.request_replan(
                prompt, step_id, plan, step_results, _save_path
            )
            steps = steps[:i] + new_steps
            _log_run_event(
                client,
                "replan_produced",
                {
                    "mode": "legacy",
                    "step_id": step_id,
                    "new_steps": len(new_steps),
                    "total_steps": len(steps),
                },
            )
            continue

        if stage in stage_order and stage_order[stage] < current_stage_rank:
            print(f"[VBF] Warning: Stage regression at {step_id} ({stage})")
        current_stage_rank = max(current_stage_rank, stage_order.get(stage, current_stage_rank))

        try:
            resolved_args = resolve_refs(args, step_results)
            result = await client.execute_skill(skill, resolved_args, step_id)
            step_results[step_id] = result
            _record_task_result_objects(client, result)
            _log_run_event(
                client,
                "step_completed",
                _step_event_payload(
                    mode="legacy",
                    index=i,
                    total_steps=len(steps),
                    step=step,
                    result=result,
                ),
            )

            if enable_step_feedback and i + 1 < len(steps):
                feedback = await client.analyze_step_result(
                    step_id, skill, resolved_args, result, plan, steps, i + 1, prompt
                )
                if feedback and feedback.get("should_adjust_plan"):
                    pass

            i += 1

        except Exception as e:
            from ..transport.jsonrpc_ws import JsonRpcError

            if isinstance(e, JsonRpcError):
                step_results[step_id] = {"ok": False, "error": {"message": str(e)}}

                if attempt_counts[step_id] <= max_retries:
                    try:
                        adapter = await client._ensure_adapter()
                        repair_prompt = (
                            f"Failed step: {step_id} (skill={skill})\n"
                            f"Error: {e}\n"
                            f"Original prompt: {prompt}\n"
                            f"Completed steps: {json.dumps(step_results, indent=2, ensure_ascii=False)}\n"
                            f"Generate a repair plan starting from step {step_id}. "
                            f"Use ONLY skills from: {allowed_skills}"
                        )
                        repair_messages = adapter.format_messages(repair_prompt)
                        repair_plan = await client._adapter_call(repair_messages)

                        if repair_plan and "steps" in repair_plan:
                            repair_steps = repair_plan.get("steps", [])
                            replace_from = repair_plan.get("repair", {}).get("replace_from_step_id", step_id)

                            await client.rollback_to_step(replace_from)

                            replace_idx = next(
                                (j for j, s in enumerate(steps) if s.get("step_id") == replace_from), i
                            )
                            steps = steps[:replace_idx] + repair_steps
                            i = replace_idx
                            print(f"[VBF] Repair: rolling back to {replace_from}, {len(repair_steps)} steps")
                            _log_run_event(
                                client,
                                "repair_plan_applied",
                                {
                                    "mode": "legacy",
                                    "step_id": step_id,
                                    "replace_from_step_id": replace_from,
                                    "repair_steps": len(repair_steps),
                                },
                            )
                            continue
                    except Exception as repair_err:
                        print(f"[VBF] Repair request failed: {repair_err}")

                raise client._create_interrupt(
                    f"Step {step_id} failed after retries",
                    prompt, _save_path, plan, steps, step_results, i, allowed_skills, cause=e
                )

            raise client._create_interrupt(
                f"Unexpected error at step {step_id}",
                prompt, _save_path, plan, steps, step_results, i, allowed_skills, cause=e
            )

    print(f"[VBF] Task completed: {len(step_results)} steps executed")
    result = {"prompt": prompt, "step_results": step_results, "plan": plan}
    _log_run_event(client, "task_completed", {"mode": "legacy", **summarize_task_result(result)})
    return result


async def run_task_with_feedback(
    client: Any,
    prompt: str,
    resume_state_path: Optional[str] = None,
    save_state_path: Optional[str] = None,
    style: Optional[str] = None,
    enable_auto_check: bool = True,
    enable_llm_feedback: bool = True,
) -> Dict[str, Any]:
    from ..feedback.control import ClosedLoopControl
    from ..feedback.geometry_capture import IncrementalSceneCapture, CaptureLevel

    await client.ensure_connected()

    _save_path = save_state_path or client._default_save_path
    os.makedirs(os.path.dirname(_save_path), exist_ok=True)
    _log_run_event(
        client,
        "task_started",
        {
            "mode": "feedback",
            "style": style,
            "resume": bool(resume_state_path),
            "auto_check": enable_auto_check,
            "llm_feedback": enable_llm_feedback,
            "save_state_path": _save_path,
        },
    )

    if not client._is_llm_enabled():
        raise client._create_interrupt(
            "LLM not configured. Set VBF_LLM_BASE_URL/API_KEY/MODEL",
            prompt, _save_path
        )

    allowed_skills = await client.list_skills()
    if not allowed_skills:
        raise client._create_interrupt(
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
        _log_run_event(
            client,
            "task_resumed",
            {
                "mode": "feedback",
                "state_path": resume_state_path,
                "current_step_index": i,
                "total_steps": len(steps),
                "completed_steps": len(step_results),
            },
        )
    else:
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
        scene = await client.capture_scene_state()
        print(f"[VBF-Feedback] Scene has {len(scene._objects)} objects")
        if hasattr(client, "_remember_task_initial_scene"):
            client._remember_task_initial_scene(scene)
        _log_run_event(
            client,
            "scene_captured",
            {
                "mode": "feedback",
                "object_count": len(scene._objects),
            },
        )
        two_stage_mode = client._should_use_two_stage_planning(styled_prompt, allowed_skills)
        scene_aware_prompt = client._inject_scene_context(
            styled_prompt,
            scene,
            max_objects=15 if two_stage_mode else None,
        )
        plan, steps = await client._plan_skill_task_auto(
            scene_aware_prompt,
            allowed_skills,
            _save_path,
        )
        step_results = {}
        i = 0
        print(f"[VBF-Feedback] Generated plan with {len(steps)} steps")
        _log_run_event(
            client,
            "plan_generated",
            {
                "mode": "feedback",
                "total_steps": len(steps),
                "plan_type": plan.get("plan_type") if isinstance(plan, dict) else None,
                "vbf_version": plan.get("vbf_version") if isinstance(plan, dict) else None,
            },
        )

    max_replans = int(plan.get("execution", {}).get("max_replans", 5))
    replan_count = 0
    loop_guard_repeat_threshold = 2
    last_replan_fingerprint: Optional[str] = None
    consecutive_replan_hits = 0
    forced_retry_used: Dict[str, bool] = {}

    loop = ClosedLoopControl(
        client=client,
        enable_auto_check=enable_auto_check,
        enable_llm_feedback=enable_llm_feedback,
        capture_level=CaptureLevel.LIGHT,
        task_prompt=prompt,
    )
    scene_capture = IncrementalSceneCapture(client)

    while i < len(steps):
        step = steps[i]
        step_id = step.get("step_id", f"step_{i:03d}")

        decision, post_state = await loop.execute_with_feedback(step, step_results, scene_capture)

        if post_state:
            scene_capture._cache.update(post_state)
        _record_task_result_objects(client, step_results.get(step_id))

        if decision.action in {"replan", "checkpoint"}:
            replan_count += 1
            if replan_count > max_replans:
                raise client._create_interrupt(
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
            replan_fingerprint = client._build_replan_fingerprint(
                reason=reason,
                skill=failing_skill,
                error_text=error_signature,
            )

            if replan_fingerprint == last_replan_fingerprint:
                consecutive_replan_hits += 1
            else:
                last_replan_fingerprint = replan_fingerprint
                consecutive_replan_hits = 1

            if decision.action == "checkpoint":
                rollback_step_id = decision.detail.get("rollback_step_id")
                if rollback_step_id:
                    rollback_resp = await client.rollback_to_step(rollback_step_id)
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
                            _log_run_event(
                                client,
                                "checkpoint_rollback",
                                {
                                    "mode": "feedback",
                                    "rollback_step_id": rollback_step_id,
                                    "rollback_index": rollback_idx,
                                    "cleared_steps": len(rolled_back_steps),
                                },
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
                            "error_signature": client._build_error_signature(error_signature),
                            "consecutive_hits": consecutive_replan_hits,
                        }
                    }
                    raise client._create_interrupt(
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
            _log_run_event(
                client,
                "replan_requested",
                {
                    "mode": "feedback",
                    "step_id": step_id,
                    "skill": failing_skill,
                    "reason": reason,
                    "from_index": replan_from_idx,
                    "loop_guard_hit": loop_guard_hit,
                    "force_corrective": force_corrective_retry,
                    "replan_fingerprint": replan_fingerprint,
                },
            )
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
            plan, new_steps = await client._replan_from_step(
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
            _log_run_event(
                client,
                "replan_produced",
                {
                    "mode": "feedback",
                    "step_id": step_id,
                    "new_steps": len(new_steps),
                    "total_steps": len(steps),
                },
            )
            continue

        last_replan_fingerprint = None
        consecutive_replan_hits = 0
        _log_run_event(
            client,
            "step_completed",
            _step_event_payload(
                mode="feedback",
                index=i,
                total_steps=len(steps),
                step=step,
                result=step_results.get(step_id),
            ),
        )
        i += 1

    print(f"[VBF-Feedback] Task completed: {len(step_results)} steps")
    result = {"prompt": prompt, "step_results": step_results, "plan": plan}
    _log_run_event(client, "task_completed", {"mode": "feedback", **summarize_task_result(result)})
    return result
