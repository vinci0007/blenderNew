# View3D Operations - Viewport and 3D cursor control
# Completely uncovered module from UNCOVERED_MODULES_ANALYSIS.md
from typing import Any, Dict, List, Optional

import bpy

from .utils import fmt_err


def view3d_cursor_set(
    location: List[float],
) -> Dict[str, Any]:
    """Set 3D cursor location.

    Args:
        location: [x, y, z] coordinates.

    Returns:
        {"location": List[float], "scene": str}
    """
    try:
        scene = bpy.context.scene
        scene.cursor.location = location

        return {
            "ok": True,
            "location": list(scene.cursor.location),
            "scene": scene.name,
        }
    except Exception as e:
        raise fmt_err("view3d_cursor_set failed", e)


def view3d_snap_cursor_to_selected(
) -> Dict[str, Any]:
    """Snap 3D cursor to the center of current selection.

    Returns:
        {"cursor_location": List[float], "scene": str}
    """
    try:
        bpy.ops.view3d.snap_cursor_to_selected()

        scene = bpy.context.scene
        return {
            "ok": True,
            "cursor_location": list(scene.cursor.location),
            "scene": scene.name,
        }
    except Exception as e:
        raise fmt_err("view3d_snap_cursor_to_selected failed", e)


def view3d_snap_cursor_to_center(
) -> Dict[str, Any]:
    """Reset 3D cursor to world origin.

    Returns:
        {"cursor_location": List[float], "scene": str}
    """
    try:
        bpy.ops.view3d.snap_cursor_to_center()

        scene = bpy.context.scene
        return {
            "ok": True,
            "cursor_location": list(scene.cursor.location),
            "scene": scene.name,
        }
    except Exception as e:
        raise fmt_err("view3d_snap_cursor_to_center failed", e)


def view3d_snap_selected_to_cursor(
    object_names: List[str],
) -> Dict[str, Any]:
    """Snap selected objects to 3D cursor.

    Args:
        object_names: Objects to move.

    Returns:
        {"objects": List[str], "cursor_location": List[float]}
    """
    try:
        # Select objects
        for obj in bpy.data.objects:
            obj.select_set(obj.name in object_names)

        bpy.context.view_layer.objects.active = bpy.data.objects.get(object_names[0])

        bpy.ops.view3d.snap_selected_to_cursor()

        scene = bpy.context.scene
        return {
            "ok": True,
            "objects": object_names,
            "cursor_location": list(scene.cursor.location),
        }
    except Exception as e:
        raise fmt_err("view3d_snap_selected_to_cursor failed", e)


def view3d_view_selected(
) -> Dict[str, Any]:
    """Frame the view to show selected objects.

    Returns:
        {"action": str}
    """
    try:
        bpy.ops.view3d.view_selected()

        return {
            "ok": True,
            "action": "FRAME_SELECTED",
        }
    except Exception as e:
        raise fmt_err("view3d_view_selected failed", e)


def view3d_view_all(
) -> Dict[str, Any]:
    """Frame the view to show all objects.

    Returns:
        {"action": str}
    """
    try:
        bpy.ops.view3d.view_all()

        return {
            "ok": True,
            "action": "FRAME_ALL",
        }
    except Exception as e:
        raise fmt_err("view3d_view_all failed", e)


def view3d_localview(
    object_names: List[str],
) -> Dict[str, Any]:
    """Toggle local view for selected objects (isolate selection).

    Args:
        object_names: Objects to isolate.

    Returns:
        {"objects": List[str], "local_view": bool}
    """
    try:
        # Select objects
        for obj in bpy.data.objects:
            obj.select_set(obj.name in object_names)

        # First select one as active
        if object_names:
            active = bpy.data.objects.get(object_names[0])
            if active:
                bpy.context.view_layer.objects.active = active

        bpy.ops.view3d.localview(frame_selected=False)

        return {
            "ok": True,
            "objects": object_names,
            "local_view": True,
        }
    except Exception as e:
        raise fmt_err("view3d_localview failed", e)
