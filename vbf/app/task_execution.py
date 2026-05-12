from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from ..core.scene_state import SceneState
from ..core.task_ledger import TaskLedger
from ..core.task_state import TaskInterruptedError, TaskState
from ..core.vibe_protocol import resolve_refs
from .plan_gate import build_prior_object_table, validate_and_repair_parent_refs
from ..feedback.llm import GeometryFeedbackAnalyzer
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


def _is_agent_loop_plan(plan: Dict[str, Any]) -> bool:
    metadata = plan.get("metadata") if isinstance(plan, dict) else {}
    return isinstance(metadata, dict) and metadata.get("planning_mode") == "adaptive_agent_loop"


def _result_object_name(result: Any) -> Optional[str]:
    if not isinstance(result, dict):
        return None
    data = result.get("data")
    if not isinstance(data, dict):
        return None
    for key in ("object_name", "name", "child"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _created_objects_for_steps(
    batch_steps: List[Dict[str, Any]],
    step_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    created: List[Dict[str, Any]] = []
    for step in batch_steps:
        if not isinstance(step, dict):
            continue
        step_id = step.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            continue
        result = step_results.get(step_id)
        if not isinstance(result, dict) or result.get("ok") is not True:
            continue
        object_name = _result_object_name(result)
        if not object_name:
            continue
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        planned_name = args.get("name") or args.get("object_name")
        created.append(
            {
                "step_id": step_id,
                "skill": step.get("skill"),
                "planned_name": planned_name if isinstance(planned_name, str) else None,
                "object_name": object_name,
            }
        )
    return created


def _planned_object_name(step: Dict[str, Any]) -> Optional[str]:
    args = step.get("args") if isinstance(step.get("args"), dict) else {}
    for key in ("name", "object_name"):
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _filter_unsafe_batch_repair_steps(
    repair_steps: List[Dict[str, Any]],
    *,
    prior_steps: List[Dict[str, Any]],
    step_results: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Prevent batch repairs from deleting established objects that later steps still need."""
    protected_names = {
        name
        for step in prior_steps
        if isinstance(step, dict)
        for name in [_planned_object_name(step)]
        if name
    }
    for step in prior_steps:
        if not isinstance(step, dict):
            continue
        result_name = _result_object_name(step_results.get(str(step.get("step_id"))))
        if result_name:
            protected_names.add(result_name)

    repair_parent_refs = set()
    for step in repair_steps:
        args = step.get("args") if isinstance(step, dict) and isinstance(step.get("args"), dict) else {}
        parent_name = args.get("parent_name")
        if isinstance(parent_name, str) and parent_name:
            repair_parent_refs.add(parent_name)

    filtered: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for step in repair_steps:
        args = step.get("args") if isinstance(step, dict) and isinstance(step.get("args"), dict) else {}
        object_name = args.get("object_name")
        is_delete = step.get("skill") == "delete_object"
        protects_prior = (
            isinstance(object_name, str)
            and object_name in protected_names
            and not object_name.endswith(".001")
        )
        deletes_needed_parent = isinstance(object_name, str) and object_name in repair_parent_refs
        if is_delete and (protects_prior or deletes_needed_parent):
            skipped.append(
                {
                    "step_id": step.get("step_id"),
                    "skill": step.get("skill"),
                    "object_name": object_name,
                    "reason": (
                        "referenced_parent"
                        if deletes_needed_parent
                        else "protected_prior_object"
                    ),
                }
            )
            continue
        filtered.append(step)
    return filtered, skipped


def _current_batch_summary(
    plan: Dict[str, Any],
    steps: List[Dict[str, Any]],
    step_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = plan.get("metadata") if isinstance(plan, dict) else {}
    stage = metadata.get("current_stage")
    batch_index = metadata.get("batch_index")
    batch_steps = [
        step
        for step in steps
        if step.get("adaptive_stage") == stage and step.get("batch_index") == batch_index
    ]
    if not batch_steps:
        batch_steps = steps
    summary = {
        "stage": stage,
        "batch_index": batch_index,
        "steps": len(batch_steps),
        "step_ids": [str(step.get("step_id")) for step in batch_steps if step.get("step_id")],
        "remaining_work": metadata.get("remaining_work", []),
    }
    if step_results is not None:
        summary["created_objects"] = _created_objects_for_steps(batch_steps, step_results)
    return summary


def _current_batch_start_index(plan: Dict[str, Any], steps: List[Dict[str, Any]]) -> int:
    metadata = plan.get("metadata") if isinstance(plan, dict) else {}
    stage = metadata.get("current_stage")
    batch_index = metadata.get("batch_index")
    for idx, step in enumerate(steps):
        if step.get("adaptive_stage") == stage and step.get("batch_index") == batch_index:
            return idx
    return max(0, len(steps) - 1)


def _batch_step_ids(plan: Dict[str, Any], steps: List[Dict[str, Any]]) -> List[str]:
    metadata = plan.get("metadata") if isinstance(plan, dict) else {}
    stage = metadata.get("current_stage")
    batch_index = metadata.get("batch_index")
    return [
        str(step.get("step_id"))
        for step in steps
        if step.get("adaptive_stage") == stage
        and step.get("batch_index") == batch_index
        and step.get("step_id")
    ]


def _batch_progress_flags(
    *,
    plan: Dict[str, Any],
    steps: List[Dict[str, Any]],
    step_results: Dict[str, Any],
    next_stage: Optional[str],
) -> Dict[str, Any]:
    metadata = plan.get("metadata") if isinstance(plan, dict) else {}
    step_ids = _batch_step_ids(plan, steps)
    results = [
        step_results.get(step_id)
        for step_id in step_ids
        if step_id in step_results
    ]
    ok_results = [result for result in results if isinstance(result, dict) and result.get("ok")]
    failed_results = [result for result in results if isinstance(result, dict) and result.get("ok") is False]
    changed = False
    warnings = False
    for result in results:
        if not isinstance(result, dict):
            continue
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        if any(key in data for key in ("object_name", "name", "child", "_post_state", "result")):
            changed = True
        if result.get("warning") or result.get("warnings") or data.get("warning") or data.get("warnings"):
            warnings = True
    return {
        "step_ids": step_ids,
        "ok_count": len(ok_results),
        "failed_count": len(failed_results),
        "has_progress": bool(ok_results and changed),
        "has_warning": warnings,
        "stage_transition": bool(next_stage and next_stage != metadata.get("current_stage")),
    }


def _record_agent_loop_batch_completed(
    client: Any,
    plan: Dict[str, Any],
    steps: List[Dict[str, Any]],
    step_results: Dict[str, Any],
) -> None:
    metadata = plan.get("metadata") if isinstance(plan, dict) else {}
    if not isinstance(metadata, dict):
        return
    ledger_path = metadata.get("ledger_path")
    if not isinstance(ledger_path, str) or not ledger_path:
        return
    step_ids = _batch_step_ids(plan, steps)
    if not step_ids:
        return
    results = [step_results.get(step_id) for step_id in step_ids]
    if not all(isinstance(result, dict) and result.get("ok") is True for result in results):
        return
    try:
        if os.path.exists(ledger_path):
            ledger = TaskLedger.load(ledger_path)
        else:
            ledger = TaskLedger(
                task_id=str(getattr(client, "_task_id", None) or "task_unknown"),
                prompt="",
                stages=list(metadata.get("stages") or ["geometry_modeling"]),
            )
        ledger.current_stage_index = int(metadata.get("current_stage_index") or 0)
        ledger.record_completed_batch(
            stage=str(metadata.get("current_stage") or "geometry_modeling"),
            batch_index=int(metadata.get("batch_index") or 1),
            step_ids=step_ids,
            continue_stage=bool(metadata.get("continue_stage", False)),
            remaining_work=list(metadata.get("remaining_work") or []),
        )
        ledger.save(ledger_path)
    except Exception as exc:
        _log_run_event(
            client,
            "agent_loop_ledger_update_failed",
            {
                "mode": "feedback",
                "ledger_path": ledger_path,
                "error": str(exc)[:500],
            },
        )


def _try_repair_failed_parent_step(
    *,
    step: Dict[str, Any],
    steps: List[Dict[str, Any]],
    step_results: Dict[str, Any],
    completed_summary: List[Dict[str, Any]],
) -> Optional[Tuple[str, str]]:
    args = step.get("args")
    if step.get("skill") != "set_parent" or not isinstance(args, dict):
        return None
    old_parent = args.get("parent_name")
    if not isinstance(old_parent, str) or not old_parent:
        return None

    prior_objects = build_prior_object_table(completed_summary)
    current_created = _created_objects_for_steps(steps, step_results)
    seen = {item.get("object_name") for item in prior_objects if isinstance(item, dict)}
    for item in current_created:
        if isinstance(item, dict) and item.get("object_name") not in seen:
            prior_objects.append(item)
            seen.add(item.get("object_name"))
    try:
        validate_and_repair_parent_refs({"steps": [step]}, prior_objects)
    except ValueError:
        return None
    new_parent = args.get("parent_name")
    if isinstance(new_parent, str) and new_parent and new_parent != old_parent:
        return old_parent, new_parent
    return None


def _should_run_batch_quality_gate(
    *,
    policy: str,
    cfg: Dict[str, Any],
    progress: Dict[str, Any],
    batch_index: Optional[int] = None,
) -> Tuple[bool, str]:
    mode = str(policy or "auto").strip().lower()
    if mode in {"off", "false", "disabled", "none"}:
        return False, "policy_off"
    if mode in {"always", "true", "on"}:
        return True, "policy_always"
    try:
        every_n = int(cfg.get("batch_quality_gate_every_n_batches", 0) or 0)
    except Exception:
        every_n = 0
    if every_n > 0 and isinstance(batch_index, int) and batch_index > 0 and batch_index % every_n == 0:
        return True, f"periodic_batch_{every_n}"
    if progress.get("failed_count", 0) > 0:
        return True, "failed_step"
    if bool(cfg.get("batch_quality_gate_on_empty_progress", True)) and not progress.get("has_progress"):
        return True, "empty_progress"
    if bool(cfg.get("batch_quality_gate_on_step_warning", True)) and progress.get("has_warning"):
        return True, "step_warning"
    if bool(cfg.get("batch_quality_gate_on_stage_transition", True)) and progress.get("stage_transition"):
        return True, "stage_transition"
    return False, "auto_skip"


def _analysis_text_items(analysis: Any) -> List[str]:
    items: List[str] = []
    for attr in ("critical_issues", "suggestions"):
        values = getattr(analysis, attr, None)
        if isinstance(values, list):
            items.extend(str(item).strip() for item in values if str(item).strip())
    reason = str(getattr(analysis, "reason", "") or "").strip()
    if reason:
        items.append(reason)
    return items


_STAGE_ORDER = (
    "geometry_modeling",
    "uv_texture_material",
    "environment_lighting",
    "animation",
    "camera_render",
)


_STAGE_ISSUE_MARKERS: Dict[str, Tuple[str, ...]] = {
    "uv_texture_material": (
        "material",
        "materials",
        "pbr",
        "shader",
        "texture",
        "textures",
        "uv",
        "color",
        "glass",
        "paint",
    ),
    "environment_lighting": (
        "light",
        "lighting",
        "area light",
        "rim light",
        "fill light",
        "studio",
        "environment",
        "floor",
        "reflective floor",
    ),
    "animation": (
        "animation",
        "animate",
        "keyframe",
        "keyframes",
        "frame range",
        "fps",
        "turntable rotation",
        "rotation keyframes",
    ),
    "camera_render": (
        "camera",
        "render",
        "cycles",
        "denoise",
        "focal length",
        "framing",
        "view",
        "resolution",
    ),
}


def _downstream_stage_markers(stage: Optional[str]) -> Tuple[str, ...]:
    current = str(stage or "").strip().lower()
    try:
        current_index = _STAGE_ORDER.index(current)
    except ValueError:
        return ()
    markers: List[str] = []
    for downstream_stage in _STAGE_ORDER[current_index + 1 :]:
        markers.extend(_STAGE_ISSUE_MARKERS.get(downstream_stage, ()))
    return tuple(markers)


def _is_downstream_stage_issue(stage: Optional[str], item: Any) -> bool:
    text = str(item or "").strip().lower()
    if not text:
        return False
    markers = _downstream_stage_markers(stage)
    return bool(markers) and any(marker in text for marker in markers)


def _analysis_critical_items(analysis: Any) -> List[str]:
    values = getattr(analysis, "critical_issues", None)
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _current_stage_critical_issues(analysis: Any, stage: Optional[str]) -> List[str]:
    return [
        item
        for item in _analysis_critical_items(analysis)
        if not _is_downstream_stage_issue(stage, item)
    ]


def _has_only_downstream_critical_issues(analysis: Any, stage: Optional[str]) -> bool:
    critical = _analysis_critical_items(analysis)
    if not critical:
        return False
    return not _current_stage_critical_issues(analysis, stage)


def _has_blocking_batch_issue(analysis: Any, stage: Optional[str] = None) -> bool:
    """Return true only for issues that should keep a batch in repair mode."""
    blocking_markers = (
        "empty scene",
        "no geometry",
        "no objects",
        "step failed",
        "execution failed",
        "skill execution failed",
        "invalid",
        "not executable",
        "cannot proceed",
        "missing main body",
        "main body is missing",
        "root scale control is missing",
        "rotation control is missing",
        "parent object not found",
        "broken hierarchy",
    )
    for item in _analysis_text_items(analysis):
        if _is_downstream_stage_issue(stage, item):
            continue
        lowered = item.lower()
        if any(marker in lowered for marker in blocking_markers):
            return True
    return False


def _add_analysis_pending_work(
    pending_work: List[str],
    analysis: Any,
    *,
    limit: int = 8,
) -> int:
    existing = set(pending_work)
    added = 0
    for item in _analysis_text_items(analysis):
        if item in existing:
            continue
        pending_work.append(item)
        existing.add(item)
        added += 1
        if added >= limit:
            break
    return added


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
        planning_prompt = saved.prompt
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
        raw_object_count = len(scene._objects)
        if hasattr(client, "_remember_task_initial_scene"):
            client._remember_task_initial_scene(scene)
        context_scene = (
            client._filter_scene_for_task_context(scene)
            if hasattr(client, "_filter_scene_for_task_context")
            else scene
        )
        context_object_count = len(context_scene.get_objects())
        task_scene_policy = getattr(client, "_task_scene_policy", "all")
        print(
            "[VBF-Feedback] Scene capture: "
            f"raw_objects={raw_object_count} "
            f"task_context_objects={context_object_count} "
            f"policy={task_scene_policy}"
        )
        _log_run_event(
            client,
            "scene_captured",
            {
                "mode": "feedback",
                "object_count": raw_object_count,
                "context_object_count": context_object_count,
                "task_scene_policy": task_scene_policy,
            },
        )
        two_stage_mode = client._should_use_two_stage_planning(styled_prompt, allowed_skills)
        scene_aware_prompt = client._inject_scene_context(
            styled_prompt,
            scene,
            max_objects=15 if two_stage_mode else None,
        )
        planning_prompt = scene_aware_prompt
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
    batch_repair_attempts: Dict[Tuple[str, int], int] = {}
    batch_quality_repair_count = 0

    loop = ClosedLoopControl(
        client=client,
        enable_auto_check=enable_auto_check,
        enable_llm_feedback=enable_llm_feedback,
        capture_level=CaptureLevel.LIGHT,
        task_prompt=prompt,
    )
    scene_capture = IncrementalSceneCapture(client)
    agent_loop_completed_summary: List[Dict[str, Any]] = []
    metadata = plan.get("metadata") if isinstance(plan, dict) else {}
    agent_loop_pending_work: List[str] = (
        list(metadata.get("remaining_work") or []) if isinstance(metadata, dict) else []
    )

    async def _append_next_agent_loop_batch_if_needed() -> bool:
        nonlocal plan, steps, agent_loop_pending_work, i, batch_quality_repair_count
        if not _is_agent_loop_plan(plan):
            return False
        summary = _current_batch_summary(plan, steps, step_results)
        if not agent_loop_completed_summary or agent_loop_completed_summary[-1] != summary:
            agent_loop_completed_summary.append(summary)

        metadata = plan.get("metadata") if isinstance(plan, dict) else {}
        stage = metadata.get("current_stage") if isinstance(metadata, dict) else "unknown"
        batch_index = metadata.get("batch_index") if isinstance(metadata, dict) else None
        batch_start_idx = _current_batch_start_index(plan, steps)
        loop_cfg = client._get_planning_loop_config()
        continue_stage = bool(metadata.get("continue_stage", False)) if isinstance(metadata, dict) else False
        max_batches = max(1, int(loop_cfg.get("max_batches_per_stage", 8)))
        current_stage_index = int(metadata.get("current_stage_index") or 0) if isinstance(metadata, dict) else 0
        current_batch_index = int(metadata.get("batch_index") or 1) if isinstance(metadata, dict) else 1
        stages_meta = list(metadata.get("stages") or []) if isinstance(metadata, dict) else []
        if continue_stage and current_batch_index < max_batches:
            next_stage = stage
        elif current_stage_index + 1 < len(stages_meta):
            next_stage = stages_meta[current_stage_index + 1]
        else:
            next_stage = None
        progress = _batch_progress_flags(
            plan=plan,
            steps=steps,
            step_results=step_results,
            next_stage=str(next_stage) if next_stage else None,
        )
        _record_agent_loop_batch_completed(client, plan, steps, step_results)
        gate_enabled, gate_reason = _should_run_batch_quality_gate(
            policy=str(loop_cfg.get("batch_quality_gate", "auto")),
            cfg=loop_cfg,
            progress=progress,
            batch_index=current_batch_index,
        )

        if gate_enabled and enable_llm_feedback:
            batch_scene = await client.capture_scene_state()
            if hasattr(client, "_filter_scene_for_task_context"):
                batch_scene = client._filter_scene_for_task_context(batch_scene)
            analyzer = GeometryFeedbackAnalyzer(client)
            analysis = await analyzer.analyze_geometry_quality(
                str(stage or "unknown"),
                batch_scene,
                step_results,
                context="general",
                task_prompt=prompt,
            )
        else:
            analysis = None
            _log_run_event(
                client,
                "agent_loop_batch_gate_skipped",
                {
                    "mode": "feedback",
                    "stage": stage,
                    "batch_index": batch_index,
                    "reason": gate_reason,
                    "progress": progress,
                },
            )

        if analysis is not None:
            _log_run_event(
                client,
                "agent_loop_batch_observed",
                {
                    "mode": "feedback",
                    "stage": stage,
                    "batch_index": batch_index,
                    "quality": analysis.quality,
                    "score": analysis.score,
                    "critical_issues": analysis.critical_issues,
                },
            )
            print(
                "[VBF] agent_loop_batch_observe "
                f"stage={stage} batch={batch_index} "
                f"quality={analysis.quality} score={analysis.score:.2f}"
            )

            loop_cfg = client._get_planning_loop_config()
            threshold = float(loop_cfg.get("batch_quality_threshold", 0.4))
            warning_accept_threshold = float(
                loop_cfg.get("batch_warning_accept_threshold", 0.6)
            )
            repair_key = (str(stage or "unknown"), int(batch_index or current_batch_index or 0))
            prior_boundary_repairs = batch_repair_attempts.get(repair_key, 0)
            current_stage_critical = _current_stage_critical_issues(analysis, str(stage or ""))
            downstream_only_critical = _has_only_downstream_critical_issues(
                analysis,
                str(stage or ""),
            )
            has_blocking_issue = _has_blocking_batch_issue(analysis, str(stage or ""))
            warning_can_defer = (
                analysis.quality == "warning"
                and analysis.score >= warning_accept_threshold
                and prior_boundary_repairs > 0
                and not has_blocking_issue
            )
            needs_repair = (
                has_blocking_issue
                or (analysis.quality == "bad" and not downstream_only_critical)
                or (analysis.score < threshold and not downstream_only_critical)
                or (bool(current_stage_critical) and not warning_can_defer)
            )
            max_batch_repairs = max(
                0,
                int(loop_cfg.get("batch_quality_max_repairs_per_batch", 2) or 0),
            )
            repair_budget_exhausted = (
                max_batch_repairs > 0
                and prior_boundary_repairs >= max_batch_repairs
                and not has_blocking_issue
            )
            repair_deferred_to_pending = False
            if needs_repair and repair_budget_exhausted:
                needs_repair = False
                repair_deferred_to_pending = True
                added = _add_analysis_pending_work(agent_loop_pending_work, analysis)
                print(
                    "[VBF] agent_loop_batch_repair_deferred "
                    f"stage={stage} batch={batch_index} attempts={prior_boundary_repairs} "
                    f"pending_added={added}"
                )
                _log_run_event(
                    client,
                    "agent_loop_batch_repair_deferred",
                    {
                        "mode": "feedback",
                        "stage": stage,
                        "batch_index": batch_index,
                        "attempts": prior_boundary_repairs,
                        "pending_added": added,
                        "quality": analysis.quality,
                        "score": analysis.score,
                    },
                )
            if not needs_repair and analysis.quality != "good" and not repair_deferred_to_pending:
                added = _add_analysis_pending_work(agent_loop_pending_work, analysis)
                if added:
                    print(
                        "[VBF] agent_loop_batch_warning_pending_work "
                        f"added={added}"
                    )
            if needs_repair:
                batch_repair_attempts[repair_key] = prior_boundary_repairs + 1
                batch_quality_repair_count += 1
                default_total_repairs = (
                    max_batches * max_batch_repairs if max_batch_repairs > 0 else 0
                )
                max_total_batch_repairs = max(
                    0,
                    int(
                        loop_cfg.get(
                            "batch_quality_max_total_repairs",
                            default_total_repairs,
                        )
                        or 0
                    ),
                )
                if (
                    max_total_batch_repairs > 0
                    and batch_quality_repair_count > max_total_batch_repairs
                ):
                    raise client._create_interrupt(
                        "Exceeded max batch quality repairs "
                        f"({max_total_batch_repairs}) at batch boundary",
                        prompt,
                        _save_path,
                        plan=plan,
                        steps=steps,
                        step_results=step_results,
                        current_index=batch_start_idx,
                        allowed_skills=allowed_skills,
                        diagnostics={"agent_loop_batch_analysis": analysis.to_dict()},
                    )
                feedback_detail = {
                    "reason": "agent_loop_batch_quality_failed",
                    "stage": stage,
                    "batch_index": batch_index,
                    "analysis": analysis.to_dict(),
                    "error": analysis.reason,
                }
                repaired_plan, repair_steps = await client._replan_from_step(
                    prompt=prompt,
                    fail_idx=batch_start_idx,
                    steps=steps,
                    step_results=step_results,
                    allowed_skills=allowed_skills,
                    save_path=_save_path,
                    feedback_detail=feedback_detail,
                    replan_fingerprint=client._build_replan_fingerprint(
                        reason="agent_loop_batch_quality_failed",
                        skill=str(stage or "unknown"),
                        error_text=analysis.reason,
                    ),
                    forced_corrective=True,
                )
                replaced_step_ids = {
                    str(step.get("step_id"))
                    for step in steps[batch_start_idx:]
                    if isinstance(step, dict) and step.get("step_id") is not None
                }
                for replaced_step_id in replaced_step_ids:
                    step_results.pop(replaced_step_id, None)
                repair_steps, skipped_repair_steps = _filter_unsafe_batch_repair_steps(
                    repair_steps,
                    prior_steps=steps[:batch_start_idx],
                    step_results=step_results,
                )
                if skipped_repair_steps:
                    print(
                        "[VBF] agent_loop_batch_repair_filtered "
                        f"stage={stage} batch={batch_index} skipped={len(skipped_repair_steps)}"
                    )
                    _log_run_event(
                        client,
                        "agent_loop_batch_repair_filtered",
                        {
                            "mode": "feedback",
                            "stage": stage,
                            "batch_index": batch_index,
                            "skipped": skipped_repair_steps,
                        },
                    )
                repair_steps = client._reindex_steps(repair_steps, batch_start_idx + 1)
                for repair_step in repair_steps:
                    if isinstance(repair_step, dict):
                        repair_step.setdefault("stage", stage)
                        repair_step["adaptive_stage"] = stage
                        repair_step["batch_index"] = batch_index
                steps = steps[:batch_start_idx] + repair_steps
                repaired_plan.setdefault("metadata", {})
                repaired_plan["metadata"].update(metadata)
                repaired_plan["steps"] = steps
                plan = repaired_plan
                i = batch_start_idx
                print(
                    "[VBF] agent_loop_batch_repair "
                    f"stage={stage} batch={batch_index} repair_steps={len(repair_steps)}"
                )
                _log_run_event(
                    client,
                    "agent_loop_batch_repair",
                    {
                        "mode": "feedback",
                        "stage": stage,
                        "batch_index": batch_index,
                        "repair_steps": len(repair_steps),
                        "quality": analysis.quality,
                        "score": analysis.score,
                    },
                )
                return True

        next_plan, next_steps = await client._plan_next_batched_stage(
            prompt=planning_prompt,
            allowed_skills=allowed_skills,
            save_path=_save_path,
            previous_plan=plan,
            completed_summary=agent_loop_completed_summary,
            pending_work=agent_loop_pending_work,
        )
        if not next_plan or not next_steps:
            return False

        next_metadata = next_plan.get("metadata") if isinstance(next_plan, dict) else {}
        stage = next_metadata.get("current_stage") if isinstance(next_metadata, dict) else None
        batch_index = next_metadata.get("batch_index") if isinstance(next_metadata, dict) else None
        remapped = client._reindex_steps(next_steps, len(steps) + 1)
        for step in remapped:
            if isinstance(step, dict):
                step.setdefault("stage", stage)
                step["adaptive_stage"] = stage
                step["batch_index"] = batch_index
        steps.extend(remapped)
        next_plan["steps"] = steps
        plan = next_plan
        agent_loop_pending_work = (
            list(next_metadata.get("remaining_work") or [])
            if isinstance(next_metadata, dict)
            else []
        )
        print(
            "[VBF] agent_loop_next_batch "
            f"stage={stage} batch={batch_index} steps={len(remapped)} total_steps={len(steps)}"
        )
        _log_run_event(
            client,
            "agent_loop_next_batch",
            {
                "mode": "feedback",
                "stage": stage,
                "batch_index": batch_index,
                "new_steps": len(remapped),
                "total_steps": len(steps),
            },
        )
        return True

    while True:
        if i >= len(steps):
            if await _append_next_agent_loop_batch_if_needed():
                continue
            break

        step = steps[i]
        step_id = step.get("step_id", f"step_{i:03d}")

        decision, post_state = await loop.execute_with_feedback(step, step_results, scene_capture)

        if post_state:
            scene_capture._cache.update(post_state)
        _record_task_result_objects(client, step_results.get(step_id))

        if decision.action in {"replan", "checkpoint"}:
            reason = decision.detail.get("reason", decision.action)
            if decision.action == "checkpoint" and reason == "execute_skill_timeout":
                diagnostics = {
                    "execute_skill_timeout": {
                        "step_id": step_id,
                        "skill": step.get("skill"),
                        "timeout_s": decision.detail.get("timeout_s"),
                        "error": decision.detail.get("error"),
                    }
                }
                raise client._create_interrupt(
                    f"Step {step_id} timed out during skill execution",
                    prompt,
                    _save_path,
                    plan=plan,
                    steps=steps,
                    step_results=step_results,
                    current_index=i,
                    allowed_skills=allowed_skills,
                    diagnostics=diagnostics,
                )

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

            replan_from_idx = i
            feedback_detail = dict(decision.detail or {})
            failing_skill = feedback_detail.get("skill") or step.get("skill") or "unknown"
            validation = getattr(decision, "validation", None)
            error_signature = feedback_detail.get("error") or (
                validation.message if validation else ""
            )
            if (
                failing_skill == "set_parent"
                and "parent object not found" in str(error_signature).lower()
            ):
                repaired_parent = _try_repair_failed_parent_step(
                    step=step,
                    steps=steps,
                    step_results=step_results,
                    completed_summary=agent_loop_completed_summary,
                )
                if repaired_parent is not None:
                    old_parent, new_parent = repaired_parent
                    step_results.pop(step_id, None)
                    print(
                        "[VBF] local_repair_parent_name "
                        f"step_id={step_id} old={old_parent} new={new_parent}"
                    )
                    _log_run_event(
                        client,
                        "local_repair_parent_name",
                        {
                            "mode": "feedback",
                            "step_id": step_id,
                            "old_parent": old_parent,
                            "new_parent": new_parent,
                        },
                    )
                    continue
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
