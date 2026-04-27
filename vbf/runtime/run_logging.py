from __future__ import annotations

import contextlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, TextIO
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp_for_record() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _timestamp_for_filename() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%S%fZ")


def _format_task_id(created_at: datetime | None = None) -> tuple[str, str]:
    timestamp = created_at or _utc_now()
    task_stamp = timestamp.strftime("%m%d-%H%M%S")
    created_at_text = timestamp.strftime("%m/%d-%H:%M:%S")
    return f"task_{task_stamp}_{uuid4().hex[:8]}", created_at_text


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _safe_step_items(step_results: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(step_results, dict):
        return step_results.items()
    return []


def _format_log_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    return str(value)


def _format_event_line(event: str, payload: Dict[str, Any] | None = None) -> str:
    payload = dict(payload or {})
    task_id = payload.pop("task_id", None)
    parts = [str(task_id), event] if task_id else [event]
    for key in sorted(payload):
        value = payload[key]
        if value is None:
            continue
        parts.append(f"{key}={_format_log_value(value)}")
    return " ".join(parts)


@dataclass(frozen=True)
class TaskLogContext:
    task_id: str
    created_at: str
    logs_dir: Path
    transcript_path: Path


class TeeStream:
    """Write console output to both the original stream and a task log file."""

    def __init__(self, primary: TextIO, mirror: TextIO):
        self._primary = primary
        self._mirror = mirror

    def write(self, text: str) -> int:
        written = self._primary.write(text)
        self._mirror.write(text)
        if "\n" in text:
            self._mirror.flush()
        return written

    def flush(self) -> None:
        self._primary.flush()
        self._mirror.flush()

    def isatty(self) -> bool:
        return bool(getattr(self._primary, "isatty", lambda: False)())

    def __getattr__(self, name: str) -> Any:
        return getattr(self._primary, name)


def create_task_log_context(logs_dir: str | Path) -> TaskLogContext:
    directory = Path(logs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    task_id, created_at = _format_task_id()
    return TaskLogContext(
        task_id=task_id,
        created_at=created_at,
        logs_dir=directory,
        transcript_path=directory / f"{task_id}.log",
    )


def append_text_log_line(log_path: str | Path, line: str) -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")
    return path


def append_task_event(
    log_path: str | Path,
    event: str,
    payload: Dict[str, Any] | None = None,
) -> Path:
    return append_text_log_line(log_path, _format_event_line(event, payload))


@contextlib.contextmanager
def tee_console_to_task_log(context: TaskLogContext) -> Iterator[None]:
    context.transcript_path.parent.mkdir(parents=True, exist_ok=True)
    with context.transcript_path.open("a", encoding="utf-8", buffering=1) as log_file:
        log_file.write(
            _format_event_line(
                "task_log_opened",
                {
                    "task_id": context.task_id,
                    "created_at": context.created_at,
                    "log_file": str(context.transcript_path),
                },
            )
            + "\n"
        )
        log_file.flush()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = TeeStream(old_stdout, log_file)
        sys.stderr = TeeStream(old_stderr, log_file)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            log_file.write(
                _format_event_line(
                    "task_log_closed",
                    {
                        "task_id": context.task_id,
                        "log_file": str(context.transcript_path),
                    },
                )
                + "\n"
            )


def summarize_task_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a small, terminal-safe summary from the full task result."""
    step_results = result.get("step_results") if isinstance(result, dict) else {}
    step_items = list(_safe_step_items(step_results))
    plan = result.get("plan") if isinstance(result, dict) else {}
    plan_steps = plan.get("steps") if isinstance(plan, dict) else []

    ok_step_ids = [
        step_id
        for step_id, payload in step_items
        if isinstance(payload, dict) and payload.get("ok") is True
    ]
    failed_step_ids = [
        step_id
        for step_id, payload in step_items
        if isinstance(payload, dict) and payload.get("ok") is False
    ]

    prompt = result.get("prompt", "") if isinstance(result, dict) else ""
    return {
        "steps": len(step_items),
        "ok": len(ok_step_ids),
        "failed": len(failed_step_ids),
        "unknown": max(0, len(step_items) - len(ok_step_ids) - len(failed_step_ids)),
        "plan_steps": len(plan_steps) if isinstance(plan_steps, list) else 0,
        "failed_step_ids": failed_step_ids[:20],
        "prompt_chars": len(prompt) if isinstance(prompt, str) else 0,
        "plan_type": plan.get("plan_type") if isinstance(plan, dict) else None,
        "vbf_version": plan.get("vbf_version") if isinstance(plan, dict) else None,
    }


def write_task_result_log(
    result: Dict[str, Any],
    logs_dir: str | Path,
    *,
    prefix: str = "task_result",
    task_id: str | None = None,
) -> Path:
    """Persist the full task result to a timestamped JSON file."""
    directory = Path(logs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    result_id = task_id or f"{_timestamp_for_filename()}_{uuid4().hex[:8]}"
    path = directory / f"{prefix}_{result_id}.json"
    payload = {
        "ts": _timestamp_for_record(),
        "event": "task_result",
        "task_id": task_id,
        "summary": summarize_task_result(result),
        "result": result,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return path


def append_run_event(
    event: str,
    payload: Dict[str, Any] | None,
    logs_dir: str | Path,
) -> Path:
    """Append a monitoring-friendly runtime event to the daily text log."""
    directory = Path(logs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"run_events_{_utc_now().strftime('%Y%m%d')}.log"
    return append_text_log_line(path, _format_event_line(event, payload))
