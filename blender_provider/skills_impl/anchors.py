from typing import Any, Dict, List

import bpy  # type: ignore
import mathutils  # type: ignore

from .spatial import spatial_query
from .utils import fmt_err, vec3


def move_object_anchor_to_point(
    object_name: str,
    anchor_type: str,
    target_point: List[float],
) -> Dict[str, Any]:
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        if obj.parent is not None:
            raise ValueError("move_object_anchor_to_point only supports objects with no parent")

        cur = spatial_query(object_name=object_name, query_type=anchor_type)
        cur_loc = cur["location"]
        tgt = vec3(target_point)
        dx = tgt[0] - cur_loc[0]
        dy = tgt[1] - cur_loc[1]
        dz = tgt[2] - cur_loc[2]

        obj.location = obj.location + mathutils.Vector((dx, dy, dz))
        return {"object_name": obj.name, "moved_by": [float(dx), float(dy), float(dz)]}
    except Exception as e:
        raise fmt_err("move_object_anchor_to_point failed", e)

