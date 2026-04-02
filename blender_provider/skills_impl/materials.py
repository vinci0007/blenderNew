from typing import Any, Dict, List

import bpy  # type: ignore

from .utils import fmt_err, vec3


def create_material_simple(
    name: str,
    base_color: List[float],
    roughness: float = 0.4,
    metallic: float = 0.0,
) -> Dict[str, Any]:
    """Create or update a Principled BSDF material with basic PBR properties.

    If a material with the given name already exists it is updated in place.

    Args:
        name: Name of the material to create or update.
        base_color: [r, g, b] color values in linear space (0.0–1.0 each).
        roughness: Surface roughness (0.0 = mirror, 1.0 = fully diffuse). Defaults to 0.4.
        metallic: Metallic factor (0.0 = dielectric, 1.0 = fully metallic). Defaults to 0.0.

    Returns:
        {"material_name": str} — the name of the created/updated material.
    """
    try:
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name=name)

        mat.use_nodes = True
        nodes = mat.node_tree.nodes

        principled = None
        for n in nodes:
            if n.type == "BSDF_PRINCIPLED":
                principled = n
                break
        if principled is None:
            raise RuntimeError("Could not find Principled BSDF node")

        r, g, b = vec3(base_color)
        principled.inputs["Base Color"].default_value = (r, g, b, 1.0)
        principled.inputs["Roughness"].default_value = float(roughness)
        principled.inputs["Metallic"].default_value = float(metallic)

        return {"material_name": mat.name}
    except Exception as e:
        raise fmt_err("create_material_simple failed", e)


def assign_material(object_name: str, material_name: str, slot_index: int = 0) -> Dict[str, Any]:
    """Assign an existing material to a material slot on an object.

    Args:
        object_name: Name of the mesh object to assign the material to.
        material_name: Name of the material to assign (must already exist).
        slot_index: Material slot index to assign to. Slots are created automatically
            if the object has fewer slots than required. Defaults to 0.

    Returns:
        {"object_name": str, "material_name": str, "slot_index": int}.
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        mat = bpy.data.materials.get(material_name)
        if not mat:
            raise ValueError(f"Material not found: {material_name}")
        if not hasattr(obj.data, "materials"):
            raise ValueError("Object has no mesh data materials")

        mats = obj.data.materials
        while len(mats) <= slot_index:
            mats.append(None)
        mats[slot_index] = mat
        return {"object_name": obj.name, "material_name": mat.name, "slot_index": int(slot_index)}
    except Exception as e:
        raise fmt_err("assign_material failed", e)

