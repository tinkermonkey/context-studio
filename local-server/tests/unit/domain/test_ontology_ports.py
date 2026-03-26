"""
Unit tests for port interfaces in the Ontology Management bounded context.

Tests verify:
- Port Protocol definitions are syntactically correct
- Ports can be imported from the module
- Structural subtyping works (implementations don't need to inherit)
"""

import sys
import os
from datetime import datetime
from typing import Callable, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.ontology.ports import (
    EmbeddingService,
    EventPublisher,
    OntologyRepository,
)
from domain.ontology.events import DomainEvent, ClassCreated
from domain.ontology.entities import Taxonomy, ConceptScheme, Class, Relationship, PropertyDefinition, Individual
from domain.ontology.value_objects import SearchCriteria


class FakeOntologyRepository:
    """
    Fake implementation of OntologyRepository Protocol.

    This demonstrates structural subtyping — it doesn't inherit from
    OntologyRepository, but implements its interface structurally.
    """

    def __init__(self):
        self.taxonomies = {}
        self.concept_schemes = {}
        self.classes = {}
        self.relationships = {}
        self.property_definitions = {}

    def get_taxonomy(self, taxonomy_id: str) -> Optional[Taxonomy]:
        return self.taxonomies.get(taxonomy_id)

    def list_taxonomies(self) -> list[Taxonomy]:
        return list(self.taxonomies.values())

    def save_taxonomy(self, taxonomy: Taxonomy) -> None:
        self.taxonomies[taxonomy.id] = taxonomy

    def delete_taxonomy(self, taxonomy_id: str) -> None:
        if taxonomy_id in self.taxonomies:
            del self.taxonomies[taxonomy_id]

    def get_concept_scheme(self, scheme_id: str) -> Optional[ConceptScheme]:
        return self.concept_schemes.get(scheme_id)

    def list_concept_schemes(self, taxonomy_id: Optional[str] = None) -> list[ConceptScheme]:
        schemes = list(self.concept_schemes.values())
        if taxonomy_id:
            schemes = [s for s in schemes if s.taxonomy_id == taxonomy_id]
        return schemes

    def save_concept_scheme(self, scheme: ConceptScheme) -> None:
        self.concept_schemes[scheme.id] = scheme

    def delete_concept_scheme(self, scheme_id: str) -> None:
        if scheme_id in self.concept_schemes:
            del self.concept_schemes[scheme_id]

    def get_class(self, class_id: str) -> Optional[Class]:
        return self.classes.get(class_id)

    def list_classes(
        self,
        scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Class]:
        classes = list(self.classes.values())
        if scheme_id:
            classes = [c for c in classes if c.scheme_id == scheme_id]
        if parent_class_id:
            classes = [c for c in classes if c.parent_class_id == parent_class_id]
        return classes[offset : offset + limit]

    def search_classes(self, criteria: SearchCriteria) -> list[Class]:
        return []

    def count_classes(self, scheme_id: Optional[str] = None) -> int:
        classes = list(self.classes.values())
        if scheme_id:
            classes = [c for c in classes if c.scheme_id == scheme_id]
        return len(classes)

    def save_class(self, cls: Class) -> None:
        self.classes[cls.id] = cls

    def delete_class(self, class_id: str) -> None:
        if class_id in self.classes:
            del self.classes[class_id]

    def get_relationship(self, relationship_id: str) -> Optional[Relationship]:
        return self.relationships.get(relationship_id)

    def list_relationships(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        property_id: Optional[str] = None,
    ) -> list[Relationship]:
        rels = list(self.relationships.values())
        if source_id:
            rels = [r for r in rels if r.source_id == source_id]
        if target_id:
            rels = [r for r in rels if r.target_id == target_id]
        if property_id:
            rels = [r for r in rels if r.property_definition_id == property_id]
        return rels

    def save_relationship(self, relationship: Relationship) -> None:
        self.relationships[relationship.id] = relationship

    def delete_relationship(self, relationship_id: str) -> None:
        if relationship_id in self.relationships:
            del self.relationships[relationship_id]

    def get_property_definition(self, property_id: str) -> Optional[PropertyDefinition]:
        return self.property_definitions.get(property_id)

    def get_property_definition_by_identifier(self, identifier: str) -> Optional[PropertyDefinition]:
        for prop in self.property_definitions.values():
            if prop.identifier == identifier:
                return prop
        return None

    def list_property_definitions(self, is_relevant: Optional[bool] = None) -> list[PropertyDefinition]:
        return list(self.property_definitions.values())

    def save_property_definition(self, prop: PropertyDefinition) -> None:
        self.property_definitions[prop.id] = prop

    def delete_property_definition(self, property_id: str) -> None:
        if property_id in self.property_definitions:
            del self.property_definitions[property_id]

    def get_individual(self, individual_id: str) -> Optional[Individual]:
        raise NotImplementedError()

    def list_individuals(self, class_id: Optional[str] = None) -> list[Individual]:
        raise NotImplementedError()

    def save_individual(self, individual: Individual) -> None:
        raise NotImplementedError()

    def delete_individual(self, individual_id: str) -> None:
        raise NotImplementedError()

    def get_all_entities_and_relationships(self, taxonomy_id: str) -> dict:
        return {}


class FakeEmbeddingService:
    """
    Fake implementation of EmbeddingService Protocol.

    This demonstrates structural subtyping — it doesn't inherit from
    EmbeddingService, but implements its interface structurally.
    """

    def embed_text(self, text: str) -> list[float]:
        # Simple fake: convert text to list of floats
        hash_val = hash(text)
        return [float((hash_val >> (i * 8)) & 0xFF) / 256.0 for i in range(8)]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        # Simple fake: return 0.5
        return 0.5


class FakeEventPublisher:
    """
    Fake implementation of EventPublisher Protocol.

    This demonstrates structural subtyping — it doesn't inherit from
    EventPublisher, but implements its interface structurally.
    """

    def __init__(self):
        self.published_events = []
        self.handlers = {}

    def publish(self, event: DomainEvent) -> None:
        self.published_events.append(event)
        event_type = type(event)
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                handler(event)

    def subscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None:
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)


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
        now = datetime.utcnow()
        tax = Taxonomy(id="tax-1", title="Test", created_at=now, updated_at=now)

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

    def test_embedding_service_embed_text_returns_list_float(self):
        """EmbeddingService.embed_text returns list of floats."""
        service = FakeEmbeddingService()
        result = service.embed_text("test text")
        assert isinstance(result, list)
        assert all(isinstance(f, float) for f in result)

    def test_embedding_service_embed_batch_returns_list_of_list_float(self):
        """EmbeddingService.embed_batch returns list of list of floats."""
        service = FakeEmbeddingService()
        result = service.embed_batch(["text1", "text2"])
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, list) for item in result)
        assert all(isinstance(f, float) for item in result for f in item)

    def test_embedding_service_similarity_returns_float(self):
        """EmbeddingService.similarity returns float."""
        service = FakeEmbeddingService()
        emb1 = service.embed_text("text1")
        emb2 = service.embed_text("text2")
        result = service.similarity(emb1, emb2)
        assert isinstance(result, float)

    def test_embedding_service_similarity_accepts_list_float(self):
        """EmbeddingService.similarity accepts list of float arguments."""
        service = FakeEmbeddingService()
        emb_a = [0.1, 0.2, 0.3, 0.4]
        emb_b = [0.2, 0.3, 0.4, 0.5]
        result = service.similarity(emb_a, emb_b)
        assert isinstance(result, float)


class TestEventPublisherProtocol:
    """Tests for EventPublisher Protocol."""

    def test_event_publisher_can_be_used_with_fake(self):
        """EventPublisher accepts a structural subtype implementation."""
        publisher: EventPublisher = FakeEventPublisher()
        assert publisher is not None

    def test_event_publisher_publish_accepts_domain_event(self):
        """EventPublisher.publish accepts DomainEvent instances."""
        publisher = FakeEventPublisher()
        now = datetime.utcnow()
        event = ClassCreated(
            event_id="evt-1",
            occurred_at=now,
            aggregate_id="class-1",
            class_id="class-1",
            title="Test Class",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
        )
        publisher.publish(event)
        assert len(publisher.published_events) == 1
        assert publisher.published_events[0] == event

    def test_event_publisher_subscribe_accepts_event_type_and_handler(self):
        """EventPublisher.subscribe accepts event type and handler callable."""
        publisher = FakeEventPublisher()

        handler_called = []

        def handler(event):
            handler_called.append(event)

        publisher.subscribe(ClassCreated, handler)

        now = datetime.utcnow()
        event = ClassCreated(
            event_id="evt-1",
            occurred_at=now,
            aggregate_id="class-1",
            class_id="class-1",
            title="Test Class",
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
        )
        publisher.publish(event)

        assert len(handler_called) == 1
        assert handler_called[0] == event

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

        now = datetime.utcnow()
        event = ClassCreated(
            event_id="evt-1",
            occurred_at=now,
            aggregate_id="class-1",
            class_id="class-1",
            title="Test Class",
            scheme_id="scheme-1",
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
