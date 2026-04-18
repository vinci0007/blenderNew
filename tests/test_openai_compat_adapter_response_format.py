from vbf.adapters.openai_compat_adapter import OpenAICompatAdapter


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
