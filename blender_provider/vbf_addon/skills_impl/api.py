from typing import Any, Dict

import bpy  # type: ignore

from .utils import fmt_err


def api_validator(api_path: str) -> Dict[str, Any]:
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

