"""
Smoke tests for fake implementations.

Validates that the fake implementations correctly satisfy their port interfaces
and provide the expected behavior for testing.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fakes import (  # noqa: E402
    InMemoryOntologyRepository,
    FakeEmbeddingService,
    FakeEventPublisher,
)
from domain.ontology.value_objects import NodeType, SearchCriteria  # noqa: E402, E501
from domain.ontology.entities import Taxonomy, Class, ConceptScheme  # noqa: E402, E501
from domain.ontology.events import ClassCreated  # noqa: E402


def test_in_memory_repository_basic_taxonomy_operations():
    """Test basic CRUD operations for taxonomies."""
    repo = InMemoryOntologyRepository()

    # Create
    t = Taxonomy(
        id="t1",
        title="Test Taxonomy",
        description="A test taxonomy",
        node_type=NodeType.TAXONOMY,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )
    saved = repo.save_taxonomy(t)
    assert saved == t

    # Read
    retrieved = repo.get_taxonomy("t1")
    assert retrieved == t
    assert retrieved.title == "Test Taxonomy"

    # List
    taxonomies = repo.list_taxonomies()
    assert len(taxonomies) == 1
    assert taxonomies[0] == t

    # Delete
    repo.delete_taxonomy("t1")
    assert repo.get_taxonomy("t1") is None
    assert len(repo.list_taxonomies()) == 0


def test_in_memory_repository_basic_scheme_operations():
    """Test basic CRUD operations for concept schemes."""
    repo = InMemoryOntologyRepository()

    scheme = ConceptScheme(
        id="s1",
        title="Test Scheme",
        description="A test scheme",
        taxonomy_id="t1",
        node_type=NodeType.CONCEPT_SCHEME,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )
    saved = repo.save_scheme(scheme)
    assert saved == scheme

    retrieved = repo.get_scheme("s1")
    assert retrieved == scheme

    repo.delete_scheme("s1")
    assert repo.get_scheme("s1") is None


def test_in_memory_repository_list_schemes_filters_by_taxonomy():
    """Test that list_schemes filters by taxonomy_id."""
    repo = InMemoryOntologyRepository()

    s1 = ConceptScheme(
        id="s1",
        title="Scheme 1",
        description=None,
        taxonomy_id="t1",
        node_type=NodeType.CONCEPT_SCHEME,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )
    s2 = ConceptScheme(
        id="s2",
        title="Scheme 2",
        description=None,
        taxonomy_id="t2",
        node_type=NodeType.CONCEPT_SCHEME,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )

    repo.save_scheme(s1)
    repo.save_scheme(s2)

    assert len(repo.list_schemes("t1")) == 1
    assert len(repo.list_schemes("t2")) == 1
    assert repo.list_schemes("t1")[0].id == "s1"


def test_in_memory_repository_basic_class_operations():
    """Test basic CRUD operations for classes."""
    repo = InMemoryOntologyRepository()

    c = Class(
        id="c1",
        title="Test Class",
        definition="A test class",
        scheme_id="s1",
        taxonomy_id="t1",
        node_type=NodeType.CLASS,
        parent_id=None,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )
    saved = repo.save_class(c)
    assert saved == c

    retrieved = repo.get_class("c1")
    assert retrieved == c

    repo.delete_class("c1")
    assert repo.get_class("c1") is None


def test_in_memory_repository_search_classes_by_query():
    """Test class search with query criteria."""
    repo = InMemoryOntologyRepository()

    c1 = Class(
        id="c1",
        title="Python Programming",
        definition="A programming language",
        scheme_id="s1",
        taxonomy_id="t1",
        node_type=NodeType.CLASS,
        parent_id=None,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )
    c2 = Class(
        id="c2",
        title="Java Programming",
        definition="Another programming language",
        scheme_id="s1",
        taxonomy_id="t1",
        node_type=NodeType.CLASS,
        parent_id=None,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )

    repo.save_class(c1)
    repo.save_class(c2)

    # Search by title
    results = repo.search_classes(SearchCriteria(query="python"))
    assert len(results) == 1
    assert results[0].id == "c1"

    # Search by definition
    results = repo.search_classes(SearchCriteria(query="programming"))
    assert len(results) == 2


def test_in_memory_repository_search_classes_with_filters():
    """Test class search with taxonomy and scheme filters."""
    repo = InMemoryOntologyRepository()

    c1 = Class(
        id="c1",
        title="Test",
        definition=None,
        scheme_id="s1",
        taxonomy_id="t1",
        node_type=NodeType.CLASS,
        parent_id=None,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )
    c2 = Class(
        id="c2",
        title="Test",
        definition=None,
        scheme_id="s2",
        taxonomy_id="t2",
        node_type=NodeType.CLASS,
        parent_id=None,
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )

    repo.save_class(c1)
    repo.save_class(c2)

    # Filter by scheme_id
    results = repo.search_classes(
        SearchCriteria(query="test", scheme_id="s1")
    )
    assert len(results) == 1
    assert results[0].scheme_id == "s1"

    # Filter by taxonomy_id
    results = repo.search_classes(
        SearchCriteria(query="test", taxonomy_id="t2")
    )
    assert len(results) == 1
    assert results[0].taxonomy_id == "t2"


def test_in_memory_repository_search_classes_respects_limit():
    """Test that search respects the limit parameter."""
    repo = InMemoryOntologyRepository()

    for i in range(5):
        c = Class(
            id=f"c{i}",
            title="Test",
            definition=None,
            scheme_id="s1",
            taxonomy_id="t1",
            node_type=NodeType.CLASS,
            parent_id=None,
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )
        repo.save_class(c)

    results = repo.search_classes(SearchCriteria(query="test", limit=2))
    assert len(results) == 2


def test_in_memory_repository_individual_methods_raise_not_implemented():
    """Test that Individual methods raise NotImplementedError."""
    repo = InMemoryOntologyRepository()

    try:
        repo.get_individual("i1")
        assert False, "Expected NotImplementedError"
    except NotImplementedError as e:
        assert "Individual support is deferred" in str(e)

    try:
        from domain.ontology.entities import Individual
        ind = Individual(
            id="i1",
            title="Test Individual",
            class_id="c1",
            node_type=NodeType.INDIVIDUAL,
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )
        repo.save_individual(ind)
        assert False, "Expected NotImplementedError"
    except NotImplementedError as e:
        assert "Individual support is deferred" in str(e)


def test_fake_embedding_service_deterministic():
    """Test that FakeEmbeddingService generates deterministic embeddings."""
    svc = FakeEmbeddingService()

    # Same text produces same embedding
    emb1 = svc.generate("hello")
    emb2 = svc.generate("hello")
    assert emb1 == emb2

    # Different text produces different embedding
    emb3 = svc.generate("world")
    assert emb1 != emb3

    # Embedding is 32 bytes (SHA-256)
    assert len(emb1) == 32
    assert isinstance(emb1, bytes)


def test_fake_embedding_service_similarity():
    """Test embedding similarity calculation."""
    svc = FakeEmbeddingService()

    # Identical embeddings have similarity 1.0
    emb_a = svc.generate("same")
    emb_b = svc.generate("same")
    assert svc.similarity(emb_a, emb_b) == 1.0

    # Different embeddings have similarity < 1.0
    emb_c = svc.generate("different")
    similarity = svc.similarity(emb_a, emb_c)
    assert 0.0 <= similarity < 1.0


def test_fake_embedding_service_batch_generate():
    """Test batch generation of embeddings."""
    svc = FakeEmbeddingService()

    texts = ["hello", "world", "test"]
    embeddings = svc.batch_generate(texts)

    assert len(embeddings) == 3
    assert all(isinstance(e, bytes) for e in embeddings)
    assert embeddings[0] == svc.generate("hello")
    assert embeddings[1] == svc.generate("world")
    assert embeddings[2] == svc.generate("test")


def test_fake_event_publisher_collects_events():
    """Test that FakeEventPublisher collects published events."""
    pub = FakeEventPublisher()

    event1 = ClassCreated(
        class_id="c1", title="Test 1", scheme_id="s1", taxonomy_id="t1"
    )
    event2 = ClassCreated(
        class_id="c2", title="Test 2", scheme_id="s1", taxonomy_id="t1"
    )

    pub.publish(event1)
    pub.publish(event2)

    events = pub.get_events()
    assert len(events) == 2
    assert events[0] == event1
    assert events[1] == event2


def test_fake_event_publisher_subscription():
    """Test event publisher subscription mechanism."""
    pub = FakeEventPublisher()

    collected_events = []

    def handler(event):
        collected_events.append(event)

    pub.subscribe(ClassCreated, handler)

    event = ClassCreated(
        class_id="c1", title="Test", scheme_id="s1", taxonomy_id="t1"
    )
    pub.publish(event)

    assert len(collected_events) == 1
    assert collected_events[0] == event


def test_fake_event_publisher_get_events_of_type():
    """Test filtering events by type."""
    pub = FakeEventPublisher()

    from domain.ontology.events import ClassUpdated, ClassDeleted

    event1 = ClassCreated(
        class_id="c1", title="Test", scheme_id="s1", taxonomy_id="t1"
    )
    event2 = ClassUpdated(class_id="c1", changed_fields=("title",))
    event3 = ClassDeleted(class_id="c1", title="Test")

    pub.publish(event1)
    pub.publish(event2)
    pub.publish(event3)

    created_events = pub.get_events_of_type(ClassCreated)
    assert len(created_events) == 1
    assert created_events[0] == event1

    updated_events = pub.get_events_of_type(ClassUpdated)
    assert len(updated_events) == 1
    assert updated_events[0] == event2


def test_fake_event_publisher_clear():
    """Test clearing events from the publisher."""
    pub = FakeEventPublisher()

    event = ClassCreated(
        class_id="c1", title="Test", scheme_id="s1", taxonomy_id="t1"
    )
    pub.publish(event)

    assert len(pub.get_events()) == 1

    pub.clear()
    assert len(pub.get_events()) == 0


def test_in_memory_repository_satisfies_protocol():
    """Smoke test verifying InMemoryOntologyRepository satisfies OntologyRepository protocol."""  # noqa: E501

    repo = InMemoryOntologyRepository()

    # Verify structural protocol compliance by checking all protocol methods exist  # noqa: E501
    protocol_methods = {
        "get_taxonomy",
        "list_taxonomies",
        "save_taxonomy",
        "delete_taxonomy",
        "get_scheme",
        "list_schemes",
        "save_scheme",
        "delete_scheme",
        "get_class",
        "list_classes",
        "search_classes",
        "save_class",
        "delete_class",
        "get_relationship",
        "list_relationships",
        "save_relationship",
        "delete_relationship",
        "get_property_definition",
        "list_property_definitions",
        "save_property_definition",
        "delete_property_definition",
        "get_individual",
        "save_individual",
    }

    for method_name in protocol_methods:
        assert hasattr(repo, method_name), f"Missing method: {method_name}"
        assert callable(
            getattr(repo, method_name)
        ), f"Method not callable: {method_name}"
