"""
Ontology Management bounded context.

This module contains all domain entities, value objects, and exceptions
for managing ontologies: taxonomies, concept schemes, classes, individuals,
relationships, and property definitions.
"""

from .entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from .exceptions import (
    CircularReferenceError,
    DuplicateEntityError,
    EntityNotFoundError,
    OntologyError,
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
