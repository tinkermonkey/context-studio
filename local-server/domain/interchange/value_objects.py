"""
Value objects for the Data Interchange bounded context.

These are immutable dataclasses representing concepts without identity:
SerializationScope, ImportConflict, ImportPlan, and ChangeEvent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ChangeOperation(str, Enum):
    """Types of operations on entities."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ResolutionKind(str, Enum):
    """Resolution strategy for import conflicts."""

    SKIP = "skip"
    OVERWRITE = "overwrite"
    MERGE = "merge"
    RENAME = "rename"
    ABORT = "abort"


class MatchKind(str, Enum):
    """Type of match found for an incoming entity."""

    EXTERNAL_REFERENCE = "external_reference"
    UUID = "uuid"
    TITLE = "title"


class SerializationScopeType(str, Enum):
    """Type of serialization scope."""

    WHOLE_GRAPH = "whole_graph"
    TAXONOMY = "taxonomy"
    SCHEME = "scheme"
    ENTITY_SET = "entity_set"


class SerializationFormat(str, Enum):
    """Supported serialization formats for import/export operations."""

    SKOS = "skos"
    OWL = "owl"
    GRAPHML = "graphml"


@dataclass(frozen=True)
class SerializationScope:
    """
    Describes what is serialized in an import/export operation.

    Discriminated union over scope types:
    - whole_graph: entire graph
    - taxonomy: single taxonomy (taxonomy_id required)
    - scheme: concept scheme with optional descendants (scheme_id required)
    - entity_set: specific entity IDs (entity_ids required)
    """

    scope_type: SerializationScopeType
    taxonomy_id: str | None = None
    scheme_id: str | None = None
    include_descendants: bool = False
    entity_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        """Validate scope invariants at construction time."""
        self.validate()

    def validate(self) -> None:
        """
        Validate scope invariants.

        Raises:
            ValueError: If the scope configuration is invalid
        """
        match self.scope_type:
            case SerializationScopeType.WHOLE_GRAPH:
                if self.taxonomy_id or self.scheme_id or self.entity_ids:
                    raise ValueError(
                        "WHOLE_GRAPH scope must not have taxonomy_id, scheme_id, or entity_ids"
                    )
            case SerializationScopeType.TAXONOMY:
                if not self.taxonomy_id:
                    raise ValueError("TAXONOMY scope requires taxonomy_id")
                if self.scheme_id or self.entity_ids:
                    raise ValueError(
                        "TAXONOMY scope must not have scheme_id or entity_ids"
                    )
            case SerializationScopeType.SCHEME:
                if not self.scheme_id:
                    raise ValueError("SCHEME scope requires scheme_id")
                if self.taxonomy_id or self.entity_ids:
                    raise ValueError(
                        "SCHEME scope must not have taxonomy_id or entity_ids"
                    )
            case SerializationScopeType.ENTITY_SET:
                if not self.entity_ids:
                    raise ValueError("ENTITY_SET scope requires entity_ids")
                if self.taxonomy_id or self.scheme_id:
                    raise ValueError(
                        "ENTITY_SET scope must not have taxonomy_id or scheme_id"
                    )


@dataclass(frozen=True)
class ImportConflict:
    """
    Represents a conflict detected during import dry-run.

    Attributes:
        match_kind: Type of match (external_reference, uuid, title)
        incoming: Serialized representation of the incoming entity
        existing: Reference to the existing entity (if matched)
        default_resolution: Derived from match_kind per cascade table (None means no default, user must choose)
        available_resolutions: List of possible resolutions
    """

    match_kind: MatchKind
    incoming: dict[str, Any]
    existing: str | None
    default_resolution: ResolutionKind | None
    available_resolutions: tuple[ResolutionKind, ...]

    def __post_init__(self) -> None:
        """Validate conflict invariants at construction time."""
        # If a default_resolution is specified, it must be in available_resolutions
        if self.default_resolution is not None and self.default_resolution not in self.available_resolutions:
            raise ValueError(
                f"default_resolution {self.default_resolution.value} must be in available_resolutions "
                f"{tuple(r.value for r in self.available_resolutions)}"
            )

    @staticmethod
    def derive_default_resolution(match_kind: MatchKind) -> ResolutionKind | None:
        """
        Derive the default resolution based on match kind.

        Per the spec cascade:
        - EXTERNAL_REFERENCE: automatically merge (clear consensus)
        - UUID: no default (user must choose)
        - TITLE: no default (user must choose)

        Args:
            match_kind: The type of match found

        Returns:
            The default resolution strategy for this match kind, or None if user must choose

        Raises:
            ValueError: If match_kind is unhandled (new MatchKind added without update)
        """
        match match_kind:
            case MatchKind.EXTERNAL_REFERENCE:
                return ResolutionKind.MERGE
            case MatchKind.UUID:
                return None
            case MatchKind.TITLE:
                return None
            case _:
                raise ValueError(f"Unhandled match kind: {match_kind}")


@dataclass(frozen=True)
class ImportPlan:
    """
    Describes what an import would do (result of dry-run).

    Immutable value object representing the plan outcome.

    Attributes:
        conflicts: Tuple of detected conflicts
        new_entity_count: Number of new entities to be created
        import_run_id: Prospective ImportRun ID (populated on dry_run=False)
        warnings: Tuple of warning messages
        source_hash: SHA256 hash of imported bytes
        scope: The scope being imported
    """

    conflicts: tuple[ImportConflict, ...]
    new_entity_count: int
    import_run_id: str | None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    source_hash: str | None = None
    scope: SerializationScope | None = None

    def __post_init__(self) -> None:
        """Validate plan invariants at construction time."""
        if self.new_entity_count < 0:
            raise ValueError(
                f"new_entity_count must be non-negative, got {self.new_entity_count}"
            )


@dataclass(frozen=True)
class ChangeEvent:
    """
    Represents a change event associated with a batch run.

    Immutable value object capturing the audit trail of changes made during
    an import or extraction operation.

    Attributes:
        id: Unique identifier for the change event
        timestamp: UTC timestamp of when the change occurred
        entity_id: ID of the entity that changed
        entity_type: Type of the entity (taxonomy, concept_scheme, class, etc.)
        operation: Operation performed (create, update, delete)
        new_state: JSON snapshot of entity after change
        previous_state: JSON snapshot of entity before change (optional, for updates)
        batch_run_id: ID of the batch run (import or extraction) that produced this change
    """

    id: str
    timestamp: datetime
    entity_id: str
    entity_type: str
    operation: ChangeOperation
    new_state: Optional[dict[str, Any]] = None
    previous_state: Optional[dict[str, Any]] = None
    batch_run_id: Optional[str] = None
