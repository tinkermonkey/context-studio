"""
Value objects and enums for the Ontology Management domain.

These are immutable (frozen) dataclasses that represent concepts
without identity. They are used as components within domain entities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NodeType(str, Enum):
    """Enumeration of ontology node types."""

    TAXONOMY = "TAXONOMY"
    CONCEPT_SCHEME = "CONCEPT_SCHEME"
    CLASS = "CLASS"
    INDIVIDUAL = "INDIVIDUAL"


@dataclass(frozen=True)
class ExternalReference:
    """
    Reference to an entity in an external source (e.g., DBpedia, Wikidata, ConceptNet).

    Attributes:
        source: The name of the external knowledge base (e.g., "dbpedia", "wikidata", "conceptnet")
        uri: The external URI
        label: Human-readable label from the source
        confidence: Match confidence score
        metadata: Source-specific metadata
    """

    source: str
    uri: str
    label: str | None = None
    confidence: float | None = None
    metadata: dict | None = None


@dataclass(frozen=True)
class LexicalSense:
    """
    Word sense disambiguation data, typically from WordNet.

    Attributes:
        synset_id: WordNet synset identifier
        definition: The sense definition
        lemma: The lemma/word form
        confidence: Optional confidence score
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
        key: Attribute name
        value: Attribute value (string, number, boolean, etc.)
        datatype: Optional type hint (e.g., "xsd:string", "xsd:integer")
    """

    key: str
    value: str | int | float | bool | None
    datatype: str | None = None


@dataclass(frozen=True)
class OntologyMapping:
    """
    Maps a PropertyDefinition to an external ontology standard.

    Attributes:
        ontology: The ontology standard (e.g., "owl", "rdfs", "skos", "conceptnet")
        uri: The property URI in that ontology
        label: Optional human-readable label
        exact_match: Whether this is an exact semantic match
    """

    ontology: str
    uri: str
    label: str | None = None
    exact_match: bool = False


@dataclass(frozen=True)
class SearchCriteria:
    """
    Encapsulates search parameters for querying ontology entities.

    Attributes:
        query: Optional text search query
        node_type: Optional filter by entity type
        taxonomy_id: Optional filter by taxonomy
        scheme_id: Optional filter by concept scheme
        parent_id: Optional filter by parent entity
        use_semantic_search: Whether to use embedding similarity (default False)
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip (default 0)
    """

    query: str | None = None
    node_type: NodeType | None = None
    taxonomy_id: str | None = None
    scheme_id: str | None = None
    parent_id: str | None = None
    use_semantic_search: bool = False
    limit: int = 50
    offset: int = 0
