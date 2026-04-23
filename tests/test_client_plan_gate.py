import pytest
from unittest.mock import AsyncMock

from vbf.app.client import VBFClient


class _SchemaAdapter:
    def format_messages(self, prompt: str, skills_subset=None):
        return [{"role": "user", "content": prompt}]

    def get_skill_description(self, skill_name: str):
        return skill_name

    def get_skill_params(self, skill_name: str):
        if skill_name == "create_primitive":
            return {
                "primitive_type": {"required": True, "type": "str", "default": None},
                "name": {"required": False, "type": "str", "default": None},
            }
        if skill_name == "mark_edge_crease":
            return {
                "object_name": {"required": True, "type": "str", "default": None},
                "edges": {"required": True, "type": "list", "default": None},
                "crease_value": {"required": False, "type": "float", "default": 1.0},
            }
        return {}


def test_plan_gate_rejects_unknown_args():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"primitive_type": "cube", "bad_arg": 1},
            }
        ]
    }
    with pytest.raises(ValueError, match="plan_gate_unknown_args"):
        client._validate_plan_with_skill_schemas(plan, adapter, ["create_primitive"])


def test_plan_gate_rejects_missing_required():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"name": "cube"},
            }
        ]
    }
    with pytest.raises(ValueError, match="plan_gate_missing_required"):
        client._validate_plan_with_skill_schemas(plan, adapter, ["create_primitive"])


def test_plan_gate_autofix_drops_mark_edge_crease_without_edges():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"primitive_type": "cube"},
            },
            {
                "step_id": "002",
                "skill": "mark_edge_crease",
                "args": {"object_name": {"$ref": "step_001.data.object_name"}},
            },
        ]
    }
    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_primitive", "mark_edge_crease"],
    )

    assert len(steps) == 1
    assert steps[0]["skill"] == "create_primitive"
    assert len(plan["steps"]) == 1


def test_plan_gate_autofix_fill_create_primitive_and_drop_unknown_args():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"bad_arg": 1},
            }
        ]
    }
    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_primitive"],
    )

    assert len(steps) == 1
    assert steps[0]["args"]["primitive_type"] == "cube"
    assert "bad_arg" not in steps[0]["args"]


@pytest.mark.asyncio
async def test_plan_skill_task_expands_subset_on_plan_gate_error(monkeypatch):
    client = VBFClient()
    adapter = _SchemaAdapter()
    monkeypatch.setattr(client, "_ensure_adapter", AsyncMock(return_value=adapter))

    subsets = []

    async def _fake_call(adapter_obj, prompt, skills_subset=None):
        subsets.append(list(skills_subset or []))
        if len(subsets) <= 2:
            return {
                "steps": [
                    {
                        "step_id": "001",
                        "skill": "unknown_skill",
                        "args": {},
                    }
                ]
            }
        return {
            "steps": [
                {
                    "step_id": "001",
                    "skill": "create_primitive",
                    "args": {"primitive_type": "cube"},
                }
            ]
        }

    monkeypatch.setattr(client, "_call_plan_with_format_retry", _fake_call)

    allowed_skills = ["create_primitive"] + [f"skill_{i:03d}" for i in range(180)]
    plan, steps = await client._plan_skill_task(
        prompt="create a precise phone with bevels",
        allowed_skills=allowed_skills,
        save_path="vbf/cache/task_state.json",
    )

    assert steps[0]["skill"] == "create_primitive"
    assert steps[0]["args"]["primitive_type"] == "cube"
    assert len(subsets) >= 3
    assert len(subsets[0]) < len(allowed_skills)
    assert len(subsets[-1]) > len(subsets[0])
