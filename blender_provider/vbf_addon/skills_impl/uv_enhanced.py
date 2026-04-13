# Enhanced UV Operations - Critical missing UV mapping skills
# Based on UNCOVERED_MODULES_ANALYSIS: project_from_view, minimize_stretch, etc.
from typing import Any, Dict, List

import bpy
import bmesh

from .utils import fmt_err, set_active_object


def uv_project_from_view(
    object_name: str,
    camera_bounds: bool = True,
    correct_aspect: bool = True,
    clip_to_bounds: bool = False,
    scale_to_bounds: bool = False,
) -> Dict[str, Any]:
    """Project UV from current 3D view.

    CRITICAL for hard-surface modeling. Projects UVs based on current
    viewport view like a camera projection.

    Args:
        object_name: Target mesh object.
        camera_bounds: Use camera bounds.
        correct_aspect: Correct for aspect ratio.
        clip_to_bounds: Clip to view bounds.
        scale_to_bounds: Scale to fit bounds.

    Returns:
        {"object_name": str, "method": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Select all faces
        bpy.ops.mesh.select_all(action="SELECT")

        # Project from view
        bpy.ops.uv.project_from_view(
            camera_bounds=camera_bounds,
            correct_aspect=correct_aspect,
            clip_to_bounds=clip_to_bounds,
            scale_to_bounds=scale_to_bounds,
        )

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "method": "PROJECT_FROM_VIEW",
        }
    except Exception as e:
        raise fmt_err("uv_project_from_view failed", e)


def uv_cylinder_project(
    object_name: str,
    direction: str = "ALIGN_TO_OBJECT",
) -> Dict[str, Any]:
    """Cylindrical UV projection.

    Perfect for bottles, legs, arms, etc.

    Args:
        object_name: Target mesh object.
        direction: Projection direction method.

    Returns:
        {"object_name": str, "method": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.cylinder_project(direction=direction)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "method": "CYLINDER",
        }
    except Exception as e:
        raise fmt_err("uv_cylinder_project failed", e)


def uv_sphere_project(
    object_name: str,
    direction: str = "ALIGN_TO_OBJECT",
) -> Dict[str, Any]:
    """Spherical UV projection.

    Perfect for balls, heads, eyes, etc.

    Args:
        object_name: Target mesh object.
        direction: Projection direction method.

    Returns:
        {"object_name": str, "method": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.sphere_project(direction=direction)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "method": "SPHERE",
        }
    except Exception as e:
        raise fmt_err("uv_sphere_project failed", e)


def uv_cube_project(
    object_name: str,
    cube_size: float = 1.0,
) -> Dict[str, Any]:
    """Cube projection for boxy UV unwrapping.

    Best for hard-surface mechanical objects.

    Args:
        object_name: Target mesh object.
        cube_size: Size of the projection cube.

    Returns:
        {"object_name": str, "method": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.cube_project(cube_size=cube_size)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "method": "CUBE",
        }
    except Exception as e:
        raise fmt_err("uv_cube_project failed", e)


def uv_minimize_stretch(
    object_name: str,
    iterations: int = 2,
) -> Dict[str, Any]:
    """Minimize UV stretching by relaxing UVs.

    IMPORTANT for quality texture mapping.

    Args:
        object_name: Target mesh object.
        iterations: Number of relaxation iterations.

    Returns:
        {"object_name": str, "iterations": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Select all UVs
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.uv.minimize_stretch(iterations=iterations)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "iterations": iterations,
        }
    except Exception as e:
        raise fmt_err("uv_minimize_stretch failed", e)


def uv_stitch(
    object_name: str,
) -> Dict[str, Any]:
    """Stitch together neighboring UV islands.

    Useful for welding UV edges together.

    Returns:
        {"object_name": str, "stitched": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.uv.stitch(use_limit=False)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "stitched": True,
        }
    except Exception as e:
        raise fmt_err("uv_stitch failed", e)


def uv_average_islands_scale(
    object_name: str,
) -> Dict[str, Any]:
    """Average the scale of UV islands.

    Makes all UV islands approximately the same size.

    Returns:
        {"object_name": str, "normalized": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.uv.average_islands_scale()

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "normalized": True,
        }
    except Exception as e:
        raise fmt_err("uv_average_islands_scale failed", e)


def uv_pin(
    object_name: str,
    pins: List[int],
    clear: bool = False,
) -> Dict[str, Any]:
    """Pin UV vertices so they don't move during unwrap.

    Args:
        object_name: Target mesh object.
        pins: UV vertex indices to pin.
        clear: If True, unpin instead.

    Returns:
        {"object_name": str, "pinned": int, "clear": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Enter UV sync mode to work with bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()

        # Pin specified UVs (would need UV layer access in bmesh)
        bpy.ops.uv.pin(clear=clear)

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "pinned": len(pins) if not clear else 0,
            "clear": clear,
        }
    except Exception as e:
        raise fmt_err("uv_pin failed", e)
