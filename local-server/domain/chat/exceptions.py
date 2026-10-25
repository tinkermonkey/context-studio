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
