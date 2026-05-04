"""
Domain entities for the Data Interchange bounded context.

Represents import/export operations and their tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .value_objects import SerializationScope, ResolutionKind, MatchKind, SerializationFormat


class ImportRunStatus(str, Enum):
    """Status of an import run."""

    PENDING = "pending"
    COMMITTED = "committed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ResolutionRecord:
    """
    A recorded resolution for a specific conflict in an import run.

    Attributes:
        match_kind: Type of match that was resolved
        entity_id: ID of the entity involved
        resolution_chosen: The resolution strategy applied
    """

    match_kind: MatchKind
    entity_id: str
    resolution_chosen: ResolutionKind


@dataclass
class ImportRun:
    """
    First-class domain entity representing an import operation.

    Tracks the import operation from inception through completion, including
    scope, resolutions applied, affected entities, and status transitions.

    Attributes:
        id: Unique identifier (UUID as string)
        created_at: Timestamp of creation
        created_by: Optional ID of user who initiated the import
        format: Format of the imported file (skos, owl, graphml)
        source_uri: Optional URI/filename of the import source
        source_hash: SHA256 hash of the imported bytes
        scope: Describes what was imported (whole_graph, taxonomy, scheme, entity_set)
        resolutions: Immutable view of applied conflict resolutions
        affected_entity_ids: Immutable view of entity IDs affected by this import
        status: Current status (pending, committed, failed, rolled_back)
    """

    id: str
    created_at: datetime
    created_by: str | None
    format: SerializationFormat
    source_uri: str | None
    source_hash: str
    scope: SerializationScope
    status: ImportRunStatus = ImportRunStatus.PENDING
    _resolutions: list[ResolutionRecord] = field(default_factory=list, init=False, repr=False)
    _affected_entity_ids: list[str] = field(default_factory=list, init=False, repr=False)

    def __init__(
        self,
        id: str,
        created_at: datetime,
        created_by: str | None,
        format: SerializationFormat,
        source_uri: str | None,
        source_hash: str,
        scope: SerializationScope,
        status: ImportRunStatus = ImportRunStatus.PENDING,
        resolutions: list[ResolutionRecord] | None = None,
        affected_entity_ids: list[str] | None = None,
    ) -> None:
        """Initialize ImportRun with immutable list storage."""
        self.id = id
        self.created_at = created_at
        self.created_by = created_by
        self.format = format
        self.source_uri = source_uri
        self.source_hash = source_hash
        self.scope = scope
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "_resolutions", list(resolutions or []))
        object.__setattr__(self, "_affected_entity_ids", list(affected_entity_ids or []))

    @property
    def resolutions(self) -> tuple[ResolutionRecord, ...]:
        """
        Immutable view of applied conflict resolutions.

        To add a resolution, use add_resolution() method instead.
        """
        return tuple(self._resolutions)

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        """
        Immutable view of entity IDs affected by this import.

        To add an affected entity, use add_affected_entity() method instead.
        """
        return tuple(self._affected_entity_ids)

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Prevent direct assignment to status field after initialization.

        State machine transitions must use mark_committed(), mark_failed(),
        or mark_rolled_back() methods to ensure proper invariants.
        """
        if name == "status" and "status" in self.__dict__:
            raise AttributeError(
                "Cannot directly assign to 'status'. Use mark_committed(), "
                "mark_failed(), or mark_rolled_back() methods instead."
            )
        object.__setattr__(self, name, value)

    def mark_committed(self) -> None:
        """
        Mark this import run as committed.

        Raises:
            ValueError: If the run is already in a terminal state
        """
        if self.status in (
            ImportRunStatus.COMMITTED,
            ImportRunStatus.FAILED,
            ImportRunStatus.ROLLED_BACK,
        ):
            raise ValueError(
                f"Cannot transition {self.status} to COMMITTED (terminal state)"
            )
        object.__setattr__(self, "status", ImportRunStatus.COMMITTED)

    def mark_failed(self) -> None:
        """
        Mark this import run as failed.

        Raises:
            ValueError: If the run is already in a terminal state
        """
        if self.status in (
            ImportRunStatus.COMMITTED,
            ImportRunStatus.FAILED,
            ImportRunStatus.ROLLED_BACK,
        ):
            raise ValueError(
                f"Cannot transition {self.status} to FAILED (terminal state)"
            )
        object.__setattr__(self, "status", ImportRunStatus.FAILED)

    def mark_rolled_back(self) -> None:
        """
        Mark this import run as rolled back.

        Raises:
            ValueError: If the run is already in a terminal state
        """
        if self.status in (
            ImportRunStatus.COMMITTED,
            ImportRunStatus.FAILED,
            ImportRunStatus.ROLLED_BACK,
        ):
            raise ValueError(
                f"Cannot transition {self.status} to ROLLED_BACK (terminal state)"
            )
        object.__setattr__(self, "status", ImportRunStatus.ROLLED_BACK)

    def add_resolution(
        self,
        match_kind: MatchKind,
        entity_id: str,
        resolution_chosen: ResolutionKind,
    ) -> None:
        """
        Record a resolution for this import run.

        Args:
            match_kind: Type of match that was resolved
            entity_id: ID of the entity involved
            resolution_chosen: The resolution strategy applied

        Raises:
            ValueError: If the run is in a terminal state
        """
        if self.status in (
            ImportRunStatus.COMMITTED,
            ImportRunStatus.FAILED,
            ImportRunStatus.ROLLED_BACK,
        ):
            raise ValueError(
                f"Cannot add resolution to {self.status} import run (terminal state)"
            )
        self._resolutions.append(
            ResolutionRecord(
                match_kind=match_kind,
                entity_id=entity_id,
                resolution_chosen=resolution_chosen,
            )
        )

    def add_affected_entity(self, entity_id: str) -> None:
        """
        Record an entity affected by this import.

        Args:
            entity_id: ID of the affected entity

        Raises:
            ValueError: If the run is in a terminal state
        """
        if self.status in (
            ImportRunStatus.COMMITTED,
            ImportRunStatus.FAILED,
            ImportRunStatus.ROLLED_BACK,
        ):
            raise ValueError(
                f"Cannot add affected entity to {self.status} import run (terminal state)"
            )
        if entity_id not in tuple(self._affected_entity_ids):
            self._affected_entity_ids.append(entity_id)
