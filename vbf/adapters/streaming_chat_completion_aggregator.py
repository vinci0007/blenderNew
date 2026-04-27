"""Aggregate OpenAI-compatible streaming chat completion chunks."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Iterator, List, Optional


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            dumped = obj.model_dump()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            dumped = obj.dict()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    return {}


def iter_sse_json_chunks(lines: Iterable[Any]) -> Iterator[Dict[str, Any]]:
    """Yield JSON payloads from OpenAI-style SSE `data:` lines."""
    for raw_line in lines:
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", errors="replace")
        else:
            line = str(raw_line)
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


class StreamingChatCompletionAggregator:
    """Build a ChatCompletion-like dict from streaming delta chunks."""

    def __init__(self) -> None:
        self.content_parts: List[str] = []
        self.tool_calls: Dict[int, Dict[str, Any]] = {}
        self.finish_reason: Optional[str] = None
        self.chunk_count = 0

    def add_chunk(self, chunk: Any) -> None:
        self.chunk_count += 1
        choices = _get(chunk, "choices")
        if not choices:
            return

        choice = choices[0]
        finish_reason = _get(choice, "finish_reason")
        if finish_reason:
            self.finish_reason = str(finish_reason)

        delta = _get(choice, "delta")
        if delta is None:
            message = _get(choice, "message")
            if message is not None:
                self._merge_message(message)
            return
        self._merge_message(delta)

    def _merge_message(self, message: Any) -> None:
        content = _get(message, "content")
        if isinstance(content, str):
            self.content_parts.append(content)

        tool_calls = _get(message, "tool_calls")
        if not tool_calls:
            return

        for fallback_index, tool_call in enumerate(tool_calls):
            index = _get(tool_call, "index", fallback_index)
            try:
                index = int(index)
            except Exception:
                index = fallback_index

            current = self.tool_calls.setdefault(
                index,
                {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                },
            )
            tool_call_id = _get(tool_call, "id")
            if tool_call_id:
                current["id"] = str(tool_call_id)
            tool_type = _get(tool_call, "type")
            if tool_type:
                current["type"] = str(tool_type)

            function = _get(tool_call, "function") or {}
            name = _get(function, "name")
            if name:
                current["function"]["name"] += str(name)
            arguments = _get(function, "arguments")
            if isinstance(arguments, str):
                current["function"]["arguments"] += arguments

    def stats(self) -> Dict[str, int]:
        return {
            "chunks": self.chunk_count,
            "content_chars": sum(len(part) for part in self.content_parts),
            "tool_arg_chars": sum(
                len(str(call.get("function", {}).get("arguments", "")))
                for call in self.tool_calls.values()
            ),
            "tool_calls": len(self.tool_calls),
        }

    def to_chat_completion(self) -> Dict[str, Any]:
        content = "".join(self.content_parts)
        tool_calls = [
            call for _, call in sorted(self.tool_calls.items(), key=lambda item: item[0])
        ]

        message: Dict[str, Any] = {"role": "assistant"}
        if content:
            message["content"] = content
        else:
            message["content"] = None
        if tool_calls:
            message["tool_calls"] = tool_calls

        return {
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": self.finish_reason,
                    "message": message,
                }
            ],
        }

