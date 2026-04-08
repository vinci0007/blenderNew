# Constraints & Parenting Skills - Blender Object Relationships
from typing import Any, Dict, List

import bpy

from .utils import fmt_err, vec3


def set_parent(
    child_name: str,
    parent_name: str,
    keep_transform: bool = True,
    inverse_parent: bool = True,
) -> Dict[str, Any]:
    """Set the parent object for another object.

    Args:
        child_name: Name of the object to be parented.
        parent_name: Name of the parent object.
        keep_transform: If True (default), preserves world transform after parenting.
        inverse_parent: If True (default), uses inverse parent matrix.

    Returns:
        {"child": str, "parent": str, "kept_transform": bool}
    """
    try:
        child = bpy.data.objects.get(child_name)
        if not child:
            raise ValueError(f"Child object not found: {child_name}")

        parent = bpy.data.objects.get(parent_name)
        if not parent:
            raise ValueError(f"Parent object not found: {parent_name}")

        if child == parent:
            raise ValueError("Cannot parent object to itself")

        # Check for cyclic dependency
        current = parent
        while current.parent:
            if current.parent == child:
                raise ValueError("Cyclic parent dependency detected")
            current = current.parent

        child.parent = parent

        if keep_transform:
            # Calculate inverse matrix to keep world transform
            child.matrix_parent_inverse = parent.matrix_world.inverted()
        else:
            child.matrix_parent_inverse.identity()

        return {
            "child": child.name,
            "parent": parent.name,
            "kept_transform": keep_transform,
        }
    except Exception as e:
        raise fmt_err("set_parent failed", e)


def clear_parent(
    object_name: str,
    keep_transform: bool = True,
    clear_inverse: bool = True,
) -> Dict[str, Any]:
    """Clear the parent relationship from an object.

    Args:
        object_name: Name of the object to unparent.
        keep_transform: If True (default), applies parent transformation before clearing.
        clear_inverse: If True (default), clears the inverse parent matrix.

    Returns:
        {"object_name": str, "had_parent": bool, "previous_parent": str | None}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        previous = obj.parent.name if obj.parent else None
        had_parent = obj.parent is not None

        if keep_transform and obj.parent:
            # Apply parent transform to keep world position
            world_matrix = obj.matrix_world.copy()

        obj.parent = None

        if keep_transform and had_parent:
            obj.matrix_world = world_matrix

        if clear_inverse:
            obj.matrix_parent_inverse.identity()

        return {
            "object_name": obj.name,
            "had_parent": had_parent,
            "previous_parent": previous,
        }
    except Exception as e:
        raise fmt_err("clear_parent failed", e)


def add_constraint_copy_location(
    object_name: str,
    target_name: str,
    influence: float = 1.0,
    use_x: bool = True,
    use_y: bool = True,
    use_z: bool = True,
    invert_x: bool = False,
    invert_y: bool = False,
    invert_z: bool = False,
) -> Dict[str, Any]:
    """Add a Copy Location constraint to an object.

    Args:
        object_name: Object to constrain.
        target_name: Target object to copy location from.
        influence: Constraint influence (0.0-1.0). Default 1.0.
        use_x/use_y/use_z: Which axes to copy.
        invert_x/invert_y/invert_z: Whether to invert each axis.

    Returns:
        {"object_name": str, "constraint_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        target = bpy.data.objects.get(target_name)
        if not target:
            raise ValueError(f"Target not found: {target_name}")

        con = obj.constraints.new(type="COPY_LOCATION")
        con.name = f"CopyLocation_{target_name}"
        con.target = target
        con.influence = float(influence)
        con.use_x = use_x
        con.use_y = use_y
        con.use_z = use_z
        con.invert_x = invert_x
        con.invert_y = invert_y
        con.invert_z = invert_z

        return {"object_name": obj.name, "constraint_name": con.name}
    except Exception as e:
        raise fmt_err("add_constraint_copy_location failed", e)


def add_constraint_copy_rotation(
    object_name: str,
    target_name: str,
    influence: float = 1.0,
    use_x: bool = True,
    use_y: bool = True,
    use_z: bool = True,
    invert_x: bool = False,
    invert_y: bool = False,
    invert_z: bool = False,
) -> Dict[str, Any]:
    """Add a Copy Rotation constraint to an object.

    Args:
        object_name: Object to constrain.
        target_name: Target object to copy rotation from.
        influence: Constraint influence (0.0-1.0). Default 1.0.
        use_x/use_y/use_z: Which axes to copy.
        invert_x/invert_y/invert_z: Whether to invert each axis.

    Returns:
        {"object_name": str, "constraint_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        target = bpy.data.objects.get(target_name)
        if not target:
            raise ValueError(f"Target not found: {target_name}")

        con = obj.constraints.new(type="COPY_ROTATION")
        con.name = f"CopyRotation_{target_name}"
        con.target = target
        con.influence = float(influence)
        con.use_x = use_x
        con.use_y = use_y
        con.use_z = use_z
        con.invert_x = invert_x
        con.invert_y = invert_y
        con.invert_z = invert_z

        return {"object_name": obj.name, "constraint_name": con.name}
    except Exception as e:
        raise fmt_err("add_constraint_copy_rotation failed", e)


def add_constraint_copy_scale(
    object_name: str,
    target_name: str,
    influence: float = 1.0,
    use_x: bool = True,
    use_y: bool = True,
    use_z: bool = True,
    power: float = 1.0,
    additive: bool = False,
) -> Dict[str, Any]:
    """Add a Copy Scale constraint to an object.

    Args:
        object_name: Object to constrain.
        target_name: Target object to copy scale from.
        influence: Constraint influence (0.0-1.0). Default 1.0.
        use_x/use_y/use_z: Which axes to copy.
        power: Power to apply to copied scale.
        additive: If True, adds scale instead of multiplying.

    Returns:
        {"object_name": str, "constraint_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        target = bpy.data.objects.get(target_name)
        if not target:
            raise ValueError(f"Target not found: {target_name}")

        con = obj.constraints.new(type="COPY_SCALE")
        con.name = f"CopyScale_{target_name}"
        con.target = target
        con.influence = float(influence)
        con.use_x = use_x
        con.use_y = use_y
        con.use_z = use_z
        con.power = float(power)
        con.use_add = additive

        return {"object_name": obj.name, "constraint_name": con.name}
    except Exception as e:
        raise fmt_err("add_constraint_copy_scale failed", e)


def add_constraint_limit_location(
    object_name: str,
    use_min_x: bool = False,
    min_x: float = 0.0,
    use_max_x: bool = False,
    max_x: float = 0.0,
    use_min_y: bool = False,
    min_y: float = 0.0,
    use_max_y: bool = False,
    max_y: float = 0.0,
    use_min_z: bool = False,
    min_z: float = 0.0,
    use_max_z: bool = False,
    max_z: float = 0.0,
) -> Dict[str, Any]:
    """Add a Limit Location constraint.

    Args:
        object_name: Object to constrain.
        use_min_x/use_max_x: Enable X axis min/max limits.
        min_x/max_x: X axis limit values.
        use_min_y/use_max_y: Enable Y axis min/max limits.
        min_y/max_y: Y axis limit values.
        use_min_z/use_max_z: Enable Z axis min/max limits.
        min_z/max_z: Z axis limit values.

    Returns:
        {"object_name": str, "constraint_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        con = obj.constraints.new(type="LIMIT_LOCATION")
        con.name = "LimitLocation"

        con.use_min_x = use_min_x
        con.min_x = float(min_x) if use_min_x else 0.0
        con.use_max_x = use_max_x
        con.max_x = float(max_x) if use_max_x else 0.0

        con.use_min_y = use_min_y
        con.min_y = float(min_y) if use_min_y else 0.0
        con.use_max_y = use_max_y
        con.max_y = float(max_y) if use_max_y else 0.0

        con.use_min_z = use_min_z
        con.min_z = float(min_z) if use_min_z else 0.0
        con.use_max_z = use_max_z
        con.max_z = float(max_z) if use_max_z else 0.0

        return {"object_name": obj.name, "constraint_name": con.name}
    except Exception as e:
        raise fmt_err("add_constraint_limit_location failed", e)


def remove_constraint(object_name: str, constraint_name: str) -> Dict[str, Any]:
    """Remove a constraint from an object.

    Args:
        object_name: Object containing the constraint.
        constraint_name: Name of the constraint to remove.

    Returns:
        {"object_name": str, "removed": bool, "constraint_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        con = obj.constraints.get(constraint_name)
        if con:
            obj.constraints.remove(con)
            return {
                "object_name": obj.name,
                "removed": True,
                "constraint_name": constraint_name,
            }
        else:
            return {
                "object_name": obj.name,
                "removed": False,
                "constraint_name": constraint_name,
            }
    except Exception as e:
        raise fmt_err("remove_constraint failed", e)


def list_constraints(object_name: str) -> Dict[str, Any]:
    """List all constraints on an object.

    Args:
        object_name: Object to inspect.

    Returns:
        {"object_name": str, "constraints": [str], "count": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        cons = [c.name for c in obj.constraints]
        return {"object_name": obj.name, "constraints": cons, "count": len(cons)}
    except Exception as e:
        raise fmt_err("list_constraints failed", e)
