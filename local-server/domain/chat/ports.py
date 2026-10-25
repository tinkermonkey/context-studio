"""
Port interfaces (protocols) for the Chat bounded context.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping, Optional, Protocol, Sequence

from domain.chat.entities import ChatMessage, Conversation
from domain.chat.value_objects import ModelEvent, PageContext, ToolOutcome, ToolSpec


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

    def supports_model(self, model: str) -> bool:
        """Whether a configured chat provider can serve the model."""
        ...

    def list_models(self) -> list[str]:
        """Known model ids the configured chat providers serve (others may also work)."""
        ...


class ChatTool(Protocol):
    """Port for a read-only tool the assistant can call."""

    @property
    def spec(self) -> ToolSpec:
        """The tool's name, description and input schema."""
        ...

    async def execute(self, args: Mapping[str, Any]) -> ToolOutcome:
        """
        Run the tool.

        Invalid arguments and missing entities are reported as an outcome with
        is_error=True rather than raised.
        """
        ...


class ConversationRepository(Protocol):
    """Port for storing conversations and their messages."""

    async def save_conversation(self, conversation: Conversation) -> None:
        """Insert or update a conversation."""
        ...

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Return the conversation, or None if it does not exist."""
        ...

    async def list_conversations(self, limit: int) -> list[Conversation]:
        """Return conversations, most recently updated first."""
        ...

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and its messages; False if it did not exist."""
        ...

    async def add_message(self, message: ChatMessage) -> None:
        """Append a message to its conversation."""
        ...

    async def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        """Return a conversation's messages in order."""
        ...


class ChatSettings(Protocol):
    """Port for chat configuration, read on every turn so changes apply at once."""

    def model(self) -> str:
        """The model the assistant uses."""
        ...

    def max_tool_rounds(self) -> int:
        """Maximum model-to-tools round trips in one turn."""
        ...


class WorkspaceContext(Protocol):
    """Port for describing the workspace and the viewed page to the model."""

    async def summarize(self) -> str:
        """A short description of what the workspace contains."""
        ...

    async def describe_page(self, page_context: PageContext) -> Optional[str]:
        """A sentence naming the entity the user is viewing, or None if none."""
        ...
