# Camera Skills - Blender Camera Operations
from typing import Any, Dict, List, Tuple

import bpy
import mathutils

from .utils import fmt_err, vec3, set_active_object


def create_camera(
    name: str,
    location: List[float],
    rotation_euler: List[float] | None = None,
    focal_length: float = 50.0,
    sensor_width: float = 36.0,
) -> Dict[str, Any]:
    """Create a camera in the scene.

    Args:
        name: Name to assign to the camera object.
        location: [x, y, z] world-space position for the camera.
        rotation_euler: Optional [rx, ry, rz] rotation in radians. Default looks at origin from +Z.
        focal_length: Lens focal length in mm. Defaults to 50mm.
        sensor_width: Sensor width in mm. Defaults to 36mm (full frame).

    Returns:
        {"object_name": str, "camera_name": str} - the created object and data names.
    """
    try:
        # Create camera data
        cam_data = bpy.data.cameras.new(name=name)
        cam_data.lens = float(focal_length)
        cam_data.sensor_width = float(sensor_width)

        # Create object
        cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
        bpy.context.collection.objects.link(cam_obj)

        # Set transform
        cam_obj.location = vec3(location)
        if rotation_euler:
            cam_obj.rotation_euler = vec3(rotation_euler)

        set_active_object(cam_obj)

        return {
            "object_name": cam_obj.name,
            "camera_name": cam_data.name,
            "focal_length": cam_data.lens,
        }
    except Exception as e:
        raise fmt_err("create_camera failed", e)


def set_camera_active(camera_name: str) -> Dict[str, Any]:
    """Set the active camera for the scene.

    Args:
        camera_name: Name of the camera object to activate.

    Returns:
        {"camera_name": str, "previous_camera": str | None}
    """
    try:
        cam_obj = bpy.data.objects.get(camera_name)
        if not cam_obj or cam_obj.type != "CAMERA":
            raise ValueError(f"Camera not found: {camera_name}")

        scene = bpy.context.scene
        prev_cam = scene.camera.name if scene.camera else None

        scene.camera = cam_obj

        return {"camera_name": cam_obj.name, "previous_camera": prev_cam}
    except Exception as e:
        raise fmt_err("set_camera_active failed", e)


def set_camera_properties(
    camera_name: str,
    focal_length: float | None = None,
    sensor_width: float | None = None,
    clip_start: float | None = None,
    clip_end: float | None = None,
    type: str | None = None,
) -> Dict[str, Any]:
    """Configure camera properties.

    Args:
        camera_name: Name of the camera data to configure.
        focal_length: Lens focal length in mm.
        sensor_width: Sensor width in mm.
        clip_start: Near clipping distance.
        clip_end: Far clipping distance.
        type: Camera type. Enum: "perspective" | "orthographic" | "panoramic".

    Returns:
        {"camera_name": str, "updated_properties": List[str]}
    """
    try:
        cam = bpy.data.cameras.get(camera_name)
        if not cam:
            raise ValueError(f"Camera data not found: {camera_name}")

        updated = []

        if focal_length is not None:
            cam.lens = float(focal_length)
            updated.append("focal_length")

        if sensor_width is not None:
            cam.sensor_width = float(sensor_width)
            updated.append("sensor_width")

        if clip_start is not None:
            cam.clip_start = float(clip_start)
            updated.append("clip_start")

        if clip_end is not None:
            cam.clip_end = float(clip_end)
            updated.append("clip_end")

        if type is not None:
            type_map = {
                "perspective": "PERSP",
                "orthographic": "ORTHO",
                "panoramic": "PANO",
            }.get(type.lower())
            if type_map:
                cam.type = type_map
                updated.append("type")

        return {"camera_name": cam.name, "updated_properties": updated}
    except Exception as e:
        raise fmt_err("set_camera_properties failed", e)


def camera_look_at(
    camera_name: str,
    target_point: List[float],
    up: str = "z_up",
) -> Dict[str, Any]:
    """Orient a camera to look at a specific point.

    Args:
        camera_name: Name of the camera object to orient.
        target_point: [x, y, z] world-space position to look at.
        up: Up direction. Enum: "z_up" | "y_up".

    Returns:
        {"camera_name": str, "rotation_euler": [rx, ry, rz]}
    """
    try:
        cam_obj = bpy.data.objects.get(camera_name)
        if not cam_obj or cam_obj.type != "CAMERA":
            raise ValueError(f"Camera not found: {camera_name}")

        target = mathutils.Vector(vec3(target_point))
        cam_loc = cam_obj.location

        # Calculate direction vector
        direction = target - cam_loc
        direction.normalize()

        # Create rotation matrix
        up_vec = mathutils.Vector((0, 0, 1)) if up == "z_up" else mathutils.Vector((0, 1, 0))

        # Handle looking straight up/down
        if abs(direction.dot(up_vec)) > 0.9999:
            up_vec = mathutils.Vector((1, 0, 0))

        rot_matrix = direction.to_track_quat("-Z", "Y").to_matrix().to_4x4()
        cam_obj.matrix_world = rot_matrix
        cam_obj.location = cam_loc  # Restore location

        return {
            "camera_name": cam_obj.name,
            "rotation_euler": list(cam_obj.rotation_euler),
        }
    except Exception as e:
        raise fmt_err("camera_look_at failed", e)


def get_camera_info(camera_name: str) -> Dict[str, Any]:
    """Get detailed information about a camera.

    Args:
        camera_name: Name of the camera object.

    Returns:
        Dictionary with camera properties and transform info.
    """
    try:
        cam_obj = bpy.data.objects.get(camera_name)
        if not cam_obj or cam_obj.type != "CAMERA":
            raise ValueError(f"Camera not found: {camera_name}")

        cam_data = cam_obj.data

        return {
            "object_name": cam_obj.name,
            "camera_name": cam_data.name,
            "location": list(cam_obj.location),
            "rotation_euler": list(cam_obj.rotation_euler),
            "focal_length": cam_data.lens,
            "sensor_width": cam_data.sensor_width,
            "sensor_height": cam_data.sensor_height,
            "clip_start": cam_data.clip_start,
            "clip_end": cam_data.clip_end,
            "type": cam_data.type,
        }
    except Exception as e:
        raise fmt_err("get_camera_info failed", e)
