import pytest

from vbf.client import VBFClient


@pytest.mark.asyncio
async def test_two_stage_planning_merges_and_reindexes_refs(monkeypatch):
    client = VBFClient()

    async def _fake_plan(prompt, allowed_skills, save_path):
        if "STAGE 1 / GEOMETRY ONLY" in prompt:
            return (
                {"vbf_version": "2.1", "plan_type": "skills_plan", "steps": []},
                [
                    {"step_id": "001", "skill": "create_primitive", "args": {"type": "cube"}},
                    {"step_id": "002", "skill": "create_primitive", "args": {"type": "cube"}},
                ],
            )
        if "STAGE 2 / PRESENTATION ONLY" in prompt:
            return (
                {"vbf_version": "2.1", "plan_type": "skills_plan", "steps": []},
                [
                    {"step_id": "001", "skill": "create_light", "args": {"light_type": "AREA"}},
                    {
                        "step_id": "002",
                        "skill": "set_parent",
                        "args": {"child_name": {"$ref": "step_001.data.object_name"}},
                    },
                ],
            )
        raise AssertionError("unexpected prompt")

    monkeypatch.setattr(client, "_plan_skill_task", _fake_plan)

    plan, steps = await client._plan_skill_task_two_stage(
        prompt="create futuristic phone and render shot",
        allowed_skills=[
            "create_primitive",
            "set_parent",
            "create_light",
            "set_render_resolution",
            "assign_material",
        ],
        save_path="vbf/config/task_state.json",
    )

    assert plan["metadata"]["planning_mode"] == "two_stage"
    assert [s["step_id"] for s in steps] == ["001", "002", "003", "004"]
    assert steps[3]["args"]["child_name"]["$ref"] == "step_003.data.object_name"


def test_two_stage_planning_can_be_forced_off(monkeypatch):
    client = VBFClient()
    monkeypatch.setenv("VBF_TWO_STAGE_PLANNING", "never")
    assert client._should_use_two_stage_planning("x" * 4000, ["a"] * 500) is False
