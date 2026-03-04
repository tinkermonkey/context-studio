"""
Port interfaces for the Extraction bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
Response dataclasses are defined in this file alongside their corresponding ports.
"""
from dataclasses import dataclass, field
from typing import Protocol, Optional, List

from domain.extraction.entities import ExtractionResult


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    token_count: int
    raw_response: dict = field(default_factory=dict)


@dataclass
class NLPEntity:
    """Entity extracted from text by NLP processor."""

    text: str
    label: str
    start: int
    end: int
    confidence: float


@dataclass
class NLPResult:
    """Results from NLP processing."""

    entities: List[NLPEntity]
    tokens: List[str]
    sentences: List[str]


@dataclass
class ReferenceRelation:
    """Relation from a reference source."""

    source_uri: str
    predicate: str
    target_uri: str
    weight: float


@dataclass
class ReferenceResult:
    """Result from a reference source lookup."""

    uri: str
    label: str
    description: Optional[str]
    relations: List[ReferenceRelation]


class LLMProvider(Protocol):
    """Provider port for LLM-based text completion and embedding."""

    def complete(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """Complete a prompt using the LLM."""
        ...

    def embed(self, text: str) -> List[float]:
        """Generate an embedding for text."""
        ...


class NLPProcessor(Protocol):
    """Processor port for natural language processing tasks."""

    def process(self, text: str) -> NLPResult:
        """Process text and return tokenized, sentence, and entity results."""
        ...

    def extract_entities(self, text: str) -> List[NLPEntity]:
        """Extract named entities from text."""
        ...


class ReferenceSource(Protocol):
    """Source port for external knowledge base lookups."""

    def lookup(self, term: str) -> Optional[ReferenceResult]:
        """Look up a term and return reference data."""
        ...

    def search(self, query: str, limit: int = 10) -> List[ReferenceResult]:
        """Search for terms and return reference data."""
        ...
