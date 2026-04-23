"""Core domain models and plan/reference utilities."""

from .task_state import TaskState, TaskInterruptedError
from .scene_state import SceneState, FeedbackContext
from .plan_normalization import (
    extract_skills_plan,
    normalize_plan,
    validate_plan_references,
    validate_plan_structure,
)
from .vibe_protocol import merge_step_results_for_prompt, resolve_refs, resolve_refs_in_value

__all__ = [
    "TaskState",
    "TaskInterruptedError",
    "SceneState",
    "FeedbackContext",
    "extract_skills_plan",
    "normalize_plan",
    "validate_plan_references",
    "validate_plan_structure",
    "merge_step_results_for_prompt",
    "resolve_refs",
    "resolve_refs_in_value",
]
