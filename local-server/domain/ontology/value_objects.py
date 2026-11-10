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


_PREDICATE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,254}$")


def validate_predicate_identifier(identifier: str) -> str:
    """
    Validate a predicate identifier: a bare relation verb such as "part_of" or
    "navigates-to" (lowercase letters, digits, "_" and "-", starting with a letter).

    Raises:
        ValueError: If it's empty or doesn't fit that shape
    """
    candidate = str(identifier or "").strip()
    if not _PREDICATE_PATTERN.match(candidate):
        raise ValueError(
            f"Predicate {identifier!r} must start with a lowercase letter and contain only"
            " lowercase letters, digits, '_' and '-'"
        )
    return candidate


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


_DATASET_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


def validate_dataset_identifier(identifier: str) -> str:
    """
    Validate and normalize a dataset identifier: a slug that may also use hyphens.

    Args:
        identifier: Candidate identifier string

    Returns:
        The validated identifier (stripped, lowercased)

    Raises:
        ValueError: If the identifier is empty or does not match the pattern
    """
    candidate = str(identifier or "").strip().lower()
    if not _DATASET_IDENTIFIER_PATTERN.match(candidate):
        raise ValueError(
            "Dataset identifier must start with a lowercase letter and contain only"
            " lowercase letters, digits, hyphens and underscores (2-64 chars)"
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


def normalize_distinguish_from(items: Any) -> list[dict[str, str]]:
    """
    A class's distinguish_from in its one shape: [{"class_id", "when"}], each
    naming another class once, with the text saying when to use it instead.

    Raises:
        ValueError: If an entry is not an object with a class_id and a non-empty
            when, or a class_id repeats
    """
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError("distinguish_from must be a list of {class_id, when}")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) - {"class_id", "when"}:
            raise ValueError("Each distinguish_from entry is {class_id, when}")
        class_id = item.get("class_id")
        when = item.get("when")
        if not isinstance(class_id, str) or not class_id.strip():
            raise ValueError("A distinguish_from entry needs a class_id")
        if not isinstance(when, str) or not when.strip():
            raise ValueError(f"The distinguish_from entry for {class_id} needs a when")
        if class_id in seen:
            raise ValueError(f"distinguish_from names {class_id} twice")
        seen.add(class_id)
        normalized.append({"class_id": class_id.strip(), "when": when.strip()})
    return normalized


def normalize_evidence_signals(signals: Any) -> list[str]:
    """
    A class's evidence signals as non-empty, trimmed text, in order.

    Raises:
        ValueError: If signals is not a list of text
    """
    if signals is None:
        return []
    if not isinstance(signals, list) or not all(isinstance(s, str) for s in signals):
        raise ValueError("evidence_signals must be a list of text")
    return [s.strip() for s in signals if s.strip()]


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
    NUMBER = "number"
    # A calendar date, written as ISO 8601 text: YYYY-MM-DD
    DATE = "date"
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

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict (used in domain event payloads and change events)."""
        return {
            "source": self.source,
            "identifier": self.identifier,
            "uri": self.uri,
            "metadata": dict(self.metadata) if self.metadata else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExternalReference":
        """Rebuild a reference from a dict produced by ``to_dict``."""
        metadata = data.get("metadata")
        return cls(
            source=data["source"],
            identifier=data["identifier"],
            uri=data.get("uri"),
            metadata=MappingProxyType(dict(metadata)) if metadata else None,
        )


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
        value: Attribute value (string, number, boolean, None, or a JSON list
            or dict for an array or object attribute)
        datatype: Optional type hint (e.g., "xsd:string", "xsd:integer")
    """

    property_identifier: str
    value: str | int | float | bool | list[Any] | dict[str, Any] | None
    datatype: str | None = None


@dataclass(frozen=True)
class SourceRevision:
    """
    A revision of the external source a mirrored taxonomy follows (a client's
    spec in its repository).

    Attributes:
        repo: The source repository (a URL or a name)
        commit: The commit
        spec_version: The source's own version label
    """

    repo: str | None = None
    commit: str | None = None
    spec_version: str | None = None

    def __post_init__(self) -> None:
        for name in ("repo", "commit", "spec_version"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"A source revision's {name} must be a non-empty string")
        if self.repo is None and self.commit is None and self.spec_version is None:
            raise ValueError("A source revision needs at least one of repo, commit, spec_version")

    def to_dict(self) -> dict[str, str | None]:
        """The revision as JSON: every key, None when unknown."""
        return {"repo": self.repo, "commit": self.commit, "spec_version": self.spec_version}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRevision:
        """
        Read {"repo", "commit", "spec_version"}; missing keys are None.

        Raises:
            ValueError: For an unknown key, a blank value, or no value at all
        """
        if not isinstance(data, dict):
            raise ValueError("A source revision must be an object")
        unknown = sorted(set(data) - {"repo", "commit", "spec_version"})
        if unknown:
            raise ValueError(f"Unknown source revision keys {unknown}")
        return cls(
            repo=data.get("repo"), commit=data.get("commit"), spec_version=data.get("spec_version")
        )


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


@dataclass(frozen=True)
class SchemeCounts:
    """
    Content counts for one concept scheme.

    Attributes:
        scheme_id: The concept scheme the counts belong to
        class_count: Classes in the scheme
        individual_count: Distinct individuals typed by at least one of its classes
        property_definition_count: Property definitions whose domain is one of its classes
    """

    scheme_id: str
    class_count: int
    individual_count: int
    property_definition_count: int


@dataclass(frozen=True)
class ClassCounts:
    """
    Content counts for one class.

    Attributes:
        class_id: The class the counts belong to
        individual_count: Individuals typed by the class
        property_definition_count: Property definitions with the class as domain
        relationship_count: Relationships whose source is an individual of the class
    """

    class_id: str
    individual_count: int
    property_definition_count: int
    relationship_count: int


@dataclass(frozen=True)
class DatasetDeletion:
    """
    What deleting a dataset removed.

    Attributes:
        dataset_id: The deleted dataset
        individual_count: Individuals deleted with it
        relationship_count: Relationships deleted with its individuals
    """

    dataset_id: str
    individual_count: int
    relationship_count: int
