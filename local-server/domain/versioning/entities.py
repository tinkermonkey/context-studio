"""Domain entities for versioning context."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.versioning.value_objects import ChangeState, ProposalState, ChangeOperation, EntityVersionState


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
    state: EntityVersionState
    snapshot: dict
    created_at: datetime
    parent_version: Optional[int] = None


@dataclass
class Changeset:
    """Collection of change events proposed as a unit."""

    id: str
    name: str
    _state: ChangeState
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    event_ids: list[str] = field(default_factory=list)

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent direct assignment to _state after initialization.

        State can only be changed via transition_to() to enforce state machine validity.
        """
        if name == "_state" and hasattr(self, "_state"):
            raise AttributeError(
                "Cannot modify state directly. Use transition_to() to change state."
            )
        object.__setattr__(self, name, value)

    @property
    def state(self) -> ChangeState:
        """Get the current state. State can only be changed via transition_to()."""
        return self._state

    def transition_to(self, new_state: ChangeState) -> None:
        """Enforce valid state transitions; raises ChangesetStateError on invalid.

        Valid transitions:
        - WORKING → STAGED (prepare for review)
        - STAGED → PROPOSED (submit for approval)
        - PROPOSED → APPROVED (reviewer approves)
        - PROPOSED → WORKING (reviewer rejects)
        - APPROVED → MERGED (merge approved changes)
        """
        from domain.versioning.exceptions import ChangesetStateError

        valid: dict[ChangeState, set[ChangeState]] = {
            ChangeState.WORKING: {ChangeState.STAGED},
            ChangeState.STAGED: {ChangeState.PROPOSED},
            ChangeState.PROPOSED: {ChangeState.APPROVED, ChangeState.WORKING},
            ChangeState.APPROVED: {ChangeState.MERGED},
            ChangeState.MERGED: set(),
        }
        if new_state not in valid[self._state]:
            raise ChangesetStateError(
                f"Cannot transition Changeset from {self._state} to {new_state}"
            )
        object.__setattr__(self, "_state", new_state)


@dataclass
class Proposal:
    """Formal proposal to merge a changeset."""

    id: str
    changeset_id: str
    _state: ProposalState
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent direct assignment to _state after initialization.

        State can only be changed via transition_to() to enforce state machine validity.
        """
        if name == "_state" and hasattr(self, "_state"):
            raise AttributeError(
                "Cannot modify state directly. Use transition_to() to change state."
            )
        object.__setattr__(self, name, value)

    @property
    def state(self) -> ProposalState:
        """Get the current state. State can only be changed via transition_to()."""
        return self._state

    def transition_to(self, new_state: ProposalState) -> None:
        """Enforce valid state transitions; raises ProposalStateError on invalid."""
        from domain.versioning.exceptions import ProposalStateError

        valid: dict[ProposalState, set[ProposalState]] = {
            ProposalState.OPEN: {ProposalState.APPROVED, ProposalState.REJECTED},
            ProposalState.APPROVED: {ProposalState.MERGED, ProposalState.REJECTED},
            ProposalState.REJECTED: {ProposalState.OPEN},
            ProposalState.MERGED: set(),
        }
        if new_state not in valid[self._state]:
            raise ProposalStateError(
                f"Cannot transition Proposal from {self._state} to {new_state}"
            )
        object.__setattr__(self, "_state", new_state)


@dataclass
class Conflict:
    """A merge conflict on a single field."""

    entity_id: str
    field_name: str
    base_value: object
    incoming_value: object
    resolved_value: object = None

    @property
    def is_resolved(self) -> bool:
        """True if conflict is resolved (resolved_value is set)."""
        return self.resolved_value is not None


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
    changeset_id: str
    merged_at: datetime
    events_applied: int
    conflicts_resolved: int
