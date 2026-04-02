from typing import Any, Dict, List

import bpy  # type: ignore

from .utils import ensure_object_mode, fmt_err, set_active_object


def boolean_tool(
    target_name: str,
    tool_name: str,
    operation: str = "difference",
    apply: bool = True,
    delete_tool: bool = True,
) -> Dict[str, Any]:
    try:
        target = bpy.data.objects.get(target_name)
        tool = bpy.data.objects.get(tool_name)
        if not target:
            raise ValueError(f"target object not found: {target_name}")
        if not tool:
            raise ValueError(f"tool object not found: {tool_name}")

        ensure_object_mode()
        set_active_object(target)

        op_map = {"difference": "DIFFERENCE", "union": "UNION", "intersect": "INTERSECT"}
        if operation not in op_map:
            raise ValueError(f"Unknown boolean operation: {operation}")

        mod = target.modifiers.new(name="VBF_Boolean", type="BOOLEAN")
        mod.operation = op_map[operation]
        mod.object = tool

        if apply:
            bpy.ops.object.modifier_apply(modifier=mod.name)

        if delete_tool:
            bpy.data.objects.remove(tool, do_unlink=True)

        return {"object_name": target.name}
    except Exception as e:
        raise fmt_err("boolean_tool failed", e)


def join_objects(object_names: List[str], new_name: str | None = None) -> Dict[str, Any]:
    try:
        if not object_names:
            raise ValueError("object_names is empty")

        objs = []
        for n in object_names:
            o = bpy.data.objects.get(n)
            if not o:
                raise ValueError(f"Object not found for join: {n}")
            objs.append(o)

        ensure_object_mode()
        for o in bpy.context.selected_objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.join()

        final = bpy.context.active_object
        if not final:
            raise RuntimeError("Join failed to produce an active object")
        if new_name:
            final.name = new_name
        return {"object_name": final.name}
    except Exception as e:
        raise fmt_err("join_objects failed", e)

