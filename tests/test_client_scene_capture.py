import pytest
from unittest.mock import AsyncMock

from vbf.app.client import VBFClient


@pytest.mark.asyncio
async def test_capture_scene_state_uses_scene_snapshot_when_available(monkeypatch):
    client = VBFClient()

    monkeypatch.setattr(
        client,
        "get_scene_snapshot",
        AsyncMock(
            return_value={
                "ok": True,
                "data": {
                    "seq": 7,
                    "objects": {
                        "Cube": {
                            "type": "MESH",
                            "location": [1, 2, 3],
                            "dimensions": [4, 5, 6],
                            "vertices": 8,
                            "polygons": 6,
                            "edges": 12,
                            "materials": 1,
                        }
                    },
                },
            }
        ),
    )

    async def _fake_execute_skill(skill, args, step_id=None):
        assert skill == "py_get"
        path_steps = args.get("path_steps", [])
        if path_steps == [{"attr": "context"}, {"attr": "scene"}, {"attr": "name"}]:
            return {"ok": True, "data": {"value": "Scene"}}
        if path_steps == [{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_current"}]:
            return {"ok": True, "data": {"value": 10}}
        if path_steps == [{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_start"}]:
            return {"ok": True, "data": {"value": 1}}
        if path_steps == [{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_end"}]:
            return {"ok": True, "data": {"value": 120}}
        raise AssertionError(f"Unexpected capture path in snapshot mode: {path_steps}")

    monkeypatch.setattr(client, "execute_skill", _fake_execute_skill)

    state = await client.capture_scene_state()
    state_dict = state.to_dict()
    objs = state_dict["objects"]

    assert len(objs) == 1
    assert objs[0]["name"] == "Cube"
    assert objs[0]["location"] == [1.0, 2.0, 3.0]
    assert objs[0]["size"] == [4.0, 5.0, 6.0]
    assert objs[0]["vertices"] == 8
    assert objs[0]["polygons"] == 6
    assert state.statistics["capture_source"] == "scene_snapshot"
    assert state.statistics["snapshot_seq"] == 7


@pytest.mark.asyncio
async def test_capture_scene_state_falls_back_to_py_get_when_snapshot_missing(monkeypatch):
    client = VBFClient()

    monkeypatch.setattr(
        client,
        "get_scene_snapshot",
        AsyncMock(return_value={"ok": False, "method_not_found": True}),
    )

    async def _fake_execute_skill(skill, args, step_id=None):
        if skill == "py_call":
            return {"ok": True, "data": {"result": ["Cube", "Light"]}}

        assert skill == "py_get"
        path_steps = args.get("path_steps", [])

        if path_steps == [{"attr": "context"}, {"attr": "scene"}, {"attr": "name"}]:
            return {"ok": True, "data": {"value": "FallbackScene"}}
        if path_steps == [{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_current"}]:
            return {"ok": True, "data": {"value": 24}}
        if path_steps == [{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_start"}]:
            return {"ok": True, "data": {"value": 1}}
        if path_steps == [{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_end"}]:
            return {"ok": True, "data": {"value": 250}}

        if path_steps == [{"attr": "data"}, {"attr": "objects"}, {"key": "Cube"}, {"attr": "type"}]:
            return {"ok": True, "data": {"value": "MESH"}}
        if path_steps == [{"attr": "data"}, {"attr": "objects"}, {"key": "Cube"}, {"attr": "location"}]:
            return {"ok": True, "data": {"value": [0, 0, 0]}}
        if path_steps == [{"attr": "data"}, {"attr": "objects"}, {"key": "Cube"}, {"attr": "dimensions"}]:
            return {"ok": True, "data": {"value": [2, 2, 2]}}

        if path_steps == [{"attr": "data"}, {"attr": "objects"}, {"key": "Light"}, {"attr": "type"}]:
            return {"ok": True, "data": {"value": "LIGHT"}}
        if path_steps == [{"attr": "data"}, {"attr": "objects"}, {"key": "Light"}, {"attr": "location"}]:
            return {"ok": True, "data": {"value": [3, 0, 1]}}
        if path_steps == [{"attr": "data"}, {"attr": "objects"}, {"key": "Light"}, {"attr": "dimensions"}]:
            return {"ok": True, "data": {"value": [0, 0, 0]}}

        return {"ok": False, "data": {}}

    monkeypatch.setattr(client, "execute_skill", _fake_execute_skill)

    state = await client.capture_scene_state()
    state_dict = state.to_dict()
    objs = state_dict["objects"]

    assert len(objs) == 2
    assert {o["name"] for o in objs} == {"Cube", "Light"}
    assert state.scene_name == "FallbackScene"
    assert state.statistics["capture_source"] == "py_get_fallback"
