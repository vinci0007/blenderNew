from typing import Any, Dict, List

import bpy  # type: ignore
import mathutils  # type: ignore

from .utils import fmt_err, set_active_object, vec3


def apply_transform(
    object_name: str,
    location: List[float] | None = None,
    rotation_euler: List[float] | None = None,
    scale: List[float] | None = None,
) -> Dict[str, Any]:
    """Set the location, rotation, and/or scale of an object.

    At least one of `location`, `rotation_euler`, or `scale` must be provided.
    Only the supplied parameters are modified; omitted ones are left unchanged.

    Args:
        object_name: Name of the object to transform.
        location: Optional [x, y, z] world-space position to set.
        rotation_euler: Optional [rx, ry, rz] rotation in radians (XYZ Euler order).
        scale: Optional [sx, sy, sz] scale factors.

    Returns:
        {"object_name": str} — the name of the transformed object.
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        set_active_object(obj)

        if location is not None:
            obj.location = mathutils.Vector(vec3(location))
        if rotation_euler is not None:
            obj.rotation_euler = mathutils.Euler(vec3(rotation_euler))
        if scale is not None:
            obj.scale = mathutils.Vector(vec3(scale))

        return {"object_name": obj.name}
    except Exception as e:
        raise fmt_err("apply_transform failed", e)
