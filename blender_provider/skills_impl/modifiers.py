from typing import Any, Dict

import bpy  # type: ignore

from .utils import fmt_err, set_active_object


def add_modifier_bevel(object_name: str, width: float = 0.03, segments: int = 3) -> Dict[str, Any]:
    """Add a Bevel modifier to an object for rounded edges.

    Args:
        object_name: Name of the object to modify.
        width: Bevel width in Blender units. Defaults to 0.03.
        segments: Number of bevel loop cuts (higher = smoother). Defaults to 3.

    Returns:
        {"object_name": str, "modifier_name": str}.
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        mod = obj.modifiers.new(name="VBF_Bevel", type="BEVEL")
        mod.width = float(width)
        mod.segments = int(segments)
        mod.limit_method = "ANGLE"
        return {"object_name": obj.name, "modifier_name": mod.name}
    except Exception as e:
        raise fmt_err("add_modifier_bevel failed", e)


def add_modifier_subdivision(object_name: str, levels: int = 2, render_levels: int = 3) -> Dict[str, Any]:
    """Add a Subdivision Surface modifier to an object for smooth geometry.

    Args:
        object_name: Name of the object to modify.
        levels: Viewport subdivision level. Defaults to 2.
        render_levels: Render subdivision level. Defaults to 3.

    Returns:
        {"object_name": str, "modifier_name": str}.
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        mod = obj.modifiers.new(name="VBF_Subdivision", type="SUBSURF")
        mod.levels = int(levels)
        mod.render_levels = int(render_levels)
        return {"object_name": obj.name, "modifier_name": mod.name}
    except Exception as e:
        raise fmt_err("add_modifier_subdivision failed", e)


def apply_modifier(object_name: str, modifier_name: str) -> Dict[str, Any]:
    """Apply (bake) a modifier on an object, making its effect permanent.

    Args:
        object_name: Name of the object that has the modifier.
        modifier_name: Exact name of the modifier to apply.

    Returns:
        {"object_name": str, "modifier_name": str}.
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        if modifier_name not in [m.name for m in obj.modifiers]:
            raise ValueError(f"Modifier not found: {modifier_name}")
        set_active_object(obj)
        bpy.ops.object.modifier_apply(modifier=modifier_name)
        return {"object_name": obj.name, "modifier_name": modifier_name}
    except Exception as e:
        raise fmt_err("apply_modifier failed", e)

