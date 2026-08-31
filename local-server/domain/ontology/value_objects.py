"""
Value objects and enums for the Ontology Management domain.

These are immutable (frozen) dataclasses that represent concepts
without identity. They are used as components within domain entities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

# Slug format: lowercase alpha leading, then alphanumeric and underscore.
# 2-64 chars. Examples: tax_life, cls_organism, scheme_ecology
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

# 7-char hex color: '#' + 6 lowercase hex digits.
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-f]{6}$")


def validate_identifier(identifier: str) -> str:
    """
    Validate and normalize a slug-style identifier.

    Args:
        identifier: Candidate identifier string

    Returns:
        The validated identifier (stripped, lowercased)

    Raises:
        ValueError: If the identifier is empty or does not match the slug pattern
    """
    if identifier is None or not str(identifier).strip():
        raise ValueError("Identifier cannot be empty")
    candidate = str(identifier).strip().lower()
    if not _IDENTIFIER_PATTERN.match(candidate):
        raise ValueError(
            "Identifier must start with a lowercase letter and contain only "
            "lowercase letters, digits, and underscores (2-64 chars)"
        )
    return candidate


def validate_hex_color(color: str | None) -> str | None:
    """
    Validate and normalize an optional hex color string.

    Args:
        color: Candidate color string (e.g. '#a3f2e4') or None

    Returns:
        The validated lowercase color, or None if input was None/empty

    Raises:
        ValueError: If the color is non-empty but does not match the #rrggbb pattern
    """
    if color is None:
        return None
    candidate = str(color).strip().lower()
    if not candidate:
        return None
    if not _HEX_COLOR_PATTERN.match(candidate):
        raise ValueError("Color must be a 7-char hex string like '#a3f2e4'")
    return candidate


def validate_default_value_against_allowed_values(
    default_value: str | None,
    allowed_values: list[str] | None,
) -> None:
    """
    Validate that default_value is in allowed_values (if both are present).

    Args:
        default_value: Optional default value
        allowed_values: Optional list of allowed values

    Raises:
        ValueError: If default_value is set and allowed_values is non-empty
                   but does not contain default_value
    """
    if default_value is not None and allowed_values:
        if default_value not in allowed_values:
            raise ValueError(
                f"Default value '{default_value}' is not in allowed values: {allowed_values}"
            )


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


class DataType(str, Enum):
    """Enumeration of valid data types for AttributeDefinition."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


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
