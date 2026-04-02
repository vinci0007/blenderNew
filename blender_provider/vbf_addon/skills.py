"""
Addon-local compatibility layer for SKILL_REGISTRY.

We keep this separate so the addon can be installed as a standalone folder
under Blender's `scripts/addons/`.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict


def _load_registry() -> Dict[str, Callable[..., Dict[str, Any]]]:
    mod = importlib.import_module(".skills_impl.registry", package=__package__)
    return getattr(mod, "SKILL_REGISTRY")


SKILL_REGISTRY = _load_registry()

