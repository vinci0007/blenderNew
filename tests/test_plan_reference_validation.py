import pytest

from vbf.core.plan_normalization import normalize_plan


def test_normalize_plan_accepts_backward_step_refs():
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"type": "cube"},
            },
            {
                "step_id": "002",
                "skill": "set_parent",
                "args": {
                    "child_name": {"$ref": "step_001.data.object_name"},
                    "parent_name": {"$ref": "001.data.object_name"},
                },
            },
        ]
    }
    normalized = normalize_plan(plan)
    assert len(normalized["steps"]) == 2


def test_normalize_plan_rejects_scene_object_ref_schema():
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "set_parent",
                "args": {"child_name": {"$ref": "scene.objects[CameraModule]"}},
            }
        ]
    }
    with pytest.raises(ValueError, match="invalid_ref_schema"):
        normalize_plan(plan)


def test_normalize_plan_rejects_unknown_ref_step():
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "set_parent",
                "args": {"child_name": {"$ref": "step_999.data.object_name"}},
            }
        ]
    }
    with pytest.raises(ValueError, match="unknown_ref_step"):
        normalize_plan(plan)


def test_normalize_plan_rejects_forward_ref_step():
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "set_parent",
                "args": {"child_name": {"$ref": "step_002.data.object_name"}},
            },
            {
                "step_id": "002",
                "skill": "create_primitive",
                "args": {"type": "cube"},
            },
        ]
    }
    with pytest.raises(ValueError, match="forward_ref_step"):
        normalize_plan(plan)


def test_normalize_plan_rejects_self_reference_as_forward_ref():
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "set_parent",
                "args": {"child_name": {"$ref": "step_001.data.object_name"}},
            }
        ]
    }
    with pytest.raises(ValueError, match="forward_ref_step"):
        normalize_plan(plan)
