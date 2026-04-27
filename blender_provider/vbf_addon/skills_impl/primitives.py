from typing import Any, Dict, List

import bpy  # type: ignore

from .utils import ensure_object_mode, fmt_err, vec3


def create_primitive(
    primitive_type: str = "cube",
    name: str = "Primitive",
    location: List[float] = None,
    rotation_euler: List[float] | None = None,
    scale: List[float] | None = None,
    size: List[float] | None = None,
    radius: float | None = None,
    height: float | None = None,
) -> Dict[str, Any]:
    """Create a mesh primitive object in the scene.

    Args:
        primitive_type: Type of primitive to create. Enum: "cube" | "cylinder" | "cone" | "sphere".
        name: Name to assign to the created object.
        location: [x, y, z] world-space position for the object origin.
        rotation_euler: Optional [rx, ry, rz] rotation in radians. Defaults to [0, 0, 0].
        scale: Optional [sx, sy, sz] scale applied after creation.
        size: Shorthand dimensions — meaning differs per type:
            - cube: [x, y, z] sets object dimensions directly.
            - cylinder: [radius, height].
            - cone: [radius1, radius2, height].
            - sphere: [radius].
            Mutually exclusive with `radius`/`height`; if both are given, `radius`/`height` take precedence.
        radius: Explicit radius (cylinder/cone/sphere). Overrides size[0] when provided.
        height: Explicit height (cylinder/cone). Overrides size[-1] when provided.

    Returns:
        {"object_name": str} — the name of the created Blender object.
    """
    try:
        ensure_object_mode()
        loc = vec3(location) if location else [0, 0, 0]
        rot = rotation_euler or [0.0, 0.0, 0.0]
        primitive_key = str(primitive_type or "cube").strip().lower().replace("-", "_").replace(" ", "_")
        primitive_aliases = {
            "box": "cube",
            "cuboid": "cube",
            "uv_sphere": "sphere",
            "ico_sphere": "sphere",
        }
        primitive_key = primitive_aliases.get(primitive_key, primitive_key)

        new_obj = None
        if primitive_key == "cube":
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
            new_obj = bpy.context.active_object
            if size and new_obj:
                sx, sy, sz = vec3(size)
                new_obj.dimensions = (sx, sy, sz)
        elif primitive_key == "cylinder":
            r = radius if radius is not None else (size[0] if size else 0.5)
            h = height if height is not None else (size[1] if size and len(size) > 1 else 1.0)
            bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, rotation=rot)
            new_obj = bpy.context.active_object
        elif primitive_key == "cone":
            r1 = radius if radius is not None else (size[0] if size else 0.5)
            r2 = (size[1] if size and len(size) > 1 else 0.0)
            h = height if height is not None else (size[2] if size and len(size) > 2 else 1.0)
            bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=h, location=loc, rotation=rot)
            new_obj = bpy.context.active_object
        elif primitive_key == "sphere":
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
