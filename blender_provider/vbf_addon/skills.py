"""
Addon-local compatibility layer for SKILL_REGISTRY.

We keep this separate so the addon can be installed as a standalone folder
under Blender's `scripts/addons/`.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict


def _load_registry() -> Dict[str, Callable[..., Dict[str, Any]]]:
    try:
        mod = importlib.import_module(".skills_impl.registry", package=__package__)
    except Exception:
        # Fallback order:
        # 1) explicit addon package import
        # 2) script-style loading without package context
        try:
            mod = importlib.import_module("vbf_addon.skills_impl.registry")
        except Exception:
            mod = importlib.import_module("skills_impl.registry")
    return getattr(mod, "SKILL_REGISTRY")


SKILL_REGISTRY = _load_registry()
