"""Tests for user feedback loop system."""

import pytest
from unittest.mock import patch
import asyncio

from vbf.feedback_loop import (
    FeedbackLoop,
    FeedbackContext,
    FeedbackResult,
    UserDecision,
    FeedbackCheckpoint,
    DEFAULT_CHECKPOINTS,
    create_feedback_context,
)
from vbf.feedback_ui import (
    should_trigger_feedback,
    FeedbackUIManager,
    RedoStageRequest,
    StopWorkflowRequest,
)


class TestFeedbackCheckpoint:
    """Tests for feedback checkpoint detection."""

    def test_silhouette_validation_trigger(self):
        """silhouette_validation should trigger at 20% (±5 tolerance)."""
        assert should_trigger_feedback("silhouette_validation", 20) is True
        # Within ±5 tolerance: 15-25 should trigger
        assert should_trigger_feedback("silhouette_validation", 15) is True
        assert should_trigger_feedback("silhouette_validation", 25) is True
        # Outside tolerance: 14 is < 15, diff = 6 > 5
        assert should_trigger_feedback("silhouette_validation", 14) is False
        assert should_trigger_feedback("silhouette_validation", 26) is False

    def test_proportion_check_trigger(self):
        """proportion_check should trigger at 35%."""
        assert should_trigger_feedback("proportion_check", 35) is True
        assert should_trigger_feedback("proportion_check", 30) is True  # Within ±5

    def test_bevel_chamfer_trigger(self):
        """bevel_chamfer should trigger at 60%."""
        assert should_trigger_feedback("bevel_chamfer", 60) is True

    def test_high_poly_finalize_trigger(self):
        """high_poly_finalize should trigger at 85%."""
        assert should_trigger_feedback("high_poly_finalize", 85) is True

    def test_non_checkpoint_stage(self):
        """Stages not in checkpoints should not trigger."""
        assert should_trigger_feedback("topology_prep", 50) is False
        assert should_trigger_feedback("unknown_stage", 50) is False


class TestFeedbackContextCreation:
    """Tests for feedback context creation."""

    def test_known_stage_context(self):
        """Context for known checkpoint stage."""
        ctx = create_feedback_context("silhouette_validation", 20, "step_1")
        assert ctx.stage_name == "silhouette_validation"
        assert ctx.progress_percent == 20
        assert ctx.step_id == "step_1"
        assert "轮廓" in ctx.description  # Chinese question

    def test_unknown_stage_context(self):
        """Context for unknown stage uses generic message."""
        ctx = create_feedback_context("topology_prep", 50, "step_2")
        assert ctx.stage_name == "topology_prep"
        assert "是否继续" in ctx.description


class TestFeedbackLoop:
    """Tests for FeedbackLoop class."""

    def test_init_default(self):
        """FeedbackLoop initializes with default checkpoints."""
        fl = FeedbackLoop()
        assert len(fl.checkpoints) == 4
        assert fl.auto_skip is False

    def test_auto_skip_no_trigger(self):
        """Auto-skip mode never triggers feedback."""
        fl = FeedbackLoop(auto_skip=True)
        # Auto-skip mode should_trigger returns False
        assert fl.should_trigger("silhouette_validation", 20) is False

    def test_checkpoint_passed_tracking(self):
        """Passed checkpoints are tracked."""
        fl = FeedbackLoop()
        # Simulate passing a checkpoint
        assert fl.should_trigger("silhouette_validation", 20) is True
        # Mark as passed
        fl._passed_checkpoints.append("silhouette_validation")
        # Should not trigger again
        assert fl.should_trigger("silhouette_validation", 20) is False


class TestUserDecision:
    """Tests for UserDecision enum."""

    def test_decision_values(self):
        """UserDecision enum has correct values."""
        assert UserDecision.CONTINUE.value == "continue"
        assert UserDecision.STOP.value == "stop"
        assert UserDecision.REDO.value == "redo"
        assert UserDecision.ADJUST.value == "adjust"


class TestFeedbackUIManager:
    """Tests for FeedbackUIManager."""

    def test_init_interactive(self):
        """UIManager initialized with interactive mode."""
        ui = FeedbackUIManager(enable_interactive=True)
        assert ui._feedback_loop is not None

    def test_init_non_interactive(self):
        """UIManager initialized without interactive mode."""
        ui = FeedbackUIManager(enable_interactive=False)
        assert ui._feedback_loop is None

    def test_summary_empty(self):
        """Summary for unused feedback loop."""
        ui = FeedbackUIManager(enable_interactive=True)
        summary = ui.get_summary()
        assert summary["checkpoints_passed"] == []
        assert summary["total_decisions"] == 0


class TestDefaultCheckpoints:
    """Tests for default checkpoint definitions."""

    def test_checkpoint_count(self):
        """There are 4 default checkpoints."""
        assert len(DEFAULT_CHECKPOINTS) == 4

    def test_checkpoint_stages(self):
        """Checkpoints cover key stages."""
        stages = [cp.stage_name for cp in DEFAULT_CHECKPOINTS]
        assert "silhouette_validation" in stages
        assert "proportion_check" in stages
        assert "bevel_chamfer" in stages
        assert "high_poly_finalize" in stages

    def test_checkpoint_options(self):
        """Each checkpoint has 4 options."""
        for cp in DEFAULT_CHECKPOINTS:
            assert len(cp.options) == 4
            assert "继续" in cp.options[0]  # Continue option contains Chinese

    def test_checkpoint_hint(self):
        """Each checkpoint has a hint."""
        for cp in DEFAULT_CHECKPOINTS:
            assert len(cp.hint) > 0


class TestConcurrentFeedback:
    """Tests ensuring feedback loop works correctly."""

    @pytest.mark.asyncio
    async def test_feedback_loop_async(self):
        """Feedback loop can be used in async context."""
        fl = FeedbackLoop(auto_skip=True)
        ctx = create_feedback_context("test", 50, "step_1")

        # Should not block
        result = await fl.request_feedback(ctx)
        assert result.decision == UserDecision.CONTINUE


class TestExceptions:
    """Tests for custom exceptions."""

    def test_redo_stage_request(self):
        """RedoStageRequest captures stage name."""
        exc = RedoStageRequest("silhouette_validation")
        assert "silhouette_validation" in str(exc)
        assert exc.stage == "silhouette_validation"

    def test_stop_workflow_request(self):
        """StopWorkflowRequest captures reason and prompt."""
        exc = StopWorkflowRequest("User requested", "create a cube")
        assert "User requested" in str(exc)
        assert exc.reason == "User requested"
        assert exc.prompt == "create a cube"
