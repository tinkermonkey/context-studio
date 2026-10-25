"""
SQLite repository for chat conversations (operations.db).

Implements the chat ConversationRepository port. Message content blocks are
stored as a JSON list of typed dicts. The port is async; each call runs its
synchronous SQLAlchemy work in the thread pool.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.operations.models import ChatConversation, ChatMessageRecord
from domain.chat.entities import ChatMessage, Conversation
from domain.chat.value_objects import (
    ChatRole,
    ContentBlock,
    ContextBlock,
    EntityRef,
    PageContext,
    ReasoningBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from utils.async_executor import run_sync_in_executor


class SqliteConversationRepository:
    """Stores chat conversations and messages in operations.db."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    # -- async port ---------------------------------------------------------

    async def save_conversation(self, conversation: Conversation) -> None:
        await run_sync_in_executor(self._save_conversation, conversation)

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        return await run_sync_in_executor(self._get_conversation, conversation_id)

    async def list_conversations(self, limit: int) -> list[Conversation]:
        return await run_sync_in_executor(self._list_conversations, limit)

    async def delete_conversation(self, conversation_id: str) -> bool:
        return await run_sync_in_executor(self._delete_conversation, conversation_id)

    async def add_message(self, message: ChatMessage) -> None:
        await run_sync_in_executor(self._add_message, message)

    async def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        return await run_sync_in_executor(self._list_messages, conversation_id)

    # -- sync implementation ------------------------------------------------

    def _save_conversation(self, conversation: Conversation) -> None:
        with self._session_factory() as session:
            session.merge(
                ChatConversation(
                    id=conversation.id,
                    title=conversation.title,
                    model=conversation.model,
                    created_at=conversation.created_at.isoformat(),
                    updated_at=conversation.updated_at.isoformat(),
                )
            )
            session.commit()

    def _get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        with self._session_factory() as session:
            row = session.get(ChatConversation, str(conversation_id))
            return _to_conversation(row) if row is not None else None

    def _list_conversations(self, limit: int) -> list[Conversation]:
        with self._session_factory() as session:
            rows = (
                session.query(ChatConversation)
                .order_by(ChatConversation.updated_at.desc())
                .limit(limit)
                .all()
            )
            return [_to_conversation(row) for row in rows]

    def _delete_conversation(self, conversation_id: str) -> bool:
        with self._session_factory() as session:
            # Messages go with it through the ON DELETE CASCADE foreign key.
            deleted = (
                session.query(ChatConversation)
                .filter(ChatConversation.id == str(conversation_id))
                .delete()
            )
            session.commit()
            return deleted > 0

    def _add_message(self, message: ChatMessage) -> None:
        with self._session_factory() as session:
            session.add(
                ChatMessageRecord(
                    id=message.id,
                    conversation_id=message.conversation_id,
                    seq=message.seq,
                    role=message.role.value,
                    blocks=[block_to_dict(b) for b in message.blocks],
                    page_context=(
                        _page_context_to_dict(message.page_context)
                        if message.page_context is not None
                        else None
                    ),
                    tokens_in=message.tokens_in,
                    tokens_out=message.tokens_out,
                    created_at=message.created_at.isoformat(),
                )
            )
            session.commit()

    def _list_messages(self, conversation_id: str) -> list[ChatMessage]:
        with self._session_factory() as session:
            rows = (
                session.query(ChatMessageRecord)
                .filter(ChatMessageRecord.conversation_id == str(conversation_id))
                .order_by(ChatMessageRecord.seq)
                .all()
            )
            return [_to_message(row) for row in rows]


# ============================================================================
# Mapping
# ============================================================================


def block_to_dict(block: ContentBlock) -> dict[str, Any]:
    """Serialize a content block to a JSON-compatible dict."""
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, ContextBlock):
        return {"type": "context", "text": block.text}
    if isinstance(block, ToolUseBlock):
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": dict(block.input)}
    if isinstance(block, ToolResultBlock):
        return {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "content": block.content,
            "is_error": block.is_error,
            "summary": block.summary,
            "entities": [{"id": e.id, "kind": e.kind, "title": e.title} for e in block.entities],
        }
    if isinstance(block, ReasoningBlock):
        return {"type": "reasoning", "provider": block.provider, "data": dict(block.data)}
    raise TypeError(f"Unknown content block: {type(block).__name__}")


def block_from_dict(data: dict[str, Any]) -> ContentBlock:
    """Deserialize a content block stored by block_to_dict."""
    kind = data["type"]
    if kind == "text":
        return TextBlock(text=data["text"])
    if kind == "context":
        return ContextBlock(text=data["text"])
    if kind == "tool_use":
        return ToolUseBlock(id=data["id"], name=data["name"], input=data["input"])
    if kind == "tool_result":
        return ToolResultBlock(
            tool_use_id=data["tool_use_id"],
            content=data["content"],
            is_error=data.get("is_error", False),
            summary=data.get("summary", ""),
            entities=tuple(EntityRef(**e) for e in data.get("entities", [])),
        )
    if kind == "reasoning":
        return ReasoningBlock(provider=data["provider"], data=data["data"])
    raise ValueError(f"Unknown stored content block type: {kind!r}")


def _page_context_to_dict(page_context: PageContext) -> dict[str, Any]:
    return {
        "route": page_context.route,
        "entity_kind": page_context.entity_kind,
        "entity_id": page_context.entity_id,
    }


def _to_conversation(row: ChatConversation) -> Conversation:
    return Conversation(
        id=row.id,
        title=row.title,
        model=row.model,
        created_at=datetime.fromisoformat(row.created_at),
        updated_at=datetime.fromisoformat(row.updated_at),
    )


def _to_message(row: ChatMessageRecord) -> ChatMessage:
    return ChatMessage(
        id=row.id,
        conversation_id=row.conversation_id,
        seq=row.seq,
        role=ChatRole(row.role),
        blocks=tuple(block_from_dict(b) for b in row.blocks),
        page_context=PageContext(**row.page_context) if row.page_context else None,
        tokens_in=row.tokens_in,
        tokens_out=row.tokens_out,
        created_at=datetime.fromisoformat(row.created_at),
    )
