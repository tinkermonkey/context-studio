"""
Domain entities for the versioning bounded context.

Entities represent change tracking, entity versioning, conflict detection,
and conflict resolution. They import only from Python stdlib.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from enum import Enum
from typing import List

from domain.versioning.enums import ChangeType


class ChangeState(str, Enum):
    """
    Enumeration of states a change event can be in.

    Attributes:
        PENDING: Change has not been synced to remote.
        SYNCED: Change has been synced to remote.
        CONFLICT: Change conflicts with remote version.
    """

    PENDING = "pending"
    SYNCED = "synced"
    CONFLICT = "conflict"


@dataclass
class ChangeEvent:
    """
    Represents a recorded change to an entity.

    Attributes:
        id: Unique identifier for this change event.
        entity_type: Type of entity that was changed (e.g., "Class", "Relationship").
        entity_id: ID of the entity that was changed.
        change_type: Type of change (created, updated, deleted).
        payload: The changed data or details about the change (immutable).
        occurred_at: ISO 8601 timestamp of when the change occurred.
        state: Current sync state of the change.
    """

    id: str
    entity_type: str
    entity_id: str
    change_type: ChangeType
    payload: types.MappingProxyType
    occurred_at: str
    state: ChangeState = ChangeState.PENDING

    def __post_init__(self) -> None:
        """Validate change event invariants."""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("ChangeEvent id must be a non-empty string")
        if not self.entity_type or not isinstance(self.entity_type, str):
            raise ValueError("ChangeEvent entity_type must be a non-empty string")
        if not self.entity_id or not isinstance(self.entity_id, str):
            raise ValueError("ChangeEvent entity_id must be a non-empty string")
        if not isinstance(self.change_type, ChangeType):
            raise TypeError(
                f"change_type must be a ChangeType enum, got {type(self.change_type).__name__}"
            )
        if not isinstance(self.payload, types.MappingProxyType):
            raise TypeError("payload must be a MappingProxyType (immutable mapping)")
        if not self.occurred_at or not isinstance(self.occurred_at, str):
            raise ValueError("ChangeEvent occurred_at must be a non-empty timestamp string")
        if not isinstance(self.state, ChangeState):
            raise TypeError(
                f"state must be a ChangeState enum, got {type(self.state).__name__}"
            )


@dataclass
class EntityVersion:
    """
    Represents a snapshot of an entity at a point in time.

    Attributes:
        entity_id: ID of the entity being versioned.
        version: Version number (monotonically increasing).
        snapshot: Complete snapshot of the entity's state (immutable).
        recorded_at: ISO 8601 timestamp when this version was recorded.
    """

    entity_id: str
    version: int
    snapshot: types.MappingProxyType
    recorded_at: str

    def __post_init__(self) -> None:
        """Validate entity version invariants."""
        if not self.entity_id or not isinstance(self.entity_id, str):
            raise ValueError("EntityVersion entity_id must be a non-empty string")
        if not isinstance(self.version, int) or self.version <= 0:
            raise ValueError("EntityVersion version must be a positive integer")
        if not isinstance(self.snapshot, types.MappingProxyType):
            raise TypeError("snapshot must be a MappingProxyType (immutable mapping)")
        if not self.recorded_at or not isinstance(self.recorded_at, str):
            raise ValueError("EntityVersion recorded_at must be a non-empty timestamp string")


@dataclass
class Conflict:
    """
    Represents a conflict between local and remote versions of an entity.

    Attributes:
        entity_id: ID of the entity with conflicting versions.
        local_version: The local version.
        remote_version: The remote version.
        conflict_fields: Tuple of field names that differ between versions (immutable).
    """

    entity_id: str
    local_version: EntityVersion
    remote_version: EntityVersion
    conflict_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate conflict invariants."""
        if not self.entity_id or not isinstance(self.entity_id, str):
            raise ValueError("Conflict entity_id must be a non-empty string")
        if not isinstance(self.local_version, EntityVersion):
            raise TypeError("local_version must be an EntityVersion instance")
        if not isinstance(self.remote_version, EntityVersion):
            raise TypeError("remote_version must be an EntityVersion instance")
        if not isinstance(self.conflict_fields, tuple):
            raise TypeError("conflict_fields must be a tuple of strings (immutable)")
        for field_name in self.conflict_fields:
            if not isinstance(field_name, str):
                raise TypeError(f"All conflict_fields must be strings, got {type(field_name).__name__}")


@dataclass
class ConflictReport:
    """
    Represents a report of conflicts detected during a sync operation.

    Attributes:
        sync_id: ID of the sync operation that detected these conflicts.
        conflicts: Tuple of individual conflicts (immutable).
        generated_at: ISO 8601 timestamp when the report was generated.
    """

    sync_id: str
    conflicts: tuple[Conflict, ...] = ()
    generated_at: str = ""

    def __post_init__(self) -> None:
        """Validate conflict report invariants."""
        if not self.sync_id or not isinstance(self.sync_id, str):
            raise ValueError("ConflictReport sync_id must be a non-empty string")
        if not isinstance(self.conflicts, tuple):
            raise TypeError("conflicts must be a tuple of Conflict instances (immutable)")
        for conflict in self.conflicts:
            if not isinstance(conflict, Conflict):
                raise TypeError(f"All conflicts must be Conflict instances, got {type(conflict).__name__}")
        if not self.generated_at or not isinstance(self.generated_at, str):
            raise ValueError("ConflictReport generated_at must be a non-empty timestamp string")


@dataclass
class MergeResult:
    """
    Represents the results of a merge operation during sync.

    Attributes:
        sync_id: ID of the sync operation.
        merged_count: Number of entities successfully merged.
        conflict_count: Number of entities with unresolved conflicts.
        skipped_count: Number of entities skipped (e.g., already in sync).
    """

    sync_id: str
    merged_count: int
    conflict_count: int
    skipped_count: int

    def __post_init__(self) -> None:
        """Validate merge result invariants."""
        if not self.sync_id or not isinstance(self.sync_id, str):
            raise ValueError("MergeResult sync_id must be a non-empty string")
        if not isinstance(self.merged_count, int) or self.merged_count < 0:
            raise ValueError("MergeResult merged_count must be a non-negative integer")
        if not isinstance(self.conflict_count, int) or self.conflict_count < 0:
            raise ValueError("MergeResult conflict_count must be a non-negative integer")
        if not isinstance(self.skipped_count, int) or self.skipped_count < 0:
            raise ValueError("MergeResult skipped_count must be a non-negative integer")
