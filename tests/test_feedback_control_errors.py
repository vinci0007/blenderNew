import pytest

from vbf.feedback_control import ClosedLoopControl
from vbf.jsonrpc_ws import JsonRpcError


class _FailingClient:
    async def execute_skill(self, skill, args, step_id=None):
        raise JsonRpcError(code=-32000, message="Skill execution failed")


class _DummyCapture:
    def __init__(self):
        self._cache = {}

    async def capture_objects(self, target_objects, level=None, use_cache=True):
        return {}


@pytest.mark.asyncio
async def test_execute_with_feedback_converts_jsonrpc_error_to_replan():
    loop = ClosedLoopControl(
        client=_FailingClient(),
        enable_auto_check=True,
        enable_llm_feedback=False,
    )
    step_results = {}
    step = {
        "step_id": "002",
        "stage": "assembly_refinement",
        "skill": "set_parent",
        "args": {"child_name": "CameraModule", "parent_name": "PhoneBody"},
    }

    decision, post_state = await loop.execute_with_feedback(step, step_results, _DummyCapture())

    assert decision.action == "replan"
    assert decision.detail.get("reason") == "execute_skill_failed"
    assert "002" in step_results
    assert step_results["002"]["ok"] is False
    assert post_state is None
