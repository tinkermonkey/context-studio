"""
Exceptions for the Chat bounded context.
"""

from __future__ import annotations

from typing import Optional


class ChatModelError(Exception):
    """
    A chat model request failed.

    Attributes:
        status_code: HTTP status of the failed request, if there was one
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConversationNotFoundError(Exception):
    """The requested conversation does not exist."""

    def __init__(self, conversation_id: str) -> None:
        super().__init__(f"Conversation not found: {conversation_id}")
        self.conversation_id = conversation_id
