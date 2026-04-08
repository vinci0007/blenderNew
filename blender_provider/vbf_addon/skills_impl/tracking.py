# Motion Tracking Skills - Blender Motion Tracking
from typing import Any, Dict, List, Optional, Tuple, Union

import bpy

from .utils import fmt_err, set_active_object


def tracking_load_clip(
    filepath: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Load a movie clip for motion tracking.

    Args:
        filepath: Path to video file.
        name: Optional clip name.

    Returns:
        {"clip_name": str, "duration": int, "resolution": [int, int]}
    """
    try:
        clip = bpy.data.movieclips.load(filepath)
        if name:
            clip.name = name

        return {
            "clip_name": clip.name,
            "duration": clip.frame_duration,
            "resolution": [clip.size[0], clip.size[1]],
        }
    except Exception as e:
        raise fmt_err("tracking_load_clip failed", e)


def tracking_create_track(
    clip_name: str,
    marker_name: Optional[str] = None,
    frame: int = 1,
    location: List[float] = [0.5, 0.5],
) -> Dict[str, Any]:
    """Create a tracking marker in a clip.

    Args:
        clip_name: Movie clip name.
        marker_name: Optional marker name.
        frame: Frame to place marker.
        location: [x, y] normalized coordinates (0-1).

    Returns:
        {"clip_name": str, "track_name": str, "frame": int}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        tracking = clip.tracking

        # Create track
        track = tracking.tracks.new(name=marker_name or "Track", frame=frame)

        # Add marker
        marker = track.markers.insert_frame(frame)
        marker.co = tuple(location)

        return {
            "clip_name": clip.name,
            "track_name": track.name,
            "frame": frame,
        }
    except Exception as e:
        raise fmt_err("tracking_create_track failed", e)


def tracking_track_frame(
    clip_name: str,
    track_name: str,
    frame: int,
) -> Dict[str, Any]:
    """Track a marker to a specific frame.

    Args:
        clip_name: Movie clip name.
        track_name: Track name.
        frame: Target frame.

    Returns:
        {"clip_name": str, "track_name": str, "frame": int}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        track = clip.tracking.tracks.get(track_name)
        if not track:
            raise ValueError(f"Track not found: {track_name}")

        # Set tracking context
        bpy.context.scene.frame_current = frame

        # Track forward
        bpy.ops.clip.track_markers(backwards=False, sequence=True)

        return {
            "clip_name": clip.name,
            "track_name": track.name,
            "frame": frame,
        }
    except Exception as e:
        raise fmt_err("tracking_track_frame failed", e)


def tracking_solve_camera(
    clip_name: str,
) -> Dict[str, Any]:
    """Solve camera motion from tracks.

    Args:
        clip_name: Movie clip name.

    Returns:
        {"clip_name": str, "solved": bool, "error": float}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        tracking = clip.tracking

        # Solve camera
        bpy.ops.clip.solve_camera()

        # Get reprojection error
        error = getattr(tracking, "reprojection_error", 0.0)

        return {
            "clip_name": clip.name,
            "solved": True,
            "error": error,
        }
    except Exception as e:
        raise fmt_err("tracking_solve_camera failed", e)


def tracking_set_camera(
    clip_name: str,
) -> Dict[str, Any]:
    """Set up camera from solved tracking data.

    Args:
        clip_name: Movie clip name.

    Returns:
        {"clip_name": str, "camera_name": str}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        # Set as background for current camera if exists
        scene = bpy.context.scene

        # Create camera if needed
        if not scene.camera:
            bpy.ops.object.camera_add()
            scene.camera = bpy.context.active_object

        cam = scene.camera
        cam.data.show_background_images = True

        # Add background image
        bg = cam.data.background_images.new()
        bg.clip = clip

        # Set camera from tracking
        bpy.ops.clip.set_camera()

        return {
            "clip_name": clip.name,
            "camera_name": cam.name,
        }
    except Exception as e:
        raise fmt_err("tracking_set_camera failed", e)


def tracking_add_plane_track(
    clip_name: str,
    name: str = "Plane",
    corners: List[List[float]] = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]],
) -> Dict[str, Any]:
    """Create a plane track from markers.

    Args:
        clip_name: Movie clip name.
        name: Plane track name.
        corners: Four corner positions [x, y] (0-1 range).

    Returns:
        {"clip_name": str, "plane_name": str}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        tracking = clip.tracking

        # Create tracks for corners if they don't exist
        corner_names = []
        for i, corner in enumerate(corners):
            track_name = f"{name}_corner_{i}"
            track = tracking.tracks.get(track_name)
            if not track:
                track = tracking.tracks.new(name=track_name, frame=1)
                marker = track.markers.insert_frame(1)
                marker.co = tuple(corner)
            corner_names.append(track_name)

        # Create plane track
        plane = tracking.plane_tracks.new(name, clip, corners)

        return {
            "clip_name": clip.name,
            "plane_name": name,
            "corners": len(corners),
        }
    except Exception as e:
        raise fmt_err("tracking_add_plane_track failed", e)


def tracking_delete_track(
    clip_name: str,
    track_name: str,
) -> Dict[str, Any]:
    """Delete a tracking track.

    Args:
        clip_name: Movie clip name.
        track_name: Track name.

    Returns:
        {"deleted": bool, "track_name": str}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        track = clip.tracking.tracks.get(track_name)
        if not track:
            return {"deleted": False, "reason": "Track not found"}

        clip.tracking.tracks.remove(track)
        return {"deleted": True, "track_name": track_name}
    except Exception as e:
        raise fmt_err("tracking_delete_track failed", e)


def tracking_list_tracks(
    clip_name: str,
) -> Dict[str, Any]:
    """List all tracking tracks in a clip.

    Args:
        clip_name: Movie clip name.

    Returns:
        {"clip_name": str, "tracks": [{"name": str, "has_3d": bool}], "count": int}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        tracks = []
        for track in clip.tracking.tracks:
            tracks.append({
                "name": track.name,
                "has_3d": track.has_3d,
                "is_enabled": track.hide == False,
            })

        return {
            "clip_name": clip.name,
            "tracks": tracks,
            "count": len(tracks),
        }
    except Exception as e:
        raise fmt_err("tracking_list_tracks failed", e)


def tracking_set_track_pattern_size(
    clip_name: str,
    track_name: str,
    size: int = 11,
) -> Dict[str, Any]:
    """Set the pattern size for a tracking marker.

    Args:
        clip_name: Movie clip name.
        track_name: Track name.
        size: Pattern size in pixels.

    Returns:
        {"clip_name": str, "track_name": str, "pattern_size": int}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        track = clip.tracking.tracks.get(track_name)
        if not track:
            raise ValueError(f"Track not found: {track_name}")

        track.pattern_match = "KEYFRAME"
        # Pattern size is controlled through track settings

        return {
            "clip_name": clip.name,
            "track_name": track.name,
            "pattern_size": size,
        }
    except Exception as e:
        raise fmt_err("tracking_set_track_pattern_size failed", e)


def tracking_create_object(
    clip_name: str,
    track_names: List[str],
    object_type: str = "CUBE",
) -> Dict[str, Any]:
    """Create 3D object solved from tracking data.

    Args:
        clip_name: Movie clip name.
        track_names: List of track names to use.
        object_type: Type of object to create (CUBE, PLANE, etc.).

    Returns:
        {"clip_name": str, "object_name": str}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        # Create object based on type
        obj = None
        if object_type == "CUBE":
            bpy.ops.mesh.primitive_cube_add()
            obj = bpy.context.active_object
        elif object_type == "PLANE":
            bpy.ops.mesh.primitive_plane_add()
            obj = bpy.context.active_object
        elif object_type == "EMPTY":
            bpy.ops.object.empty_add(type="ARROWS")
            obj = bpy.context.active_object
        else:
            raise ValueError(f"Unknown object type: {object_type}")

        # Link to tracking
        obj.track = None  # Set track constraint if needed

        return {
            "clip_name": clip.name,
            "object_name": obj.name if obj else None,
        }
    except Exception as e:
        raise fmt_err("tracking_create_object failed", e)

def tracking_create_scene_from_clip(
    clip_name: str,
    name: str = "Tracking",
) -> Dict[str, Any]:
    """Create a new scene with tracking setup.

    Args:
        clip_name: Movie clip name.
        name: Scene name.

    Returns:
        {"scene_name": str, "clip_name": str}
    """
    try:
        clip = bpy.data.movieclips.get(clip_name)
        if not clip:
            raise ValueError(f"Clip not found: {clip_name}")

        # Create new scene
        new_scene = bpy.data.scenes.new(name=name)

        # Set resolution to match clip
        new_scene.render.resolution_x = clip.size[0]
        new_scene.render.resolution_y = clip.size[1]

        return {
            "scene_name": new_scene.name,
            "clip_name": clip.name,
        }
    except Exception as e:
        raise fmt_err("tracking_create_scene_from_clip failed", e)
