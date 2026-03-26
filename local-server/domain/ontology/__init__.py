"""
Ontology Management bounded context.

This module contains all domain entities, value objects, events, exceptions,
and port interfaces for managing ontologies: taxonomies, concept schemes,
classes, individuals, relationships, and property definitions.
"""

from .entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from .events import (
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    DomainEvent,
    GraphInvalidated,
    PropertyDefinitionCreated,
    RelationshipCreated,
    RelationshipDeleted,
    SchemeCreated,
    TaxonomyCreated,
)
from .exceptions import (
    CircularReferenceError,
    DuplicateEntityError,
    EntityNotFoundError,
    OntologyError,
)
from .ports import (
    EmbeddingService,
    EventPublisher,
    OntologyRepository,
)
from .value_objects import (
    DataPropertyValue,
    ExternalReference,
    LexicalSense,
    NodeType,
    OntologyMapping,
    SearchCriteria,
)

__all__ = [
    # Entities
    "Taxonomy",
    "ConceptScheme",
    "Class",
    "Individual",
    "Relationship",
    "PropertyDefinition",
    # Domain Events
    "DomainEvent",
    "TaxonomyCreated",
    "SchemeCreated",
    "ClassCreated",
    "ClassUpdated",
    "ClassDeleted",
    "ClassMoved",
    "RelationshipCreated",
    "RelationshipDeleted",
    "PropertyDefinitionCreated",
    "GraphInvalidated",
    # Ports (Protocols)
    "OntologyRepository",
    "EmbeddingService",
    "EventPublisher",
    # Value Objects
    "NodeType",
    "ExternalReference",
    "LexicalSense",
    "DataPropertyValue",
    "OntologyMapping",
    "SearchCriteria",
    # Exceptions
    "OntologyError",
    "EntityNotFoundError",
    "CircularReferenceError",
    "DuplicateEntityError",
]
