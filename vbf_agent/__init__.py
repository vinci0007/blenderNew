"""
VBF Agent - Autonomous Modeling Agent for Vibe-Blender-Flow

Single-file agent that wraps VBFClient with autonomous goal decomposition,
self-correction loops, and persistent memory.

Usage:
    from vbf_agent import VBFAgent

    agent = VBFAgent(goal="Create a futuristic drone with neon lights")
    await agent.run()
"""

from .agent import VBFAgent

__all__ = ["VBFAgent"]
__version__ = "0.1.0"