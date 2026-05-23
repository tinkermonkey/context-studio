"""
Unit tests for port interfaces in the Ontology Management bounded context.

Tests verify:
- Port Protocol definitions are syntactically correct
- Ports can be imported from the module
- Structural subtyping works (implementations don't need to inherit)
"""

from datetime import datetime, timezone

from domain.ontology.entities import Taxonomy
from domain.ontology.events import ClassCreated
from domain.ontology.ports import (
    EmbeddingService,
    OntologyRepository,
)
from domain.ports import EventPublisher
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


class TestOntologyRepositoryProtocol:
    """Tests for OntologyRepository Protocol."""

    def test_ontology_repository_can_be_used_with_fake(self):
        """OntologyRepository accepts a structural subtype implementation."""
        repo: OntologyRepository = FakeOntologyRepository()
        assert repo is not None

    def test_ontology_repository_all_methods_defined_in_protocol(self):
        """OntologyRepository Protocol has all required methods."""
        expected_methods = [
            # Taxonomy
            "get_taxonomy",
            "list_taxonomies",
            "save_taxonomy",
            "delete_taxonomy",
            # ConceptScheme
            "get_concept_scheme",
            "list_concept_schemes",
            "save_concept_scheme",
            "delete_concept_scheme",
            # Class
            "get_class",
            "list_classes",
            "search_classes",
            "count_classes",
            "save_class",
            "delete_class",
            # Relationship
            "get_relationship",
            "list_relationships",
            "save_relationship",
            "delete_relationship",
            # PropertyDefinition
            "get_property_definition",
            "get_property_definition_by_identifier",
            "list_property_definitions",
            "save_property_definition",
            "delete_property_definition",
            # Individual (deferred)
            "get_individual",
            "list_individuals",
            "save_individual",
            "delete_individual",
            # Bulk
            "get_all_entities_and_relationships",
        ]
        repo = FakeOntologyRepository()
        for method_name in expected_methods:
            assert hasattr(repo, method_name), f"Repository missing method: {method_name}"

    def test_ontology_repository_fake_taxonomy_operations(self):
        """FakeOntologyRepository implements taxonomy operations."""
        repo = FakeOntologyRepository()
        now = datetime.now(timezone.utc)
        tax = Taxonomy(id="tax-1", title="Test", created_at=now, last_modified=now)

        repo.save_taxonomy(tax)
        retrieved = repo.get_taxonomy("tax-1")
        assert retrieved is not None
        assert retrieved.id == "tax-1"
        assert retrieved.title == "Test"

        all_taxs = repo.list_taxonomies()
        assert len(all_taxs) == 1

        repo.delete_taxonomy("tax-1")
        assert repo.get_taxonomy("tax-1") is None

    def test_ontology_repository_get_returns_none_for_missing(self):
        """Repository returns None for missing entities."""
        repo = FakeOntologyRepository()
        assert repo.get_taxonomy("missing") is None
        assert repo.get_concept_scheme("missing") is None
        assert repo.get_class("missing") is None


class TestEmbeddingServiceProtocol:
    """Tests for EmbeddingService Protocol."""

    def test_embedding_service_can_be_used_with_fake(self):
        """EmbeddingService accepts a structural subtype implementation."""
        service: EmbeddingService = FakeEmbeddingService()
        assert service is not None

    def test_embedding_service_embed_returns_list_of_floats(self):
        """EmbeddingService.embed returns list[float] matching the Protocol (FR-1.15)."""
        service = FakeEmbeddingService()
        result = service.embed("test text")
        assert isinstance(result, list)
        assert len(result) == 8  # Fixed dimension
        assert all(isinstance(f, float) for f in result)

    def test_embedding_service_embed_returns_deterministic_embedding(self):
        """EmbeddingService.embed returns deterministic embeddings for same text (FR-1.22)."""
        service = FakeEmbeddingService()
        emb1 = service.embed("hello world")
        emb2 = service.embed("hello world")
        assert emb1 == emb2, "Same text should produce identical embeddings"

    def test_embedding_service_embed_batch_returns_list_of_float_lists(self):
        """EmbeddingService.embed_batch returns list[list[float]]."""
        service = FakeEmbeddingService()
        result = service.embed_batch(["text1", "text2"])
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(emb, list) for emb in result)
        assert all(all(isinstance(f, float) for f in emb) for emb in result)
        assert all(len(emb) == 8 for emb in result)

    def test_embedding_service_similarity_returns_float(self):
        """EmbeddingService.similarity returns float."""
        service = FakeEmbeddingService()
        emb1 = service.embed("text1")
        emb2 = service.embed("text2")
        result = service.similarity(emb1, emb2)
        assert isinstance(result, float)

    def test_embedding_service_similarity_accepts_float_lists(self):
        """EmbeddingService.similarity accepts list[float] arguments."""
        service = FakeEmbeddingService()
        embedding1 = service.embed("hello")
        embedding2 = service.embed("hello")
        result = service.similarity(embedding1, embedding2)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0
        assert result == 1.0, "Identical embeddings should have 1.0 similarity"


class TestEventPublisherProtocol:
    """Tests for EventPublisher Protocol."""

    def test_event_publisher_can_be_used_with_fake(self):
        """EventPublisher accepts a structural subtype implementation."""
        publisher: EventPublisher = FakeEventPublisher()
        assert publisher is not None

    def test_event_publisher_publish_accepts_domain_event(self):
        """EventPublisher.publish accepts DomainEvent instances."""
        publisher = FakeEventPublisher()
        event = ClassCreated(
            class_id="class-1",
            title="Test Class",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
        )
        publisher.publish(event)
        events = publisher.get_events()
        assert len(events) == 1
        assert events[0] == event

    def test_event_publisher_subscribe_accepts_event_type_and_handler(self):
        """EventPublisher.subscribe accepts event type and handler callable."""
        publisher = FakeEventPublisher()

        handler_called = []

        def handler(event):
            handler_called.append(event)

        publisher.subscribe(ClassCreated, handler)

        event = ClassCreated(
            class_id="class-1",
            title="Test Class",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
        )
        publisher.publish(event)

        assert len(handler_called) == 1
        assert handler_called[0] == event
        # Verify event was also stored
        events = publisher.get_events()
        assert len(events) == 1

    def test_event_publisher_multiple_subscribers(self):
        """EventPublisher supports multiple subscribers for same event type."""
        publisher = FakeEventPublisher()

        handler1_called = []
        handler2_called = []

        def handler1(event):
            handler1_called.append(event)

        def handler2(event):
            handler2_called.append(event)

        publisher.subscribe(ClassCreated, handler1)
        publisher.subscribe(ClassCreated, handler2)

        event = ClassCreated(
            class_id="class-1",
            title="Test Class",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
        )
        publisher.publish(event)

        assert len(handler1_called) == 1
        assert len(handler2_called) == 1


class TestPortsImportability:
    """Tests that all ports can be imported from the module."""

    def test_all_ports_importable(self):
        """All three port Protocols are importable from domain.ontology.ports."""
        ports = [
            OntologyRepository,
            EmbeddingService,
            EventPublisher,
        ]
        for port in ports:
            assert port is not None
