"""
Domain events for the Ontology Management bounded context.

Events capture state changes in the ontology and are used for event sourcing,
notifications, and trigger-based workflows. All events are frozen dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from domain.events import DomainEvent


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
        identifier: Identifier/name of the deleted property definition
        title: Title of the deleted property definition
    """

    _aggregate_id_field: ClassVar[str] = "property_id"
    property_id: str = ""
    identifier: str = ""
    title: str = ""


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
class IndividualCreated(DomainEvent):
    """
    Event emitted when a new individual is created.

    Attributes:
        individual_id: ID of the created individual
        title: Title of the individual
        class_ids: List of parent class IDs
    """

    _aggregate_id_field: ClassVar[str] = "individual_id"
    individual_id: str = ""
    title: str = ""
    class_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IndividualUpdated(DomainEvent):
    """
    Event emitted when an individual is updated.

    Attributes:
        individual_id: ID of the updated individual
        changed_fields: Tuple of field names that changed
        old_values: Dictionary of field names to their previous values
        new_values: Dictionary of field names to their new values
    """

    _aggregate_id_field: ClassVar[str] = "individual_id"
    individual_id: str = ""
    changed_fields: tuple[str, ...] = field(default_factory=tuple)
    old_values: dict[str, object] = field(default_factory=dict)
    new_values: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class IndividualDeleted(DomainEvent):
    """
    Event emitted when an individual is deleted.

    Attributes:
        individual_id: ID of the deleted individual
        title: Title of the deleted individual
    """

    _aggregate_id_field: ClassVar[str] = "individual_id"
    individual_id: str = ""
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
