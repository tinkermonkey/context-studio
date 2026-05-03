"""
Value objects for the Data Interchange bounded context.

These are immutable dataclasses representing concepts without identity:
SerializationScope, ImportConflict, and ImportPlan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
        default_resolution: Derived from match_kind per cascade table
        available_resolutions: List of possible resolutions
    """

    match_kind: MatchKind
    incoming: dict[str, Any]
    existing: str | None
    default_resolution: ResolutionKind
    available_resolutions: tuple[ResolutionKind, ...]

    @staticmethod
    def derive_default_resolution(match_kind: MatchKind) -> ResolutionKind:
        """
        Derive the default resolution based on match kind.

        Args:
            match_kind: The type of match found

        Returns:
            The default resolution strategy for this match kind
        """
        if match_kind == MatchKind.EXTERNAL_REFERENCE:
            return ResolutionKind.MERGE
        else:
            return ResolutionKind.SKIP


@dataclass
class ImportPlan:
    """
    Describes what an import would do (result of dry-run).

    Attributes:
        conflicts: List of detected conflicts
        new_entity_count: Number of new entities to be created
        import_run_id: Prospective ImportRun ID (populated on dry_run=False)
        warnings: List of warning messages
        source_hash: SHA256 hash of imported bytes
        scope: The scope being imported
    """

    conflicts: list[ImportConflict]
    new_entity_count: int
    import_run_id: str | None
    warnings: list[str] = field(default_factory=list)
    source_hash: str | None = None
    scope: SerializationScope | None = None
