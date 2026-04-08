# Driver Skills - Blender Drivers and Expressions
from typing import Any, Dict, List, Optional, Tuple, Union

import bpy

from .utils import fmt_err


def add_driver(
    target_object: str,
    target_property: str,
    index: int = -1,
    expression: str = "",
) -> Dict[str, Any]:
    """Add a driver to an object property.

    Args:
        target_object: Object name.
        target_property: Property to drive (e.g., "location", "rotation_euler").
        index: Array index (-1 for all, 0, 1, 2 for x, y, z).
        expression: Driver expression.

    Returns:
        {"object_name": str, "property": str, "driver_added": bool}
    """
    try:
        obj = bpy.data.objects.get(target_object)
        if not obj:
            raise ValueError(f"Object not found: {target_object}")

        # Get the property
        prop = getattr(obj, target_property, None)
        if prop is None:
            raise ValueError(f"Property not found: {target_property}")

        # Add driver
        if index >= 0:
            prop.driver_add(index)
            driver_path = f"{target_property}[{index}]"
        else:
            prop.driver_add()
            driver_path = target_property

        driver = obj.driver_add(target_property) if index < 0 else obj.driver_add(target_property)[index]
        if expression:
            driver.driver.expression = expression

        return {
            "object_name": obj.name,
            "property": target_property,
            "driver_added": True,
        }
    except Exception as e:
        raise fmt_err("add_driver failed", e)


def driver_add_variable(
    target_object: str,
    target_property: str,
    var_name: str,
    var_type: str = "SINGLE_PROP",
    source_object: Optional[str] = None,
    source_property: Optional[str] = None,
    index: int = -1,
) -> Dict[str, Any]:
    """Add a variable to a driver.

    Args:
        target_object: Target object with driver.
        target_property: Property with driver.
        var_name: Variable name.
        var_type: Variable type (SINGLE_PROP, TRANSFORMS, ROTATION_DIFF, LOC_DIFF).
        source_object: Source object for variable.
        source_property: Source property.
        index: Array index (-1 for all).

    Returns:
        {"object_name": str, "property": str, "variable": str}
    """
    try:
        obj = bpy.data.objects.get(target_object)
        if not obj:
            raise ValueError(f"Object not found: {target_object}")

        # Get driver
        fcurve = None
        for fc in obj.animation_data.drivers if obj.animation_data else []:
            if fc.data_path == target_property and (index < 0 or fc.array_index == index):
                fcurve = fc
                break

        if not fcurve:
            raise ValueError(f"No driver found on {target_property}")

        # Add variable
        var = fcurve.driver.variables.new()
        var.name = var_name
        var.type = var_type

        if var_type == "SINGLE_PROP":
            if source_object and source_property:
                src_obj = bpy.data.objects.get(source_object)
                if src_obj:
                    var.targets[0].id = src_obj
                    var.targets[0].data_path = source_property

        return {
            "object_name": obj.name,
            "property": target_property,
            "variable": var_name,
        }
    except Exception as e:
        raise fmt_err("driver_add_variable failed", e)


def driver_set_expression(
    target_object: str,
    target_property: str,
    expression: str,
    index: int = -1,
) -> Dict[str, Any]:
    """Set the expression for a driver.

    Args:
        target_object: Target object.
        target_property: Property with driver.
        expression: New expression.
        index: Array index.

    Returns:
        {"object_name": str, "property": str, "expression": str}
    """
    try:
        obj = bpy.data.objects.get(target_object)
        if not obj:
            raise ValueError(f"Object not found: {target_object}")

        fcurve = None
        for fc in obj.animation_data.drivers if obj.animation_data else []:
            if fc.data_path == target_property and (index < 0 or fc.array_index == index):
                fcurve = fc
                break

        if not fcurve:
            raise ValueError(f"No driver found on {target_property}")

        fcurve.driver.expression = expression
        fcurve.driver.use_self = False

        return {
            "object_name": obj.name,
            "property": target_property,
            "expression": expression,
        }
    except Exception as e:
        raise fmt_err("driver_set_expression failed", e)


def driver_remove(
    target_object: str,
    target_property: str,
    index: int = -1,
) -> Dict[str, Any]:
    """Remove a driver from an object property.

    Args:
        target_object: Target object.
        target_property: Property with driver.
        index: Array index (-1 for all).

    Returns:
        {"removed": bool, "object_name": str, "property": str}
    """
    try:
        obj = bpy.data.objects.get(target_object)
        if not obj:
            raise ValueError(f"Object not found: {target_object}")

        prop = getattr(obj, target_property, None)
        if prop is None:
            raise ValueError(f"Property not found: {target_property}")

        if index >= 0:
            prop.driver_remove(index)
        else:
            prop.driver_remove()

        return {
            "removed": True,
            "object_name": obj.name,
            "property": target_property,
        }
    except Exception as e:
        raise fmt_err("driver_remove failed", e)


def driver_copy(
    source_object: str,
    target_object: str,
    source_property: str,
    target_property: str,
) -> Dict[str, Any]:
    """Copy a driver from one object/property to another.

    Args:
        source_object: Source object.
        target_object: Target object.
        source_property: Source property.
        target_property: Target property.

    Returns:
        {"copied": bool}
    """
    try:
        src_obj = bpy.data.objects.get(source_object)
        tgt_obj = bpy.data.objects.get(target_object)

        if not src_obj:
            raise ValueError(f"Source object not found: {source_object}")
        if not tgt_obj:
            raise ValueError(f"Target object not found: {target_object}")

        # Find source driver
        src_fcurve = None
        for fc in src_obj.animation_data.drivers if src_obj.animation_data else []:
            if fc.data_path == source_property:
                src_fcurve = fc
                break

        if not src_fcurve:
            raise ValueError(f"No driver found on source")

        # Copy to target
        prop = getattr(tgt_obj, target_property)
        tgt_fcurve = prop.driver_add()

        # Copy expression
        tgt_fcurve.driver.expression = src_fcurve.driver.expression
        tgt_fcurve.driver.type = src_fcurve.driver.type

        # Copy variables
        for src_var in src_fcurve.driver.variables:
            tgt_var = tgt_fcurve.driver.variables.new()
            tgt_var.name = src_var.name
            tgt_var.type = src_var.type
            # Copy targets
            for i, src_target in enumerate(src_var.targets):
                if i < len(tgt_var.targets):
                    tgt_var.targets[i].id = src_target.id
                    tgt_var.targets[i].data_path = src_target.data_path

        return {
            "copied": True,
            "source": f"{source_object}.{source_property}",
            "target": f"{target_object}.{target_property}",
        }
    except Exception as e:
        raise fmt_err("driver_copy failed", e)


def driver_list(
    target_object: str,
) -> Dict[str, Any]:
    """List all drivers on an object.

    Args:
        target_object: Object name.

    Returns:
        {"object_name": str, "drivers": [{"path": str, "expression": str}], "count": int}
    """
    try:
        obj = bpy.data.objects.get(target_object)
        if not obj:
            raise ValueError(f"Object not found: {target_object}")

        drivers = []
        if obj.animation_data:
            for fc in obj.animation_data.drivers:
                drivers.append({
                    "path": fc.data_path,
                    "array_index": fc.array_index,
                    "expression": fc.driver.expression,
                    "type": fc.driver.type,
                })

        return {
            "object_name": obj.name,
            "drivers": drivers,
            "count": len(drivers),
        }
    except Exception as e:
        raise fmt_err("driver_list failed", e)


def driver_add_shape_key(
    object_name: str,
    shape_key_name: str,
    expression: str,
) -> Dict[str, Any]:
    """Add a driver to a shape key value.

    Args:
        object_name: Mesh object name.
        shape_key_name: Shape key name.
        expression: Driver expression.

    Returns:
        {"object_name": str, "shape_key": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        shape_key = obj.data.shape_keys.key_blocks.get(shape_key_name)
        if not shape_key:
            raise ValueError(f"Shape key not found: {shape_key_name}")

        # Add driver to shape key value
        shape_key.driver_add("value")
        fcurve = obj.data.shape_keys.animation_data.drivers[-1]
        fcurve.driver.expression = expression

        return {
            "object_name": obj.name,
            "shape_key": shape_key_name,
        }
    except Exception as e:
        raise fmt_err("driver_add_shape_key failed", e)
