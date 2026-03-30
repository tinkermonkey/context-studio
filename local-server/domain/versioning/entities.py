"""
Domain entities for the Version Control & Collaboration bounded context.

These dataclasses represent the core concepts of version control:
change events, entity versions, changesets, proposals, and conflicts.
All entities are mutable but enforce invariants through their methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .value_objects import ChangeState


@dataclass
class ChangeEvent:
    """
    An atomic record of a change to an entity.

    Represents a single operation (create, update, delete) on an entity,
    with before/after state snapshots and optional metadata about who
    made the change and why.

    Attributes:
        id: Unique identifier (UUID as string)
        entity_id: ID of the entity that changed
        entity_type: Type of entity (e.g., 'class', 'taxonomy')
        operation: Type of operation ('create', 'update', 'delete')
        new_state: JSON snapshot of entity after change
        timestamp: When the change occurred
        previous_state: JSON snapshot of entity before change (for updates)
        user_id: Optional ID of user who made the change
        change_reason: Optional explanation of the change
        changeset_id: Optional ID of a changeset this event belongs to
        processed: Whether this change has been synchronized to remote
    """

    id: str
    entity_id: str
    entity_type: str
    operation: str
    new_state: dict
    timestamp: datetime
    previous_state: Optional[dict] = None
    user_id: Optional[str] = None
    change_reason: Optional[str] = None
    changeset_id: Optional[str] = None
    processed: bool = False


@dataclass
class EntityVersion:
    """
    A point-in-time snapshot of an entity's state.

    Each version represents a distinct state of an entity in its history.
    Versions form a chain where each may reference its parent version.

    Attributes:
        entity_id: ID of the entity
        version: Version number (increments with each change)
        state: State code or label (e.g., 'active', 'archived')
        snapshot: Full JSON snapshot of entity at this version
        created_at: When this version was created
        parent_version: Version number of parent (for tracking lineage)
    """

    entity_id: str
    version: int
    state: str
    snapshot: dict
    created_at: datetime
    parent_version: Optional[int] = None


@dataclass
class Changeset:
    """
    A grouped set of related change events (a transaction).

    Changesets progress through a workflow: working → staged → proposed → approved → merged.
    They represent a logical unit of work that can be reviewed and applied as a whole.

    Attributes:
        id: Unique identifier (UUID as string)
        name: Human-readable name for the changeset
        state: Current state in the workflow (ChangeState enum)
        created_at: When the changeset was created
        updated_at: When the changeset was last modified
        description: Optional detailed description
        event_ids: List of change event IDs in this changeset
    """

    id: str
    name: str
    state: ChangeState
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    event_ids: list[str] = field(default_factory=list)

    def transition_to(self, new_state: ChangeState) -> None:
        """
        Transition the changeset to a new state.

        Enforces valid state transitions. Raises ChangesetStateError on invalid transitions.

        Args:
            new_state: The target state

        Raises:
            ChangesetStateError: If the transition is not allowed
        """
        from .exceptions import ChangesetStateError

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
    """
    A formal request to merge a changeset.

    Proposals allow review and discussion before changes are applied.
    They track submission time, reviewer comments, and approval status.

    Attributes:
        id: Unique identifier (UUID as string)
        changeset_id: ID of the changeset being proposed
        state: Current state ('open', 'approved', 'rejected', 'merged')
        submitted_at: When the proposal was submitted
        reviewed_at: When the proposal was reviewed (None if not reviewed)
        reviewer_notes: Optional notes from the reviewer
    """

    id: str
    changeset_id: str
    state: str
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None


@dataclass
class Conflict:
    """
    A conflicting change to a single field.

    Represents a situation where two versions of the same entity
    have conflicting values for the same field.

    Attributes:
        entity_id: ID of the entity with the conflict
        field_name: Name of the conflicting field
        base_value: The original value before divergence
        incoming_value: The new value being proposed
        resolved_value: The chosen resolution value (None if unresolved)
        is_resolved: Whether this conflict has been resolved
    """

    entity_id: str
    field_name: str
    base_value: object
    incoming_value: object
    resolved_value: object = None
    is_resolved: bool = False


@dataclass
class ConflictReport:
    """
    Summary of conflicts found during a merge operation.

    Tracks all conflicts in a proposal and provides
    convenience properties for checking resolution status.

    Attributes:
        proposal_id: ID of the proposal with conflicts
        conflicts: List of Conflict objects
    """

    proposal_id: str
    conflicts: list[Conflict] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """Whether this report contains any conflicts."""
        return len(self.conflicts) > 0

    @property
    def all_resolved(self) -> bool:
        """Whether all conflicts have been resolved."""
        return all(c.is_resolved for c in self.conflicts)


@dataclass
class MergeResult:
    """
    Result summary of a successful merge operation.

    Attributes:
        proposal_id: ID of the proposal that was merged
        merged_at: When the merge completed
        events_applied: Number of change events applied
        conflicts_resolved: Number of conflicts that were resolved
    """

    proposal_id: str
    merged_at: datetime
    events_applied: int
    conflicts_resolved: int
