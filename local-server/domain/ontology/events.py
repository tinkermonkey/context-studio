"""
Domain events for the Ontology Management bounded context.

Events capture state changes in the ontology and are used for event sourcing,
notifications, and trigger-based workflows. All events are frozen dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for all domain events in the Ontology Management context.

    All events have an event ID, timestamp, and aggregate ID. Subclasses
    add domain-specific fields.

    Attributes:
        event_id: Unique identifier for this event (typically a UUID string)
        occurred_at: Timestamp of when the event occurred
        aggregate_id: ID of the primary aggregate involved in the event
    """

    event_id: str
    occurred_at: datetime
    aggregate_id: str

    def __post_init__(self) -> None:
        """
        Validate that required string fields are not empty.

        Raises:
            ValueError: If any string field is empty or contains only whitespace
        """
        for field_name, _ in self.__dataclass_fields__.items():
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

    taxonomy_id: str
    title: str


@dataclass(frozen=True)
class SchemeCreated(DomainEvent):
    """
    Event emitted when a new concept scheme is created.

    Attributes:
        scheme_id: ID of the created concept scheme
        title: Title of the concept scheme
        taxonomy_id: ID of the parent taxonomy
    """

    scheme_id: str
    title: str
    taxonomy_id: str


@dataclass(frozen=True)
class ClassCreated(DomainEvent):
    """
    Event emitted when a new class is created.

    Attributes:
        class_id: ID of the created class
        title: Title of the class
        scheme_id: ID of the parent concept scheme
        taxonomy_id: ID of the parent taxonomy
    """

    class_id: str
    title: str
    scheme_id: str
    taxonomy_id: str


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

    class_id: str
    changed_fields: tuple[str, ...]
    old_values: dict[str, str | None]
    new_values: dict[str, str | None]


@dataclass(frozen=True)
class ClassDeleted(DomainEvent):
    """
    Event emitted when a class is deleted.

    Attributes:
        class_id: ID of the deleted class
        title: Title of the deleted class
    """

    class_id: str
    title: str


@dataclass(frozen=True)
class ClassMoved(DomainEvent):
    """
    Event emitted when a class is moved in the hierarchy.

    Attributes:
        class_id: ID of the moved class
        old_parent_id: ID of the old parent class (None if was root)
        new_parent_id: ID of the new parent class (None if now root)
    """

    class_id: str
    old_parent_id: str | None
    new_parent_id: str | None


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

    relationship_id: str
    source_id: str
    target_id: str
    property_definition_id: str


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

    relationship_id: str
    source_id: str
    target_id: str
    property_definition_id: str


@dataclass(frozen=True)
class PropertyDefinitionCreated(DomainEvent):
    """
    Event emitted when a new property definition is created.

    Attributes:
        property_id: ID of the created property definition
        title: Title of the property definition
    """

    property_id: str
    title: str


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

    taxonomy_id: str
    changed_fields: tuple[str, ...]
    old_values: dict[str, str | None]
    new_values: dict[str, str | None]


@dataclass(frozen=True)
class TaxonomyDeleted(DomainEvent):
    """
    Event emitted when a taxonomy is deleted.

    Attributes:
        taxonomy_id: ID of the deleted taxonomy
        title: Title of the deleted taxonomy
    """

    taxonomy_id: str
    title: str


@dataclass(frozen=True)
class SchemeUpdated(DomainEvent):
    """
    Event emitted when a concept scheme is updated (e.g., renamed).

    Attributes:
        scheme_id: ID of the updated concept scheme
        taxonomy_id: ID of the parent taxonomy
        changed_fields: Tuple of field names that changed
        old_values: Dictionary of field names to their previous values
        new_values: Dictionary of field names to their new values
    """

    scheme_id: str
    taxonomy_id: str
    changed_fields: tuple[str, ...]
    old_values: dict[str, str | None]
    new_values: dict[str, str | None]


@dataclass(frozen=True)
class SchemeDeleted(DomainEvent):
    """
    Event emitted when a concept scheme is deleted.

    Attributes:
        scheme_id: ID of the deleted concept scheme
        taxonomy_id: ID of the parent taxonomy
        title: Title of the deleted concept scheme
    """

    scheme_id: str
    taxonomy_id: str
    title: str


@dataclass(frozen=True)
class GraphInvalidated(DomainEvent):
    """
    Event emitted when the graph state is invalidated and needs recomputation.

    Attributes:
        taxonomy_id: ID of the affected taxonomy
        reason: Human-readable reason for invalidation
    """

    taxonomy_id: str
    reason: str
