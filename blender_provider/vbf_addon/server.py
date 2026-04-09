from __future__ import annotations

import asyncio
import inspect
import json
import queue
import threading
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

import bpy # type: ignore

from .skills import SKILL_REGISTRY

try:
    import websockets # type: ignore
except Exception: # pragma: no cover
    websockets = None

HOST_ENV = "VBF_WS_HOST"
PORT_ENV = "VBF_WS_PORT"

def _extract_skill_schema(fn, compact=False) -> dict:
    """Extract skill schema with optional compact mode to save bandwidth."""
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or ""
    args = {}
    for param_name, param in sig.parameters.items():
        args[param_name] = {
            "required": param.default is inspect.Parameter.empty,
            "default": None if param.default is inspect.Parameter.empty else repr(param.default),
            "type": str(param.annotation) if param.annotation is not inspect.Parameter.empty else "any",
        }
    first_line = doc.split("\n")[0].strip() if doc else ""

    if compact:
        return {"description": first_line, "args": args}

    return {"description": first_line, "args": args, "doc": doc}

@dataclass
class _Job:
    req: Dict[str, Any]
    fut: asyncio.Future
    ws_id: str

class VBFWebSocketServer:
    def __init__(self, host: str, port: int, poll_interval_s: float = 0.1):
        self.host = host
        self.port = port
        self.poll_interval_s = poll_interval_s

        self._incoming: "queue.Queue[_Job]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Any = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        if websockets is None:
            raise ImportError("Addon requires Python package `websockets` in Blender's Python environment.")

        self._running = True
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Best-effort stop.
        Notes:
        - Websockets server runs in its own asyncio loop/thread.
        - We stop the loop, which stops accepting new connections.
        """
        if not self._running:
            return
        self._running = False
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
        self._loop = None
        self._server = None

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)

        async def handler(websocket):
            ws_id = str(id(websocket))
            async for message in websocket:
                try:
                    req = json.loads(message)
                except Exception:
                    continue

                req_id = req.get("id")
                method = req.get("method")
                params = req.get("params") or {}

                if method == "vbf.list_skills":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"ok": True, "data": {"skills": sorted(list(SKILL_REGISTRY.keys()))}},
                    }
                    await websocket.send(json.dumps(resp))
                    continue

                if method == "vbf.describe_skills":
                    skill_names = params.get("skill_names") if isinstance(params, dict) else None
                    registry = SKILL_REGISTRY
                    if skill_names and isinstance(skill_names, list):
                        registry = {k: v for k, v in SKILL_REGISTRY.items() if k in skill_names}
                    schemas = {name: _extract_skill_schema(fn) for name, fn in registry.items()}
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"ok": True, "data": {"skills": schemas}},
                    }
                    await websocket.send(json.dumps(resp))
                    continue

                if method != "vbf.execute_skill":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }
                    await websocket.send(json.dumps(resp))
                    continue

                if not isinstance(params, dict):
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "Invalid params"},
                    }
                    await websocket.send(json.dumps(resp))
                    continue

                fut: asyncio.Future = loop.create_future()
                self._incoming.put(_Job(req=req, fut=fut, ws_id=ws_id))
                try:
                    result_payload = await fut
                except Exception:
                    result_payload = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32000, "message": "Internal server error"},
                    }
                await websocket.send(json.dumps(result_payload))

        async def main() -> None:
            self._server = await websockets.serve(handler, self.host, self.port)

        loop.run_until_complete(main())
        loop.run_forever()

    def poll_once_and_execute(self) -> None:
        if not self._running or not self._loop:
            return
        loop = self._loop

        while True:
            try:
                job = self._incoming.get_nowait()
            except queue.Empty:
                break

            req_id = job.req.get("id")
            try:
                params = job.req.get("params") or {}
                skill = params.get("skill")
                args = params.get("args") or {}

                if not isinstance(args, dict):
                    raise ValueError("params.args must be an object")
                if not skill or not isinstance(skill, str):
                    raise ValueError("params.skill must be a string")

                fn = SKILL_REGISTRY.get(skill)
                if not fn:
                    raise ValueError(f"Unknown skill: {skill}")

                data = fn(**args)
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"ok": True, "data": data}}
            except ValueError as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": f"Parameter error: {str(e)}",
                        "data": {"traceback": traceback.format_exc()},
                    },
                }
            except Exception as e:
                # Capture Blender context for better LLM recovery
                context_snapshot = {
                    "active_object": getattr(bpy.context, "active_object", None).name if hasattr(bpy.context, "active_object") and bpy.context.active_object else None,
                    "selected_objects": [obj.name for obj in bpy.context.selected_objects] if hasattr(bpy.context, "selected_objects") else [],
                    "mode": getattr(bpy.context, "mode", "UNKNOWN"),
                    "current_frame": getattr(bpy.context.scene, "frame_current", 0) if hasattr(bpy.context, "scene") else 0,
                }
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": f"Skill execution failed: {str(e)}",
                        "data": {
                            "traceback": traceback.format_exc(),
                            "blender_context": context_snapshot,
                        },
                    },
                }

            try:
                if not job.fut.done():
                    loop.call_soon_threadsafe(job.fut.set_result, resp)
            except Exception:
                pass

_SERVER: Optional[VBFWebSocketServer] = None

def get_server() -> VBFWebSocketServer:
    global _SERVER
    if _SERVER is None:
        host = "127.0.0.1"
        port = 8006
        try:
            import os
            port = int(os.getenv(PORT_ENV, "8006"))
            host = os.getenv(HOST_ENV, host)
        except Exception:
            pass

        # Prefer addon preferences if available (UI configurable).
        try:
            addon_key = __package__ or "vbf_addon"
            prefs = bpy.context.preferences.addons[addon_key].preferences
            host = getattr(prefs, "host", host) or host
            port = int(getattr(prefs, "port", port) or port)
        except Exception:
            pass

        _SERVER = VBFWebSocketServer(host=host, port=port)
    return _SERVER

class VBF_OT_serve(bpy.types.Operator):
    bl_idname = "vbf.serve"
    bl_label = "VBF Serve (WebSocket JSON-RPC)"

    _timer = None

    def execute(self, context):
        server = get_server()
        if not server.running:
            server.start()

        wm = getattr(context, "window_manager", None)
        if wm:
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            return {"RUNNING_MODAL"}

        bpy.app.timers.register(_headless_poll, first_interval=0.1)
        return {"FINISHED"}

    def modal(self, context, event):
        if event.type == "TIMER":
            get_server().poll_once_and_execute()
        return {"PASS_THROUGH"}

    def cancel(self, context):
        try:
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
        except Exception:
            pass

def _headless_poll():
    try:
        get_server().poll_once_and_execute()
    except Exception:
        pass
    return 0.1

def start_vbf_ws_server() -> None:
    server = get_server()
    if not server.running:
        server.start()
    bpy.app.timers.register(_headless_poll, first_interval=0.1)

class VBF_OT_stop(bpy.types.Operator):
    bl_idname = "vbf.stop"
    bl_label = "VBF Stop (WebSocket JSON-RPC)"

    def execute(self, context):
        try:
            get_server().stop()
        except Exception:
            pass
        return {"FINISHED"}
