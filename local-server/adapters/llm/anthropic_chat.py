"""
Anthropic streaming chat adapter.

Implements the ChatModel port over the Anthropic Messages API with tools,
using the async SDK's `messages.stream()` helper. Thinking blocks are kept as
ReasoningBlocks and passed back unchanged on later requests, which the API
requires for models that think between tool calls.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Sequence

import anthropic

from adapters.llm.anthropic_provider import AnthropicProvider
from domain.chat.entities import ChatMessage
from domain.chat.value_objects import (
    ContentBlock,
    ContextBlock,
    ModelEvent,
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

PROVIDER = "anthropic"

_REASONING_BLOCK_TYPES = ("thinking", "redacted_thinking")

# A short connect timeout and one retry, so an unreachable API fails within
# seconds and the router can fall through to the next provider; reads keep the
# SDK's long default, since a turn can stream for minutes.
_TIMEOUT = anthropic.Timeout(600.0, connect=3.0)
_MAX_RETRIES = 1

_STOP_REASONS = {
    "end_turn": StopReason.END_TURN,
    "stop_sequence": StopReason.END_TURN,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
    "refusal": StopReason.REFUSAL,
}


class AnthropicChatModel:
    """ChatModel adapter for Anthropic Claude models."""

    def __init__(self, api_key: str, http_client: Any = None) -> None:
        """
        Initialize the adapter.

        Args:
            api_key: Anthropic API key
            http_client: Optional HTTP client for the SDK (tests inject a mock transport)
        """
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, http_client=http_client, timeout=_TIMEOUT, max_retries=_MAX_RETRIES
        )

    def list_models(self) -> list[str]:
        """Known Claude model ids (others may also work)."""
        return list(AnthropicProvider.AVAILABLE_MODELS)

    async def stream_chat(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        model: str,
        max_tokens: int = 16000,
    ) -> AsyncIterator[ModelEvent]:
        """Stream one model turn. See ChatModel.stream_chat."""
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [to_anthropic_message(m) for m in messages],
            # Automatic prompt caching: each tool round re-sends the whole prefix.
            "cache_control": {"type": "ephemeral"},
        }
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": dict(t.input_schema)}
                for t in tools
            ]

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "text":
                    yield TextDelta(text=event.text)
                elif event.type == "content_block_stop" and event.content_block.type == "tool_use":
                    yield ToolCallRequested(tool_use=_tool_use_block(event.content_block))
            final = await stream.get_final_message()

        usage = final.usage
        tokens_in = (
            usage.input_tokens
            + (usage.cache_read_input_tokens or 0)
            + (usage.cache_creation_input_tokens or 0)
        )
        yield ModelTurnEnded(
            stop_reason=_STOP_REASONS.get(final.stop_reason or "", StopReason.OTHER),
            tokens_in=tokens_in,
            tokens_out=usage.output_tokens,
            blocks=tuple(_from_anthropic_blocks(final.content)),
        )


def to_anthropic_message(message: ChatMessage) -> dict[str, Any]:
    """Convert a chat message to an Anthropic Messages API message."""
    content: list[dict[str, Any]] = []
    for block in message.blocks:
        if isinstance(block, (TextBlock, ContextBlock)):
            if block.text:
                content.append({"type": "text", "text": block.text})
        elif isinstance(block, ToolUseBlock):
            content.append(
                {"type": "tool_use", "id": block.id, "name": block.name, "input": dict(block.input)}
            )
        elif isinstance(block, ToolResultBlock):
            content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": block.is_error,
                }
            )
        elif isinstance(block, ReasoningBlock) and block.provider == PROVIDER:
            content.append(dict(block.data))
    return {"role": message.role.value, "content": content}


def _tool_use_block(block: Any) -> ToolUseBlock:
    tool_input = block.input if isinstance(block.input, dict) else {}
    return ToolUseBlock(id=block.id, name=block.name, input=tool_input)


def _from_anthropic_blocks(blocks: Sequence[Any]) -> list[ContentBlock]:
    result: list[ContentBlock] = []
    for block in blocks:
        if block.type == "text":
            result.append(TextBlock(text=block.text))
        elif block.type == "tool_use":
            result.append(_tool_use_block(block))
        elif block.type in _REASONING_BLOCK_TYPES:
            result.append(ReasoningBlock(provider=PROVIDER, data=block.to_dict()))
    return result
