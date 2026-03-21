"""
Test Fakes - In-Memory Implementations for Testing.

Provides fake/stub implementations of domain port interfaces for use in
unit tests and domain testing without requiring external infrastructure.

These test doubles enable isolated testing of domain logic, service layers,
and business rules in a controlled environment.

See rearchitecture/e2e_test_strategy.md for testing strategy details.
"""

from tests.fakes.fake_ontology_repository import InMemoryOntologyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher

__all__ = [
    "InMemoryOntologyRepository",
    "FakeEmbeddingService",
    "FakeEventPublisher",
]
