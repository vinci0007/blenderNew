from vbf.adapters.openai_compat_adapter import OpenAICompatAdapter
from vbf.adapters.endpoint_protocol import (
    endpoint_response_to_chat_completion,
    messages_to_anthropic,
    messages_to_responses_input,
)
from vbf.adapters.internal_response import VBFLLMResponse, VBFLLMToolCall, endpoint_response_to_internal
from vbf.adapters.skill_registry import SkillRegistry
import sys
import types
import pytest
import json
from unittest.mock import Mock


class _Err(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


def test_should_retry_without_response_format_true_on_json_object_rejection():
    err = _Err("'response_format.type' must be 'json_schema' or 'text'")
    body = {"model": "x", "messages": [], "response_format": {"type": "json_object"}}
    assert OpenAICompatAdapter._should_retry_without_response_format(err, body) is True


def test_should_retry_without_response_format_false_without_response_format_field():
    err = _Err("'response_format.type' must be 'json_schema' or 'text'")
    body = {"model": "x", "messages": []}
    assert OpenAICompatAdapter._should_retry_without_response_format(err, body) is False


def test_should_retry_without_response_format_true_on_responses_text_format_rejection():
    err = _Err("'text.format.type' must be 'json_schema' or 'text'")
    body = {"model": "x", "input": [], "text": {"format": {"type": "json_object"}}}
    assert OpenAICompatAdapter._should_retry_without_response_format(err, body) is True


def test_should_retry_without_tools_true_on_tool_payload_rejection():
    err = _Err("Unsupported parameter: tools")
    body = {"model": "x", "messages": [], "tools": [], "tool_choice": "auto"}
    assert OpenAICompatAdapter._should_retry_without_tools(err, body) is True


def test_should_retry_without_tools_false_without_tool_fields():
    err = _Err("Unsupported parameter: tools")
    body = {"model": "x", "messages": []}
    assert OpenAICompatAdapter._should_retry_without_tools(err, body) is False


def test_build_api_request_with_mode_disables_tools_and_json_object():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )
    request = adapter._build_api_request_with_mode(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "x", "parameters": {"type": "object"}}}],
        allow_tools=False,
        allow_json_object=False,
    )
    assert "tools" not in request
    assert "tool_choice" not in request
    assert "response_format" not in request


def test_build_tools_includes_planning_skill_schemas_for_active_subset():
    SkillRegistry.reset()
    registry = SkillRegistry.get_instance()
    registry._skills = {
        "create_primitive": {
            "description": "Create a primitive object",
            "args": {
                "primitive_type": {"type": "str", "required": True},
                "name": {"type": "str", "required": False},
                "size": {"type": "list", "required": False},
            },
        },
        "set_parent": {
            "description": "Parent one object to another",
            "args": {
                "child_name": {"type": "str", "required": True},
                "parent_name": {"type": "str", "required": True},
            },
        },
    }
    registry._initialized = True
    try:
        adapter = OpenAICompatAdapter(
            model_name="default",
            model_config={
                "base_url": "http://127.0.0.1:12347/v1",
                "default_model": "dummy-model",
                "api_protocol": "openai_responses",
                "response_format": {"type": "json_object"},
                "use_function_calling": True,
                "planning_tool_mode": "schema",
                "planning_skill_tool_limit": 1,
            },
            client=None,
        )
        adapter.format_messages(
            "create model",
            skills_subset=["create_primitive", "set_parent"],
        )

        tools = adapter.build_tools_for_llm()

        names = [tool["function"]["name"] for tool in tools]
        assert names == ["load_skill", "create_primitive"]
        primitive_schema = tools[1]["function"]["parameters"]
        assert primitive_schema["required"] == ["primitive_type"]
        assert primitive_schema["properties"]["size"]["type"] == "array"
    finally:
        SkillRegistry.reset()


def test_planning_skill_tool_calls_convert_to_plan_steps():
    SkillRegistry.reset()
    registry = SkillRegistry.get_instance()
    registry._skills = {
        "create_primitive": {"description": "Create primitive", "args": {}},
    }
    registry._initialized = True
    try:
        adapter = OpenAICompatAdapter(
            model_name="default",
            model_config={
                "base_url": "http://127.0.0.1:12347/v1",
                "default_model": "dummy-model",
                "planning_tool_mode": "schema",
            },
            client=None,
        )
        tool_call = VBFLLMToolCall(
            id="call_1",
            name="create_primitive",
            arguments={"primitive_type": "cube", "name": "Root"},
        )

        assert adapter._is_planning_skill_tool_call("create_primitive") is True
        plan = adapter._planning_tool_calls_to_plan([tool_call])

        assert plan["plan_type"] == "skills_plan"
        assert plan["metadata"]["planning_tool_calls"] is True
        assert plan["steps"] == [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"primitive_type": "cube", "name": "Root"},
            }
        ]
    finally:
        SkillRegistry.reset()


def test_build_responses_api_request_with_protocol_config():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "openai_responses",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "supports_streaming": True,
        },
        client=None,
    )
    request = adapter._build_api_request_with_mode(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "load_skill", "parameters": {"type": "object"}}}],
        allow_tools=True,
        allow_json_object=True,
        stream=True,
    )
    assert "input" in request
    assert "messages" not in request
    assert request["tools"][0]["name"] == "load_skill"
    assert request["text"]["format"]["type"] == "json_object"
    assert request["stream"] is True


def test_build_responses_request_keeps_native_system_role_by_default():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "openai_responses",
        },
        client=None,
    )
    request = adapter._build_api_request_with_mode(
        messages=[
            {"role": "system", "content": "return json"},
            {"role": "user", "content": "hi"},
        ],
        tools=None,
        allow_tools=False,
        allow_json_object=False,
    )
    assert request["input"][0] == {"role": "system", "content": "return json"}
    assert request["input"][1] == {"role": "user", "content": "hi"}


def test_build_responses_request_folds_system_when_proxy_compatibility_enabled():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "openai_responses",
            "enable_proxy_compatibility_mode": True,
        },
        client=None,
    )
    request = adapter._build_api_request_with_mode(
        messages=[
            {"role": "system", "content": "return json"},
            {"role": "developer", "content": "use compact output"},
            {"role": "user", "content": "hi"},
        ],
        tools=None,
        allow_tools=False,
        allow_json_object=False,
    )

    roles = [item.get("role") for item in request["input"]]
    assert "system" not in roles
    assert "developer" not in roles
    assert request["input"][0]["role"] == "user"
    assert "System instructions:" in request["input"][0]["content"]
    assert "return json" in request["input"][0]["content"]
    assert "use compact output" in request["input"][0]["content"]
    assert request["input"][0]["content"].endswith("hi")


def test_responses_request_preserves_image_content_blocks():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "model this reference"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,AAAA"},
                    "source_path": "local-only.png",
                },
            ],
        }
    ]

    converted = messages_to_responses_input(messages)

    assert converted[0]["role"] == "user"
    assert converted[0]["content"] == [
        {"type": "input_text", "text": "model this reference"},
        {"type": "input_image", "image_url": "data:image/png;base64,AAAA"},
    ]


def test_anthropic_request_converts_image_content_blocks_to_base64_source():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "model this reference"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,BBBB"}},
            ],
        }
    ]

    converted = messages_to_anthropic(messages)

    assert converted[0]["role"] == "user"
    assert converted[0]["content"][0] == {"type": "text", "text": "model this reference"}
    assert converted[0]["content"][1] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": "BBBB"},
    }


def test_default_api_protocol_is_openai_responses():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
        },
        client=None,
    )
    request = adapter._build_api_request_with_mode(
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        allow_tools=False,
        allow_json_object=False,
    )
    assert adapter.api_protocol == "openai_responses"
    assert "input" in request
    assert "messages" not in request


def test_compat_mode_cache_key_is_protocol_and_endpoint_specific():
    OpenAICompatAdapter._COMPAT_MODE_CACHE.clear()
    base = {
        "base_url": "http://127.0.0.1:12347/v1",
        "default_model": "dummy-model",
        "response_format": {"type": "json_object"},
        "use_function_calling": True,
    }

    chat = OpenAICompatAdapter(
        model_name="default",
        model_config={**base, "api_protocol": "chat"},
        client=None,
    )
    OpenAICompatAdapter._COMPAT_MODE_CACHE[chat._compat_mode_key] = {
        "allow_tools": False,
        "allow_json_object": False,
        "allow_streaming": False,
    }
    chat_cached = OpenAICompatAdapter(
        model_name="default",
        model_config={**base, "api_protocol": "chat"},
        client=None,
    )

    responses = OpenAICompatAdapter(
        model_name="default",
        model_config={**base, "api_protocol": "openai_responses", "responses_path": "/responses"},
        client=None,
    )
    responses_proxy = OpenAICompatAdapter(
        model_name="default",
        model_config={
            **base,
            "api_protocol": "openai_responses",
            "responses_path": "/responses",
            "enable_proxy_compatibility_mode": True,
        },
        client=None,
    )
    messages = OpenAICompatAdapter(
        model_name="default",
        model_config={**base, "api_protocol": "claude_responses", "responses_path": "/messages"},
        client=None,
    )

    assert chat._compat_mode_key != responses._compat_mode_key
    assert responses._compat_mode_key != responses_proxy._compat_mode_key
    assert responses._compat_mode_key != messages._compat_mode_key
    assert chat_cached._allow_tools is False
    assert responses._allow_tools is True
    assert messages._allow_tools is True
    assert "|chat|" in chat._compat_mode_key
    assert "|openai_responses|/responses" in responses._compat_mode_key
    assert "|openai_responses|/responses|proxy=1" in responses_proxy._compat_mode_key
    assert "|claude_responses|/messages" in messages._compat_mode_key


def test_build_responses_api_request_can_disable_json_object_format():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "openai_responses",
            "response_format": {"type": "json_object"},
        },
        client=None,
    )
    request = adapter._build_api_request_with_mode(
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        allow_tools=False,
        allow_json_object=False,
    )
    assert "text" not in request
    assert "response_format" not in request


@pytest.mark.asyncio
async def test_stream_transport_errors_retry_same_mode_before_nonstream(monkeypatch):
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "openai_responses",
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
            "use_streaming": True,
            "supports_streaming": True,
        },
        client=None,
    )
    monkeypatch.setattr(adapter, "_maybe_probe_compatibility_sync", lambda _openai_cls: None)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    stream_call = Mock(
        side_effect=[
            ConnectionError("drop 1"),
            ConnectionError("drop 2"),
            {
                "id": "resp_ok",
                "status": "completed",
                "output_text": json.dumps(
                    {
                        "steps": [
                            {
                                "step_id": "001",
                                "stage": "primitive_blocking",
                                "skill": "create_primitive",
                                "args": {"primitive_type": "cube"},
                            }
                        ]
                    }
                ),
            },
        ]
    )
    nonstream_call = Mock(side_effect=AssertionError("non-stream fallback should not run"))
    monkeypatch.setattr(adapter, "_post_chat_completions_http_stream", stream_call)
    monkeypatch.setattr(adapter, "_post_chat_completions_http", nonstream_call)

    plan = await adapter.call_llm([{"role": "user", "content": "return a plan"}])

    assert stream_call.call_count == 3
    assert nonstream_call.call_count == 0
    assert plan["steps"][0]["skill"] == "create_primitive"


def test_parse_response_reads_responses_output_text():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "openai_responses",
        },
        client=None,
    )
    parsed = adapter.parse_response({"output_text": "{\"steps\": []}"})
    assert parsed["steps"] == []


def test_build_claude_responses_request_with_protocol_config():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "claude_responses",
            "responses_path": "/v1/messages",
            "use_function_calling": True,
            "supports_streaming": True,
        },
        client=None,
    )
    request = adapter._build_api_request_with_mode(
        messages=[
            {"role": "system", "content": "system"},
            {"role": "developer", "content": "developer"},
            {"role": "user", "content": "hi"},
        ],
        tools=[{"type": "function", "function": {"name": "load_skill", "parameters": {"type": "object"}}}],
        allow_tools=True,
        allow_json_object=True,
        stream=True,
    )
    assert request["system"] == "system\n\ndeveloper"
    assert request["messages"] == [{"role": "user", "content": "hi"}]
    assert request["tools"][0]["name"] == "load_skill"
    assert request["stream"] is True
    assert adapter.api_protocol == "claude_responses"
    assert adapter._endpoint_path() == "/v1/messages"


def test_claude_responses_request_converts_tool_loop_messages():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "claude_responses",
            "responses_path": "/messages",
        },
        client=None,
    )
    request = adapter._build_api_request_with_mode(
        messages=[
            {"role": "user", "content": "make cube"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "load_skill",
                            "arguments": '{"skill_name": "create_primitive"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": '{"ok": true}'},
        ],
        tools=None,
        allow_tools=False,
        allow_json_object=False,
    )
    assert request["messages"][1]["content"][0]["type"] == "tool_use"
    assert request["messages"][2]["role"] == "user"
    assert request["messages"][2]["content"][0]["type"] == "tool_result"


def test_endpoint_response_normalizes_responses_function_call():
    response = {
        "id": "resp_1",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "load_skill",
                "arguments": '{"skill_name": "create_primitive"}',
            }
        ],
    }
    normalized = endpoint_response_to_chat_completion("openai_responses", response)
    message = normalized["choices"][0]["message"]
    assert message["tool_calls"][0]["function"]["name"] == "load_skill"
    assert normalized["choices"][0]["finish_reason"] == "tool_calls"


def test_endpoint_response_normalizes_responses_to_vbf_internal_shape():
    response = {
        "id": "resp_1",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "load_skill",
                "arguments": '{"skill_name": "create_primitive"}',
            }
        ],
    }

    normalized = endpoint_response_to_internal("openai_responses", response)

    assert isinstance(normalized, VBFLLMResponse)
    assert normalized.protocol == "openai_responses"
    assert normalized.response_id == "resp_1"
    assert normalized.finish_reason == "tool_calls"
    assert normalized.tool_calls[0].name == "load_skill"
    assert normalized.tool_calls[0].arguments == {"skill_name": "create_primitive"}


def test_endpoint_response_normalizes_anthropic_tool_use():
    response = {
        "id": "msg_1",
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "load_skill",
                "input": {"skill_name": "create_primitive"},
            }
        ],
    }
    normalized = endpoint_response_to_chat_completion("claude_responses", response)
    message = normalized["choices"][0]["message"]
    assert message["tool_calls"][0]["id"] == "toolu_1"
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {
        "skill_name": "create_primitive"
    }


def test_endpoint_response_normalizes_anthropic_to_vbf_internal_shape():
    response = {
        "id": "msg_1",
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "load_skill",
                "input": {"skill_name": "create_primitive"},
            }
        ],
    }

    normalized = endpoint_response_to_internal("claude_responses", response)

    assert isinstance(normalized, VBFLLMResponse)
    assert normalized.protocol == "claude_responses"
    assert normalized.response_id == "msg_1"
    assert normalized.finish_reason == "tool_calls"
    assert normalized.tool_calls[0].id == "toolu_1"
    assert normalized.tool_calls[0].arguments == {"skill_name": "create_primitive"}


def test_parse_response_repairs_missing_array_closer():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
        },
        client=None,
    )
    response = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{\n'
                        '  "quality": "good",\n'
                        '  "suggestions": ["check materials"],\n'
                        '  "recommendations": {\n'
                        '    "overall": ["keep names clear"\n'
                        "  }\n"
                        "}"
                    )
                }
            }
        ]
    }

    parsed = adapter.parse_response(response)

    assert parsed["quality"] == "good"
    assert parsed["recommendations"]["overall"] == ["keep names clear"]


def test_auto_probe_downgrades_tools_when_gateway_rejects_tool_payload():
    calls = []

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            class _Completions:
                @staticmethod
                def create(**request):
                    calls.append(request)
                    if "tools" in request:
                        raise _Err("Unsupported parameter: tools")
                    return {"choices": [{"message": {"content": '{"ok": true}'}}]}

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/probe-tools",
            "default_model": "dummy-model-probe-tools",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": "auto",
            "planning_capability_probe": {
                "enabled": True,
                "timeout_seconds": 3,
                "cache_ttl_seconds": 3600,
            },
        },
        client=None,
    )

    adapter._maybe_probe_compatibility_sync(_FakeOpenAI)

    assert adapter._allow_tools is False
    assert any("tools" in request for request in calls)
    assert any("tools" not in request for request in calls)


def test_adapter_sanitizes_request_headers_in_proxy_compatibility_mode():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "enable_proxy_compatibility_mode": True,
            "enable_extra_request_headers": True,
            "request_headers": {
                "User-Agent": "curl/8.8.0",
                "Authorization": "blocked",
                "HOST": "blocked",
                "X-Test": 42,
            },
        },
        client=None,
    )

    assert adapter.request_headers == {
        "User-Agent": "curl/8.8.0",
        "X-Test": "42",
    }


def test_adapter_ignores_request_headers_when_extra_headers_disabled():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "enable_proxy_compatibility_mode": True,
            "enable_extra_request_headers": False,
            "request_headers": {
                "User-Agent": "curl/8.8.0",
            },
        },
        client=None,
    )

    assert adapter.request_headers == {}


def test_extra_request_headers_apply_to_all_protocols():
    for api_protocol, auth_header in [
        ("chat", "Authorization"),
        ("openai_responses", "Authorization"),
        ("claude_responses", "x-api-key"),
    ]:
        adapter = OpenAICompatAdapter(
            model_name="default",
            model_config={
                "base_url": "http://127.0.0.1:12347/v1",
                "default_model": "dummy-model",
                "api_protocol": api_protocol,
                "api_key": "key",
                "enable_proxy_compatibility_mode": True,
                "enable_extra_request_headers": True,
                "request_headers": {
                    "User-Agent": "curl/8.8.0",
                    "X-Test": api_protocol,
                },
            },
            client=None,
        )

        headers = adapter._build_standard_http_headers()
        assert headers[auth_header]
        assert headers["User-Agent"] == "curl/8.8.0"
        assert headers["X-Test"] == api_protocol


def test_claude_responses_can_use_bearer_auth_scheme():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "https://api.longcat.chat/anthropic/v1",
            "default_model": "LongCat-2.0-Preview",
            "api_protocol": "claude_responses",
            "auth_scheme": "bearer",
            "api_key": "key",
        },
        client=None,
    )

    headers = adapter._build_standard_http_headers()

    assert headers["Authorization"] == "Bearer key"
    assert "x-api-key" not in headers
    assert headers["anthropic-version"] == "2023-06-01"


def test_parse_response_unwraps_markdown_then_extracts_outermost_json():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )
    payload = {
        "choices": [
            {
                "message": {
                    "content": "Here is plan:\n```json\n{\"steps\": [{\"step_id\": \"001\", \"skill\": \"create_primitive\", \"args\": {\"primitive_type\": \"cube\"}}]}\n```\nthanks"
                }
            }
        ]
    }
    parsed = adapter.parse_response(payload)
    assert "error" not in parsed
    assert parsed["steps"][0]["skill"] == "create_primitive"


def test_parse_response_extracts_outermost_json_from_plain_text():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )
    payload = {"choices[0].message.content": "prefix {\"steps\": []} suffix"}
    parsed = adapter.parse_response(payload)
    assert parsed["steps"] == []


def test_parse_response_returns_parse_stage_when_json_is_malformed():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )
    payload = {"choices[0].message.content": "```json\n{\"steps\": [}\n```"}
    parsed = adapter.parse_response(payload)
    assert parsed["error"] == "Failed to parse JSON from response"
    assert parsed["parse_stage"] == "strict_json_loads"
    assert "fallback_mode" in parsed


def test_build_system_prompt_includes_schema_cards_when_tools_off():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "schema_cards_limit": 2,
        },
        client=None,
    )

    adapter._allow_tools = False
    adapter.list_skill_summaries = lambda: {
        "create_primitive": "create mesh primitive",
        "set_parent": "set parent relation",
    }
    adapter.get_skill_full = lambda skill_name: {
        "args": {
            "name": {"required": True, "type": "str"},
            "location": {"required": False, "type": "list"},
        }
    }

    prompt = adapter.build_system_prompt(skills_subset=["create_primitive", "set_parent"])
    assert "Compact Skill Signatures" in prompt
    assert "create_primitive | required:" in prompt


def test_build_system_prompt_can_include_all_retained_compact_schemas():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
            "schema_cards_limit": 1,
            "planning_context": {
                "include_compact_schema_for_required": True,
            },
        },
        client=None,
    )

    adapter.list_skill_summaries = lambda: {
        "create_primitive": "create mesh primitive",
        "set_parent": "set parent relation",
    }
    adapter.get_skill_full = lambda skill_name: {
        "args": {
            "name": {"required": True, "type": "str"},
        }
    }

    prompt = adapter.build_system_prompt(skills_subset=["create_primitive", "set_parent"])
    assert "create_primitive | required:" in prompt
    assert "set_parent | required:" in prompt


def test_build_system_prompt_includes_priority_schema_cards_when_tools_on():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "schema_cards_limit": 2,
            "planning_context": {
                "include_compact_schema_for_high_risk": True,
            },
        },
        client=None,
    )

    adapter._allow_tools = True
    adapter.list_skill_summaries = lambda: {
        "z_misc_skill": "misc",
        "create_beveled_box": "create box with bevel",
        "apply_transform": "apply object transform",
    }
    adapter.get_skill_full = lambda skill_name: {
        "args": {
            "name": {"required": True, "type": "str"},
            "size": {"required": False, "type": "list"},
            "rotation_euler": {"required": False, "type": "list"},
        }
    }

    prompt = adapter.build_system_prompt(
        skills_subset=["z_misc_skill", "create_beveled_box", "apply_transform"]
    )

    assert "Progressive Disclosure" in prompt
    assert "Compact Skill Signatures" in prompt
    assert "create_beveled_box | required:" in prompt
    assert "apply_transform | required:" in prompt
    assert "z_misc_skill | required:" not in prompt


@pytest.mark.asyncio
async def test_call_llm_accepts_plain_string_gateway_response(monkeypatch):
    observed = {}

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            observed["default_headers"] = default_headers
            observed["timeout"] = timeout

            class _Completions:
                @staticmethod
                def create(**kwargs):
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
            "enable_proxy_compatibility_mode": True,
            "enable_extra_request_headers": True,
            "request_headers": {"User-Agent": "curl/8.8.0", "Authorization": "blocked"},
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert observed["default_headers"] == {"User-Agent": "curl/8.8.0"}
    assert observed["timeout"] == adapter._request_timeout_seconds()


@pytest.mark.asyncio
async def test_call_llm_records_empty_provider_response(monkeypatch):
    OpenAICompatAdapter._COMPAT_MODE_CACHE.clear()
    recorded = {}

    class _FakeClient:
        def _record_plan_shape_failure(self, error_message, raw_plan, stage="normalize_plan"):
            recorded["error_message"] = error_message
            recorded["raw_plan"] = raw_plan
            recorded["stage"] = stage

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    if "tools" in kwargs:
                        return {"object": "chat.completion", "choices": []}
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=_FakeClient(),
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert recorded["stage"] == "llm_empty_response"
    assert recorded["raw_plan"]["reason"] == "empty_chunk_payload"
    assert recorded["raw_plan"]["response"] == {"object": "chat.completion", "choices": []}


@pytest.mark.asyncio
async def test_call_llm_empty_responses_after_tool_call_uses_compact_json_off_retry(monkeypatch):
    OpenAICompatAdapter._COMPAT_MODE_CACHE.clear()
    calls = []
    recorded = {}

    class _FakeClient:
        def _record_plan_shape_failure(self, error_message, raw_plan, stage="normalize_plan"):
            recorded["error_message"] = error_message
            recorded["raw_plan"] = raw_plan
            recorded["stage"] = stage

    fake_openai = types.SimpleNamespace(
        OpenAI=object,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/empty-responses-after-tool",
            "default_model": "dummy-model-empty-responses-after-tool",
            "api_protocol": "openai_responses",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "use_streaming": False,
            "planning_capability_probe": {"enabled": False},
        },
        client=_FakeClient(),
    )
    adapter.get_skill_full = lambda skill_name: {
        "description": "create primitive",
        "args": {"primitive_type": {"required": True, "type": "str"}},
    }

    def _fake_http(request_body, timeout_seconds, protocol=None):
        calls.append(request_body)
        if len(calls) == 1:
            return {
                "id": "resp_tool",
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "load_skill",
                        "arguments": '{"skill_name":"create_primitive"}',
                    }
                ],
            }
        if len(calls) == 2:
            return {
                "id": "resp_empty",
                "status": "completed",
                "output": [],
                "usage": {"output_tokens": 100, "output_tokens_details": {"reasoning_tokens": 20}},
            }
        return {
            "id": "chatcmpl_final",
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"steps":[{"step_id":"001","skill":"create_primitive",'
                            '"args":{"primitive_type":"cube"}}]}'
                        )
                    }
                }
            ],
        }

    monkeypatch.setattr(adapter, "_post_chat_completions_http", _fake_http)

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert recorded["stage"] == "llm_empty_response"
    assert recorded["raw_plan"]["reason"] == "empty_responses_output"
    assert len(calls) == 3
    assert "tools" in calls[1]
    assert "text" in calls[1]
    assert "tools" not in calls[2]
    assert "text" not in calls[2]
    assert "messages" in calls[2]
    assert "input" not in calls[2]
    assert all(message.get("role") != "tool" for message in calls[2]["messages"])
    assert any(
        "COMPACT LOADED SKILL SUMMARY" in str(item.get("content", ""))
        for item in calls[2]["messages"]
        if isinstance(item, dict)
    )


@pytest.mark.asyncio
async def test_call_llm_tool_result_stream_timeout_switches_to_compact_retry(monkeypatch):
    OpenAICompatAdapter._COMPAT_MODE_CACHE.clear()
    stream_calls = []
    final_calls = []

    fake_openai = types.SimpleNamespace(
        OpenAI=object,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/tool-result-timeout",
            "default_model": "dummy-model-tool-result-timeout",
            "api_protocol": "openai_responses",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "use_streaming": True,
            "supports_streaming": True,
            "planning_capability_probe": {"enabled": False},
        },
        client=None,
    )
    adapter.get_skill_full = lambda skill_name: {
        "description": "create primitive",
        "args": {"primitive_type": {"required": True, "type": "str"}},
    }

    def _fake_stream(request_body, timeout_seconds, protocol=None):
        stream_calls.append(request_body)
        if len(stream_calls) == 1:
            return VBFLLMResponse(
                tool_calls=[
                    VBFLLMToolCall(
                        id="call_1",
                        name="load_skill",
                        arguments={"skill_name": "create_primitive"},
                    )
                ],
                finish_reason="tool_calls",
                protocol="openai_responses",
            )
        raise TimeoutError("stream timed out")

    def _fake_http(request_body, timeout_seconds, protocol=None):
        final_calls.append(request_body)
        return {
            "id": "resp_final",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"steps":[{"step_id":"001","skill":"create_primitive",'
                                '"args":{"primitive_type":"cube"}}]}'
                            ),
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(adapter, "_post_chat_completions_http_stream", _fake_stream)
    monkeypatch.setattr(adapter, "_post_chat_completions_http", _fake_http)

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert len(stream_calls) == 2
    assert len(final_calls) == 1
    assert "tools" in stream_calls[1]
    assert "text" in stream_calls[1]
    assert "tools" not in final_calls[0]
    assert "text" not in final_calls[0]
    assert all(item.get("type") != "function_call_output" for item in final_calls[0]["input"])
    assert any(
        "COMPACT LOADED SKILL SUMMARY" in str(item.get("content", ""))
        for item in final_calls[0]["input"]
        if isinstance(item, dict)
    )


@pytest.mark.asyncio
async def test_call_llm_uses_curl_http_compat_when_enabled(monkeypatch):
    observed = {}

    class _FakeHTTPStatusError(Exception):
        pass

    class _FakeRequestError(Exception):
        pass

    class _FakeTimeoutException(Exception):
        pass

    class _FakeResponse:
        status_code = 200
        text = '{"choices":[{"message":{"content":"{\\"steps\\":[{\\"step_id\\":\\"001\\",\\"skill\\":\\"create_primitive\\",\\"args\\":{\\"primitive_type\\":\\"cube\\"}}]}"}}]}'

        def raise_for_status(self):
            return None

        def json(self):
            return json.loads(self.text)

    class _FakeClient:
        def __init__(self, timeout=None):
            observed["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            observed["url"] = url
            observed["headers"] = headers
            observed["json"] = json
            return _FakeResponse()

    fake_httpx = types.SimpleNamespace(
        Client=_FakeClient,
        HTTPStatusError=_FakeHTTPStatusError,
        RequestError=_FakeRequestError,
        TimeoutException=_FakeTimeoutException,
    )
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "https://example.test/v1",
            "chat_completions_path": "/v1/chat/completions",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
            "enable_proxy_compatibility_mode": True,
            "enable_extra_request_headers": True,
            "use_curl_http_compat": True,
            "http_timeout_seconds": 123,
            "api_key": "key",
            "request_headers": {"User-Agent": "curl/8.8.0"},
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert observed["url"] == "https://example.test/v1/chat/completions"
    assert observed["headers"]["Authorization"] == "Bearer key"
    assert observed["headers"]["User-Agent"] == "curl/8.8.0"
    assert observed["headers"]["Accept"] == "application/json"
    assert observed["timeout"] == adapter._request_timeout_seconds()
    assert observed["json"]["model"] == "dummy-model"


@pytest.mark.asyncio
async def test_call_llm_accepts_stringified_completion_payload(monkeypatch):
    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    return (
                        '{"choices":[{"message":{"content":"{\\"steps\\":[{\\"step_id\\":\\"001\\",'
                        '\\"skill\\":\\"create_primitive\\",\\"args\\":{\\"primitive_type\\":\\"cube\\"}}]}"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"


@pytest.mark.asyncio
async def test_call_llm_fallback_on_empty_chunk_payload(monkeypatch):
    OpenAICompatAdapter._COMPAT_MODE_CACHE.clear()

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    # Simulate gateway returning empty chunk when tools/json enabled.
                    if "tools" in kwargs or "response_format" in kwargs:
                        return {
                            "id": "",
                            "object": "chat.completion.chunk",
                            "choices": [],
                        }
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert adapter._allow_tools is True
    assert adapter._allow_json_object is True


@pytest.mark.asyncio
async def test_call_llm_fallback_when_choice_message_is_none(monkeypatch):
    class _ResponseWithNoneMessage:
        object = "chat.completion"

        class _Choice:
            finish_reason = "stop"
            message = None

        choices = [_Choice()]

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    # First pass with tools enabled returns malformed response.
                    if "tools" in kwargs:
                        return _ResponseWithNoneMessage()
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"


@pytest.mark.asyncio
async def test_call_llm_fallback_when_choices_missing(monkeypatch):
    class _ResponseWithMissingChoices:
        object = "chat.completion"
        choices = None

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    if "tools" in kwargs:
                        return _ResponseWithMissingChoices()
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"


@pytest.mark.asyncio
async def test_call_llm_retries_without_tools_on_timeout_without_persisting(monkeypatch):
    calls = []

    class _FakeTimeout(Exception):
        pass

    class _FakeConnectionError(Exception):
        pass

    class _FakeAPIError(Exception):
        status_code = 500
        message = "api error"

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs)
                    if "tools" in kwargs:
                        raise _FakeTimeout("request timed out")
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=_FakeTimeout,
        APIConnectionError=_FakeConnectionError,
        APIError=_FakeAPIError,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/timeout-tools",
            "default_model": "dummy-model-timeout-tools",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": "auto",
            "planning_capability_probe": {"enabled": False},
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert "tools" in calls[0]
    assert "tools" in calls[1]
    assert "tools" not in calls[2]
    assert adapter._allow_tools is True


@pytest.mark.asyncio
async def test_call_llm_streaming_auto_probe_passes_and_uses_stream(monkeypatch):
    calls = []

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs)
                    if kwargs.get("stream"):
                        return iter([
                            {"choices": [{"delta": {"content": '{"steps":['}}]},
                            {
                                "choices": [
                                    {
                                        "delta": {
                                            "content": (
                                                '{"step_id":"001","skill":"create_primitive",'
                                                '"args":{"primitive_type":"cube"}}]}'
                                            )
                                        },
                                        "finish_reason": "stop",
                                    }
                                ]
                            },
                        ])
                    return {"choices": [{"message": {"content": '{"ok": true}'}}]}

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/stream-auto",
            "default_model": "dummy-model-stream-auto",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": "auto",
            "use_streaming": "auto",
            "supports_streaming": True,
            "planning_capability_probe": {
                "enabled": True,
                "timeout_seconds": 3,
                "cache_ttl_seconds": 3600,
            },
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert any(call.get("stream") is True for call in calls)
    assert adapter._allow_streaming is True


@pytest.mark.asyncio
async def test_call_llm_streaming_probe_failure_keeps_tools_nonstream(monkeypatch):
    calls = []

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs)
                    if kwargs.get("stream"):
                        raise RuntimeError("stream unsupported")
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/stream-probe-fail",
            "default_model": "dummy-model-stream-probe-fail",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": "auto",
            "use_streaming": "auto",
            "supports_streaming": True,
            "planning_capability_probe": {
                "enabled": True,
                "timeout_seconds": 3,
                "cache_ttl_seconds": 3600,
            },
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert adapter._allow_streaming is False
    assert adapter._allow_tools is True
    assert any("tools" in call and not call.get("stream") for call in calls)


@pytest.mark.asyncio
async def test_call_llm_streaming_runtime_failure_retries_nonstream(monkeypatch):
    calls = []

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs)
                    if kwargs.get("stream"):
                        raise RuntimeError("stream broke")
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/stream-runtime-fail",
            "default_model": "dummy-model-stream-runtime-fail",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "use_streaming": True,
            "supports_streaming": True,
            "planning_capability_probe": {"enabled": False},
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert [call.get("stream") for call in calls[:3]] == [True, True, True]
    assert not calls[3].get("stream")
    assert adapter._allow_streaming is True


@pytest.mark.asyncio
async def test_call_llm_streaming_tool_call_loop_loads_skill(monkeypatch):
    call_count = {"value": 0}

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    call_count["value"] += 1
                    if call_count["value"] == 1:
                        return iter([
                            {
                                "choices": [
                                    {
                                        "delta": {
                                            "tool_calls": [
                                                {
                                                    "index": 0,
                                                    "id": "call_1",
                                                    "type": "function",
                                                    "function": {
                                                        "name": "load_skill",
                                                        "arguments": '{"skill_',
                                                    },
                                                }
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                "choices": [
                                    {
                                        "delta": {
                                            "tool_calls": [
                                                {
                                                    "index": 0,
                                                    "function": {
                                                        "arguments": 'name": "create_primitive"}',
                                                    },
                                                }
                                            ]
                                        },
                                        "finish_reason": "tool_calls",
                                    }
                                ]
                            },
                        ])
                    return iter([
                        {
                            "choices": [
                                {
                                    "delta": {
                                        "content": (
                                            '{"steps":[{"step_id":"001","skill":"create_primitive",'
                                            '"args":{"primitive_type":"cube"}}]}'
                                        )
                                    },
                                    "finish_reason": "stop",
                                }
                            ]
                        }
                    ])

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/stream-tool-loop",
            "default_model": "dummy-model-stream-tool-loop",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "use_streaming": True,
            "supports_streaming": True,
            "planning_capability_probe": {"enabled": False},
        },
        client=None,
    )
    adapter.get_skill_full = lambda skill_name: {
        "description": "create primitive",
        "args": {"primitive_type": {"required": True, "type": "str"}},
    }

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert call_count["value"] == 2


@pytest.mark.asyncio
async def test_call_llm_tool_budget_exhaustion_retries_with_structured_history(monkeypatch):
    observed = {"calls": []}

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    observed["calls"].append(kwargs)
                    if "tools" in kwargs:
                        return {
                            "choices": [
                                {
                                    "finish_reason": "tool_calls",
                                    "message": {
                                        "content": "",
                                        "tool_calls": [
                                            {
                                                "id": f"call_{len(observed['calls'])}",
                                                "type": "function",
                                                "function": {
                                                    "name": "load_skill",
                                                    "arguments": '{"skill_name":"create_primitive"}',
                                                },
                                            }
                                        ],
                                    },
                                }
                        ]
                    }
                    assert all(
                        msg.get("role") != "tool"
                        for msg in kwargs.get("messages", [])
                        if isinstance(msg, dict)
                    )
                    assert any(
                        "COMPACT LOADED SKILL SUMMARY" in str(msg.get("content", ""))
                        for msg in kwargs.get("messages", [])
                        if isinstance(msg, dict)
                    )
                    assert any(
                        "The local load_skill tool budget for this planning call is exhausted"
                        in str(msg.get("content", ""))
                        for msg in kwargs.get("messages", [])
                        if isinstance(msg, dict)
                    )
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/tool-loop-exhausted",
            "default_model": "dummy-model-tool-loop-exhausted",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "max_tool_calls": 3,
            "planning_capability_probe": {"enabled": False},
        },
        client=None,
    )
    adapter.get_skill_full = lambda skill_name: {
        "description": "create primitive",
        "args": {"primitive_type": {"required": True, "type": "str"}},
    }

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert len(observed["calls"]) == 3
    assert "tools" not in observed["calls"][-1]


@pytest.mark.asyncio
async def test_call_llm_tool_loop_handles_none_assistant_content(monkeypatch):
    observed = {"assistant_content": None, "call_count": 0}

    class _Function:
        name = "load_skill"
        arguments = '{"skill_name": "create_primitive"}'

    class _ToolCall:
        id = "call_1"
        function = _Function()

    class _ToolMessage:
        content = None
        tool_calls = [_ToolCall()]

    class _ToolChoice:
        finish_reason = "tool_calls"
        message = _ToolMessage()

    class _ToolResponse:
        choices = [_ToolChoice()]

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    observed["call_count"] += 1
                    if observed["call_count"] == 1:
                        return _ToolResponse()
                    assistant_msgs = [
                        m for m in kwargs.get("messages", [])
                        if isinstance(m, dict) and m.get("role") == "assistant"
                    ]
                    observed["assistant_content"] = (
                        assistant_msgs[-1].get("content") if assistant_msgs else None
                    )
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/tool-loop",
            "default_model": "dummy-model-tool-loop",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert observed["assistant_content"] == ""


@pytest.mark.asyncio
async def test_call_llm_breaks_consecutive_tool_only_loop_early(monkeypatch):
    import sys
    import types

    from vbf.adapters.openai_compat_adapter import OpenAICompatAdapter

    observed = {"calls": []}

    class _Function:
        name = "load_skill"
        arguments = '{"skill_name": "create_primitive"}'

    class _ToolCall:
        id = "call_1"
        function = _Function()

    class _ToolMessage:
        content = ""
        tool_calls = [_ToolCall()]

    class _ToolChoice:
        finish_reason = "tool_calls"
        message = _ToolMessage()

    class _ToolResponse:
        choices = [_ToolChoice()]

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, default_headers=None, timeout=None):
            class _Completions:
                @staticmethod
                def create(**kwargs):
                    observed["calls"].append(kwargs)
                    if "tools" in kwargs:
                        return _ToolResponse()
                    return (
                        '{"steps":[{"step_id":"001","skill":"create_primitive",'
                        '"args":{"primitive_type":"cube"}}]}'
                    )

            class _Chat:
                completions = _Completions()

            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APITimeoutError=Exception,
        APIConnectionError=Exception,
        APIError=Exception,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1/tool-only-early-break",
            "default_model": "dummy-model-tool-only-early-break",
            "api_protocol": "chat",
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
            "max_tool_calls": 40,
            "max_consecutive_tool_only_rounds": 2,
            "planning_capability_probe": {"enabled": False},
        },
        client=None,
    )
    adapter.get_skill_full = lambda skill_name: {
        "description": "create primitive",
        "args": {"primitive_type": {"required": True, "type": "str"}},
    }

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert len(observed["calls"]) == 3
    assert "tools" not in observed["calls"][-1]
    final_messages = observed["calls"][-1]["messages"]
    assert all(message.get("role") != "tool" for message in final_messages)
    assert any(
        "COMPACT LOADED SKILL SUMMARY" in str(message.get("content", ""))
        for message in final_messages
    )
