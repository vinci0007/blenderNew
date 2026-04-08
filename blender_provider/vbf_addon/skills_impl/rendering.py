# Rendering & Export Skills - Blender Rendering and Output
from typing import Any, Dict, List, Optional, Tuple, Union

import bpy

from .utils import fmt_err


def render_image(
    filepath: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Dict[str, Any]:
    """Render a single image.

    Args:
        filepath: Optional output path (default: scene setting).
        width: Optional render width.
        height: Optional render height.

    Returns:
        {"rendered": bool, "filepath": str, "time": float}
    """
    try:
        scene = bpy.context.scene

        if width:
            scene.render.resolution_x = width
        if height:
            scene.render.resolution_y = height

        if filepath:
            scene.render.filepath = filepath

        import time
        start = time.time()
        bpy.ops.render.render(write_file=True)
        elapsed = time.time() - start

        return {
            "rendered": True,
            "filepath": scene.render.filepath,
            "time": elapsed,
        }
    except Exception as e:
        raise fmt_err("render_image failed", e)


def set_render_engine(
    engine: str = "BLENDER_EEVEE_NEXT",
) -> Dict[str, Any]:
    """Set the active render engine.

    Args:
        engine: Render engine (BLENDER_EEVEE_NEXT, CYCLES, BLENDER_WORKBENCH).

    Returns:
        {"engine": str}
    """
    try:
        scene = bpy.context.scene
        scene.render.engine = engine
        return {"engine": scene.render.engine}
    except Exception as e:
        raise fmt_err("set_render_engine failed", e)


def set_render_resolution(
    width: int = 1920,
    height: int = 1080,
    scale: int = 100,
) -> Dict[str, Any]:
    """Set render resolution.

    Args:
        width: Resolution width.
        height: Resolution height.
        scale: Resolution percentage (1-100).

    Returns:
        {"resolution": [int, int], "scale": int}
    """
    try:
        scene = bpy.context.scene
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.resolution_percentage = scale

        return {
            "resolution": [width, height],
            "scale": scale,
        }
    except Exception as e:
        raise fmt_err("set_render_resolution failed", e)


def set_frame_range(
    start: int = 1,
    end: int = 250,
) -> Dict[str, Any]:
    """Set animation frame range.

    Args:
        start: Start frame.
        end: End frame.

    Returns:
        {"frame_range": [int, int]}
    """
    try:
        scene = bpy.context.scene
        scene.frame_start = start
        scene.frame_end = end

        return {"frame_range": [start, end]}
    except Exception as e:
        raise fmt_err("set_frame_range failed", e)


def export_obj(
    filepath: str,
    selected_only: bool = True,
) -> Dict[str, Any]:
    """Export scene or selection as OBJ.

    Args:
        filepath: Output path (.obj).
        selected_only: Export only selected objects.

    Returns:
        {"exported": bool, "filepath": str}
    """
    try:
        bpy.ops.wm.obj_export(
            filepath=filepath,
            export_selected_objects=selected_only,
        )
        return {"exported": True, "filepath": filepath}
    except Exception as e:
        raise fmt_err("export_obj failed", e)


def export_fbx(
    filepath: str,
    selected_only: bool = True,
) -> Dict[str, Any]:
    """Export scene or selection as FBX.

    Args:
        filepath: Output path (.fbx).
        selected_only: Export only selected objects.

    Returns:
        {"exported": bool, "filepath": str}
    """
    try:
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            use_selection=selected_only,
        )
        return {"exported": True, "filepath": filepath}
    except Exception as e:
        raise fmt_err("export_fbx failed", e)


def export_gltf(
    filepath: str,
    export_format: str = "GLB",
) -> Dict[str, Any]:
    """Export scene as glTF/glB.

    Args:
        filepath: Output path.
        export_format: "GLB", "GLTF_SEPARATE", or "GLTF_EMBEDDED".

    Returns:
        {"exported": bool, "filepath": str}
    """
    try:
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format=export_format,
        )
        return {"exported": True, "filepath": filepath}
    except Exception as e:
        raise fmt_err("export_gltf failed", e)


def import_obj(
    filepath: str,
) -> Dict[str, Any]:
    """Import OBJ file.

    Args:
        filepath: Path to .obj file.

    Returns:
        {"imported": bool, "filepath": str}
    """
    try:
        bpy.ops.wm.obj_import(filepath=filepath)
        return {"imported": True, "filepath": filepath}
    except Exception as e:
        raise fmt_err("import_obj failed", e)


def import_fbx(
    filepath: str,
) -> Dict[str, Any]:
    """Import FBX file.

    Args:
        filepath: Path to .fbx file.

    Returns:
        {"imported": bool, "filepath": str}
    """
    try:
        bpy.ops.import_scene.fbx(filepath=filepath)
        return {"imported": True, "filepath": filepath}
    except Exception as e:
        raise fmt_err("import_fbx failed", e)


def import_gltf(
    filepath: str,
) -> Dict[str, Any]:
    """Import glTF/glB file.

    Args:
        filepath: Path to file.

    Returns:
        {"imported": bool, "filepath": str}
    """
    try:
        bpy.ops.import_scene.gltf(filepath=filepath)
        return {"imported": True, "filepath": filepath}
    except Exception as e:
        raise fmt_err("import_gltf failed", e)


def set_render_output(
    filepath: str,
    file_format: str = "PNG",
) -> Dict[str, Any]:
    """Set render output settings.

    Args:
        filepath: Output path.
        file_format: File format (PNG, JPEG, EXR, etc.).

    Returns:
        {"filepath": str, "format": str}
    """
    try:
        scene = bpy.context.scene
        scene.render.filepath = filepath
        scene.render.image_settings.file_format = file_format

        return {"filepath": filepath, "format": file_format}
    except Exception as e:
        raise fmt_err("set_render_output failed", e)


def enable_pass(
    pass_type: str,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Enable/disable a render pass.

    Args:
        pass_type: Pass type (COMBINED, Z, SHADOW, etc.).
        enabled: Enable the pass.

    Returns:
        {"pass_type": str, "enabled": bool}
    """
    try:
        scene = bpy.context.scene
        view_layer = scene.view_layers[0]

        # Map pass types to view layer attributes
        pass_map = {
            "Z": "use_pass_z",
            "MIST": "use_pass_mist",
            "NORMAL": "use_pass_normal",
            "VECTOR": "use_pass_vector",
            "UV": "use_pass_uv",
            "SHADOW": "use_pass_shadow",
            "AO": "use_pass_ambient_occlusion",
        }

        if pass_type.upper() in pass_map:
            setattr(view_layer, pass_map[pass_type.upper()], enabled)

        return {"pass_type": pass_type, "enabled": enabled}
    except Exception as e:
        raise fmt_err("enable_pass failed", e)


def set_cycles_samples(
    samples: int = 128,
    preview_samples: int = 32,
) -> Dict[str, Any]:
    """Set Cycles render samples.

    Args:
        samples: Final render samples.
        preview_samples: Viewport samples.

    Returns:
        {"samples": int, "preview_samples": int}
    """
    try:
        scene = bpy.context.scene
        scene.cycles.samples = samples
        scene.cycles.preview_samples = preview_samples

        return {"samples": samples, "preview_samples": preview_samples}
    except Exception as e:
        raise fmt_err("set_cycles_samples failed", e)


def set_cycles_denoise(
    enable: bool = True,
) -> Dict[str, Any]:
    """Enable/disable Cycles denoising.

    Args:
        enable: Enable denoising.

    Returns:
        {"denoise_enabled": bool}
    """
    try:
        scene = bpy.context.scene
        scene.cycles.use_denoising = enable

        return {"denoise_enabled": enable}
    except Exception as e:
        raise fmt_err("set_cycles_denoise failed", e)


def set_eevee_samples(
    samples: int = 16,
) -> Dict[str, Any]:
    """Set Eevee render samples.

    Args:
        samples: Render samples.

    Returns:
        {"samples": int}
    """
    try:
        scene = bpy.context.scene
        scene.eevee.taa_render_samples = samples

        return {"samples": samples}
    except Exception as e:
        raise fmt_err("set_eevee_samples failed", e)
