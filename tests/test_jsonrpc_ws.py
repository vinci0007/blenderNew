import pytest

from vbf.transport.jsonrpc_ws import JsonRpcWebSocketClient


class _SilentWebSocket:
    closed = False

    def __init__(self):
        self.sent = []
        self.close_called = False

    async def send(self, payload):
        self.sent.append(payload)

    async def close(self):
        self.close_called = True
        self.closed = True


@pytest.mark.asyncio
async def test_jsonrpc_call_timeout_drops_connection():
    client = JsonRpcWebSocketClient("ws://unused")
    ws = _SilentWebSocket()
    client._ws = ws

    with pytest.raises(TimeoutError, match="JSON-RPC call timed out"):
        await client.call("vbf.execute_skill", {"skill": "noop"}, timeout_s=0.01)

    assert ws.close_called is True
    assert client._ws is None
    assert client._pending == {}
