import pytest
from types import SimpleNamespace

from vbf.feedback.control import ClosedLoopControl
from vbf.feedback.geometry_capture import ObjectGeometry
from vbf.core.scene_state import SceneState
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


class _OkClient:
    async def execute_skill(self, skill, args, step_id=None):
        return {"ok": True, "data": {}}

    async def capture_scene_state(self):
        return SceneState()


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


@pytest.mark.asyncio
async def test_llm_feedback_uses_major_analysis_stage_boundaries(monkeypatch):
    analyzed_stages = []

    class _FakeAnalyzer:
        def __init__(self, client):
            self.client = client

        async def analyze_geometry_quality(self, stage, scene, step_results, context="general", task_prompt=None):
            analyzed_stages.append(stage)
            return SimpleNamespace(quality="good", score=1.0)

    monkeypatch.setattr("vbf.feedback.llm.GeometryFeedbackAnalyzer", _FakeAnalyzer)

    loop = ClosedLoopControl(
        client=_OkClient(),
        enable_auto_check=False,
        enable_llm_feedback=True,
    )
    capture = _DummyCapture()
    step_results = {}

    steps = [
        {"step_id": "001", "stage": "primitive_blocking", "skill": "noop", "args": {}},
        {"step_id": "002", "stage": "transform_alignment", "skill": "noop", "args": {}},
        {"step_id": "003", "stage": "mesh_cleanup", "skill": "noop", "args": {}},
        {"step_id": "004", "stage": "material_setup", "skill": "noop", "args": {}},
        {"step_id": "005", "stage": "uv_setup", "skill": "noop", "args": {}},
        {"step_id": "006", "stage": "lighting_setup", "skill": "noop", "args": {}},
    ]

    for step in steps:
        decision, _post_state = await loop.execute_with_feedback(step, step_results, capture)
        assert decision.action == "continue"

    assert analyzed_stages == ["geometry_modeling", "uv_texture_material"]
