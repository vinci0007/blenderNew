from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


class TaskState:
    """Snapshot of a modeling task at a given step index, for resume support.

    Memory-optimized with __slots__ to reduce per-instance memory overhead.
    """

    __slots__ = [
        'prompt', 'plan', 'steps', 'step_results',
        'current_step_index', 'allowed_skills', 'skill_schemas', 'saved_at'
    ]

    def __init__(
        self,
        prompt: str,
        plan: Dict[str, Any],
        steps: List[Dict[str, Any]],
        step_results: Dict[str, Dict[str, Any]],
        current_step_index: int,
        allowed_skills: List[str],
        skill_schemas: Optional[Dict[str, Any]] = None,
    ):
        self.prompt = prompt
        self.plan = plan
        self.steps = steps
        self.step_results = step_results
        self.current_step_index = current_step_index
        self.allowed_skills = allowed_skills
        self.skill_schemas = skill_schemas
        self.saved_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vbf_state_version": "1.0",
            "saved_at": self.saved_at or time.time(),
            "prompt": self.prompt,
            "plan": self.plan,
            "steps": self.steps,
            "step_results": self.step_results,
            "current_step_index": self.current_step_index,
            "allowed_skills": self.allowed_skills,
            "skill_schemas": self.skill_schemas,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskState":
        state = cls(
            prompt=data["prompt"],
            plan=data["plan"],
            steps=data["steps"],
            step_results=data["step_results"],
            current_step_index=data["current_step_index"],
            allowed_skills=data["allowed_skills"],
            skill_schemas=data.get("skill_schemas"),
        )
        state.saved_at = data.get("saved_at")
        return state

    def save(self, path: str) -> None:
        self.saved_at = time.time()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "TaskState":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


class TaskInterruptedError(RuntimeError):
    """Task was interrupted (LLM error); state has been saved for resume."""

    def __init__(self, message: str, state: TaskState, state_path: str):
        super().__init__(message)
        self.state = state
        self.state_path = state_path
