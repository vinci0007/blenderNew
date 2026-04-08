# Lighting Skills - Blender Light Types
from typing import Any, Dict, List

import bpy

from .utils import fmt_err, vec3, set_active_object


def create_light(
    light_type: str,
    name: str,
    location: List[float],
    energy: float = 10.0,
    color: List[float] | None = None,
    rotation_euler: List[float] | None = None,
) -> Dict[str, Any]:
    """Create a light source in the scene.

    Args:
        light_type: Type of light. Enum: "point" | "sun" | "spot" | "area".
        name: Name to assign to the light object.
        location: [x, y, z] world-space position for the light.
        energy: Light power in watts. Defaults to 10.0.
        color: Optional [r, g, b] color (0.0-1.0). Defaults to white [1, 1, 1].
        rotation_euler: Optional [rx, ry, rz] rotation in radians for sun/spot lights.

    Returns:
        {"object_name": str, "light_name": str} - the created object and data names.
    """
    try:
        light_type_enum = {
            "point": "POINT",
            "sun": "SUN",
            "spot": "SPOT",
            "area": "AREA",
        }.get(light_type.lower())

        if not light_type_enum:
            raise ValueError(f"Unknown light type: {light_type}. Use: point, sun, spot, area")

        color_rgb = color or [1.0, 1.0, 1.0]

        # Create light data
        light_data = bpy.data.lights.new(name=name, type=light_type_enum)
        light_data.energy = float(energy)
        light_data.color = tuple(vec3(color_rgb))

        # Create object
        light_obj = bpy.data.objects.new(name=name, object_data=light_data)
        bpy.context.collection.objects.link(light_obj)
        light_obj.location = vec3(location)

        if rotation_euler:
            light_obj.rotation_euler = vec3(rotation_euler)

        set_active_object(light_obj)

        return {
            "object_name": light_obj.name,
            "light_name": light_data.name,
            "type": light_type_enum,
        }
    except Exception as e:
        raise fmt_err("create_light failed", e)


def set_light_properties(
    light_name: str,
    energy: float | None = None,
    color: List[float] | None = None,
    specular: float | None = None,
    shadow_soft_size: float | None = None,
    # Spot light specific
    spot_size: float | None = None,
    spot_blend: float | None = None,
    # Sun light specific
    angle: float | None = None,
    # Area light specific
    size: float | None = None,
    shape: str | None = None,
) -> Dict[str, Any]:
    """Configure properties of an existing light.

    Args:
        light_name: Name of the light data (not object) to configure.
        energy: Light power in watts.
        color: [r, g, b] color values (0.0-1.0).
        specular: Specular intensity multiplier.
        shadow_soft_size: Shadow softness in radians (for point/spot).
        spot_size: Spotlight angle in radians.
        spot_blend: Spotlight edge softness (0.0-1.0).
        angle: Sun apparent angle in radians.
        size: Area light size in Blender units.
        shape: Area light shape. Enum: "square" | "rectangle" | "disk" | "ellipse".

    Returns:
        {"light_name": str, "updated_properties": List[str]}
    """
    try:
        light = bpy.data.lights.get(light_name)
        if not light:
            raise ValueError(f"Light not found: {light_name}")

        updated = []

        if energy is not None:
            light.energy = float(energy)
            updated.append("energy")

        if color is not None:
            light.color = vec3(color)
            updated.append("color")

        if specular is not None:
            light.specular = float(specular)
            updated.append("specular")

        if shadow_soft_size is not None:
            light.shadow_soft_size = float(shadow_soft_size)
            updated.append("shadow_soft_size")

        # Spot light properties
        if light.type == "SPOT":
            if spot_size is not None:
                light.spot_size = float(spot_size)
                updated.append("spot_size")
            if spot_blend is not None:
                light.spot_blend = float(spot_blend)
                updated.append("spot_blend")

        # Sun light properties
        if light.type == "SUN" and angle is not None:
            light.angle = float(angle)
            updated.append("angle")

        # Area light properties
        if light.type == "AREA":
            if size is not None:
                light.size = float(size)
                updated.append("size")
            if shape is not None:
                shape_enum = {
                    "square": "SQUARE",
                    "rectangle": "RECTANGLE",
                    "disk": "DISK",
                    "ellipse": "ELLIPSE",
                }.get(shape.lower())
                if shape_enum:
                    light.shape = shape_enum
                    updated.append("shape")

        return {"light_name": light.name, "updated_properties": updated}
    except Exception as e:
        raise fmt_err("set_light_properties failed", e)


def set_render_engine(engine: str = "cycles") -> Dict[str, Any]:
    """Set the render engine for the scene.

    Args:
        engine: Render engine. Enum: "cycles" | "eevee" | "workbench".

    Returns:
        {"engine": str, "previous_engine": str}
    """
    try:
        scene = bpy.context.scene
        prev = scene.render.engine

        engine_map = {
            "cycles": "CYCLES",
            "eevee": "BLENDER_EEVEE_NEXT",
            "workbench": "BLENDER_WORKBENCH",
        }.get(engine.lower())

        if not engine_map:
            raise ValueError(f"Unknown engine: {engine}")

        scene.render.engine = engine_map

        return {"engine": engine_map, "previous_engine": prev}
    except Exception as e:
        raise fmt_err("set_render_engine failed", e)


def set_render_resolution(
    width: int = 1920,
    height: int = 1080,
    percentage: int = 100,
) -> Dict[str, Any]:
    """Configure render resolution settings.

    Args:
        width: Horizontal resolution in pixels.
        height: Vertical resolution in pixels.
        percentage: Resolution percentage (25, 50, 75, 100, 200).

    Returns:
        {"resolution": [width, height], "percentage": int}
    """
    try:
        scene = bpy.context.scene
        scene.render.resolution_x = int(width)
        scene.render.resolution_y = int(height)
        scene.render.resolution_percentage = int(percentage)

        return {
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "percentage": scene.render.resolution_percentage,
        }
    except Exception as e:
        raise fmt_err("set_render_resolution failed", e)
