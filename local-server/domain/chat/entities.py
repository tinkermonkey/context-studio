"""
Domain entities for the Chat bounded context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from domain.chat.value_objects import ChatRole, ContentBlock, PageContext


@dataclass
class ChatMessage:
    """
    One message in a conversation.

    Attributes:
        id: Unique message identifier
        conversation_id: Conversation the message belongs to
        seq: Position of the message in the conversation (0-based)
        role: Who wrote the message; tool results travel in user messages
        blocks: Message content in order
        page_context: Page the user was viewing (user messages only)
        tokens_in: Input tokens the model turn consumed (assistant messages only)
        tokens_out: Output tokens the model turn generated (assistant messages only)
        created_at: When the message was created
    """

    id: str
    conversation_id: str
    seq: int
    role: ChatRole
    blocks: tuple[ContentBlock, ...]
    page_context: Optional[PageContext] = None
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
