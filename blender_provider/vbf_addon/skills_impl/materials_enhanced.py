# Enhanced Materials - PBR Workflow Support
# Based on CG Boost and industry standard PBR workflows
from typing import Any, Dict, List, Optional, Tuple

import bpy

from .utils import fmt_err, set_active_object


def create_material_pbr(
    name: str,
    base_color: List[float] = [0.8, 0.8, 0.8, 1.0],
    metallic: float = 0.0,
    roughness: float = 0.5,
    specular: float = 0.5,
    specular_tint: float = 0.0,
    subsurface: float = 0.0,
    subsurface_color: List[float] = [1.0, 0.8, 0.7],
    subsurface_radius: List[float] = [1.0, 0.4, 0.1],
    emission: List[float] = [0.0, 0.0, 0.0, 1.0],
    emission_strength: float = 1.0,
    alpha: float = 1.0,
    normal_strength: float = 1.0,
    displacement_scale: float = 0.0,
    ior: float = 1.45,
    transmission: float = 0.0,
    transmission_roughness: float = 0.0,
    sheen: float = 0.0,
    sheen_tint: float = 0.5,
    clearcoat: float = 0.0,
    clearcoat_roughness: float = 0.03,
    anisotropic: float = 0.0,
    anisotropic_rotation: float = 0.0,
) -> Dict[str, Any]:
    """Create a complete PBR material with Principled BSDF.

    Industry-standard PBR material creation following CG Boost workflows.
    Supports all major PBR parameters from simple diffuse to complex
    metals, glass, and skin.

    Args:
        name: Material name.
        base_color: RGBA base color [r, g, b, a].
        metallic: Metallic factor (0.0 = dielectric, 1.0 = metal).
        roughness: Surface roughness (0.0 = mirror, 1.0 = diffuse).
        specular: Specular reflection amount (for non-metals).
        specular_tint: Tint specular towards base color.
        subsurface: Subsurface scattering amount.
        subsurface_color: Subsurface scattering color [r, g, b].
        subsurface_radius: Scattering distance per channel [r, g, b].
        emission: Emission color [r, g, b, a].
        emission_strength: Emission brightness.
        alpha: Opacity (1.0 = opaque, 0.0 = transparent).
        normal_strength: Bump/Normal strength multiplier.
        displacement_scale: Displacement amount.
        ior: Index of refraction (glass: 1.45, water: 1.33).
        transmission: Transmission (0.0 = opaque, 1.0 = glass).
        transmission_roughness: Roughness of transmission.
        sheen: Velvet-like sheen effect.
        sheen_tint: Sheen color tint.
        clearcoat: Clear coat layer (car paint, varnish).
        clearcoat_roughness: Clear coat roughness.
        anisotropic: Anisotropic reflection (brushed metal).
        anisotropic_rotation: Rotation of anisotropy.

    Returns:
        {"material_name": str, "pbr_setup": bool, "parameters": dict}

    Example:
        # Basic plastic
        create_material_pbr("Plastic", base_color=[0.2, 0.3, 0.8], roughness=0.3)

        # Brushed metal
        create_material_pbr("Metal", base_color=[0.8, 0.8, 0.9], metallic=1.0,
                            roughness=0.3, anisotropic=0.8)

        # Glass
        create_material_pbr("Glass", base_color=[1, 1, 1], roughness=0.0,
                            transmission=1.0, ior=1.45)

        # Skin
        create_material_pbr("Skin", base_color=[0.8, 0.6, 0.5], roughness=0.4,
                            subsurface=0.5, subsurface_color=[1, 0.8, 0.7])
    """
    try:
        # Create material
        if name in bpy.data.materials:
            mat = bpy.data.materials[name]
            mat.use_nodes = True
        else:
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True

        # Clear existing nodes
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        # Create Principled BSDF
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        bsdf.name = "Principled BSDF"

        # Create Output
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (300, 0)

        # Link BSDF to output
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

        # Set parameters
        bsdf.inputs["Base Color"].default_value = tuple(base_color)
        bsdf.inputs["Metallic"].default_value = float(metallic)
        bsdf.inputs["Roughness"].default_value = float(roughness)
        bsdf.inputs["Specular IOR Level"].default_value = float(specular)
        bsdf.inputs["Specular Tint"].default_value = float(specular_tint)
        bsdf.inputs["Subsurface Weight"].default_value = float(subsurface)
        bsdf.inputs["Subsurface Radius"].default_value = tuple(subsurface_radius)
        bsdf.inputs["Subsurface Scale"].default_value = 1.0
        # Note: Subsurface color is linked through the radius in newer Blender
        bsdf.inputs["Emission Color"].default_value = tuple(emission)
        bsdf.inputs["Emission Strength"].default_value = float(emission_strength)
        bsdf.inputs["Alpha"].default_value = float(alpha)
        bsdf.inputs["Coat Weight"].default_value = float(clearcoat)
        bsdf.inputs["Coat Roughness"].default_value = float(clearcoat_roughness)
        bsdf.inputs["Sheen Weight"].default_value = float(sheen)
        bsdf.inputs["Sheen Tint"].default_value = float(sheen_tint)
        bsdf.inputs["IOR"].default_value = float(ior)
        bsdf.inputs["Transmission Weight"].default_value = float(transmission)
        bsdf.inputs["Transmission Roughness"].default_value = float(transmission_roughness)
        bsdf.inputs["Anisotropic"].default_value = float(anisotropic)
        bsdf.inputs["Anisotropic Rotation"].default_value = float(anisotropic_rotation)

        # Add normal input (will be used by normal map texture if added)
        bsdf.inputs["Normal"].default_value = (0, 0, 0)

        return {
            "ok": True,
            "material_name": mat.name,
            "pbr_setup": True,
            "parameters": {
                "base_color": base_color,
                "metallic": metallic,
                "roughness": roughness,
                "transmission": transmission,
                "subsurface": subsurface,
                "clearcoat": clearcoat,
            },
            "node_count": len(nodes),
        }
    except Exception as e:
        raise fmt_err("create_material_pbr failed", e)


def attach_texture_to_material(
    material_name: str,
    texture_type: str,
    image_path: str,
    color_space: str = "sRGB",
    normal_type: str = "OPEN_GL",
    uv_map: str = "UVMap",
) -> Dict[str, Any]:
    """Attach a texture to a PBR material.

    Args:
        material_name: Target material name.
        texture_type: "BASE_COLOR" | "METALLIC" | "ROUGHNESS" |
                      "NORMAL" | "HEIGHT" | "SPECULAR" |
                      "SUBSURFACE" | "EMISSION" | "ALPHA".
        image_path: Path to image file.
        color_space: "sRGB" | "Linear" | "Non-Color".
        normal_type: "OPEN_GL" | "DIRECTX" (for normal maps).
        uv_map: UV map name to use.

    Returns:
        {"material_name": str, "texture_type": str, "attached": bool}
    """
    try:
        if material_name not in bpy.data.materials:
            raise ValueError(f"Material not found: {material_name}")

        mat = bpy.data.materials[material_name]
        if not mat.use_nodes:
            mat.use_nodes = True

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Find Principled BSDF
        bsdf = None
        for node in nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node
                break

        if not bsdf:
            raise ValueError(f"Principled BSDF not found in {material_name}")

        # Load image
        if image_path in bpy.data.images:
            image = bpy.data.images[image_path]
        else:
            image = bpy.data.images.load(image_path, check_existing=True)

        image.colorspace_settings.name = color_space

        # Create image texture node
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.name = f"{texture_type}_Texture"
        tex_node.image = image
        tex_node.location = (-600, -200 * len(nodes))

        # Add UV mapping node
        uv_node = nodes.new("ShaderNodeUVMap")
        uv_node.uv_map = uv_map
        uv_node.location = (-800, tex_node.location[1])
        links.new(uv_node.outputs["UV"], tex_node.inputs["Vector"])

        # Connect based on texture type
        if texture_type == "BASE_COLOR":
            links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
            socket = "Color"
        elif texture_type == "METALLIC":
            links.new(tex_node.outputs["Color"], bsdf.inputs["Metallic"])
            image.colorspace_settings.name = "Non-Color"
            socket = "Color"
        elif texture_type == "ROUGHNESS":
            links.new(tex_node.outputs["Color"], bsdf.inputs["Roughness"])
            image.colorspace_settings.name = "Non-Color"
            socket = "Color"
        elif texture_type == "SPECULAR":
            links.new(tex_node.outputs["Color"], bsdf.inputs["Specular IOR Level"])
            image.colorspace_settings.name = "Non-Color"
            socket = "Color"
        elif texture_type == "NORMAL":
            # Create normal map node
            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.location = (-300, tex_node.location[1])
            normal_map.uv_map = uv_map

            # Connect texture to normal map
            links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
            links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
            socket = "Color"
        elif texture_type == "HEIGHT":
            # Bump/displacement
            bump = nodes.new("ShaderNodeBump")
            bump.location = (-300, tex_node.location[1])
            links.new(tex_node.outputs["Color"], bump.inputs["Height"])
            links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
            socket = "Height"
        elif texture_type == "EMISSION":
            links.new(tex_node.outputs["Color"], bsdf.inputs["Emission Color"])
            socket = "Color"
        elif texture_type == "ALPHA":
            links.new(tex_node.outputs["Color"], bsdf.inputs["Alpha"])
            mat.blend_method = "BLEND"
            socket = "Color"
        elif texture_type == "SUBSURFACE":
            links.new(tex_node.outputs["Color"], bsdf.inputs["Subsurface Weight"])
            socket = "Color"
        else:
            socket = "None"

        return {
            "ok": True,
            "material_name": material_name,
            "texture_type": texture_type,
            "image": image.name,
            "color_space": color_space,
            "attached": True,
            "socket": socket,
        }
    except Exception as e:
        raise fmt_err("attach_texture_to_material failed", e)


def create_material_preset(
    preset_name: str,
    material_name: str,
) -> Dict[str, Any]:
    """Create material from predefined preset.

    Presets: "PLASTIC", "METAL", "GLASS", "SKIN", "WOOD", "STONE",
            "CAR_PAINT", "EMISSIVE", "MATTE", "GLOSSY".

    Args:
        preset_name: Preset type.
        material_name: Name for the new material.

    Returns:
        {"preset": str, "material_name": str, "settings": dict}
    """
    presets = {
        "PLASTIC": {
            "base_color": [0.8, 0.1, 0.1, 1.0],
            "metallic": 0.0,
            "roughness": 0.2,
            "specular": 0.5,
        },
        "METAL": {
            "base_color": [0.9, 0.9, 0.95, 1.0],
            "metallic": 1.0,
            "roughness": 0.2,
            "specular": 0.5,
        },
        "ROUGH_METAL": {
            "base_color": [0.6, 0.6, 0.65, 1.0],
            "metallic": 1.0,
            "roughness": 0.7,
            "anisotropic": 0.3,
        },
        "GOLD": {
            "base_color": [1.0, 0.76, 0.33, 1.0],
            "metallic": 1.0,
            "roughness": 0.1,
        },
        "GLASS": {
            "base_color": [1.0, 1.0, 1.0, 1.0],
            "metallic": 0.0,
            "roughness": 0.0,
            "transmission": 1.0,
            "ior": 1.45,
        },
        "SKIN": {
            "base_color": [0.8, 0.6, 0.5, 1.0],
            "metallic": 0.0,
            "roughness": 0.4,
            "subsurface": 0.5,
            "subsurface_color": [1.0, 0.8, 0.7],
            "subsurface_radius": [1.0, 0.4, 0.1],
        },
        "CAR_PAINT": {
            "base_color": [0.8, 0.0, 0.0, 1.0],
            "metallic": 0.6,
            "roughness": 0.1,
            "clearcoat": 1.0,
            "clearcoat_roughness": 0.03,
        },
        "EMISSIVE": {
            "base_color": [0, 0, 0, 1.0],
            "emission": [1.0, 0.8, 0.5, 1.0],
            "emission_strength": 5.0,
        },
        "MATTE": {
            "base_color": [0.5, 0.5, 0.5, 1.0],
            "metallic": 0.0,
            "roughness": 1.0,
        },
        "GLOSSY": {
            "base_color": [0.9, 0.9, 0.9, 1.0],
            "metallic": 0.0,
            "roughness": 0.05,
        },
    }

    preset_name_upper = preset_name.upper()
    if preset_name_upper not in presets:
        available = ", ".join(presets.keys())
        raise ValueError(f"Unknown preset '{preset_name}'. Available: {available}")

    settings = presets[preset_name_upper]

    # Create material with preset
    result = create_material_pbr(name=material_name, **settings)

    return {
        "ok": True,
        "preset": preset_name_upper,
        "material_name": result["material_name"],
        "settings": settings,
    }


def set_material_ior(
    material_name: str,
    ior: float,
) -> Dict[str, Any]:
    """Set Index of Refraction for a material.

    Common IOR values:
    - Water: 1.33
    - Glass: 1.45-1.55
    - Diamond: 2.42
    - Plastic: 1.45-1.55
    - Metal: Use complex IOR in base color

    Args:
        material_name: Target material.
        ior: Index of refraction value.

    Returns:
        {"material_name": str, "ior": float}
    """
    try:
        if material_name not in bpy.data.materials:
            raise ValueError(f"Material not found: {material_name}")

        mat = bpy.data.materials[material_name]
        if not mat.use_nodes:
            raise ValueError(f"Material {material_name} doesn't use nodes")

        # Find Principled BSDF
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                node.inputs["IOR"].default_value = float(ior)
                break

        return {
            "ok": True,
            "material_name": material_name,
            "ior": ior,
        }
    except Exception as e:
        raise fmt_err("set_material_ior failed", e)
