"""Feedback subpackage for closed-loop validation and user interaction."""

from .control import ClosedLoopControl, FeedbackDecision
from .geometry_capture import (
    CaptureLevel,
    GeometryDelta,
    IncrementalSceneCapture,
    ObjectGeometry,
    ValidationResult,
)
from .llm import GeometryAnalysis, GeometryFeedbackAnalyzer
from .loop import (
    DEFAULT_CHECKPOINTS,
    FeedbackCheckpoint,
    FeedbackContext,
    FeedbackLoop,
    FeedbackResult,
    NonInteractiveFeedbackLoop,
    UserDecision,
    create_feedback_context,
)
from .rules import BuiltinValidationRules, ValidationRuleRegistry
from .ui import FeedbackUIManager, maybe_request_feedback

__all__ = [
    "ClosedLoopControl",
    "FeedbackDecision",
    "CaptureLevel",
    "GeometryDelta",
    "IncrementalSceneCapture",
    "ObjectGeometry",
    "ValidationResult",
    "GeometryAnalysis",
    "GeometryFeedbackAnalyzer",
    "DEFAULT_CHECKPOINTS",
    "FeedbackCheckpoint",
    "FeedbackContext",
    "FeedbackLoop",
    "FeedbackResult",
    "NonInteractiveFeedbackLoop",
    "UserDecision",
    "create_feedback_context",
    "BuiltinValidationRules",
    "ValidationRuleRegistry",
    "FeedbackUIManager",
    "maybe_request_feedback",
]
