from __future__ import annotations

import asyncio
import copy
import inspect
import json
import queue
import socket
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import bpy # type: ignore

try:
    from .skills import SKILL_REGISTRY
except Exception:
    # Fallback for script-style loading without package context.
    from skills import SKILL_REGISTRY  # type: ignore

try:
    import websockets # type: ignore
except Exception: # pragma: no cover
    websockets = None

HOST_ENV = "VBF_WS_HOST"
PORT_ENV = "VBF_WS_PORT"


def _capture_object_state(obj: Any, name_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Capture LIGHT-level geometry state for a single Blender object."""
    if obj is None:
        return None
    try:
        name = name_hint or getattr(obj, "name", None)
        if not name:
            return None
        obj_type = getattr(obj, "type", "UNKNOWN")
        obj_data = {
            "name": name,
            "type": obj_type,
            "location": list(getattr(obj, "location", [0.0, 0.0, 0.0])),
            "dimensions": list(getattr(obj, "dimensions", [0.0, 0.0, 0.0])),
        }

        if obj_type == "MESH" and hasattr(obj, "data") and hasattr(obj.data, "vertices"):
            mesh = obj.data
            obj_data["vertices"] = len(mesh.vertices)
            obj_data["polygons"] = len(mesh.polygons)
            obj_data["edges"] = len(mesh.edges)
        else:
            obj_data["vertices"] = 0
            obj_data["polygons"] = 0
            obj_data["edges"] = 0

        if hasattr(obj, "material_slots"):
            obj_data["materials"] = len(obj.material_slots)
        else:
            obj_data["materials"] = 0
        return obj_data
    except Exception:
        return None


def _capture_target_state(target_names: list) -> Dict[str, Any]:
    """
    Capture LIGHT-level geometry state for specified objects.

    This is called automatically after each skill execution to provide
    post-state data for closed-loop feedback validation.

    Args:
        target_names: List of object names to capture. If empty, captures nothing.

    Returns:
        Dict mapping object name to geometry data dict.
    """
    if not target_names:
        return {}

    result = {}
    for name in target_names:
        try:
            obj = bpy.data.objects.get(name)
            obj_data = _capture_object_state(obj, name_hint=name)
            if obj_data:
                result[name] = obj_data

        except Exception:
            # Silently skip objects we can't capture
            pass

    return result


def _capture_scene_snapshot() -> Dict[str, Dict[str, Any]]:
    """Capture a LIGHT-level snapshot for all objects in the current scene."""
    snapshot: Dict[str, Dict[str, Any]] = {}
    for obj in bpy.data.objects:
        obj_state = _capture_object_state(obj, name_hint=getattr(obj, "name", None))
        if obj_state and "name" in obj_state:
            snapshot[obj_state["name"]] = obj_state
    return snapshot


def _extract_target_objects_from_args(args: Dict, data: Any) -> List[str]:
    """Extract target object names from skill arguments.

    Checks common parameter names and result data to find object names
    that should have post-state captured.
    """
    targets = []

    # Check args for common object name parameters
    for key in ["name", "object_name", "target", "object"]:
        val = args.get(key)
        if val and isinstance(val, str):
            targets.append(val)

    # Check result data for object_name
    if isinstance(data, dict):
        obj_name = data.get("object_name")
        if obj_name and isinstance(obj_name, str) and obj_name not in targets:
            targets.append(obj_name)

    # Deduplicate
    seen = set()
    unique = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique



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

        # Track undo stack depth for each step_id to support physical rollbacks
        # Mapping: step_id -> undo_stack_index
        self._step_undo_map: Dict[str, int] = {}
        self._current_undo_count = 0

        # Realtime scene delta cache (depsgraph-driven).
        self._scene_lock = threading.Lock()
        self._scene_seq = 0
        self._scene_state: Dict[str, Dict[str, Any]] = {}
        self._pending_scene_delta: Dict[str, Optional[Dict[str, Any]]] = {}
        self._scene_events: List[Dict[str, Any]] = []
        self._scene_events_max = 500
        self._scene_dropped = False
        self._delta_flush_interval_s = 0.1
        self._last_flush_monotonic = time.monotonic()
        self._depsgraph_pre_count = 0
        self._depsgraph_post_count = 0

        self._depsgraph_pre_handler = None
        self._depsgraph_post_handler = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        if websockets is None:
            raise ImportError("Addon requires Python package `websockets` in Blender's Python environment.")

        self._initialize_scene_cache()
        self._register_depsgraph_handlers()

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
        self._unregister_depsgraph_handlers()
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

                if method == "vbf.get_capabilities":
                    data = self._get_capabilities()
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"ok": True, "data": data},
                    }
                    await websocket.send(json.dumps(resp))
                    continue

                if method == "vbf.rollback_to_step":
                    step_id = params.get("step_id") if isinstance(params, dict) else None
                    if not step_id or not isinstance(step_id, str):
                        resp = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": "Invalid params: step_id must be a string"},
                        }
                        await websocket.send(json.dumps(resp))
                        continue

                    # Rollback must be executed on the main thread via the job queue
                    fut: asyncio.Future = loop.create_future()
                    # Special job format for rollback
                    self._incoming.put(_Job(req={"method": "vbf.rollback_to_step", "params": {"step_id": step_id}, "id": req_id}, fut=fut, ws_id=ws_id))
                    try:
                        result_payload = await fut
                    except Exception:
                        result_payload = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32000, "message": "Internal server error during rollback"},
                        }
                    await websocket.send(json.dumps(result_payload))
                    continue

                if method == "vbf.get_scene_delta":
                    if not isinstance(params, dict):
                        resp = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": "Invalid params"},
                        }
                        await websocket.send(json.dumps(resp))
                        continue
                    since_seq = params.get("since_seq", 0)
                    try:
                        since_seq = int(since_seq)
                    except Exception:
                        since_seq = 0
                    data = self._get_scene_delta(since_seq)
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"ok": True, "data": data},
                    }
                    await websocket.send(json.dumps(resp))
                    continue

                if method == "vbf.get_scene_snapshot":
                    data = self._get_scene_snapshot()
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"ok": True, "data": data},
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
            method = job.req.get("method", "vbf.execute_skill") # Default to execute_skill
            try:
                params = job.req.get("params") or {}

                if method == "vbf.rollback_to_step":
                    step_id = params.get("step_id")
                    if not step_id or step_id not in self._step_undo_map:
                        raise ValueError(f"Unknown or missing step_id for rollback: {step_id}")

                    # Calculate how many undos are needed
                    target_undo_count = self._step_undo_map[step_id]
                    current_undo_count = self._current_undo_count
                    undo_diff = current_undo_count - target_undo_count

                    if undo_diff < 0:
                        raise ValueError(f"Cannot rollback forward: target {target_undo_count}, current {current_undo_count}")

                    # Execute undos
                    for _ in range(undo_diff):
                        bpy.ops.ed.undo()

                    self._current_undo_count = target_undo_count

                    # Cleanup the map: remove all steps that happened after this one
                    # Since steps are added sequentially, we can just filter by count
                    self._step_undo_map = {sid: cnt for sid, cnt in self._step_undo_map.items() if cnt <= target_undo_count}

                    resp = {"jsonrpc": "2.0", "id": req_id, "result": {"ok": True, "data": {"undone_steps": undo_diff}}}
                else:
                    # Normal execute_skill path
                    skill = params.get("skill")
                    args = params.get("args") or {}

                    if not isinstance(args, dict):
                        raise ValueError("params.args must be an object")
                    if not skill or not isinstance(skill, str):
                        raise ValueError("params.skill must be a string")

                    fn = SKILL_REGISTRY.get(skill)
                    if not fn:
                        raise ValueError(f"Unknown skill: {skill}")

                    # Record undo state before executing.
                    # We use a simple counter of successful VBF operations that typically trigger undo.
                    # Note: In a real scenario, we'd check if the op actually created an undo step.
                    # For now, we assume each successful skill execution adds one undo step.
                    # We can't easily get the global undo index from bpy, so we track relative to server start.

                    # We use the step_id if it's passed in params, otherwise we can't track it.
                    # The client should pass 'step_id' in params for tracking.
                    step_id = params.get("step_id")
                    if step_id:
                        self._step_undo_map[step_id] = self._current_undo_count

                    data = fn(**args)

                    # If successful, increment our internal undo tracker
                    if step_id:
                        self._current_undo_count += 1

                    # Normalize skill result payload to dict for downstream feedback fields.
                    if not isinstance(data, dict):
                        data = {"value": data}

                    # Include executed skill name for feedback/debug prompts.
                    data.setdefault("_skill", skill)

                    # Auto-capture post-state for closed-loop feedback.
                    target_objects = _extract_target_objects_from_args(args, data)
                    if target_objects:
                        post_state = _capture_target_state(target_objects)
                        if post_state:
                            data["_post_state"] = post_state

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

    def _initialize_scene_cache(self) -> None:
        """Initialize full scene cache used by delta/snapshot RPC."""
        with self._scene_lock:
            self._scene_state = _capture_scene_snapshot()
            self._scene_seq = 0
            self._pending_scene_delta.clear()
            self._scene_events.clear()
            self._scene_dropped = False
            self._last_flush_monotonic = time.monotonic()

    def _register_depsgraph_handlers(self) -> None:
        """Register depsgraph handlers used for realtime delta collection."""
        self._unregister_depsgraph_handlers()

        def _on_depsgraph_update_pre(scene, depsgraph):  # pragma: no cover - Blender runtime callback
            try:
                self._depsgraph_pre_count += 1
            except Exception:
                pass

        def _on_depsgraph_update_post(scene, depsgraph):  # pragma: no cover - Blender runtime callback
            try:
                self._depsgraph_post_count += 1
                self._collect_depsgraph_updates(depsgraph)
            except Exception:
                pass

        self._depsgraph_pre_handler = _on_depsgraph_update_pre
        self._depsgraph_post_handler = _on_depsgraph_update_post
        try:
            bpy.app.handlers.depsgraph_update_pre.append(self._depsgraph_pre_handler)
        except Exception:
            self._depsgraph_pre_handler = None
        try:
            bpy.app.handlers.depsgraph_update_post.append(self._depsgraph_post_handler)
        except Exception:
            self._depsgraph_post_handler = None

    def _unregister_depsgraph_handlers(self) -> None:
        """Unregister depsgraph handlers if they were registered."""
        pre = self._depsgraph_pre_handler
        post = self._depsgraph_post_handler
        if pre:
            try:
                if pre in bpy.app.handlers.depsgraph_update_pre:
                    bpy.app.handlers.depsgraph_update_pre.remove(pre)
            except Exception:
                pass
        if post:
            try:
                if post in bpy.app.handlers.depsgraph_update_post:
                    bpy.app.handlers.depsgraph_update_post.remove(post)
            except Exception:
                pass
        self._depsgraph_pre_handler = None
        self._depsgraph_post_handler = None

    def _collect_depsgraph_updates(self, depsgraph: Any) -> None:
        """Collect object updates from depsgraph into a throttled delta buffer."""
        updated_any = False
        with self._scene_lock:
            for update in getattr(depsgraph, "updates", []):
                id_block = getattr(update, "id", None)
                if not isinstance(id_block, bpy.types.Object):
                    continue
                obj_name = getattr(id_block, "name", None)
                if not obj_name:
                    continue
                obj = bpy.data.objects.get(obj_name)
                if obj is None:
                    self._pending_scene_delta[obj_name] = None
                    updated_any = True
                    continue
                try:
                    eval_obj = obj.evaluated_get(depsgraph)
                except Exception:
                    eval_obj = obj
                state = _capture_object_state(eval_obj, name_hint=obj_name)
                if state:
                    self._pending_scene_delta[obj_name] = state
                    updated_any = True

            now = time.monotonic()
            if updated_any and (now - self._last_flush_monotonic >= self._delta_flush_interval_s):
                self._flush_pending_scene_delta_locked()

    def _flush_pending_scene_delta_locked(self) -> None:
        if not self._pending_scene_delta:
            self._last_flush_monotonic = time.monotonic()
            return

        deltas: Dict[str, Any] = {}
        for obj_name, state in self._pending_scene_delta.items():
            if state is None:
                self._scene_state.pop(obj_name, None)
                deltas[obj_name] = {"deleted": True}
            else:
                self._scene_state[obj_name] = state
                deltas[obj_name] = state

        self._pending_scene_delta.clear()
        self._scene_seq += 1
        self._scene_events.append({"seq": self._scene_seq, "deltas": deltas})
        if len(self._scene_events) > self._scene_events_max:
            overflow = len(self._scene_events) - self._scene_events_max
            del self._scene_events[:overflow]
            self._scene_dropped = True
        self._last_flush_monotonic = time.monotonic()

    def _get_scene_delta(self, since_seq: int) -> Dict[str, Any]:
        with self._scene_lock:
            if self._pending_scene_delta:
                self._flush_pending_scene_delta_locked()

            latest_seq = self._scene_seq
            events = self._scene_events
            oldest_seq = events[0]["seq"] if events else latest_seq

            dropped = self._scene_dropped and since_seq < oldest_seq
            merged: Dict[str, Any] = {}
            for evt in events:
                if evt["seq"] > since_seq:
                    merged.update(evt["deltas"])

            # Once caller observed latest watermark, clear dropped flag.
            if since_seq >= latest_seq:
                self._scene_dropped = False

            return {
                "latest_seq": latest_seq,
                "deltas": copy.deepcopy(merged),
                "dropped": bool(dropped),
                "flush_interval_ms": int(self._delta_flush_interval_s * 1000),
            }

    def _get_scene_snapshot(self) -> Dict[str, Any]:
        with self._scene_lock:
            if self._pending_scene_delta:
                self._flush_pending_scene_delta_locked()
            return {
                "seq": self._scene_seq,
                "objects": copy.deepcopy(self._scene_state),
            }

    def _get_capabilities(self) -> Dict[str, Any]:
        """Return server RPC capabilities for client-side feature negotiation."""
        return {
            "server": "vbf_addon",
            "rpc_version": "1.0",
            "addon_version": "0.1.0",
            "features": {
                "capabilities_rpc": True,
                "list_skills": True,
                "describe_skills": True,
                "execute_skill": True,
                "rollback_to_step": True,
                "scene_delta": True,
                "scene_snapshot": True,
                "closed_loop_events": True,
            },
            "limits": {
                "scene_events_max": int(self._scene_events_max),
                "delta_flush_interval_ms": int(self._delta_flush_interval_s * 1000),
            },
            "runtime": {
                "depsgraph_handlers_registered": bool(self._depsgraph_pre_handler and self._depsgraph_post_handler),
            },
            "methods": [
                "vbf.list_skills",
                "vbf.describe_skills",
                "vbf.get_capabilities",
                "vbf.get_scene_delta",
                "vbf.get_scene_snapshot",
                "vbf.rollback_to_step",
                "vbf.execute_skill",
            ],
        }

_SERVER: Optional[VBFWebSocketServer] = None
_LAST_SELF_CHECK: Optional[Dict[str, Any]] = None

def _read_bind_from_preferences(default_host: str, default_port: int) -> tuple[str, int]:
    """Read bind host/port from addon preferences with safe defaults."""
    host = default_host
    port = default_port
    try:
        addon_key = __package__ or "vbf_addon"
        addon_entry = bpy.context.preferences.addons.get(addon_key)
        if addon_entry and getattr(addon_entry, "preferences", None):
            prefs = addon_entry.preferences
            host = getattr(prefs, "host", host) or host
            port = int(getattr(prefs, "port", port) or port)
    except Exception:
        pass
    return host, port

def _sync_server_bind_from_preferences(server: VBFWebSocketServer) -> bool:
    """Sync existing server object's bind fields from UI preferences."""
    host, port = _read_bind_from_preferences(server.host, server.port)
    changed = (server.host != host) or (int(server.port) != int(port))
    if changed:
        server.host = host
        server.port = int(port)
    return changed

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
        host, port = _read_bind_from_preferences(host, port)

        _SERVER = VBFWebSocketServer(host=host, port=port)
    return _SERVER

def _normalize_probe_host(host: str) -> str:
    """Normalize bind host to a loopback address suitable for local probing."""
    if not host:
        return "127.0.0.1"
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host

def _tcp_probe(host: str, port: int, timeout_s: float = 1.0) -> tuple[bool, str]:
    probe_host = _normalize_probe_host(host)
    try:
        with socket.create_connection((probe_host, int(port)), timeout=timeout_s):
            return True, f"TCP reachable at {probe_host}:{port}"
    except Exception as e:
        return False, f"TCP probe failed at {probe_host}:{port}: {e}"

def run_self_check() -> Dict[str, Any]:
    """Run one-click runtime self-check for addon status and local connectivity."""
    global _LAST_SELF_CHECK

    server = get_server()
    checks: List[Dict[str, Any]] = []

    checks.append({
        "name": "server_running",
        "ok": bool(server.running),
        "message": "Server is running" if server.running else "Server is not running",
    })

    tcp_ok, tcp_message = _tcp_probe(server.host, server.port)
    checks.append({
        "name": "tcp_reachable",
        "ok": bool(tcp_ok),
        "message": tcp_message,
    })

    skill_count = len(SKILL_REGISTRY)
    checks.append({
        "name": "skill_registry_loaded",
        "ok": skill_count > 0,
        "message": f"Skill registry size: {skill_count}",
    })

    capabilities: Dict[str, Any] = {}
    try:
        capabilities = server._get_capabilities() if hasattr(server, "_get_capabilities") else {}
    except Exception:
        capabilities = {}
    features = capabilities.get("features", {}) if isinstance(capabilities, dict) else {}
    caps_ok = isinstance(features, dict) and bool(features)
    checks.append({
        "name": "capabilities_available",
        "ok": caps_ok,
        "message": "Capabilities metadata available" if caps_ok else "Capabilities metadata unavailable",
    })

    all_ok = all(check.get("ok") for check in checks)
    summary = (
        f"running={'yes' if server.running else 'no'}, "
        f"tcp={'yes' if tcp_ok else 'no'}, "
        f"skills={skill_count}"
    )
    result = {
        "ok": all_ok,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "bind": f"{server.host}:{server.port}",
        "summary": summary,
        "checks": checks,
    }
    _LAST_SELF_CHECK = result
    return result

def get_last_self_check() -> Optional[Dict[str, Any]]:
    return _LAST_SELF_CHECK

class VBF_OT_serve(bpy.types.Operator):
    bl_idname = "vbf.serve"
    bl_label = "VBF Serve (WebSocket JSON-RPC)"

    _timer = None

    def execute(self, context):
        server = get_server()
        bind_changed = _sync_server_bind_from_preferences(server)

        # If bind changed while running, restart server so new address takes effect.
        if bind_changed and server.running:
            server.stop()

        if not server.running:
            server.start()
            if bind_changed:
                self.report({"INFO"}, f"VBF bind updated to {server.host}:{server.port}")

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
    _sync_server_bind_from_preferences(server)
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

class VBF_OT_self_check(bpy.types.Operator):
    bl_idname = "vbf.self_check"
    bl_label = "VBF Self Check"
    bl_description = "Run one-click connectivity and runtime self-check"

    def execute(self, context):
        result = run_self_check()
        if result.get("ok"):
            self.report({"INFO"}, f"[VBF] Self-check OK: {result.get('summary', '')}")
        else:
            self.report({"WARNING"}, f"[VBF] Self-check FAILED: {result.get('summary', '')}")
        return {"FINISHED"}
