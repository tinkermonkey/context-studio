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
    Reference to an entity in an external source (e.g., DBpedia, schema.org).

    Attributes:
        source: The name of the external knowledge base (e.g., "DBpedia", "schema.org")
        identifier: The unique identifier in the external source
        uri: Optional URI pointing to the external resource
    """

    source: str
    identifier: str
    uri: str | None = None


@dataclass(frozen=True)
class LexicalSense:
    """
    Lexical representation (label, language, sense type) of a concept.

    Attributes:
        label: The text label or term for this sense
        language_code: ISO 639 language code (e.g., "en", "fr", "es")
        sense_type: Type of sense: "preferred", "alternative", or "hidden"
    """

    label: str
    language_code: str
    sense_type: str


@dataclass(frozen=True)
class DataPropertyValue:
    """
    Value for a data property on an individual.

    Attributes:
        property_identifier: Identifier of the property definition
        value: The value as a string
        datatype: Optional datatype annotation (e.g., "xsd:string", "xsd:integer")
    """

    property_identifier: str
    value: str
    datatype: str | None = None


@dataclass(frozen=True)
class OntologyMapping:
    """
    Mapping between entities in different ontologies.

    Attributes:
        source_id: ID of the source entity
        target_id: ID of the target entity
        mapping_type: Type of mapping: "exactMatch", "closeMatch", "broadMatch", "narrowMatch"
    """

    source_id: str
    target_id: str
    mapping_type: str


@dataclass(frozen=True)
class SearchCriteria:
    """
    Criteria for searching within the ontology.

    Attributes:
        query: The search query string
        node_types: Optional list of NodeType values to filter by
        scheme_id: Optional concept scheme ID to limit search to
        taxonomy_id: Optional taxonomy ID to limit search to
        limit: Maximum number of results to return (default 20)
        offset: Number of results to skip (default 0)
    """

    query: str
    node_types: list[NodeType] | None = None
    scheme_id: str | None = None
    taxonomy_id: str | None = None
    limit: int = 20
    offset: int = 0
