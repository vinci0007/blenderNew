"""LLM integration utilities for VBF.

This module handles LLM configuration, message building, and plan generation,
separated from the main client logic.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from .llm_openai_compat import OpenAICompatLLM, OpenAICompatConfig, load_openai_compat_config
from .vibe_protocol import merge_step_results_for_prompt
from .plan_normalization import normalize_plan, validate_plan_structure


def load_llm() -> Optional[OpenAICompatLLM]:
    """Load LLM instance from config.

    Returns:
        OpenAICompatLLM instance or None if not configured/disabled
    """
    cfg = load_openai_compat_config()
    if not cfg:
        return None
    # Explicit opt-out: use_llm=false in config disables LLM entirely
    if not cfg.use_llm:
        return None
    return OpenAICompatLLM(cfg)


def load_llm_config() -> Optional[OpenAICompatConfig]:
    """Return the raw OpenAICompatConfig (or None if not configured)."""
    return load_openai_compat_config()


def is_llm_enabled() -> bool:
    """Check if LLM is configured AND use_llm is not disabled."""
    cfg = load_openai_compat_config()
    if not cfg:
        return False
    return bool(cfg.use_llm)


async def call_llm_json(
    llm: OpenAICompatLLM,
    messages: List[Dict[str, str]],
    use_throttle: bool = True,
    use_cache: bool = True
) -> Dict[str, Any]:
    """Call LLM with caching and optional throttling.

    Args:
        llm: The LLM instance
        messages: Chat messages for the LLM
        use_throttle: Whether to apply rate limiting (default: True)
        use_cache: Whether to use response caching (default: True)

    Returns:
        Parsed JSON response as dict
    """
    from .llm_cache import get_cache
    from .llm_rate_limiter import call_llm_with_throttle

    cache = get_cache() if use_cache else None

    # Try cache first
    if cache:
        cached = cache.get(messages)
        if cached is not None:
            return cached

    # Miss: call LLM (with optional throttling)
    async def _call_impl():
        return await asyncio.to_thread(llm.chat_json, messages)

    if use_throttle:
        response = await call_llm_with_throttle(_call_impl)
    else:
        response = await _call_impl()

    # Cache the response
    if cache:
        cache.set(messages, response)

    return response


def _json_dumps(obj: Any) -> str:
    """Helper for JSON serialization."""
    return json.dumps(obj, ensure_ascii=False)


def build_skill_plan_messages(
    prompt: str,
    allowed_skills: List[str],
    skill_schemas: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Build messages for skill-based task planning.

    Args:
        prompt: User's modeling prompt
        allowed_skills: List of allowed skill names
        skill_schemas: Optional dict of skill parameter schemas

    Returns:
        List of chat messages for the LLM
    """
    # Generic plan schema for user-controlled modeling
    schema = {
        "vbf_version": "string",
        "plan_id": "string",
        "execution": {"max_retries_per_step": "number"},
        "controls": {
            "max_steps": "number",
            "allow_low_level_gateway": "boolean",
            "require_ops_introspect_before_invoke": "boolean",
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
                        "step_return_json_path": "string",
                    }
                },
            }
        ],
    }

    # Group skills by category for better LLM organization
    skills_by_category = None
    try:
        # Import here to avoid circular dependency
        from blender_provider.vbf_addon.skills_impl.registry import SKILL_CATEGORIES

        skills_by_category = {}
        for category_name, skill_names in SKILL_CATEGORIES.items():
            skills_in_category = []
            for skill_name in skill_names:
                if skill_name in allowed_skills:
                    if skill_schemas and skill_name in skill_schemas:
                        skills_in_category.append({"name": skill_name, **skill_schemas[skill_name]})
                    else:
                        skills_in_category.append({"name": skill_name})
            if skills_in_category:
                skills_by_category[category_name] = skills_in_category
    except Exception:
        # Fallback to flat list if categories not available
        skills_by_category = None

    # Always include flat allowed_skills list for LLM reference
    user = {
        "prompt": prompt,
        "task_type": "user_modeling_task",
        "allowed_skills": allowed_skills,
        "allowed_skills_by_category": skills_by_category,
        "must_return_only_json": True,
        "instructions": [
            "Decompose the user request into atomic Blender skills steps.",
            "ONLY use skills from allowed_skills; never invent skills.",
            "Never output any bpy/bmesh code. ONLY output the skills_plan JSON.",
            'Use $ref to reference prior step outputs: {"$ref":"<step_id>.data.<key>"}.',
            'If you use on_success.store_as, then later you may reference by alias name as: {"$ref":"<alias_name>.data.<key>"}.',
            'If the stored value is not an object/dict, reference it as {"$ref":"<alias_name>.data.value"}.',
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
        {"role": "user", "content": _json_dumps(user)},
    ]


def build_skill_repair_messages(
    prompt: str,
    failed_step_id: str,
    error_message: str,
    error_traceback: str,
    original_plan: Dict[str, Any],
    step_results: Dict[str, Dict[str, Any]],
    allowed_skills: List[str],
    skill_schemas: Optional[Dict[str, Any]] = None,
    low_level_gateway_hint: bool = False,
) -> List[Dict[str, str]]:
    """Build messages for skill-based plan repair.

    Args:
        prompt: Original user prompt
        failed_step_id: ID of the failed step
        error_message: Error message from the failure
        error_traceback: Full error traceback
        original_plan: The original plan that failed
        step_results: Results from executed steps
        allowed_skills: List of allowed skill names
        skill_schemas: Optional dict of skill parameter schemas
        low_level_gateway_hint: Whether to add gateway usage hint

    Returns:
        List of chat messages for the LLM
    """
    schema = {
        "vbf_version": "string",
        "plan_id": "string",
        "repair": {"replace_from_step_id": "string"},
        "execution": {"max_retries_per_step": "number"},
        "steps": [{"step_id": "string", "skill": "string", "args": {"any": "json-serializable"}}],
    }

    compact_steps = merge_step_results_for_prompt(step_results)

    user = {
        "prompt": prompt,
        "task_type": "user_modeling_task",
        "failed_step_id": failed_step_id,
        "error_message": error_message,
        "error_traceback": error_traceback,
        "allowed_skills": [
            (
                {"name": name, **skill_schemas[name]}
                if skill_schemas is not None and name in skill_schemas
                else {"name": name}
            )
            for name in allowed_skills
        ]
        if skill_schemas is not None
        else allowed_skills,
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

    if low_level_gateway_hint:
        user["instructions"].append(
            "py_call and py_set are now available as low-level gateway skills; "
            "use them only if high-level skills cannot fulfill the requirement"
        )

    system_msg = (
        "You are the Vibe Protocol auto-repair planner. "
        "You MUST return JSON only that matches the provided repair_plan_schema exactly."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": _json_dumps(user)},
    ]


async def generate_skill_plan(
    prompt: str,
    allowed_skills: List[str],
    describe_skills_func,
    llm: Optional[OpenAICompatLLM] = None,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Generate a skill plan using LLM.

    Args:
        prompt: User's modeling prompt
        allowed_skills: List of allowed skill names
        describe_skills_func: Async function to get skill schemas
        llm: Optional LLM instance (will load if not provided)

    Returns:
        Tuple of (plan dict, steps list)

    Raises:
        ValueError: If LLM is not configured or plan is invalid
    """
    if llm is None:
        llm = load_llm()

    if llm is None:
        raise ValueError(
            "LLM is not configured. Please set VBF_LLM_API_KEY and VBF_LLM_BASE_URL "
            "or configure vbf/config/llm.json"
        )

    skill_schemas = await describe_skills_func(allowed_skills)
    messages = build_skill_plan_messages(prompt, allowed_skills, skill_schemas=skill_schemas)
    raw_plan = await call_llm_json(llm, messages)

    # Normalize the plan
    try:
        normalized_plan = normalize_plan(raw_plan)
        steps = validate_plan_structure(normalized_plan)
        return normalized_plan, steps
    except ValueError as e:
        raise ValueError(f"LLM generated invalid plan: {e}") from e
