# Video Sequencer Skills - Blender Video Sequence Editor
from typing import Any, Dict, List, Optional, Tuple, Union

import bpy

from .utils import fmt_err, set_active_object


def sequencer_create_scene(
    name: str = "Video Sequence Editor",
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
) -> Dict[str, Any]:
    """Create a new scene configured for video editing.

    Args:
        name: Scene name.
        width: Resolution width.
        height: Resolution height.
        fps: Frame rate.

    Returns:
        {"scene_name": str, "resolution": [int, int], "fps": int}
    """
    try:
        # Create new scene
        new_scene = bpy.data.scenes.new(name=name)
        new_scene.render.resolution_x = width
        new_scene.render.resolution_y = height
        new_scene.render.fps = fps

        # Switch to VSE
        new_scene.sequence_editor_create()

        return {
            "scene_name": new_scene.name,
            "resolution": [width, height],
            "fps": fps,
        }
    except Exception as e:
        raise fmt_err("sequencer_create_scene failed", e)


def sequencer_add_movie_strip(
    filepath: str,
    channel: int = 1,
    frame_start: int = 1,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a movie strip to the sequencer.

    Args:
        filepath: Path to video file.
        channel: Channel number.
        frame_start: Start frame.
        name: Optional strip name.

    Returns:
        {"strip_name": str, "channel": int, "duration": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            scene.sequence_editor_create()

        seq_ed = scene.sequence_editor

        # Add movie strip
        strip = seq_ed.sequences.new_movie(
            name=name or "Movie",
            filepath=filepath,
            channel=channel,
            frame_start=frame_start,
        )

        return {
            "strip_name": strip.name,
            "channel": channel,
            "duration": strip.frame_duration,
        }
    except Exception as e:
        raise fmt_err("sequencer_add_movie_strip failed", e)


def sequencer_add_image_strip(
    filepath: str,
    channel: int = 1,
    frame_start: int = 1,
    frame_end: Optional[int] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an image strip to the sequencer.

    Args:
        filepath: Path to image file.
        channel: Channel number.
        frame_start: Start frame.
        frame_end: End frame (default: start + 24).
        name: Optional strip name.

    Returns:
        {"strip_name": str, "channel": int, "frames": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            scene.sequence_editor_create()

        seq_ed = scene.sequence_editor
        end = frame_end or (frame_start + 24)

        strip = seq_ed.sequences.new_image(
            name=name or "Image",
            filepath=filepath,
            channel=channel,
            frame_start=frame_start,
        )

        # Set duration
        strip.frame_final_duration = end - frame_start

        return {
            "strip_name": strip.name,
            "channel": channel,
            "frames": strip.frame_final_duration,
        }
    except Exception as e:
        raise fmt_err("sequencer_add_image_strip failed", e)


def sequencer_add_sound_strip(
    filepath: str,
    channel: int = 2,
    frame_start: int = 1,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a sound strip to the sequencer.

    Args:
        filepath: Path to audio file.
        channel: Channel number.
        frame_start: Start frame.
        name: Optional strip name.

    Returns:
        {"strip_name": str, "channel": int, "duration": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            scene.sequence_editor_create()

        seq_ed = scene.sequence_editor

        strip = seq_ed.sequences.new_sound(
            name=name or "Sound",
            filepath=filepath,
            channel=channel,
            frame_start=frame_start,
        )

        return {
            "strip_name": strip.name,
            "channel": channel,
            "duration": strip.frame_duration,
        }
    except Exception as e:
        raise fmt_err("sequencer_add_sound_strip failed", e)


def sequencer_add_text_strip(
    text: str,
    channel: int = 3,
    frame_start: int = 1,
    frame_end: int = 25,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a text strip to the sequencer.

    Args:
        text: Text content.
        channel: Channel number.
        frame_start: Start frame.
        frame_end: End frame.
        name: Optional strip name.

    Returns:
        {"strip_name": str, "channel": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            scene.sequence_editor_create()

        seq_ed = scene.sequence_editor

        strip = seq_ed.sequences.new_effect(
            name=name or "Text",
            type="TEXT",
            channel=channel,
            frame_start=frame_start,
            frame_end=frame_end,
        )

        strip.text = text

        return {
            "strip_name": strip.name,
            "channel": channel,
        }
    except Exception as e:
        raise fmt_err("sequencer_add_text_strip failed", e)


def sequencer_set_strip_position(
    strip_name: str,
    channel: int,
    frame_start: int,
) -> Dict[str, Any]:
    """Move a strip to new position.

    Args:
        strip_name: Strip name.
        channel: New channel number.
        frame_start: New start frame.

    Returns:
        {"strip_name": str, "channel": int, "frame_start": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            raise ValueError("No sequence editor")

        strip = scene.sequence_editor.sequences.get(strip_name)
        if not strip:
            raise ValueError(f"Strip not found: {strip_name}")

        strip.channel = channel
        strip.frame_start = frame_start

        return {
            "strip_name": strip.name,
            "channel": channel,
            "frame_start": frame_start,
        }
    except Exception as e:
        raise fmt_err("sequencer_set_strip_position failed", e)


def sequencer_delete_strip(
    strip_name: str,
) -> Dict[str, Any]:
    """Delete a strip from the sequencer.

    Args:
        strip_name: Strip name to delete.

    Returns:
        {"deleted": bool, "strip_name": str}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            raise ValueError("No sequence editor")

        seq_ed = scene.sequence_editor
        strip = seq_ed.sequences.get(strip_name)
        if not strip:
            return {"deleted": False, "reason": "Strip not found"}

        seq_ed.sequences.remove(strip)
        return {"deleted": True, "strip_name": strip_name}
    except Exception as e:
        raise fmt_err("sequencer_delete_strip failed", e)


def sequencer_add_effect_strip(
    effect_type: str,
    channel: int,
    frame_start: int,
    frame_end: int,
    strip1: str,
    strip2: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an effect strip.

    Args:
        effect_type: Effect type ("CROSS", "ADD", "SUBTRACT", "ALPHA_OVER", "WIPE", etc.).
        channel: Channel number.
        frame_start: Start frame.
        frame_end: End frame.
        strip1: First input strip name.
        strip2: Second input strip name (for some effects).
        name: Optional strip name.

    Returns:
        {"strip_name": str, "type": str}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            scene.sequence_editor_create()

        seq_ed = scene.sequence_editor

        inputs = [seq_ed.sequences[strip1]]
        if strip2:
            inputs.append(seq_ed.sequences[strip2])

        strip = seq_ed.sequences.new_effect(
            name=name or "Effect",
            type=effect_type,
            channel=channel,
            frame_start=frame_start,
            frame_end=frame_end,
            seq1=inputs[0],
            seq2=inputs[1] if len(inputs) > 1 else None,
        )

        return {"strip_name": strip.name, "type": effect_type}
    except Exception as e:
        raise fmt_err("sequencer_add_effect_strip failed", e)


def sequencer_set_strip_opacity(
    strip_name: str,
    opacity: float,
) -> Dict[str, Any]:
    """Set opacity for a strip.

    Args:
        strip_name: Strip name.
        opacity: Opacity 0.0-1.0.

    Returns:
        {"strip_name": str, "opacity": float}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            raise ValueError("No sequence editor")

        strip = scene.sequence_editor.sequences.get(strip_name)
        if not strip:
            raise ValueError(f"Strip not found: {strip_name}")

        strip.blend_alpha = opacity

        return {"strip_name": strip.name, "opacity": opacity}
    except Exception as e:
        raise fmt_err("sequencer_set_strip_opacity failed", e)


def sequencer_set_strip_volume(
    strip_name: str,
    volume: float,
) -> Dict[str, Any]:
    """Set volume for a sound strip.

    Args:
        strip_name: Sound strip name.
        volume: Volume 0.0-1.0.

    Returns:
        {"strip_name": str, "volume": float}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            raise ValueError("No sequence editor")

        strip = scene.sequence_editor.sequences.get(strip_name)
        if not strip:
            raise ValueError(f"Strip not found: {strip_name}")

        if strip.type == "SOUND":
            strip.volume = volume
            return {"strip_name": strip.name, "volume": volume}
        else:
            return {"error": "Strip is not a sound strip", "type": strip.type}
    except Exception as e:
        raise fmt_err("sequencer_set_strip_volume failed", e)


def sequencer_list_strips() -> Dict[str, Any]:
    """List all strips in the sequencer.

    Returns:
        {"strips": [{"name": str, "type": str, "channel": int, "start": int}], "count": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            return {"strips": [], "count": 0}

        strips = []
        for strip in scene.sequence_editor.sequences:
            strips.append({
                "name": strip.name,
                "type": strip.type,
                "channel": strip.channel,
                "start": strip.frame_start,
                "duration": getattr(strip, "frame_duration", strip.frame_final_duration),
            })

        return {"strips": strips, "count": len(strips)}
    except Exception as e:
        raise fmt_err("sequencer_list_strips failed", e)


def sequencer_meta_strip_create(
    strip_names: List[str],
    name: str = "Meta",
) -> Dict[str, Any]:
    """Create a meta strip from multiple strips.

    Args:
        strip_names: List of strip names to include.
        name: Name for the meta strip.

    Returns:
        {"strip_name": str, "count": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.sequence_editor:
            raise ValueError("No sequence editor")

        seq_ed = scene.sequence_editor

        # Select strips
        bpy.ops.sequencer.select_all(action="DESELECT")
        for strip_name in strip_names:
            strip = seq_ed.sequences.get(strip_name)
            if strip:
                strip.select = True

        # Make meta
        bpy.ops.sequencer.meta_make()

        # Rename
        meta = seq_ed.active_strip
        if meta:
            meta.name = name

        return {"strip_name": name, "count": len(strip_names)}
    except Exception as e:
        raise fmt_err("sequencer_meta_strip_create failed", e)
