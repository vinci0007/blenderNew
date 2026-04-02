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
    """Apply a boolean modifier from one mesh object onto another.

    Args:
        target_name: Name of the target (base) object that receives the modifier.
        tool_name: Name of the tool object used as the boolean operand.
        operation: Boolean operation to perform. Enum: "difference" | "union" | "intersect".
            Defaults to "difference".
        apply: If True (default), the modifier is applied immediately so the result is
            baked into the mesh. If False, the modifier is added but left unapplied.
        delete_tool: If True (default), the tool object is removed from the scene after
            the operation. Set to False to keep it.

    Returns:
        {"object_name": str} — the name of the target object after the operation.
    """
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
    """Merge multiple mesh objects into a single object.

    Args:
        object_names: List of object names to merge. All objects must exist in the scene.
            The first object in the list becomes the active (base) object for the join.
        new_name: Optional name for the resulting merged object. If omitted, the result
            keeps the name of the first object in `object_names`.

    Returns:
        {"object_name": str} — the name of the merged object.
    """
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
