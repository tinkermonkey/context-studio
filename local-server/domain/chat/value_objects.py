"""
Value objects for the Chat bounded context.

Content blocks make up chat messages in a provider-neutral form. Model events
are what a ChatModel yields while streaming one model turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Union


class ChatRole(str, Enum):
    """Who wrote a chat message. Tool results travel in user messages."""

    USER = "user"
    ASSISTANT = "assistant"


class StopReason(str, Enum):
    """Why the model stopped a turn, normalized across providers."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    REFUSAL = "refusal"
    OTHER = "other"


# ============================================================================
# Content blocks
# ============================================================================


@dataclass(frozen=True)
class TextBlock:
    """Plain text written by the user or the model."""

    text: str


@dataclass(frozen=True)
class ToolUseBlock:
    """A tool call requested by the model."""

    id: str
    name: str
    input: Mapping[str, Any]


@dataclass(frozen=True)
class ToolResultBlock:
    """The result of a tool call, sent back to the model."""

    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class ReasoningBlock:
    """
    Opaque model reasoning that must be passed back unchanged.

    Providers return reasoning (Anthropic thinking blocks, OpenRouter
    reasoning_details) that has to be replayed verbatim on later requests in the
    same conversation. Only the adapter for `provider` reads `data`; other
    adapters drop the block.
    """

    provider: str
    data: Mapping[str, Any]


ContentBlock = Union[TextBlock, ToolUseBlock, ToolResultBlock, ReasoningBlock]


# ============================================================================
# Tools and context
# ============================================================================


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call: name, description and JSON Schema of its input."""

    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True)
class PageContext:
    """The page the user is viewing when they send a message."""

    route: str
    entity_kind: Optional[str] = None
    entity_id: Optional[str] = None


@dataclass(frozen=True)
class EntityRef:
    """A workspace entity a tool returned, so answers can link to its page."""

    id: str
    kind: str
    title: str


@dataclass(frozen=True)
class ToolOutcome:
    """
    What a tool returns.

    Attributes:
        content: Text sent back to the model
        summary: Short human-readable summary for the UI
        entities: Entities the result mentions
        is_error: Whether the tool failed
    """

    content: str
    summary: str
    entities: tuple[EntityRef, ...] = field(default_factory=tuple)
    is_error: bool = False


# ============================================================================
# Model events (yielded by ChatModel.stream_chat)
# ============================================================================


@dataclass(frozen=True)
class TextDelta:
    """A fragment of the model's answer text."""

    text: str


@dataclass(frozen=True)
class ToolCallRequested:
    """The model finished writing a tool call."""

    tool_use: ToolUseBlock


@dataclass(frozen=True)
class ModelTurnEnded:
    """
    The model turn is complete.

    Attributes:
        stop_reason: Why the model stopped
        tokens_in: Input tokens consumed (including cached input)
        tokens_out: Output tokens generated
        blocks: The full assistant content in order (reasoning, text, tool calls),
            to store and replay on the next request
    """

    stop_reason: StopReason
    tokens_in: int
    tokens_out: int
    blocks: tuple[ContentBlock, ...]


ModelEvent = Union[TextDelta, ToolCallRequested, ModelTurnEnded]
