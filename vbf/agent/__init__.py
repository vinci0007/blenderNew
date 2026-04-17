"""
VBF Agent - Autonomous Blender Modeling Agent

A lightweight wrapper around VBFClient that adds:
- Conversation memory (cross-task context persistence)
- Autonomous execution loop (no manual checkpoint confirmations)
- Tool exposure for Agent SDK integration
- Session management (user preferences, project history)

Does NOT modify any existing vbf/ code.

Usage:
    from vbf.agent import VBFAgent

    agent = VBFAgent()
    result = await agent.run("create a smartphone")

    # Or with tools (Agent SDK style)
    tools = agent.tools  # [{"type": "function", "function": {...}}, ...]
"""

from .agent import VBFAgent, AgentStatus, AgentTask, AgentMessage, SessionMemory

__all__ = [
    "VBFAgent",
    "AgentStatus",
    "AgentTask",
    "AgentMessage",
    "SessionMemory",
]