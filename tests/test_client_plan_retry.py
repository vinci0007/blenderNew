import pytest
from unittest.mock import AsyncMock

from vbf.client import VBFClient


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
        save_path="vbf/config/task_state.json",
    )

    assert call_mock.await_count == 2
    assert len(steps) == 1
    assert steps[0]["skill"] == "create_primitive"
    assert steps[0]["args"]["primitive_type"] == "cube"
