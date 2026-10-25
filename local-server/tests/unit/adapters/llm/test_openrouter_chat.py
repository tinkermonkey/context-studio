"""
Unit tests for OpenRouterChatModel.

The two SSE fixtures were recorded from OpenRouter with claude-sonnet-5-5: a
turn that requests two parallel tool calls, and the answer turn after the tool
results. They are replayed through an httpx mock transport.
"""

import json
from pathlib import Path

import httpx
import pytest

from adapters.llm.openrouter_chat import OpenRouterChatModel
from domain.chat.entities import ChatMessage
from domain.chat.exceptions import ChatModelError
from domain.chat.value_objects import (
    ChatRole,
    ContextBlock,
    ModelTurnEnded,
    ReasoningBlock,
    StopReason,
    TextBlock,
    TextDelta,
    ToolCallRequested,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)

FIXTURES = Path(__file__).parent / "fixtures" / "chat_streams"

SEARCH = ToolSpec(
    name="search_entities",
    description="Search workspace entities by text.",
    input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
)


def _message(seq, role, *blocks):
    return ChatMessage(id=f"m{seq}", conversation_id="c1", seq=seq, role=role, blocks=blocks)


def _sse(*chunks) -> bytes:
    lines = [": OPENROUTER PROCESSING", ""]
    for chunk in chunks:
        lines += [f"data: {json.dumps(chunk)}", ""]
    lines += ["data: [DONE]", ""]
    return "\n".join(lines).encode()


def _chat_model(body: bytes = b"", status_code: int = 200, error: Exception | None = None):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if error is not None:
            raise error
        return httpx.Response(
            status_code, headers={"content-type": "text/event-stream"}, content=body
        )

    return OpenRouterChatModel("test-key", transport=httpx.MockTransport(handler)), requests


async def _collect(model, messages, tools=(SEARCH,), model_id="claude-sonnet-5-5"):
    return [
        event
        async for event in model.stream_chat(
            system="sys", messages=messages, tools=list(tools), model=model_id
        )
    ]


USER_QUESTION = _message(0, ChatRole.USER, TextBlock("Is there a class for API operations?"))


@pytest.mark.llm
class TestOpenRouterChatRecordedStreams:
    async def test_tool_call_turn_accumulates_parallel_tool_calls(self):
        model, _ = _chat_model((FIXTURES / "openrouter_tool_call.sse").read_bytes())

        events = await _collect(model, [USER_QUESTION])

        calls = [e.tool_use for e in events if isinstance(e, ToolCallRequested)]
        assert calls == [
            ToolUseBlock(
                id="toolu_01RNaM3tWAKx418fVxLLf9bW",
                name="search_entities",
                input={"query": "API operation"},
            ),
            ToolUseBlock(
                id="toolu_014RLFq7DQYQhjL1DWm5Zwxh",
                name="search_entities",
                input={"query": "API"},
            ),
        ]
        ended = events[-1]
        assert isinstance(ended, ModelTurnEnded)
        assert ended.stop_reason == StopReason.TOOL_USE
        assert (ended.tokens_in, ended.tokens_out) == (461, 95)
        assert list(ended.blocks) == calls

    async def test_answer_turn_streams_text_with_entity_link(self):
        model, _ = _chat_model((FIXTURES / "openrouter_answer.sse").read_bytes())

        events = await _collect(model, [USER_QUESTION])

        deltas = [e.text for e in events if isinstance(e, TextDelta)]
        assert len(deltas) > 1
        answer = "".join(deltas)
        assert "[Operation](entity:class/6f1c2a9e-0000-4000-8000-000000000001)" in answer
        ended = events[-1]
        assert ended.stop_reason == StopReason.END_TURN
        assert ended.blocks == (TextBlock(answer),)
        assert (ended.tokens_in, ended.tokens_out) == (730, 71)


@pytest.mark.llm
class TestOpenRouterChatChunks:
    async def test_reasoning_details_fragments_merge_by_index(self):
        body = _sse(
            {
                "choices": [
                    {
                        "delta": {
                            "reasoning_details": [
                                {
                                    "type": "reasoning.text",
                                    "text": "Let me ",
                                    "signature": None,
                                    "format": "anthropic-claude-v1",
                                    "index": 0,
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
                            "reasoning_details": [
                                {"type": "reasoning.text", "text": "think.", "index": 0},
                                {"type": "reasoning.text", "signature": "sig", "index": 0},
                            ]
                        }
                    }
                ]
            },
            {"choices": [{"delta": {"content": "Hi"}, "finish_reason": "stop"}]},
        )
        model, _ = _chat_model(body)

        events = await _collect(model, [USER_QUESTION])

        assert events[-1].blocks == (
            ReasoningBlock(
                provider="openrouter",
                data={
                    "reasoning_details": [
                        {
                            "type": "reasoning.text",
                            "text": "Let me think.",
                            "format": "anthropic-claude-v1",
                            "index": 0,
                            "signature": "sig",
                        }
                    ]
                },
            ),
            TextBlock("Hi"),
        )

    async def test_invalid_tool_arguments_become_empty_input(self):
        body = _sse(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {"name": "search_entities", "arguments": "{bad"},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        )
        model, _ = _chat_model(body)

        events = await _collect(model, [USER_QUESTION])

        assert events[0] == ToolCallRequested(
            ToolUseBlock(id="call_1", name="search_entities", input={})
        )

    async def test_length_finish_maps_to_max_tokens(self):
        model, _ = _chat_model(
            _sse({"choices": [{"delta": {"content": "x"}, "finish_reason": "length"}]})
        )

        events = await _collect(model, [USER_QUESTION])

        assert events[-1].stop_reason == StopReason.MAX_TOKENS

    async def test_mid_stream_error_raises(self):
        model, _ = _chat_model(_sse({"error": {"message": "overloaded", "code": 502}}))

        with pytest.raises(ChatModelError, match="overloaded"):
            await _collect(model, [USER_QUESTION])


@pytest.mark.llm
class TestOpenRouterChatErrors:
    @pytest.mark.parametrize("status_code", [401, 403, 429, 500])
    async def test_http_error_raises_with_status_code(self, status_code):
        model, _ = _chat_model(b'{"error": {"message": "nope"}}', status_code=status_code)

        with pytest.raises(ChatModelError) as exc_info:
            await _collect(model, [USER_QUESTION])

        assert exc_info.value.status_code == status_code

    async def test_timeout_raises_chat_model_error(self):
        model, _ = _chat_model(error=httpx.ReadTimeout("slow"))

        with pytest.raises(ChatModelError, match="ReadTimeout"):
            await _collect(model, [USER_QUESTION])

    def test_empty_api_key_rejected(self):
        with pytest.raises(ValueError):
            OpenRouterChatModel("")


@pytest.mark.llm
class TestOpenRouterChatRequest:
    async def test_request_body_converts_conversation_and_tools(self):
        model, requests = _chat_model(_sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}))
        reasoning = {"reasoning_details": [{"type": "reasoning.text", "text": "t", "index": 0}]}
        messages = [
            USER_QUESTION,
            _message(
                1,
                ChatRole.ASSISTANT,
                ReasoningBlock(provider="openrouter", data=reasoning),
                ReasoningBlock(provider="anthropic", data={"type": "thinking"}),
                TextBlock("Searching."),
                ToolUseBlock(id="call_1", name="search_entities", input={"query": "API"}),
            ),
            _message(
                2,
                ChatRole.USER,
                ToolResultBlock(tool_use_id="call_1", content="[]"),
                ContextBlock("Note for the model."),
                TextBlock("Also check schemes."),
            ),
        ]

        await _collect(model, messages)

        request = requests[0]
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "anthropic/claude-sonnet-5-5"  # bare id prefixed by _wire_model
        assert body["stream"] is True
        assert body["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "search_entities",
                    "description": "Search workspace entities by text.",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
                },
            }
        ]
        assert body["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "Is there a class for API operations?"},
            {
                "role": "assistant",
                "content": "Searching.",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search_entities", "arguments": '{"query": "API"}'},
                    }
                ],
                "reasoning_details": reasoning["reasoning_details"],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "[]"},
            {"role": "user", "content": "Note for the model.\n\nAlso check schemes."},
        ]

    async def test_prefixed_model_id_passes_through_and_no_tools_key(self):
        model, requests = _chat_model(_sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}))

        await _collect(model, [USER_QUESTION], tools=(), model_id="openai/gpt-5")

        body = json.loads(requests[0].content)
        assert body["model"] == "openai/gpt-5"
        assert "tools" not in body

    async def test_each_turn_makes_a_fresh_request(self):
        """No response cache: the same request twice hits the API twice."""
        model, requests = _chat_model(_sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}))

        await _collect(model, [USER_QUESTION])
        await _collect(model, [USER_QUESTION])

        assert len(requests) == 2
