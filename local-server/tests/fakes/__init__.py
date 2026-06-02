"""Fake implementations of port interfaces for unit testing."""

from .fake_embedding_service import FakeEmbeddingService
from .fake_event_publisher import FakeEventPublisher
from .fake_graph_engine import FakeGraphEngine
from .fake_llm_provider import FakeLLMProvider
from .fake_nlp_processor import FakeNLPProcessor
from .fake_ontology_repository import FakeOntologyRepository
from .fake_reference_source import FakeReferenceSource
from .fake_semantic_query_engine import FakeSemanticQueryEngine

__all__ = [
    "FakeEmbeddingService",
    "FakeEventPublisher",
    "FakeGraphEngine",
    "FakeLLMProvider",
    "FakeNLPProcessor",
    "FakeOntologyRepository",
    "FakeReferenceSource",
    "FakeSemanticQueryEngine",
]
