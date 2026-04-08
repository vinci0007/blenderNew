# Asset Management Skills - Blender Asset Browser and Management
from typing import Any, Dict, List, Optional, Tuple, Union

import bpy

from .utils import fmt_err, set_active_object


def asset_mark(
    object_name: str,
    asset_type: str = "OBJECT",
) -> Dict[str, Any]:
    """Mark an object as an asset.

    Args:
        object_name: Object name to mark.
        asset_type: Type of asset (OBJECT, MATERIAL, ACTION, NODE_GROUP, etc.).

    Returns:
        {"object_name": str, "asset_type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        # Mark as asset
        obj.asset_mark()
        obj.asset_data.description = f"Asset of type {asset_type}"

        return {
            "object_name": obj.name,
            "asset_type": asset_type,
            "marked": True,
        }
    except Exception as e:
        raise fmt_err("asset_mark failed", e)


def asset_clear(
    object_name: str,
) -> Dict[str, Any]:
    """Clear asset mark from an object.

    Args:
        object_name: Object name.

    Returns:
        {"object_name": str, "cleared": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        if obj.asset_data:
            obj.asset_clear()
            return {"object_name": obj.name, "cleared": True}
        else:
            return {"object_name": obj.name, "cleared": False, "reason": "Not an asset"}
    except Exception as e:
        raise fmt_err("asset_clear failed", e)


def asset_set_metadata(
    object_name: str,
    description: str = "",
    author: str = "",
    copyright: str = "",
    license_type: str = "",
) -> Dict[str, Any]:
    """Set metadata for an asset.

    Args:
        object_name: Asset object name.
        description: Asset description.
        author: Asset author.
        copyright: Copyright information.
        license_type: License type.

    Returns:
        {"object_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or not obj.asset_data:
            raise ValueError(f"Asset not found: {object_name}")

        asset_data = obj.asset_data
        asset_data.description = description

        return {
            "object_name": obj.name,
            "description": description,
        }
    except Exception as e:
        raise fmt_err("asset_set_metadata failed", e)


def asset_catalog_create(
    name: str,
    parent_path: str = "",
) -> Dict[str, Any]:
    """Create a new asset catalog.

    Args:
        name: Catalog name.
        parent_path: Parent catalog path.

    Returns:
        {"catalog_name": str, "path": str}
    """
    try:
        # Asset catalogs are managed through the asset library
        catalogs = bpy.data.asset_catalogs

        full_path = f"{parent_path}/{name}" if parent_path else name

        # Currently Blender API doesn't expose direct catalog creation
        # This is a placeholder for future API support

        return {
            "catalog_name": name,
            "path": full_path,
            "created": False,
            "note": "Asset catalogs are managed through the UI currently",
        }
    except Exception as e:
        raise fmt_err("asset_catalog_create failed", e)


def asset_list(
) -> Dict[str, Any]:
    """List all marked assets in the current file.

    Returns:
        {"assets": [{"name": str, "type": str}], "count": int}
    """
    try:
        assets = []
        for obj in bpy.data.objects:
            if obj.asset_data:
                assets.append({
                    "name": obj.name,
                    "type": obj.type,
                })

        for mat in bpy.data.materials:
            if mat.asset_data:
                assets.append({
                    "name": mat.name,
                    "type": "MATERIAL",
                })

        for action in bpy.data.actions:
            if action.asset_data:
                assets.append({
                    "name": action.name,
                    "type": "ACTION",
                })

        return {
            "assets": assets,
            "count": len(assets),
        }
    except Exception as e:
        raise fmt_err("asset_list failed", e)


def library_append(
    filepath: str,
    directory: str,
    filename: str,
) -> Dict[str, Any]:
    """Append data from another .blend file.

    Args:
        filepath: Path to .blend file.
        directory: Data block type path (e.g., "Object", "Collection").
        filename: Name of data block to append.

    Returns:
        {"filepath": str, "imported": str}
    """
    try:
        full_path = f"{filepath}\\{directory}\\{filename}"

        bpy.ops.wm.append(
            filepath=full_path,
            directory=f"{filepath}\\{directory}",
            filename=filename,
        )

        return {
            "filepath": filepath,
            "imported": filename,
            "type": directory,
        }
    except Exception as e:
        raise fmt_err("library_append failed", e)


def library_link(
    filepath: str,
    directory: str,
    filename: str,
) -> Dict[str, Any]:
    """Link data from another .blend file.

    Args:
        filepath: Path to .blend file.
        directory: Data block type path.
        filename: Name of data block to link.

    Returns:
        {"filepath": str, "linked": str}
    """
    try:
        full_path = f"{filepath}\\{directory}\\{filename}"

        bpy.ops.wm.link(
            filepath=full_path,
            directory=f"{filepath}\\{directory}",
            filename=filename,
        )

        return {
            "filepath": filepath,
            "linked": filename,
            "type": directory,
        }
    except Exception as e:
        raise fmt_err("library_link failed", e)


def library_reload(
    library_name: str,
) -> Dict[str, Any]:
    """Reload a linked library.

    Args:
        library_name: Library name.

    Returns:
        {"reloaded": str}
    """
    try:
        lib = bpy.data.libraries.get(library_name)
        if not lib:
            raise ValueError(f"Library not found: {library_name}")

        lib.reload()

        return {
            "reloaded": lib.name,
        }
    except Exception as e:
        raise fmt_err("library_reload failed", e)


def library_list(
) -> Dict[str, Any]:
    """List all linked libraries.

    Returns:
        {"libraries": [{"name": str, "filepath": str}], "count": int}
    """
    try:
        libraries = []
        for lib in bpy.data.libraries:
            libraries.append({
                "name": lib.name,
                "filepath": lib.filepath,
            })

        return {
            "libraries": libraries,
            "count": len(libraries),
        }
    except Exception as e:
        raise fmt_err("library_list failed", e)


def pack_blend(
) -> Dict[str, Any]:
    """Pack all external data into the .blend file.

    Returns:
        {"packed": bool}
    """
    try:
        bpy.ops.file.pack_all()
        return {"packed": True}
    except Exception as e:
        raise fmt_err("pack_blend failed", e)


def unpack_blend(
    method: str = "USE_ORIGINAL",
) -> Dict[str, Any]:
    """Unpack data from the .blend file.

    Args:
        method: Unpack method (USE_ORIGINAL, WRITE_LOCAL, USE_LOCAL).

    Returns:
        {"unpacked": bool, "method": str}
    """
    try:
        bpy.ops.file.unpack_all(method=method)
        return {"unpacked": True, "method": method}
    except Exception as e:
        raise fmt_err("unpack_blend failed", e)


def make_paths_absolute(
) -> Dict[str, Any]:
    """Convert all paths to absolute paths.

    Returns:
        {"converted": bool}
    """
    try:
        bpy.ops.file.make_paths_absolute()
        return {"converted": True}
    except Exception as e:
        raise fmt_err("make_paths_absolute failed", e)


def make_paths_relative(
) -> Dict[str, Any]:
    """Convert all paths to relative paths.

    Returns:
        {"converted": bool}
    """
    try:
        bpy.ops.file.make_paths_relative()
        return {"converted": True}
    except Exception as e:
        raise fmt_err("make_paths_relative failed", e)


def find_missing_files(
    directory: str,
) -> Dict[str, Any]:
    """Find missing files and search in directory.

    Args:
        directory: Directory to search for missing files.

    Returns:
        {"searched": bool, "directory": str}
    """
    try:
        bpy.ops.file.find_missing_files(directory=directory)
        return {"searched": True, "directory": directory}
    except Exception as e:
        raise fmt_err("find_missing_files failed", e)


def report_missing_files(
) -> Dict[str, Any]:
    """Report all missing files.

    Returns:
        {"files": [{"name": str, "filepath": str}], "count": int}
    """
    try:
        missing = []
        for img in bpy.data.images:
            if img.filepath and img.is_missing:
                missing.append({
                    "name": img.name,
                    "filepath": img.filepath,
                    "type": "IMAGE",
                })

        for lib in bpy.data.libraries:
            if lib.filepath and lib.is_missing:
                missing.append({
                    "name": lib.name,
                    "filepath": lib.filepath,
                    "type": "LIBRARY",
                })

        return {
            "files": missing,
            "count": len(missing),
        }
    except Exception as e:
        raise fmt_err("report_missing_files failed", e)
