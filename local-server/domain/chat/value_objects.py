"""
Value objects for the Chat bounded context.

Content blocks make up chat messages in a provider-neutral form. Model events
are what a ChatModel yields while streaming one model turn; chat events are
what ChatService yields while running one user turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Union

# Entity kinds the assistant links to, as `entity:<kind>/<id>`. Each maps to an
# entity page in the UI (property definitions have no page yet).
ENTITY_KINDS = ("taxonomy", "scheme", "class", "individual", "property")
# What the assistant can link to: the entity kinds, and change proposals (their
# review page).
LINK_KINDS = (*ENTITY_KINDS, "proposal")


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


@dataclass(frozen=True)
class EntityRef:
    """
    A workspace entity or change proposal a tool returned, so answers can link
    to its page; `kind` is one of LINK_KINDS.
    """

    id: str
    kind: str
    title: str


# ============================================================================
# Content blocks
# ============================================================================


@dataclass(frozen=True)
class TextBlock:
    """Plain text written by the user or the model."""

    text: str


@dataclass(frozen=True)
class ContextBlock:
    """
    Text the app adds to a user message for the model only.

    Carries the workspace summary and the page the user is viewing. Sent to the
    model as text, never shown as the user's words. Kept in the stored message
    (rather than the system prompt) so earlier requests stay unchanged, which
    models that replay reasoning blocks require.
    """

    text: str


@dataclass(frozen=True)
class ToolUseBlock:
    """A tool call requested by the model."""

    id: str
    name: str
    input: Mapping[str, Any]


@dataclass(frozen=True)
class ToolResultBlock:
    """
    The result of a tool call, sent back to the model.

    Attributes:
        tool_use_id: The tool call this answers
        content: Text sent to the model
        is_error: Whether the tool failed
        summary: Short human-readable summary for the UI (not sent to the model)
        entities: Entities the result mentions, so stored conversations can
            still validate entity links (not sent to the model)
    """

    tool_use_id: str
    content: str
    is_error: bool = False
    summary: str = ""
    entities: tuple[EntityRef, ...] = field(default_factory=tuple)


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


ContentBlock = Union[TextBlock, ContextBlock, ToolUseBlock, ToolResultBlock, ReasoningBlock]


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


@dataclass(frozen=True)
class ChatStatus:
    """Whether chat can run: the configured model and whether a provider serves it."""

    model: str
    available: bool
    max_tool_rounds: int
    available_models: tuple[str, ...] = ()


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


# ============================================================================
# Chat events (yielded by ChatService.send); TextDelta is shared
# ============================================================================


@dataclass(frozen=True)
class ToolStarted:
    """A tool began running."""

    tool_use_id: str
    name: str
    input: Mapping[str, Any]


@dataclass(frozen=True)
class ToolFinished:
    """
    A tool finished; `entities` are the refs answers may link to.

    Yielded once every tool call of the round has run and the results are
    stored, so a round's ToolFinished events follow all its ToolStarted ones.
    """

    tool_use_id: str
    name: str
    summary: str
    entities: tuple[EntityRef, ...]
    is_error: bool


@dataclass(frozen=True)
class TurnCompleted:
    """The assistant finished answering the user's message."""

    stop_reason: StopReason
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True)
class ChatFailed:
    """The turn failed; `message` is safe to show the user."""

    message: str


ChatEvent = Union[TextDelta, ToolStarted, ToolFinished, TurnCompleted, ChatFailed]
