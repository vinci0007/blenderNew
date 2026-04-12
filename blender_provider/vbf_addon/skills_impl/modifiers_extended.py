# Extended Modifiers - YouTube Tutorial Analysis Based Additions
# Covers: solidify, array, mirror, boolean_modifier, shrinkwrap, curve
# Critical for hard-surface workflows (CG Boost tutorials)
from typing import Any, Dict, List, Optional

import bpy

from .utils import fmt_err, set_active_object


def add_modifier_solidify(
    object_name: str,
    thickness: float = 0.01,
    offset: float = -1.0,
    use_rim: bool = True,
    use_rim_only: bool = False,
    vertex_group: Optional[str] = None,
) -> Dict[str, Any]:
    """Add Solidify modifier to give mesh thickness.

    CRITICAL for hard-surface modeling: Creates panel lines and thickness
    from flat surfaces. Tutorial source: 5+ YouTube tutorials.

    Args:
        object_name: Target mesh object.
        thickness: Thickness amount.
        offset: Offset direction. -1.0 = inside, 0 = center, 1.0 = outside.
        use_rim: Fill rim edges.
        use_rim_only: Only fill rim, no thickness.
        vertex_group: Optional vertex group name for variable thickness.

    Returns:
        {"object_name": str, "modifier_name": str, "thickness": float}

    Example:
        # Create panel lines effect
        add_modifier_solidify("Panel", thickness=0.002, offset=0)

        # Inside thickness for walls
        add_modifier_solidify("Wall", thickness=0.1, offset=-1.0)
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        mod = obj.modifiers.new(name="Solidify", type="SOLIDIFY")
        mod.thickness = thickness
        mod.offset = offset
        mod.use_rim = use_rim
        mod.use_rim_only = use_rim_only

        if vertex_group and vertex_group in obj.vertex_groups:
            mod.vertex_group = vertex_group

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": mod.name,
            "modifier_type": "SOLIDIFY",
            "thickness": thickness,
            "offset": offset,
        }
    except Exception as e:
        raise fmt_err("add_modifier_solidify failed", e)


def add_modifier_array(
    object_name: str,
    count: int = 2,
    relative_offset: Optional[List[float]] = None,
    constant_offset: Optional[List[float]] = None,
    use_object_offset: bool = False,
    offset_object: Optional[str] = None,
    use_merge: bool = True,
    merge_threshold: float = 0.01,
) -> Dict[str, Any]:
    """Add Array modifier for repeating geometry.

    Essential for mechanical modeling: screws, ladders, railings, etc.
    Tutorial source: Multiple CG Boost tutorials.

    Args:
        object_name: Target mesh object.
        count: Number of copies.
        relative_offset: [x, y, z] relative offset (in object bounds).
        constant_offset: [x, y, z] constant offset (in Blender units).
        use_object_offset: Use another object for offset/rotation.
        offset_object: Name of offset object (if use_object_offset).
        use_merge: Merge vertices at array boundaries.
        merge_threshold: Distance for merging vertices.

    Returns:
        {"object_name": str, "modifier_name": str, "count": int}

    Example:
        # Linear array along X
        add_modifier_array("Screw", count=5, relative_offset=[1.5, 0, 0])

        # Radial array using empty
        add_modifier_array("Spoke", count=8, use_object_offset=True,
                          offset_object="Empty_Rotator")
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        mod = obj.modifiers.new(name="Array", type="ARRAY")
        mod.count = max(1, count)

        # Relative offset (default: X axis)
        if relative_offset:
            mod.use_relative_offset = True
            mod.relative_offset_displace = tuple(relative_offset)
        else:
            mod.use_relative_offset = True
            mod.relative_offset_displace = (1.0, 0.0, 0.0)

        # Constant offset
        if constant_offset:
            mod.use_constant_offset = True
            mod.constant_offset_displace = tuple(constant_offset)

        # Object offset (for radial arrays)
        if use_object_offset and offset_object:
            offset_obj = bpy.data.objects.get(offset_object)
            if offset_obj:
                mod.use_object_offset = True
                mod.offset_object = offset_obj

        # Merge settings
        mod.use_merge_vertices = use_merge
        mod.merge_threshold = merge_threshold

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": mod.name,
            "modifier_type": "ARRAY",
            "count": count,
            "relative_offset": relative_offset or [1.0, 0.0, 0.0],
        }
    except Exception as e:
        raise fmt_err("add_modifier_array failed", e)


def add_modifier_mirror(
    object_name: str,
    use_x: bool = True,
    use_y: bool = False,
    use_z: bool = False,
    mirror_object: Optional[str] = None,
    use_clip: bool = True,
    use_mirror_merge: bool = True,
    merge_threshold: float = 0.001,
) -> Dict[str, Any]:
    """Add Mirror modifier for symmetrical modeling.

    Most used modifier in hard-surface workflows. Enable clipping to
    prevent gaps at the mirror plane.

    Args:
        object_name: Target mesh object.
        use_x: Mirror across X axis.
        use_y: Mirror across Y axis.
        use_z: Mirror across Z axis.
        mirror_object: Object to use as mirror center (default: self).
        use_clip: Clip vertices to mirror plane (prevents gaps).
        use_mirror_merge: Merge vertices at mirror plane.
        merge_threshold: Distance for merging vertices.

    Returns:
        {"object_name": str, "modifier_name": str, "axes": List[str]}

    Example:
        # Standard X mirror with clipping
        add_modifier_mirror("Character", use_x=True, use_clip=True)

        # Mirror across another object
        add_modifier_mirror("Detail", mirror_object="Center_Empty")
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        mod = obj.modifiers.new(name="Mirror", type="MIRROR")
        mod.use_axis[0] = use_x
        mod.use_axis[1] = use_y
        mod.use_axis[2] = use_z
        mod.use_clip = use_clip
        mod.use_mirror_merge = use_mirror_merge
        mod.merge_threshold = merge_threshold

        if mirror_object:
            mirror_obj = bpy.data.objects.get(mirror_object)
            if mirror_obj:
                mod.mirror_object = mirror_obj

        axes = []
        if use_x:
            axes.append("X")
        if use_y:
            axes.append("Y")
        if use_z:
            axes.append("Z")

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": mod.name,
            "modifier_type": "MIRROR",
            "axes": axes,
            "use_clip": use_clip,
        }
    except Exception as e:
        raise fmt_err("add_modifier_mirror failed", e)


def add_modifier_boolean(
    object_name: str,
    operation: str = "DIFFERENCE",
    operand_object: str = "",
    use_self: bool = False,
    solver: str = "FAST",
) -> Dict[str, Any]:
    """Add Boolean modifier for non-destructive boolean operations.

    Different from boolean_tool (destructive): This is a modifier that
    preserves the original mesh and allows tweaking.

    Args:
        object_name: Target mesh object.
        operation: "DIFFERENCE" | "UNION" | "INTERSECT".
        operand_object: Object to use as boolean cutter.
        use_self: Use self-intersection (experimental).
        solver: "FAST" | "EXACT". EXACT is more robust but slower.

    Returns:
        {"object_name": str, "modifier_name": str, "operation": str}

    Example:
        # Cut object with cube
        add_modifier_boolean("Panel", operation="DIFFERENCE",
                            operand_object="Cutter_Cube")

        # Union two objects
        add_modifier_boolean("Base", operation="UNION",
                            operand_object="Detail")
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        operand = bpy.data.objects.get(operand_object)
        if not operand:
            raise ValueError(f"Operand object not found: {operand_object}")

        set_active_object(obj)

        mod = obj.modifiers.new(name="Boolean", type="BOOLEAN")
        mod.operation = operation
        mod.object = operand
        mod.use_self = use_self
        mod.solver = solver

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": mod.name,
            "modifier_type": "BOOLEAN",
            "operation": operation,
            "operand_object": operand_object,
            "solver": solver,
        }
    except Exception as e:
        raise fmt_err("add_modifier_boolean failed", e)


def add_modifier_shrinkwrap(
    object_name: str,
    target_object: str,
    wrap_method: str = "NEAREST_SURFACEPOINT",
    offset: float = 0.0,
    vertex_group: Optional[str] = None,
) -> Dict[str, Any]:
    """Add Shrinkwrap modifier to conform mesh to another surface.

    Essential for: clothing, armor fitting, decals, panel lines.
    Tutorial source: CG Boost hard-surface workflows.

    Args:
        object_name: Object to shrinkwrap.
        target_object: Target surface to conform to.
        wrap_method: "NEAREST_SURFACEPOINT" | "PROJECT" | "NEAREST_VERTEX" |
                    "TARGET_PROJECT".
        offset: Distance to keep from surface.
        vertex_group: Optional group for partial shrinkwrap.

    Returns:
        {"object_name": str, "modifier_name": str, "target": str}

    Example:
        # Fit detail to curved surface
        add_modifier_shrinkwrap("Detail_Panel", target_object="Surface")

        # Armor plates on body
        add_modifier_shrinkwrap("Armor", target_object="Body",
                               wrap_method="PROJECT", offset=0.001)
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        target = bpy.data.objects.get(target_object)
        if not target:
            raise ValueError(f"Target object not found: {target_object}")

        set_active_object(obj)

        mod = obj.modifiers.new(name="Shrinkwrap", type="SHRINKWRAP")
        mod.target = target
        mod.wrap_mode = wrap_method
        mod.offset = offset

        if vertex_group and vertex_group in obj.vertex_groups:
            mod.vertex_group = vertex_group

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": mod.name,
            "modifier_type": "SHRINKWRAP",
            "target_object": target_object,
            "wrap_method": wrap_method,
            "offset": offset,
        }
    except Exception as e:
        raise fmt_err("add_modifier_shrinkwrap failed", e)


def add_modifier_curve(
    object_name: str,
    curve_object: str,
    deform_axis: str = "POS_X",
) -> Dict[str, Any]:
    """Add Curve modifier to deform mesh along a curve.

    Args:
        object_name: Object to deform.
        curve_object: Curve to deform along.
        deform_axis: "POS_X" | "POS_Y" | "POS_Z" | "NEG_X" | "NEG_Y" | "NEG_Z".

    Returns:
        {"object_name": str, "modifier_name": str, "curve": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        curve = bpy.data.objects.get(curve_object)
        if not curve:
            raise ValueError(f"Curve object not found: {curve_object}")

        set_active_object(obj)

        mod = obj.modifiers.new(name="Curve", type="CURVE")
        mod.object = curve
        mod.deform_axis = deform_axis

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": mod.name,
            "modifier_type": "CURVE",
            "curve_object": curve_object,
            "deform_axis": deform_axis,
        }
    except Exception as e:
        raise fmt_err("add_modifier_curve failed", e)


def add_modifier_displace(
    object_name: str,
    strength: float = 1.0,
    midlevel: float = 0.5,
    direction: str = "NORMAL",
    vertex_group: Optional[str] = None,
) -> Dict[str, Any]:
    """Add Displace modifier for mesh displacement.

    Args:
        object_name: Target mesh object.
        strength: Displacement strength.
        midlevel: Midpoint for displacement (0-1).
        direction: "NORMAL" | "X" | "Y" | "Z" | "RGB_TO_XYZ".
        vertex_group: Optional vertex group for limiting displacement.

    Returns:
        {"object_name": str, "modifier_name": str, "strength": float}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        mod = obj.modifiers.new(name="Displace", type="DISPLACE")
        mod.strength = strength
        mod.mid_level = midlevel
        mod.direction = direction

        if vertex_group and vertex_group in obj.vertex_groups:
            mod.vertex_group = vertex_group

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": mod.name,
            "modifier_type": "DISPLACE",
            "strength": strength,
            "direction": direction,
        }
    except Exception as e:
        raise fmt_err("add_modifier_displace failed", e)


def configure_modifier(
    object_name: str,
    modifier_name: str,
    properties: Dict[str, Any],
) -> Dict[str, Any]:
    """Configure an existing modifier with arbitrary properties.

    Args:
        object_name: Object containing the modifier.
        modifier_name: Name of the modifier.
        properties: Dict of property names to values.

    Returns:
        {"object_name": str, "modifier_name": str, "configured": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mod = obj.modifiers.get(modifier_name)
        if not mod:
            raise ValueError(f"Modifier '{modifier_name}' not found on {object_name}")

        for prop, value in properties.items():
            if hasattr(mod, prop):
                setattr(mod, prop, value)

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": modifier_name,
            "configured": True,
            "properties_set": list(properties.keys()),
        }
    except Exception as e:
        raise fmt_err("configure_modifier failed", e)


def move_modifier(
    object_name: str,
    modifier_name: str,
    direction: str = "UP",
) -> Dict[str, Any]:
    """Change modifier order in stack.

    Modifier order is critical in Blender. This allows reordering.

    Args:
        object_name: Object containing the modifier.
        modifier_name: Name of the modifier to move.
        direction: "UP" | "DOWN" | "FIRST" | "LAST".

    Returns:
        {"object_name": str, "modifier_name": str, "new_position": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mod = obj.modifiers.get(modifier_name)
        if not mod:
            raise ValueError(f"Modifier '{modifier_name}' not found")

        if direction == "UP":
            bpy.ops.object.modifier_move_up(modifier=modifier_name)
        elif direction == "DOWN":
            bpy.ops.object.modifier_move_down(modifier=modifier_name)
        elif direction == "FIRST":
            bpy.ops.object.modifier_move_to_index(
                modifier=modifier_name, index=0
            )
        elif direction == "LAST":
            bpy.ops.object.modifier_move_to_index(
                modifier=modifier_name, index=len(obj.modifiers) - 1
            )

        # Get new position
        new_pos = list(obj.modifiers).index(mod)

        return {
            "ok": True,
            "object_name": object_name,
            "modifier_name": modifier_name,
            "new_position": new_pos,
        }
    except Exception as e:
        raise fmt_err("move_modifier failed", e)


def list_modifiers(
    object_name: str,
) -> Dict[str, Any]:
    """List all modifiers on an object.

    Args:
        object_name: Target object.

    Returns:
        {"object_name": str, "modifiers": [{"name": str, "type": str, "show_viewport": bool}]}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mods = []
        for mod in obj.modifiers:
            mods.append({
                "name": mod.name,
                "type": mod.type,
                "show_viewport": mod.show_viewport,
                "show_render": mod.show_render,
            })

        return {
            "ok": True,
            "object_name": object_name,
            "modifiers": mods,
            "count": len(mods),
        }
    except Exception as e:
        raise fmt_err("list_modifiers failed", e)
