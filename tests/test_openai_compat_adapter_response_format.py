from vbf.adapters.openai_compat_adapter import OpenAICompatAdapter
import sys
import types
import pytest


class _Err:
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


def test_parse_response_unwraps_markdown_then_extracts_outermost_json():
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
    assert "Schema Cards (Tools-Off Fallback)" in prompt
    assert "create_primitive | required:" in prompt


@pytest.mark.asyncio
async def test_call_llm_accepts_plain_string_gateway_response(monkeypatch):
    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
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
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"


@pytest.mark.asyncio
async def test_call_llm_accepts_stringified_completion_payload(monkeypatch):
    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
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
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"


@pytest.mark.asyncio
async def test_call_llm_fallback_on_empty_chunk_payload(monkeypatch):
    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
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
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"
