from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Set


GATEWAY_SKILLS = {"ops_search", "ops_introspect", "ops_invoke", "py_call", "py_set"}


def _tokens(value: Any) -> Set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _schema_keys(schema: Any) -> Set[str]:
    return set(schema.keys()) if isinstance(schema, dict) else set()


def _required_params(schema: Any) -> Set[str]:
    if not isinstance(schema, dict):
        return set()
    required: Set[str] = set()
    for name, info in schema.items():
        if isinstance(info, dict) and info.get("required") is True:
            required.add(str(name))
    return required


def _get_skill_schema(adapter: Any, skill_name: str) -> Dict[str, Any]:
    try:
        schema = adapter.get_skill_params(skill_name)
    except Exception:
        schema = None
    return schema if isinstance(schema, dict) else {}


def _get_skill_description(adapter: Any, skill_name: str) -> str:
    try:
        desc = adapter.get_skill_description(skill_name)
    except Exception:
        desc = ""
    return desc if isinstance(desc, str) else ""


def parse_plan_gate_issue(error_message: str) -> Dict[str, Any]:
    text = error_message or ""
    unknown = re.search(
        r"plan_gate_unknown_args:\s*step\[(\d+)\]\s*skill=([^\s]+)\s*unknown=(\[[^\]]*\])",
        text,
    )
    if unknown:
        try:
            args = ast.literal_eval(unknown.group(3))
        except Exception:
            args = []
        return {
            "kind": "unknown_args",
            "step_index": int(unknown.group(1)),
            "skill": unknown.group(2),
            "args": [str(item) for item in args if isinstance(item, str)],
        }

    missing = re.search(
        r"plan_gate_missing_required:\s*step\[(\d+)\]\s*skill=([^\s]+)\s*missing arg=([^\s]+)",
        text,
    )
    if missing:
        return {
            "kind": "missing_required",
            "step_index": int(missing.group(1)),
            "skill": missing.group(2),
            "args": [missing.group(3)],
        }

    mismatch = re.search(
        r"plan_gate_type_mismatch:\s*step\[(\d+)\]\s*skill=([^\s]+)\s*arg=([^\s]+)",
        text,
    )
    if mismatch:
        return {
            "kind": "type_mismatch",
            "step_index": int(mismatch.group(1)),
            "skill": mismatch.group(2),
            "args": [mismatch.group(3)],
        }

    unknown_skill = re.search(
        r"plan_gate_unknown_skill:\s*step\[(\d+)\]\s*skill=([^'\s]+|'[^']+')",
        text,
    )
    if unknown_skill:
        skill = unknown_skill.group(2).strip("'")
        return {
            "kind": "unknown_skill",
            "step_index": int(unknown_skill.group(1)),
            "skill": skill,
            "args": [],
        }

    return {"kind": "unknown", "step_index": None, "skill": None, "args": []}


def _score_candidate(
    *,
    adapter: Any,
    candidate: str,
    current_skill: str,
    step_args: Dict[str, Any],
    issue_args: Sequence[str],
    issue_kind: str,
) -> Optional[Dict[str, Any]]:
    schema = _get_skill_schema(adapter, candidate)
    if not schema:
        return None
    schema_names = _schema_keys(schema)
    required = _required_params(schema)
    current_arg_names = set(step_args.keys())
    issue_arg_names = set(issue_args)
    supported_current_args = sorted(current_arg_names & schema_names)
    supported_issue_args = sorted(issue_arg_names & schema_names)
    missing_required = sorted(required - current_arg_names)

    name_tokens = _tokens(candidate)
    desc_tokens = _tokens(_get_skill_description(adapter, candidate))
    current_tokens = _tokens(current_skill) | _tokens(" ".join(issue_args)) | _tokens(" ".join(current_arg_names))
    lexical_overlap = len((name_tokens | desc_tokens) & current_tokens)

    score = 0
    score += len(supported_current_args) * 8
    score += len(supported_issue_args) * 25
    score += min(lexical_overlap, 10) * 3
    score -= len(missing_required) * 6

    if issue_kind == "missing_required" and issue_arg_names & required:
        score -= 15
    if candidate in GATEWAY_SKILLS:
        score -= 40
    if candidate == current_skill:
        score -= 100

    if score <= 0:
        return None

    return {
        "skill": candidate,
        "score": score,
        "supports_current_args": supported_current_args,
        "supports_issue_args": supported_issue_args,
        "missing_required_args": missing_required,
        "description": _get_skill_description(adapter, candidate)[:220],
        "schema_args": sorted(schema_names),
    }


def resolve_skill_capability_issue(
    *,
    adapter: Any,
    allowed_skills: List[str],
    plan: Optional[Dict[str, Any]],
    error_message: str,
    include_gateway: bool = True,
) -> Dict[str, Any]:
    issue = parse_plan_gate_issue(error_message)
    steps = plan.get("steps") if isinstance(plan, dict) else None
    step: Dict[str, Any] = {}
    if isinstance(steps, list) and isinstance(issue.get("step_index"), int):
        idx = int(issue["step_index"])
        if 0 <= idx < len(steps) and isinstance(steps[idx], dict):
            step = steps[idx]

    current_skill = str(issue.get("skill") or step.get("skill") or "")
    step_args = step.get("args") if isinstance(step.get("args"), dict) else {}
    current_schema = _get_skill_schema(adapter, current_skill) if current_skill else {}
    current_schema_visible = bool(current_schema)
    issue_args = list(issue.get("args") or [])

    candidates: List[Dict[str, Any]] = []
    for skill in allowed_skills:
        if skill == current_skill or skill in GATEWAY_SKILLS:
            continue
        scored = _score_candidate(
            adapter=adapter,
            candidate=skill,
            current_skill=current_skill,
            step_args=step_args,
            issue_args=issue_args,
            issue_kind=str(issue.get("kind") or ""),
        )
        if scored:
            candidates.append(scored)
    candidates.sort(key=lambda item: (-int(item["score"]), str(item["skill"])))
    candidates = candidates[:6]

    gateway_registered = sorted(skill for skill in allowed_skills if skill in GATEWAY_SKILLS)
    has_gateway_discovery = {"ops_search", "ops_introspect", "ops_invoke"}.issubset(set(allowed_skills))
    has_low_level_bridge = bool({"py_call", "py_set"} & set(allowed_skills))

    issue_kind = str(issue.get("kind") or "")

    if issue_kind == "unknown":
        if "plan_gate_autofix_exhausted" in (error_message or ""):
            classification = "local_autofix_exhausted"
        else:
            classification = "unclassified_plan_gate_issue"
    elif candidates and candidates[0].get("supports_issue_args"):
        classification = "better_registered_skill_found"
    elif candidates:
        classification = "requires_skill_composition_or_repair"
    elif not current_schema_visible:
        classification = "schema_not_visible"
    elif include_gateway and (has_gateway_discovery or has_low_level_bridge):
        classification = "no_high_level_registered_match_gateway_available"
    else:
        classification = "current_skill_schema_violation"

    return {
        "classification": classification,
        "issue": issue,
        "current_step": {
            "step_id": step.get("step_id"),
            "skill": current_skill,
            "args": step_args,
        },
        "current_skill_schema_visible": current_schema_visible,
        "current_skill_schema": current_schema,
        "candidate_registered_skills": candidates,
        "gateway": {
            "registered_skills": gateway_registered,
            "discovery_available": has_gateway_discovery,
            "low_level_bridge_available": has_low_level_bridge,
            "policy": (
                "Use gateway discovery only when no high-level registered skill can satisfy "
                "the intent; first run ops_search, then ops_introspect, then plan ops_invoke "
                "with the introspected signature."
            ),
        },
    }


def format_skill_capability_resolution(resolution: Dict[str, Any]) -> str:
    if not resolution:
        return ""
    compact = {
        "classification": resolution.get("classification"),
        "issue": resolution.get("issue"),
        "current_step": resolution.get("current_step"),
        "current_skill_schema_visible": resolution.get("current_skill_schema_visible"),
        "current_skill_schema_args": sorted(
            _schema_keys(resolution.get("current_skill_schema"))
        ),
        "candidate_registered_skills": [
            {
                "skill": item.get("skill"),
                "supports_issue_args": item.get("supports_issue_args"),
                "supports_current_args": item.get("supports_current_args"),
                "missing_required_args": item.get("missing_required_args"),
                "schema_args": item.get("schema_args"),
                "description": item.get("description"),
            }
            for item in resolution.get("candidate_registered_skills", [])[:4]
        ],
        "gateway": resolution.get("gateway"),
    }
    return (
        "Skill capability resolution (facts from registered skill schemas):\n"
        f"{json.dumps(compact, ensure_ascii=False, indent=2, default=str)}\n"
        "Use these facts to repair the plan. Prefer a listed high-level registered skill "
        "when it better matches the required arguments. If no high-level match exists and "
        "gateway.discovery_available is true, use the registered gateway discovery sequence "
        "instead of inventing a new skill or unsupported parameter."
    )
