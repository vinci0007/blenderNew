"""
Compatibility module.

Implementation is split by domain under `blender_provider/skills_impl/`.
This file keeps the old import path stable: `from blender_provider.skills import SKILL_REGISTRY`.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict


def _load_registry() -> Dict[str, Callable[..., Dict[str, Any]]]:
    # Prefer package import; fallback to plain module import for Blender's direct script loading.
    try:
        mod = importlib.import_module(".skills_impl.registry", package=__package__)
    except Exception:
        mod = importlib.import_module("skills_impl.registry")
    return getattr(mod, "SKILL_REGISTRY")


SKILL_REGISTRY = _load_registry()

