from typing import Any, Dict, List

import bpy  # type: ignore
import mathutils  # type: ignore

from .utils import ensure_object_mode, fmt_err, vec3


def create_nested_cones(
    name_prefix: str,
    base_location: List[float],
    layers: int = 4,
    base_radius: float = 0.06,
    top_radius: float = 0.006,
    height: float = 0.24,
    z_jitter: float = 0.0,
) -> Dict[str, Any]:
    """Create a set of nested, progressively smaller cones joined into one object.

    Each layer is a cone whose radius interpolates linearly from `base_radius` (layer 0)
    to `top_radius` (last layer). All cones are joined into a single mesh.

    Args:
        name_prefix: Prefix used for intermediate cone names and the final joined object name.
        base_location: [x, y, z] world-space position for the base of the cone stack.
        layers: Number of nested cone layers to create. Defaults to 4.
        base_radius: Radius of the outermost (bottom) cone. Defaults to 0.06.
        top_radius: Radius of the innermost (top) cone. Defaults to 0.006.
        height: Height of the base cone. Inner cones are slightly shorter. Defaults to 0.24.
        z_jitter: Z-axis offset applied per layer index (layer_i * z_jitter). Use 0.0 (default)
            to stack all cones at the same base Z. Positive values spread layers upward.

    Returns:
        {"object_name": str} — the name of the final joined cone object.
    """
    try:
        ensure_object_mode()
        base_loc = mathutils.Vector(vec3(base_location))
        layers_i = max(1, int(layers))
        objs: List[bpy.types.Object] = []

        for i in range(layers_i):
            t = i / max(1, layers_i - 1)
            r1 = base_radius + (top_radius - base_radius) * t
            r2 = r1 * 0.1
            h = height * (1.0 - t * 0.15)

            loc = mathutils.Vector((base_loc.x, base_loc.y, base_loc.z + (z_jitter * i)))
            bpy.ops.mesh.primitive_cone_add(
                radius1=r1,
                radius2=r2,
                depth=h,
                location=loc,
                rotation=(0.0, 0.0, 0.0),
            )
            created = bpy.context.active_object
            created.name = f"{name_prefix}_{i}"
            objs.append(created)

        for o in bpy.context.selected_objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.join()

        final = bpy.context.active_object
        final.name = name_prefix
        return {"object_name": final.name}
    except Exception as e:
        raise fmt_err("create_nested_cones failed", e)
