# Shape Keys Skills - Blender Morph Targets
from typing import Any, Dict, List

import bpy

from .utils import fmt_err, set_active_object


def add_shape_key(
    object_name: str,
    key_name: str,
    type: str = "KEY",
) -> Dict[str, Any]:
    """Add a new shape key to a mesh object.

    Args:
        object_name: Name of the mesh object.
        key_name: Name for the new shape key.
        type: Shape key type. Enum:
            - "KEY" (relative mix)
            - "BASIS" (base shape, overwrites existing)

    Returns:
        {"object_name": str, "key_name": str, "key_index": int, "type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Create shape key
        shape_key = obj.shape_key_add(name=key_name, from_mix=(type != "BASIS"))

        if type == "BASIS":
            # Make this the basis
            obj.data.shape_keys.use_relative = True

        return {
            "object_name": obj.name,
            "key_name": shape_key.name,
            "key_index": shape_key.slider_min if hasattr(shape_key, 'slider_min') else 0,
            "type": type,
            "total_keys": len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 1,
        }
    except Exception as e:
        raise fmt_err("add_shape_key failed", e)


def set_shape_key_value(
    object_name: str,
    key_name: str,
    value: float = 0.0,
) -> Dict[str, Any]:
    """Set the influence value of a shape key.

    Args:
        object_name: Name of the mesh object.
        key_name: Name of the shape key.
        value: Influence value (0.0 - 1.0).

    Returns:
        {"object_name": str, "key_name": str, "value": float}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        if not obj.data.shape_keys:
            raise ValueError(f"Object has no shape keys: {object_name}")

        key_block = obj.data.shape_keys.key_blocks.get(key_name)
        if not key_block:
            raise ValueError(f"Shape key not found: {key_name}")

        key_block.value = value

        return {
            "object_name": obj.name,
            "key_name": key_block.name,
            "value": key_block.value,
        }
    except Exception as e:
        raise fmt_err("set_shape_key_value failed", e)


def set_shape_key_range(
    object_name: str,
    key_name: str,
    min: float = 0.0,
    max: float = 1.0,
) -> Dict[str, Any]:
    """Set the value range of a shape key.

    Args:
        object_name: Name of the mesh object.
        key_name: Name of the shape key.
        min: Minimum slider value.
        max: Maximum slider value.

    Returns:
        {"object_name": str, "key_name": str, "min": float, "max": float}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        if not obj.data.shape_keys:
            raise ValueError(f"Object has no shape keys: {object_name}")

        key_block = obj.data.shape_keys.key_blocks.get(key_name)
        if not key_block:
            raise ValueError(f"Shape key not found: {key_name}")

        key_block.slider_min = min
        key_block.slider_max = max

        return {
            "object_name": obj.name,
            "key_name": key_block.name,
            "min": key_block.slider_min,
            "max": key_block.slider_max,
        }
    except Exception as e:
        raise fmt_err("set_shape_key_range failed", e)


def delete_shape_key(object_name: str, key_name: str) -> Dict[str, Any]:
    """Delete a shape key from an object.

    Args:
        object_name: Name of the mesh object.
        key_name: Name of the shape key to delete.

    Returns:
        {"deleted": bool, "key_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        if not obj.data.shape_keys:
            return {"deleted": False, "key_name": key_name, "reason": "No shape keys"}

        key_block = obj.data.shape_keys.key_blocks.get(key_name)
        if not key_block:
            return {"deleted": False, "key_name": key_name, "reason": "Key not found"}

        set_active_object(obj)

        # Remove shape key
        obj.shape_key_remove(key_block)

        return {"deleted": True, "key_name": key_name}
    except Exception as e:
        raise fmt_err("delete_shape_key failed", e)


def rename_shape_key(
    object_name: str,
    old_name: str,
    new_name: str,
) -> Dict[str, Any]:
    """Rename a shape key.

    Args:
        object_name: Name of the mesh object.
        old_name: Current shape key name.
        new_name: New name for the shape key.

    Returns:
        {"object_name": str, "old_name": str, "new_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        if not obj.data.shape_keys:
            raise ValueError(f"Object has no shape keys: {object_name}")

        key_block = obj.data.shape_keys.key_blocks.get(old_name)
        if not key_block:
            raise ValueError(f"Shape key not found: {old_name}")

        key_block.name = new_name

        return {
            "object_name": obj.name,
            "old_name": old_name,
            "new_name": key_block.name,
        }
    except Exception as e:
        raise fmt_err("rename_shape_key failed", e)


def list_shape_keys(object_name: str) -> Dict[str, Any]:
    """List all shape keys of an object.

    Args:
        object_name: Name of the mesh object.

    Returns:
        {"object_name": str, "keys": [{"name": str, "value": float, "mins": float, "maxs": float}], "count": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        keys = []
        if obj.data.shape_keys:
            for key_block in obj.data.shape_keys.key_blocks:
                keys.append({
                    "name": key_block.name,
                    "value": key_block.value,
                    "min": key_block.slider_min,
                    "max": key_block.slider_max,
                })

        return {
            "object_name": obj.name,
            "keys": keys,
            "count": len(keys),
        }
    except Exception as e:
        raise fmt_err("list_shape_keys failed", e)


def reset_shape_keys(object_name: str) -> Dict[str, Any]:
    """Reset all shape key values to 0.

    Args:
        object_name: Name of the mesh object.

    Returns:
        {"object_name": str, "reset": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        if not obj.data.shape_keys:
            return {"object_name": obj.name, "reset": 0, "reason": "No shape keys"}

        count = 0
        for key_block in obj.data.shape_keys.key_blocks:
            key_block.value = 0.0
            count += 1

        return {"object_name": obj.name, "reset": count}
    except Exception as e:
        raise fmt_err("reset_shape_keys failed", e)


def shape_key_from_mix(
    object_name: str,
    new_key_name: str,
) -> Dict[str, Any]:
    """Create a new shape key from the current mix of shape keys.

    Args:
        object_name: Name of the mesh object.
        new_key_name: Name for the new shape key.

    Returns:
        {"object_name": str, "key_name": str, "mixed": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Create new shape key from mix
        shape_key = obj.shape_key_add(name=new_key_name, from_mix=True)

        return {
            "object_name": obj.name,
            "key_name": shape_key.name,
            "from_mix": True,
        }
    except Exception as e:
        raise fmt_err("shape_key_from_mix failed", e)


def set_shape_key_vertex_position(
    object_name: str,
    key_name: str,
    vertex_index: int,
    position: List[float],
) -> Dict[str, Any]:
    """Set the position of a vertex in a shape key.

    Args:
        object_name: Name of the mesh object.
        key_name: Name of the shape key.
        vertex_index: Index of the vertex to modify.
        position: [x, y, z] new position.

    Returns:
        {"object_name": str, "key_name": str, "vertex": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        if not obj.data.shape_keys:
            raise ValueError(f"Object has no shape keys: {object_name}")

        key_block = obj.data.shape_keys.key_blocks.get(key_name)
        if not key_block:
            raise ValueError(f"Shape key not found: {key_name}")

        if len(key_block.data) <= vertex_index:
            raise ValueError(f"Vertex index out of range: {vertex_index}")

        from .utils import vec3
        key_block.data[vertex_index].co = vec3(position)

        return {
            "object_name": obj.name,
            "key_name": key_block.name,
            "vertex_index": vertex_index,
        }
    except Exception as e:
        raise fmt_err("set_shape_key_vertex_position failed", e)
