import pytest

from vbf.feedback.control import ClosedLoopControl
from vbf.feedback.geometry_capture import ObjectGeometry
from vbf.transport.jsonrpc_ws import JsonRpcError


class _FailingClient:
    async def execute_skill(self, skill, args, step_id=None):
        raise JsonRpcError(code=-32000, message="Skill execution failed")


class _DummyCapture:
    def __init__(self):
        self._cache = {}

    async def capture_objects(self, target_objects, level=None, use_cache=True):
        return {}


class _CreateClient:
    async def execute_skill(self, skill, args, step_id=None):
        return {"ok": True, "data": {"object_name": args["name"]}}


class _RecordingCapture:
    def __init__(self):
        self._cache = {}
        self.calls = []

    async def capture_objects(self, target_objects, level=None, use_cache=True):
        self.calls.append({"targets": list(target_objects), "use_cache": use_cache})
        result = {}
        for name in target_objects:
            result[name] = ObjectGeometry(
                name=name,
                obj_type="MESH",
                location=[0.0, 0.0, 0.0],
                dimensions=[1.0, 1.0, 1.0],
            )
            self._cache[name] = result[name]
        return result


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


@pytest.mark.asyncio
async def test_execute_with_feedback_does_not_precapture_new_create_target():
    loop = ClosedLoopControl(
        client=_CreateClient(),
        enable_auto_check=False,
        enable_llm_feedback=False,
    )
    capture = _RecordingCapture()
    step_results = {}
    step = {
        "step_id": "001",
        "stage": "primitive_blocking",
        "skill": "create_beveled_box",
        "args": {
            "name": "GEO_Phone_Chassis",
            "size": [7.2, 14.8, 0.75],
            "location": [0, 0, 0],
        },
    }

    decision, post_state = await loop.execute_with_feedback(step, step_results, capture)

    assert decision.action == "continue"
    assert capture.calls[0]["targets"] == []
    assert capture.calls[-1]["targets"] == ["GEO_Phone_Chassis"]
    assert capture.calls[-1]["use_cache"] is False
    assert "GEO_Phone_Chassis" in post_state
