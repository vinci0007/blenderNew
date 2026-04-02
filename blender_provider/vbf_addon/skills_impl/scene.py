from typing import Any, Dict

import bpy  # type: ignore

from .utils import fmt_err


def scene_clear() -> Dict[str, Any]:
    try:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        return {"ok": True}
    except Exception as e:
        raise fmt_err("scene_clear failed", e)


def delete_object(object_name: str) -> Dict[str, Any]:
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            return {"deleted": False, "object_name": object_name}
        bpy.data.objects.remove(obj, do_unlink=True)
        return {"deleted": True, "object_name": object_name}
    except Exception as e:
        raise fmt_err("delete_object failed", e)


def rename_object(object_name: str, new_name: str) -> Dict[str, Any]:
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        old = obj.name
        obj.name = new_name
        return {"object_name": new_name, "old_name": old}
    except Exception as e:
        raise fmt_err("rename_object failed", e)

