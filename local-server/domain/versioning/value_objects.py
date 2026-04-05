"""Value objects and enums for versioning domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from domain.versioning.entities import ChangeEvent


class ChangeState(str, Enum):
    """Valid states for a changeset."""

    WORKING = "working"
    STAGED = "staged"
    PROPOSED = "proposed"
    APPROVED = "approved"
    MERGED = "merged"


class ProposalState(str, Enum):
    """Valid states for a proposal."""

    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"


class ChangeOperation(str, Enum):
    """Types of operations on entities."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ConflictStatus(str, Enum):
    """Status of conflict resolution."""

    UNRESOLVED = "unresolved"
    RESOLVED_MANUAL = "resolved_manual"
    RESOLVED_AUTO = "resolved_auto"


@dataclass(frozen=True)
class SyncStatus:
    """Status of remote synchronization."""

    last_pushed_at: Optional[datetime]
    last_pulled_at: Optional[datetime]
    unprocessed_count: int
    is_configured: bool


@dataclass(frozen=True)
class SyncResult:
    """Result of a sync operation.

    Attributes:
        pushed: Count of successfully pushed events
        pulled: Count of successfully pulled events
        errors: Tuple of error messages from failed operations
        pushed_event_ids: Specific IDs of events that were successfully pushed
    """

    pushed: int
    pulled: int
    errors: tuple[str, ...] = field(default_factory=tuple)
    pushed_event_ids: Optional[tuple[str, ...]] = None  # Specific event IDs that were successfully pushed


@dataclass(frozen=True)
class ChangeHistoryResult:
    """Paginated result of a change history query.

    Attributes:
        events: List of change events matching the query
        total: Total count of all matching events (without limit applied)
    """

    events: list[ChangeEvent]
    total: int
