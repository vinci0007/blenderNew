"""UI feedback integration for VBF."""

from typing import Any, Dict, List, Optional, Callable

from .loop import (
    FeedbackLoop,
    FeedbackContext,
    FeedbackResult,
    UserDecision,
    create_feedback_context,
)
from ..core.scene_state import SceneState


class FeedbackUIManager:
    """Manages UI feedback during modeling execution."""

    def __init__(self, enable_interactive: bool = True):
        self._feedback_loop = FeedbackLoop() if enable_interactive else None
        self._scene_state: Optional[SceneState] = None
        self._last_feedback: Optional[FeedbackResult] = None

    async def check_and_trigger(
        self,
        stage: str,
        progress_percent: int,
        step_id: Optional[str],
        execute_skill_fn: Callable,
    ) -> Optional[FeedbackResult]:
        if not self._feedback_loop:
            return None
        if not self._feedback_loop.should_trigger(stage, progress_percent):
            return None

        context = self._create_context(stage, progress_percent, step_id)
        result = await self._feedback_loop.request_feedback(
            context,
            preview_callback=lambda: self._generate_scene_preview(execute_skill_fn),
        )
        self._last_feedback = result
        return result

    def _create_context(self, stage: str, progress: int, step_id: Optional[str]) -> FeedbackContext:
        return create_feedback_context(stage, progress, step_id)

    def _generate_scene_preview(self, execute_skill_fn: Callable) -> Optional[str]:
        try:
            # Placeholder for richer preview integration.
            _ = execute_skill_fn
            return "Scene preview generated (objects/camera/material summary)."
        except Exception as e:
            return f"Failed to generate preview: {e}"

    def handle_decision(self, result: FeedbackResult) -> Dict[str, Any]:
        actions = {
            UserDecision.CONTINUE: {"action": "continue", "message": "Continue execution"},
            UserDecision.ADJUST: {
                "action": "adjust",
                "message": f"Adjust parameters: {result.feedback_text}",
            },
            UserDecision.REDO: {"action": "redo", "message": "Redo current stage"},
            UserDecision.STOP: {"action": "stop", "message": "Stop workflow and save state"},
        }
        return actions.get(result.decision, actions[UserDecision.CONTINUE])

    def get_summary(self) -> Dict[str, Any]:
        if not self._feedback_loop:
            return {"enabled": False}
        return self._feedback_loop.get_feedback_summary()

    def reset(self) -> None:
        if self._feedback_loop:
            self._feedback_loop.reset()


FEEDBACK_TRIGGERS: Dict[str, int] = {
    "silhouette_validation": 20,
    "proportion_check": 35,
    "bevel_chamfer": 60,
    "high_poly_finalize": 85,
}


def should_trigger_feedback(stage: str, progress: int) -> bool:
    trigger_progress = FEEDBACK_TRIGGERS.get(stage)
    if trigger_progress is None:
        return False
    return abs(trigger_progress - progress) <= 5


async def maybe_request_feedback(
    stage: str,
    step_id: str,
    progress_overall: int,
    feedback_manager: Optional[FeedbackUIManager],
    prompt: str,
    execute_skill_fn: Callable,
) -> Optional[str]:
    if not feedback_manager:
        return None
    if not should_trigger_feedback(stage, progress_overall):
        return None

    result = await feedback_manager.check_and_trigger(
        stage, progress_overall, step_id, execute_skill_fn
    )
    if not result:
        return None
    if result.decision == UserDecision.CONTINUE:
        return None
    if result.decision == UserDecision.ADJUST:
        return result.feedback_text
    if result.decision == UserDecision.REDO:
        raise RedoStageRequest(f"User requested redo of {stage}")
    if result.decision == UserDecision.STOP:
        raise StopWorkflowRequest("User requested stop", prompt)
    return None


class RedoStageRequest(Exception):
    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(f"Redo requested for stage: {stage}")


class StopWorkflowRequest(Exception):
    def __init__(self, reason: str, prompt: str):
        self.reason = reason
        self.prompt = prompt
        super().__init__(f"Stop requested: {reason}")


class ConsoleFeedbackUI:
    """Console-based feedback UI."""

    @staticmethod
    def show_progress_bar(current: int, total: int, stage: str) -> None:
        percent = int(100 * current / total) if total > 0 else 0
        bar_width = 40
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = "#" * filled + "-" * (bar_width - filled)
        print(f"\r[{bar}] {percent}% | {stage}", end="", flush=True)
        if current >= total:
            print()

    @staticmethod
    def show_checkpoint_message(stage: str, percent: int, question: str) -> None:
        print(f"\n{'=' * 60}")
        print(f"Modeling checkpoint | {stage} | Progress: {percent}%")
        print(f"{'=' * 60}")
        print(f"\n{question}")

    @staticmethod
    def show_options(options: List[str]) -> None:
        print("\nOptions:")
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")

    @staticmethod
    def get_choice(prompt: str = "Choose: ") -> str:
        try:
            return input(f"\n{prompt}")
        except (EOFError, KeyboardInterrupt):
            return "1"


class ProgrammaticFeedbackLoop:
    """Feedback loop that accepts predetermined responses (for tests/API)."""

    def __init__(self, responses: Optional[List[FeedbackResult]] = None):
        self._responses = responses or []
        self._response_index = 0
        self._passed_checkpoints: List[str] = []

    def should_trigger(self, stage: str, progress_percent: int) -> bool:
        _ = (stage, progress_percent)
        return self._response_index < len(self._responses)

    async def request_feedback(
        self,
        context: FeedbackContext,
        preview_callback: Optional[Callable[[], str]] = None,
    ) -> FeedbackResult:
        _ = (context, preview_callback)
        if self._response_index < len(self._responses):
            result = self._responses[self._response_index]
            self._response_index += 1
            print(f"[ProgrammaticFeedback] Auto-replied: {result.decision.value}")
            return result
        return FeedbackResult(decision=UserDecision.CONTINUE)

    def queue_response(self, decision: UserDecision, feedback: str = "") -> None:
        self._responses.append(
            FeedbackResult(
                decision=decision,
                feedback_text=feedback,
            )
        )
