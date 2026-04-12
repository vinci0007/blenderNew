# Enhanced Animation Skills
# Based on YouTube Tutorial Analysis:
# - HulkFatZerg EP14 (机械动画), EP13 (物理/平衡动画)
# - 3D Bibi 动画系列 (形态键动画)
from typing import Any, Dict, List, Optional

import bpy

from .utils import fmt_err, set_active_object


def insert_keyframe_bone(
    armature_name: str,
    bone_name: str,
    frame: float,
    data_path: str = "location",
    value: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Insert a keyframe on a specific bone.

    CRITICAL for character animation workflows.
    YouTube source: HulkFatZerg EP14 机械风格动画教程.

    Args:
        armature_name: Target armature object name.
        bone_name: Target bone name.
        frame: Frame number.
        data_path: Property to keyframe. Options:
                   "location" | "rotation_euler" | "rotation_quaternion" |
                   "scale" | "rotation_axis_angle"
        value: Optional value to set before keyframing [x, y, z].

    Returns:
        {"armature": str, "bone": str, "frame": float, "data_path": str}

    Example:
        # Animate arm rotation
        insert_keyframe_bone("Armature", "UpperArm.L", frame=1, data_path="rotation_euler")
        insert_keyframe_bone("Armature", "UpperArm.L", frame=10,
                             data_path="rotation_euler", value=[0, 0, 1.5])
    """
    try:
        armature = bpy.data.objects.get(armature_name)
        if not armature:
            raise ValueError(f"Armature not found: {armature_name}")
        if armature.type != "ARMATURE":
            raise ValueError(f"Object {armature_name} is not an armature")

        # Check bone exists
        if bone_name not in armature.pose.bones:
            raise ValueError(f"Bone '{bone_name}' not found in {armature_name}")

        set_active_object(armature)

        # Set pose mode
        bpy.ops.object.mode_set(mode="POSE")

        # Get bone
        bone = armature.pose.bones[bone_name]

        # Set current frame
        bpy.context.scene.frame_set(int(frame))

        # Set value if provided
        if value is not None:
            if data_path == "location":
                bone.location = tuple(value[:3])
            elif data_path == "rotation_euler":
                bone.rotation_euler = tuple(value[:3])
            elif data_path == "rotation_quaternion":
                bone.rotation_quaternion = tuple(value[:4])
            elif data_path == "scale":
                bone.scale = tuple(value[:3])

        # Insert keyframe
        bone.keyframe_insert(data_path=data_path)

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "ok": True,
            "armature": armature_name,
            "bone": bone_name,
            "frame": frame,
            "data_path": data_path,
        }
    except Exception as e:
        raise fmt_err("insert_keyframe_bone failed", e)


def insert_keyframe_shape_key(
    shape_key_name: str,
    frame: float,
    value: float,
    object_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a keyframe for a shape key.

    YouTube source: 3D Bibi 形态键动画教程.
    Essential for facial animation and morph targets.

    Args:
        shape_key_name: Name of the shape key.
        frame: Frame number.
        value: Shape key value (0.0 to 1.0).
        object_name: Optional object name (searches all if not provided).

    Returns:
        {"shape_key": str, "frame": float, "value": float}

    Example:
        # Animate facial expression
        insert_keyframe_shape_key("Smile", frame=1, value=0.0, object_name="Character")
        insert_keyframe_shape_key("Smile", frame=10, value=1.0, object_name="Character")
    """
    try:
        target_key = None
        target_mesh = None

        if object_name:
            obj = bpy.data.objects.get(object_name)
            if not obj or obj.type != "MESH":
                raise ValueError(f"Mesh object not found: {object_name}")
            if not obj.data.shape_keys:
                raise ValueError(f"Object {object_name} has no shape keys")

            target_mesh = obj.data
            if shape_key_name in target_mesh.shape_keys.key_blocks:
                target_key = target_mesh.shape_keys.key_blocks[shape_key_name]
        else:
            # Search all objects
            for obj in bpy.data.objects:
                if obj.type == "MESH" and obj.data.shape_keys:
                    if shape_key_name in obj.data.shape_keys.key_blocks:
                        target_key = obj.data.shape_keys.key_blocks[shape_key_name]
                        target_mesh = obj.data
                        break

        if not target_key:
            raise ValueError(f"Shape key '{shape_key_name}' not found")

        # Set current frame
        bpy.context.scene.frame_set(int(frame))

        # Set value and insert keyframe
        target_key.value = float(value)
        target_key.keyframe_insert(data_path="value")

        return {
            "ok": True,
            "shape_key": shape_key_name,
            "frame": frame,
            "value": float(value),
        }
    except Exception as e:
        raise fmt_err("insert_keyframe_shape_key failed", e)


def set_keyframe_handle_type(
    object_name: str,
    data_path: str,
    array_index: int,
    handle_type: str = "AUTO",
    keyframe_indices: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Set handle type for keyframes to control animation curves.

    Handle types control the interpolation between keyframes.
    - AUTO: Automatic smooth handles
    - AUTO_CLAMPED: Auto with clamped extreme values
    - VECTOR: Linear-like, sharp corners
    - ALIGNED: Manual, keep handles aligned
    - FREE: Free control, can break alignment

    Args:
        object_name: Target object name.
        data_path: Property data path.
        array_index: Array index (0=x, 1=y, 2=z).
        handle_type: "AUTO" | "AUTO_CLAMPED" | "VECTOR" | "ALIGNED" | "FREE".
        keyframe_indices: Specific keyframe indices to set. If None, sets all.

    Returns:
        {"object_name": str, "affected": int, "handle_type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        if not obj.animation_data or not obj.animation_data.action:
            raise ValueError(f"Object {object_name} has no animation")

        action = obj.animation_data.action
        affected = 0

        VALID_HANDLE_TYPES = {"AUTO", "AUTO_CLAMPED", "VECTOR", "ALIGNED", "FREE"}
        if handle_type not in VALID_HANDLE_TYPES:
            raise ValueError(f"Invalid handle_type. Valid: {VALID_HANDLE_TYPES}")

        for fcurve in action.fcurves:
            if fcurve.data_path == data_path and fcurve.array_index == array_index:
                keyframes = fcurve.keyframe_points

                indices = keyframe_indices if keyframe_indices else range(len(keyframes))

                for idx in indices:
                    if 0 <= idx < len(keyframes):
                        kp = keyframes[idx]
                        kp.handle_left_type = handle_type
                        kp.handle_right_type = handle_type
                        affected += 1

        return {
            "ok": True,
            "object_name": object_name,
            "affected": affected,
            "handle_type": handle_type,
        }
    except Exception as e:
        raise fmt_err("set_keyframe_handle_type failed", e)


def copy_keyframes(
    source_object: str,
    data_path: str,
    array_index: int = -1,
    frame_start: Optional[float] = None,
    frame_end: Optional[float] = None,
) -> Dict[str, Any]:
    """Copy keyframes to internal clipboard for pasting.

    Args:
        source_object: Source object name.
        data_path: Property path to copy.
        array_index: Array index (-1 for all). 0=x, 1=y, 2=z.
        frame_start: Start frame (optional).
        frame_end: End frame (optional).

    Returns:
        {"source_object": str, "copied": int, "data_path": str}
    """
    try:
        obj = bpy.data.objects.get(source_object)
        if not obj:
            raise ValueError(f"Object not found: {source_object}")

        if not obj.animation_data or not obj.animation_data.action:
            raise ValueError(f"Object {source_object} has no animation")

        # Store in scene custom properties for internal clipboard
        if "vbf_animation_clipboard" not in bpy.context.scene:
            bpy.context.scene["vbf_animation_clipboard"] = {}

        clipboard = bpy.context.scene["vbf_animation_clipboard"]
        clipboard["source_object"] = source_object
        clipboard["data_path"] = data_path
        clipboard["array_index"] = array_index
        clipboard["frame_start"] = frame_start
        clipboard["frame_end"] = frame_end
        clipboard["source_action"] = obj.animation_data.action.name

        action = obj.animation_data.action
        copied_count = 0

        for fcurve in action.fcurves:
            if fcurve.data_path == data_path:
                if array_index == -1 or fcurve.array_index == array_index:
                    keyframes = []
                    for kp in fcurve.keyframe_points:
                        if frame_start is not None and kp.co.x < frame_start:
                            continue
                        if frame_end is not None and kp.co.x > frame_end:
                            continue
                        keyframes.append({
                            "frame": float(kp.co.x),
                            "value": float(kp.co.y),
                            "interpolation": kp.interpolation,
                            "handle_left": (float(kp.handle_left.x), float(kp.handle_left.y)),
                            "handle_right": (float(kp.handle_right.x), float(kp.handle_right.y)),
                        })
                        copied_count += 1

        clipboard["keyframes"] = keyframes

        return {
            "ok": True,
            "source_object": source_object,
            "copied": copied_count,
            "data_path": data_path,
            "frame_range": [frame_start, frame_end] if frame_start else "all",
        }
    except Exception as e:
        raise fmt_err("copy_keyframes failed", e)


def paste_keyframes(
    target_object: str,
    frame_offset: float = 0.0,
    data_path_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Paste copied keyframes to target object.

    Args:
        target_object: Target object name.
        frame_offset: Frame offset for pasted keyframes.
        data_path_mapping: Optional mapping of source data_path to target.
                          e.g., {"location": "location", "rotation_euler": "rotation_euler"}

    Returns:
        {"target_object": str, "pasted": int, "frame_offset": float}
    """
    try:
        if "vbf_animation_clipboard" not in bpy.context.scene:
            raise ValueError("No keyframes in clipboard. Use copy_keyframes first.")

        clipboard = bpy.context.scene["vbf_animation_clipboard"]
        obj = bpy.data.objects.get(target_object)
        if not obj:
            raise ValueError(f"Object not found: {target_object}")

        # Ensure animation data
        if not obj.animation_data:
            obj.animation_data_create()
        if not obj.animation_data.action:
            action = bpy.data.actions.new(name=f"{target_object}Action")
            obj.animation_data.action = action

        action = obj.animation_data.action

        # Get data path (use mapping if provided)
        source_data_path = clipboard.get("data_path", "")
        target_data_path = data_path_mapping.get(source_data_path, source_data_path) if data_path_mapping else source_data_path

        # Find or create fcurve
        fcurve = None
        for fc in action.fcurves:
            if fc.data_path == target_data_path:
                fcurve = fc
                break

        if not fcurve:
            fcurve = action.fcurves.new(path=target_data_path, index=0)

        keyframes = clipboard.get("keyframes", [])
        pasted = 0

        for kp_data in keyframes:
            frame = kp_data["frame"] + frame_offset
            value = kp_data["value"]

            # Create keyframe
            keyframe = fcurve.keyframe_points.insert(frame, value)
            keyframe.interpolation = kp_data.get("interpolation", "LINEAR")
            # Note: Handle copying requires more complex logic

            pasted += 1

        return {
            "ok": True,
            "target_object": target_object,
            "pasted": pasted,
            "frame_offset": frame_offset,
            "data_path": target_data_path,
        }
    except Exception as e:
        raise fmt_err("paste_keyframes failed", e)


def bake_animation(
    object_name: str,
    frame_start: int,
    frame_end: int,
    bake_types: List[str] = ["LOCATION", "ROTATION", "SCALE"],
    only_selected: bool = False,
) -> Dict[str, Any]:
    """Bake animation/physics to keyframes.

    YouTube source: HulkFatZerg EP13 平衡动画，物理模拟需要烘焙.
    Essential for: physics simulation, armature constraints, drivers.

    Args:
        object_name: Object to bake.
        frame_start: Start frame.
        frame_end: End frame.
        bake_types: List of types to bake: "LOCATION" | "ROTATION" | "SCALE" | "BONE".
        only_selected: Only bake selected bones (if armature).

    Returns:
        {"object_name": str, "baked_frames": int, "types": List[str]}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        bake_options = set()
        for bt in bake_types:
            bake_options.add(bt.upper())

        # Determine bake type
        if "BONE" in bake_options and obj.type == "ARMATURE":
            # Bake armature action
            bpy.ops.nla.bake(
                frame_start=frame_start,
                frame_end=frame_end,
                only_selected=only_selected,
                bake_types={"POSE"},
            )
        else:
            # Bake object transforms
            bpy.ops.nla.bake(
                frame_start=frame_start,
                frame_end=frame_end,
                only_selected=False,
                bake_types={"OBJECT"},
            )

        return {
            "ok": True,
            "object_name": object_name,
            "baked_frames": frame_end - frame_start + 1,
            "types": list(bake_types),
        }
    except Exception as e:
        raise fmt_err("bake_animation failed", e)


def set_action(
    object_name: str,
    action_name: str,
) -> Dict[str, Any]:
    """Set an action (animation clip) on an object.

    Actions are reusable animation clips in Blender.
    Essential for: character animation libraries, animation mixing.

    Args:
        object_name: Target object.
        action_name: Name of the action to set.

    Returns:
        {"object_name": str, "action": str, "active": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        action = bpy.data.actions.get(action_name)
        if not action:
            raise ValueError(f"Action not found: {action_name}")

        # Ensure animation data
        if not obj.animation_data:
            obj.animation_data_create()

        obj.animation_data.action = action

        return {
            "ok": True,
            "object_name": object_name,
            "action": action_name,
            "active": True,
        }
    except Exception as e:
        raise fmt_err("set_action failed", e)


def create_action(
    action_name: str,
    object_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new animation action.

    Args:
        action_name: Name for the new action.
        object_name: Optional object to assign the action to immediately.

    Returns:
        {"action_name": str, "assigned_to": Optional[str]}
    """
    try:
        # Check if action exists
        if action_name in bpy.data.actions:
            action = bpy.data.actions[action_name]
        else:
            action = bpy.data.actions.new(name=action_name)

        assigned_to = None
        if object_name:
            obj = bpy.data.objects.get(object_name)
            if obj:
                if not obj.animation_data:
                    obj.animation_data_create()
                obj.animation_data.action = action
                assigned_to = object_name

        return {
            "ok": True,
            "action_name": action.name,
            "assigned_to": assigned_to,
        }
    except Exception as e:
        raise fmt_err("create_action failed", e)


def list_actions() -> Dict[str, Any]:
    """List all available animation actions.

    Returns:
        {"actions": [{"name": str, "frame_range": [start, end]}]}
    """
    try:
        actions = []
        for action in bpy.data.actions:
            actions.append({
                "name": action.name,
                "frame_range": [action.frame_range[0], action.frame_range[1]] if action.frame_range else [0, 0],
                "user_count": action.users,
            })

        return {
            "ok": True,
            "actions": actions,
            "count": len(actions),
        }
    except Exception as e:
        raise fmt_err("list_actions failed", e)


def delete_action(
    action_name: str,
) -> Dict[str, Any]:
    """Delete an animation action.

    Args:
        action_name: Name of action to delete.

    Returns:
        {"action_name": str, "deleted": bool}
    """
    try:
        action = bpy.data.actions.get(action_name)
        if not action:
            raise ValueError(f"Action not found: {action_name}")

        bpy.data.actions.remove(action)

        return {
            "ok": True,
            "action_name": action_name,
            "deleted": True,
        }
    except Exception as e:
        raise fmt_err("delete_action failed", e)


def nla_add_strip(
    object_name: str,
    action_name: str,
    start_frame: int,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an action strip to NLA (Non-Linear Animation) editor.

    NLA allows combining and layering multiple animations.

    Args:
        object_name: Target object.
        action_name: Action to add.
        start_frame: Frame to start the strip.
        name: Optional custom name for the strip.

    Returns:
        {"object_name": str, "strip_name": str, "action": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        action = bpy.data.actions.get(action_name)
        if not action:
            raise ValueError(f"Action not found: {action_name}")

        # Ensure animation data
        if not obj.animation_data:
            obj.animation_data_create()

        # Ensure NLA track exists
        if not obj.animation_data.nla_tracks:
            track = obj.animation_data.nla_tracks.new()
        else:
            track = obj.animation_data.nla_tracks[0]

        # Add strip
        strip = track.strips.new(
            name=name or action_name,
            start=start_frame,
            action=action,
        )

        return {
            "ok": True,
            "object_name": object_name,
            "strip_name": strip.name,
            "action": action_name,
            "start_frame": start_frame,
        }
    except Exception as e:
        raise fmt_err("nla_add_strip failed", e)


def set_nla_strip_properties(
    object_name: str,
    strip_name: str,
    blend_type: str = "REPLACE",
    influence: float = 1.0,
    repeat: int = 1,
) -> Dict[str, Any]:
    """Set properties for an NLA strip.

    Args:
        object_name: Target object.
        strip_name: NLA strip name.
        blend_type: "REPLACE" | "ADD" | "SUBTRACT" | "MULTIPLY".
        influence: Weight (0.0-1.0).
        repeat: Number of repetitions.

    Returns:
        {"object_name": str, "strip_name": str, "blend_type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or not obj.animation_data:
            raise ValueError(f"Object {object_name} has no animation")

        for track in obj.animation_data.nla_tracks:
            for strip in track.strips:
                if strip.name == strip_name:
                    strip.blend_type = blend_type
                    strip.influence = influence
                    strip.repeat = repeat

                    return {
                        "ok": True,
                        "object_name": object_name,
                        "strip_name": strip_name,
                        "blend_type": blend_type,
                        "influence": influence,
                    }

        raise ValueError(f"NLA strip '{strip_name}' not found")
    except Exception as e:
        raise fmt_err("set_nla_strip_properties failed", e)
