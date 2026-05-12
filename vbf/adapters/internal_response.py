from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VBFLLMToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VBFLLMResponse:
    content: str = ""
    tool_calls: List[VBFLLMToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    response_id: Optional[str] = None
    protocol: str = "chat"
    raw: Any = None

    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


def parse_tool_arguments(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def serialize_tool_arguments(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value or {}, ensure_ascii=False)


def get_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def chat_tool_call_to_internal(tool_call: Any) -> Optional[VBFLLMToolCall]:
    if isinstance(tool_call, dict):
        function = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
        name = function.get("name")
        arguments = function.get("arguments")
        call_id = tool_call.get("id")
    else:
        function = getattr(tool_call, "function", None)
        name = getattr(function, "name", "")
        arguments = getattr(function, "arguments", None)
        call_id = getattr(tool_call, "id", "")

    if not name:
        return None
    return VBFLLMToolCall(
        id=str(call_id or ""),
        name=str(name),
        arguments=parse_tool_arguments(arguments),
    )


def internal_tool_call_to_chat(tool_call: VBFLLMToolCall) -> Dict[str, Any]:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": serialize_tool_arguments(tool_call.arguments),
        },
    }


def content_to_internal(
    content: Any,
    *,
    protocol: str,
    raw: Any = None,
    finish_reason: Optional[str] = None,
    response_id: Optional[str] = None,
) -> VBFLLMResponse:
    return VBFLLMResponse(
        content="" if content is None else str(content),
        finish_reason=finish_reason,
        response_id=response_id,
        protocol=protocol,
        raw=raw if raw is not None else content,
    )


def chat_completion_to_internal(protocol: str, payload: Any) -> VBFLLMResponse:
    if isinstance(payload, VBFLLMResponse):
        return payload
    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except Exception:
                return content_to_internal(payload, protocol=protocol, raw=payload)
            if isinstance(parsed, dict) and "choices" in parsed:
                return chat_completion_to_internal(protocol, parsed)
        return content_to_internal(payload, protocol=protocol, raw=payload)

    choices = get_field(payload, "choices")
    if not isinstance(choices, list) or not choices:
        return VBFLLMResponse(protocol=protocol, raw=payload)

    choice = choices[0]
    if choice is None:
        return VBFLLMResponse(protocol=protocol, raw=payload)
    finish_reason = get_field(choice, "finish_reason")
    message = get_field(choice, "message")
    if message is None:
        return VBFLLMResponse(finish_reason=finish_reason, protocol=protocol, raw=payload)

    content = get_field(message, "content")
    raw_tool_calls = get_field(message, "tool_calls") or []
    tool_calls = [
        tc for tc in (chat_tool_call_to_internal(item) for item in raw_tool_calls)
        if tc is not None
    ]
    return VBFLLMResponse(
        content="" if content is None else str(content),
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        response_id=get_field(payload, "id") or get_field(payload, "response_id"),
        protocol=protocol,
        raw=payload,
    )


def responses_response_to_internal(response: Any) -> VBFLLMResponse:
    if not isinstance(response, dict):
        return content_to_internal(response, protocol="openai_responses", raw=response)

    output = response.get("output")
    tool_calls: List[VBFLLMToolCall] = []
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
                        VBFLLMToolCall(
                            id=call_id,
                            name=str(item.get("name")),
                            arguments=parse_tool_arguments(item.get("arguments")),
                        )
                    )
            content = item.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text")
                        if isinstance(text, str):
                            text_parts.append(text)

    return VBFLLMResponse(
        content="".join(text_parts),
        tool_calls=tool_calls,
        finish_reason="tool_calls" if tool_calls else response.get("status"),
        response_id=response.get("id"),
        protocol="openai_responses",
        raw=response,
    )


def anthropic_response_to_internal(response: Any) -> VBFLLMResponse:
    if not isinstance(response, dict):
        return content_to_internal(response, protocol="claude_responses", raw=response)

    content = response.get("content")
    text_parts: List[str] = []
    tool_calls: List[VBFLLMToolCall] = []

    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use" and block.get("name"):
                tool_calls.append(
                    VBFLLMToolCall(
                        id=str(block.get("id") or f"call_{len(tool_calls) + 1}"),
                        name=str(block.get("name")),
                        arguments=parse_tool_arguments(block.get("input")),
                    )
                )
    elif isinstance(content, str):
        text_parts.append(content)

    return VBFLLMResponse(
        content="".join(text_parts),
        tool_calls=tool_calls,
        finish_reason="tool_calls" if tool_calls else response.get("stop_reason"),
        response_id=response.get("id"),
        protocol="claude_responses",
        raw=response,
    )


def endpoint_response_to_internal(protocol: str, response: Any) -> VBFLLMResponse:
    if isinstance(response, VBFLLMResponse):
        return response
    if protocol == "openai_responses":
        return responses_response_to_internal(response)
    if protocol == "claude_responses":
        return anthropic_response_to_internal(response)
    return chat_completion_to_internal(protocol, response)


def internal_response_to_chat_completion(response: VBFLLMResponse) -> Dict[str, Any]:
    message: Dict[str, Any] = {"role": "assistant", "content": response.content}
    if response.tool_calls:
        message["tool_calls"] = [
            internal_tool_call_to_chat(tool_call) for tool_call in response.tool_calls
        ]
    result: Dict[str, Any] = {
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": (
                    "tool_calls" if response.tool_calls else response.finish_reason
                ),
                "message": message,
            }
        ],
    }
    if response.response_id:
        result["response_id"] = response.response_id
    return result
