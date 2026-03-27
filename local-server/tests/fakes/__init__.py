"""Fake implementations of port interfaces for unit testing."""

from .fake_ontology_repository import FakeOntologyRepository
from .fake_embedding_service import FakeEmbeddingService
from .fake_event_publisher import FakeEventPublisher
from .fake_graph_engine import FakeGraphEngine
from .fake_semantic_query_engine import FakeSemanticQueryEngine

__all__ = [
    "FakeOntologyRepository",
    "FakeEmbeddingService",
    "FakeEventPublisher",
    "FakeGraphEngine",
    "FakeSemanticQueryEngine",
]
