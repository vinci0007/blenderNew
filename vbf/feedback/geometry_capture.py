"""Incremental scene capture with geometry awareness for closed-loop feedback.

This module provides enhanced scene state capture with multiple capture levels,
delta computation, and caching for efficient closed-loop control.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import time

class CaptureLevel(Enum):
    """Capture detail levels for scene state.

    - LIGHT: Minimal overhead, basic object info
    - GEOMETRY: + vertex/poly/edge counts, materials
    - TOPOLOGY: + topological analysis (ngons, face types)
    - FULL: Everything including modifiers, constraints, UV
    """
    LIGHT = "light"       # ~5-20ms per object
    GEOMETRY = "geometry" # ~20-50ms per object
    TOPOLOGY = "topology" # ~50-150ms per object
    FULL = "full"         # ~100-300ms per object


@dataclass
class ObjectGeometry:
    """Complete geometry data for an object."""
    name: str
    obj_type: str
    location: List[float]
    dimensions: List[float]

    # GEOMETRY level
    vertices: int = 0
    polygons: int = 0
    edges: int = 0
    materials: int = 0

    # Metadata
    _captured_at: float = field(default_factory=time.time)
    _cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.obj_type,
            "location": self.location,
            "dimensions": self.dimensions,
            "vertices": self.vertices,
            "polygons": self.polygons,
            "edges": self.edges,
            "materials": self.materials,
        }


@dataclass
class GeometryDelta:
    """Delta between two scene states - what changed."""
    before: Dict[str, ObjectGeometry]
    after: Dict[str, ObjectGeometry]
    added: Set[str] = field(default_factory=set)
    removed: Set[str] = field(default_factory=set)
    modified: Set[str] = field(default_factory=set)

    @classmethod
    def diff(cls, before: Dict[str, ObjectGeometry],
             after: Dict[str, ObjectGeometry]) -> "GeometryDelta":
        """Calculate delta between two object sets."""
        before_names = set(before.keys())
        after_names = set(after.keys())

        added = after_names - before_names
        removed = before_names - after_names

        modified = set()
        for name in before_names & after_names:
            b = before[name]
            a = after[name]
            # Check if any meaningful property changed
            if (b.vertices != a.vertices or
                b.polygons != a.polygons or
                b.edges != a.edges or
                b.materials != a.materials or
                abs(b.location[0] - a.location[0]) > 0.0001 or
                abs(b.dimensions[0] - a.dimensions[0]) > 0.0001):
                modified.add(name)

        return cls(
            before=before,
            after=after,
            added=added,
            removed=removed,
            modified=modified
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return {
            "added": list(self.added),
            "removed": list(self.removed),
            "modified": list(self.modified),
            "added_count": len(self.added),
            "removed_count": len(self.removed),
            "modified_count": len(self.modified),
        }

    def __repr__(self) -> str:
        return f"GeometryDelta(+{len(self.added)}, -{len(self.removed)}, ~{len(self.modified)})"


class IncrementalSceneCapture:
    """Capture Blender scene incrementally with caching.

    Purpose: Support closed-loop feedback by efficiently tracking
    which objects change after each skill execution.
    """

    def __init__(self, client):
        """Initialize with VBFClient instance."""
        self.client = client
        self._cache: Dict[str, ObjectGeometry] = {}
        self._full_sync_count: int = 0
        self._capture_stats = {"total_captures": 0, "cache_hits": 0}
        self._event_seq: int = 0
        self._event_stream_available: Optional[bool] = None

    async def capture_objects(self, names: List[str],
                              level: CaptureLevel = CaptureLevel.LIGHT,
                              use_cache: bool = True) -> Dict[str, ObjectGeometry]:
        """Capture specified objects at given detail level.

        Args:
            names: List of object names to capture
            level: Detail level (LIGHT, GEOMETRY, etc.)
            use_cache: Whether to use cached data if available

        Returns:
            Dict mapping object name to ObjectGeometry
        """
        results = {}
        names_to_fetch = []
        event_synced = False

        # Check cache first
        if use_cache:
            event_synced = await self.sync_from_events()
            for name in names:
                if name in self._cache:
                    results[name] = self._cache[name]
                    self._capture_stats["cache_hits"] += 1
                else:
                    names_to_fetch.append(name)

            # Event stream may start from deltas only; if requested names are missing,
            # request a full snapshot once before falling back to py_get.
            if names_to_fetch and self._event_stream_available is not False and not event_synced:
                await self.sync_from_events(force_snapshot=True)
                names_to_fetch = []
                for name in names:
                    if name in self._cache:
                        results[name] = self._cache[name]
                        self._capture_stats["cache_hits"] += 1
                    else:
                        names_to_fetch.append(name)
        else:
            names_to_fetch = names

        # Fetch uncached objects
        for name in names_to_fetch:
            try:
                obj_data = await self._capture_single_object(name, level)
                if obj_data:
                    results[name] = obj_data
                    self._cache[name] = obj_data
            except Exception as e:
                if self._is_missing_object_error(e):
                    self._cache.pop(name, None)
                    continue
                # Log but continue - partial capture is better than none
                print(f"[Capture] Failed to capture {name}: {e}")

        self._capture_stats["total_captures"] += len(names_to_fetch)
        return results

    @staticmethod
    def _is_missing_object_error(error: Exception) -> bool:
        text = str(error).lower()
        return (
            "bpy_prop_collection[key]" in text
            and "not found" in text
        ) or (
            "object not found" in text
        )

    async def _capture_single_object(self, name: str,
                                   level: CaptureLevel) -> Optional[ObjectGeometry]:
        """Capture a single object's data via py_get RPC calls."""

        # Base path for object access: bpy.data.objects[name]
        base_path = [{"attr": "data"}, {"attr": "objects"}, {"key": name}]

        # Get basic info (LIGHT level always collected)
        type_resp = await self._py_get(base_path + [{"attr": "type"}])
        if not type_resp:
            return None

        obj_type = type_resp

        loc_resp = await self._py_get(base_path + [{"attr": "location"}])
        location = list(loc_resp) if loc_resp else [0.0, 0.0, 0.0]

        dim_resp = await self._py_get(base_path + [{"attr": "dimensions"}])
        dimensions = list(dim_resp) if dim_resp else [0.0, 0.0, 0.0]

        obj = ObjectGeometry(
            name=name,
            obj_type=obj_type,
            location=location,
            dimensions=dimensions
        )

        # GEOMETRY level and above
        if level in (CaptureLevel.GEOMETRY, CaptureLevel.TOPOLOGY, CaptureLevel.FULL):
            # Get mesh data if object is a mesh
            if obj_type == "MESH":
                mesh_path = base_path + [{"attr": "data"}]

                # Vertices count
                verts_resp = await self._py_get(mesh_path + [{"attr": "vertices"}, {"len": True}])
                obj.vertices = verts_resp or 0

                # Polygons count
                poly_resp = await self._py_get(mesh_path + [{"attr": "polygons"}, {"len": True}])
                obj.polygons = poly_resp or 0

                # Edges count
                edge_resp = await self._py_get(mesh_path + [{"attr": "edges"}, {"len": True}])
                obj.edges = edge_resp or 0

                # Material slots
            mat_resp = await self._py_get(base_path + [{"attr": "material_slots"}, {"len": True}])
            obj.materials = mat_resp or 0

        obj._captured_at = time.time()
        return obj

    async def _py_get(self, path_steps: List[Dict]) -> Any:
        """Helper to call py_get skill via RPC."""
        resp = await self.client.execute_skill("py_get", {"path_steps": path_steps})
        if resp.get("ok"):
            return resp.get("data", {}).get("value")
        return None

    async def sync_from_events(self, force_snapshot: bool = False) -> bool:
        """Sync local cache from depsgraph event stream if server supports it."""
        if self._event_stream_available is False and not force_snapshot:
            return False

        snapshot_ok = True
        if force_snapshot or self._event_seq == 0:
            snapshot_resp = await self._rpc_scene_snapshot()
            if snapshot_resp.get("method_not_found"):
                self._event_stream_available = False
                return False
            snapshot_ok = snapshot_resp.get("ok", False)
            if snapshot_ok:
                data = snapshot_resp.get("data", {})
                self._event_seq = int(data.get("seq", 0))
                self._load_snapshot(data.get("objects", {}))
                self._event_stream_available = True
            elif force_snapshot:
                return False

        delta_resp = await self._rpc_scene_delta(self._event_seq)
        if delta_resp.get("method_not_found"):
            self._event_stream_available = False
            return False
        if not delta_resp.get("ok"):
            return False

        data = delta_resp.get("data", {})
        latest_seq = int(data.get("latest_seq", self._event_seq))
        dropped = bool(data.get("dropped", False))

        if dropped:
            snapshot_resp = await self._rpc_scene_snapshot()
            if snapshot_resp.get("ok"):
                snap_data = snapshot_resp.get("data", {})
                self._event_seq = int(snap_data.get("seq", latest_seq))
                self._load_snapshot(snap_data.get("objects", {}))
                self._event_stream_available = True
                return True
            return False

        self._apply_deltas(data.get("deltas", {}))
        self._event_seq = latest_seq
        self._event_stream_available = True
        return True

    async def _rpc_scene_delta(self, since_seq: int) -> Dict[str, Any]:
        fn = getattr(self.client, "get_scene_delta", None)
        if not callable(fn):
            return {"ok": False, "method_not_found": True}
        try:
            return await fn(since_seq)
        except Exception:
            return {"ok": False}

    async def _rpc_scene_snapshot(self) -> Dict[str, Any]:
        fn = getattr(self.client, "get_scene_snapshot", None)
        if not callable(fn):
            return {"ok": False, "method_not_found": True}
        try:
            return await fn()
        except Exception:
            return {"ok": False}

    def _load_snapshot(self, objects: Dict[str, Any]) -> None:
        self._cache.clear()
        if not isinstance(objects, dict):
            return
        for name, state in objects.items():
            obj = self._object_from_payload(name, state)
            if obj:
                self._cache[name] = obj

    def _apply_deltas(self, deltas: Dict[str, Any]) -> None:
        if not isinstance(deltas, dict):
            return
        for name, delta in deltas.items():
            if not isinstance(name, str):
                continue
            if isinstance(delta, dict) and delta.get("deleted"):
                self._cache.pop(name, None)
                continue
            obj = self._object_from_payload(name, delta)
            if obj:
                self._cache[name] = obj

    def _object_from_payload(self, name: str, payload: Any) -> Optional[ObjectGeometry]:
        if not isinstance(payload, dict):
            return None
        location = payload.get("location", [0, 0, 0])
        dimensions = payload.get("dimensions", [0, 0, 0])
        if not isinstance(location, list) or len(location) < 3:
            location = [0, 0, 0]
        if not isinstance(dimensions, list) or len(dimensions) < 3:
            dimensions = [0, 0, 0]
        try:
            return ObjectGeometry(
                name=name,
                obj_type=str(payload.get("type", "UNKNOWN")),
                location=list(location[:3]),
                dimensions=list(dimensions[:3]),
                vertices=int(payload.get("vertices", 0) or 0),
                polygons=int(payload.get("polygons", 0) or 0),
                edges=int(payload.get("edges", 0) or 0),
                materials=int(payload.get("materials", 0) or 0),
                _cached=True,
            )
        except Exception:
            return None

    async def capture_delta(self, target_names: List[str],
                           level: CaptureLevel = CaptureLevel.GEOMETRY
                           ) -> GeometryDelta:
        """Capture before state, then return delta after skill execution.

        This is used by ClosedLoopControl to track changes.
        """
        # Return cached "before" state for these targets
        before = {name: self._cache.get(name)
                  for name in target_names if name in self._cache}

        # Capture current state as "after"
        after = await self.capture_objects(target_names, level, use_cache=False)

        return GeometryDelta.diff(before, after)

    def update_cache_from_result(self, post_state: Dict[str, Any]) -> None:
        """Update cache from skill execution result's _post_state.

        This integrates with server.py's automatic post-state capture.
        """
        for name, data in post_state.items():
            if isinstance(data, dict):
                self._cache[name] = ObjectGeometry(
                    name=name,
                    obj_type=data.get("type", "UNKNOWN"),
                    location=data.get("location", [0, 0, 0]),
                    dimensions=data.get("dimensions", [0, 0, 0]),
                    vertices=data.get("vertices", 0),
                    polygons=data.get("polygons", 0),
                    edges=data.get("edges", 0),
                    materials=data.get("materials", 0),
                    _cached=True
                )

    def get_cache_stats(self) -> Dict[str, int]:
        """Return capture statistics for debugging."""
        return {
            "cached_objects": len(self._cache),
            **self._capture_stats
        }

    def invalidate_cache(self, object_names: Optional[List[str]] = None) -> None:
        """Invalidate cache for specified objects, or all if None."""
        if object_names is None:
            self._cache.clear()
        else:
            for name in object_names:
                self._cache.pop(name, None)


# Validation result types for closed-loop control
@dataclass
class ValidationResult:
    """Result of validating a skill execution."""
    status: str  # "passed" | "failed" | "warning" | "skipped"
    skill: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def passed(cls, skill: str, message: str = "") -> "ValidationResult":
        return cls(status="passed", skill=skill, message=message)

    @classmethod
    def failed(cls, skill: str, message: str, details: Dict = None) -> "ValidationResult":
        return cls(status="failed", skill=skill, message=message,
                   details=details or {})

    @classmethod
    def warning(cls, skill: str, message: str, details: Dict = None) -> "ValidationResult":
        return cls(status="warning", skill=skill, message=message,
                   details=details or {})

    @classmethod
    def skipped(cls, skill: str, message: str = "", details: Dict = None) -> "ValidationResult":
        return cls(status="skipped", skill=skill, message=message,
                   details=details or {})


# Convenience exports
__all__ = [
    "CaptureLevel",
    "ObjectGeometry",
    "GeometryDelta",
    "IncrementalSceneCapture",
    "ValidationResult",
]
