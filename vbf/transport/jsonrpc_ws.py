import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import websockets


@dataclass
class JsonRpcError(Exception):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        if self.data:
            return f"JsonRpcError(code={self.code}, message={self.message}, data={self.data})"
        return f"JsonRpcError(code={self.code}, message={self.message})"


class JsonRpcWebSocketClient:
    """Minimal JSON-RPC 2.0 over WebSocket client with a single recv loop."""

    def __init__(self, uri: str):
        self._uri = uri
        self._ws = None
        self._recv_task: Optional[asyncio.Task] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._id_counter = 1
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not getattr(self._ws, "closed", False)

    async def connect(self) -> None:
        if self.is_connected:
            return
        self._ws = await websockets.connect(self._uri)
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def close(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
        self._recv_task = None
        if self._ws:
            await self._ws.close()
        self._ws = None

    async def _drop_connection_after_timeout(self, request_id: int) -> None:
        """Close the transport after a timed-out RPC to avoid late response reuse."""
        self._pending.pop(request_id, None)
        for pending_id, fut in list(self._pending.items()):
            if not fut.done():
                fut.set_exception(
                    TimeoutError(
                        "JSON-RPC connection reset after another request timed out"
                    )
                )
            self._pending.pop(pending_id, None)
        recv_task = self._recv_task
        self._recv_task = None
        if recv_task:
            recv_task.cancel()
        ws = self._ws
        self._ws = None
        if ws:
            try:
                await ws.close()
            except Exception:
                pass

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None, timeout_s: float = 60.0) -> Any:
        await self.connect()
        async with self._lock:
            request_id = self._id_counter
            self._id_counter += 1

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[request_id] = fut

        req: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        await self._ws.send(json.dumps(req))

        try:
            resp = await asyncio.wait_for(fut, timeout=timeout_s)
            return resp
        except TimeoutError:
            await self._drop_connection_after_timeout(request_id)
            raise TimeoutError(
                f"JSON-RPC call timed out: method={method} timeout={timeout_s:.1f}s"
            ) from None
        finally:
            self._pending.pop(request_id, None)

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        ws = self._ws
        try:
            async for msg in ws:
                try:
                    data = json.loads(msg)
                except Exception as e:  # pragma: no cover
                    continue

                request_id = data.get("id")
                fut = self._pending.get(request_id)
                if not fut:
                    continue

                if "error" in data:
                    err = data["error"] or {}
                    code = int(err.get("code", -32000))
                    message = str(err.get("message", "Unknown JSON-RPC error"))
                    err_data = err.get("data")
                    fut.set_exception(JsonRpcError(code=code, message=message, data=err_data))
                else:
                    fut.set_result(data.get("result"))
        except asyncio.CancelledError:
            pass
        except Exception:
            # Fail all pending calls.
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(ConnectionError("WebSocket recv loop crashed"))
            self._pending.clear()
