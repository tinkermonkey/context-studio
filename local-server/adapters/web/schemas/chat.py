"""
Pydantic schemas for the chat API.

Message content is returned as typed blocks for display: text, tool calls and
tool results (summary and entity refs, not the raw content sent to the model).
Model reasoning and app-added context notes are internal and not returned.

The SSE stream's events share one discriminated union, ChatStreamEvent; each
event's SSE `event:` name equals its `type`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from domain.chat.entities import ChatMessage, Conversation
from domain.chat.value_objects import (
    ChatEvent,
    ChatFailed,
    ChatStatus,
    EntityRef,
    PageContext,
    TextBlock,
    TextDelta,
    ToolFinished,
    ToolResultBlock,
    ToolStarted,
    ToolUseBlock,
    TurnCompleted,
)

EntityKind = Literal["taxonomy", "scheme", "class", "individual", "property"]


class EntityRefSchema(BaseModel):
    """An entity a tool returned; answers may link to it as entity:<kind>/<id>."""

    id: str
    kind: EntityKind
    title: str

    @classmethod
    def from_domain(cls, ref: EntityRef) -> "EntityRefSchema":
        return cls(id=ref.id, kind=ref.kind, title=ref.title)  # type: ignore[arg-type]


class PageContextSchema(BaseModel):
    """The page the user is viewing when sending a message."""

    route: str = Field(..., min_length=1, max_length=500, description="Current app route")
    entity_kind: Optional[EntityKind] = Field(None, description="Kind of the viewed entity")
    entity_id: Optional[str] = Field(None, max_length=100, description="Id of the viewed entity")

    def to_domain(self) -> PageContext:
        return PageContext(route=self.route, entity_kind=self.entity_kind, entity_id=self.entity_id)

    @classmethod
    def from_domain(cls, page_context: PageContext) -> "PageContextSchema":
        return cls(
            route=page_context.route,
            entity_kind=page_context.entity_kind,  # type: ignore[arg-type]
            entity_id=page_context.entity_id,
        )


class ChatStatusResponse(BaseModel):
    """Whether chat can run with the configured model."""

    model: str = Field(..., description="Configured chat model (config.json chat.model)")
    available: bool = Field(..., description="Whether a configured provider serves the model")
    max_tool_rounds: int

    @classmethod
    def from_domain(cls, status: ChatStatus) -> "ChatStatusResponse":
        return cls(
            model=status.model, available=status.available, max_tool_rounds=status.max_tool_rounds
        )


class ConversationResponse(BaseModel):
    """A stored conversation."""

    id: str
    title: str
    model: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, conversation: Conversation) -> "ConversationResponse":
        return cls(
            id=conversation.id,
            title=conversation.title,
            model=conversation.model,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )


class TextBlockSchema(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlockSchema(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlockSchema(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    summary: str
    is_error: bool
    entities: list[EntityRefSchema]


MessageBlock = Annotated[
    Union[TextBlockSchema, ToolUseBlockSchema, ToolResultBlockSchema],
    Field(discriminator="type"),
]


class ChatMessageResponse(BaseModel):
    """A stored message with its displayable blocks."""

    id: str
    seq: int
    role: Literal["user", "assistant"]
    blocks: list[MessageBlock]
    page_context: Optional[PageContextSchema] = None
    created_at: datetime

    @classmethod
    def from_domain(cls, message: ChatMessage) -> "ChatMessageResponse":
        blocks: list[Any] = []
        for block in message.blocks:
            if isinstance(block, TextBlock):
                blocks.append(TextBlockSchema(text=block.text))
            elif isinstance(block, ToolUseBlock):
                blocks.append(
                    ToolUseBlockSchema(id=block.id, name=block.name, input=dict(block.input))
                )
            elif isinstance(block, ToolResultBlock):
                blocks.append(
                    ToolResultBlockSchema(
                        tool_use_id=block.tool_use_id,
                        summary=block.summary,
                        is_error=block.is_error,
                        entities=[EntityRefSchema.from_domain(e) for e in block.entities],
                    )
                )
        return cls(
            id=message.id,
            seq=message.seq,
            role=message.role.value,  # type: ignore[arg-type]
            blocks=blocks,
            page_context=(
                PageContextSchema.from_domain(message.page_context)
                if message.page_context
                else None
            ),
            created_at=message.created_at,
        )


class ConversationDetailResponse(ConversationResponse):
    """A conversation with its messages in order."""

    messages: list[ChatMessageResponse]


class SendMessageRequest(BaseModel):
    """A user message, with the page the user is viewing."""

    text: str = Field(..., min_length=1, max_length=8000)
    page_context: Optional[PageContextSchema] = None


# ============================================================================
# SSE stream events
# ============================================================================


class MessageStartEvent(BaseModel):
    type: Literal["message_start"] = "message_start"
    conversation_id: str


class TextDeltaEvent(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class ToolStartEvent(BaseModel):
    type: Literal["tool_start"] = "tool_start"
    tool_use_id: str
    name: str
    input: dict[str, Any]


class ToolEndEvent(BaseModel):
    """A tool finished; `entities` are the ids answers may link to."""

    type: Literal["tool_end"] = "tool_end"
    tool_use_id: str
    name: str
    summary: str
    is_error: bool
    entities: list[EntityRefSchema]


class MessageEndEvent(BaseModel):
    type: Literal["message_end"] = "message_end"
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "refusal", "other"]
    tokens_in: int
    tokens_out: int


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


ChatStreamEvent = Annotated[
    Union[
        MessageStartEvent,
        TextDeltaEvent,
        ToolStartEvent,
        ToolEndEvent,
        MessageEndEvent,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]


def stream_event_from_domain(event: ChatEvent) -> BaseModel:
    """Convert a ChatService event to its SSE payload."""
    if isinstance(event, TextDelta):
        return TextDeltaEvent(text=event.text)
    if isinstance(event, ToolStarted):
        return ToolStartEvent(
            tool_use_id=event.tool_use_id, name=event.name, input=dict(event.input)
        )
    if isinstance(event, ToolFinished):
        return ToolEndEvent(
            tool_use_id=event.tool_use_id,
            name=event.name,
            summary=event.summary,
            is_error=event.is_error,
            entities=[EntityRefSchema.from_domain(e) for e in event.entities],
        )
    if isinstance(event, TurnCompleted):
        return MessageEndEvent(
            stop_reason=event.stop_reason.value,  # type: ignore[arg-type]
            tokens_in=event.tokens_in,
            tokens_out=event.tokens_out,
        )
    if isinstance(event, ChatFailed):
        return ErrorEvent(message=event.message)
    raise TypeError(f"Unknown chat event: {type(event).__name__}")
