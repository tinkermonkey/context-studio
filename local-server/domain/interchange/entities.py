"""
Domain entities for the Data Interchange bounded context.

Represents import/export operations and their tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .value_objects import SerializationScope, ResolutionKind, MatchKind


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
        resolutions: List of applied conflict resolutions
        affected_entity_ids: Denormalized list of entity IDs affected by this import
        status: Current status (pending, committed, failed, rolled_back)
    """

    id: str
    created_at: datetime
    created_by: str | None
    format: str
    source_uri: str | None
    source_hash: str
    scope: SerializationScope
    resolutions: list[ResolutionRecord] = field(default_factory=list)
    affected_entity_ids: list[str] = field(default_factory=list)
    status: ImportRunStatus = ImportRunStatus.PENDING

    def mark_committed(self) -> None:
        """
        Mark this import run as committed.

        Raises:
            ValueError: If the run is already in a terminal state
        """
        if self.status in (ImportRunStatus.COMMITTED, ImportRunStatus.ROLLED_BACK):
            raise ValueError(
                f"Cannot transition {self.status} to COMMITTED (terminal state)"
            )
        self.status = ImportRunStatus.COMMITTED

    def mark_failed(self) -> None:
        """
        Mark this import run as failed.

        Raises:
            ValueError: If the run is already in a terminal state
        """
        if self.status in (ImportRunStatus.COMMITTED, ImportRunStatus.ROLLED_BACK):
            raise ValueError(
                f"Cannot transition {self.status} to FAILED (terminal state)"
            )
        self.status = ImportRunStatus.FAILED

    def mark_rolled_back(self) -> None:
        """
        Mark this import run as rolled back.

        Raises:
            ValueError: If the run is already in a terminal state
        """
        if self.status == ImportRunStatus.COMMITTED:
            raise ValueError("Cannot roll back a COMMITTED run")
        self.status = ImportRunStatus.ROLLED_BACK

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
        """
        self.resolutions.append(
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
        """
        if entity_id not in self.affected_entity_ids:
            self.affected_entity_ids.append(entity_id)
