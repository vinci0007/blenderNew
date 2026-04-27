# Collection Skills - Blender Collection Management
from typing import Any, Dict, List

import bpy

from .utils import fmt_err


def create_collection(name: str, parent_name: str | None = None) -> Dict[str, Any]:
    """Create a new collection in the scene.

    Args:
        name: Name for the new collection.
        parent_name: Optional parent collection name. If None, creates at root level.

    Returns:
        {"collection_name": str, "parent": str | None}
    """
    try:
        # Check if collection already exists
        if name in bpy.data.collections:
            raise ValueError(f"Collection already exists: {name}")

        new_coll = bpy.data.collections.new(name=name)

        if parent_name:
            parent = bpy.data.collections.get(parent_name)
            if not parent:
                raise ValueError(f"Parent collection not found: {parent_name}")
            parent.children.link(new_coll)
        else:
            # Link to master scene collection
            bpy.context.scene.collection.children.link(new_coll)

        return {"collection_name": new_coll.name, "parent": parent_name}
    except Exception as e:
        raise fmt_err("create_collection failed", e)


def link_to_collection(object_name: str, collection_name: str) -> Dict[str, Any]:
    """Link an object to a collection.

    Args:
        object_name: Name of the object to link.
        collection_name: Target collection name.

    Returns:
        {"object_name": str, "collection_name": str, "linked": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        coll = bpy.data.collections.get(collection_name)
        if not coll:
            raise ValueError(f"Collection not found: {collection_name}")

        if obj.name not in coll.objects:
            coll.objects.link(obj)

        return {"object_name": obj.name, "collection_name": coll.name, "linked": True}
    except Exception as e:
        raise fmt_err("link_to_collection failed", e)


def unlink_from_collection(object_name: str, collection_name: str) -> Dict[str, Any]:
    """Unlink an object from a collection.

    Args:
        object_name: Name of the object to unlink.
        collection_name: Collection to unlink from.

    Returns:
        {"object_name": str, "collection_name": str, "unlinked": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        coll = bpy.data.collections.get(collection_name)
        if not coll:
            raise ValueError(f"Collection not found: {collection_name}")

        if obj.name in coll.objects:
            coll.objects.unlink(obj)
            unlinked = True
        else:
            unlinked = False

        return {"object_name": obj.name, "collection_name": coll.name, "unlinked": unlinked}
    except Exception as e:
        raise fmt_err("unlink_from_collection failed", e)


def remove_collection(name: str, delete_objects: bool = False) -> Dict[str, Any]:
    """Remove a collection from the scene.

    Args:
        name: Name of the collection to remove.
        delete_objects: If True, also delete contained objects. Default False.

    Returns:
        {"collection_name": str, "objects_deleted": int}
    """
    try:
        coll = bpy.data.collections.get(name)
        if not coll:
            raise ValueError(f"Collection not found: {name}")

        deleted_count = 0

        if delete_objects:
            # Copy list since we're modifying
            for obj in list(coll.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
                deleted_count += 1
        else:
            # Unlink objects first
            for obj in list(coll.objects):
                coll.objects.unlink(obj)

        # Remove from parent
        for parent in list(bpy.data.collections):
            if coll.name in [c.name for c in parent.children]:
                parent.children.unlink(coll)

        # Remove from scene
        for scene in bpy.data.scenes:
            if coll.name in [c.name for c in scene.collection.children]:
                scene.collection.children.unlink(coll)

        # Finally remove collection
        bpy.data.collections.remove(coll)

        return {"collection_name": name, "objects_deleted": deleted_count}
    except Exception as e:
        raise fmt_err("remove_collection failed", e)


def move_to_layer(  # Renamed to avoid confusion, actually sets instance_offset
    collection_name: str,
    origin: List[float],
) -> Dict[str, Any]:
    """Set the instance offset/origin for a collection.

    Args:
        collection_name: Target collection name.
        origin: [x, y, z] origin position.

    Returns:
        {"collection_name": str, "instance_offset": [x, y, z]}
    """
    try:
        coll = bpy.data.collections.get(collection_name)
        if not coll:
            raise ValueError(f"Collection not found: {collection_name}")

        from .utils import vec3
        coll.instance_offset = vec3(origin)

        return {"collection_name": coll.name, "instance_offset": list(coll.instance_offset)}
    except Exception as e:
        raise fmt_err("move_to_layer failed", e)


def list_collections() -> Dict[str, Any]:
    """List all collections in the scene.

    Returns:
        {"collections": [{"name": str, "object_count": int, "is_master": bool}]}
    """
    try:
        result = []
        for coll in bpy.data.collections:
            is_master = coll == bpy.context.scene.collection
            result.append({
                "name": coll.name,
                "object_count": len(coll.objects),
                "is_master": is_master,
            })

        return {"collections": result, "count": len(result)}
    except Exception as e:
        raise fmt_err("list_collections failed", e)


def isolate_in_collection(
    object_names: List[str],
    collection_name: str,
    remove_from_others: bool = False,
) -> Dict[str, Any]:
    """Move objects to a collection, optionally removing from other collections.

    Args:
        object_names: List of object names to move.
        collection_name: Target collection.
        remove_from_others: If True, remove from all other collections.

    Returns:
        {"moved": int, "collection_name": str}
    """
    try:
        target = bpy.data.collections.get(collection_name)
        if not target:
            raise ValueError(f"Collection not found: {collection_name}")

        moved = 0
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if not obj:
                continue

            # Link to target
            if obj.name not in target.objects:
                target.objects.link(obj)

            # Remove from others if requested
            if remove_from_others:
                for coll in list(obj.users_collection):
                    if coll != target and obj.name in coll.objects:
                        coll.objects.unlink(obj)

            moved += 1

        return {"moved": moved, "collection_name": target.name}
    except Exception as e:
        raise fmt_err("isolate_in_collection failed", e)
