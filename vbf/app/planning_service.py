from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.plan_normalization import extract_skills_plan, normalize_plan, validate_plan_structure
from ..core.scene_state import SceneState
from ..core.task_ledger import TaskLedger, ledger_path_for_task
from ..core.task_state import TaskInterruptedError
from .planning_context import (
    build_json_format_retry_prompt,
    build_nonempty_steps_rescue_prompt,
    has_nonempty_steps,
    is_tool_calls_payload,
    scene_to_prompt_text,
)
from .plan_gate import build_prior_object_table, validate_and_repair_parent_refs
from .skill_capability_resolver import (
    format_skill_capability_resolution,
    resolve_skill_capability_issue,
)
from .stage_intent import (
    StageIntent,
    analyze_stage_intent,
    build_requirement_assessment_prompt,
    extract_stage_selection_text,
    infer_planning_stage,
    normalize_assessed_stage_intent,
    select_adaptive_planning_stages,
)


def _is_simple_model_asset_request(text: str) -> bool:
    normalized = (text or "").lower()
    has_model_word = bool(
        re.search(r"\b3d\s*model\b|\bmodel\b|模型|建模", normalized)
    )
    downstream_words = (
        "render",
        "presentation",
        "client",
        "premium",
        "photoreal",
        "material",
        "texture",
        "lighting",
        "animation",
        "渲染",
        "材质",
        "贴图",
        "灯光",
        "动画",
        "展示",
    )
    return has_model_word and not any(word in normalized for word in downstream_words)


def _build_stage_evidence(
    text: str,
    local_intent: StageIntent,
    llm_intent: StageIntent,
    prefer_simple_model_advisory: bool,
) -> Dict[str, Any]:
    llm_downstream = [stage for stage in llm_intent.stages if stage != "geometry_modeling"]
    local_downstream = [stage for stage in local_intent.stages if stage != "geometry_modeling"]
    explicit_geometry_only = local_intent.explicit_scope == "geometry_only"
    explicit_local_stage = local_intent.explicit_scope in {
        "explicit_stage",
        "explicit_multistage",
        "explicit_limited",
        "conflicting_explicit",
    }
    llm_added_downstream_to_explicit_geometry_only = explicit_geometry_only and bool(llm_downstream)
    llm_omitted_locally_detected_explicit_stage = explicit_local_stage and any(
        stage not in llm_intent.stages for stage in local_downstream
    )
    severe = (
        local_intent.has_conflict
        or llm_intent.has_conflict
        or llm_added_downstream_to_explicit_geometry_only
        or llm_omitted_locally_detected_explicit_stage
    )
    simple_asset_request = bool(prefer_simple_model_advisory and _is_simple_model_asset_request(text))
    advisory = (
        simple_asset_request
        and not severe
        and local_intent.stages == ["geometry_modeling"]
        and bool(llm_downstream)
        and llm_intent.explicit_scope in {"llm_inferred", "llm_low_confidence_preserved"}
    )
    if severe:
        severity = "severe"
    elif advisory:
        severity = "advisory"
    else:
        severity = "none"
    return {
        "simple_asset_request": simple_asset_request,
        "local_stages": local_intent.stages,
        "local_scope": local_intent.explicit_scope,
        "local_has_conflict": local_intent.has_conflict,
        "llm_added_downstream_to_explicit_geometry_only": llm_added_downstream_to_explicit_geometry_only,
        "llm_omitted_locally_detected_explicit_stage": llm_omitted_locally_detected_explicit_stage,
        "conflict_severity": severity,
    }


def _build_requirement_resolution_prompt(
    prompt: str,
    first_intent: StageIntent,
    local_evidence: Dict[str, Any],
) -> str:
    return (
        "Resolve a severe Blender requirement-assessment conflict before planning.\n"
        "Return plain JSON only. Use the stage contract exactly.\n\n"
        "Allowed stages, in order:\n"
        "- geometry_modeling: mesh/object construction, topology, transforms, booleans, bevels, hierarchy.\n"
        "- uv_texture_material: UV unwraps, seams, texture setup, simple color assignment, "
        "material assignment, PBR/material presets.\n"
        "- environment_lighting: lights, HDR/world/background, scene lighting setup.\n"
        "- animation: timeline, keyframes, motion, camera/object animation.\n"
        "- camera_render: render camera, render engine/settings, final still/video output.\n\n"
        "Resolution policy:\n"
        "- The final decision is LLM-driven; local evidence is advisory conflict evidence only.\n"
        "- Honor explicit user exclusions over inferred deliverables.\n"
        "- If the first LLM result omitted an explicit requested stage, restore that stage.\n"
        "- If the first LLM result added stages despite an explicit geometry-only request, remove those stages.\n"
        "- Do not generate modeling steps.\n\n"
        "Return exactly this JSON shape:\n"
        "{\n"
        '  "requested_stages": ["geometry_modeling"],\n'
        '  "excluded_stages": [],\n'
        '  "deliverable_level": "model_asset|textured_asset|lit_scene|animation|render_output|ambiguous",\n'
        '  "explicit_scope": true,\n'
        '  "confidence": 0.0,\n'
        '  "reason": "short conflict resolution explanation",\n'
        '  "risks": []\n'
        "}\n\n"
        "FIRST LLM RESULT:\n"
        f"{json.dumps(first_intent.__dict__, ensure_ascii=False)}\n\n"
        "LOCAL EVIDENCE:\n"
        f"{json.dumps(local_evidence, ensure_ascii=False)}\n\n"
        "USER REQUEST:\n"
        f"{extract_stage_selection_text(prompt)}"
    )


async def _call_requirement_assessment_llm(
    client: Any,
    messages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Call requirement assessment without forcing skill-registry initialization.

    Requirement assessment is an LLM classification task and does not need
    Blender skill schemas. Keeping this call lightweight avoids a duplicate
    vbf.list_skills RPC before the actual planning call.
    """
    try:
        return await client._adapter_call(
            messages,
            load_skills=False,
            allow_tools=False,
        )
    except TypeError as exc:
        # Some tests or external clients monkeypatch _adapter_call with the old
        # one-argument signature. Keep that compatibility path narrow.
        message = str(exc)
        if (
            "unexpected keyword" not in message
            and "positional" not in message
            and "keyword argument" not in message
        ):
            raise
        return await client._adapter_call(messages)


async def call_plan_with_format_retry(
    client: Any,
    adapter: Any,
    prompt: str,
    skills_subset: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Call planner once, then retry once on parse/shape format failures."""

    def _format(p: str) -> List[Dict[str, Any]]:
        try:
            return adapter.format_messages(p, skills_subset=skills_subset)
        except TypeError:
            return adapter.format_messages(p)

    try:
        response = await client._adapter_call(_format(prompt))
        if has_nonempty_steps(response, extract_skills_plan):
            return response
        print("[VBF] parse_stage=plan_shape retry_mode=structured_json_retry")
        retry_prompt = build_json_format_retry_prompt(prompt)
        if is_tool_calls_payload(response):
            allow_tools_prev = getattr(adapter, "_allow_tools", None)
            if isinstance(allow_tools_prev, bool):
                adapter._allow_tools = False
                try:
                    retry_response = await client._adapter_call(_format(retry_prompt))
                finally:
                    adapter._allow_tools = allow_tools_prev
            else:
                retry_response = await client._adapter_call(_format(retry_prompt))
        else:
            retry_response = await client._adapter_call(_format(retry_prompt))

        if has_nonempty_steps(retry_response, extract_skills_plan):
            return retry_response

        print("[VBF] parse_stage=plan_shape retry_mode=nonempty_steps_rescue")
        rescue_prompt = build_nonempty_steps_rescue_prompt(prompt)
        return await client._adapter_call(_format(rescue_prompt))
    except ValueError as e:
        if not client._is_llm_parse_error(e):
            raise
        match = re.search(r"parse_stage=([^)]+)", str(e))
        stage = match.group(1) if match else "unknown"
        print(f"[VBF] parse_stage={stage} retry_mode=structured_json_retry")
        retry_prompt = build_json_format_retry_prompt(prompt)
        return await client._adapter_call(_format(retry_prompt))


async def assess_adaptive_stage_intent(client: Any, prompt: str) -> StageIntent:
    text = client._extract_stage_selection_text(prompt)
    cfg = client._get_requirement_assessment_config()
    local_fallback_enabled = bool(cfg.get("enable_local_fallback", False))
    local_intent = client._analyze_stage_intent(text)
    fallback = local_intent if local_fallback_enabled else None
    mode = str(cfg.get("mode", "auto") or "auto").strip().lower()
    if mode in {"off", "false", "disabled", "none"}:
        if fallback is not None:
            return fallback
        raise ValueError(
            "requirement_assessment_disabled_without_local_fallback: "
            "enable requirement_assessment or set enable_local_fallback=true"
        )

    threshold = float(cfg.get("use_llm_when_confidence_below", 1.0))
    if mode == "auto" and fallback is not None and fallback.confidence >= threshold:
        return fallback

    try:
        prompt_text = client._build_requirement_assessment_prompt(prompt, fallback)
        messages = [
            {
                "role": "system",
                "content": (
                    "You assess Blender task requirements before planning. "
                    "Return one strict JSON object only."
                ),
            },
            {"role": "user", "content": prompt_text},
        ]
        timeout_seconds = max(1.0, float(cfg.get("timeout_seconds", 45)))
        if mode == "always":
            payload = await _call_requirement_assessment_llm(client, messages)
        else:
            # In auto mode the adapter may still be initializing and loading skill
            # schemas from Blender. Do not wrap this in an outer wait_for, because
            # cancelling the WebSocket list_skills call can leave the adapter in a
            # half-initialized state. The adapter/rate-limiter HTTP timeout still
            # bounds the actual provider request.
            payload = await _call_requirement_assessment_llm(client, messages)
        low_confidence_threshold = max(
            0.0,
            min(1.0, float(cfg.get("low_confidence_threshold", 0.7))),
        )
        intent = client._normalize_assessed_stage_intent(
            payload,
            fallback,
            low_confidence_threshold=low_confidence_threshold,
        )
        local_evidence = _build_stage_evidence(
            text,
            local_intent,
            intent,
            bool(cfg.get("prefer_geometry_for_simple_model_requests", True)),
        )
        if local_evidence["conflict_severity"] == "advisory":
            print(
                "[VBF] requirement_assessment local_advisory=simple_model_downstream "
                f"llm_stages={','.join(intent.stages)} "
                f"local_scope={local_evidence['local_scope']}"
            )
        elif local_evidence["conflict_severity"] == "severe":
            print(
                "[VBF] requirement_assessment conflict_resolution=llm_second_pass "
                f"llm_stages={','.join(intent.stages)} "
                f"local_stages={','.join(local_intent.stages)}"
            )
            try:
                resolution_prompt = _build_requirement_resolution_prompt(
                    prompt,
                    intent,
                    local_evidence,
                )
                resolution_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You resolve Blender task requirement conflicts before planning. "
                            "Return one strict JSON object only."
                        ),
                    },
                    {"role": "user", "content": resolution_prompt},
                ]
                if mode == "always":
                    resolution_payload = await _call_requirement_assessment_llm(
                        client,
                        resolution_messages,
                    )
                else:
                    resolution_payload = await _call_requirement_assessment_llm(
                        client,
                        resolution_messages,
                    )
                intent = client._normalize_assessed_stage_intent(
                    resolution_payload,
                    intent,
                    low_confidence_threshold=low_confidence_threshold,
                )
            except Exception as resolution_error:
                print(
                    "[VBF] requirement_assessment "
                    "conflict_resolution_failed_using_first_llm: "
                    f"{resolution_error}"
                )
        print(
            "[VBF] requirement_assessment "
            f"stages={','.join(intent.stages)} "
            f"confidence={intent.confidence:.2f} "
            f"scope={intent.explicit_scope}"
        )
        return intent
    except Exception as e:
        fallback_for_error = fallback
        if fallback_for_error is None:
            print(
                "[VBF] requirement_assessment "
                f"llm_failed_local_fallback_disabled: {e}"
            )
            raise RuntimeError(
                f"requirement_assessment_llm_failed_local_fallback_disabled: {e}"
            ) from e
        print(f"[VBF] requirement_assessment fallback_to_local: {e}")
        if (
            str(cfg.get("fallback_policy", "preserve_more_stages")) == "preserve_more_stages"
            and fallback_for_error.confidence < 0.7
        ):
            preserved = list(fallback_for_error.stages)
            for stage in ("uv_texture_material", "environment_lighting", "camera_render"):
                if stage not in preserved:
                    preserved.append(stage)
            return StageIntent(
                stages=preserved,
                primary_stage=preserved[-1],
                confidence=fallback_for_error.confidence,
                explicit_scope="local_fallback_preserved",
                has_conflict=fallback_for_error.has_conflict,
            )
        return fallback_for_error


async def plan_skill_task_adaptive_staged(
    client: Any,
    prompt: str,
    allowed_skills: List[str],
    save_path: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    stage_intent = await client._assess_adaptive_stage_intent(prompt)
    stages = stage_intent.stages
    planning_loop = client._get_planning_loop_config()
    loop_mode = str(planning_loop.get("mode", "full_plan") or "full_plan").strip().lower()
    if loop_mode in {"agent_loop", "plan_execute_loop", "interleaved"}:
        max_steps = max(1, int(planning_loop.get("max_steps_per_batch", 12)))
        max_batches = max(1, int(planning_loop.get("max_batches_per_stage", 8)))
        stage_index = 0
        stage = stages[stage_index]
        stage_skills = client._filter_skills_for_adaptive_stage(allowed_skills, stage)
        if not stage_skills:
            raise ValueError(
                "planning_context_missing_stage_skill_coverage: "
                f"stage={stage}"
            )
        stage_prompt = client._build_batched_stage_prompt(
            prompt=prompt,
            stage=stage,
            batch_index=1,
            max_steps=max_steps,
            completed_summary=[],
            pending_work=[],
        )
        batch_plan, batch_steps = await client._plan_skill_task(
            stage_prompt,
            stage_skills,
            save_path,
        )
        remapped_steps = client._reindex_steps(batch_steps, 1)
        for step in remapped_steps:
            if isinstance(step, dict):
                step.setdefault("stage", stage)
                step["adaptive_stage"] = stage
                step["batch_index"] = 1
        continue_stage = _infer_continue_stage(batch_plan, batch_steps, max_steps)
        pending_work = _extract_remaining_work(batch_plan)

        task_id = getattr(client, "_task_id", "planning")
        runtime_paths = getattr(client, "_runtime_paths", {}) or {}
        ledger_path = ledger_path_for_task(
            runtime_paths.get("cache_dir", os.path.dirname(save_path)),
            task_id,
        )
        ledger = TaskLedger(task_id=str(task_id or "planning"), prompt=prompt, stages=stages)
        ledger.current_stage_index = stage_index
        ledger.record_planned_batch(
            stage=stage,
            batch_index=1,
            step_ids=[str(step.get("step_id")) for step in remapped_steps if step.get("step_id")],
            continue_stage=continue_stage,
            remaining_work=pending_work,
            response_id=batch_plan.get("response_id") if isinstance(batch_plan, dict) else None,
        )
        if bool(planning_loop.get("save_partial_plan", True)):
            ledger.save(ledger_path)

        plan: Dict[str, Any] = {
            "vbf_version": "2.4.0",
            "plan_type": "skills_plan",
            "steps": remapped_steps,
            "metadata": {
                "planning_mode": "adaptive_agent_loop",
                "stages": stages,
                "current_stage_index": stage_index,
                "current_stage": stage,
                "batch_index": 1,
                "max_steps_per_batch": max_steps,
                "max_batches_per_stage": max_batches,
                "continue_stage": continue_stage,
                "remaining_work": pending_work,
                "ledger_path": ledger_path,
            },
        }
        plan = normalize_plan(plan)
        steps = validate_plan_structure(plan)
        print(
            "[VBF] planning_mode=adaptive_agent_loop "
            f"stage={stage} batch=1 steps={len(steps)} "
            f"continue_stage={str(continue_stage).lower()} ledger={ledger_path}"
        )
        return plan, steps

    if loop_mode in {"batched", "batch"}:
        max_steps = max(1, int(planning_loop.get("max_steps_per_batch", 12)))
        max_batches = max(1, int(planning_loop.get("max_batches_per_stage", 8)))
        all_steps: List[Dict[str, Any]] = []
        stage_counts: Dict[str, int] = {}
        completed_summary: List[Dict[str, Any]] = []
        pending_work: List[str] = []
        task_id = getattr(client, "_task_id", "planning")
        runtime_paths = getattr(client, "_runtime_paths", {}) or {}
        ledger_path = ledger_path_for_task(
            runtime_paths.get("cache_dir", os.path.dirname(save_path)),
            task_id,
        )
        ledger = TaskLedger(task_id=str(task_id or "planning"), prompt=prompt, stages=stages)

        for stage_index, stage in enumerate(stages):
            stage_steps_total = 0
            pending_work = []
            for batch_index in range(1, max_batches + 1):
                stage_skills = client._filter_skills_for_adaptive_stage(allowed_skills, stage)
                if not stage_skills:
                    raise ValueError(
                        "planning_context_missing_stage_skill_coverage: "
                        f"stage={stage}"
                    )
                stage_prompt = client._build_batched_stage_prompt(
                    prompt=prompt,
                    stage=stage,
                    batch_index=batch_index,
                    max_steps=max_steps,
                    completed_summary=completed_summary,
                    pending_work=pending_work,
                )
                try:
                    batch_plan, batch_steps = await client._plan_skill_task(
                        stage_prompt,
                        stage_skills,
                        save_path,
                    )
                except Exception as e:
                    partial_plan = {
                        "vbf_version": "2.4.0",
                        "plan_type": "skills_plan",
                        "steps": all_steps,
                        "metadata": {
                            "planning_mode": "adaptive_batched",
                            "stages": stages,
                            "failed_stage": stage,
                            "failed_batch_index": batch_index,
                            "ledger_path": ledger_path,
                        },
                    }
                    ledger.last_error = str(e)
                    if bool(planning_loop.get("save_partial_plan", True)):
                        ledger.save(ledger_path)
                    raise client._create_interrupt(
                        f"Batched plan generation failed at stage={stage} batch={batch_index}",
                        prompt,
                        save_path,
                        plan=partial_plan,
                        steps=all_steps,
                        allowed_skills=allowed_skills,
                        diagnostics={
                            "planning_loop": {
                                "mode": "batched",
                                "failed_stage": stage,
                                "failed_batch_index": batch_index,
                                "ledger_path": ledger_path,
                            }
                        },
                        cause=e,
                    )
                remapped_steps = client._reindex_steps(batch_steps, len(all_steps) + 1)
                for step in remapped_steps:
                    if isinstance(step, dict):
                        step.setdefault("stage", stage)
                        step["adaptive_stage"] = stage
                        step["batch_index"] = batch_index
                all_steps.extend(remapped_steps)
                stage_steps_total += len(remapped_steps)
                continue_stage = _infer_continue_stage(batch_plan, batch_steps, max_steps)
                pending_work = _extract_remaining_work(batch_plan)
                step_ids = [str(step.get("step_id")) for step in remapped_steps if step.get("step_id")]
                ledger.current_stage_index = stage_index
                ledger.record_planned_batch(
                    stage=stage,
                    batch_index=batch_index,
                    step_ids=step_ids,
                    continue_stage=continue_stage,
                    remaining_work=pending_work,
                    response_id=batch_plan.get("response_id") if isinstance(batch_plan, dict) else None,
                )
                if bool(planning_loop.get("save_partial_plan", True)):
                    ledger.save(ledger_path)
                completed_summary.append(
                    {
                        "stage": stage,
                        "batch_index": batch_index,
                        "steps": len(remapped_steps),
                        "step_ids": step_ids,
                        "remaining_work": pending_work,
                    }
                )
                if not continue_stage:
                    break
            stage_counts[stage] = stage_steps_total
            ledger.advance_stage()

        if not all_steps:
            raise ValueError("adaptive_batched planning produced no executable steps")

        merged_plan: Dict[str, Any] = {
            "vbf_version": "2.4.0",
            "plan_type": "skills_plan",
            "steps": all_steps,
            "metadata": {
                "planning_mode": "adaptive_batched",
                "stages": stages,
                "stage_step_counts": stage_counts,
                "max_steps_per_batch": max_steps,
                "max_batches_per_stage": max_batches,
                "ledger_path": ledger_path,
            },
        }
        merged_plan = normalize_plan(merged_plan)
        merged_steps = validate_plan_structure(merged_plan)
        print(
            "[VBF] planning_mode=adaptive_batched "
            f"stages={','.join(stages)} "
            f"steps={len(merged_steps)} "
            f"ledger={ledger_path}"
        )
        return merged_plan, merged_steps
    if stages == ["geometry_modeling"]:
        return await client._plan_skill_task(
            client._build_adaptive_stage_prompt(prompt, "geometry_modeling"),
            client._filter_skills_for_adaptive_stage(allowed_skills, "geometry_modeling"),
            save_path,
        )

    print(
        "[VBF] planning_mode=adaptive_staged "
        f"stages={','.join(stages)} "
        f"intent_confidence={stage_intent.confidence:.2f} "
        f"intent_scope={stage_intent.explicit_scope}"
    )
    all_steps: List[Dict[str, Any]] = []
    stage_counts: Dict[str, int] = {}

    for stage in stages:
        stage_skills = client._filter_skills_for_adaptive_stage(allowed_skills, stage)
        if not stage_skills:
            raise ValueError(
                "planning_context_missing_stage_skill_coverage: "
                f"stage={stage}"
            )
        stage_prompt = client._build_adaptive_stage_prompt(prompt, stage)
        _stage_plan, stage_steps = await client._plan_skill_task(stage_prompt, stage_skills, save_path)
        remapped_steps = client._reindex_steps(stage_steps, len(all_steps) + 1)
        for step in remapped_steps:
            if isinstance(step, dict):
                step.setdefault("stage", stage)
                step["adaptive_stage"] = stage
        all_steps.extend(remapped_steps)
        stage_counts[stage] = len(remapped_steps)

    if not all_steps:
        raise ValueError("adaptive_staged planning produced no executable steps")

    merged_plan: Dict[str, Any] = {
        "vbf_version": "2.4.0",
        "plan_type": "skills_plan",
        "steps": all_steps,
        "metadata": {
            "planning_mode": "adaptive_staged",
            "stages": stages,
            "stage_step_counts": stage_counts,
        },
    }
    merged_plan = normalize_plan(merged_plan)
    merged_steps = validate_plan_structure(merged_plan)
    return merged_plan, merged_steps


def _extract_remaining_work(plan: Dict[str, Any]) -> List[str]:
    remaining = plan.get("remaining_work")
    if isinstance(remaining, list):
        return [str(item) for item in remaining if str(item).strip()]
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    remaining = metadata.get("remaining_work")
    if isinstance(remaining, list):
        return [str(item) for item in remaining if str(item).strip()]
    return []


def _infer_continue_stage(
    plan: Dict[str, Any],
    steps: List[Dict[str, Any]],
    max_steps: int,
) -> bool:
    for source in (plan, plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}):
        value = source.get("continue_stage") if isinstance(source, dict) else None
        if isinstance(value, bool):
            return value
    return len(steps) >= max_steps


def build_batched_stage_prompt(
    client: Any,
    *,
    prompt: str,
    stage: str,
    batch_index: int,
    max_steps: int,
    completed_summary: List[Dict[str, Any]],
    pending_work: List[str],
) -> str:
    completed_text = json.dumps(completed_summary[-8:], ensure_ascii=False, default=str)
    pending_text = json.dumps(pending_work, ensure_ascii=False, default=str)
    prior_objects = build_prior_object_table(completed_summary)
    prior_objects_text = json.dumps(prior_objects[-40:], ensure_ascii=False, default=str)
    base = client._build_adaptive_stage_prompt(prompt, stage)
    return (
        f"{base}\n\n"
        "PLANNING LOOP: BATCHED EXECUTION.\n"
        f"- Generate ONLY the next batch for stage `{stage}`.\n"
        f"- Batch index: {batch_index}.\n"
        f"- Hard limit: return at most {max_steps} executable steps.\n"
        "- Do not try to complete the entire user request in this response.\n"
        "- Use existing object names from PRIOR BATCH OBJECT TABLE directly; do not $ref prior batch steps.\n"
        "- For set_parent.parent_name, use exactly one listed object_name or a parent created earlier in this same batch.\n"
        "- Do not invent synonymous parent names such as Hypercar_Turntable_Control if they are not listed.\n"
        "- If this stage needs more work after this batch, set top-level `continue_stage` to true.\n"
        "- If this stage is complete after this batch, set top-level `continue_stage` to false.\n"
        "- Include top-level `remaining_work` as short strings for the next batch.\n"
        "- Return one JSON object with top-level `steps`, `continue_stage`, and `remaining_work`.\n\n"
        f"COMPLETED BATCH SUMMARY:\n{completed_text}\n\n"
        f"PRIOR BATCH OBJECT TABLE:\n{prior_objects_text}\n\n"
        f"PENDING WORK FROM PRIOR BATCH:\n{pending_text}\n"
    )


async def plan_next_batched_stage(
    client: Any,
    *,
    prompt: str,
    allowed_skills: List[str],
    save_path: str,
    previous_plan: Dict[str, Any],
    completed_summary: List[Dict[str, Any]],
    pending_work: List[str],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    metadata = previous_plan.get("metadata") if isinstance(previous_plan.get("metadata"), dict) else {}
    planning_mode = metadata.get("planning_mode")
    if planning_mode not in {"adaptive_batched", "adaptive_agent_loop"}:
        return None, []

    stages = list(metadata.get("stages") or ["geometry_modeling"])
    stage_index = int(metadata.get("current_stage_index") or 0)
    batch_index = int(metadata.get("batch_index") or 1)
    max_steps = max(1, int(metadata.get("max_steps_per_batch") or 12))
    continue_stage = bool(metadata.get("continue_stage", False))
    max_batches_per_stage = max(
        1,
        int(client._get_planning_loop_config().get("max_batches_per_stage", 8)),
    )

    if continue_stage and batch_index < max_batches_per_stage:
        next_stage_index = stage_index
        next_batch_index = batch_index + 1
    else:
        next_stage_index = stage_index + 1
        next_batch_index = 1

    if next_stage_index >= len(stages):
        return None, []

    stage = stages[next_stage_index]
    stage_skills = client._filter_skills_for_adaptive_stage(allowed_skills, stage)
    if not stage_skills:
        raise ValueError(
            "planning_context_missing_stage_skill_coverage: "
            f"stage={stage}"
        )
    stage_prompt = build_batched_stage_prompt(
        client,
        prompt=prompt,
        stage=stage,
        batch_index=next_batch_index,
        max_steps=max_steps,
        completed_summary=completed_summary,
        pending_work=pending_work,
    )
    plan, steps = await client._plan_skill_task(stage_prompt, stage_skills, save_path)
    plan.setdefault("metadata", {})
    plan["metadata"].update(
        {
            "planning_mode": planning_mode,
            "stages": stages,
            "current_stage_index": next_stage_index,
            "current_stage": stage,
            "batch_index": next_batch_index,
            "max_steps_per_batch": max_steps,
            "continue_stage": _infer_continue_stage(plan, steps, max_steps),
            "remaining_work": _extract_remaining_work(plan),
        }
    )
    prior_objects = build_prior_object_table(completed_summary)
    if prior_objects:
        validate_and_repair_parent_refs(plan, prior_objects)
    return plan, steps


async def plan_skill_task_two_stage(
    client: Any,
    prompt: str,
    allowed_skills: List[str],
    save_path: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    geometry_skills, presentation_skills = client._classify_skills_for_two_stage(allowed_skills)
    if not geometry_skills or not presentation_skills:
        return await client._plan_skill_task(prompt, allowed_skills, save_path)

    print(
        "[VBF] planning_mode=two_stage "
        f"geometry_skills={len(geometry_skills)} "
        f"presentation_skills={len(presentation_skills)}"
    )

    geometry_prompt = client._build_geometry_stage_prompt(prompt)
    geom_plan, geom_steps = await client._plan_skill_task(
        geometry_prompt,
        geometry_skills,
        save_path,
    )

    presentation_prompt = client._build_presentation_stage_prompt(prompt)
    try:
        pres_plan, pres_steps = await client._plan_skill_task(
            presentation_prompt,
            presentation_skills,
            save_path,
        )
    except TaskInterruptedError:
        raise
    except Exception as e:
        print(f"[VBF] Stage-2 planning failed, keeping geometry-only plan: {e}")
        return geom_plan, geom_steps

    merged_plan, merged_steps = client._merge_two_stage_plans(
        geom_plan,
        geom_steps,
        pres_plan,
        pres_steps,
    )
    merged_plan = normalize_plan(merged_plan)
    merged_steps = validate_plan_structure(merged_plan)
    return merged_plan, merged_steps


async def plan_skill_task_auto(
    client: Any,
    prompt: str,
    allowed_skills: List[str],
    save_path: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    mode = client._get_planning_mode()
    if mode in {"adaptive", "adaptive_staged"}:
        try:
            return await client._plan_skill_task_adaptive_staged(prompt, allowed_skills, save_path)
        except TaskInterruptedError:
            raise
        except Exception as e:
            if "requirement_assessment_" in str(e):
                raise
            print(f"[VBF] adaptive_staged planning fallback to two-stage/single-stage: {e}")
    use_two_stage = mode in {"two_stage", "two-stage"} or (
        mode in {"auto"}
        and client._should_use_two_stage_planning(prompt, allowed_skills)
    )
    if mode in {"single", "single_stage"}:
        use_two_stage = False

    if use_two_stage:
        try:
            return await client._plan_skill_task_two_stage(prompt, allowed_skills, save_path)
        except TaskInterruptedError:
            raise
        except Exception as e:
            print(f"[VBF] two_stage planning fallback to single-stage: {e}")
    return await client._plan_skill_task(prompt, allowed_skills, save_path)


async def plan_skill_task(
    client: Any,
    prompt: str,
    allowed_skills: List[str],
    save_path: str,
) -> Tuple[Dict, List]:
    """Generate skill plan via adapter with checkpoint on failure."""
    try:
        adapter = await client._ensure_adapter()
        topk = max(20, int(os.getenv("VBF_SKILL_TOPK", "60")))
        expand_factor = max(1.2, float(os.getenv("VBF_SKILL_TOPK_EXPAND_FACTOR", "1.6")))
        planning_context = client._get_planning_context()
        allow_full_skill_fallback = bool(
            planning_context.get("allow_full_skill_fallback", False)
        )

        subset_candidates: List[List[str]] = []
        try:
            first_subset = client._derive_skill_subset(adapter, prompt, allowed_skills, topk)
        except ValueError as e:
            if "planning_context_missing_required_capability" not in str(e):
                raise
            first_subset = list(allowed_skills)
        subset_candidates.append(first_subset)

        expanded_size = min(len(allowed_skills), int(round(topk * expand_factor)))
        if expanded_size > len(first_subset):
            try:
                subset_candidates.append(
                    client._derive_skill_subset(adapter, prompt, allowed_skills, expanded_size)
                )
            except ValueError as e:
                if "planning_context_missing_required_capability" not in str(e):
                    raise
                subset_candidates.append(list(allowed_skills))
        if allow_full_skill_fallback and len(allowed_skills) > len(subset_candidates[-1]):
            subset_candidates.append(list(allowed_skills))

        seen_subset_keys: Set[Tuple[str, ...]] = set()
        last_error: Optional[Exception] = None

        for round_idx, skill_subset in enumerate(subset_candidates, start=1):
            subset_key = tuple(skill_subset)
            if subset_key in seen_subset_keys:
                continue
            seen_subset_keys.add(subset_key)
            raw_plan: Any = None
            raw_plan_snapshot: Any = None
            plan: Optional[Dict[str, Any]] = None

            print(
                "[VBF] planning_subset "
                f"round={round_idx}/{len(subset_candidates)} "
                f"skills={len(skill_subset)}"
            )
            try:
                raw_plan = await client._call_plan_with_format_retry(
                    adapter,
                    prompt,
                    skills_subset=skill_subset,
                )
                raw_plan_snapshot = client._snapshot_payload(raw_plan)
                client._record_pre_normalize_plan_snapshot(raw_plan_snapshot, stage="plan_round")
                plan = normalize_plan(raw_plan)
                steps = client._validate_plan_with_schema_autofix(plan, adapter, skill_subset)
                return plan, steps
            except ValueError as e:
                last_error = e
                capability_resolution = {}
                capability_text = ""
                if plan is not None and "plan_gate_" in str(e):
                    capability_resolution = resolve_skill_capability_issue(
                        adapter=adapter,
                        allowed_skills=skill_subset,
                        plan=plan,
                        error_message=str(e),
                    )
                    capability_text = format_skill_capability_resolution(capability_resolution)
                    if capability_text:
                        print(
                            "[VBF] skill_capability_resolution "
                            f"classification={capability_resolution.get('classification')}",
                            flush=True,
                        )
                client._record_plan_shape_failure(
                    f"{e}\n\n{capability_text}" if capability_text else str(e),
                    raw_plan_snapshot if raw_plan_snapshot is not None else raw_plan,
                    stage="plan_round",
                )
                if not client._is_recoverable_plan_error(str(e)):
                    raise
                repair_prompt = client._build_plan_repair_prompt(prompt, str(e))
                if capability_text:
                    repair_prompt = f"{repair_prompt}\n\n{capability_text}\n"
                repaired_raw_plan: Any = None
                repaired_raw_plan_snapshot: Any = None
                repaired_plan: Optional[Dict[str, Any]] = None
                try:
                    repaired_raw_plan = await client._call_plan_with_format_retry(
                        adapter,
                        repair_prompt,
                        skills_subset=skill_subset,
                    )
                    repaired_raw_plan_snapshot = client._snapshot_payload(repaired_raw_plan)
                    client._record_pre_normalize_plan_snapshot(
                        repaired_raw_plan_snapshot,
                        stage="plan_round_repair",
                    )
                    repaired_plan = normalize_plan(repaired_raw_plan)
                    steps = client._validate_plan_with_schema_autofix(repaired_plan, adapter, skill_subset)
                    return repaired_plan, steps
                except ValueError as repair_err:
                    last_error = repair_err
                    repair_capability_text = ""
                    if repaired_plan is not None and "plan_gate_" in str(repair_err):
                        repair_resolution = resolve_skill_capability_issue(
                            adapter=adapter,
                            allowed_skills=skill_subset,
                            plan=repaired_plan,
                            error_message=str(repair_err),
                        )
                        repair_capability_text = format_skill_capability_resolution(repair_resolution)
                        if repair_capability_text:
                            print(
                                "[VBF] skill_capability_resolution "
                                f"classification={repair_resolution.get('classification')} "
                                "stage=plan_round_repair",
                                flush=True,
                            )
                    client._record_plan_shape_failure(
                        (
                            f"{repair_err}\n\n{repair_capability_text}"
                            if repair_capability_text
                            else str(repair_err)
                        ),
                        repaired_raw_plan_snapshot
                        if repaired_raw_plan_snapshot is not None
                        else repaired_raw_plan,
                        stage="plan_round_repair",
                    )
                    if not client._is_recoverable_plan_error(str(repair_err)):
                        raise
                    continue

        if last_error is not None:
            raise last_error
        raise ValueError("Plan generation failed with empty subset candidate list")
    except ValueError as e:
        if "not configured" in str(e):
            raise client._create_interrupt(
                "LLM not configured. Set VBF_LLM_BASE_URL/API_KEY/MODEL",
                prompt, save_path,
                allowed_skills=allowed_skills, cause=e
            )
        raise client._create_interrupt(
            f"Plan generation failed: {e}",
            prompt, save_path, allowed_skills=allowed_skills, cause=e
        )
    except TaskInterruptedError:
        raise
    except Exception as e:
        raise client._create_interrupt(
            f"Plan generation failed: {e}",
            prompt, save_path, allowed_skills=allowed_skills, cause=e
        )


async def request_replan(
    client: Any,
    prompt: str,
    from_step_id: str,
    current_plan: Dict,
    step_results: Dict,
    save_path: str,
) -> Tuple[Dict, List]:
    """Request LLM to regenerate plan from given step with current scene context."""
    try:
        adapter = await client._ensure_adapter()
    except Exception as e:
        raise client._create_interrupt("Cannot replan: LLM not available", prompt, save_path) from e

    allowed_skills = await client.list_skills()
    scene = await client.capture_scene_state()
    if hasattr(client, "_filter_scene_for_task_context"):
        scene = client._filter_scene_for_task_context(scene)

    replan_prompt = f"""Replanning request from step: {from_step_id}
Original prompt: {prompt}

Current scene state:
{scene_to_prompt_text(scene, max_objects=20)}

Completed steps:
{json.dumps(step_results, indent=2, ensure_ascii=False)}

        Please generate a new plan starting from step "{from_step_id}".
Consider the current scene state when planning.
"""
    raw_plan: Any = None
    raw_plan_snapshot: Any = None
    try:
        raw_plan = await client._call_plan_with_format_retry(
            adapter,
            replan_prompt,
            skills_subset=allowed_skills,
        )
        raw_plan_snapshot = client._snapshot_payload(raw_plan)
        client._record_pre_normalize_plan_snapshot(raw_plan_snapshot, stage="request_replan")
        plan = normalize_plan(raw_plan)
        steps = validate_plan_structure(plan)
        if not steps:
            raise ValueError("No steps in replan")
        return plan, steps
    except ValueError as e:
        client._record_plan_shape_failure(
            str(e),
            raw_plan_snapshot if raw_plan_snapshot is not None else raw_plan,
            stage="request_replan",
        )
        raise client._create_interrupt(f"Replan failed: {e}", prompt, save_path, cause=e)


async def replan_from_step(
    client: Any,
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
    adapter = await client._ensure_adapter()
    scene = await client.capture_scene_state()
    if hasattr(client, "_filter_scene_for_task_context"):
        scene = client._filter_scene_for_task_context(scene)

    failed_step = steps[fail_idx] if fail_idx < len(steps) else {}
    failed_step_id = failed_step.get("step_id", "unknown")
    failed_skill = failed_step.get("skill", "unknown")
    failed_result = step_results.get(failed_step_id, {})
    failure_signature = (feedback_detail or {}).get("error", "")
    current_stage = (
        (feedback_detail or {}).get("stage")
        or failed_step.get("adaptive_stage")
        or failed_step.get("stage")
        or client._infer_planning_stage(prompt)
    )

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

Current adaptive stage:
{current_stage}

Current scene state:
{scene_to_prompt_text(scene, max_objects=20)}

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
5) For newly created objects, use `$ref` from the creation step outputs in relationship/modify steps.
6) Existing scene objects may be referenced by exact name only if they appear in Current scene state.
7) Registered skill signatures are authoritative: use the exact skill name and only the parameters exposed by that skill's description/signature.
8) If a modeling intent needs an unsupported parameter on the chosen skill, choose another registered skill that supports it or add a later registered transform/modify step.
9) Do not invent optional args that are not in the skill schema.
{client._modeling_quality_contract()}
{corrective_block}
"""
    subset_small = client._derive_skill_subset(
        adapter,
        replan_prompt,
        allowed_skills,
        min(140, max(30, int(os.getenv("VBF_REPLAN_SKILL_TOPK", "70")))),
        stage=str(current_stage or "geometry_modeling"),
    )
    subset_candidates: List[List[str]] = [subset_small]
    if len(allowed_skills) > len(subset_small):
        subset_candidates.append(list(allowed_skills))

    last_error: Optional[Exception] = None
    for subset in subset_candidates:
        raw_plan: Any = None
        raw_plan_snapshot: Any = None
        plan: Optional[Dict[str, Any]] = None
        try:
            model_config = getattr(adapter, "_model_config", None)
            old_tool_only_rounds = None
            if isinstance(model_config, dict):
                old_tool_only_rounds = model_config.get("max_consecutive_tool_only_rounds")
                model_config["max_consecutive_tool_only_rounds"] = min(
                    2,
                    int(old_tool_only_rounds or 2),
                )
            try:
                raw_plan = await client._call_plan_with_format_retry(
                    adapter,
                    replan_prompt,
                    skills_subset=subset,
                )
            finally:
                if isinstance(model_config, dict):
                    if old_tool_only_rounds is None:
                        model_config.pop("max_consecutive_tool_only_rounds", None)
                    else:
                        model_config["max_consecutive_tool_only_rounds"] = old_tool_only_rounds
            raw_plan_snapshot = client._snapshot_payload(raw_plan)
            client._record_pre_normalize_plan_snapshot(raw_plan_snapshot, stage="feedback_replan")
            plan = normalize_plan(raw_plan)
            new_steps = client._validate_plan_with_schema_autofix(plan, adapter, subset)
            return plan, new_steps
        except ValueError as e:
            last_error = e
            capability_text = ""
            if plan is not None and "plan_gate_" in str(e):
                capability_resolution = resolve_skill_capability_issue(
                    adapter=adapter,
                    allowed_skills=subset,
                    plan=plan,
                    error_message=str(e),
                )
                capability_text = format_skill_capability_resolution(capability_resolution)
                if capability_text:
                    print(
                        "[VBF] skill_capability_resolution "
                        f"classification={capability_resolution.get('classification')} "
                        "stage=feedback_replan",
                        flush=True,
                    )
            client._record_plan_shape_failure(
                f"{e}\n\n{capability_text}" if capability_text else str(e),
                raw_plan_snapshot if raw_plan_snapshot is not None else raw_plan,
                stage="feedback_replan",
            )
            if not client._is_recoverable_plan_error(str(e)):
                raise
            if capability_text and capability_text not in replan_prompt:
                replan_prompt = f"{replan_prompt}\n\n{capability_text}\n"
            continue

    if last_error is not None:
        raise last_error
    raise ValueError("Replan generation failed without candidate subsets")


def inject_scene_context(
    client: Any,
    prompt: str,
    scene: SceneState,
    max_objects: Optional[int] = None,
) -> str:
    scene_text = scene_to_prompt_text(scene, max_objects=max_objects)
    return f"""Current Blender scene state:
{scene_text}

--- USER REQUEST ---
{prompt}

Planning constraints:
- The final model must satisfy the user request semantically, not just produce arbitrary primitives.
- Generate coherent, connected modeling steps toward a complete result.
- Every geometry creation step must specify explicit dimensions, locations, and semantic names.
{client._modeling_quality_contract()}
"""
