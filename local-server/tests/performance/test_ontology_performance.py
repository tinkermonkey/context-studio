"""Performance tests for bulk ontology operations at various scales.

Tests measure bulk insert throughput, list/search response time, and update throughput
at multiple entity counts (100, 500, 1000) using both fake and real embedding adapters.
"""

import sys
import os
import time
import pytest
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.ontology.services import OntologyService
from domain.ontology.entities import Taxonomy, ConceptScheme, Class
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher


def _setup_ontology_context() -> tuple[OntologyService, FakeOntologyRepository]:
    """Set up ontology service with fake dependencies.

    Returns:
        Tuple of (service, repository) for testing
    """
    repository = FakeOntologyRepository()
    embedding_service = FakeEmbeddingService()
    event_publisher = FakeEventPublisher()
    service = OntologyService(repository, embedding_service, event_publisher)
    return service, repository


def _create_test_taxonomy_and_scheme(service: OntologyService) -> tuple[str, str]:
    """Create a taxonomy and concept scheme for testing.

    Args:
        service: OntologyService instance

    Returns:
        Tuple of (taxonomy_id, scheme_id)
    """
    taxonomy = service.create_taxonomy("Test Taxonomy", "Test description")
    scheme = service.create_scheme(
        taxonomy.id,
        "Test Scheme",
        "Test scheme description"
    )
    return taxonomy.id, scheme.id


@pytest.mark.performance
def test_bulk_insert_100_classes_fake_embedding():
    """Measure throughput of inserting 100 classes with fake embedding."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    start = time.perf_counter()
    for i in range(100):
        service.create_class(
            scheme_id,
            f"Class_{i:03d}",
            f"Description for class {i}"
        )
    elapsed = time.perf_counter() - start

    print(f"\nBulk insert (100 classes, fake embedding): {elapsed:.4f}s ({100 / elapsed:.1f} classes/sec)")
    assert elapsed < 5.0


@pytest.mark.performance
def test_bulk_insert_500_classes_fake_embedding():
    """Measure throughput of inserting 500 classes with fake embedding."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    start = time.perf_counter()
    for i in range(500):
        service.create_class(
            scheme_id,
            f"Class_{i:04d}",
            f"Description for class {i}"
        )
    elapsed = time.perf_counter() - start

    print(f"\nBulk insert (500 classes, fake embedding): {elapsed:.4f}s ({500 / elapsed:.1f} classes/sec)")
    assert elapsed < 15.0


@pytest.mark.performance
def test_bulk_insert_1000_classes_fake_embedding():
    """Measure throughput of inserting 1000 classes with fake embedding."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    start = time.perf_counter()
    for i in range(1000):
        service.create_class(
            scheme_id,
            f"Class_{i:04d}",
            f"Description for class {i}"
        )
    elapsed = time.perf_counter() - start

    print(f"\nBulk insert (1000 classes, fake embedding): {elapsed:.4f}s ({1000 / elapsed:.1f} classes/sec)")
    assert elapsed < 30.0


@pytest.mark.performance
def test_list_classes_100_entities():
    """Measure time to list classes from a 100-class scheme."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    # Insert 100 classes
    for i in range(100):
        service.create_class(scheme_id, f"Class_{i:03d}")

    start = time.perf_counter()
    classes = service.list_classes(concept_scheme_id=scheme_id, limit=200)
    elapsed = time.perf_counter() - start

    print(f"\nList classes (100 entities): {elapsed:.4f}s")
    assert len(classes) == 100
    assert elapsed < 0.5


@pytest.mark.performance
def test_list_classes_500_entities():
    """Measure time to list classes from a 500-class scheme."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    # Insert 500 classes
    for i in range(500):
        service.create_class(scheme_id, f"Class_{i:04d}")

    start = time.perf_counter()
    classes = service.list_classes(concept_scheme_id=scheme_id, limit=600)
    elapsed = time.perf_counter() - start

    print(f"\nList classes (500 entities): {elapsed:.4f}s")
    assert len(classes) == 500
    assert elapsed < 1.0


@pytest.mark.performance
def test_list_classes_1000_entities():
    """Measure time to list classes from a 1000-class scheme."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    # Insert 1000 classes
    for i in range(1000):
        service.create_class(scheme_id, f"Class_{i:04d}")

    start = time.perf_counter()
    classes = service.list_classes(concept_scheme_id=scheme_id, limit=1100)
    elapsed = time.perf_counter() - start

    print(f"\nList classes (1000 entities): {elapsed:.4f}s")
    assert len(classes) == 1000
    assert elapsed < 2.0


@pytest.mark.performance
def test_update_classes_100_entities():
    """Measure throughput of updating 100 classes."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    # Insert 100 classes
    class_ids = []
    for i in range(100):
        cls = service.create_class(scheme_id, f"Class_{i:03d}")
        class_ids.append(cls.id)

    start = time.perf_counter()
    for i, class_id in enumerate(class_ids):
        service.update_class(
            class_id,
            title=f"Updated_Class_{i:03d}",
            description=f"Updated description {i}"
        )
    elapsed = time.perf_counter() - start

    print(f"\nUpdate classes (100 entities): {elapsed:.4f}s ({100 / elapsed:.1f} updates/sec)")
    assert elapsed < 5.0


@pytest.mark.performance
def test_update_classes_500_entities():
    """Measure throughput of updating 500 classes."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    # Insert 500 classes
    class_ids = []
    for i in range(500):
        cls = service.create_class(scheme_id, f"Class_{i:04d}")
        class_ids.append(cls.id)

    start = time.perf_counter()
    for i, class_id in enumerate(class_ids):
        service.update_class(
            class_id,
            title=f"Updated_Class_{i:04d}",
            description=f"Updated description {i}"
        )
    elapsed = time.perf_counter() - start

    print(f"\nUpdate classes (500 entities): {elapsed:.4f}s ({500 / elapsed:.1f} updates/sec)")
    assert elapsed < 15.0


@pytest.mark.performance
def test_update_classes_1000_entities():
    """Measure throughput of updating 1000 classes."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    # Insert 1000 classes
    class_ids = []
    for i in range(1000):
        cls = service.create_class(scheme_id, f"Class_{i:04d}")
        class_ids.append(cls.id)

    start = time.perf_counter()
    for i, class_id in enumerate(class_ids):
        service.update_class(
            class_id,
            title=f"Updated_Class_{i:04d}",
            description=f"Updated description {i}"
        )
    elapsed = time.perf_counter() - start

    print(f"\nUpdate classes (1000 entities): {elapsed:.4f}s ({1000 / elapsed:.1f} updates/sec)")
    assert elapsed < 30.0


@pytest.mark.performance
@pytest.mark.nlp
def test_bulk_insert_100_classes_real_embedding():
    """Measure throughput of inserting 100 classes with real SentenceTransformer embedding.

    This test requires the sentence-transformers library to be installed.
    """
    try:
        from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
    except ImportError:
        pytest.skip("SentenceTransformer not installed")

    repository = FakeOntologyRepository()
    embedding_service = SentenceTransformerEmbedding()
    event_publisher = FakeEventPublisher()
    service = OntologyService(repository, embedding_service, event_publisher)

    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    start = time.perf_counter()
    for i in range(100):
        service.create_class(
            scheme_id,
            f"Class_{i:03d}",
            f"Description for class {i}"
        )
    elapsed = time.perf_counter() - start

    print(f"\nBulk insert (100 classes, real embedding): {elapsed:.4f}s ({100 / elapsed:.1f} classes/sec)")
    assert elapsed < 30.0
