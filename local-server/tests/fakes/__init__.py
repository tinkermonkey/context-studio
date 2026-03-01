"""
Test Fakes - In-Memory Implementations for Testing.

Provides fake/stub implementations of domain port interfaces for use in
unit tests and domain testing without requiring external infrastructure.

Includes:
- InMemoryOntologyRepository: Dict-based ontology storage
- FakeEmbeddingService: Deterministic embedding generation
- FakeEventPublisher: Event collection and replay for assertions

See rearchitecture/e2e_test_strategy.md for testing strategy details.
"""
