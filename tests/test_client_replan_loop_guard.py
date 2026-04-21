import pytest
from unittest.mock import AsyncMock
import os

from vbf.client import VBFClient
from vbf.feedback_control import FeedbackDecision
from vbf.task_state import TaskInterruptedError


class _DummyScene:
    def __init__(self):
        self._objects = []

    def to_prompt_text(self):
        return "Scene: Test"


class _FakeLoop:
    def __init__(self, *args, **kwargs):
        self._calls = 0

    async def execute_with_feedback(self, step, step_results, scene_capture):
        self._calls += 1
        return FeedbackDecision(
            action="replan",
            detail={
                "step_id": step.get("step_id", "001"),
                "skill": "set_parent",
                "error": "child object not found: CameraModule",
                "reason": "execute_skill_failed",
            },
        ), None


class _DummyCapture:
    def __init__(self, client):
        self._cache = {}

    def invalidate_cache(self):
        return None


@pytest.mark.asyncio
async def test_run_task_with_feedback_interrupts_on_repeated_replan_fingerprint(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(client, "ensure_connected", AsyncMock())
    monkeypatch.setattr(client, "_is_llm_enabled", lambda: True)
    monkeypatch.setattr(client, "list_skills", AsyncMock(return_value=["create_primitive", "set_parent"]))
    monkeypatch.setattr(client, "capture_scene_state", AsyncMock(return_value=_DummyScene()))

    initial_plan = {"execution": {"max_replans": 8}}
    initial_steps = [{"step_id": "001", "stage": "detail", "skill": "set_parent", "args": {}}]
    monkeypatch.setattr(
        client,
        "_plan_skill_task",
        AsyncMock(return_value=(initial_plan, initial_steps)),
    )

    replan_mock = AsyncMock(return_value=({"execution": {"max_replans": 8}}, initial_steps))
    monkeypatch.setattr(client, "_replan_from_step", replan_mock)

    monkeypatch.setattr("vbf.feedback_control.ClosedLoopControl", _FakeLoop)
    monkeypatch.setattr("vbf.geometry_capture.IncrementalSceneCapture", _DummyCapture)

    save_path = os.path.join("vbf", "config", "task_state_loop_guard_test.json")
    try:
        with pytest.raises(TaskInterruptedError) as exc:
            await client.run_task_with_feedback(
                prompt="create a phone",
                save_state_path=save_path,
            )

        assert "Loop guard interrupted repeated replans" in str(exc.value)
        assert exc.value.state.diagnostics.get("loop_guard", {}).get("hit") is True
        assert replan_mock.await_count == 2
        assert replan_mock.await_args_list[0].kwargs["forced_corrective"] is False
        assert replan_mock.await_args_list[1].kwargs["forced_corrective"] is True
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)
