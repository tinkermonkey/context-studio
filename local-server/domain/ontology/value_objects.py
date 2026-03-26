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


@dataclass(frozen=True)
class ExternalReference:
    """
    Reference to an entity in an external source (e.g., DBpedia, Wikidata, ConceptNet).

    Attributes:
        identifier: The external identifier (required)
        source: The name of the external knowledge base (e.g., "dbpedia", "wikidata", "conceptnet")
        uri: The external URI
        label: Human-readable label from the source
        confidence: Match confidence score
        metadata: Source-specific metadata (immutable proxy around dict, or None)
    """

    identifier: str
    source: str
    uri: str
    label: str | None = None
    confidence: float | None = None
    metadata: MappingProxyType[str, Any] | None = None


@dataclass(frozen=True)
class LexicalSense:
    """
    Word sense disambiguation data, typically from WordNet.

    Attributes:
        synset_id: The WordNet synset identifier (e.g., "dog.n.01")
        definition: The definition of the sense from the source
        lemma: The canonical lemma or term for this sense
        confidence: Optional confidence score for the sense match
        source: The source of the lexical sense data (default: "wordnet")
    """

    synset_id: str
    definition: str
    lemma: str
    confidence: float | None = None
    source: str = "wordnet"


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
    Maps to an external ontology standard or schema.

    Attributes:
        ontology: The name of the external ontology standard (e.g., "owl", "schema.org", "dbpedia")
        uri: The URI of the external ontology term or class
        label: Human-readable label from the external ontology
        exact_match: Boolean indicating whether this is an exact semantic match
        confidence: Optional confidence score for the mapping
        source: The source system that created the mapping (default: "external")
    """

    ontology: str
    uri: str
    label: str
    exact_match: bool
    confidence: float | None = None
    source: str = "external"


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
