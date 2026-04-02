from typing import Any, Dict

import bpy  # type: ignore

from .utils import fmt_err


def api_validator(api_path: str) -> Dict[str, Any]:
    """Check whether a bpy API path exists and is accessible.

    Useful for discovering available operators and properties before invoking them.

    Args:
        api_path: Dot-separated bpy API path to validate, e.g. "bpy.ops.mesh.primitive_cube_add"
            or "ops.mesh.primitive_cube_add" (the "bpy." prefix is optional).

    Returns:
        {"ok": bool, "api_path": str} on success, or
        {"ok": False, "api_path": str, "missing": str} if a path segment is not found.
    """
    try:
        if not api_path:
            raise ValueError("api_path is empty")

        path = api_path.strip()
        if path.startswith("bpy."):
            path = path[len("bpy.") :]

        parts = [p for p in path.split(".") if p]
        cur: Any = bpy
        for part in parts:
            if not hasattr(cur, part):
                return {"ok": False, "api_path": api_path, "missing": part}
            cur = getattr(cur, part)
        return {"ok": True, "api_path": api_path}
    except Exception as e:
        raise fmt_err("api_validator failed", e)

