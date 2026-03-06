"""
Port interfaces for the Extraction bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
Response dataclasses are defined in this file alongside their corresponding ports.
"""
from dataclasses import dataclass, field
from typing import Protocol, Optional, List


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    finish_reason: str  # "stop", "length", "error"
    raw_response: dict = field(default_factory=dict)


@dataclass
class NLPEntity:
    """Entity extracted from text by NLP processor."""

    text: str
    label: str
    start: int
    end: int
    confidence: float
    linked_uri: Optional[str] = None


@dataclass
class NLPResult:
    """Results from NLP processing."""

    entities: List[NLPEntity]
    tokens: List[str]
    noun_chunks: List[str]
    language: str


@dataclass
class ReferenceRelation:
    """Relation from a reference source."""

    subject_uri: str
    predicate: str
    object_uri: str
    object_label: Optional[str] = None
    weight: Optional[float] = None


@dataclass
class ReferenceResult:
    """Result from a reference source lookup."""

    uri: str
    label: str
    description: Optional[str]
    source: str
    confidence: float
    metadata: Optional[dict] = None


class LLMProvider(Protocol):
    """Provider for LLM inference.

    Implementations route to specific providers (OpenAI, Anthropic, etc.)
    based on the model identifier.
    """

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,  # "json", "text"
    ) -> LLMResponse:
        """Send prompts to an LLM and receive a completion."""
        ...

    def is_model_available(self, model: str) -> bool:
        """Check if a model is available for use."""
        ...

    def list_available_models(self) -> list[str]:
        """List all available models."""
        ...


class NLPProcessor(Protocol):
    """Processor for NLP text analysis.

    Wraps a full NLP pipeline (tokenization, NER, entity linking, etc.)
    behind a simple interface.
    """

    def process(self, text: str) -> NLPResult:
        """Process text and return tokenized, noun chunk, and entity results."""
        ...

    def extract_entities(self, text: str) -> List[NLPEntity]:
        """Extract named entities from text."""
        ...

    def is_ready(self) -> bool:
        """Check if the NLP processor is ready for use."""
        ...


class ReferenceSource(Protocol):
    """A source of reference knowledge for concept enrichment.

    Each implementation wraps a specific external API (ConceptNet, DBpedia, etc.).
    The interface is intentionally simple — complex multi-source aggregation
    is handled by the domain service, not the adapter.
    """

    @property
    def source_name(self) -> str:
        """Get the name of this reference source."""
        ...

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """Search for a term and return matching results."""
        ...

    def get_relations(self, uri: str, limit: int = 20) -> list[ReferenceRelation]:
        """Get relations for an entity identified by URI."""
        ...

    def is_available(self) -> bool:
        """Check if this source is available (e.g., API reachable)."""
        ...
