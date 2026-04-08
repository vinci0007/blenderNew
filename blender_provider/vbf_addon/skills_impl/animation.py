# Animation Skills - Blender Keyframe and Animation Control
from typing import Any, Dict, List

import bpy

from .utils import fmt_err


def insert_keyframe(
    object_name: str,
    frame: float,
    data_path: str = "location",
    index: int = -1,
) -> Dict[str, Any]:
    """Insert a keyframe for an object's property.

    Args:
        object_name: Target object name.
        frame: Frame number to insert keyframe.
        data_path: Property path to keyframe. Common values:
            - "location" | "rotation_euler" | "scale"
            - "hide_viewport" | "hide_render"
        index: Array index for vector properties. -1 means all-components.

    Returns:
        {"object_name": str, "frame": float, "data_path": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        # Set current frame
        bpy.context.scene.frame_set(int(frame))

        # Insert keyframe
        result = obj.keyframe_insert(data_path=data_path, index=index)

        if not result:
            raise RuntimeError(f"Failed to insert keyframe for {data_path}")

        return {
            "object_name": obj.name,
            "frame": float(frame),
            "data_path": data_path,
            "index": index,
        }
    except Exception as e:
        raise fmt_err("insert_keyframe failed", e)


def delete_keyframe(
    object_name: str,
    frame: float,
    data_path: str = "location",
    index: int = -1,
) -> Dict[str, Any]:
    """Delete a keyframe from an object's property.

    Args:
        object_name: Target object name.
        frame: Frame number where keyframe exists.
        data_path: Property path.
        index: Array index. -1 means all-components.

    Returns:
        {"object_name": str, "frame": float, "data_path": str, "deleted": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        # Set current frame
        bpy.context.scene.frame_set(int(frame))

        # Delete keyframe
        result = obj.keyframe_delete(data_path=data_path, index=index)

        return {
            "object_name": obj.name,
            "frame": float(frame),
            "data_path": data_path,
            "deleted": result,
        }
    except Exception as e:
        raise fmt_err("delete_keyframe failed", e)


def set_current_frame(frame: float) -> Dict[str, Any]:
    """Set the current frame of the timeline.

    Args:
        frame: Frame number to set.

    Returns:
        {"frame": float, "scene": str}
    """
    try:
        bpy.context.scene.frame_set(int(frame))
        return {
            "frame": bpy.context.scene.frame_current,
            "scene": bpy.context.scene.name,
        }
    except Exception as e:
        raise fmt_err("set_current_frame failed", e)


def get_current_frame() -> Dict[str, Any]:
    """Get the current frame.

    Returns:
        {"frame": int, "frame_float": float, "scene": str}
    """
    try:
        scene = bpy.context.scene
        return {
            "frame": scene.frame_current,
            "frame_float": scene.frame_current_final,
            "scene": scene.name,
        }
    except Exception as e:
        raise fmt_err("get_current_frame failed", e)


def set_frame_range(
    start: int | None = None,
    end: int | None = None,
    preview_start: int | None = None,
    preview_end: int | None = None,
) -> Dict[str, Any]:
    """Set the frame range for the scene.

    Args:
        start: Start frame.
        end: End frame.
        preview_start: Preview range start frame.
        preview_end: Preview range end frame.

    Returns:
        {"frame_start": int, "frame_end": int}
    """
    try:
        scene = bpy.context.scene

        if start is not None:
            scene.frame_start = int(start)
        if end is not None:
            scene.frame_end = int(end)
        if preview_start is not None:
            scene.frame_preview_start = int(preview_start)
        if preview_end is not None:
            scene.frame_preview_end = int(preview_end)

        return {
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_preview_start": scene.frame_preview_start,
            "frame_preview_end": scene.frame_preview_end,
        }
    except Exception as e:
        raise fmt_err("set_frame_range failed", e)


def set_animation_fps(fps: float, fps_base: float = 1.0) -> Dict[str, Any]:
    """Set animation frame rate.

    Args:
        fps: Frames per second (e.g., 24, 30, 60).
        fps_base: Base for FPS calculation (usually 1.0).

    Returns:
        {"fps": float, "fps_base": float}
    """
    try:
        scene = bpy.context.scene
        render = scene.render

        render.fps = int(fps)
        render.fps_base = float(fps_base)

        return {"fps": render.fps / render.fps_base, "fps_base": render.fps_base}
    except Exception as e:
        raise fmt_err("set_animation_fps failed", e)


def clear_animation(
    object_name: str,
    data_path: str | None = None,
) -> Dict[str, Any]:
    """Clear all or specific animation data from an object.

    Args:
        object_name: Target object name.
        data_path: Optional specific data path to clear. If None, clears all animation.

    Returns:
        {"object_name": str, "cleared": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        if data_path:
            # Clear specific fcurve
            if obj.animation_data and obj.animation_data.action:
                action = obj.animation_data.action
                fcurves_to_remove = [fc for fc in action.fcurves if fc.data_path == data_path]
                for fc in fcurves_to_remove:
                    action.fcurves.remove(fc)
        else:
            # Clear all animation data
            obj.animation_data_clear()

        return {"object_name": obj.name, "cleared": True}
    except Exception as e:
        raise fmt_err("clear_animation failed", e)


def list_fcurves(object_name: str) -> Dict[str, Any]:
    """List all fcurves (animation curves) on an object.

    Args:
        object_name: Target object name.

    Returns:
        {"object_name": str, "fcurves": [{"data_path": str, "array_index": int}]}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        curves = []
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                curves.append({
                    "data_path": fc.data_path,
                    "array_index": fc.array_index,
                    "keyframe_count": len(fc.keyframe_points),
                })

        return {"object_name": obj.name, "fcurves": curves, "count": len(curves)}
    except Exception as e:
        raise fmt_err("list_fcurves failed", e)


def set_keyframe_interpolation(
    object_name: str,
    data_path: str,
    array_index: int,
    interpolation: str = "LINEAR",
) -> Dict[str, Any]:
    """Set interpolation type for keyframes on an fcurve.

    Args:
        object_name: Target object.
        data_path: FCurve data path.
        array_index: FCurve array index.
        interpolation: Interpolation type. Enum:
            "CONSTANT" | "LINEAR" | "BEZIER" | "SINE" | "QUAD" | "CUBIC" |
            "QUART" | "QUINT" | "EXPO" | "CIRC" | "BACK" | "BOUNCE" | "ELASTIC"

    Returns:
        {"object_name": str, "affected": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        if not obj.animation_data or not obj.animation_data.action:
            return {"object_name": obj.name, "affected": 0}

        action = obj.animation_data.action
        affected = 0

        for fc in action.fcurves:
            if fc.data_path == data_path and fc.array_index == array_index:
                for kp in fc.keyframe_points:
                    kp.interpolation = interpolation
                    affected += 1

        return {"object_name": obj.name, "affected": affected}
    except Exception as e:
        raise fmt_err("set_keyframe_interpolation failed", e)


def evaluate_fcurve(
    object_name: str,
    data_path: str,
    array_index: int,
    frame: float,
) -> Dict[str, Any]:
    """Evaluate an fcurve at a specific frame.

    Args:
        object_name: Target object.
        data_path: FCurve data path.
        array_index: FCurve array index.
        frame: Frame to evaluate at.

    Returns:
        {"value": float, "frame": float}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        if not obj.animation_data or not obj.animation_data.action:
            raise ValueError(f"Object has no animation data: {object_name}")

        action = obj.animation_data.action

        for fc in action.fcurves:
            if fc.data_path == data_path and fc.array_index == array_index:
                value = fc.evaluate(frame)
                return {"value": value, "frame": float(frame)}

        raise ValueError(f"FCurve not found: {data_path}[{array_index}]")
    except Exception as e:
        raise fmt_err("evaluate_fcurve failed", e)
