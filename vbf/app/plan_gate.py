from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.plan_normalization import (
    CREATE_PRIMITIVE_TYPE_ALIASES,
    SUPPORTED_CREATE_PRIMITIVE_TYPES,
    validate_plan_structure,
)


def guess_python_type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def matches_expected_type(expected_hint: str, value: Any) -> bool:
    hint = (expected_hint or "any").lower()
    if hint in {"any", "typing.any"}:
        return True
    if isinstance(value, dict) and "$ref" in value:
        # Type resolved at runtime; do not fail preflight.
        return True
    if isinstance(value, str) and value.startswith("$ref:"):
        return True
    if "list" in hint or "tuple" in hint or "sequence" in hint:
        return isinstance(value, list)
    if "bool" in hint and isinstance(value, bool):
        return True
    if "int" in hint and isinstance(value, int) and not isinstance(value, bool):
        return True
    if "float" in hint and isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if "str" in hint and isinstance(value, str):
        return True
    if ("dict" in hint or "mapping" in hint) and isinstance(value, dict):
        return True
    return False


def validate_plan_with_skill_schemas(
    plan: Dict[str, Any],
    adapter: Any,
    allowed_skills: List[str],
) -> None:
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return
    allowed_set = set(allowed_skills)
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        skill = step.get("skill")
        if not isinstance(skill, str) or not skill:
            raise ValueError(f"plan_gate_invalid_skill: step[{idx}] missing valid skill")
        if skill not in allowed_set:
            raise ValueError(f"plan_gate_unknown_skill: step[{idx}] skill={skill!r} not in allowed set")

        args = step.get("args", {})
        if not isinstance(args, dict):
            raise ValueError(f"plan_gate_invalid_args: step[{idx}] args must be object")

        try:
            schema = adapter.get_skill_params(skill)
        except Exception:
            schema = None
        if not isinstance(schema, dict) or not schema:
            continue

        for param_name, param_info in schema.items():
            info = param_info if isinstance(param_info, dict) else {}
            if info.get("required") is True and param_name not in args:
                raise ValueError(
                    f"plan_gate_missing_required: step[{idx}] skill={skill} missing arg={param_name}"
                )

        unknown_args = [name for name in args.keys() if name not in schema]
        if unknown_args:
            raise ValueError(
                f"plan_gate_unknown_args: step[{idx}] skill={skill} unknown={unknown_args[:6]}"
            )

        for arg_name, arg_value in args.items():
            expected = schema.get(arg_name, {})
            expected_type = expected.get("type") if isinstance(expected, dict) else "any"
            if not matches_expected_type(str(expected_type), arg_value):
                raise ValueError(
                    "plan_gate_type_mismatch: "
                    f"step[{idx}] skill={skill} arg={arg_name} "
                    f"expected={expected_type} actual={guess_python_type_name(arg_value)}"
                )

        if skill == "create_primitive":
            primitive_type = args.get("primitive_type")
            primitive_key = (
                primitive_type.strip().lower().replace("-", "_").replace(" ", "_")
                if isinstance(primitive_type, str)
                else ""
            )
            if primitive_key not in SUPPORTED_CREATE_PRIMITIVE_TYPES:
                raise ValueError(
                    "plan_gate_invalid_primitive_type: "
                    f"step[{idx}] skill=create_primitive primitive_type={primitive_type!r} "
                    "supported=['cube','cylinder','cone','sphere']"
                )


def extract_plan_gate_missing_required(
    message: str,
) -> Optional[Tuple[int, str, str]]:
    match = re.search(
        r"plan_gate_missing_required:\s*step\[(\d+)\]\s*skill=([^\s]+)\s*missing arg=([^\s]+)",
        message or "",
    )
    if not match:
        return None
    return int(match.group(1)), match.group(2), match.group(3)


def extract_plan_gate_type_mismatch(
    message: str,
) -> Optional[Tuple[int, str, str, str, str]]:
    match = re.search(
        r"plan_gate_type_mismatch:\s*"
        r"step\[(\d+)\]\s*skill=([^\s]+)\s*arg=([^\s]+)\s*"
        r"expected=(.*?)\s+actual=([^\s]+)",
        message or "",
    )
    if not match:
        return None
    return (
        int(match.group(1)),
        match.group(2),
        match.group(3),
        match.group(4),
        match.group(5),
    )


def extract_plan_gate_invalid_primitive_type(message: str) -> Optional[Tuple[int, str]]:
    match = re.search(
        r"plan_gate_invalid_primitive_type:\s*"
        r"step\[(\d+)\]\s*skill=create_primitive\s*primitive_type=([^\s]+)",
        message or "",
    )
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def _normalize_create_primitive_numeric_size(args: Dict[str, Any]) -> bool:
    size = args.get("size")
    if not isinstance(size, (int, float)) or isinstance(size, bool):
        return False
    value = float(size)
    primitive_type = str(args.get("primitive_type") or "cube").strip().lower()
    primitive_key = CREATE_PRIMITIVE_TYPE_ALIASES.get(primitive_type, primitive_type)
    if primitive_key == "cube":
        args["size"] = [value, value, value]
    else:
        args["size"] = [value]
    print(
        "[VBF] plan_gate_autofix "
        "action=normalize_numeric_size skill=create_primitive "
        f"primitive_type={primitive_key} value={value:g}"
    )
    return True


def _tokenize_object_name(value: str) -> Set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value or ""))
    tokens = re.split(r"[^A-Za-z0-9]+", spaced.lower())
    stop = {"geo", "mat", "obj", "mesh", "object", "hypercar", "car", "the"}
    return {token for token in tokens if token and token not in stop}


def _object_table_names(prior_objects: List[Dict[str, Any]]) -> Set[str]:
    names: Set[str] = set()
    for item in prior_objects:
        if not isinstance(item, dict):
            continue
        for key in ("object_name", "actual_name", "planned_name", "name"):
            value = item.get(key)
            if isinstance(value, str) and value:
                names.add(value)
    return names


def _find_unique_semantic_object_match(
    requested_name: str,
    prior_objects: List[Dict[str, Any]],
) -> Optional[str]:
    requested_tokens = _tokenize_object_name(requested_name)
    if len(requested_tokens) < 2:
        return None

    scored: List[Tuple[float, str]] = []
    for item in prior_objects:
        if not isinstance(item, dict):
            continue
        actual = item.get("object_name") or item.get("actual_name") or item.get("name")
        planned = item.get("planned_name")
        if not isinstance(actual, str) or not actual:
            continue
        candidate_tokens = _tokenize_object_name(" ".join(
            part for part in (actual, planned if isinstance(planned, str) else "") if part
        ))
        if not candidate_tokens:
            continue
        overlap = requested_tokens & candidate_tokens
        if len(overlap) < 2:
            continue
        coverage = len(overlap) / max(1, len(requested_tokens))
        if requested_tokens.issubset(candidate_tokens):
            coverage += 0.25
        scored.append((coverage, actual))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score = scored[0][0]
    best = [actual for score, actual in scored if abs(score - best_score) < 0.0001]
    if best_score < 0.66 or len(set(best)) != 1:
        return None
    return best[0]


def build_prior_object_table(completed_summary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    table: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for summary in completed_summary:
        if not isinstance(summary, dict):
            continue
        created = summary.get("created_objects")
        if not isinstance(created, list):
            continue
        for item in created:
            if not isinstance(item, dict):
                continue
            actual = item.get("object_name") or item.get("actual_name") or item.get("name")
            if not isinstance(actual, str) or not actual or actual in seen:
                continue
            seen.add(actual)
            table.append(
                {
                    "step_id": item.get("step_id"),
                    "skill": item.get("skill"),
                    "planned_name": item.get("planned_name"),
                    "object_name": actual,
                }
            )
    return table


def validate_and_repair_parent_refs(
    plan: Dict[str, Any],
    prior_objects: List[Dict[str, Any]],
) -> int:
    """Validate set_parent parent strings against current/prior objects.

    Cross-batch plans cannot $ref prior batch steps during standalone validation,
    so parent strings must be real object names from prior batch object tables.
    """
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return 0

    valid_names = _object_table_names(prior_objects)
    repairs = 0
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        args = step.get("args")
        if not isinstance(args, dict):
            args = {}
        skill = step.get("skill")
        if skill != "set_parent":
            for key in ("name", "object_name"):
                value = args.get(key)
                if isinstance(value, str) and value:
                    valid_names.add(value)
            continue

        parent_name = args.get("parent_name")
        if isinstance(parent_name, dict) and "$ref" in parent_name:
            continue
        if not isinstance(parent_name, str) or not parent_name:
            continue
        if parent_name in valid_names:
            continue
        replacement = _find_unique_semantic_object_match(parent_name, prior_objects)
        if replacement:
            args["parent_name"] = replacement
            repairs += 1
            print(
                "[VBF] plan_gate_autofix "
                "action=repair_parent_name "
                f"old={parent_name} new={replacement}"
            )
            continue
        raise ValueError(
            "plan_gate_unknown_parent_object: "
            f"step[{idx}] skill=set_parent parent_name={parent_name!r} "
            "not in current batch objects or prior object table"
        )
    return repairs


TRANSFORM_ARG_ALIASES = {
    "rotation": "rotation_euler",
    "rotation_euler": "rotation_euler",
    "scale": "scale",
    "location": "location",
    "position": "location",
}


SCHEMA_ARG_ALIASES = {
    "primitive_type": ("type", "primitive"),
    "name": ("object_name", "obj_name"),
    "object_name": ("name", "target", "target_name"),
    "target_name": ("object_name", "target_object", "target"),
    "tool_name": ("cutter_name", "boolean_object", "tool_object"),
    "size": ("dimensions",),
    "location": ("position", "pos"),
    "rotation_euler": ("rotation",),
    "enable": ("enabled",),
    "focal_length": ("lens",),
    "modifier_name": ("modifier",),
}


def _get_skill_schema(adapter: Any, skill: str) -> Dict[str, Any]:
    try:
        schema = adapter.get_skill_params(skill)
    except Exception:
        schema = None
    return schema if isinstance(schema, dict) else {}


def _next_inserted_step_id(steps: List[Dict[str, Any]], source_step: Dict[str, Any]) -> str:
    existing = {str(step.get("step_id")) for step in steps if isinstance(step, dict)}
    base = str(source_step.get("step_id") or "autofix").strip() or "autofix"
    for suffix in ("transform", *[f"transform_{idx}" for idx in range(2, 100)]):
        candidate = f"{base}_{suffix}"
        if candidate not in existing:
            return candidate
    return f"{base}_transform_autofix"


def _find_object_target_arg(schema: Dict[str, Any]) -> Optional[str]:
    for name in ("object_name", "target_name", "name"):
        if name in schema:
            return name
    return None


def _alias_args_to_schema(
    *,
    step: Dict[str, Any],
    adapter: Any,
    only_targets: Optional[List[str]] = None,
    only_sources: Optional[List[str]] = None,
) -> bool:
    skill = step.get("skill")
    args = step.get("args")
    if not isinstance(skill, str) or not isinstance(args, dict):
        return False

    schema = _get_skill_schema(adapter, skill)
    if not schema:
        return False

    target_filter = set(only_targets or schema.keys())
    source_filter = set(only_sources or args.keys())
    for target, aliases in SCHEMA_ARG_ALIASES.items():
        if target not in schema or target in args or target not in target_filter:
            continue
        for alias in aliases:
            if alias not in args or alias not in source_filter:
                continue
            expected = schema.get(target, {})
            expected_type = expected.get("type") if isinstance(expected, dict) else "any"
            value = args[alias]
            if not matches_expected_type(str(expected_type), value):
                continue
            args[target] = args.pop(alias)
            print(
                "[VBF] plan_gate_autofix "
                f"action=schema_alias_arg skill={skill} old={alias} new={target}"
            )
            return True
    return False


def _object_ref_for_step(step: Dict[str, Any]) -> Any:
    step_id = step.get("step_id")
    if isinstance(step_id, str) and step_id.strip():
        normalized = step_id if step_id.startswith("step_") else f"step_{step_id}"
        return {"$ref": f"{normalized}.data.object_name"}
    args = step.get("args") if isinstance(step.get("args"), dict) else {}
    for name in ("name", "object_name"):
        value = args.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def _split_transform_args_to_apply_transform(
    *,
    plan: Dict[str, Any],
    adapter: Any,
    allowed_skills: List[str],
    step_index: int,
    unknown_args: List[str],
) -> bool:
    if "apply_transform" not in set(allowed_skills):
        return False
    apply_schema = _get_skill_schema(adapter, "apply_transform")
    if not apply_schema:
        return False
    target_arg = _find_object_target_arg(apply_schema)
    if not target_arg:
        return False

    steps = plan.get("steps")
    if not isinstance(steps, list) or not (0 <= step_index < len(steps)):
        return False
    step = steps[step_index]
    if not isinstance(step, dict):
        return False
    args = step.get("args")
    if not isinstance(args, dict):
        return False

    transform_args: Dict[str, Any] = {}
    consumed: List[str] = []
    for arg_name in unknown_args:
        if not isinstance(arg_name, str) or arg_name not in args:
            continue
        canonical = TRANSFORM_ARG_ALIASES.get(arg_name)
        if not canonical or canonical not in apply_schema:
            continue
        if canonical in transform_args:
            continue
        transform_args[canonical] = args[arg_name]
        consumed.append(arg_name)

    if not transform_args:
        return False

    object_ref = _object_ref_for_step(step)
    if object_ref is None:
        return False

    for arg_name in consumed:
        args.pop(arg_name, None)

    transform_step = {
        "step_id": _next_inserted_step_id(steps, step),
        "stage": step.get("stage"),
        "skill": "apply_transform",
        "args": {
            target_arg: object_ref,
            **transform_args,
        },
    }
    if transform_step["stage"] is None:
        transform_step.pop("stage")

    steps.insert(step_index + 1, transform_step)
    print(
        "[VBF] plan_gate_autofix "
        "action=split_transform "
        f"source_step_index={step_index} inserted_skill=apply_transform "
        f"moved={consumed}"
    )
    return True


def auto_fix_known_plan_gate_issue(
    plan: Dict[str, Any],
    error_message: str,
    adapter: Any = None,
    allowed_skills: Optional[List[str]] = None,
) -> bool:
    """Best-effort local auto-fix for known plan-gate failures."""
    parsed = extract_plan_gate_missing_required(error_message)
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return False
    alias_rules = {
        ("set_cycles_denoise", "enabled"): "enable",
        ("set_camera_properties", "lens"): "focal_length",
        ("create_light", "rotation"): "rotation_euler",
        ("create_beveled_box", "object_name"): "name",
    }

    if parsed:
        idx, skill, missing_arg = parsed
        if not (0 <= idx < len(steps)):
            return False
        step = steps[idx]

        if adapter is not None and _alias_args_to_schema(
            step=step,
            adapter=adapter,
            only_targets=[missing_arg],
        ):
            return True

        # Common LLM failure on hard-surface prompts: emits mark_edge_crease
        # without edges payload. This step is optional polish, so safely prune.
        if skill == "mark_edge_crease" and missing_arg == "edges":
            removed = steps.pop(idx)
            step_id = removed.get("step_id", f"step[{idx}]")
            print(
                "[VBF] plan_gate_autofix "
                f"action=drop_step reason=missing_edges skill=mark_edge_crease step_id={step_id}"
            )
            return True

        # Common LLM omission on minimal prompts.
        if skill == "create_primitive" and missing_arg == "primitive_type":
            step = steps[idx]
            args = step.get("args")
            if isinstance(args, dict):
                args["primitive_type"] = "cube"
                print(
                    "[VBF] plan_gate_autofix "
                    "action=fill_default skill=create_primitive arg=primitive_type value=cube"
                )
                return True

        if skill == "create_material_simple" and missing_arg == "base_color":
            step = steps[idx]
            args = step.get("args")
            if isinstance(args, dict):
                args["base_color"] = [0.55, 0.48, 0.40]
                print(
                    "[VBF] plan_gate_autofix "
                    "action=fill_default skill=create_material_simple "
                    "arg=base_color value=[0.55,0.48,0.40]"
                )
                return True

        if skill == "create_beveled_box":
            step = steps[idx]
            args = step.get("args")
            if not isinstance(args, dict):
                return False

            if missing_arg == "name" and "object_name" in args:
                args["name"] = args.pop("object_name")
                print(
                    "[VBF] plan_gate_autofix "
                    "action=alias_arg skill=create_beveled_box old=object_name new=name"
                )
                return True

            if missing_arg == "size":
                if isinstance(args.get("dimensions"), list):
                    args["size"] = args.pop("dimensions")
                    print(
                        "[VBF] plan_gate_autofix "
                        "action=alias_arg skill=create_beveled_box old=dimensions new=size"
                    )
                    return True
                if all(name in args for name in ("width", "height", "depth")):
                    args["size"] = [args.pop("width"), args.pop("height"), args.pop("depth")]
                    print(
                        "[VBF] plan_gate_autofix "
                        "action=compose_size skill=create_beveled_box source=[width,height,depth]"
                    )
                    return True

            if missing_arg == "location" and "position" in args:
                args["location"] = args.pop("position")
                print(
                    "[VBF] plan_gate_autofix "
                    "action=alias_arg skill=create_beveled_box old=position new=location"
                )
                return True

    type_mismatch = extract_plan_gate_type_mismatch(error_message or "")
    if type_mismatch:
        idx, skill, arg_name, _expected, actual = type_mismatch
        if not (0 <= idx < len(steps)):
            return False
        step = steps[idx]
        args = step.get("args")
        if not isinstance(args, dict):
            return False
        if (
            skill == "create_primitive"
            and arg_name == "size"
            and actual in {"int", "float"}
            and _normalize_create_primitive_numeric_size(args)
        ):
            return True

    invalid_primitive = extract_plan_gate_invalid_primitive_type(error_message or "")
    if invalid_primitive:
        idx, raw_primitive = invalid_primitive
        if not (0 <= idx < len(steps)):
            return False
        step = steps[idx]
        args = step.get("args")
        if not isinstance(args, dict):
            return False
        normalized = raw_primitive.strip("'\"").strip().lower().replace("-", "_").replace(" ", "_")
        replacement = CREATE_PRIMITIVE_TYPE_ALIASES.get(normalized)
        if replacement in SUPPORTED_CREATE_PRIMITIVE_TYPES:
            args["primitive_type"] = replacement
            print(
                "[VBF] plan_gate_autofix "
                "action=replace_unsupported_primitive "
                f"old={raw_primitive} new={replacement}"
            )
            return True

    unknown_match = re.search(
        r"plan_gate_unknown_args:\s*step\[(\d+)\]\s*skill=([^\s]+)\s*unknown=(\[[^\]]*\])",
        error_message or "",
    )
    if unknown_match:
        idx = int(unknown_match.group(1))
        if not (0 <= idx < len(steps)):
            return False
        step = steps[idx]
        args = step.get("args")
        if not isinstance(args, dict):
            return False
        unknown_payload = unknown_match.group(3)
        try:
            unknown_args = ast.literal_eval(unknown_payload)
        except Exception:
            unknown_args = []
        if not isinstance(unknown_args, list):
            return False
        if adapter is not None and allowed_skills is not None:
            if _alias_args_to_schema(
                step=step,
                adapter=adapter,
                only_sources=[name for name in unknown_args if isinstance(name, str)],
            ):
                return True
            if _split_transform_args_to_apply_transform(
                plan=plan,
                adapter=adapter,
                allowed_skills=allowed_skills,
                step_index=idx,
                unknown_args=unknown_args,
            ):
                return True
        removed = [name for name in unknown_args if isinstance(name, str) and name in args]
        aliased = []
        dropped = []
        for name in removed:
            alias_target = alias_rules.get((step.get("skill"), name))
            if alias_target and alias_target not in args:
                args[alias_target] = args.pop(name)
                aliased.append(f"{name}->{alias_target}")
            else:
                args.pop(name, None)
                dropped.append(name)
        if aliased or dropped:
            details = []
            if aliased:
                details.append(f"aliased={aliased}")
            if dropped:
                details.append(f"removed={dropped}")
            print(
                "[VBF] plan_gate_autofix "
                f"action=drop_unknown_args step_index={idx} {' '.join(details)}"
            )
            return True

    return False


def validate_plan_with_schema_autofix(
    plan: Dict[str, Any],
    adapter: Any,
    allowed_skills: List[str],
) -> List[Dict[str, Any]]:
    """Validate plan against skill schemas, with targeted auto-fix retries."""
    steps = validate_plan_structure(plan)
    max_attempts = max(12, min(50, len(steps) * 4 + 4))
    for _ in range(max_attempts):
        try:
            validate_plan_with_skill_schemas(plan, adapter, allowed_skills)
            return steps
        except ValueError as e:
            if not auto_fix_known_plan_gate_issue(plan, str(e), adapter, allowed_skills):
                raise
            steps = validate_plan_structure(plan)
    raise ValueError("plan_gate_autofix_exhausted")


def is_recoverable_plan_error(message: str) -> bool:
    msg = (message or "").lower()
    tokens = [
        "no executable steps",
        "invalid_ref_schema",
        "unknown_ref_step",
        "forward_ref_step",
        "plan must be a dict with 'steps' field",
        "plan missing 'steps' field",
        "plan 'steps' must be a list",
        "plan_gate_",
        "llm parse error",
    ]
    return any(token in msg for token in tokens)


def build_plan_repair_prompt(
    prompt: str,
    error_message: str,
    modeling_quality_contract: str,
) -> str:
    return (
        f"{prompt}\n\n"
        "IMPORTANT:\n"
        "- Return ONLY executable Blender skills in steps[].\n"
        "- Do NOT use load_skill as a step skill.\n"
        "- Every step must have a valid skill name and args object.\n"
        "- Use ONLY skills from Available Skills in system prompt.\n"
        "- Use ONLY $ref paths in this format: step_<id>.data.<field> or <id>.data.<field>.\n"
        "- Never use scene.objects[...] as a $ref target.\n"
        "- If an object is referenced, it must be created in an earlier step.\n"
        f"{modeling_quality_contract}\n"
        f"- Previous validation error to fix: {error_message}\n"
    )
