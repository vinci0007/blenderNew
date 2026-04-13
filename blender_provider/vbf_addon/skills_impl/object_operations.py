# Core Object Operations - Critical missing bpy.ops.object skills
# Analyzed from UNCOVERED_MODULES_ANALYSIS.md
from typing import Any, Dict, List, Optional

import bpy

from .utils import fmt_err, set_active_object


def object_origin_set(
    object_name: str,
    origin_type: str = "GEOMETRY_ORIGIN",
    center: str = "BOUNDS",
) -> Dict[str, Any]:
    """Set the origin of an object to its geometric center or cursor.

    CRITICAL for proper object transformations. This sets the local coordinate
    origin of the object, which affects rotation and scaling.

    Args:
        object_name: Name of the object.
        origin_type: "GEOMETRY_ORIGIN" | "ORIGIN_GEOMETRY" | "ORIGIN_CURSOR" |
                    "ORIGIN_CENTER_OF_MASS" | "ORIGIN_CENTER_OF_VOLUME"
        center: For GEOMETRY_ORIGIN, use "BOUNDS" or "MEDIAN".

    Returns:
        {"object_name": str, "origin_type": str}

    Example:
        # Center origin to geometry
        object_origin_set("Cube", origin_type="GEOMETRY_ORIGIN")

        # Set origin to 3D cursor location
        object_origin_set("Cube", origin_type="ORIGIN_CURSOR")
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        # Set the origin
        if origin_type == "GEOMETRY_ORIGIN":
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center=center)
        else:
            bpy.ops.object.origin_set(type=origin_type, center=center)

        return {
            "ok": True,
            "object_name": object_name,
            "origin_type": origin_type,
            "center": center,
        }
    except Exception as e:
        raise fmt_err("object_origin_set failed", e)


def object_select_all(
    action: str = "SELECT",
) -> Dict[str, Any]:
    """Select or deselect all objects in the scene.

    Args:
        action: "SELECT" | "DESELECT" | "INVERT" | "TOGGLE"

    Returns:
        {"action": str, "selected_count": int}
    """
    try:
        bpy.ops.object.select_all(action=action)

        selected_count = len([o for o in bpy.data.objects if o.select_get()])

        return {
            "ok": True,
            "action": action,
            "selected_count": selected_count,
        }
    except Exception as e:
        raise fmt_err("object_select_all failed", e)


def object_select_by_type(
    object_type: str,
    extend: bool = False,
) -> Dict[str, Any]:
    """Select objects by their type (mesh, light, camera, etc.).

    Args:
        object_type: "MESH" | "LIGHT" | "CAMERA" | "CURVE" | "ARMATURE" | "EMPTY" etc.
        extend: If True, add to current selection instead of replacing.

    Returns:
        {"object_type": str, "selected_count": int}
    """
    try:
        if not extend:
            bpy.ops.object.select_all(action="DESELECT")

        selected_count = 0
        for obj in bpy.data.objects:
            if obj.type == object_type:
                obj.select_set(True)
                selected_count += 1

        return {
            "ok": True,
            "object_type": object_type,
            "selected_count": selected_count,
        }
    except Exception as e:
        raise fmt_err("object_select_by_type failed", e)


def object_duplicate(
    object_name: str,
    linked: bool = False,
) -> Dict[str, Any]:
    """Duplicate an object.

    Args:
        object_name: Object to duplicate.
        linked: If True, create linked duplicate (shares mesh data).

    Returns:
        {"original": str, "new_object": str, "linked": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        # Duplicate
        if linked:
            bpy.ops.object.duplicate_move_linked()
        else:
            bpy.ops.object.duplicate_move()

        # Get the new object (active after duplicate)
        new_obj = bpy.context.active_object

        return {
            "ok": True,
            "original": object_name,
            "new_object": new_obj.name if new_obj else None,
            "linked": linked,
        }
    except Exception as e:
        raise fmt_err("object_duplicate failed", e)


def object_make_local(
    object_name: str,
    clear_data: bool = True,
) -> Dict[str, Any]:
    """Make a linked object local to this scene.

    When objects are linked from other blend files, this makes them
    independent so they can be edited.

    Args:
        object_name: Linked object name.
        clear_data: If True, clear library linkage.

    Returns:
        {"object_name": str, "was_local": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        was_linked = obj.library is not None

        set_active_object(obj)

        # Make local
        bpy.ops.object.make_local(type="SELECT_OBDATA")

        return {
            "ok": True,
            "object_name": object_name,
            "was_linked": was_linked,
            "now_local": obj.library is None,
        }
    except Exception as e:
        raise fmt_err("object_make_local failed", e)


def object_shade_smooth(
    object_names: List[str],
) -> Dict[str, Any]:
    """Set smooth shading on object(s).

    Args:
        object_names: List of object names to smooth.

    Returns:
        {"objects": List[str], "smoothed": bool}
    """
    try:
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                set_active_object(obj)
                bpy.ops.object.shade_smooth()

        return {
            "ok": True,
            "objects": object_names,
            "smoothed": True,
        }
    except Exception as e:
        raise fmt_err("object_shade_smooth failed", e)


def object_shade_flat(
    object_names: List[str],
) -> Dict[str, Any]:
    """Set flat shading on object(s).

    Args:
        object_names: List of object names.

    Returns:
        {"objects": List[str], "smoothed": bool}
    """
    try:
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                set_active_object(obj)
                bpy.ops.object.shade_flat()

        return {
            "ok": True,
            "objects": object_names,
            "shaded_flat": True,
        }
    except Exception as e:
        raise fmt_err("object_shade_flat failed", e)


def object_move_to_collection(
    object_names: List[str],
    collection_name: str,
) -> Dict[str, Any]:
    """Move objects to a specific collection.

    Args:
        object_names: Objects to move.
        collection_name: Target collection name. Creates if doesn't exist.

    Returns:
        {"moved": int, "collection": str}
    """
    try:
        # Get or create collection
        coll = bpy.data.collections.get(collection_name)
        if not coll:
            coll = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(coll)

        moved_count = 0
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj:
                # Unlink from all current collections
                for c in list(obj.users_collection):
                    c.objects.unlink(obj)
                # Link to target
                coll.objects.link(obj)
                moved_count += 1

        return {
            "ok": True,
            "moved": moved_count,
            "collection": collection_name,
        }
    except Exception as e:
        raise fmt_err("object_move_to_collection failed", e)


def object_hide_set(
    object_names: List[str],
    hide_viewport: bool = True,
    hide_render: Optional[bool] = None,
) -> Dict[str, Any]:
    """Hide objects in viewport and/or render.

    Args:
        object_names: Objects to hide/unhide.
        hide_viewport: Hide in viewport.
        hide_render: Hide in render (if None, matches viewport).

    Returns:
        {"hidden": int, "objects": List[str]}
    """
    try:
        if hide_render is None:
            hide_render = hide_viewport

        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj:
                obj.hide_viewport = hide_viewport
                obj.hide_render = hide_render

        return {
            "ok": True,
            "objects": object_names,
            "hide_viewport": hide_viewport,
            "hide_render": hide_render,
        }
    except Exception as e:
        raise fmt_err("object_hide_set failed", e)


def object_convert(
    object_name: str,
    target: str = "MESH",
) -> Dict[str, Any]:
    """Convert an object to another type.

    Args:
        object_name: Object to convert.
        target: "MESH" | "CURVE" | "GPENCIL" | "ARMATURE" etc.

    Returns:
        {"original": str, "target": str, "result": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        bpy.ops.object.convert(target=target)

        # Get result
        result_obj = bpy.context.active_object

        return {
            "ok": True,
            "original": object_name,
            "target": target,
            "result": result_obj.name if result_obj else None,
        }
    except Exception as e:
        raise fmt_err("object_convert failed", e)
