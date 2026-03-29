"""
Extraction domain ports (interfaces).

Protocol definitions for external dependencies required by the extraction domain,
plus value objects used in port contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, Sequence

if TYPE_CHECKING:
    from domain.extraction.entities import ExtractionResult


# ============================================================================
# Value types used in port contracts
# ============================================================================

@dataclass(frozen=True)
class LLMResponse:
    """
    Response from an LLM completion request.

    Attributes:
        content: The generated text response
        tokens_in: Count of input tokens consumed
        tokens_out: Count of output tokens generated
        duration_ms: Time spent processing the request in milliseconds
        finish_reason: Reason the model stopped (e.g., 'stop', 'length')
        model: Name of the model that generated the response
    """
    content: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    finish_reason: str
    model: str


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

    Raises:
        ValueError: If confidence is not 0.0-1.0 or end < start
    """
    text: str
    label: str
    start: int
    end: int
    confidence: float
    linked_uri: str | None = None

    def __post_init__(self) -> None:
        """Validate NLP entity invariants."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
        if self.end < self.start:
            raise ValueError(f"end must be >= start, got start={self.start}, end={self.end}")


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

    Raises:
        ValueError: If confidence is not 0.0-1.0
    """
    uri: str
    label: str
    description: str | None = None
    confidence: float = 1.0
    source: str = ""

    def __post_init__(self) -> None:
        """Validate reference result invariants."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")


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

class LLMProvider(Protocol):
    """
    Port for LLM completion and model introspection.

    Implementations provide access to language models for text generation
    and information about available models. This port is shared across both
    the extraction and pipeline bounded contexts.
    """

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format: Literal["json", "text"] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """
        Request a completion from an LLM.

        Args:
            system_prompt: System context for the model
            user_prompt: User message to respond to
            model: Model identifier
            temperature: Sampling temperature (0.0–1.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional response format ("json" for JSON output, "text" for plain text)
            timeout: Request timeout in seconds (provider-specific behavior)

        Returns:
            LLMResponse with generated content and metadata
        """
        ...

    def is_model_available(self, model: str) -> bool:
        """
        Check if a specific model is available.

        Args:
            model: Model identifier

        Returns:
            True if the model can be used, False otherwise
        """
        ...

    def list_available_models(self) -> list[str]:
        """
        Get list of available model identifiers.

        Returns:
            List of model names that can be used with complete()
        """
        ...


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

    async def search_async(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term asynchronously.

        Implementations should delegate to search() via run_sync_in_executor
        to avoid blocking the event loop.

        Args:
            term: Search query
            limit: Maximum number of results

        Returns:
            List of matching ReferenceResult objects
        """
        ...

    async def get_relations_async(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI asynchronously.

        Implementations should delegate to get_relations() via run_sync_in_executor
        to avoid blocking the event loop.

        Args:
            uri: URI of the resource to find relations for
            limit: Maximum number of relations

        Returns:
            List of ReferenceRelation objects
        """
        ...

    async def is_available_async(self) -> bool:
        """
        Check if this source is available asynchronously.

        Implementations should delegate to is_available() via run_sync_in_executor
        to avoid blocking the event loop.

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
