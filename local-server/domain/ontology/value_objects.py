"""
Value objects and enums for the Ontology Management domain.

These are immutable (frozen) dataclasses that represent concepts
without identity. They are used as components within domain entities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from types import MappingProxyType


class NodeType(str, Enum):
    """Enumeration of ontology node types."""

    TAXONOMY = "taxonomy"
    CONCEPT_SCHEME = "concept_scheme"
    CLASS = "class"
    INDIVIDUAL = "individual"
    PROPERTY_DEFINITION = "property_definition"


class Status(str, Enum):
    """Enumeration of publication status for domain entities."""

    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass(frozen=True)
class ExternalReference:
    """
    Reference to an entity in an external source (e.g., DBpedia, Wikidata, ConceptNet).

    Attributes:
        source: The name of the external knowledge base (e.g., "dbpedia", "wikidata", "conceptnet")
        identifier: The external identifier (required)
        uri: The external URI (optional)
        metadata: Source-specific metadata (immutable proxy around dict, or None)
    """

    source: str
    identifier: str
    uri: str | None = None
    metadata: MappingProxyType[str, Any] | None = None


@dataclass(frozen=True)
class LexicalSense:
    """
    Word sense disambiguation data from external lexical sources.

    Attributes:
        label: The sense label or term (required)
        language_code: ISO 639-1 language code (required)
        sense_type: The type of sense (e.g., "synset", "word_sense") (required)
    """

    label: str
    language_code: str
    sense_type: str


@dataclass(frozen=True)
class DataPropertyValue:
    """
    A literal-valued attribute on an entity (corresponds to OWL DatatypeProperty).

    Attributes:
        property_identifier: Property identifier
        value: Attribute value (string, number, boolean, etc.)
        datatype: Optional type hint (e.g., "xsd:string", "xsd:integer")
    """

    property_identifier: str
    value: str | int | float | bool | None
    datatype: str | None = None


@dataclass(frozen=True)
class OntologyMapping:
    """
    Maps between entities in different ontologies.

    Attributes:
        source_id: The UUID of the source entity (required)
        target_id: The UUID of the target entity (required)
        mapping_type: The type of mapping (e.g., "exact_match", "related_match") (required)
    """

    source_id: str
    target_id: str
    mapping_type: str


@dataclass(frozen=True)
class SearchCriteria:
    """
    Encapsulates search parameters for querying ontology entities.

    Attributes:
        query: Optional text search query
        node_types: Optional filter by entity types (tuple of node types, immutable)
        taxonomy_id: Optional filter by taxonomy
        concept_scheme_id: Optional filter by concept scheme
        parent_id: Optional filter by parent entity
        use_semantic_search: Whether to use embedding similarity (default False)
        limit: Maximum number of results to return (default 20)
        offset: Number of results to skip (default 0)
    """

    query: str | None = None
    node_types: tuple[NodeType, ...] | None = None
    taxonomy_id: str | None = None
    concept_scheme_id: str | None = None
    parent_id: str | None = None
    use_semantic_search: bool = False
    limit: int = 20
    offset: int = 0
