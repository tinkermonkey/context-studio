"""Domain entities for versioning context."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.versioning.value_objects import ChangeState, ProposalState, ChangeOperation


@dataclass
class ChangeEvent:
    """Record of a single change to an entity."""

    id: str
    entity_id: str
    entity_type: str
    operation: ChangeOperation
    new_state: dict
    timestamp: datetime
    previous_state: Optional[dict] = None
    user_id: Optional[str] = None
    change_reason: Optional[str] = None
    changeset_id: Optional[str] = None
    processed: bool = False


@dataclass
class EntityVersion:
    """Snapshot of an entity at a specific version."""

    entity_id: str
    version: int
    state: str
    snapshot: dict
    created_at: datetime
    parent_version: Optional[int] = None


@dataclass
class Changeset:
    """Collection of change events proposed as a unit."""

    id: str
    name: str
    state: ChangeState
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    event_ids: list[str] = field(default_factory=list)

    def transition_to(self, new_state: ChangeState) -> None:
        """Enforce valid state transitions; raises ChangesetStateError on invalid."""
        from domain.versioning.exceptions import ChangesetStateError

        valid: dict[ChangeState, set[ChangeState]] = {
            ChangeState.WORKING: {ChangeState.STAGED},
            ChangeState.STAGED: {ChangeState.PROPOSED, ChangeState.WORKING},
            ChangeState.PROPOSED: {ChangeState.APPROVED, ChangeState.WORKING},
            ChangeState.APPROVED: {ChangeState.MERGED},
            ChangeState.MERGED: set(),
        }
        if new_state not in valid[self.state]:
            raise ChangesetStateError(
                f"Cannot transition Changeset from {self.state} to {new_state}"
            )
        self.state = new_state


@dataclass
class Proposal:
    """Formal proposal to merge a changeset."""

    id: str
    changeset_id: str
    state: ProposalState
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    conflict_resolutions: dict[str, dict[str, str]] = field(default_factory=dict)

    def transition_to(self, new_state: ProposalState) -> None:
        """Enforce valid state transitions; raises ProposalStateError on invalid."""
        from domain.versioning.exceptions import ProposalStateError

        valid: dict[ProposalState, set[ProposalState]] = {
            ProposalState.OPEN: {ProposalState.APPROVED, ProposalState.REJECTED},
            ProposalState.APPROVED: {ProposalState.MERGED, ProposalState.REJECTED},
            ProposalState.REJECTED: {ProposalState.OPEN},
            ProposalState.MERGED: set(),
        }
        if new_state not in valid[self.state]:
            raise ProposalStateError(
                f"Cannot transition Proposal from {self.state} to {new_state}"
            )
        self.state = new_state


@dataclass
class Conflict:
    """A merge conflict on a single field."""

    entity_id: str
    field_name: str
    base_value: object
    incoming_value: object
    resolved_value: object = None
    is_resolved: bool = False


@dataclass
class ConflictReport:
    """Report of conflicts in a merge proposal."""

    proposal_id: str
    conflicts: list[Conflict] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """True if any conflicts are present."""
        return len(self.conflicts) > 0

    @property
    def all_resolved(self) -> bool:
        """True if all conflicts are resolved."""
        return all(c.is_resolved for c in self.conflicts)


@dataclass
class MergeResult:
    """Result of a successful merge."""

    proposal_id: str
    merged_at: datetime
    events_applied: int
    conflicts_resolved: int
