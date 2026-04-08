# Texture Skills - Image Textures and Node Setup
from typing import Any, Dict, List

import bpy

from .utils import fmt_err


def import_image_texture(
    filepath: str,
    name: str | None = None,
) -> Dict[str, Any]:
    """Import an image file for use as a texture.

    Args:
        filepath: Path to the image file.
        name: Optional name for the image. If None, uses filename.

    Returns:
        {"image_name": str, "filepath": str, "size": [w, h]}
    """
    try:
        img = bpy.data.images.load(filepath, check_existing=True)

        if name:
            img.name = name

        return {
            "image_name": img.name,
            "filepath": img.filepath,
            "size": [img.size[0], img.size[1]] if img.size[0] > 0 else None,
        }
    except Exception as e:
        raise fmt_err("import_image_texture failed", e)


def create_image_texture(
    name: str,
    width: int = 1024,
    height: int = 1024,
    color: List[float] | None = None,
) -> Dict[str, Any]:
    """Create a new blank image texture.

    Args:
        name: Name for the image.
        width: Image width in pixels.
        height: Image height in pixels.
        color: Optional [r, g, b, a] color (0.0-1.0). Defaults to transparent black.

    Returns:
        {"image_name": str, "size": [w, h]}
    """
    try:
        # Create image
        img = bpy.data.images.new(
            name=name,
            width=width,
            height=height,
            alpha=True,
        )

        # Fill with color if provided
        if color:
            rgba = list(color) + [1.0] * (4 - len(color))
            pixels = rgba * (width * height)
            img.pixels = pixels

        return {
            "image_name": img.name,
            "size": [width, height],
        }
    except Exception as e:
        raise fmt_err("create_image_texture failed", e)


def add_texture_to_material(
    material_name: str,
    image_name: str,
    node_type: str = " principled",
    socket_name: str = "Base Color",
) -> Dict[str, Any]:
    """Add an image texture to a material.

    Args:
        material_name: Name of the material.
        image_name: Name of the image in bpy.data.images.
        node_type: Type of texture. Enum: "principled" | "emission" | "normal".
        socket_name: Which socket to connect to. Default "Base Color".

    Returns:
        {"material_name": str, "texture_name": str}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat:
            raise ValueError(f"Material not found: {material_name}")

        img = bpy.data.images.get(image_name)
        if not img:
            raise ValueError(f"Image not found: {image_name}")

        if not mat.use_nodes:
            mat.use_nodes = True

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Find principled BSDF
        bsdf = None
        for n in nodes:
            if n.type == "BSDF_PRINCIPLED":
                bsdf = n
                break

        if not bsdf:
            raise RuntimeError("No Principled BSDF found in material")

        # Create texture node
        tex_node = nodes.new(type="ShaderNodeTexImage")
        tex_node.name = f"Texture_{image_name}"
        tex_node.image = img

        # Link to base color
        if socket_name in bsdf.inputs:
            links.new(tex_node.outputs["Color"], bsdf.inputs[socket_name])

        return {
            "material_name": mat.name,
            "texture_name": tex_node.name,
            "image_name": img.name,
        }
    except Exception as e:
        raise fmt_err("add_texture_to_material failed", e)


def set_texture_mapping(
    material_name: str,
    texture_node_name: str,
    mapping_type: str = "UV",
    projection: str = "FLAT",
) -> Dict[str, Any]:
    """Set texture mapping for an image texture node.

    Args:
        material_name: Name of the material.
        texture_node_name: Name of the texture node.
        mapping_type: Mapping type. Enum: "UV" | "Generated" | "Object" | "Camera".
        projection: Projection type. Enum: "FLAT" | "BOX" | "SPHERE" | "TUBE".

    Returns:
        {"material_name": str, "texture_node": str, "mapping": str}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat:
            raise ValueError(f"Material not found: {material_name}")

        if not mat.use_nodes:
            raise ValueError("Material does not use nodes")

        node = mat.node_tree.nodes.get(texture_node_name)
        if not node or node.type != "TEX_IMAGE":
            raise ValueError(f"Texture node not found: {texture_node_name}")

        # Map string to enum
        projection_map = {
            "FLAT": "FLAT",
            "BOX": "BOX",
            "SPHERE": "SPHERE",
            "TUBE": "TUBE",
        }

        node.projection = projection_map.get(projection.upper(), "FLAT")

        return {
            "material_name": mat.name,
            "texture_node": node.name,
            "projection": node.projection,
        }
    except Exception as e:
        raise fmt_err("set_texture_mapping failed", e)


def add_normal_map(
    material_name: str,
    image_name: str,
    strength: float = 1.0,
) -> Dict[str, Any]:
    """Add a normal map to a material.

    Args:
        material_name: Name of the material.
        image_name: Name of the normal map image.
        strength: Normal map strength (0.0 - 10.0).

    Returns:
        {"material_name": str, "normal_map": str}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat:
            raise ValueError(f"Material not found: {material_name}")

        img = bpy.data.images.get(image_name)
        if not img:
            raise ValueError(f"Image not found: {image_name}")

        if not mat.use_nodes:
            mat.use_nodes = True

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Find principled BSDF
        bsdf = None
        for n in nodes:
            if n.type == "BSDF_PRINCIPLED":
                bsdf = n
                break

        if not bsdf:
            raise RuntimeError("No Principled BSDF found in material")

        # Create normal map node
        normal_map = nodes.new(type="ShaderNodeNormalMap")
        normal_map.name = "NormalMap"
        normal_map.inputs["Strength"].default_value = strength

        # Create texture node
        tex_node = nodes.new(type="ShaderNodeTexImage")
        tex_node.name = f"NormalTexture_{image_name}"
        tex_node.image = img
        tex_node.image.colorspace_settings.name = "Non-Color"

        # Link nodes
        links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

        return {
            "material_name": mat.name,
            "normal_map": normal_map.name,
            "texture": tex_node.name,
        }
    except Exception as e:
        raise fmt_err("add_normal_map failed", e)


def bake_texture(
    object_name: str,
    image_name: str,
    bake_type: str = "DIFFUSE",
    pass_filter: List[str] | None = None,
) -> Dict[str, Any]:
    """Bake texture from object(s) to an image.

    Args:
        object_name: Name of object to bake (must have material with image texture node).
        image_name: Name of image to bake to.
        bake_type: Type of bake. Enum: "DIFFUSE" | "NORMAL" | "ROUGHNESS" | "EMISSION" | "AO".
        pass_filter: For diffuse, filter contributions. ["DIRECT", "INDIRECT", "COLOR"].

    Returns:
        {"object_name": str, "image_name": str, "bake_type": str}
    """
    try:
        from .utils import set_active_object

        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        img = bpy.data.images.get(image_name)
        if not img:
            raise ValueError(f"Image not found: {image_name}")

        # Ensure object has a material with the image
        if not obj.data.materials:
            raise ValueError(f"Object has no material: {object_name}")

        # Select image node
        for mat in obj.data.materials:
            if not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image == img:
                    node.select = True
                    mat.node_tree.nodes.active = node

        set_active_object(obj)

        # Set bake settings
        bpy.context.scene.cycles.bake_type = bake_type

        # Execute bake
        bpy.ops.object.bake(
            type=bake_type,
            pass_filter=set(pass_filter or ["COLOR"]),
        )

        return {
            "object_name": obj.name,
            "image_name": img.name,
            "bake_type": bake_type,
        }
    except Exception as e:
        raise fmt_err("bake_texture failed", e)


def save_image(
    image_name: str,
    filepath: str | None = None,
) -> Dict[str, Any]:
    """Save an image to file.

    Args:
        image_name: Name of the image in bpy.data.images.
        filepath: Optional filepath. If None, uses image.filepath.

    Returns:
        {"image_name": str, "filepath": str}
    """
    try:
        img = bpy.data.images.get(image_name)
        if not img:
            raise ValueError(f"Image not found: {image_name}")

        save_path = filepath or img.filepath
        if not save_path:
            raise ValueError("No filepath specified and image has no filepath")

        img.filepath = save_path
        img.save()

        return {"image_name": img.name, "filepath": save_path}
    except Exception as e:
        raise fmt_err("save_image failed", e)
