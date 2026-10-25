"""
Unit tests for AnthropicChatModel.

Recorded-format SSE streams are fed through the real anthropic SDK via a mock
HTTP transport, so the tests cover the SDK's stream parsing as well as the
adapter's event mapping and request building.
"""

import json
from pathlib import Path

import httpx2
import pytest

from adapters.llm.anthropic_chat import AnthropicChatModel
from domain.chat.entities import ChatMessage
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


def _chat_model(fixture: str, status_code: int = 200):
    """Return a chat model whose HTTP calls answer with the fixture, and the request log."""
    requests: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        if status_code != 200:
            return httpx2.Response(
                status_code,
                json={"type": "error", "error": {"type": "authentication_error", "message": "x"}},
            )
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(FIXTURES / fixture).read_bytes(),
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    model = AnthropicChatModel("test-key", http_client=client)
    model._client = model._client.with_options(max_retries=0)
    return model, requests


async def _collect(model, messages, tools=(SEARCH,)):
    return [
        event
        async for event in model.stream_chat(
            system="sys", messages=messages, tools=list(tools), model="claude-sonnet-5-5"
        )
    ]


@pytest.mark.llm
class TestAnthropicChatStream:
    async def test_tool_call_turn_yields_text_tool_call_and_turn_end(self):
        model, _ = _chat_model("anthropic_tool_call.sse")

        events = await _collect(model, [_message(0, ChatRole.USER, TextBlock("find API ops"))])

        assert [e.text for e in events if isinstance(e, TextDelta)] == [
            "Let me search ",
            "the workspace.",
        ]
        calls = [e.tool_use for e in events if isinstance(e, ToolCallRequested)]
        assert calls == [
            ToolUseBlock(
                id="toolu_01AnthropicSearch",
                name="search_entities",
                input={"query": "API operation"},
            )
        ]
        ended = events[-1]
        assert isinstance(ended, ModelTurnEnded)
        assert ended.stop_reason == StopReason.TOOL_USE
        assert ended.tokens_in == 412 + 1024  # uncached + cache reads
        assert ended.tokens_out == 58

    async def test_turn_end_keeps_thinking_block_for_replay(self):
        model, _ = _chat_model("anthropic_tool_call.sse")

        events = await _collect(model, [_message(0, ChatRole.USER, TextBlock("q"))])

        reasoning, text, tool_use = events[-1].blocks
        assert reasoning == ReasoningBlock(
            provider="anthropic",
            data={"type": "thinking", "thinking": "", "signature": "EqQBCkYIBxgCKkDsig=="},
        )
        assert text == TextBlock("Let me search the workspace.")
        assert isinstance(tool_use, ToolUseBlock)

    async def test_answer_turn_ends_with_end_turn(self):
        model, _ = _chat_model("anthropic_answer.sse")

        events = await _collect(model, [_message(0, ChatRole.USER, TextBlock("q"))])

        assert "".join(e.text for e in events if isinstance(e, TextDelta)) == (
            "Yes: [Operation](entity:class/6f1c2a9e-0000-4000-8000-000000000001)."
        )
        assert not [e for e in events if isinstance(e, ToolCallRequested)]
        assert events[-1].stop_reason == StopReason.END_TURN

    async def test_auth_failure_raises_sdk_error_with_status_code(self):
        model, _ = _chat_model("anthropic_answer.sse", status_code=401)

        with pytest.raises(Exception) as exc_info:
            await _collect(model, [_message(0, ChatRole.USER, TextBlock("q"))])

        assert getattr(exc_info.value, "status_code", None) == 401


@pytest.mark.llm
class TestAnthropicChatRequest:
    async def test_request_carries_tools_system_caching_and_replayed_blocks(self):
        model, requests = _chat_model("anthropic_answer.sse")
        thinking = {"type": "thinking", "thinking": "", "signature": "sig"}
        messages = [
            _message(0, ChatRole.USER, TextBlock("find API ops")),
            _message(
                1,
                ChatRole.ASSISTANT,
                ReasoningBlock(provider="anthropic", data=thinking),
                ReasoningBlock(provider="openrouter", data={"reasoning_details": []}),
                TextBlock("Searching."),
                ToolUseBlock(id="toolu_1", name="search_entities", input={"query": "API"}),
            ),
            _message(
                2,
                ChatRole.USER,
                ToolResultBlock(tool_use_id="toolu_1", content="[]"),
                ContextBlock("Note for the model."),
            ),
        ]

        await _collect(model, messages)

        body = requests[0]
        assert body["model"] == "claude-sonnet-5-5"
        assert body["system"] == "sys"
        assert body["stream"] is True
        assert body["cache_control"] == {"type": "ephemeral"}
        assert "temperature" not in body
        assert body["tools"] == [
            {
                "name": "search_entities",
                "description": "Search workspace entities by text.",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
            }
        ]
        assert body["messages"] == [
            {"role": "user", "content": [{"type": "text", "text": "find API ops"}]},
            {
                "role": "assistant",
                "content": [
                    thinking,  # replayed unchanged; the other provider's reasoning is dropped
                    {"type": "text", "text": "Searching."},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "search_entities",
                        "input": {"query": "API"},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "[]",
                        "is_error": False,
                    },
                    {"type": "text", "text": "Note for the model."},
                ],
            },
        ]

    async def test_no_tools_key_when_no_tools(self):
        model, requests = _chat_model("anthropic_answer.sse")

        await _collect(model, [_message(0, ChatRole.USER, TextBlock("hi"))], tools=())

        assert "tools" not in requests[0]
