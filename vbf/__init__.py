# VBF - Vibe-Blender-Flow
"""
VBF: Model-agnostic Blender AI integration package.

This package provides adapters for multiple LLM models to interact with
Blender through a standardized JSON-RPC skill interface.

Skills are loaded from Blender via RPC, enabling standalone client usage
without access to the addon directory.

Usage:
from vbf import get_adapter, VBFClient

client = VBFClient()
await client.connect()

adapter = get_adapter("glm-4", client=client)
await adapter.init()  # Loads skills from Blender

messages = adapter.format_messages("Create a cube")
"""

from .adapters import (
    VBFModelAdapter,
    OpenAICompatAdapter,
    SkillRegistry,
    get_registry,
    get_adapter,
    list_supported_models,
    SUPPORTED_MODELS,
)
from .app.client import VBFClient

def _read_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("vibe-blender-flow")
    except Exception:
        try:
            import tomllib
            from pathlib import Path

            pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            return str(data.get("project", {}).get("version", "0+unknown"))
        except Exception:
            return "0+unknown"


__version__ = _read_version()

__all__ = [
    "VBFModelAdapter",
    "OpenAICompatAdapter",
    "SkillRegistry",
    "get_registry",
    "get_adapter",
    "list_supported_models",
    "SUPPORTED_MODELS",
    "VBFClient",
]
