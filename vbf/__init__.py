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

__version__ = "2.2.0"

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
