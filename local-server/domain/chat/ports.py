"""
Port interfaces (protocols) for the Chat bounded context.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, Sequence

from domain.chat.entities import ChatMessage
from domain.chat.value_objects import ModelEvent, ToolSpec


class ChatModel(Protocol):
    """Port for a streaming, tool-calling chat model."""

    def stream_chat(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        model: str,
        max_tokens: int = 16000,
    ) -> AsyncIterator[ModelEvent]:
        """
        Stream one model turn.

        Yields TextDelta for answer text as it arrives, ToolCallRequested for each
        completed tool call, and finally one ModelTurnEnded carrying the full
        assistant content. The caller runs the tools and calls again with the
        assistant message and the tool results appended.
        """
        ...
