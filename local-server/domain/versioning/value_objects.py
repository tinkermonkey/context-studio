"""Value objects and enums for versioning domain."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ChangeState(str, Enum):
    """Valid states for a changeset."""

    WORKING = "working"
    STAGED = "staged"
    PROPOSED = "proposed"
    APPROVED = "approved"
    MERGED = "merged"


@dataclass(frozen=True)
class SyncStatus:
    """Status of remote synchronization."""

    last_pushed_at: Optional[str]
    last_pulled_at: Optional[str]
    unprocessed_count: int
    is_configured: bool


@dataclass(frozen=True)
class SyncResult:
    """Result of a sync operation."""

    pushed: int
    pulled: int
    errors: list[str]
