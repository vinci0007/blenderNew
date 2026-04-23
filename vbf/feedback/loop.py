"""User Feedback Loop System for VBF.

Provides interactive checkpoints during modeling workflow
where users can review progress and provide feedback.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import time


class UserDecision(Enum):
    """User decisions at feedback checkpoints."""

    CONTINUE = "continue"  # Proceed to next stage
    ADJUST = "adjust"  # Continue with adjusted parameters
    REDO = "redo"  # Redo current/last stage
    STOP = "stop"  # Stop workflow and save state
    SKIP = "skip"  # Skip feedback and continue (for automation)


@dataclass
class FeedbackContext:
    """Context for a feedback checkpoint."""

    stage_name: str
    progress_percent: int
    step_id: Optional[str]
    description: str
    options: List[str] = field(default_factory=list)
    hint: str = ""


@dataclass
class FeedbackResult:
    """Result of user feedback."""

    decision: UserDecision
    feedback_text: str = ""  # User's text feedback
    adjustment_params: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class FeedbackCheckpoint:
    """Definition of a feedback checkpoint."""

    stage_name: str
    progress_percent: int
    question: str
    options: List[str]
    hint: str
    # Extended fields for closed-loop integration
    geometry_delta: Optional[Dict[str, Any]] = None  # Geometry changes at this checkpoint
    llm_analysis: Optional[Dict[str, Any]] = None  # LLM quality analysis result
    stage_objects: Optional[List[str]] = None  # Objects in this stage


# Predefined feedback checkpoints for 18-stage workflow
DEFAULT_CHECKPOINTS: List[FeedbackCheckpoint] = [
    FeedbackCheckpoint(
        stage_name="silhouette_validation",
        progress_percent=20,
        question="轮廓剪影验证完成。当前模型的整体形状是否符合预期？",
        options=["继续下一步", "调整比例", "重做此阶段", "暂停任务"],
        hint="关注整体轮廓，忽略细节",
    ),
    FeedbackCheckpoint(
        stage_name="proportion_check",
        progress_percent=35,
        question="比例检查完成。各部分尺寸比例是否满意？",
        options=["继续下一步", "调整尺寸", "重做blocking", "暂停任务"],
        hint="比较各部分相对大小",
    ),
    FeedbackCheckpoint(
        stage_name="bevel_chamfer",
        progress_percent=60,
        question="倒角处理完成。边缘软硬程度是否符合预期？",
        options=["继续下一步", "调整倒角", "重做bevel", "暂停任务"],
        hint="检查边缘过渡是否自然",
    ),
    FeedbackCheckpoint(
        stage_name="high_poly_finalize",
        progress_percent=85,
        question="高模最终化完成。模型细节程度是否满意？",
        options=["继续材质", "增加细节", "重做细节阶段", "暂停任务"],
        hint="确认细节后将进入材质阶段",
    ),
]


class FeedbackLoop:
    """Manages interactive feedback checkpoints during modeling."""

    def __init__(
        self,
        checkpoints: Optional[List[FeedbackCheckpoint]] = None,
        auto_skip: bool = False,
        timeout_seconds: Optional[float] = None,
    ):
        self.checkpoints = checkpoints or DEFAULT_CHECKPOINTS
        self.auto_skip = auto_skip
        self.timeout_seconds = timeout_seconds
        self._passed_checkpoints: List[str] = []
        self._feedback_history: List[FeedbackResult] = []

    def should_trigger(self, stage_name: str, progress_percent: int) -> bool:
        """Check if a checkpoint should be triggered."""
        if self.auto_skip:
            return False

        for cp in self.checkpoints:
            if cp.stage_name == stage_name:
                # Trigger near the checkpoint progress (±5%)
                if abs(cp.progress_percent - progress_percent) <= 5:
                    if stage_name not in self._passed_checkpoints:
                        return True
        return False

    async def request_feedback(
        self,
        context: FeedbackContext,
        preview_callback: Optional[Callable[[], str]] = None,
    ) -> FeedbackResult:
        """Request user feedback at a checkpoint."""

        if self.auto_skip:
            return FeedbackResult(decision=UserDecision.CONTINUE)

        # Print context
        print("\n" + "=" * 60)
        print(f"[VBF] 建模反馈检查点 - {context.progress_percent}% 完成")
        print("=" * 60)
        print(f"\n当前阶段: {context.stage_name}")
        print(f"步骤ID: {context.step_id or 'N/A'}")
        print(f"\n{context.description}")

        if context.hint:
            print(f"\n提示: {context.hint}")

        # Generate preview if available
        if preview_callback:
            try:
                preview_info = await asyncio.to_thread(preview_callback)
                if preview_info:
                    print(f"\n预览信息: {preview_info}")
            except Exception as e:
                print(f"\n[预览生成失败: {e}]")

        # Show options
        print("\n选项:")
        for i, option in enumerate(context.options, 1):
            print(f"  {i}. {option}")

        # Get user input
        decision = await self._get_user_choice(context.options, self.timeout_seconds)

        # Record that we passed this checkpoint
        if context.stage_name not in self._passed_checkpoints:
            self._passed_checkpoints.append(context.stage_name)

        # Map choice to decision
        choice_map = {
            1: UserDecision.CONTINUE,
            2: UserDecision.ADJUST,
            3: UserDecision.REDO,
            4: UserDecision.STOP,
        }
        result = FeedbackResult(
            decision=choice_map.get(decision, UserDecision.CONTINUE)
        )

        # Additional feedback for ADJUST
        if result.decision == UserDecision.ADJUST:
            adjustment = await self._get_adjustment_input()
            result.feedback_text = adjustment

        self._feedback_history.append(result)
        return result

    async def _get_user_choice(
        self, options: List[str], timeout: Optional[float]
    ) -> int:
        """Get user choice with optional timeout."""
        if timeout:
            print(f"\n请在 {timeout} 秒内选择 (默认: 1.继续): ", end="", flush=True)
        else:
            print("\n请选择 (输入数字): ", end="", flush=True)

        try:
            if timeout:
                # Use asyncio.wait_for for timeout
                user_input = await asyncio.wait_for(
                    asyncio.to_thread(input), timeout=timeout
                )
            else:
                user_input = input()

            choice = int(user_input.strip())
            if 1 <= choice <= len(options):
                return choice
        except asyncio.TimeoutError:
            print("\n[超时，自动继续]")
            return 1
        except (ValueError, IndexError):
            pass

        # Default to continue
        print("[无效输入，默认继续]")
        return 1

    async def _get_adjustment_input(self) -> str:
        """Get user's adjustment request."""
        print("\n请输入调整建议 (例如: '整体放大20%', '增加更多细节', '边缘再圆润一些'): ")
        try:
            return input("> ").strip()
        except Exception:
            return ""

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary of all feedback provided."""
        return {
            "checkpoints_passed": self._passed_checkpoints,
            "total_decisions": len(self._feedback_history),
            "adjustments_requested": sum(
                1 for r in self._feedback_history if r.decision == UserDecision.ADJUST
            ),
            "redos_requested": sum(
                1 for r in self._feedback_history if r.decision == UserDecision.REDO
            ),
        }

    def reset(self) -> None:
        """Reset feedback loop for new task."""
        self._passed_checkpoints.clear()
        self._feedback_history.clear()


class NonInteractiveFeedbackLoop(FeedbackLoop):
    """Feedback loop that auto-continues (for testing/automation)."""

    def __init__(self):
        super().__init__(auto_skip=True)

    async def request_feedback(
        self,
        context: FeedbackContext,
        preview_callback: Optional[Callable[[], str]] = None,
    ) -> FeedbackResult:
        """Auto-continue without user interaction."""
        print(f"\n[VBF] Checkpoint at {context.progress_percent}%: auto-continuing")
        return FeedbackResult(decision=UserDecision.CONTINUE)


# Utility functions for integration

def create_feedback_context(
    stage_name: str,
    progress_percent: int,
    step_id: Optional[str] = None,
    custom_hint: str = "",
) -> FeedbackContext:
    """Create a feedback context for the given stage."""

    # Find matching checkpoint
    checkpoint = None
    for cp in DEFAULT_CHECKPOINTS:
        if cp.stage_name == stage_name:
            checkpoint = cp
            break

    if checkpoint:
        return FeedbackContext(
            stage_name=stage_name,
            progress_percent=progress_percent,
            step_id=step_id,
            description=checkpoint.question,
            options=checkpoint.options,
            hint=checkpoint.hint if not custom_hint else custom_hint,
        )

    # Generic context
    return FeedbackContext(
        stage_name=stage_name,
        progress_percent=progress_percent,
        step_id=step_id,
        description=f"完成 {stage_name} 阶段。是否继续？",
        options=["继续下一步", "调整参数", "重做此阶段", "暂停任务"],
        hint="检查当前进度",
    )
