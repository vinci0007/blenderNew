from types import SimpleNamespace

from vbf.adapters.streaming_chat_completion_aggregator import (
    StreamingChatCompletionAggregator,
    iter_sse_json_chunks,
)


def test_streaming_aggregator_concatenates_content_chunks():
    aggregator = StreamingChatCompletionAggregator()

    aggregator.add_chunk({"choices": [{"delta": {"content": '{"steps": '}}]})
    aggregator.add_chunk({"choices": [{"delta": {"content": "[]}"}, "finish_reason": "stop"}]})

    result = aggregator.to_chat_completion()
    message = result["choices"][0]["message"]
    assert message["content"] == '{"steps": []}'
    assert result["choices"][0]["finish_reason"] == "stop"


def test_streaming_aggregator_concatenates_tool_call_arguments():
    aggregator = StreamingChatCompletionAggregator()

    aggregator.add_chunk({
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
    })
    aggregator.add_chunk({
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
    })

    result = aggregator.to_chat_completion()
    tool_call = result["choices"][0]["message"]["tool_calls"][0]
    assert tool_call["id"] == "call_1"
    assert tool_call["function"]["name"] == "load_skill"
    assert tool_call["function"]["arguments"] == '{"skill_name": "create_primitive"}'
    assert result["choices"][0]["finish_reason"] == "tool_calls"


def test_streaming_aggregator_accepts_object_like_chunks():
    aggregator = StreamingChatCompletionAggregator()
    delta = SimpleNamespace(content='{"steps":[]}', tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason="stop")
    chunk = SimpleNamespace(choices=[choice])

    aggregator.add_chunk(chunk)

    assert aggregator.to_chat_completion()["choices"][0]["message"]["content"] == '{"steps":[]}'


def test_streaming_aggregator_ignores_empty_chunks_and_done_lines():
    chunks = list(iter_sse_json_chunks([
        "",
        ": keepalive",
        "data: {\"choices\":[{\"delta\":{\"content\":\"ok\"}}]}",
        "data: [DONE]",
        "not-json",
    ]))
    aggregator = StreamingChatCompletionAggregator()
    aggregator.add_chunk({"choices": []})
    for chunk in chunks:
        aggregator.add_chunk(chunk)

    assert aggregator.to_chat_completion()["choices"][0]["message"]["content"] == "ok"

