"""
Ontology Management bounded context.

This module contains all domain entities, value objects, events, exceptions,
and port interfaces for managing ontologies: taxonomies, concept schemes,
classes, individuals, relationships, and property definitions.
"""

from .entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from .events import (
    AttributeDefinitionCreated,
    AttributeDefinitionDeleted,
    AttributeDefinitionUpdated,
    ClassCreated,
    ClassDeleted,
    ClassMoved,
    ClassUpdated,
    GraphInvalidated,
    PropertyDefinitionCreated,
    RelationshipCreated,
    RelationshipDeleted,
    SchemeCreated,
    SchemeDeleted,
    SchemeUpdated,
    TaxonomyCreated,
    TaxonomyDeleted,
    TaxonomyUpdated,
)
from .exceptions import (
    CircularReferenceError,
    DuplicateEntityError,
    EntityNotFoundError,
    OntologyError,
)
from .ports import (
    EmbeddingService,
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
    "AttributeDefinition",
    # Domain Events
    "TaxonomyCreated",
    "TaxonomyUpdated",
    "TaxonomyDeleted",
    "SchemeCreated",
    "SchemeUpdated",
    "SchemeDeleted",
    "ClassCreated",
    "ClassUpdated",
    "ClassDeleted",
    "ClassMoved",
    "RelationshipCreated",
    "RelationshipDeleted",
    "PropertyDefinitionCreated",
    "AttributeDefinitionCreated",
    "AttributeDefinitionUpdated",
    "AttributeDefinitionDeleted",
    "GraphInvalidated",
    # Ports (Protocols)
    "OntologyRepository",
    "EmbeddingService",
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
