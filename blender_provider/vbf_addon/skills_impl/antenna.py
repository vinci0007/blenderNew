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

