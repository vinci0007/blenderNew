import pytest
from unittest.mock import AsyncMock

from vbf.app.client import VBFClient


class _FakeAdapter:
    def format_messages(self, prompt: str):
        return [{"role": "user", "content": prompt}]


@pytest.mark.asyncio
async def test_plan_generation_retries_when_only_pseudo_steps(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(client, "_ensure_adapter", AsyncMock(return_value=_FakeAdapter()))

    first_bad = {
        "steps": [
            {
                "step_id": "001",
                "stage": "skill_discovery",
                "skill": "load_skill",
                "args": {"skill_name": "create_primitive"},
            }
        ]
    }
    second_good = {
        "steps": [
            {
                "step_id": "001",
                "stage": "primitive_blocking",
                "skill": "create_primitive",
                "args": {"type": "cube"},
            }
        ]
    }
    call_mock = AsyncMock(side_effect=[first_bad, second_good])
    monkeypatch.setattr(client, "_adapter_call", call_mock)

    plan, steps = await client._plan_skill_task(
        prompt="create a iphoneX",
        allowed_skills=["create_primitive"],
        save_path="vbf/cache/task_state.json",
    )

    assert call_mock.await_count == 2
    assert len(steps) == 1
    assert steps[0]["skill"] == "create_primitive"
    assert steps[0]["args"]["primitive_type"] == "cube"


@pytest.mark.asyncio
async def test_plan_shape_failure_logs_pre_normalize_raw_snapshot(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(client, "_ensure_adapter", AsyncMock(return_value=_FakeAdapter()))

    first_bad = {
        "steps": [
            {
                "step_id": "001",
                "stage": "skill_discovery",
                "skill": "load_skill",
                "args": {"skill_name": "create_primitive"},
            }
        ]
    }
    second_good = {
        "steps": [
            {
                "step_id": "001",
                "stage": "primitive_blocking",
                "skill": "create_primitive",
                "args": {"type": "cube"},
            }
        ]
    }
    call_mock = AsyncMock(side_effect=[first_bad, second_good])
    monkeypatch.setattr(client, "_call_plan_with_format_retry", call_mock)

    captured = []

    def _capture(error_message, raw_plan, stage="normalize_plan"):
        captured.append({"error": error_message, "raw_plan": raw_plan, "stage": stage})

    monkeypatch.setattr(client, "_record_plan_shape_failure", _capture)

    plan, steps = await client._plan_skill_task(
        prompt="create a smartphone",
        allowed_skills=["create_primitive"],
        save_path="vbf/cache/task_state.json",
    )

    assert len(steps) == 1
    assert captured, "expected at least one logged plan-shape failure"
    assert captured[0]["stage"] == "plan_round"
    assert captured[0]["raw_plan"]["steps"][0]["skill"] == "load_skill"


@pytest.mark.asyncio
async def test_plan_generation_retries_when_steps_field_missing(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(client, "_ensure_adapter", AsyncMock(return_value=_FakeAdapter()))

    first_bad = {"result": {"message": "no steps"}}
    second_good = {
        "steps": [
            {
                "step_id": "001",
                "stage": "primitive_blocking",
                "skill": "create_primitive",
                "args": {"type": "cube"},
            }
        ]
    }
    call_mock = AsyncMock(side_effect=[first_bad, second_good])
    monkeypatch.setattr(client, "_adapter_call", call_mock)

    plan, steps = await client._plan_skill_task(
        prompt="create a smartphone",
        allowed_skills=["create_primitive"],
        save_path="vbf/cache/task_state.json",
    )

    assert call_mock.await_count == 2
    assert len(steps) == 1
    assert steps[0]["skill"] == "create_primitive"


@pytest.mark.asyncio
async def test_call_plan_with_format_retry_retries_on_plan_shape_missing_steps(monkeypatch):
    client = VBFClient()
    adapter = _FakeAdapter()

    first_bad = {"result": {"message": "no steps"}}
    second_good = {
        "steps": [
            {
                "step_id": "001",
                "stage": "primitive_blocking",
                "skill": "create_primitive",
                "args": {"type": "cube"},
            }
        ]
    }
    call_mock = AsyncMock(side_effect=[first_bad, second_good])
    monkeypatch.setattr(client, "_adapter_call", call_mock)

    plan = await client._call_plan_with_format_retry(adapter, "create a smartphone")

    assert call_mock.await_count == 2
    assert "steps" in plan
    assert plan["steps"][0]["skill"] == "create_primitive"


@pytest.mark.asyncio
async def test_call_plan_with_format_retry_disables_tools_for_tool_calls_payload(monkeypatch):
    client = VBFClient()
    adapter = _FakeAdapter()
    adapter._allow_tools = True

    first_bad = {
        "tool_calls": [
            {"name": "load_skill", "arguments": {"skill_name": "create_primitive"}},
        ]
    }
    second_good = {
        "steps": [
            {
                "step_id": "001",
                "stage": "primitive_blocking",
                "skill": "create_primitive",
                "args": {"type": "cube"},
            }
        ]
    }
    call_mock = AsyncMock(side_effect=[first_bad, second_good])
    monkeypatch.setattr(client, "_adapter_call", call_mock)

    plan = await client._call_plan_with_format_retry(adapter, "create a smartphone")

    assert call_mock.await_count == 2
    assert adapter._allow_tools is True
    assert "steps" in plan


@pytest.mark.asyncio
async def test_call_plan_with_format_retry_rescues_after_two_empty_step_payloads(monkeypatch):
    client = VBFClient()
    adapter = _FakeAdapter()

    first_empty = {"steps": []}
    second_empty = {"steps": []}
    third_good = {
        "steps": [
            {
                "step_id": "001",
                "stage": "primitive_blocking",
                "skill": "create_primitive",
                "args": {"type": "cube"},
            },
            {
                "step_id": "002",
                "stage": "detail",
                "skill": "add_modifier_bevel",
                "args": {"object_name": {"$ref": "step_001.data.object_name"}, "width": 0.02, "segments": 2},
            },
            {
                "step_id": "003",
                "stage": "finalize",
                "skill": "apply_modifier",
                "args": {"object_name": {"$ref": "step_001.data.object_name"}, "modifier": "VBF_Bevel"},
            },
        ]
    }
    call_mock = AsyncMock(side_effect=[first_empty, second_empty, third_good])
    monkeypatch.setattr(client, "_adapter_call", call_mock)

    plan = await client._call_plan_with_format_retry(adapter, "create a smartphone")

    assert call_mock.await_count == 3
    assert "steps" in plan
    assert len(plan["steps"]) >= 3
