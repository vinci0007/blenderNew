from typing import Any, Dict, List

import bpy  # type: ignore

from .utils import ensure_object_mode, fmt_err, vec3


def create_primitive(
    primitive_type: str,
    name: str,
    location: List[float],
    rotation_euler: List[float] | None = None,
    scale: List[float] | None = None,
    size: List[float] | None = None,
    radius: float | None = None,
    height: float | None = None,
) -> Dict[str, Any]:
    try:
        ensure_object_mode()
        loc = vec3(location)
        rot = rotation_euler or [0.0, 0.0, 0.0]

        new_obj = None
        if primitive_type == "cube":
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
            new_obj = bpy.context.active_object
            if size and new_obj:
                sx, sy, sz = vec3(size)
                new_obj.dimensions = (sx, sy, sz)
        elif primitive_type == "cylinder":
            r = radius if radius is not None else (size[0] if size else 0.5)
            h = height if height is not None else (size[1] if size and len(size) > 1 else 1.0)
            bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, rotation=rot)
            new_obj = bpy.context.active_object
        elif primitive_type == "cone":
            r1 = radius if radius is not None else (size[0] if size else 0.5)
            r2 = (size[1] if size and len(size) > 1 else 0.0)
            h = height if height is not None else (size[2] if size and len(size) > 2 else 1.0)
            bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=h, location=loc, rotation=rot)
            new_obj = bpy.context.active_object
        elif primitive_type == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=radius or (size[0] if size else 0.5), location=loc, rotation=rot)
            new_obj = bpy.context.active_object
        else:
            raise ValueError(f"Unknown primitive_type: {primitive_type}")

        if not new_obj:
            raise RuntimeError("Failed to create primitive object")

        if scale:
            sx, sy, sz = vec3(scale)
            new_obj.scale = (sx, sy, sz)

        new_obj.name = name
        return {"object_name": new_obj.name}
    except Exception as e:
        raise fmt_err("create_primitive failed", e)

