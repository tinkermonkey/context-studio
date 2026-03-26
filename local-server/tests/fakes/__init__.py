"""Fake implementations of port interfaces for unit testing."""

from .fake_ontology_repository import FakeOntologyRepository
from .fake_embedding_service import FakeEmbeddingService
from .fake_event_publisher import FakeEventPublisher

__all__ = [
    "FakeOntologyRepository",
    "FakeEmbeddingService",
    "FakeEventPublisher",
]
