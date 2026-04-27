# UV Mapping Skills - UV Unwrap and Layout Operations
import math
from typing import Any, Dict, List

import bpy

from .utils import ensure_object_mode, fmt_err, set_active_object


def unwrap_mesh(
    object_name: str,
    method: str = "ANGLE_BASED",
    margin: float = 0.001,
) -> Dict[str, Any]:
    """Unwrap mesh UVs using standard unwrap algorithm.

    Args:
        object_name: Mesh object to unwrap.
        method: Unwrap method. Enum: "ANGLE_BASED" | "CONFORMAL".
        margin: UV island margin.

    Returns:
        {"object_name": str, "unwrapped": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.unwrap(method=method, margin=margin)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "unwrapped": True, "method": method}
    except Exception as e:
        raise fmt_err("unwrap_mesh failed", e)


def smart_project_uv(
    object_name: str,
    angle_limit: float = 66.0,
    island_margin: float = 0.02,
    area_threshold: float = 0.0,
) -> Dict[str, Any]:
    """Smart UV project - automatic UV layout based on mesh geometry.

    Args:
        object_name: Mesh object to project.
        angle_limit: Angle limit in degrees for seams (1-89).
        island_margin: Margin between UV islands.
        area_threshold: Area threshold for face grouping.

    Returns:
        {"object_name": str, "projected": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.smart_project(
            angle_limit=math.radians(angle_limit),
            island_margin=island_margin,
            area_weight=area_threshold,
        )

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "projected": True}
    except Exception as e:
        raise fmt_err("smart_project_uv failed", e)


def lightmap_pack(
    object_name: str,
    pack_quality: int = 12,
    margin: float = 0.005,
) -> Dict[str, Any]:
    """Pack UVs for lightmap baking.

    Args:
        object_name: Mesh object to pack.
        pack_quality: Quality of packing (1-48, higher = slower but better).
        margin: Margin between UV islands.

    Returns:
        {"object_name": str, "packed": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.lightmap_pack(PREF_BOX_DIV=pack_quality, PREF_MARGIN_DIV=margin)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "packed": True}
    except Exception as e:
        raise fmt_err("lightmap_pack failed", e)


def mark_seam(
    object_name: str,
    clear: bool = False,
) -> Dict[str, Any]:
    """Mark selected edges as UV seams.

    Args:
        object_name: Mesh object.
        clear: If True, clears seams instead of marking.

    Returns:
        {"object_name": str, "marked": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        if clear:
            bpy.ops.mesh.mark_seam(clear=True)
        else:
            bpy.ops.mesh.mark_seam(clear=False)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "seams_marked": not clear}
    except Exception as e:
        raise fmt_err("mark_seam failed", e)


def pack_uv_islands(
    object_name: str,
    margin: float = 0.0,
    rotate: bool = True,
) -> Dict[str, Any]:
    """Pack UV islands into UV space with minimal overlap.

    Args:
        object_name: Mesh object to pack.
        margin: Space between UV islands.
        rotate: Allow rotating islands for better packing.

    Returns:
        {"object_name": str, "packed": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.pack_islands(margin=margin, rotate=rotate)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "packed": True, "margin": margin}
    except Exception as e:
        raise fmt_err("pack_uv_islands failed", e)


def scale_uv(
    object_name: str,
    scale: List[float],
    pivot: List[float] | None = None,
) -> Dict[str, Any]:
    """Scale UV coordinates.

    Args:
        object_name: Mesh object.
        scale: [sx, sy] scale factors.
        pivot: Optional [px, py] pivot point for scaling (default: center).

    Returns:
        {"object_name": str, "scaled": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.select_all(action="SELECT")

        sx, sy = float(scale[0]), float(scale[1])
        pivot_2d = [0.5, 0.5] if pivot is None else [float(pivot[0]), float(pivot[1])]

        bpy.ops.transform.resize(
            value=(sx, sy, 1.0),
            center_override=(pivot_2d[0], pivot_2d[1], 0.0),
        )

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "scale": [sx, sy]}
    except Exception as e:
        raise fmt_err("scale_uv failed", e)


def arrange_uvs(
    object_names: List[str],
    shape_method: str = "AABB",
) -> Dict[str, Any]:
    """Arrange UVs of multiple objects together.

    Args:
        object_names: List of mesh object names to arrange.
        shape_method: Island shape method. Enum: "AABB" | "CONCAVE" | "CONVEX".

    Returns:
        {"arranged": int} - number of objects arranged.
    """
    try:
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                set_active_object(obj)
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.uv.select_all(action="SELECT")
                bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.uv.pack_islands()
        bpy.ops.object.mode_set(mode="OBJECT")

        return {"arranged": len(object_names)}
    except Exception as e:
        raise fmt_err("arrange_uvs failed", e)


def add_uv_map(
    object_name: str,
    name: str = "UVMap",
) -> Dict[str, Any]:
    """Add a new UV map to a mesh.

    Args:
        object_name: Mesh object to add UV map to.
        name: Name for the new UV map.

    Returns:
        {"object_name": str, "uv_map_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        mesh = obj.data

        # Create new UV map
        uv_layer = mesh.uv_layers.new(name=name)

        return {"object_name": obj.name, "uv_map_name": uv_layer.name}
    except Exception as e:
        raise fmt_err("add_uv_map failed", e)


def set_active_uv_map(
    object_name: str,
    uv_map_name: str,
) -> Dict[str, Any]:
    """Set the active UV map for rendering/display.

    Args:
        object_name: Mesh object.
        uv_map_name: Name of UV map to activate.

    Returns:
        {"object_name": str, "active_uv": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        mesh = obj.data

        # Find and activate UV map
        for uv in mesh.uv_layers:
            if uv.name == uv_map_name:
                mesh.uv_layers.active = uv
                return {"object_name": obj.name, "active_uv": uv.name}

        raise ValueError(f"UV map not found: {uv_map_name}")
    except Exception as e:
        raise fmt_err("set_active_uv_map failed", e)
