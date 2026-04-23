"""
VBF Agent - Autonomous Blender Modeling Agent

A lightweight, non-invasive wrapper around VBFClient that adds:
- Conversation memory (cross-task context persistence)
- Autonomous execution loop (no manual checkpoints)
- Tool exposure for Agent SDK integration
- Session management (user preferences, project history)

Does NOT modify VBFClient or any existing vbf/ code.
All state is stored in vbf/agent/memory/ directory.

Usage:
    from vbf.agent import VBFAgent

    agent = VBFAgent()
    result = await agent.run("create a smartphone")
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from ..config_runtime import load_project_paths

try:
    from ..app.client import VBFClient
    from ..core.task_state import TaskInterruptedError
except ImportError:
    # Blender not available - agent can still manage sessions
    VBFClient = None
    TaskInterruptedError = None


class AgentStatus(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """A single message in the agent conversation history."""

    id: str
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTask:
    """A modeling task managed by the agent."""

    id: str
    user_prompt: str
    created_at: float
    status: AgentStatus
    vbf_task_state_path: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    steps_executed: int = 0
    completed_at: Optional[float] = None


class SessionMemory:
    """Persistent session memory for cross-task context.

    Stores:
    - Conversation history (AgentMessage list)
    - User preferences (style, detail level, etc.)
    - Project history (past tasks and outcomes)
    - Current Blender scene context snapshot

    All persisted to JSON files in vbf/agent/memory/
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.memory_dir = Path(__file__).parent / "memory" / self.session_id
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.messages: List[AgentMessage] = []
        self.preferences: Dict[str, Any] = {}
        self.project_history: List[Dict[str, Any]] = []
        self.scene_snapshot: Dict[str, Any] = {}

        self._load()

    def _load(self):
        """Load session state from disk."""
        msgs_path = self.memory_dir / "messages.json"
        if msgs_path.exists():
            with open(msgs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.messages = [AgentMessage(**m) for m in data.get("messages", [])]
                self.preferences = data.get("preferences", {})
                self.project_history = data.get("project_history", [])

        prefs_path = self.memory_dir / "preferences.json"
        if prefs_path.exists():
            with open(prefs_path, "r", encoding="utf-8") as f:
                self.preferences = json.load(f)

    def save(self):
        """Persist session state to disk."""
        msgs_path = self.memory_dir / "messages.json"
        with open(msgs_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "session_id": self.session_id,
                    "messages": [
                        {
                            "id": m.id,
                            "role": m.role,
                            "content": m.content,
                            "timestamp": m.timestamp,
                            "metadata": m.metadata,
                        }
                        for m in self.messages
                    ],
                    "preferences": self.preferences,
                    "project_history": self.project_history,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add a message to conversation history."""
        self.messages.append(
            AgentMessage(
                id=str(uuid.uuid4()),
                role=role,
                content=content,
                timestamp=time.time(),
                metadata=metadata or {},
            )
        )
        # Keep last 100 messages
        if len(self.messages) > 100:
            self.messages = self.messages[-100:]
        self.save()

    def update_preference(self, key: str, value: Any):
        """Update a user preference."""
        self.preferences[key] = value
        self.save()

    def get_recent_context(self, max_messages: int = 10) -> str:
        """Build context string from recent messages."""
        recent = self.messages[-max_messages:]
        ctx_parts = []
        for m in recent:
            role_label = {"user": "User", "assistant": "Assistant"}.get(m.role, m.role)
            ctx_parts.append(f"[{role_label}]: {m.content[:200]}")
        return "\n".join(ctx_parts)

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return self.preferences.get(key, default)


class VBFAgent:
    """
    Autonomous Blender Modeling Agent.

    Wraps VBFClient without modifying it. Adds:
    - Session memory (user preferences, conversation history)
    - Autonomous execution (no manual checkpoint confirmations)
    - Tool exposure for Agent SDK integration
    - Status tracking and streaming progress

    Design principles:
    1. Zero changes to existing vbf/ code
    2. All agent state in vbf/agent/memory/
    3. VBFClient instantiated once, reused across tasks
    4. Graceful degradation if Blender not available
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        blender_path: Optional[str] = None,
        session_id: Optional[str] = None,
        auto_retry: int = 3,
        auto_retry_delay: float = 2.0,
        stream_callback: Optional[callable] = None,
    ):
        """
        Initialize VBF Agent.

        Args:
            host: WebSocket host (default: 127.0.0.1)
            port: WebSocket port (default: 8006)
            blender_path: Blender executable path
            session_id: Optional session ID for memory persistence
            auto_retry: Max retries on step failure before giving up
            auto_retry_delay: Seconds between retries (exponential backoff)
            stream_callback: Optional async callback(status, message) for progress
        """
        self.host = host or os.getenv("VBF_WS_HOST", "127.0.0.1")
        self.port = port or int(os.getenv("VBF_WS_PORT", "8006"))
        self.blender_path = blender_path
        self.session_id = session_id
        self.auto_retry = auto_retry
        self.auto_retry_delay = auto_retry_delay
        self.stream_callback = stream_callback

        # Lazy-init client (needs Blender running)
        self._client: Optional[VBFClient] = None
        self._client_initialized = False

        # Agent state
        self.status = AgentStatus.IDLE
        self.current_task: Optional[AgentTask] = None
        self.session = SessionMemory(session_id)

        # Tool definitions for Agent SDK compatibility
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "vbf_create_model",
                    "description": "Create a 3D model in Blender from a natural language description. Use this as the primary tool for any modeling request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "Natural language description of the model to create. Be specific about shape, proportions, and details.",
                            },
                            "style": {
                                "type": "string",
                                "description": "Optional style preset: hard_surface_realistic, stylized_low_poly, organic_character, industrial_prop",
                                "default": "hard_surface_realistic",
                            },
                        },
                        "required": ["prompt"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vbf_resume_task",
                    "description": "Resume an interrupted modeling task from a saved checkpoint.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "state_path": {
                                "type": "string",
                                "description": "Path to the task state JSON file (default: vbf/cache/task_state.json)",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vbf_get_scene",
                    "description": "Capture and return the current Blender scene state (objects, materials, animations).",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vbf_list_skills",
                    "description": "List all available Blender skills. Returns skill names and brief descriptions.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    # --- Client lifecycle ---

    def _get_client(self) -> Optional[VBFClient]:
        """Get or create VBFClient (lazy init)."""
        if self._client is None:
            if VBFClient is None:
                return None
            self._client = VBFClient(
                host=self.host,
                port=self.port,
                blender_path=self.blender_path,
            )
        return self._client

    async def connect(self) -> bool:
        """Connect to Blender WebSocket server. Returns True if connected."""
        client = self._get_client()
        if client is None:
            return False
        try:
            self.status = AgentStatus.CONNECTING
            await self._emit("connecting", "Connecting to Blender...")
            await client.ensure_connected()
            self._client_initialized = True
            self.status = AgentStatus.IDLE
            await self._emit("connected", "Connected to Blender")
            return True
        except Exception as e:
            self.status = AgentStatus.FAILED
            await self._emit("error", f"Connection failed: {e}")
            return False

    # --- Main agent loop ---

    async def run(self, user_prompt: str, style: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a modeling task autonomously.

        This is the main entry point. The agent will:
        1. Connect to Blender if not connected
        2. Generate execution plan via LLM
        3. Execute steps with automatic error recovery
        4. Handle failures with retry/rollback
        5. Report completion or failure

        Args:
            user_prompt: Natural language description of the model
            style: Optional style preset

        Returns:
            Dict with keys: ok, task_id, result, error, steps_executed
        """
        task_id = str(uuid.uuid4())[:8]
        self.current_task = AgentTask(
            id=task_id,
            user_prompt=user_prompt,
            created_at=time.time(),
            status=AgentStatus.PLANNING,
        )

        self.session.add_message("user", user_prompt, {"task_id": task_id, "style": style})
        await self._emit("status", f"[{task_id}] Planning: {user_prompt[:50]}...")

        # Auto-apply user preferences
        if style is None:
            style = self.session.get_preference("default_style", "hard_surface_realistic")

        # Connect if needed
        if not self._client_initialized:
            if not await self.connect():
                return self._fail_result(task_id, "Failed to connect to Blender")

        client = self._get_client()
        assert client is not None

        try:
            self.status = AgentStatus.EXECUTING

            # Run the task (VBFClient.run_task handles planning + execution)
            resume_path = self.session.get_preference(f"last_task_path_{task_id}")

            if resume_path and os.path.exists(resume_path):
                await self._emit("status", f"[{task_id}] Resuming from {resume_path}")
                result = await client.run_task(
                    user_prompt,
                    resume_state_path=resume_path,
                )
            else:
                # Apply style if specified
                if style:
                    await self._emit("status", f"[{task_id}] Style: {style}")
                result = await client.run_task(
                    user_prompt,
                    style=style,
                )

            self.current_task.status = AgentStatus.COMPLETED
            self.current_task.completed_at = time.time()
            self.current_task.result = result
            self.current_task.steps_executed = len(result.get("steps", []))

            # Save to project history
            self._record_completion(task_id, user_prompt, result, style)

            self.status = AgentStatus.IDLE
            await self._emit("completed", f"[{task_id}] Done: {self.current_task.steps_executed} steps")

            self.session.add_message(
                "assistant",
                f"Completed: {user_prompt} ({self.current_task.steps_executed} steps)",
                {"task_id": task_id, "result": result},
            )

            return self._ok_result(task_id, result)

        except TaskInterruptedError as e:
            self.current_task.status = AgentStatus.WAITING
            self.current_task.vbf_task_state_path = e.state_path
            self.session.update_preference(f"last_task_path_{task_id}", e.state_path)
            await self._emit(
                "waiting",
                f"[{task_id}] Interrupted, state saved. Resume with vbf_resume_task",
            )
            return {
                "ok": False,
                "task_id": task_id,
                "error": str(e),
                "interrupted": True,
                "resume_path": e.state_path,
            }

        except Exception as e:
            self.current_task.status = AgentStatus.FAILED
            self.current_task.error = str(e)
            self.status = AgentStatus.FAILED
            await self._emit("error", f"[{task_id}] Failed: {e}")
            return self._fail_result(task_id, str(e))

    # --- Tools (Agent SDK compatible) ---

    async def tool_create_model(self, prompt: str, style: str = "hard_surface_realistic") -> Dict[str, Any]:
        """Tool wrapper: vbf_create_model."""
        return await self.run(prompt, style=style)

    async def tool_resume_task(self, state_path: Optional[str] = None) -> Dict[str, Any]:
        """Tool wrapper: vbf_resume_task."""
        state_path = state_path or load_project_paths()["task_state_file"]
        if not os.path.exists(state_path):
            return {"ok": False, "error": f"State file not found: {state_path}"}

        client = self._get_client()
        if client is None:
            return {"ok": False, "error": "Blender not available"}

        await self._emit("status", f"Resuming from {state_path}")
        try:
            result = await client.run_task("continue", resume_state_path=state_path)
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def tool_get_scene(self) -> Dict[str, Any]:
        """Tool wrapper: vbf_get_scene."""
        client = self._get_client()
        if client is None:
            return {"ok": False, "error": "Blender not available"}
        try:
            scene = await client.capture_scene_state()
            self.session.scene_snapshot = scene.to_dict()
            return {"ok": True, "scene": scene.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def tool_list_skills(self) -> Dict[str, Any]:
        """Tool wrapper: vbf_list_skills."""
        client = self._get_client()
        if client is None:
            return {"ok": False, "error": "Blender not available"}
        try:
            skills = await client.list_skills()
            return {"ok": True, "skills": skills, "count": len(skills)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # --- Session management ---

    def get_context(self) -> str:
        """Get current conversation context for LLM prompts."""
        return self.session.get_recent_context()

    def get_preferences(self) -> Dict[str, Any]:
        """Get all user preferences."""
        return self.session.preferences.copy()

    def set_preference(self, key: str, value: Any):
        """Set a user preference (persisted to disk)."""
        self.session.update_preference(key, value)

    # --- Internal helpers ---

    async def _emit(self, event: str, message: str):
        """Emit a status event via callback if registered."""
        if self.stream_callback:
            try:
                await self.stream_callback(event, message)
            except Exception:
                pass
        print(f"[VBF-Agent] {event.upper()}: {message}")

    def _ok_result(self, task_id: str, result: Any) -> Dict[str, Any]:
        return {
            "ok": True,
            "task_id": task_id,
            "result": result,
            "steps_executed": self.current_task.steps_executed,
        }

    def _fail_result(self, task_id: str, error: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "task_id": task_id,
            "error": error,
            "steps_executed": self.current_task.steps_executed or 0,
        }

    def _record_completion(self, task_id: str, prompt: str, result: Dict, style: Optional[str]):
        """Save completed task to project history."""
        self.session.project_history.append(
            {
                "task_id": task_id,
                "prompt": prompt,
                "style": style,
                "completed_at": datetime.now().isoformat(),
                "steps": len(result.get("steps", [])),
                "objects": [o.get("name") for o in result.get("objects", [])],
            }
        )
        self.session.save()

        # Auto-learn preferences
        if style:
            self.session.update_preference("default_style", style)
