from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


class TaskLedger:
    """Persistent progress ledger for batched planning and recovery."""

    def __init__(
        self,
        *,
        task_id: str,
        prompt: str,
        stages: List[str],
        current_stage_index: int = 0,
        current_batch_index: int = 0,
        planned_batches: Optional[List[Dict[str, Any]]] = None,
        completed_batches: Optional[List[Dict[str, Any]]] = None,
        pending_work: Optional[List[str]] = None,
        last_response_id: Optional[str] = None,
        last_error: Optional[str] = None,
    ):
        self.task_id = task_id
        self.prompt = prompt
        self.stages = stages
        self.current_stage_index = current_stage_index
        self.current_batch_index = current_batch_index
        self.planned_batches = planned_batches or []
        self.completed_batches = completed_batches or []
        self.pending_work = pending_work or []
        self.last_response_id = last_response_id
        self.last_error = last_error
        self.saved_at: Optional[float] = None

    @property
    def current_stage(self) -> str:
        if not self.stages:
            return "geometry_modeling"
        idx = max(0, min(self.current_stage_index, len(self.stages) - 1))
        return self.stages[idx]

    @staticmethod
    def _batch_key(stage: str, batch_index: int) -> tuple[str, int]:
        return str(stage), int(batch_index)

    def _record_batch_in(
        self,
        target: List[Dict[str, Any]],
        *,
        stage: str,
        batch_index: int,
        step_ids: List[str],
        continue_stage: bool,
        remaining_work: Optional[List[str]] = None,
        response_id: Optional[str] = None,
    ) -> None:
        key = self._batch_key(stage, batch_index)
        payload = {
            "stage": stage,
            "batch_index": batch_index,
            "step_ids": step_ids,
            "continue_stage": continue_stage,
            "remaining_work": remaining_work or [],
            "completed_at": time.time(),
        }
        for idx, existing in enumerate(target):
            if self._batch_key(existing.get("stage", ""), int(existing.get("batch_index") or 0)) == key:
                target[idx] = payload
                break
        else:
            target.append(payload)
        self.current_batch_index = batch_index
        self.pending_work = remaining_work or []
        if response_id:
            self.last_response_id = response_id

    def record_planned_batch(
        self,
        *,
        stage: str,
        batch_index: int,
        step_ids: List[str],
        continue_stage: bool,
        remaining_work: Optional[List[str]] = None,
        response_id: Optional[str] = None,
    ) -> None:
        self._record_batch_in(
            self.planned_batches,
            stage=stage,
            batch_index=batch_index,
            step_ids=step_ids,
            continue_stage=continue_stage,
            remaining_work=remaining_work,
            response_id=response_id,
        )

    def record_completed_batch(
        self,
        *,
        stage: str,
        batch_index: int,
        step_ids: List[str],
        continue_stage: bool,
        remaining_work: Optional[List[str]] = None,
        response_id: Optional[str] = None,
    ) -> None:
        self._record_batch_in(
            self.completed_batches,
            stage=stage,
            batch_index=batch_index,
            step_ids=step_ids,
            continue_stage=continue_stage,
            remaining_work=remaining_work,
            response_id=response_id,
        )

    def record_batch(self, **kwargs: Any) -> None:
        """Backward-compatible alias for an executed/completed batch."""
        self.record_completed_batch(**kwargs)

    def advance_stage(self) -> None:
        self.current_stage_index += 1
        self.current_batch_index = 0
        self.pending_work = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ledger_version": "1.0",
            "saved_at": self.saved_at or time.time(),
            "task_id": self.task_id,
            "prompt": self.prompt,
            "stages": self.stages,
            "current_stage_index": self.current_stage_index,
            "current_stage": self.current_stage,
            "current_batch_index": self.current_batch_index,
            "planned_batches": self.planned_batches,
            "completed_batches": self.completed_batches,
            "pending_work": self.pending_work,
            "last_response_id": self.last_response_id,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskLedger":
        ledger = cls(
            task_id=str(data.get("task_id") or "task_unknown"),
            prompt=str(data.get("prompt") or ""),
            stages=list(data.get("stages") or ["geometry_modeling"]),
            current_stage_index=int(data.get("current_stage_index") or 0),
            current_batch_index=int(data.get("current_batch_index") or 0),
            planned_batches=list(data.get("planned_batches") or []),
            completed_batches=list(data.get("completed_batches") or []),
            pending_work=list(data.get("pending_work") or []),
            last_response_id=data.get("last_response_id"),
            last_error=data.get("last_error"),
        )
        ledger.saved_at = data.get("saved_at")
        return ledger

    def save(self, path: str) -> None:
        self.saved_at = time.time()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "TaskLedger":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def ledger_path_for_task(cache_dir: str, task_id: Optional[str]) -> str:
    safe_id = str(task_id or "task_unknown").replace("\\", "_").replace("/", "_")
    return os.path.join(cache_dir, f"task_ledger_{safe_id}.json")
