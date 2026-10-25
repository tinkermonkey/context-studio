"""
SQLAlchemy ORM models for operations.db.
"""

from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

OperationsBase = declarative_base()  # type: ignore[valid-type]


class PipelineConfiguration(OperationsBase):  # type: ignore[valid-type,misc]
    """
    User-created pipeline configuration record.

    System configs are code-defined and live in the in-memory registry.
    User-created configs are persisted here and loaded into the registry at startup.
    """

    __tablename__ = "pipeline_configurations"

    id: str = Column(String, primary_key=True)  # type: ignore[assignment]
    config_ref: str = Column(String, nullable=False, index=True)  # type: ignore[assignment]
    pipeline_type: str = Column(String, nullable=False, index=True)  # type: ignore[assignment]
    implementation_id: str = Column(String, nullable=False)  # type: ignore[assignment]
    name: str = Column(String, nullable=False)  # type: ignore[assignment]
    description: Optional[str] = Column(Text)  # type: ignore[assignment]
    provider: str = Column(String, nullable=False)  # type: ignore[assignment]
    model: str = Column(String, nullable=False)  # type: ignore[assignment]
    system_prompt: Optional[str] = Column(Text)  # type: ignore[assignment]
    user_prompt_template: str = Column(Text, nullable=False)  # type: ignore[assignment]
    temperature: float = Column(Float, nullable=False, default=0.4)  # type: ignore[assignment]
    max_tokens: int = Column(Integer, nullable=False, default=800)  # type: ignore[assignment]
    top_p: float = Column(Float, nullable=False, default=0.9)  # type: ignore[assignment]
    enabled: bool = Column(Boolean, nullable=False, default=True)  # type: ignore[assignment]
    version: int = Column(Integer, nullable=False, default=1)  # type: ignore[assignment]
    deleted_at: Optional[str] = Column(String)  # type: ignore[assignment]
    created_at: str = Column(String, nullable=False)  # type: ignore[assignment]
    updated_at: str = Column(String, nullable=False)  # type: ignore[assignment]


class ChatConversation(OperationsBase):  # type: ignore[valid-type,misc]
    """A conversation with the chat assistant."""

    __tablename__ = "chat_conversations"

    id: str = Column(String, primary_key=True)  # type: ignore[assignment]
    title: str = Column(String, nullable=False)  # type: ignore[assignment]
    model: str = Column(String, nullable=False)  # type: ignore[assignment]
    created_at: str = Column(String, nullable=False)  # type: ignore[assignment]
    updated_at: str = Column(String, nullable=False, index=True)  # type: ignore[assignment]


class ChatMessageRecord(OperationsBase):  # type: ignore[valid-type,misc]
    """
    One message in a chat conversation.

    `blocks` holds the message content as a JSON list of typed blocks (text,
    context, tool_use, tool_result, reasoning); `page_context` the page the user
    was viewing, for user messages.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (UniqueConstraint("conversation_id", "seq", name="uk_chat_message_seq"),)

    id: str = Column(String, primary_key=True)  # type: ignore[assignment]
    conversation_id: str = Column(  # type: ignore[assignment]
        String,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    role: str = Column(String, nullable=False)  # type: ignore[assignment]
    blocks: list = Column(JSON, nullable=False)  # type: ignore[assignment]
    page_context: Optional[dict] = Column(JSON)  # type: ignore[assignment]
    tokens_in: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    tokens_out: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    created_at: str = Column(String, nullable=False)  # type: ignore[assignment]
