"""
Domain entities for the versioning bounded context.

Entities represent change tracking, entity versioning, conflict detection,
and conflict resolution. They import only from Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


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
        change_type: Type of change: "created", "updated", or "deleted".
        payload: The changed data or details about the change.
        occurred_at: ISO 8601 timestamp of when the change occurred.
        state: Current sync state of the change.
    """

    id: str
    entity_type: str
    entity_id: str
    change_type: str
    payload: dict
    occurred_at: str
    state: ChangeState = ChangeState.PENDING


@dataclass
class EntityVersion:
    """
    Represents a snapshot of an entity at a point in time.

    Attributes:
        entity_id: ID of the entity being versioned.
        version: Version number (monotonically increasing).
        snapshot: Complete snapshot of the entity's state.
        recorded_at: ISO 8601 timestamp when this version was recorded.
    """

    entity_id: str
    version: int
    snapshot: dict
    recorded_at: str


@dataclass
class Conflict:
    """
    Represents a conflict between local and remote versions of an entity.

    Attributes:
        entity_id: ID of the entity with conflicting versions.
        local_version: The local version.
        remote_version: The remote version.
        conflict_fields: List of field names that differ between versions.
    """

    entity_id: str
    local_version: EntityVersion
    remote_version: EntityVersion
    conflict_fields: List[str]


@dataclass
class ConflictReport:
    """
    Represents a report of conflicts detected during a sync operation.

    Attributes:
        sync_id: ID of the sync operation that detected these conflicts.
        conflicts: List of individual conflicts.
        generated_at: ISO 8601 timestamp when the report was generated.
    """

    sync_id: str
    conflicts: List[Conflict]
    generated_at: str


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
