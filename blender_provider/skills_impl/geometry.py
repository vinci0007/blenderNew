from typing import Any, Dict, List

import bpy  # type: ignore

from .primitives import create_primitive
from .utils import fmt_err, set_active_object


def create_beveled_box(
    name: str,
    size: List[float],
    location: List[float],
    bevel_width: float = 0.03,
    bevel_segments: int = 3,
) -> Dict[str, Any]:
    try:
        obj = create_primitive(
            primitive_type="cube",
            name=name,
            location=location,
            size=size,
        )
        target = bpy.data.objects.get(obj["object_name"])
        if not target:
            raise RuntimeError("Beveled box target object not found after creation")
        set_active_object(target)

        mod = target.modifiers.new(name="VBF_Bevel", type="BEVEL")
        mod.width = float(bevel_width)
        mod.segments = int(bevel_segments)
        mod.limit_method = "ANGLE"
        return {"object_name": target.name}
    except Exception as e:
        raise fmt_err("create_beveled_box failed", e)

