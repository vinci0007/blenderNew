# Mesh Selection Operations - Critical missing selection skills
# Based on UNCOVERED_MODULES_ANALYSIS: bpy.ops.mesh selection modes
from typing import Any, Dict, List, Optional

import bpy
import bmesh

from .utils import fmt_err, set_active_object


def mesh_select_all(
    object_name: str,
    action: str = "SELECT",
) -> Dict[str, Any]:
    """Select or deselect all mesh elements.

    Args:
        object_name: Target mesh object.
        action: "SELECT" | "DESELECT" | "INVERT"

    Returns:
        {"object_name": str, "action": str, "selected": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.mesh.select_all(action=action)

        # Count selected
        bm = bmesh.from_edit_mesh(obj.data)
        selected_count = sum(1 for e in bm.faces if e.select)

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "action": action,
            "selected": selected_count,
        }
    except Exception as e:
        raise fmt_err("mesh_select_all failed", e)


def mesh_select_mode(
    object_name: str,
    mode: str = "FACE",
) -> Dict[str, Any]:
    """Set mesh selection mode (vertex, edge, face).

    Args:
        object_name: Target mesh object.
        mode: "VERT" | "EDGE" | "FACE" or combined "VERT,EDGE", etc.

    Returns:
        {"object_name": str, "mode": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Parse mode
        modes = [m.strip() for m in mode.split(",")]
        use_vert = "VERT" in modes
        use_edge = "EDGE" in modes
        use_face = "FACE" in modes

        bpy.context.tool_settings.mesh_select_mode = (use_vert, use_edge, use_face)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "mode": mode,
        }
    except Exception as e:
        raise fmt_err("mesh_select_mode failed", e)


def mesh_select_similar(
    object_name: str,
    type: str = "PERIMETER",
    compare: str = "EQUAL",
    threshold: float = 0.1,
) -> Dict[str, Any]:
    """Select similar faces/edges/verts based on properties.

    Args:
        object_name: Target mesh object.
        type: "PERIMETER" | "AREA" | "SIDE" | "NORMAL" | "FACE" | "VERT" | "EDGE"
        compare: "EQUAL" | "GREATER" | "LESS"
        threshold: Comparison threshold.

    Returns:
        {"object_name": str, "type": str, "selected": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.mesh.select_similar(
            type=type,
            compare=compare,
            threshold=threshold,
        )

        # Count
        bm = bmesh.from_edit_mesh(obj.data)
        selected_count = sum(1 for e in bm.faces if e.select)

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "type": type,
            "selected": selected_count,
        }
    except Exception as e:
        raise fmt_err("mesh_select_similar failed", e)


def mesh_loop_select(
    object_name: str,
    edge_index: int,
    extend: bool = False,
) -> Dict[str, Any]:
    """Select edge loop from an edge.

    Args:
        object_name: Target mesh object.
        edge_index: Starting edge index.
        extend: Extend current selection.

    Returns:
        {"object_name": str, "edge_index": int, "selected": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Ensure edge mode
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)

        if not extend:
            bpy.ops.mesh.select_all(action="DESELECT")

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        if edge_index < len(bm.edges):
            bm.edges[edge_index].select = True

        bmesh.update_edit_mesh(obj.data)

        # Select loop
        bpy.ops.mesh.loop_select(extend=extend)

        selected_count = sum(1 for e in bm.edges if e.select)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "edge_index": edge_index,
            "selected": selected_count,
        }
    except Exception as e:
        raise fmt_err("mesh_loop_select failed", e)


def mesh_select_mirror(
    object_name: str,
    axis: str = "X",
) -> Dict[str, Any]:
    """Select mirror elements based on existing selection.

    Args:
        object_name: Target mesh object.
        axis: "X" | "Y" | "Z"

    Returns:
        {"object_name": str, "axis": str, "selected": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.mesh.select_mirror(axis=axis)

        # Count
        bm = bmesh.from_edit_mesh(obj.data)
        selected_count = sum(1 for e in bm.faces if e.select)

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "axis": axis,
            "selected": selected_count,
        }
    except Exception as e:
        raise fmt_err("mesh_select_mirror failed", e)


def mesh_select_more_less(
    object_name: str,
    more: bool = True,
) -> Dict[str, Any]:
    """Grow or shrink current selection.

    Args:
        object_name: Target mesh object.
        more: True for more, False for less.

    Returns:
        {"object_name": str, "action": str, "selected": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        if more:
            bpy.ops.mesh.select_more()
            action = "MORE"
        else:
            bpy.ops.mesh.select_less()
            action = "LESS"

        # Count
        bm = bmesh.from_edit_mesh(obj.data)
        selected_count = sum(1 for e in bm.faces if e.select)

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "action": action,
            "selected": selected_count,
        }
    except Exception as e:
        raise fmt_err("mesh_select_more_less failed", e)


def mesh_select_non_manifold(
    object_name: str,
) -> Dict[str, Any]:
    """Select non-manifold geometry.

    Useful for finding mesh errors.

    Returns:
        {"object_name": str, "selected": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.mesh.select_non_manifold()

        # Count
        bm = bmesh.from_edit_mesh(obj.data)
        selected_count = sum(1 for e in bm.edges if e.select)

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "selected": selected_count,
            "type": "non_manifold",
        }
    except Exception as e:
        raise fmt_err("mesh_select_non_manifold failed", e)
