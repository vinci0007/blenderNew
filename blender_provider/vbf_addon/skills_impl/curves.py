# Curves & Text Skills - Blender Curve and Text Operations
from typing import Any, Dict, List

import bpy
import mathutils

from .utils import fmt_err, set_active_object, vec3


def create_curve_bezier(
    name: str,
    location: List[float],
    points: List[List[float]],
    is_cyclic: bool = False,
) -> Dict[str, Any]:
    """Create a Bezier curve.

    Args:
        name: Name for the curve object.
        location: [x, y, z] world-space position.
        points: List of [x, y, z] control point positions.
        is_cyclic: If True, closes the curve.

    Returns:
        {"object_name": str, "control_points": int}
    """
    try:
        curve_data = bpy.data.curves.new(name=name, type="CURVE")
        curve_data.dimensions = "3D"
        curve_data.resolution_u = 12

        # Create spline
        spline = curve_data.splines.new("BEZIER")
        spline.bezier_points.add(count=len(points) - 1)
        spline.use_cyclic_u = is_cyclic

        # Set points
        for i, pt in enumerate(points):
            spline.bezier_points[i].co = (pt[0], pt[1], pt[2], 1.0)
            spline.bezier_points[i].handle_left = (pt[0] - 0.1, pt[1], pt[2])
            spline.bezier_points[i].handle_right = (pt[0] + 0.1, pt[1], pt[2])

        # Create object
        curve_obj = bpy.data.objects.new(name=name, object_data=curve_data)
        bpy.context.collection.objects.link(curve_obj)
        curve_obj.location = vec3(location)

        set_active_object(curve_obj)

        return {
            "object_name": curve_obj.name,
            "control_points": len(points),
            "is_cyclic": is_cyclic,
        }
    except Exception as e:
        raise fmt_err("create_curve_bezier failed", e)


def create_curve_circle(
    name: str,
    location: List[float],
    radius: float = 1.0,
    is_nurbs: bool = False,
) -> Dict[str, Any]:
    """Create a circular curve.

    Args:
        name: Name for the curve object.
        location: [x, y, z] world-space position.
        radius: Circle radius.
        is_nurbs: If True, uses NURBS curves instead of Bezier.

    Returns:
        {"object_name": str, "radius": float}
    """
    try:
        curve_type = "NURBS" if is_nurbs else "BEZIER"
        if is_nurbs:
            bpy.ops.curve.primitive_nurbs_circle_add(radius=radius, location=vec3(location))
        else:
            bpy.ops.curve.primitive_bezier_circle_add(radius=radius, location=vec3(location))

        obj = bpy.context.active_object
        obj.name = name

        return {"object_name": obj.name, "radius": radius, "type": curve_type}
    except Exception as e:
        raise fmt_err("create_curve_circle failed", e)


def create_text(
    name: str,
    text: str,
    location: List[float],
    size: float = 1.0,
    extrude: float = 0.0,
) -> Dict[str, Any]:
    """Create a text object.

    Args:
        name: Name for the text object.
        text: Text content string.
        location: [x, y, z] world-space position.
        size: Text size.
        extrude: Extrusion depth for 3D text.

    Returns:
        {"object_name": str, "char_count": int}
    """
    try:
        bpy.ops.object.text_add(location=vec3(location))
        text_obj = bpy.context.active_object
        text_obj.name = name

        # Set text content
        text_obj.data.body = text
        text_obj.data.size = size
        text_obj.data.extrude = extrude

        set_active_object(text_obj)

        return {
            "object_name": text_obj.name,
            "char_count": len(text),
            "text": text,
        }
    except Exception as e:
        raise fmt_err("create_text failed", e)


def set_text_content(
    object_name: str,
    text: str,
) -> Dict[str, Any]:
    """Change text content of a text object.

    Args:
        object_name: Name of text object.
    text: New text content.

    Returns:
        {"object_name": str, "char_count": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "FONT":
            raise ValueError(f"Text object not found: {object_name}")

        obj.data.body = text

        return {
            "object_name": obj.name,
            "char_count": len(text),
            "text": text,
        }
    except Exception as e:
        raise fmt_err("set_text_content failed", e)


def set_text_properties(
    object_name: str,
    size: float | None = None,
    extrude: float | None = None,
    bevel_depth: float | None = None,
    bevel_resolution: int | None = None,
) -> Dict[str, Any]:
    """Configure text object properties.

    Args:
        object_name: Name of text object.
        size: Text size.
        extrude: 3D extrusion depth.
        bevel_depth: Bevel depth for outline.
        bevel_resolution: Resolution of bevel.

    Returns:
        {"object_name": str, "updated": List[str]}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "FONT":
            raise ValueError(f"Text object not found: {object_name}")

        updated = []
        data = obj.data

        if size is not None:
            data.size = size
            updated.append("size")

        if extrude is not None:
            data.extrude = extrude
            updated.append("extrude")

        if bevel_depth is not None:
            data.bevel_depth = bevel_depth
            updated.append("bevel_depth")

        if bevel_resolution is not None:
            data.bevel_resolution = bevel_resolution
            updated.append("bevel_resolution")

        return {"object_name": obj.name, "updated": updated}
    except Exception as e:
        raise fmt_err("set_text_properties failed", e)


def set_curve_bevel(
    curve_name: str,
    bevel_depth: float = 0.0,
    bevel_resolution: int = 2,
    fill_mode: str = "HALF",
) -> Dict[str, Any]:
    """Set bevel properties for a curve.

    Args:
        curve_name: Name of curve object.
        bevel_depth: Depth of bevel/roundness.
        bevel_resolution: Resolution of bevel.
        fill_mode: Fill mode. Enum: "HALF" | "FRONT" | "BACK" | "FULL".

    Returns:
        {"curve_name": str, "bevel_depth": float}
    """
    try:
        obj = bpy.data.objects.get(curve_name)
        if not obj or obj.type != "CURVE":
            raise ValueError(f"Curve object not found: {curve_name}")

        obj.data.bevel_depth = bevel_depth
        obj.data.bevel_resolution = bevel_resolution
        obj.data.fill_mode = fill_mode

        return {
            "curve_name": obj.name,
            "bevel_depth": bevel_depth,
            "bevel_resolution": bevel_resolution,
        }
    except Exception as e:
        raise fmt_err("set_curve_bevel failed", e)


def set_curve_taper(
    curve_name: str,
    taper_curve_name: str | None = None,
) -> Dict[str, Any]:
    """Set taper object for a curve.

    Args:
        curve_name: Name of curve to apply taper to.
        taper_curve_name: Name of curve to use as taper profile (None to clear).

    Returns:
        {"curve_name": str, "taper": str | None}
    """
    try:
        obj = bpy.data.objects.get(curve_name)
        if not obj or obj.type != "CURVE":
            raise ValueError(f"Curve object not found: {curve_name}")

        if taper_curve_name:
            taper_obj = bpy.data.objects.get(taper_curve_name)
            if not taper_obj or taper_obj.type != "CURVE":
                raise ValueError(f"Taper curve not found: {taper_curve_name}")
            obj.data.taper_object = taper_obj
            taper_name = taper_obj.name
        else:
            obj.data.taper_object = None
            taper_name = None

        return {"curve_name": obj.name, "taper": taper_name}
    except Exception as e:
        raise fmt_err("set_curve_taper failed", e)


def set_curve_extrude(
    curve_name: str,
    extrude: float = 0.0,
) -> Dict[str, Any]:
    """Set extrusion amount for a curve.

    Args:
        curve_name: Name of curve object.
        extrude: Amount to extrude curve profile.

    Returns:
        {"curve_name": str, "extrude": float}
    """
    try:
        obj = bpy.data.objects.get(curve_name)
        if not obj or obj.type != "CURVE":
            raise ValueError(f"Curve object not found: {curve_name}")

        obj.data.extrude = extrude

        return {"curve_name": obj.name, "extrude": extrude}
    except Exception as e:
        raise fmt_err("set_curve_extrude failed", e)


def array_along_curve(
    object_name: str,
    curve_name: str,
    count: int = 10,
) -> Dict[str, Any]:
    """Add a modifier to array an object along a curve.

    Args:
        object_name: Name of object to array.
        curve_name: Name of curve to array along.
        count: Number of items in array.

    Returns:
        {"object_name": str, "modifier_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        curve = bpy.data.objects.get(curve_name)
        if not curve or curve.type != "CURVE":
            raise ValueError(f"Curve not found: {curve_name}")

        # Add array modifier
        mod = obj.modifiers.new(name="ArrayAlongCurve", type="ARRAY")
        mod.fit_type = "FIT_CURVE"
        mod.curve = curve
        mod.count = count

        return {"object_name": obj.name, "modifier_name": mod.name, "count": count}
    except Exception as e:
        raise fmt_err("array_along_curve failed", e)


def curve_to_mesh(object_name: str) -> Dict[str, Any]:
    """Convert a curve object to a mesh object.

    Args:
        object_name: Name of curve object to convert.

    Returns:
        {"object_name": str, "mesh_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "CURVE":
            raise ValueError(f"Curve object not found: {object_name}")

        set_active_object(obj)

        # Convert to mesh
        bpy.ops.object.convert(target="MESH")

        return {"object_name": obj.name, "type": "MESH"}
    except Exception as e:
        raise fmt_err("curve_to_mesh failed", e)


def text_to_curve(object_name: str) -> Dict[str, Any]:
    """Convert a text object to a curve object.

    Args:
        object_name: Name of text object.

    Returns:
        {"object_name": str, "type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "FONT":
            raise ValueError(f"Text object not found: {object_name}")

        set_active_object(obj)

        # Convert to curve
        bpy.ops.object.convert(target="CURVE")

        return {"object_name": obj.name, "type": "CURVE"}
    except Exception as e:
        raise fmt_err("text_to_curve failed", e)


def set_font(
    object_name: str,
    font_name: str | None = None,
) -> Dict[str, Any]:
    """Set the font for a text object.

    Args:
        object_name: Name of text object.
        font_name: Name of font in bpy.data.fonts. None for default.

    Returns:
        {"object_name": str, "font": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "FONT":
            raise ValueError(f"Text object not found: {object_name}")

        if font_name:
            font = bpy.data.fonts.get(font_name)
            if not font:
                raise ValueError(f"Font not found: {font_name}")
            obj.data.font = font
            font_name_return = font.name
        else:
            obj.data.font = None  # Use default
            font_name_return = "default"

        return {"object_name": obj.name, "font": font_name_return}
    except Exception as e:
        raise fmt_err("set_font failed", e)
