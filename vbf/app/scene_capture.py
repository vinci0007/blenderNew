from __future__ import annotations

from typing import Any, List, Optional

from ..core.scene_state import SceneState


async def capture_scene_state(client: Any) -> SceneState:
    """Capture current Blender scene state with snapshot-first fallback."""
    state = SceneState()

    async def _get_value(path_steps: list):
        resp = await client.execute_skill("py_get", {"path_steps": path_steps})
        if resp.get("ok"):
            return resp.get("data", {}).get("value")
        return None

    def _vec3(value: Any, default: Optional[List[float]] = None) -> List[float]:
        fallback = default or [0.0, 0.0, 0.0]
        if not isinstance(value, list) or len(value) < 3:
            return list(fallback)
        out: List[float] = []
        for idx in range(3):
            try:
                out.append(float(value[idx]))
            except Exception:
                out.append(float(fallback[idx]))
        return out

    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    async def _capture_scene_meta() -> None:
        state.scene_name = (
            await _get_value([{"attr": "context"}, {"attr": "scene"}, {"attr": "name"}])
            or "Scene"
        )
        state.frame_current = _to_int(
            await _get_value([{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_current"}]),
            1,
        )
        state.frame_start = _to_int(
            await _get_value([{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_start"}]),
            1,
        )
        state.frame_end = _to_int(
            await _get_value([{"attr": "context"}, {"attr": "scene"}, {"attr": "frame_end"}]),
            250,
        )

    try:
        snapshot_resp = await client.get_scene_snapshot()
        if snapshot_resp.get("ok"):
            data = snapshot_resp.get("data", {}) or {}
            objects = data.get("objects")
            if isinstance(objects, dict):
                await _capture_scene_meta()
                for obj_name, obj_state in objects.items():
                    if not isinstance(obj_name, str) or not isinstance(obj_state, dict):
                        continue
                    state.add_object(
                        name=obj_name,
                        obj_type=str(obj_state.get("type", "UNKNOWN")),
                        location=_vec3(obj_state.get("location")),
                        size=_vec3(obj_state.get("dimensions")),
                        vertices=_to_int(obj_state.get("vertices"), 0),
                        polygons=_to_int(obj_state.get("polygons"), 0),
                        edges=_to_int(obj_state.get("edges"), 0),
                        materials=_to_int(obj_state.get("materials"), 0),
                    )
                state.set_statistics(
                    object_count=len(state.get_objects()),
                    capture_source="scene_snapshot",
                    snapshot_seq=_to_int(data.get("seq"), 0),
                )
                state.finalize()
                return state
        elif not snapshot_resp.get("method_not_found"):
            state.add_warning(
                f"Scene snapshot unavailable ({snapshot_resp.get('error', 'unknown')}); fallback to py_get"
            )
    except Exception as e:
        state.add_warning(f"Scene snapshot failed: {e}")

    try:
        await _capture_scene_meta()

        object_names: List[str] = []

        names_resp = await client.execute_skill(
            "py_call",
            {
                "callable_path_steps": [{"attr": "data"}, {"attr": "objects"}, {"attr": "keys"}],
                "args": [],
                "kwargs": {},
            },
        )
        if names_resp.get("ok"):
            names_data = names_resp.get("data", {}) or {}
            maybe_names = names_data.get("result")
            if isinstance(maybe_names, list):
                object_names = [name for name in maybe_names if isinstance(name, str) and name]

        if not object_names:
            count = _to_int(
                await _get_value([{"attr": "data"}, {"attr": "objects"}, {"len": True}]),
                0,
            )
            for idx in range(max(count, 0)):
                obj_name = await _get_value(
                    [{"attr": "data"}, {"attr": "objects"}, {"index": idx}, {"attr": "name"}]
                )
                if isinstance(obj_name, str) and obj_name:
                    object_names.append(obj_name)

        seen = set()
        deduped_names: List[str] = []
        for name in object_names:
            if name not in seen:
                seen.add(name)
                deduped_names.append(name)

        for obj_name in deduped_names:
            obj_type = await _get_value([{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "type"}])
            location = await _get_value([{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "location"}])
            dimensions = await _get_value([{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "dimensions"}])
            vertices = await _get_value(
                [{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "data"}, {"attr": "vertices"}, {"len": True}]
            )
            polygons = await _get_value(
                [{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "data"}, {"attr": "polygons"}, {"len": True}]
            )
            edges = await _get_value(
                [{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "data"}, {"attr": "edges"}, {"len": True}]
            )
            materials = await _get_value(
                [{"attr": "data"}, {"attr": "objects"}, {"key": obj_name}, {"attr": "material_slots"}, {"len": True}]
            )
            state.add_object(
                name=obj_name,
                obj_type=str(obj_type or "UNKNOWN"),
                location=_vec3(location),
                size=_vec3(dimensions),
                vertices=_to_int(vertices, 0),
                polygons=_to_int(polygons, 0),
                edges=_to_int(edges, 0),
                materials=_to_int(materials, 0),
            )

        state.set_statistics(
            object_count=len(state.get_objects()),
            capture_source="py_get_fallback",
        )
        state.finalize()
        return state
    except Exception as e:
        state.add_warning(f"Scene capture fallback failed: {e}")
        state.finalize()
        return state
