# View3D Operations - Viewport and 3D cursor control
# Completely uncovered module from UNCOVERED_MODULES_ANALYSIS.md
from typing import Any, Dict, List, Optional

import bpy
from mathutils import Vector

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
        scene = bpy.context.scene
        selected = list(bpy.context.selected_objects)
        if not selected:
            scene.cursor.location = (0.0, 0.0, 0.0)
        else:
            center = Vector((0.0, 0.0, 0.0))
            for obj in selected:
                center += obj.matrix_world.translation
            scene.cursor.location = center / len(selected)

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
        scene = bpy.context.scene
        scene.cursor.location = (0.0, 0.0, 0.0)
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
        scene = bpy.context.scene
        cursor_location = scene.cursor.location.copy()
        moved = []
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj:
                obj.location = cursor_location
                obj.select_set(True)
                moved.append(obj.name)
        if moved:
            bpy.context.view_layer.objects.active = bpy.data.objects.get(moved[0])

        return {
            "ok": True,
            "objects": moved,
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
        return {
            "ok": True,
            "action": "FRAME_SELECTED",
            "skipped": "viewport-only operation is not required for headless execution",
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
        return {
            "ok": True,
            "action": "FRAME_ALL",
            "skipped": "viewport-only operation is not required for headless execution",
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
        for obj in bpy.data.objects:
            obj.select_set(obj.name in object_names)

        # First select one as active
        if object_names:
            active = bpy.data.objects.get(object_names[0])
            if active:
                bpy.context.view_layer.objects.active = active

        return {
            "ok": True,
            "objects": object_names,
            "local_view": False,
            "skipped": "viewport-only operation is not required for headless execution",
        }
    except Exception as e:
        raise fmt_err("view3d_localview failed", e)
