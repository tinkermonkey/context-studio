"""
OpenRouter streaming chat adapter.

Implements the ChatModel port over OpenRouter's OpenAI-compatible chat
completions API with `stream: true` and function tools, using async httpx.
Responses are never cached: every chat turn is a fresh request.

Tool-call arguments and reasoning_details arrive in fragments keyed by index
and are accumulated until the stream ends. reasoning_details are kept as a
ReasoningBlock and passed back unchanged on the assistant message, as
OpenRouter requires for Claude models during tool use.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional, Sequence

import httpx

from adapters.llm.anthropic_provider import AnthropicProvider
from adapters.llm.openrouter_provider import OpenRouterProvider
from domain.chat.entities import ChatMessage
from domain.chat.exceptions import ChatModelError
from domain.chat.value_objects import (
    ChatRole,
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
from utils.logger import get_logger

logger = get_logger(__name__)

PROVIDER = "openrouter"

_STOP_REASONS = {
    "stop": StopReason.END_TURN,
    "tool_calls": StopReason.TOOL_USE,
    "length": StopReason.MAX_TOKENS,
    "content_filter": StopReason.REFUSAL,
}

# reasoning_details fields that stream as text fragments to concatenate; any
# other field (id, type, format, signature, data) keeps its last non-null value.
_CONCATENATED_REASONING_FIELDS = ("text", "summary")


@dataclass
class _ToolCallParts:
    id: str = ""
    name: str = ""
    arguments: str = ""


@dataclass
class _TurnState:
    text: list[str] = field(default_factory=list)
    tool_calls: dict[int, _ToolCallParts] = field(default_factory=dict)
    reasoning: dict[int, dict[str, Any]] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0


class OpenRouterChatModel:
    """ChatModel adapter for OpenRouter."""

    def __init__(
        self,
        api_key: str,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        timeout: float = 60.0,
    ) -> None:
        """
        Initialize the adapter.

        Args:
            api_key: OpenRouter API key
            transport: Optional httpx transport (tests inject a mock transport)
            timeout: Connect/read timeout in seconds (read applies between chunks)
        """
        if not api_key:
            raise ValueError("OpenRouter API key not configured")
        self._api_key = api_key
        self._transport = transport
        self._timeout = timeout

    def list_models(self) -> list[str]:
        """
        Known model ids to suggest (OpenRouter serves many more).

        The Claude ids, which route here by their bare names, then OpenRouter's
        default model.
        """
        models = list(AnthropicProvider.AVAILABLE_MODELS)
        if OpenRouterProvider.DEFAULT_MODEL not in models:
            models.append(OpenRouterProvider.DEFAULT_MODEL)
        return models

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
        body: dict[str, Any] = {
            "model": OpenRouterProvider._wire_model(model),
            "messages": to_openai_messages(system, messages),
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": dict(t.input_schema),
                    },
                }
                for t in tools
            ]

        state = _TurnState()
        try:
            async with httpx.AsyncClient(
                base_url=OpenRouterProvider.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "HTTP-Referer": "https://contextstudio.local",
                    "X-Title": "Context Studio",
                },
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                async with client.stream("POST", "/chat/completions", json=body) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode(errors="replace")[:500]
                        raise ChatModelError(
                            f"OpenRouter API error {response.status_code}: {detail}",
                            status_code=response.status_code,
                        )
                    async for chunk in _sse_chunks(response):
                        text = _apply_chunk(state, chunk)
                        if text:
                            yield TextDelta(text=text)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise ChatModelError(f"OpenRouter request failed: {type(e).__name__}: {e}") from e

        tool_uses = [_tool_use_block(parts) for _, parts in sorted(state.tool_calls.items())]
        for tool_use in tool_uses:
            yield ToolCallRequested(tool_use=tool_use)

        blocks: list[ContentBlock] = []
        if state.reasoning:
            details = [state.reasoning[i] for i in sorted(state.reasoning)]
            blocks.append(ReasoningBlock(provider=PROVIDER, data={"reasoning_details": details}))
        if state.text:
            blocks.append(TextBlock(text="".join(state.text)))
        blocks.extend(tool_uses)

        yield ModelTurnEnded(
            stop_reason=_STOP_REASONS.get(state.finish_reason or "", StopReason.OTHER),
            tokens_in=state.tokens_in,
            tokens_out=state.tokens_out,
            blocks=tuple(blocks),
        )


def to_openai_messages(system: str, messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    """Convert chat messages to OpenAI-style chat completion messages."""
    result: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for message in messages:
        if message.role == ChatRole.ASSISTANT:
            result.append(_assistant_message(message))
            continue
        # Tool results must directly follow the assistant message that called the tools.
        for block in message.blocks:
            if isinstance(block, ToolResultBlock):
                result.append(
                    {"role": "tool", "tool_call_id": block.tool_use_id, "content": block.content}
                )
        text = _joined_text(message)
        if text:
            result.append({"role": "user", "content": text})
    return result


def _assistant_message(message: ChatMessage) -> dict[str, Any]:
    entry: dict[str, Any] = {"role": "assistant", "content": _joined_text(message) or None}
    tool_calls = [
        {
            "id": block.id,
            "type": "function",
            "function": {"name": block.name, "arguments": json.dumps(dict(block.input))},
        }
        for block in message.blocks
        if isinstance(block, ToolUseBlock)
    ]
    if tool_calls:
        entry["tool_calls"] = tool_calls
    for block in message.blocks:
        if isinstance(block, ReasoningBlock) and block.provider == PROVIDER:
            entry["reasoning_details"] = list(block.data.get("reasoning_details", []))
    return entry


def _joined_text(message: ChatMessage) -> str:
    return "\n\n".join(
        b.text for b in message.blocks if isinstance(b, (TextBlock, ContextBlock)) and b.text
    )


async def _sse_chunks(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """Yield the JSON payload of each SSE data line until [DONE]."""
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue  # blank separators and ": OPENROUTER PROCESSING" keep-alive comments
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            return
        chunk = json.loads(payload)
        if "error" in chunk:
            error = chunk["error"]
            message = error.get("message", error) if isinstance(error, dict) else error
            raise ChatModelError(f"OpenRouter stream error: {message}")
        yield chunk


def _apply_chunk(state: _TurnState, chunk: dict[str, Any]) -> str:
    """Accumulate one chunk into the turn state and return its answer text."""
    usage = chunk.get("usage")
    if usage:
        state.tokens_in = usage.get("prompt_tokens", state.tokens_in)
        state.tokens_out = usage.get("completion_tokens", state.tokens_out)

    text = ""
    for choice in chunk.get("choices") or []:
        if choice.get("finish_reason"):
            state.finish_reason = choice["finish_reason"]
        delta = choice.get("delta") or {}
        if delta.get("content"):
            text += delta["content"]
        for call in delta.get("tool_calls") or []:
            parts = state.tool_calls.setdefault(call.get("index", 0), _ToolCallParts())
            parts.id = call.get("id") or parts.id
            function = call.get("function") or {}
            parts.name = function.get("name") or parts.name
            parts.arguments += function.get("arguments") or ""
        for detail in delta.get("reasoning_details") or []:
            _merge_reasoning(state.reasoning, detail)
    if text:
        state.text.append(text)
    return text


def _merge_reasoning(reasoning: dict[int, dict[str, Any]], fragment: dict[str, Any]) -> None:
    merged = reasoning.setdefault(fragment.get("index", 0), {})
    for key, value in fragment.items():
        if value is None:
            continue
        if key in _CONCATENATED_REASONING_FIELDS:
            merged[key] = merged.get(key, "") + value
        else:
            merged[key] = value


def _tool_use_block(parts: _ToolCallParts) -> ToolUseBlock:
    try:
        tool_input = json.loads(parts.arguments) if parts.arguments.strip() else {}
    except json.JSONDecodeError:
        logger.warning(
            "OpenRouter: tool call %s (%s) has invalid JSON arguments; sending it empty input",
            parts.id,
            parts.name,
        )
        tool_input = {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    return ToolUseBlock(id=parts.id, name=parts.name, input=tool_input)
