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
    """Move an object so that a specific anchor point aligns with a target world position.

    The object is translated by the delta between its current anchor location and the
    target point. Only objects with no parent are supported.

    Args:
        object_name: Name of the object to move. Must have no parent object.
        anchor_type: Which point on the object to use as the anchor. Enum (same as
            spatial_query query_type):
            - "top_center": center of the top (max-Z) face.
            - "bottom_center": center of the bottom (min-Z) face.
            - "side_center": center of the side (max-X) face.
            - "center": geometric center of the bounding box.
        target_point: [x, y, z] world-space position to move the anchor to.

    Returns:
        {"object_name": str, "moved_by": [dx, dy, dz]} — the object name and the
        translation vector applied.
    """
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
