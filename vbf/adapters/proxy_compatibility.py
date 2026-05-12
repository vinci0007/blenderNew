from __future__ import annotations

from typing import Any, Dict, List


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


def _split_instruction_messages(messages: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
    instruction_parts: List[str] = []
    rest: List[Dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") in {"system", "developer"}:
            content = message.get("content")
            if content:
                instruction_parts.append(str(content))
        else:
            rest.append(message)
    return "\n\n".join(instruction_parts), rest


def fold_instructions_into_first_user(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fold system/developer instructions into user text for strict proxy relays."""
    instruction_text, rest = _split_instruction_messages(messages)
    if not instruction_text:
        return list(messages)

    prefix = f"System instructions:\n{instruction_text}\n\nUser request:\n"
    converted: List[Dict[str, Any]] = []
    inserted = False
    for message in rest:
        copied = dict(message)
        if not inserted and copied.get("role") == "user":
            content = copied.get("content")
            if isinstance(content, str):
                copied["content"] = f"{prefix}{content}"
            elif isinstance(content, list):
                copied["content"] = [{"type": "text", "text": prefix}] + content
            else:
                copied["content"] = f"{prefix}{_message_text_content(content)}"
            inserted = True
        converted.append(copied)

    if not inserted:
        converted.insert(0, {"role": "user", "content": prefix.rstrip()})
    return converted


def apply_proxy_compatibility_to_messages(
    protocol: str,
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Apply relay-gateway compatibility transforms without changing protocol shape."""
    if protocol == "openai_responses":
        return fold_instructions_into_first_user(messages)
    return list(messages)
