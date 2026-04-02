from typing import Any, Dict, List

import bpy  # type: ignore

from .utils import fmt_err, vec3


def create_material_simple(
    name: str,
    base_color: List[float],
    roughness: float = 0.4,
    metallic: float = 0.0,
) -> Dict[str, Any]:
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

