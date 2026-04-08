# Geometry Processing Skills - Advanced Mesh Operations
from typing import Any, Dict, List, Tuple

import bpy
import bmesh

from .utils import ensure_object_mode, fmt_err, set_active_object, vec3


def extrude_faces(
    object_name: str,
    amount: float = 1.0,
    normal: List[float] | None = None,
) -> Dict[str, Any]:
    """Extrude faces of a mesh object along normals.

    Args:
        object_name: Mesh object to extrude.
        amount: Distance to extrude (can be negative for inset).
        normal: Optional [x, y, z] direction override. If None, uses face normals.

    Returns:
        {"object_name": str, "extruded_faces": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Enter edit mode
        bpy.ops.object.mode_set(mode="EDIT")

        # Select all faces
        bpy.ops.mesh.select_all(action="SELECT")

        # Extrude
        if normal:
            nx, ny, nz = vec3(normal)
            bpy.ops.mesh.extrude_region_move(
                TRANSFORM_OT_translate={"value": (nx * amount, ny * amount, nz * amount)}
            )
        else:
            bpy.ops.transform.shrink_fatten(value=amount)

        # Return to object mode
        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "extruded": True}
    except Exception as e:
        raise fmt_err("extrude_faces failed", e)


def inset_faces(
    object_name: str,
    thickness: float = 0.1,
    depth: float = 0.0,
) -> Dict[str, Any]:
    """Inset faces of a mesh object.

    Args:
        object_name: Mesh object to inset.
        thickness: Amount to inset inward from face edges.
        depth: Amount to move inset faces along their normals (positive = extrude).

    Returns:
        {"object_name": str, "inset": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.mesh.inset(thickness=thickness, depth=depth)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "inset": True, "thickness": thickness}
    except Exception as e:
        raise fmt_err("inset_faces failed", e)


def bridge_edge_loops(object_name: str) -> Dict[str, Any]:
    """Bridge selected edge loops in a mesh.

    Args:
        object_name: Mesh object to bridge.

    Returns:
        {"object_name": str, "bridged": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")

        # Bridge edge loops
        bpy.ops.mesh.bridge_edge_loops()

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "bridged": True}
    except Exception as e:
        raise fmt_err("bridge_edge_loops failed", e)


def subdivide_mesh(
    object_name: str,
    cuts: int = 1,
    smoothness: float = 0.0,
) -> Dict[str, Any]:
    """Subdivide mesh faces.

    Args:
        object_name: Mesh object to subdivide.
        cuts: Number of subdivision cuts.
        smoothness: Smoothness factor (0.0 = no smoothing).

    Returns:
        {"object_name": str, "subdivided": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.mesh.subdivide(number_cuts=cuts, smoothness=smoothness)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "cuts": cuts, "smoothness": smoothness}
    except Exception as e:
        raise fmt_err("subdivide_mesh failed", e)


def triangulate_faces(object_name: str) -> Dict[str, Any]:
    """Convert mesh polygons to triangles.

    Args:
        object_name: Mesh object to triangulate.

    Returns:
        {"object_name": str, "triangulated": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "triangulated": True}
    except Exception as e:
        raise fmt_err("triangulate_faces failed", e)


def remove_doubles(
    object_name: str,
    distance: float = 0.0001,
) -> Dict[str, Any]:
    """Merge duplicate vertices by distance.

    Args:
        object_name: Mesh object to clean.
        distance: Minimum distance for vertices to be considered duplicates.

    Returns:
        {"object_name": str, "removed": int} - number of vertices removed.
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        # Get initial vertex count
        initial_verts = len(obj.data.vertices)

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.mesh.remove_doubles(threshold=distance)

        bpy.ops.object.mode_set(mode="OBJECT")

        # Calculate removed
        final_verts = len(obj.data.vertices)
        removed = initial_verts - final_verts

        return {"object_name": obj.name, "removed": removed}
    except Exception as e:
        raise fmt_err("remove_doubles failed", e)


def recalculate_normals(object_name: str, inside: bool = False) -> Dict[str, Any]:
    """Recalculate mesh vertex normals.

    Args:
        object_name: Mesh object to recalculate normals.
        inside: If True, normals point inward.

    Returns:
        {"object_name": str, "recalculated": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.mesh.normals_make_consistent(inside=inside)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "recalculated": True, "inside": inside}
    except Exception as e:
        raise fmt_err("recalculate_normals failed", e)


def scale_normals(object_name: str, scale: float = 1.0) -> Dict[str, Any]:
    """Scale the normals of mesh faces (flat shading effect).

    Args:
        object_name: Mesh object to shade flat/smooth.
        scale: 0.0 = flat, 1.0 = smooth default.

    Returns:
        {"object_name": str, "scaled": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Use bmesh for normal scaling
        bm = bmesh.from_mesh(obj.data)
        bm.normal_update()

        for face in bm.faces:
            face.normal = face.normal * scale

        bm.to_mesh(obj.data)
        bm.free()

        return {"object_name": obj.name, "scale": scale}
    except Exception as e:
        raise fmt_err("scale_normals failed", e)


def shade_smooth(object_name: str, auto_smooth: bool = True) -> Dict[str, Any]:
    """Set smooth shading on a mesh object.

    Args:
        object_name: Mesh object to shade.
        auto_smooth: Enable auto smooth shading.

    Returns:
        {"object_name": str, "smoothed": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.shade_smooth(use_auto_smooth=auto_smooth)

        return {"object_name": obj.name, "smoothed": True, "auto_smooth": auto_smooth}
    except Exception as e:
        raise fmt_err("shade_smooth failed", e)


def shade_flat(object_name: str) -> Dict[str, Any]:
    """Set flat shading on a mesh object.

    Args:
        object_name: Mesh object to shade.

    Returns:
        {"object_name": str, "flat": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.shade_flat()

        return {"object_name": obj.name, "flat": True}
    except Exception as e:
        raise fmt_err("shade_flat failed", e)


def set_sharp_edges(
    object_name: str,
    angle: float = 60.0,
) -> Dict[str, Any]:
    """Mark edges as sharp based on angle.

    Args:
        object_name: Mesh object to process.
        angle: Angle threshold in degrees for marking sharp edges.

    Returns:
        {"object_name": str, "sharp_edges_marked": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        # Mark sharp edges
        bpy.ops.mesh.mark_sharp(use_verts=False)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"object_name": obj.name, "sharp_angle": angle}
    except Exception as e:
        raise fmt_err("set_sharp_edges failed", e)
