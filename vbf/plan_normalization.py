"""Plan normalization utilities for LLM-generated plans.

This module handles the normalization of LLM-generated plan structures
to match the expected VBF plan schema, including:
- Field name normalization (params/parameters -> args)
- Parameter alias resolution (type -> primitive_type)
- on_success structure completion
"""

import re
from typing import Any, Dict, Iterable, List, Set, Tuple


# Parameter alias mapping for common LLM naming conventions
PARAMETER_ALIASES: Dict[str, Dict[str, str]] = {
    "create_primitive": {
        "type": "primitive_type",  # LLM commonly uses 'type', actual is 'primitive_type'
        "rotation": "rotation_euler",  # Blender primitive helper expects rotation_euler
    },
}

# Skills/tools that are for planning-time documentation query, not Blender execution.
NON_EXECUTION_SKILLS: Set[str] = {
    "load_skill",
}


def _normalize_step_id(step_id: str) -> str:
    if step_id.startswith("step_"):
        return step_id[len("step_") :]
    return step_id


def _extract_ref_token(value: Any) -> str | None:
    if isinstance(value, dict) and set(value.keys()) == {"$ref"}:
        ref = value.get("$ref")
        return ref if isinstance(ref, str) and ref.strip() else None
    if isinstance(value, str) and value.startswith("$ref:"):
        ref = value[len("$ref:") :].strip()
        return ref if ref else None
    return None


def _iter_refs(value: Any, path: str = "args") -> Iterable[Tuple[str, str]]:
    ref = _extract_ref_token(value)
    if ref is not None:
        yield path, ref
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _iter_refs(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, nested in enumerate(value):
            yield from _iter_refs(nested, f"{path}[{idx}]")


def validate_plan_references(plan: Dict[str, Any]) -> None:
    """Validate that all $ref tokens use executable, backward-only step refs."""
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return

    all_step_ids: Set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            continue
        sid = step.get("step_id")
        if isinstance(sid, str) and sid:
            all_step_ids.add(_normalize_step_id(sid))

    seen_step_ids: Set[str] = set()
    ref_pattern = re.compile(r"^(?:step_)?([A-Za-z0-9_-]+)\.(?:data|result)\.[^.\s].*$")

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        sid = step.get("step_id")
        sid_normalized = _normalize_step_id(sid) if isinstance(sid, str) and sid else None

        args = step.get("args")
        if not isinstance(args, (dict, list)):
            if sid_normalized:
                seen_step_ids.add(sid_normalized)
            continue

        for ref_path, ref in _iter_refs(args):
            if ref.startswith("scene.") or "scene.objects[" in ref:
                raise ValueError(
                    f"invalid_ref_schema: step[{idx}] {ref_path}={ref!r}; "
                    "only step_<id>.data.* or <id>.data.* refs are allowed"
                )

            match = ref_pattern.match(ref)
            if not match:
                raise ValueError(
                    f"invalid_ref_schema: step[{idx}] {ref_path}={ref!r}; "
                    "expected step_<id>.data.<field> or <id>.data.<field>"
                )

            ref_step_id = _normalize_step_id(match.group(1))
            if ref_step_id not in all_step_ids:
                raise ValueError(
                    f"unknown_ref_step: step[{idx}] {ref_path} references {ref_step_id!r}"
                )
            if ref_step_id not in seen_step_ids:
                raise ValueError(
                    f"forward_ref_step: step[{idx}] {ref_path} references future step {ref_step_id!r}"
                )

        if sid_normalized:
            seen_step_ids.add(sid_normalized)


def _looks_like_step_dict(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if isinstance(item.get("skill"), str) and item.get("skill"):
        return True
    if isinstance(item.get("step_id"), str) and item.get("step_id"):
        return True
    for key in ("args", "params", "parameters", "on_success", "stage"):
        if key in item:
            return True
    return False


def _looks_like_steps_list(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return all(isinstance(item, dict) for item in value) and any(
        _looks_like_step_dict(item) for item in value
    )


def _find_plan_container(value: Any, depth: int = 0) -> Dict[str, Any] | None:
    """Find a dict containing `steps` from common or arbitrary wrapper layouts."""
    if depth > 8:
        return None
    if isinstance(value, dict):
        steps = value.get("steps")
        if isinstance(steps, list):
            # Accept empty list (later normalized as no executable steps) or
            # list with step-like structures.
            if not steps or _looks_like_steps_list(steps):
                return value

        # Common provider/model wrappers first.
        for key in ("skills_plan", "plan", "output", "result", "data", "response"):
            nested = value.get(key)
            found = _find_plan_container(nested, depth + 1)
            if found is not None:
                return found

        # Generic recursive scan over all nested values as a fallback.
        for nested in value.values():
            found = _find_plan_container(nested, depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        # Some models may directly return step list.
        if _looks_like_steps_list(value):
            return {"steps": value}

        # Some models may wrap the plan object in arrays.
        for nested in value:
            found = _find_plan_container(nested, depth + 1)
            if found is not None:
                return found
    return None


def extract_skills_plan(plan: Any) -> Any:
    """Extract executable plan from raw LLM response wrappers when possible."""
    found = _find_plan_container(plan)
    if found is not None:
        return found
    return plan


def normalize_step_field_names(step: Dict[str, Any]) -> None:
    """Normalize field names in a step (in-place).

    Converts 'parameters' or 'params' to 'args'.

    Args:
        step: The step dict to normalize (modified in-place)
    """
    if "parameters" in step and "args" not in step:
        step["args"] = step.pop("parameters")
    elif "params" in step and "args" not in step:
        step["args"] = step.pop("params")


def apply_parameter_aliases(skill_name: str, args: Dict[str, Any]) -> None:
    """Apply parameter aliases for a specific skill (in-place).

    Args:
        skill_name: The skill name to look up aliases for
        args: The args dict to normalize (modified in-place)
    """
    if skill_name in PARAMETER_ALIASES:
        aliases = PARAMETER_ALIASES[skill_name]
        for alias, canonical in aliases.items():
            if alias in args:
                alias_value = args.pop(alias)
                # Prefer canonical key when both are present; still remove alias to
                # avoid passing unsupported kwargs to Blender skill functions.
                if canonical not in args:
                    args[canonical] = alias_value


def ensure_on_success_structure(on_success: Dict[str, Any]) -> None:
    """Ensure on_success has required fields (in-place).

    If on_success has store_as but missing step_return_json_path,
    adds a default based on store_type.

    Args:
        on_success: The on_success dict to complete (modified in-place)
    """
    if "store_as" in on_success and "step_return_json_path" not in on_success:
        store_type = on_success.get("store_type", "object")
        # For object creation skills, default return path is data.object_name
        if store_type == "object":
            on_success["step_return_json_path"] = "data.object_name"
        # Future: other store_type mappings can be added here


def normalize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a complete LLM plan.

    Performs all normalization steps:
    1. Extract skills_plan if wrapped
    2. Normalize field names in each step
    3. Apply parameter aliases
    4. Complete on_success structures

    Args:
        plan: The raw LLM plan

    Returns:
        The normalized plan
    """
    # 1. Extract from wrapper
    plan = extract_skills_plan(plan)

    # 2. Validate basic structure
    if not isinstance(plan, dict) or "steps" not in plan:
        raise ValueError("Plan must be a dict with 'steps' field")

    steps = plan["steps"]
    if not isinstance(steps, list):
        raise ValueError("Plan 'steps' must be a list")

    # 3. Normalize each step
    normalized_steps: List[Dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue

        # Normalize field names
        normalize_step_field_names(step)

        # Apply parameter aliases
        skill_name = step.get("skill")
        if skill_name and "args" in step:
            apply_parameter_aliases(skill_name, step["args"])

        # Complete on_success structure
        on_success = step.get("on_success")
        if isinstance(on_success, dict):
            ensure_on_success_structure(on_success)

        # Drop planning-time pseudo tools that cannot be executed as Blender skills.
        skill_name = step.get("skill")
        if isinstance(skill_name, str) and skill_name in NON_EXECUTION_SKILLS:
            continue

        normalized_steps.append(step)

    plan["steps"] = normalized_steps
    if not normalized_steps:
        raise ValueError("Plan has no executable steps after normalization")
    validate_plan_references(plan)

    return plan


def validate_plan_structure(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate plan structure and return steps.

    Args:
        plan: The plan to validate

    Returns:
        The steps list from the plan

    Raises:
        ValueError: If plan structure is invalid
    """
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a dict")

    if "steps" not in plan:
        raise ValueError("Plan missing 'steps' field")

    steps = plan["steps"]
    if not isinstance(steps, list):
        raise ValueError("Plan 'steps' must be a list")

    # Validate each step is a dict
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"Plan step[{idx}] must be an object/dict")

    validate_plan_references(plan)

    return steps
