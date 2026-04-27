# Grease Pencil Skills - Blender Grease Pencil 3.0
from typing import Any, Dict, List, Optional, Tuple, Union

import bpy

from .utils import ensure_object_mode, fmt_err, set_active_object, vec3


def gpencil_add_blank(
    name: str = "Grease Pencil",
    location: List[float] = [0, 0, 0],
) -> Dict[str, Any]:
    """Add a blank Grease Pencil object.

    Args:
        name: Name for the Grease Pencil object.
        location: [x, y, z] position.

    Returns:
        {"object_name": str}
    """
    try:
        loc = vec3(location)

        bpy.ops.object.grease_pencil_add(
            type="EMPTY",
            location=loc,
        )
        obj = bpy.context.active_object
        obj.name = name

        return {"object_name": obj.name}
    except Exception as e:
        raise fmt_err("gpencil_add_blank failed", e)


def gpencil_layer_create(
    object_name: str,
    layer_name: str,
) -> Dict[str, Any]:
    """Create a new Grease Pencil layer.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Name for the new layer.

    Returns:
        {"object_name": str, "layer_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.new(name=layer_name)

        return {"object_name": obj.name, "layer_name": layer.name}
    except Exception as e:
        raise fmt_err("gpencil_layer_create failed", e)


def gpencil_layer_remove(
    object_name: str,
    layer_name: str,
) -> Dict[str, Any]:
    """Remove a Grease Pencil layer.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Name of layer to remove.

    Returns:
        {"removed": bool, "layer_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if layer:
            gp.layers.remove(layer)
            return {"removed": True, "layer_name": layer_name}
        else:
            return {"removed": False, "reason": "Layer not found"}
    except Exception as e:
        raise fmt_err("gpencil_layer_remove failed", e)


def gpencil_frame_add(
    object_name: str,
    layer_name: str,
    frame_number: Optional[int] = None,
) -> Dict[str, Any]:
    """Add a frame to a Grease Pencil layer.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Layer name.
        frame_number: Frame number (defaults to current scene frame).

    Returns:
        {"object_name": str, "layer_name": str, "frame": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if not layer:
            raise ValueError(f"Layer not found: {layer_name}")

        frame = frame_number or bpy.context.scene.frame_current
        f = layer.frames.new(frame)

        return {"object_name": obj.name, "layer_name": layer.name, "frame": frame}
    except Exception as e:
        raise fmt_err("gpencil_frame_add failed", e)


def gpencil_draw_line(
    object_name: str,
    layer_name: str,
    start_point: List[float],
    end_point: List[float],
    pressure: float = 1.0,
    strength: float = 1.0,
) -> Dict[str, Any]:
    """Draw a line stroke in Grease Pencil.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Layer name.
        start_point: [x, y, z] start position.
        end_point: [x, y, z] end position.
        pressure: Stroke pressure/thickness.
        strength: Stroke opacity strength.

    Returns:
        {"object_name": str, "layer_name": str, "points": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if not layer:
            raise ValueError(f"Layer not found: {layer_name}")

        # Get active frame or create new one
        frame = layer.active_frame
        if not frame:
            frame = layer.frames.new(bpy.context.scene.frame_current)

        # Create stroke
        stroke = frame.strokes.new()
        stroke.display_mode = "3DSPACE"

        # Add points
        stroke.points.add(count=2)
        stroke.points[0].co = vec3(start_point)
        stroke.points[0].pressure = pressure
        stroke.points[0].strength = strength
        stroke.points[1].co = vec3(end_point)
        stroke.points[1].pressure = pressure
        stroke.points[1].strength = strength

        return {"object_name": obj.name, "layer_name": layer.name, "points": 2}
    except Exception as e:
        raise fmt_err("gpencil_draw_line failed", e)


def gpencil_draw_stroke(
    object_name: str,
    layer_name: str,
    points: List[List[float]],
    pressure: float = 1.0,
    strength: float = 1.0,
) -> Dict[str, Any]:
    """Draw a multi-point stroke in Grease Pencil.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Layer name.
        points: List of [x, y, z] points.
        pressure: Stroke pressure/thickness.
        strength: Stroke opacity strength.

    Returns:
        {"object_name": str, "layer_name": str, "points": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if not layer:
            raise ValueError(f"Layer not found: {layer_name}")

        frame = layer.active_frame
        if not frame:
            frame = layer.frames.new(bpy.context.scene.frame_current)

        stroke = frame.strokes.new()
        stroke.display_mode = "3DSPACE"
        stroke.points.add(count=len(points))

        for i, p in enumerate(points):
            stroke.points[i].co = vec3(p)
            stroke.points[i].pressure = pressure
            stroke.points[i].strength = strength

        return {"object_name": obj.name, "layer_name": layer.name, "points": len(points)}
    except Exception as e:
        raise fmt_err("gpencil_draw_stroke failed", e)


def gpencil_fill(
    object_name: str,
    layer_name: str,
    points: List[List[float]],
    pressure: float = 1.0,
) -> Dict[str, Any]:
    """Draw a filled polygon stroke in Grease Pencil.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Layer name.
        points: List of [x, y, z] points forming closed shape.
        pressure: Stroke pressure/thickness.

    Returns:
        {"object_name": str, "layer_name": str, "points": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if not layer:
            raise ValueError(f"Layer not found: {layer_name}")

        frame = layer.active_frame
        if not frame:
            frame = layer.frames.new(bpy.context.scene.frame_current)

        stroke = frame.strokes.new()
        stroke.display_mode = "3DSPACE"
        stroke.use_cyclic = True  # Closed shape
        stroke.points.add(count=len(points))

        for i, p in enumerate(points):
            stroke.points[i].co = vec3(p)
            stroke.points[i].pressure = pressure
            stroke.points[i].strength = 1.0

        return {"object_name": obj.name, "layer_name": layer.name, "points": len(points)}
    except Exception as e:
        raise fmt_err("gpencil_fill failed", e)


def gpencil_delete_stroke(
    object_name: str,
    layer_name: str,
    stroke_index: int = -1,
) -> Dict[str, Any]:
    """Delete a stroke from Grease Pencil.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Layer name.
        stroke_index: Index of stroke to delete (-1 for last).

    Returns:
        {"deleted": bool, "remaining": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if not layer or not layer.active_frame:
            raise ValueError(f"Layer or frame not found")

        frame = layer.active_frame
        if not frame.strokes:
            return {"deleted": False, "reason": "No strokes in frame"}

        idx = stroke_index if stroke_index >= 0 else len(frame.strokes) - 1
        frame.strokes.remove(frame.strokes[idx])

        return {"deleted": True, "remaining": len(frame.strokes)}
    except Exception as e:
        raise fmt_err("gpencil_delete_stroke failed", e)


def gpencil_material_add(
    object_name: str,
    material_name: str = "GP_Material",
    stroke_color: List[float] = [0, 0, 0, 1],
    fill_color: List[float] = [0.5, 0.5, 0.5, 1],
) -> Dict[str, Any]:
    """Add a material to Grease Pencil.

    Args:
        object_name: Grease Pencil object name.
        material_name: Name for the material.
        stroke_color: [r, g, b, a] stroke color (0-1).
        fill_color: [r, g, b, a] fill color (0-1).

    Returns:
        {"object_name": str, "material_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        # Create material
        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True

        # Setup as Grease Pencil material
        bpy.data.materials.create_gpencil_data(mat)

        # Set colors
        gp_mat = mat.grease_pencil
        gp_mat.color = tuple(stroke_color)
        gp_mat.fill_color = tuple(fill_color)

        # Append to object
        obj.data.materials.append(mat)

        return {"object_name": obj.name, "material_name": mat.name}
    except Exception as e:
        raise fmt_err("gpencil_material_add failed", e)


def gpencil_set_material(
    object_name: str,
    material_index: int,
) -> Dict[str, Any]:
    """Set active material for Grease Pencil.

    Args:
        object_name: Grease Pencil object name.
        material_index: Material slot index.

    Returns:
        {"object_name": str, "material_index": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        if material_index >= len(gp.materials):
            raise ValueError(f"Material index out of range")

        gp.materials.active_index = material_index

        return {"object_name": obj.name, "material_index": material_index}
    except Exception as e:
        raise fmt_err("gpencil_set_material failed", e)


def gpencil_convert_to_mesh(
    object_name: str,
    new_name: Optional[str] = None,
    thickness: float = 0.01,
) -> Dict[str, Any]:
    """Convert Grease Pencil strokes to mesh.

    Args:
        object_name: Grease Pencil object name.
        new_name: Name for the new mesh object.
        thickness: Thickness for converted strokes.

    Returns:
        {"object_name": str, "mesh_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        set_active_object(obj)

        bpy.ops.object.convert(target="MESH", thickness=thickness)
        mesh_obj = bpy.context.active_object
        if not mesh_obj or mesh_obj.type != "MESH":
            raise RuntimeError("Grease Pencil to mesh conversion did not produce a mesh")

        if new_name:
            mesh_obj.name = new_name

        return {"object_name": obj.name, "mesh_name": mesh_obj.name}
    except Exception as e:
        raise fmt_err("gpencil_convert_to_mesh failed", e)


def gpencil_convert_to_curve(
    object_name: str,
    new_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert Grease Pencil strokes to curve.

    Args:
        object_name: Grease Pencil object name.
        new_name: Name for the new curve object.

    Returns:
        {"object_name": str, "curve_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        set_active_object(obj)

        bpy.ops.object.convert(target="CURVE")

        curve_obj = bpy.context.active_object
        if new_name and curve_obj:
            curve_obj.name = new_name

        return {"object_name": obj.name, "curve_name": curve_obj.name if curve_obj else None}
    except Exception as e:
        raise fmt_err("gpencil_convert_to_curve failed", e)


def set_gpencil_brush(
    brush_name: str,
    size: float = 30.0,
    strength: float = 1.0,
) -> Dict[str, Any]:
    """Set the active Grease Pencil brush.

    Args:
        brush_name: Name of the brush (e.g., "Ink Pen", "Pencil", "Marker").
        size: Brush size.
        strength: Brush strength.

    Returns:
        {"brush_name": str, "size": float, "strength": float}
    """
    try:
        tool_settings = bpy.context.tool_settings
        gp_paint = (
            getattr(tool_settings, "gpencil_paint", None)
            or getattr(tool_settings, "grease_pencil_paint", None)
        )
        if gp_paint is None:
            raise RuntimeError("Grease Pencil paint settings are not available")

        # Find brush
        brush = None
        for b in bpy.data.brushes:
            if b.use_paint_grease_pencil and b.name == brush_name:
                brush = b
                break

        if not brush:
            # Create simple brush
            try:
                brush = bpy.data.brushes.new(name=brush_name, mode="GPENCIL_PAINT")
            except TypeError:
                brush = bpy.data.brushes.new(name=brush_name, mode="GREASE_PENCIL")

        gp_paint.brush = brush
        brush.size = int(size)
        brush.strength = strength

        return {"brush_name": brush.name, "size": brush.size, "strength": brush.strength}
    except Exception as e:
        raise fmt_err("set_gpencil_brush failed", e)


def gpencil_import_svg(
    filepath: str,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """Import SVG as Grease Pencil.

    Args:
        filepath: Path to SVG file.
        scale: Import scale factor.

    Returns:
        {"imported": bool, "filepath": str}
    """
    try:
        bpy.ops.wm.grease_pencil_import_svg(
            filepath=filepath,
            scale=scale,
        )
        return {"imported": True, "filepath": filepath}
    except Exception as e:
        raise fmt_err("gpencil_import_svg failed", e)


def gpencil_export_svg(
    filepath: str,
) -> Dict[str, Any]:
    """Export Grease Pencil to SVG.

    Args:
        filepath: Output path for SVG file.

    Returns:
        {"exported": bool, "filepath": str}
    """
    try:
        bpy.ops.wm.grease_pencil_export_svg(
            filepath=filepath,
        )
        return {"exported": True, "filepath": filepath}
    except Exception as e:
        raise fmt_err("gpencil_export_svg failed", e)


def gpencil_set_line_attributes(
    object_name: str,
    layer_name: str,
    line_width: float = 3.0,
    offset: float = 0.0,
) -> Dict[str, Any]:
    """Set line attributes for Grease Pencil layer.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Layer name.
        line_width: Line thickness.
        offset: Offset from surface.

    Returns:
        {"object_name": str, "layer_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if not layer:
            raise ValueError(f"Layer not found: {layer_name}")

        layer.line_width = int(line_width)
        layer.offset = offset

        return {"object_name": obj.name, "layer_name": layer.name}
    except Exception as e:
        raise fmt_err("gpencil_set_line_attributes failed", e)


def gpencil_set_view_layer(
    object_name: str,
    layer_name: str,
    show_in_view: bool = True,
    lock: bool = False,
) -> Dict[str, Any]:
    """Set view layer visibility and lock for Grease Pencil layer.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Layer name.
        show_in_view: Show in view.
        lock: Lock layer for editing.

    Returns:
        {"object_name": str, "layer_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if not layer:
            raise ValueError(f"Layer not found: {layer_name}")

        layer.hide = not show_in_view
        layer.lock = lock

        return {"object_name": obj.name, "layer_name": layer.name}
    except Exception as e:
        raise fmt_err("gpencil_set_view_layer failed", e)


def gpencil_duplicate_frame(
    object_name: str,
    layer_name: str,
    source_frame: int,
    target_frame: int,
) -> Dict[str, Any]:
    """Duplicate a frame in Grease Pencil layer.

    Args:
        object_name: Grease Pencil object name.
        layer_name: Layer name.
        source_frame: Frame number to duplicate.
        target_frame: New frame number.

    Returns:
        {"object_name": str, "layer_name": str, "from": int, "to": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "GREASEPENCIL":
            raise ValueError(f"Grease Pencil object not found: {object_name}")

        gp = obj.data
        layer = gp.layers.get(layer_name)
        if not layer:
            raise ValueError(f"Layer not found: {layer_name}")

        # Find source frame
        src_frame = None
        for f in layer.frames:
            if f.frame_number == source_frame:
                src_frame = f
                break

        if not src_frame:
            raise ValueError(f"Frame {source_frame} not found")

        # Create new frame by copying
        new_frame = layer.frames.copy(src_frame)
        new_frame.frame_number = target_frame

        return {"object_name": obj.name, "layer_name": layer.name, "from": source_frame, "to": target_frame}
    except Exception as e:
        raise fmt_err("gpencil_duplicate_frame failed", e)
