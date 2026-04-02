import traceback
from typing import List, Tuple

import bpy  # type: ignore
import mathutils  # type: ignore


def ensure_object_mode() -> None:
    try:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass


def set_active_object(obj: bpy.types.Object) -> None:
    ensure_object_mode()
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def vec3(v: List[float]) -> Tuple[float, float, float]:
    return float(v[0]), float(v[1]), float(v[2])


def fmt_err(prefix: str, e: Exception) -> RuntimeError:
    return RuntimeError(f"{prefix}: {e}\n{traceback.format_exc()}")

