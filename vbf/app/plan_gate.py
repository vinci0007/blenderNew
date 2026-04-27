from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Tuple

from ..core.plan_normalization import validate_plan_structure


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
    if "bool" in hint and isinstance(value, bool):
        return True
    if "int" in hint and isinstance(value, int) and not isinstance(value, bool):
        return True
    if "float" in hint and isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if "str" in hint and isinstance(value, str):
        return True
    if ("list" in hint or "tuple" in hint or "sequence" in hint) and isinstance(value, list):
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


def auto_fix_known_plan_gate_issue(plan: Dict[str, Any], error_message: str) -> bool:
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
    max_attempts = max(6, min(12, len(steps) + 2))
    for _ in range(max_attempts):
        try:
            validate_plan_with_skill_schemas(plan, adapter, allowed_skills)
            return steps
        except ValueError as e:
            if not auto_fix_known_plan_gate_issue(plan, str(e)):
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
