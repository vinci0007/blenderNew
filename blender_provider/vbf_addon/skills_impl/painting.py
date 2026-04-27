# Texture Painting Skills - Blender Texture Painting
from typing import Any, Dict, List, Optional, Tuple, Union

import bpy

from .utils import ensure_object_mode, fmt_err, set_active_object


def set_texture_paint_brush(
    brush_name: str = "Brush",
    size: int = 50,
    strength: float = 1.0,
    color: List[float] = [1.0, 1.0, 1.0, 1.0],
) -> Dict[str, Any]:
    """Configure the texture paint brush.

    Args:
        brush_name: Brush name.
        size: Brush size in pixels.
        strength: Brush strength.
        color: [r, g, b, a] color.

    Returns:
        {"brush_name": str, "size": int, "strength": float}
    """
    try:
        # Get or create brush
        brush = bpy.data.brushes.get(brush_name)
        if not brush or not brush.use_paint_image:
            brush = bpy.data.brushes.new(brush_name, mode="TEXTURE_PAINT")

        tool_settings = bpy.context.tool_settings
        tool_settings.image_paint.brush = brush

        brush.size = size
        brush.strength = strength
        brush.color = color[:3]

        return {
            "brush_name": brush.name,
            "size": brush.size,
            "strength": brush.strength,
        }
    except Exception as e:
        raise fmt_err("set_texture_paint_brush failed", e)


def texture_paint_mode(
    object_name: str,
    enable: bool = True,
) -> Dict[str, Any]:
    """Enter or exit texture paint mode.

    Args:
        object_name: Object name.
        enable: True to enter, False to exit.

    Returns:
        {"object_name": str, "mode": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        if enable:
            bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
        else:
            bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "object_name": obj.name,
            "mode": "TEXTURE_PAINT" if enable else "OBJECT",
        }
    except Exception as e:
        raise fmt_err("texture_paint_mode failed", e)


def quick_paint(
    object_name: str,
    color: List[float],
    size: int = 50,
) -> Dict[str, Any]:
    """Quick paint on a mesh object.

    Args:
        object_name: Mesh object.
        color: [r, g, b, a] paint color.
        size: Brush size.

    Returns:
        {"object_name": str, "color": List[float]}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Ensure in texture paint mode
        if bpy.context.mode != "PAINT_TEXTURE":
            bpy.ops.object.mode_set(mode="TEXTURE_PAINT")

        # Set brush
        set_texture_paint_brush("QuickBrush", size, 1.0, color)

        return {
            "object_name": obj.name,
            "color": color,
            "ready": True,
        }
    except Exception as e:
        raise fmt_err("quick_paint failed", e)


def image_paint_slot(
    object_name: str,
    slot_index: int,
) -> Dict[str, Any]:
    """Set the active paint slot for texture painting.

    Args:
        object_name: Object name.
        slot_index: Material slot index.

    Returns:
        {"object_name": str, "paint_slot": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        tool_settings = bpy.context.tool_settings
        tool_settings.image_paint.paint_mode = "MATERIAL"
        tool_settings.image_paint.paint_slot = slot_index

        return {
            "object_name": obj.name,
            "paint_slot": slot_index,
        }
    except Exception as e:
        raise fmt_err("image_paint_slot failed", e)


def paint_image(
    image_name: str,
) -> Dict[str, Any]:
    """Set the active paint image.

    Args:
        image_name: Image name.

    Returns:
        {"image_name": str}
    """
    try:
        img = bpy.data.images.get(image_name)
        if not img:
            raise ValueError(f"Image not found: {image_name}")

        tool_settings = bpy.context.tool_settings
        tool_settings.image_paint.canvas = img

        return {"image_name": img.name}
    except Exception as e:
        raise fmt_err("paint_image failed", e)


def texture_paint_fill(
    object_name: str,
    color: List[float],
) -> Dict[str, Any]:
    """Fill the active image with a solid color.

    Args:
        object_name: Object name.
        color: [r, g, b, a] fill color.

    Returns:
        {"object_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Enter texture paint mode
        if bpy.context.mode != "PAINT_TEXTURE":
            bpy.ops.object.mode_set(mode="TEXTURE_PAINT")

        img = bpy.context.tool_settings.image_paint.canvas
        if not img:
            raise ValueError("No active texture paint image/canvas")

        rgba = list(color[:4])
        if len(rgba) < 4:
            rgba.extend([1.0] * (4 - len(rgba)))
        img.pixels.foreach_set((rgba * (img.size[0] * img.size[1]))[: len(img.pixels)])
        img.update()

        return {"object_name": obj.name, "image_name": img.name, "filled": True}
    except Exception as e:
        raise fmt_err("texture_paint_fill failed", e)


def set_paint_symmetry(
    x: bool = True,
    y: bool = False,
    z: bool = False,
) -> Dict[str, Any]:
    """Set texture paint symmetry.

    Args:
        x: X-axis symmetry.
        y: Y-axis symmetry.
        z: Z-axis symmetry.

    Returns:
        {"x": bool, "y": bool, "z": bool}
    """
    try:
        tool_settings = bpy.context.tool_settings
        tool_settings.image_paint.use_symmetry_x = x
        tool_settings.image_paint.use_symmetry_y = y
        tool_settings.image_paint.use_symmetry_z = z

        return {
            "x": tool_settings.image_paint.use_symmetry_x,
            "y": tool_settings.image_paint.use_symmetry_y,
            "z": tool_settings.image_paint.use_symmetry_z,
        }
    except Exception as e:
        raise fmt_err("set_paint_symmetry failed", e)


def paint_operator_enable(
    operator: str,
) -> Dict[str, Any]:
    """Enable a paint operator (Clone, Smear, Soften, etc.).

    Args:
        operator: Operator name (CLONE, SMOOTH, SMEAR).

    Returns:
        {"operator": str, "enabled": bool}
    """
    try:
        tool_settings = bpy.context.tool_settings

        if operator == "CLONE":
            tool_settings.image_paint.brush.image_tool = "CLONE"
        elif operator == "SMEAR":
            tool_settings.image_paint.brush.image_tool = "SMEAR"
        elif operator == "SOFTEN":
            tool_settings.image_paint.brush.image_tool = "SOFTEN"
        else:
            tool_settings.image_paint.brush.image_tool = "DRAW"

        return {"operator": operator, "enabled": True}
    except Exception as e:
        raise fmt_err("paint_operator_enable failed", e)


def clone_from_image(
    image_name: str,
) -> Dict[str, Any]:
    """Set clone source image.

    Args:
        image_name: Clone source image.

    Returns:
        {"image_name": str}
    """
    try:
        img = bpy.data.images.get(image_name)
        if not img:
            raise ValueError(f"Image not found: {image_name}")

        tool_settings = bpy.context.tool_settings
        brush = tool_settings.image_paint.brush
        brush.clone_image = img

        return {"image_name": img.name}
    except Exception as e:
        raise fmt_err("clone_from_image failed", e)


def project_paint(
    object_name: str,
    image_name: str,
) -> Dict[str, Any]:
    """Project paint using camera view.

    Args:
        object_name: Object to paint.
        image_name: Image to paint from.

    Returns:
        {"object_name": str, "image_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        img = bpy.data.images.get(image_name)

        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh not found: {object_name}")
        if not img:
            raise ValueError(f"Image not found: {image_name}")

        set_active_object(obj)

        # Set up for project paint
        tool_settings = bpy.context.tool_settings
        tool_settings.image_paint.mode = "PROJECTIVE"
        tool_settings.image_paint.canvas = img

        return {
            "object_name": obj.name,
            "image_name": img.name,
        }
    except Exception as e:
        raise fmt_err("project_paint failed", e)


def uv_texture_paint_prep(
    object_name: str,
    image_name: str,
    resolution: int = 1024,
) -> Dict[str, Any]:
    """Prepare object for UV texture painting.

    Args:
        object_name: Mesh object.
        image_name: Image to create/use.
        resolution: Image resolution.

    Returns:
        {"object_name": str, "image_name": str, "resolution": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh not found: {object_name}")

        set_active_object(obj)

        # Ensure UV map exists
        if not obj.data.uv_layers:
            bpy.ops.uv.smart_project()

        # Create image if needed
        img = bpy.data.images.get(image_name)
        if not img:
            img = bpy.data.images.new(
                name=image_name,
                width=resolution,
                height=resolution,
            )

        # Enter texture paint mode
        bpy.ops.object.mode_set(mode="TEXTURE_PAINT")

        return {
            "object_name": obj.name,
            "image_name": img.name,
            "resolution": resolution,
        }
    except Exception as e:
        raise fmt_err("uv_texture_paint_prep failed", e)


# Vertex Paint skills
def vertex_paint_mode(
    object_name: str,
    enable: bool = True,
) -> Dict[str, Any]:
    """Enter or exit vertex paint mode.

    Args:
        object_name: Object name.
        enable: True to enter, False to exit.

    Returns:
        {"object_name": str, "mode": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh not found: {object_name}")

        set_active_object(obj)

        if enable:
            bpy.ops.object.mode_set(mode="VERTEX_PAINT")
        else:
            bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "object_name": obj.name,
            "mode": "VERTEX_PAINT" if enable else "OBJECT",
        }
    except Exception as e:
        raise fmt_err("vertex_paint_mode failed", e)


def set_vertex_paint_brush(
    brush_name: str = "Draw",
    size: int = 50,
    strength: float = 1.0,
    color: List[float] = [1.0, 1.0, 1.0, 1.0],
) -> Dict[str, Any]:
    """Configure the vertex paint brush.

    Args:
        brush_name: Brush name.
        size: Brush size.
        strength: Brush strength.
        color: [r, g, b, a] color.

    Returns:
        {"brush_name": str, "size": int, "strength": float}
    """
    try:
        brush = bpy.data.brushes.get(brush_name)
        if not brush or not brush.use_paint_vertex:
            brush = bpy.data.brushes.new(brush_name, mode="VERTEX_PAINT")

        tool_settings = bpy.context.tool_settings
        tool_settings.vertex_paint.brush = brush

        brush.size = size
        brush.strength = strength

        return {
            "brush_name": brush.name,
            "size": brush.size,
            "strength": brush.strength,
        }
    except Exception as e:
        raise fmt_err("set_vertex_paint_brush failed", e)


def vertex_paint_fill(
    object_name: str,
    color: List[float],
) -> Dict[str, Any]:
    """Fill vertex colors on a mesh.

    Args:
        object_name: Mesh object.
        color: [r, g, b, a] fill color.

    Returns:
        {"object_name": str, "vertices_painted": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh not found: {object_name}")

        set_active_object(obj)

        # Enter vertex paint mode
        if bpy.context.mode != "PAINT_VERTEX":
            bpy.ops.object.mode_set(mode="VERTEX_PAINT")

        # Select all and fill
        bpy.ops.paint.vertex_color_set()

        return {
            "object_name": obj.name,
            "vertices_painted": len(obj.data.vertices),
        }
    except Exception as e:
        raise fmt_err("vertex_paint_fill failed", e)


# Weight Paint skills
def weight_paint_mode(
    object_name: str,
    enable: bool = True,
) -> Dict[str, Any]:
    """Enter or exit weight paint mode.

    Args:
        object_name: Object name.
        enable: True to enter, False to exit.

    Returns:
        {"object_name": str, "mode": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh not found: {object_name}")

        set_active_object(obj)

        if enable:
            bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
        else:
            bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "object_name": obj.name,
            "mode": "WEIGHT_PAINT" if enable else "OBJECT",
        }
    except Exception as e:
        raise fmt_err("weight_paint_mode failed", e)


def set_weight_paint_brush(
    brush_name: str = "Draw",
    size: int = 50,
    strength: float = 1.0,
) -> Dict[str, Any]:
    """Configure the weight paint brush.

    Args:
        brush_name: Brush name.
        size: Brush size.
        strength: Brush strength.

    Returns:
        {"brush_name": str, "size": int, "strength": float}
    """
    try:
        brush = bpy.data.brushes.get(brush_name)
        if not brush or not brush.use_paint_weight:
            brush = bpy.data.brushes.new(brush_name, mode="WEIGHT_PAINT")

        tool_settings = bpy.context.tool_settings
        tool_settings.weight_paint.brush = brush

        brush.size = size
        brush.strength = strength

        return {
            "brush_name": brush.name,
            "size": brush.size,
            "strength": brush.strength,
        }
    except Exception as e:
        raise fmt_err("set_weight_paint_brush failed", e)


def weight_paint_set(
    object_name: str,
    vertex_group: str,
    weight: float = 1.0,
) -> Dict[str, Any]:
    """Set weight for all vertices in a vertex group.

    Args:
        object_name: Mesh object.
        vertex_group: Vertex group name.
        weight: Weight value (0-1).

    Returns:
        {"object_name": str, "vertex_group": str, "weight": float}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh not found: {object_name}")

        if vertex_group not in obj.vertex_groups:
            raise ValueError(f"Vertex group not found: {vertex_group}")

        set_active_object(obj)

        # Enter weight paint mode
        if bpy.context.mode != "PAINT_WEIGHT":
            bpy.ops.object.mode_set(mode="WEIGHT_PAINT")

        vg = obj.vertex_groups[vertex_group]
        vg.add([vertex.index for vertex in obj.data.vertices], weight, "REPLACE")

        return {
            "object_name": obj.name,
            "vertex_group": vertex_group,
            "weight": weight,
        }
    except Exception as e:
        raise fmt_err("weight_paint_set failed", e)
