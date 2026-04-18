"""Plan normalization utilities for LLM-generated plans.

This module handles the normalization of LLM-generated plan structures
to match the expected VBF plan schema, including:
- Field name normalization (params/parameters -> args)
- Parameter alias resolution (type -> primitive_type)
- on_success structure completion
"""

from typing import Any, Dict, List, Set


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


def extract_skills_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the skills_plan from LLM response if wrapped.

    Some LLMs return {"skills_plan": {...}} instead of a direct plan.

    Args:
        plan: The raw LLM response

    Returns:
        The extracted plan or original plan if not wrapped
    """
    if isinstance(plan, dict) and "skills_plan" in plan:
        return plan["skills_plan"]
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

    return steps
