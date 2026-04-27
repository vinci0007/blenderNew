from vbf.adapters.openai_compat_adapter import OpenAICompatAdapter
import sys
import types
import pytest


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


def test_adapter_sanitizes_request_headers():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "is_proxy_api": True,
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


def test_adapter_ignores_request_headers_when_disabled():
    adapter = OpenAICompatAdapter(
        model_name="default",
        model_config={
            "base_url": "http://127.0.0.1:12347/v1",
            "default_model": "dummy-model",
            "is_proxy_api": True,
            "enable_extra_request_headers": False,
            "request_headers": {
                "User-Agent": "curl/8.8.0",
            },
        },
        client=None,
    )

    assert adapter.request_headers == {}


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
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
            "is_proxy_api": True,
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
            "response_format": {"type": "json_object"},
            "use_function_calling": False,
            "is_proxy_api": True,
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
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"


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
            "response_format": {"type": "json_object"},
            "use_function_calling": "auto",
            "planning_capability_probe": {"enabled": False},
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])

    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert "tools" in calls[0]
    assert "tools" not in calls[1]
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
    assert calls[0].get("stream") is True
    assert not calls[1].get("stream")
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
            "response_format": {"type": "json_object"},
            "use_function_calling": True,
        },
        client=None,
    )

    parsed = await adapter.call_llm([{"role": "user", "content": "make cube"}])
    assert parsed["steps"][0]["skill"] == "create_primitive"
    assert observed["assistant_content"] == ""
