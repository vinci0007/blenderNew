# Edge Control Skills - Critical for Hard-Surface Modeling
# Based on YouTube tutorial analysis (5+ dedicated edge_crease tutorials found)
from typing import Any, Dict, List, Optional

import bpy
import bmesh

from .utils import fmt_err, set_active_object, ensure_object_mode


def _edge_float_layer(
    bm: bmesh.types.BMesh,
    legacy_accessor_name: str,
    attribute_names: List[str],
    create: bool = False,
):
    layers = bm.edges.layers
    legacy_accessor = getattr(layers, legacy_accessor_name, None)
    if legacy_accessor is not None:
        layer = legacy_accessor.active
        if layer is None and create:
            layer = legacy_accessor.new()
        if layer is not None:
            return layer

    float_layers = getattr(layers, "float", None)
    if float_layers is not None:
        for name in attribute_names:
            layer = float_layers.get(name)
            if layer is not None:
                return layer
        if create and attribute_names:
            return float_layers.new(attribute_names[0])

    return None


def mark_edge_crease(
    object_name: str,
    edges: List[int],
    crease_value: float = 1.0,
    use_sharp: bool = False,
) -> Dict[str, Any]:
    """Mark edges with crease value for subdivision surface control.

    CRITICAL for hard-surface modeling: Keeps edges sharp when subdividing.
    Tutorial sources: PIXXO 3D, Francesco Milanese, BlenderVitals (5+ dedicated tutorials)

    Args:
        object_name: Target mesh object name.
        edges: List of edge indices to mark.
        crease_value: Crease value 0.0-1.0. Higher = sharper edge when subdivided.
                       1.0 = fully sharp (like having more edges),
                       0.0 = no crease (smooth).
        use_sharp: Also mark as sharp edge (for shade_smooth with sharp edges).

    Returns:
        {"object_name": str, "edges_marked": int, "crease_value": float}

    Example:
        # Mark edges as fully sharp for subdivision
        mark_edge_crease("Cube", edges=[0, 1, 2], crease_value=1.0)

        # Mark edges with medium crease
        mark_edge_crease("Panel", edges=[5, 6], crease_value=0.5)
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        if obj.type != "MESH":
            raise ValueError(f"Object {object_name} is not a mesh")

        set_active_object(obj)

        # Ensure we're in edit mode to access bmesh
        bpy.ops.object.mode_set(mode="EDIT")

        # Create bmesh from edit mesh
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        marked_count = 0
        for edge_idx in edges:
            if edge_idx < len(bm.edges):
                edge = bm.edges[edge_idx]
                # Set crease value directly on edge layer
                crease_layer = _edge_float_layer(
                    bm,
                    "crease",
                    ["crease_edge", "edge_creases", "crease"],
                    create=True,
                )
                if crease_layer:
                    edge[crease_layer] = max(0.0, min(1.0, float(crease_value)))
                marked_count += 1

                # Optionally mark as sharp edge
                if use_sharp:
                    edge.smooth = False

        # Update mesh
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "edges_marked": marked_count,
            "crease_value": max(0.0, min(1.0, float(crease_value))),
            "use_sharp": use_sharp,
        }
    except Exception as e:
        raise fmt_err("mark_edge_crease failed", e)


def clear_edge_crease(
    object_name: str,
    edges: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Clear edge crease values.

    Args:
        object_name: Target mesh object name.
        edges: List of edge indices to clear. If None, clears all edges.

    Returns:
        {"object_name": str, "edges_cleared": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        if obj.type != "MESH":
            raise ValueError(f"Object {object_name} is not a mesh")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        crease_layer = _edge_float_layer(
            bm,
            "crease",
            ["crease_edge", "edge_creases", "crease"],
        )
        if not crease_layer:
            bpy.ops.object.mode_set(mode="OBJECT")
            return {"ok": True, "object_name": object_name, "edges_cleared": 0}

        edges_to_clear = edges if edges is not None else range(len(bm.edges))
        cleared_count = 0

        for edge_idx in edges_to_clear:
            if edge_idx < len(bm.edges):
                bm.edges[edge_idx][crease_layer] = 0.0
                cleared_count += 1

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "edges_cleared": cleared_count,
        }
    except Exception as e:
        raise fmt_err("clear_edge_crease failed", e)


def set_edge_bevel_weight(
    object_name: str,
    edges: List[int],
    weight: float = 0.5,
) -> Dict[str, Any]:
    """Set bevel weight for variable width beveling.

    CRITICAL for professional hard-surface workflows: Different edges can have
    different bevel widths. Tutorial source: CG Boost, Francesco Milanese.

    Args:
        object_name: Target mesh object name.
        edges: List of edge indices to set weight on.
        weight: Bevel weight 0.0-1.0. Higher = wider bevel.

    Returns:
        {"object_name": str, "edges_set": int, "bevel_weight": float}

    Example:
        # Set primary edges to full bevel width
        set_edge_bevel_weight("Cube", edges=[0, 1, 2], weight=1.0)

        # Set secondary edges to smaller bevel
        set_edge_bevel_weight("Cube", edges=[3, 4], weight=0.3)
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        if obj.type != "MESH":
            raise ValueError(f"Object {object_name} is not a mesh")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        # Get bevel weight layer
        bevel_weight_layer = _edge_float_layer(
            bm,
            "bevel_weight",
            ["bevel_weight_edge", "edge_bevel_weight", "bevel_weight"],
            create=True,
        )

        weight_value = max(0.0, min(1.0, float(weight)))
        set_count = 0

        for edge_idx in edges:
            if edge_idx < len(bm.edges):
                bm.edges[edge_idx][bevel_weight_layer] = weight_value
                set_count += 1

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "edges_set": set_count,
            "bevel_weight": weight_value,
        }
    except Exception as e:
        raise fmt_err("set_edge_bevel_weight failed", e)


def clear_edge_bevel_weight(
    object_name: str,
    edges: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Clear edge bevel weights.

    Args:
        object_name: Target mesh object name.
        edges: List of edge indices to clear. If None, clears all.

    Returns:
        {"object_name": str, "edges_cleared": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        if obj.type != "MESH":
            raise ValueError(f"Object {object_name} is not a mesh")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        bevel_weight_layer = _edge_float_layer(
            bm,
            "bevel_weight",
            ["bevel_weight_edge", "edge_bevel_weight", "bevel_weight"],
        )
        if not bevel_weight_layer:
            bpy.ops.object.mode_set(mode="OBJECT")
            return {"ok": True, "object_name": object_name, "edges_cleared": 0}

        edges_to_clear = edges if edges is not None else range(len(bm.edges))
        cleared_count = 0

        for edge_idx in edges_to_clear:
            if edge_idx < len(bm.edges):
                bm.edges[edge_idx][bevel_weight_layer] = 0.0
                cleared_count += 1

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "edges_cleared": cleared_count,
        }
    except Exception as e:
        raise fmt_err("clear_edge_bevel_weight failed", e)


def get_edge_data(
    object_name: str,
) -> Dict[str, Any]:
    """Get edge data including crease and bevel weight values.

    Useful for inspecting current edge settings before modification.

    Args:
        object_name: Target mesh object name.

    Returns:
        {
            "object_name": str,
            "edge_count": int,
            "edges_with_crease": int,
            "edges_with_bevel_weight": int,
            "edges": [{"index": int, "crease": float, "bevel_weight": float}]
        }
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        if obj.type != "MESH":
            raise ValueError(f"Object {object_name} is not a mesh")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        crease_layer = _edge_float_layer(
            bm,
            "crease",
            ["crease_edge", "edge_creases", "crease"],
        )
        bevel_layer = _edge_float_layer(
            bm,
            "bevel_weight",
            ["bevel_weight_edge", "edge_bevel_weight", "bevel_weight"],
        )

        edge_data = []
        edges_with_crease = 0
        edges_with_bevel = 0

        for i, edge in enumerate(bm.edges):
            data = {"index": i, "crease": 0.0, "bevel_weight": 0.0, "is_sharp": not edge.smooth}

            if crease_layer:
                data["crease"] = edge[crease_layer]
                if data["crease"] > 0.001:
                    edges_with_crease += 1

            if bevel_layer:
                data["bevel_weight"] = edge[bevel_layer]
                if data["bevel_weight"] > 0.001:
                    edges_with_bevel += 1

            edge_data.append(data)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "edge_count": len(bm.edges),
            "edges_with_crease": edges_with_crease,
            "edges_with_bevel_weight": edges_with_bevel,
            "edges": edge_data,
        }
    except Exception as e:
        raise fmt_err("get_edge_data failed", e)


def bisect_mesh(
    object_name: str,
    plane_co: List[float],
    plane_no: List[float],
    use_fill: bool = False,
    clear_inner: bool = False,
    clear_outer: bool = False,
) -> Dict[str, Any]:
    """Bisect (cut) mesh with a plane.

    Useful for precise cuts along arbitrary planes.

    Args:
        object_name: Target mesh object.
        plane_co: Plane center point [x, y, z].
        plane_no: Plane normal [x, y, z].
        use_fill: Fill the cut.
        clear_inner: Remove geometry on the inner side.
        clear_outer: Remove geometry on the outer side.

    Returns:
        {"object_name": str, "cut_done": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Select all
        bpy.ops.mesh.select_all(action="SELECT")

        # Perform bisect
        bpy.ops.mesh.bisect(
            plane_co=tuple(plane_co),
            plane_no=tuple(plane_no),
            use_fill=use_fill,
            clear_inner=clear_inner,
            clear_outer=clear_outer,
        )

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "cut_done": True,
            "plane_co": plane_co,
            "plane_no": plane_no,
        }
    except Exception as e:
        raise fmt_err("bisect_mesh failed", e)


def fill_holes(
    object_name: str,
    sides: int = 4,
) -> Dict[str, Any]:
    """Fill holes in mesh.

    Args:
        object_name: Target mesh object.
        sides: Maximum number of sides in hole to fill.

    Returns:
        {"object_name": str, "holes_filled": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Select all
        bpy.ops.mesh.select_all(action="SELECT")

        # Fill holes
        bpy.ops.mesh.fill_holes(sides=sides)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "holes_filled": "completed",
            "max_sides": sides,
        }
    except Exception as e:
        raise fmt_err("fill_holes failed", e)


def symmetrize_mesh(
    object_name: str,
    axis: str = "NEGATIVE_X",
    threshold: float = 0.001,
) -> Dict[str, Any]:
    """Symmetrize mesh around an axis.

    More flexible than mirror modifier for one-time symmetry operations.

    Args:
        object_name: Target mesh object.
        axis: Symmetry axis. Options: "NEGATIVE_X", "POSITIVE_X",
              "NEGATIVE_Y", "POSITIVE_Y", "NEGATIVE_Z", "POSITIVE_Z"
        threshold: Distance for merging vertices.

    Returns:
        {"object_name": str, "axis": str, "symmetrized": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Select all
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.mesh.symmetrize(
            direction=axis,
            threshold=threshold,
        )

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "axis": axis,
            "symmetrized": True,
        }
    except Exception as e:
        raise fmt_err("symmetrize_mesh failed", e)


def select_edge_rings(
    object_name: str,
    edge_index: int,
    extend: bool = False,
) -> Dict[str, Any]:
    """Select edge ring from an edge.

    Edge rings are perpendicular to edge loops and important for
    controlling edge flow in hard-surface modeling.

    Args:
        object_name: Target mesh object.
        edge_index: Starting edge index.
        extend: Extend current selection.

    Returns:
        {"object_name": str, "edges_selected": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Clear selection if not extending
        if not extend:
            bpy.ops.mesh.select_all(action="DESELECT")

        # Ensure edge select mode
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)

        # Select edge ring
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()

        if edge_index < len(bm.edges):
            bm.edges[edge_index].select = True
            bpy.ops.mesh.edgering_select()

        selected_count = sum(1 for e in bm.edges if e.select)

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "object_name": object_name,
            "edges_selected": selected_count,
        }
    except Exception as e:
        raise fmt_err("select_edge_rings failed", e)
