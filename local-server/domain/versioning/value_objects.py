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


class EntityVersionState(str, Enum):
    """Valid states for an entity version."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class SyncDirection(str, Enum):
    """Direction of a synchronization operation."""

    PUSH = "push"
    PULL = "pull"


class MergeStrategy(str, Enum):
    """Strategy for resolving conflicts during merge."""

    LAST_WRITE_WINS = "last_write_wins"
    BASE_VALUE_WINS = "base_value_wins"
    MERGE_BOTH = "merge_both"
    MANUAL = "manual"


@dataclass(frozen=True)
class SyncStatus:
    """Status of remote synchronization."""

    last_pushed_at: Optional[datetime]
    last_pulled_at: Optional[datetime]
    unprocessed_count: int
    is_configured: bool
    is_degraded: bool = False


@dataclass(frozen=True)
class SyncResult:
    """Result of a sync operation.

    Attributes:
        pushed: Count of successfully pushed events
        pulled: Count of successfully pulled events
        errors: Tuple of error messages from failed operations
        pushed_event_ids: Specific IDs of events that were successfully pushed
        started_at: Timestamp when the sync operation started
        completed_at: Timestamp when the sync operation completed

    Invariants:
        - pushed >= 0
        - pulled >= 0
        - If started_at and completed_at are both set, completed_at >= started_at
        - If pushed_event_ids is set, len(pushed_event_ids) == pushed
    """

    pushed: int
    pulled: int
    errors: tuple[str, ...] = field(default_factory=tuple)
    pushed_event_ids: Optional[tuple[str, ...]] = None  # Specific event IDs that were successfully pushed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if self.pushed < 0:
            raise ValueError(f"pushed count cannot be negative: {self.pushed}")
        if self.pulled < 0:
            raise ValueError(f"pulled count cannot be negative: {self.pulled}")
        if self.started_at is not None and self.completed_at is not None:
            if self.completed_at < self.started_at:
                raise ValueError(
                    f"completed_at ({self.completed_at}) cannot be before "
                    f"started_at ({self.started_at})"
                )
        if self.pushed_event_ids is not None:
            if len(self.pushed_event_ids) != self.pushed:
                raise ValueError(
                    f"pushed_event_ids length ({len(self.pushed_event_ids)}) "
                    f"must equal pushed count ({self.pushed})"
                )


@dataclass(frozen=True)
class ChangeHistoryResult:
    """Paginated result of a change history query.

    Attributes:
        events: Tuple of change events matching the query
        total: Total count of all matching events (without limit applied)
    """

    events: tuple[ChangeEvent, ...]
    total: int
