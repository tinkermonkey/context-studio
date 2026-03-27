"""
Domain events for the Ontology Management bounded context.

Events capture state changes in the ontology and are used for event sourcing,
notifications, and trigger-based workflows. All events are frozen dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for all domain events in the Ontology Management context.

    All events have an event ID, timestamp, and aggregate ID (the entity that changed).
    Subclasses add domain-specific fields that capture the details of what changed.

    Attributes:
        event_id: Unique identifier for this event (typically a UUID string)
        occurred_at: Timestamp of when the event occurred
        aggregate_id: UUID of the aggregate (entity) that changed
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    aggregate_id: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    _aggregate_id_field: ClassVar[str] = ""

    def __post_init__(self) -> None:
        """
        Auto-populate aggregate_id from the specified field and validate string fields.

        For subclasses that set _aggregate_id_field, this method copies the value
        from that field to aggregate_id before validation runs. Then validates that
        required string fields are not empty.

        Raises:
            ValueError: If any string field is empty or contains only whitespace
        """
        # Auto-populate aggregate_id from subclass field if configured
        if self._aggregate_id_field and not self.aggregate_id:
            object.__setattr__(self, "aggregate_id", getattr(self, self._aggregate_id_field))

        # Validate that all string fields (including aggregate_id) are non-empty
        for field_name, _ in self.__dataclass_fields__.items():
            # Skip internal class variable fields
            if field_name.startswith("_"):
                continue
            v = getattr(self, field_name)
            # Only validate string fields; skip datetime and other types
            if isinstance(v, str) and not v.strip():
                raise ValueError(f"Event field '{field_name}' cannot be empty")


@dataclass(frozen=True)
class TaxonomyCreated(DomainEvent):
    """
    Event emitted when a new taxonomy is created.

    Attributes:
        taxonomy_id: ID of the created taxonomy
        title: Title of the taxonomy
    """

    _aggregate_id_field: ClassVar[str] = "taxonomy_id"
    taxonomy_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class SchemeCreated(DomainEvent):
    """
    Event emitted when a new concept scheme is created.

    Attributes:
        concept_scheme_id: ID of the created concept scheme
        title: Title of the concept scheme
        taxonomy_id: ID of the parent taxonomy
    """

    _aggregate_id_field: ClassVar[str] = "concept_scheme_id"
    concept_scheme_id: str = ""
    title: str = ""
    taxonomy_id: str = ""


@dataclass(frozen=True)
class ClassCreated(DomainEvent):
    """
    Event emitted when a new class is created.

    Attributes:
        class_id: ID of the created class
        title: Title of the class
        concept_scheme_id: ID of the parent concept scheme
        taxonomy_id: ID of the parent taxonomy
    """

    _aggregate_id_field: ClassVar[str] = "class_id"
    class_id: str = ""
    title: str = ""
    concept_scheme_id: str = ""
    taxonomy_id: str = ""


@dataclass(frozen=True)
class ClassUpdated(DomainEvent):
    """
    Event emitted when a class is updated.

    Attributes:
        class_id: ID of the updated class
        changed_fields: Tuple of field names that changed
        old_values: Dictionary of field names to their previous values
        new_values: Dictionary of field names to their new values
    """

    _aggregate_id_field: ClassVar[str] = "class_id"
    class_id: str = ""
    changed_fields: tuple[str, ...] = field(default_factory=tuple)
    old_values: dict[str, str | None] = field(default_factory=dict)
    new_values: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class ClassDeleted(DomainEvent):
    """
    Event emitted when a class is deleted.

    Attributes:
        class_id: ID of the deleted class
        title: Title of the deleted class
    """

    _aggregate_id_field: ClassVar[str] = "class_id"
    class_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class ClassMoved(DomainEvent):
    """
    Event emitted when a class is moved in the hierarchy.

    Attributes:
        class_id: ID of the moved class
        old_parent_id: ID of the old parent class (None if was root)
        new_parent_id: ID of the new parent class (None if now root)
    """

    _aggregate_id_field: ClassVar[str] = "class_id"
    class_id: str = ""
    old_parent_id: str | None = None
    new_parent_id: str | None = None


@dataclass(frozen=True)
class RelationshipCreated(DomainEvent):
    """
    Event emitted when a new relationship is created.

    Attributes:
        relationship_id: ID of the created relationship
        source_id: ID of the source entity
        target_id: ID of the target entity
        property_definition_id: ID of the property definition for this relationship type
    """

    _aggregate_id_field: ClassVar[str] = "relationship_id"
    relationship_id: str = ""
    source_id: str = ""
    target_id: str = ""
    property_definition_id: str = ""


@dataclass(frozen=True)
class RelationshipDeleted(DomainEvent):
    """
    Event emitted when a relationship is deleted.

    Attributes:
        relationship_id: ID of the deleted relationship
        source_id: ID of the source entity
        target_id: ID of the target entity
        property_definition_id: ID of the property definition for this relationship type
    """

    _aggregate_id_field: ClassVar[str] = "relationship_id"
    relationship_id: str = ""
    source_id: str = ""
    target_id: str = ""
    property_definition_id: str = ""


@dataclass(frozen=True)
class PropertyDefinitionCreated(DomainEvent):
    """
    Event emitted when a new property definition is created.

    Attributes:
        property_id: ID of the created property definition
        identifier: Identifier/name of the property definition
        title: Title of the property definition
    """

    _aggregate_id_field: ClassVar[str] = "property_id"
    property_id: str = ""
    identifier: str = ""
    title: str = ""


@dataclass(frozen=True)
class TaxonomyUpdated(DomainEvent):
    """
    Event emitted when a taxonomy is updated (e.g., renamed).

    Attributes:
        taxonomy_id: ID of the updated taxonomy
        changed_fields: Tuple of field names that changed
        old_values: Dictionary of field names to their previous values
        new_values: Dictionary of field names to their new values
    """

    _aggregate_id_field: ClassVar[str] = "taxonomy_id"
    taxonomy_id: str = ""
    changed_fields: tuple[str, ...] = field(default_factory=tuple)
    old_values: dict[str, str | None] = field(default_factory=dict)
    new_values: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class TaxonomyDeleted(DomainEvent):
    """
    Event emitted when a taxonomy is deleted.

    Attributes:
        taxonomy_id: ID of the deleted taxonomy
        title: Title of the deleted taxonomy
    """

    _aggregate_id_field: ClassVar[str] = "taxonomy_id"
    taxonomy_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class SchemeUpdated(DomainEvent):
    """
    Event emitted when a concept scheme is updated (e.g., renamed).

    Attributes:
        concept_scheme_id: ID of the updated concept scheme
        taxonomy_id: ID of the parent taxonomy
        changed_fields: Tuple of field names that changed
        old_values: Dictionary of field names to their previous values
        new_values: Dictionary of field names to their new values
    """

    _aggregate_id_field: ClassVar[str] = "concept_scheme_id"
    concept_scheme_id: str = ""
    taxonomy_id: str = ""
    changed_fields: tuple[str, ...] = field(default_factory=tuple)
    old_values: dict[str, str | None] = field(default_factory=dict)
    new_values: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class SchemeDeleted(DomainEvent):
    """
    Event emitted when a concept scheme is deleted.

    Attributes:
        concept_scheme_id: ID of the deleted concept scheme
        taxonomy_id: ID of the parent taxonomy
        title: Title of the deleted concept scheme
    """

    _aggregate_id_field: ClassVar[str] = "concept_scheme_id"
    concept_scheme_id: str = ""
    taxonomy_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class PropertyDefinitionUpdated(DomainEvent):
    """
    Event emitted when a property definition is updated.

    Attributes:
        property_id: ID of the updated property definition
        title: New title of the property definition
        description: New description of the property definition
    """

    _aggregate_id_field: ClassVar[str] = "property_id"
    property_id: str = ""
    title: str = ""
    description: str | None = None


@dataclass(frozen=True)
class PropertyDefinitionDeleted(DomainEvent):
    """
    Event emitted when a property definition is deleted.

    Attributes:
        property_id: ID of the deleted property definition
    """

    _aggregate_id_field: ClassVar[str] = "property_id"
    property_id: str = ""


@dataclass(frozen=True)
class ConceptSchemeUpdated(DomainEvent):
    """
    Event emitted when a concept scheme is updated.

    Attributes:
        concept_scheme_id: ID of the updated concept scheme
        title: New title of the concept scheme
    """

    _aggregate_id_field: ClassVar[str] = "concept_scheme_id"
    concept_scheme_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class GraphInvalidated(DomainEvent):
    """
    Event emitted when the graph state is invalidated and needs recomputation.

    Attributes:
        taxonomy_id: ID of the affected taxonomy
        reason: Human-readable reason for invalidation
    """

    _aggregate_id_field: ClassVar[str] = "taxonomy_id"
    taxonomy_id: str = ""
    reason: str = ""
