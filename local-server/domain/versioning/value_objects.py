"""
Value objects and enums for the Version Control & Collaboration domain.

These are immutable (frozen) dataclasses that represent concepts
without identity. They are used as components within domain entities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ChangeState(str, Enum):
    """Enumeration of changeset states in the versioning workflow."""

    WORKING = "working"
    STAGED = "staged"
    PROPOSED = "proposed"
    APPROVED = "approved"
    MERGED = "merged"


@dataclass(frozen=True)
class SyncStatus:
    """
    Snapshot of the current synchronization state.

    Attributes:
        last_pushed_at: ISO datetime string of last successful push, or None
        last_pulled_at: ISO datetime string of last successful pull, or None
        unprocessed_count: Number of unprocessed change events pending sync
        is_configured: Whether this workspace has a remote sync target configured
    """

    last_pushed_at: Optional[str]
    last_pulled_at: Optional[str]
    unprocessed_count: int
    is_configured: bool


@dataclass(frozen=True)
class SyncResult:
    """
    Result summary of a push or pull operation.

    Attributes:
        pushed: Number of events successfully pushed
        pulled: Number of events successfully pulled
        errors: List of error messages encountered (empty if successful)
    """

    pushed: int
    pulled: int
    errors: list[str]
