"""
Domain value objects for the ontology bounded context.

Value objects are immutable types that represent domain concepts and are identified
by their values rather than by identity. All types in this module are framework-free
and depend only on Python stdlib.

NOTE: There are two NodeType enums in the codebase (this one and database.enums.NodeType).
This is a temporary duality during the re-architecture phase. See domain/ontology/compat.py
for the mapping utilities and detailed explanation. Issue #270 tracks consolidation.
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field
from enum import Enum


class NodeType(str, Enum):
    """
    Enumeration of structure node types in the domain model.

    This enum represents the four core entity types in the ontology:
    - TAXONOMY: A top-level categorization system (legacy: "layer")
    - CONCEPT_SCHEME: A collection of related concepts (legacy: "domain")
    - CLASS: A concept or class definition (legacy: "term")
    - INDIVIDUAL: A specific instance of a class (not yet implemented)
    """

    TAXONOMY = "taxonomy"
    CONCEPT_SCHEME = "concept_scheme"
    CLASS = "class"
    INDIVIDUAL = "individual"

    @classmethod
    def from_legacy(cls, legacy_value: str) -> NodeType:
        """
        Map legacy node_type values to new NodeType values.

        This method provides backwards compatibility by translating the old
        terminology (layer, domain, term) to the new terminology.
        Also supports new terminology values for forward compatibility.

        Args:
            legacy_value: A legacy node type string ("layer", "domain", "term")
                         or new terminology ("taxonomy", "concept_scheme", "class", "individual")

        Returns:
            The corresponding NodeType enum value

        Raises:
            ValueError: If the value is not recognized
        """
        mapping = {
            "layer": cls.TAXONOMY,
            "domain": cls.CONCEPT_SCHEME,
            "term": cls.CLASS,
            # Forward mappings for new terminology
            "taxonomy": cls.TAXONOMY,
            "concept_scheme": cls.CONCEPT_SCHEME,
            "class": cls.CLASS,
            "individual": cls.INDIVIDUAL,
        }
        mapped_type = mapping.get(legacy_value)
        if mapped_type is None:
            raise ValueError(
                f"Unknown node type: {legacy_value!r}. "
                f"Expected one of: {', '.join(mapping.keys())}"
            )
        return mapped_type


@dataclass(frozen=True)
class ExternalReference:
    """
    An immutable reference to an external ontology or knowledge base.

    Attributes:
        source: The name of the external source (e.g., "wikidata", "dbpedia")
        uri: The unique identifier (URI/URL) in the external source
        label: A human-readable label or name from the external source
        confidence: A confidence score between 0.0 and 1.0 for the reference accuracy
        metadata: Additional structured data about the reference (wrapped as read-only)
    """

    source: str
    uri: str
    label: str
    confidence: float
    metadata: types.MappingProxyType = field(
        default_factory=lambda: types.MappingProxyType({})
    )

    def __post_init__(self) -> None:
        """Wrap mutable dict in a read-only proxy to preserve immutability."""
        if not isinstance(self.metadata, types.MappingProxyType):
            object.__setattr__(self, "metadata", types.MappingProxyType(self.metadata))


@dataclass(frozen=True)
class LexicalSense:
    """
    An immutable lexical sense definition from a lexicon or word sense database.

    Attributes:
        synset_id: The identifier of the synset in the lexicon
        definition: A textual definition of the sense
        lemma: The lemma (base form) associated with this sense
        confidence: A confidence score between 0.0 and 1.0 for the sense match
        source: The source lexicon or knowledge base (e.g., "wordnet")
    """

    synset_id: str
    definition: str
    lemma: str
    confidence: float
    source: str


@dataclass(frozen=True)
class DataPropertyValue:
    """
    An immutable data property assertion on an entity.

    Attributes:
        key: The property name or identifier
        value: The property value as a string
        datatype: The datatype of the value (e.g., "xsd:string", "xsd:integer")
    """

    key: str
    value: str
    datatype: str


@dataclass(frozen=True)
class OntologyMapping:
    """
    An immutable mapping assertion linking entities to external ontologies.

    Attributes:
        ontology: The name of the external ontology (e.g., "rdfs", "skos")
        uri: The URI of the mapped entity in the external ontology
        label: A human-readable label from the external ontology
        exact_match: True if this is an exact match, False if approximate
    """

    ontology: str
    uri: str
    label: str
    exact_match: bool


@dataclass(frozen=True)
class SearchCriteria:
    """
    An immutable search criteria specification for querying the ontology.

    Attributes:
        query: The search query string
        node_type: Optional filter by node type
        taxonomy_id: Optional filter by taxonomy parent
        scheme_id: Optional filter by concept scheme parent
        parent_id: Optional filter by direct parent node
        use_semantic_search: Whether to use semantic/embedding-based search
        limit: Maximum number of results to return
        offset: Number of results to skip for pagination
    """

    query: str
    node_type: NodeType | None = None
    taxonomy_id: str | None = None
    scheme_id: str | None = None
    parent_id: str | None = None
    use_semantic_search: bool = False
    limit: int = 20
    offset: int = 0
