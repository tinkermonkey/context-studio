"""Performance tests for bulk ontology operations at various scales.

Tests measure bulk insert throughput, list/search response time, and update throughput
at multiple entity counts (100, 500, 1000) using both fake and real embedding adapters.
"""

import time

import pytest

from domain.ontology.services import OntologyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


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
    scheme = service.create_scheme(taxonomy.id, "Test Scheme", "Test scheme description")
    return taxonomy.id, scheme.id


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_classes,max_time",
    [
        (100, 0.01),
        (500, 0.1),
        (1000, 0.2),
    ],
)
def test_bulk_insert_fake_embedding(num_classes: int, max_time: float) -> None:
    """Measure throughput of inserting classes with fake embedding."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    start = time.perf_counter()
    for i in range(num_classes):
        service.create_class(scheme_id, f"class_{i:04d}", f"Class_{i:04d}", f"Description for class {i}")
    elapsed = time.perf_counter() - start

    print(
        f"\nBulk insert ({num_classes} classes, fake embedding): {elapsed:.4f}s"
        f" ({num_classes / elapsed:.1f} classes/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_classes,max_time",
    [
        (100, 0.5),
        (500, 1.0),
        (1000, 2.0),
    ],
)
def test_list_classes(num_classes: int, max_time: float) -> None:
    """Measure time to list classes from a scheme of specified size."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    # Insert classes
    for i in range(num_classes):
        service.create_class(scheme_id, f"class_{i:04d}", f"Class_{i:04d}")

    start = time.perf_counter()
    classes = service.list_classes(concept_scheme_id=scheme_id, limit=num_classes + 100)
    elapsed = time.perf_counter() - start

    print(f"\nList classes ({num_classes} entities): {elapsed:.4f}s")
    assert len(classes) == num_classes
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_classes,max_time",
    [
        (100, 0.01),
        (500, 0.1),
        (1000, 0.24),
    ],
)
def test_update_classes(num_classes: int, max_time: float) -> None:
    """Measure throughput of updating classes."""
    service, _ = _setup_ontology_context()
    _, scheme_id = _create_test_taxonomy_and_scheme(service)

    # Insert classes
    class_ids = []
    for i in range(num_classes):
        cls = service.create_class(scheme_id, f"class_{i:04d}", f"Class_{i:04d}")
        class_ids.append(cls.id)

    start = time.perf_counter()
    for i, class_id in enumerate(class_ids):
        service.update_class(
            class_id,
            title=f"Updated_Class_{i:04d}",
            description=f"Updated description {i}",
        )
    elapsed = time.perf_counter() - start

    print(
        f"\nUpdate classes ({num_classes} entities): {elapsed:.4f}s"
        f" ({num_classes / elapsed:.1f} updates/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.nlp
def test_bulk_insert_100_classes_real_embedding() -> None:
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
        service.create_class(scheme_id, f"class_{i:03d}", f"Class_{i:03d}", f"Description for class {i}")
    elapsed = time.perf_counter() - start

    print(
        f"\nBulk insert (100 classes, real embedding): {elapsed:.4f}s"
        f" ({100 / elapsed:.1f} classes/sec)"
    )
    assert elapsed < 30.0
