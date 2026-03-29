"""
Extraction domain ports (interfaces).

Protocol definitions for external dependencies required by the extraction domain,
plus value objects used in port contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Sequence

if TYPE_CHECKING:
    from domain.extraction.entities import ExtractionResult


# ============================================================================
# Value types used in port contracts
# ============================================================================

@dataclass(frozen=True)
class NLPEntity:
    """
    A named entity identified by an NLP processor.

    Attributes:
        text: The literal text of the entity in the source document
        label: The entity type label (e.g., 'ORG', 'PERSON', 'GPE')
        start: Character offset where entity begins
        end: Character offset where entity ends
        confidence: Confidence score from 0.0 to 1.0
        linked_uri: Optional URI linking to external knowledge base
    """
    text: str
    label: str
    start: int
    end: int
    confidence: float
    linked_uri: str | None = None


@dataclass(frozen=True)
class NLPResult:
    """
    Complete output from NLP processing.

    Attributes:
        tokens: List of tokenized words/phrases
        entities: Named entities identified in the text
        noun_chunks: List of noun phrases extracted from the text
        language: Detected language code (e.g., 'en', 'es')
    """
    tokens: list[str]
    entities: list[NLPEntity]
    noun_chunks: list[str]
    language: str


@dataclass(frozen=True)
class ReferenceResult:
    """
    A single search result from a reference source.

    Attributes:
        uri: Unique URI for this resource
        label: Human-readable label or title
        description: Optional longer description
        confidence: Confidence score from 0.0 to 1.0
        source: Which reference source returned this result
    """
    uri: str
    label: str
    description: str | None = None
    confidence: float = 1.0
    source: str = ""


@dataclass(frozen=True)
class ReferenceRelation:
    """
    A relationship between concepts in a reference source.

    Attributes:
        subject_uri: URI of the source concept
        predicate: Type of relationship (e.g., 'narrower', 'broader')
        object_uri: URI of the target concept
        weight: Optional strength/confidence weight for the relation
        source: Which reference source this relation comes from
    """
    subject_uri: str
    predicate: str
    object_uri: str
    weight: float | None = None
    source: str = ""


# ============================================================================
# Port interfaces (Protocols)
# ============================================================================

class NLPProcessor(Protocol):
    """
    Port for natural language processing.

    Implementations provide entity extraction, tokenization, and
    language detection capabilities.
    """

    def process(self, text: str) -> NLPResult:
        """
        Perform full NLP processing on text.

        Args:
            text: Text to process

        Returns:
            NLPResult with tokens, entities, and language
        """
        ...

    def extract_entities(self, text: str) -> list[NLPEntity]:
        """
        Extract named entities from text.

        Args:
            text: Text to process

        Returns:
            List of NLPEntity objects found in the text
        """
        ...

    def is_ready(self) -> bool:
        """
        Check if the processor is ready to use.

        Returns:
            True if initialized and ready, False otherwise
        """
        ...


class ReferenceSource(Protocol):
    """
    Port for external reference knowledge sources.

    Implementations provide search and relationship retrieval from
    sources like ConceptNet, DBpedia, Wikidata, or schema.org.
    """

    @property
    def source_name(self) -> str:
        """
        Get the name of this reference source.

        Returns:
            Human-readable name (e.g., 'ConceptNet', 'DBpedia')
        """
        ...

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term.

        Args:
            term: Search query
            limit: Maximum number of results

        Returns:
            List of matching ReferenceResult objects
        """
        ...

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI.

        Args:
            uri: URI of the resource to find relations for
            limit: Maximum number of relations

        Returns:
            List of ReferenceRelation objects
        """
        ...

    def is_available(self) -> bool:
        """
        Check if this source is available.

        Returns:
            True if the source can be queried, False otherwise
        """
        ...


class ExtractionRepository(Protocol):
    """
    Port for persistence of extraction results.

    Implementations store and retrieve extraction results, processing metrics,
    and related extraction pipeline artifacts.
    """

    def save_extraction_result(self, result: ExtractionResult) -> ExtractionResult:
        """
        Save an extraction result to persistent storage.

        Args:
            result: The ExtractionResult to save

        Returns:
            The saved ExtractionResult (may have updated metadata like id or timestamp)
        """
        ...

    def get_extraction_result(self, result_id: str) -> ExtractionResult | None:
        """
        Retrieve an extraction result by ID.

        Args:
            result_id: The ID of the extraction result

        Returns:
            The ExtractionResult or None if not found
        """
        ...

    def list_extraction_results(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionResult]:
        """
        List extraction results with pagination.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of ExtractionResult objects
        """
        ...
