from typing import Any, Dict, List

import bpy  # type: ignore
import mathutils  # type: ignore

from .utils import fmt_err


def spatial_query(object_name: str, query_type: str) -> Dict[str, Any]:
    """Query a spatial point on an object's bounding box in world coordinates.

    Args:
        object_name: Name of the Blender object to query.
        query_type: Which point to return. Enum:
            - "top_center": center of the top (max-Z) face.
            - "bottom_center": center of the bottom (min-Z) face.
            - "side_center": center of the side (max-X) face.
            - "center": geometric center of the bounding box.

    Returns:
        {"location": [x, y, z]} — world-space coordinates of the queried point.
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        corners_local = [mathutils.Vector(corner) for corner in obj.bound_box]
        corners_world = [obj.matrix_world @ v for v in corners_local]

        def face_center(axis: str, extreme: str) -> List[float]:
            if axis == "x":
                vals = [p.x for p in corners_world]
                coord = lambda p: p.x
            elif axis == "y":
                vals = [p.y for p in corners_world]
                coord = lambda p: p.y
            else:
                vals = [p.z for p in corners_world]
                coord = lambda p: p.z

            target = max(vals) if extreme == "max" else min(vals)
            tol = 1e-6
            pts = [p for p in corners_world if abs(coord(p) - target) <= tol * 10]
            if not pts:
                pts = [max(corners_world, key=coord)] if extreme == "max" else [min(corners_world, key=coord)]
            x = sum(p.x for p in pts) / len(pts)
            y = sum(p.y for p in pts) / len(pts)
            z = sum(p.z for p in pts) / len(pts)
            return [float(x), float(y), float(z)]

        if query_type == "top_center":
            return {"location": face_center(axis="z", extreme="max")}
        if query_type == "bottom_center":
            return {"location": face_center(axis="z", extreme="min")}
        if query_type == "side_center":
            return {"location": face_center(axis="x", extreme="max")}
        if query_type == "center":
            min_x = min(p.x for p in corners_world)
            min_y = min(p.y for p in corners_world)
            min_z = min(p.z for p in corners_world)
            max_x = max(p.x for p in corners_world)
            max_y = max(p.y for p in corners_world)
            max_z = max(p.z for p in corners_world)
            return {"location": [float((min_x + max_x) / 2), float((min_y + max_y) / 2), float((min_z + max_z) / 2)]}

        raise ValueError(f"Unknown query_type: {query_type}")
    except Exception as e:
        raise fmt_err("spatial_query failed", e)
