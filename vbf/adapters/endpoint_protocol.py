from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Iterator, List, Optional

from .proxy_compatibility import apply_proxy_compatibility_to_messages
from .streaming_chat_completion_aggregator import iter_sse_json_chunks
from .internal_response import (
    VBFLLMResponse,
    VBFLLMToolCall,
    endpoint_response_to_internal,
    internal_response_to_chat_completion,
    parse_tool_arguments,
)


def normalize_api_protocol(value: Any) -> str:
    protocol = str(value or "openai_responses").strip().lower().replace("-", "_")
    aliases = {
        "chat": "chat",
        "chat_completion": "chat",
        "chat_completions": "chat",
        "openai": "openai_responses",
        "openai_response": "openai_responses",
        "openai_responses": "openai_responses",
        "response": "openai_responses",
        "responses": "openai_responses",
        "claude": "claude_responses",
        "claude_response": "claude_responses",
        "claude_responses": "claude_responses",
        "anthropic": "claude_responses",
        "messages": "claude_responses",
        "anthropic_messages": "claude_responses",
    }
    return aliases.get(protocol, "openai_responses")


def chat_tools_to_responses_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not tools:
        return None
    converted: List[Dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = function.get("name")
        if not name:
            continue
        converted.append(
            {
                "type": "function",
                "name": name,
                "description": function.get("description", ""),
                "parameters": function.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return converted or None


def chat_tools_to_anthropic_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not tools:
        return None
    converted: List[Dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = function.get("name")
        if not name:
            continue
        converted.append(
            {
                "name": name,
                "description": function.get("description", ""),
                "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return converted or None


def split_system_messages(messages: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
    system_parts: List[str] = []
    rest: List[Dict[str, Any]] = []
    for message in messages:
        if message.get("role") in {"system", "developer"}:
            content = message.get("content")
            if content:
                system_parts.append(str(content))
        else:
            rest.append(message)
    return "\n\n".join(system_parts), rest


def _loads_json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _message_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return "" if content is None else str(content)


def _content_blocks(content: Any) -> List[Dict[str, Any]]:
    if isinstance(content, list):
        blocks: List[Dict[str, Any]] = []
        for block in content:
            if isinstance(block, dict):
                blocks.append(dict(block))
            elif isinstance(block, str):
                blocks.append({"type": "text", "text": block})
        return blocks
    if content is None:
        return []
    return [{"type": "text", "text": str(content)}]


def _image_url_from_block(block: Dict[str, Any]) -> Optional[str]:
    image_url = block.get("image_url")
    if isinstance(image_url, dict):
        url = image_url.get("url")
        if isinstance(url, str) and url:
            return url
    if isinstance(image_url, str) and image_url:
        return image_url
    url = block.get("url")
    if isinstance(url, str) and url:
        return url
    return None


def _data_url_parts(url: str) -> tuple[Optional[str], Optional[str]]:
    prefix = "data:"
    marker = ";base64,"
    if not url.startswith(prefix) or marker not in url:
        return None, None
    media_type, data = url[len(prefix) :].split(marker, 1)
    return media_type or None, data or None


def _to_openai_chat_content_blocks(content: Any) -> Any:
    blocks = _content_blocks(content)
    if not blocks:
        return "" if content is None else str(content)
    converted: List[Dict[str, Any]] = []
    has_image = False
    for block in blocks:
        block_type = block.get("type")
        if block_type in {"text", "input_text"}:
            text = block.get("text", "")
            if text:
                converted.append({"type": "text", "text": str(text)})
        elif block_type in {"image_url", "input_image"}:
            url = _image_url_from_block(block)
            if url:
                converted.append({"type": "image_url", "image_url": {"url": url}})
                has_image = True
    if has_image:
        return converted
    return _message_text_content(content)


def _to_responses_content_blocks(content: Any) -> Any:
    blocks = _content_blocks(content)
    if not blocks:
        return "" if content is None else str(content)
    converted: List[Dict[str, Any]] = []
    has_image = False
    for block in blocks:
        block_type = block.get("type")
        if block_type in {"text", "input_text"}:
            text = block.get("text", "")
            if text:
                converted.append({"type": "input_text", "text": str(text)})
        elif block_type in {"image_url", "input_image"}:
            url = _image_url_from_block(block)
            if url:
                converted.append({"type": "input_image", "image_url": url})
                has_image = True
    if has_image:
        return converted
    return _message_text_content(content)


def _to_anthropic_content_blocks(content: Any) -> Any:
    blocks = _content_blocks(content)
    if not blocks:
        return "" if content is None else str(content)
    converted: List[Dict[str, Any]] = []
    has_image = False
    for block in blocks:
        block_type = block.get("type")
        if block_type in {"text", "input_text"}:
            text = block.get("text", "")
            if text:
                converted.append({"type": "text", "text": str(text)})
        elif block_type in {"image_url", "input_image"}:
            url = _image_url_from_block(block)
            media_type, data = _data_url_parts(url or "")
            if media_type and data:
                converted.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    }
                )
                has_image = True
    if has_image:
        return converted
    return _message_text_content(content)


def messages_to_anthropic(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert internal OpenAI-chat messages to Anthropic Messages format."""
    converted: List[Dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role in {"system", "developer"}:
            continue
        if role == "tool":
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": str(message.get("tool_call_id") or ""),
                            "content": _message_text_content(message.get("content")),
                        }
                    ],
                }
            )
            continue

        converted_content = _to_anthropic_content_blocks(message.get("content"))
        content_blocks: List[Dict[str, Any]] = (
            list(converted_content) if isinstance(converted_content, list) else []
        )
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function") if isinstance(call.get("function"), dict) else {}
                name = function.get("name")
                if not name:
                    continue
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": str(call.get("id") or ""),
                        "name": str(name),
                        "input": _loads_json_object(function.get("arguments")),
                    }
                )

        has_tool_blocks = any(
            isinstance(block, dict) and block.get("type") == "tool_use"
            for block in content_blocks
        )
        converted.append(
            {
                "role": "assistant" if role == "assistant" else "user",
                "content": content_blocks if has_tool_blocks else converted_content,
            }
        )
    return converted


def messages_to_responses_input(
    messages: List[Dict[str, Any]],
    *,
    proxy_compatibility_mode: bool = False,
) -> List[Dict[str, Any]]:
    """Convert internal OpenAI-chat messages to Responses API input items."""
    converted: List[Dict[str, Any]] = []
    source_messages = (
        apply_proxy_compatibility_to_messages("openai_responses", messages)
        if proxy_compatibility_mode
        else messages
    )
    for message in source_messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role == "tool":
            converted.append(
                {
                    "type": "function_call_output",
                    "call_id": str(message.get("tool_call_id") or ""),
                    "output": _message_text_content(message.get("content")),
                }
            )
            continue
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function") if isinstance(call.get("function"), dict) else {}
                name = function.get("name")
                if not name:
                    continue
                converted.append(
                    {
                        "type": "function_call",
                        "call_id": str(call.get("id") or ""),
                        "name": str(name),
                        "arguments": function.get("arguments") or "{}",
                    }
                )
        content = _to_responses_content_blocks(message.get("content"))
        if content or role in {"system", "developer", "user", "assistant"}:
            converted.append(
                {
                    "role": role if role in {"system", "developer", "assistant"} else "user",
                    "content": content,
                }
            )
    return converted


def build_protocol_request(
    *,
    protocol: str,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    tools: Optional[List[Dict[str, Any]]],
    json_object: bool,
    stream: bool,
    proxy_compatibility_mode: bool = False,
) -> Dict[str, Any]:
    if protocol == "openai_responses":
        request: Dict[str, Any] = {
            "model": model,
            "input": messages_to_responses_input(
                messages,
                proxy_compatibility_mode=proxy_compatibility_mode,
            ),
            "temperature": temperature,
        }
        response_tools = chat_tools_to_responses_tools(tools)
        if response_tools:
            request["tools"] = response_tools
            request["tool_choice"] = "auto"
        if json_object:
            request["text"] = {"format": {"type": "json_object"}}
        if stream:
            request["stream"] = True
        return request

    if protocol == "claude_responses":
        system, _ = split_system_messages(messages)
        anthropic_messages = messages_to_anthropic(messages)
        request = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": 8192,
        }
        if system:
            request["system"] = system
        anthropic_tools = chat_tools_to_anthropic_tools(tools)
        if anthropic_tools:
            request["tools"] = anthropic_tools
        if stream:
            request["stream"] = True
        return request

    request = {
        "model": model,
        "messages": [
            {
                **message,
                "content": _to_openai_chat_content_blocks(message.get("content")),
            }
            if isinstance(message, dict)
            else message
            for message in messages
        ],
        "temperature": temperature,
    }
    if tools:
        request["tools"] = tools
        request["tool_choice"] = "auto"
    if json_object:
        request["response_format"] = {"type": "json_object"}
    if stream:
        request["stream"] = True
    return request


class EndpointStreamingAggregator:
    """Aggregate chat, OpenAI Responses, or Anthropic Messages SSE chunks."""

    def __init__(self, protocol: str) -> None:
        self.protocol = protocol
        self.content_parts: List[str] = []
        self.chunk_count = 0
        self.response_id: Optional[str] = None
        self.finish_reason: Optional[str] = None
        self.tool_calls: List[Dict[str, Any]] = []
        self._seen_tool_ids: set[str] = set()
        self._anthropic_blocks: Dict[int, Dict[str, Any]] = {}

    def add_chunk(self, chunk: Dict[str, Any]) -> None:
        self.chunk_count += 1
        if not isinstance(chunk, dict):
            return
        if self.protocol == "openai_responses":
            self._add_responses_chunk(chunk)
        elif self.protocol == "claude_responses":
            self._add_anthropic_chunk(chunk)

    def _add_responses_chunk(self, chunk: Dict[str, Any]) -> None:
        event_type = str(chunk.get("type") or "")
        response = chunk.get("response") if isinstance(chunk.get("response"), dict) else {}
        if response.get("id"):
            self.response_id = str(response.get("id"))
        if chunk.get("response_id"):
            self.response_id = str(chunk.get("response_id"))
        if event_type.endswith("output_text.delta") and isinstance(chunk.get("delta"), str):
            self.content_parts.append(chunk["delta"])
        elif event_type.endswith("output_text.done") and isinstance(chunk.get("text"), str):
            if not self.content_parts:
                self.content_parts.append(chunk["text"])
        elif event_type == "response.completed":
            output_text = response.get("output_text")
            if isinstance(output_text, str) and not self.content_parts:
                self.content_parts.append(output_text)
            self._add_responses_output_items(response.get("output"))
            self.finish_reason = "stop"
        elif event_type == "response.incomplete":
            self.finish_reason = "incomplete"
        elif event_type in {"response.output_item.done", "response.output_item.added"}:
            self._add_responses_tool_call(chunk.get("item"))

    def _add_responses_output_items(self, output: Any) -> None:
        if isinstance(output, list):
            for item in output:
                self._add_responses_tool_call(item)

    def _add_responses_tool_call(self, item: Any) -> None:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            return
        name = item.get("name")
        if not name:
            return
        call_id = str(item.get("call_id") or item.get("id") or f"call_{len(self.tool_calls) + 1}")
        if call_id in self._seen_tool_ids:
            return
        self._seen_tool_ids.add(call_id)
        self.tool_calls.append(
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": str(name),
                    "arguments": item.get("arguments") or "{}",
                },
            }
        )

    def _add_anthropic_chunk(self, chunk: Dict[str, Any]) -> None:
        event_type = str(chunk.get("type") or "")
        if event_type == "content_block_start":
            index = int(chunk.get("index") or 0)
            block = chunk.get("content_block") if isinstance(chunk.get("content_block"), dict) else {}
            if block.get("type") == "tool_use":
                self._anthropic_blocks[index] = {
                    "id": str(block.get("id") or f"call_{index}"),
                    "name": str(block.get("name") or ""),
                    "args": [],
                }
        elif event_type == "content_block_delta":
            delta = chunk.get("delta") if isinstance(chunk.get("delta"), dict) else {}
            text = delta.get("text")
            if isinstance(text, str):
                self.content_parts.append(text)
            partial_json = delta.get("partial_json")
            index = int(chunk.get("index") or 0)
            if isinstance(partial_json, str) and index in self._anthropic_blocks:
                self._anthropic_blocks[index]["args"].append(partial_json)
        elif event_type == "content_block_stop":
            index = int(chunk.get("index") or 0)
            block = self._anthropic_blocks.pop(index, None)
            if block and block.get("name"):
                call_id = str(block.get("id") or f"call_{index}")
                if call_id not in self._seen_tool_ids:
                    self._seen_tool_ids.add(call_id)
                    self.tool_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": str(block.get("name")),
                                "arguments": "".join(block.get("args") or []) or "{}",
                            },
                        }
                    )
        elif event_type == "message_delta":
            delta = chunk.get("delta") if isinstance(chunk.get("delta"), dict) else {}
            stop_reason = delta.get("stop_reason")
            if stop_reason:
                self.finish_reason = str(stop_reason)

    def stats(self) -> Dict[str, int]:
        return {
            "chunks": self.chunk_count,
            "content_chars": sum(len(part) for part in self.content_parts),
            "tool_arg_chars": 0,
            "tool_calls": len(self.tool_calls),
        }

    def to_chat_completion(self) -> Dict[str, Any]:
        return internal_response_to_chat_completion(self.to_internal_response())

    def to_internal_response(self) -> VBFLLMResponse:
        tool_calls: List[VBFLLMToolCall] = []
        for call in self.tool_calls:
            function = call.get("function") if isinstance(call.get("function"), dict) else {}
            name = function.get("name")
            if not name:
                continue
            tool_calls.append(
                VBFLLMToolCall(
                    id=str(call.get("id") or ""),
                    name=str(name),
                    arguments=parse_tool_arguments(function.get("arguments")),
                )
            )
        return VBFLLMResponse(
            content="".join(self.content_parts),
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else self.finish_reason,
            response_id=self.response_id,
            protocol=self.protocol,
        )


def iter_endpoint_sse_json_chunks(lines: Iterable[Any]) -> Iterator[Dict[str, Any]]:
    yield from iter_sse_json_chunks(lines)


def endpoint_response_to_chat_completion(protocol: str, response: Any) -> Any:
    """Normalize non-stream endpoint responses into the internal chat shape."""
    return internal_response_to_chat_completion(
        endpoint_response_to_internal(protocol, response)
    )


def _responses_response_to_chat_completion(response: Dict[str, Any]) -> Dict[str, Any]:
    output = response.get("output")
    tool_calls: List[Dict[str, Any]] = []
    text_parts: List[str] = []
    seen_tool_ids: set[str] = set()

    if isinstance(response.get("output_text"), str):
        text_parts.append(response["output_text"])

    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "function_call" and item.get("name"):
                call_id = str(item.get("call_id") or item.get("id") or f"call_{len(tool_calls) + 1}")
                if call_id not in seen_tool_ids:
                    seen_tool_ids.add(call_id)
                    tool_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": str(item.get("name")),
                                "arguments": item.get("arguments") or "{}",
                            },
                        }
                    )
            content = item.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text")
                        if isinstance(text, str):
                            text_parts.append(text)

    message: Dict[str, Any] = {"role": "assistant", "content": "".join(text_parts)}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "object": "chat.completion",
        "response_id": response.get("id"),
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls" if tool_calls else response.get("status"),
                "message": message,
            }
        ],
    }


def _anthropic_response_to_chat_completion(response: Dict[str, Any]) -> Dict[str, Any]:
    content = response.get("content")
    text_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []

    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use" and block.get("name"):
                tool_calls.append(
                    {
                        "id": str(block.get("id") or f"call_{len(tool_calls) + 1}"),
                        "type": "function",
                        "function": {
                            "name": str(block.get("name")),
                            "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                        },
                    }
                )
    elif isinstance(content, str):
        text_parts.append(content)

    message: Dict[str, Any] = {"role": "assistant", "content": "".join(text_parts)}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "object": "chat.completion",
        "id": response.get("id"),
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls" if tool_calls else response.get("stop_reason"),
                "message": message,
            }
        ],
    }
