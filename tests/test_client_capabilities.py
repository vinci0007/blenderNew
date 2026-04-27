import pytest
from unittest.mock import AsyncMock
from pathlib import Path

from vbf.app.client import VBFClient
from vbf.transport.jsonrpc_ws import JsonRpcError


@pytest.mark.asyncio
async def test_get_server_capabilities_caches_result(monkeypatch):
    client = VBFClient()
    ws_call = AsyncMock(
        return_value={
            "ok": True,
            "data": {"features": {"scene_snapshot": True, "scene_delta": True}},
        }
    )
    monkeypatch.setattr(client._ws, "call", ws_call)

    first = await client.get_server_capabilities()
    second = await client.get_server_capabilities()

    assert first["ok"] is True
    assert second["ok"] is True
    assert second.get("cached") is True
    assert ws_call.await_count == 1


@pytest.mark.asyncio
async def test_get_server_capabilities_method_not_found(monkeypatch):
    client = VBFClient()
    ws_call = AsyncMock(side_effect=JsonRpcError(code=-32601, message="Method not found"))
    monkeypatch.setattr(client._ws, "call", ws_call)

    resp = await client.get_server_capabilities()

    assert resp["ok"] is False
    assert resp.get("method_not_found") is True


@pytest.mark.asyncio
async def test_get_scene_snapshot_short_circuits_when_capability_disabled(monkeypatch):
    client = VBFClient()
    client._capabilities_cache = {"features": {"scene_snapshot": False}}
    ws_call = AsyncMock()
    monkeypatch.setattr(client._ws, "call", ws_call)

    resp = await client.get_scene_snapshot()

    assert resp["ok"] is False
    assert resp.get("method_not_found") is True
    ws_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_scene_delta_short_circuits_when_capability_disabled(monkeypatch):
    client = VBFClient()
    client._capabilities_cache = {"features": {"scene_delta": False}}
    ws_call = AsyncMock()
    monkeypatch.setattr(client._ws, "call", ws_call)

    resp = await client.get_scene_delta(10)

    assert resp["ok"] is False
    assert resp.get("method_not_found") is True
    ws_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_connected_probes_capabilities(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(client._ws, "connect", AsyncMock(return_value=None))
    probe_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(client, "_probe_server_capabilities_once", probe_mock)

    await client.ensure_connected(timeout_s=0.5)

    probe_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_blender_headless_raises_clear_error_for_missing_executable(tmp_path):
    client = VBFClient(
        blender_path=str(tmp_path / "missing-blender.exe"),
        start_script_path=str(Path(__file__).resolve()),
    )

    with pytest.raises(FileNotFoundError, match="Set BLENDER_PATH or pass --blender-path"):
        await client._start_blender_headless()


@pytest.mark.asyncio
async def test_probe_logs_capabilities_once(monkeypatch, capsys):
    client = VBFClient()
    ws_call = AsyncMock(
        return_value={
            "ok": True,
            "data": {
                "features": {
                    "capabilities_rpc": True,
                    "scene_snapshot": True,
                    "scene_delta": False,
                    "rollback_to_step": True,
                }
            },
        }
    )
    monkeypatch.setattr(client._ws, "call", ws_call)

    await client._probe_server_capabilities_once()
    await client._probe_server_capabilities_once()

    out = capsys.readouterr().out
    assert "Server capabilities:" in out
    assert out.count("Server capabilities:") == 1


@pytest.mark.asyncio
async def test_probe_logs_compatibility_fallback_once(monkeypatch, capsys):
    client = VBFClient()
    ws_call = AsyncMock(side_effect=JsonRpcError(code=-32601, message="Method not found"))
    monkeypatch.setattr(client._ws, "call", ws_call)

    await client._probe_server_capabilities_once()
    await client._probe_server_capabilities_once()

    out = capsys.readouterr().out
    assert "capabilities RPC unavailable" in out
    assert out.count("capabilities RPC unavailable") == 1
