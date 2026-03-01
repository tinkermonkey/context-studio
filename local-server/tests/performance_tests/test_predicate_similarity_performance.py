"""
Clustering performance tests for predicate similarity.

These tests validate the clustering algorithm performance with realistic predicate sets.

Note: High-latency performance tests (PT-VS-001, PT-VS-003, PT-VS-004, PT-VS-007) have been
removed as they are not suitable for CI/CD. These tests require generating embeddings for
10K+ predicates, which takes 100+ seconds and masks actual search performance. Performance
validation should be done with pre-populated databases in dedicated benchmarking environments.
"""

import pytest
import tempfile
import os
import time

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from services.predicate_similarity import PredicateSimilarityService
from embeddings.generate_embeddings import generate_embedding


# Skip if embeddings not available
pytest.importorskip("embeddings.generate_embeddings", reason="embeddings module not available")


@pytest.fixture(scope="module")
def large_external_predicates_dataset():
    """
    Create a test dataset with 10K+ external predicates for performance testing.

    This simulates a production scenario with multiple knowledge sources.
    """
    config = ReferenceConfig()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    manager = ReferenceManager(config, db_path=db_path)

    # Create 10K external predicates across multiple sources
    sources = {
        "conceptnet": 40,  # ConceptNet relations
        "dbpedia": 760,  # DBpedia properties
        "wikidata": 9200  # WikiData properties
    }

    predicate_count = 0

    for source, count in sources.items():
        for i in range(count):
            title = f"{source}_predicate_{i}"
            definition = f"A predicate from {source} with index {i}. Used for relationship modeling."

            # Generate real embeddings
            title_emb = generate_embedding(title)
            def_emb = generate_embedding(definition)

            manager.add_external_predicate(
                title=title,
                definition=definition,
                source=source,
                external_id=f"{source}:{i}",
                title_embedding=title_emb,
                definition_embedding=def_emb,
                embedding_dims=384
            )
            predicate_count += 1

    print(f"\nCreated test dataset with {predicate_count} external predicates")

    yield manager, db_path

    manager.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestClusteringPerformance:
    """Test predicate clustering performance."""

    def test_clustering_10_predicates(self, large_external_predicates_dataset):
        """
        Test clustering performance with 10 predicates.

        Clustering should be reasonably fast for small predicate sets.
        """
        manager, db_path = large_external_predicates_dataset
        service = PredicateSimilarityService(manager)

        # Create 10 test predicates
        test_predicates = [
            (f"pred_{i}", f"Predicate {i}", f"Definition for predicate {i}")
            for i in range(10)
        ]

        start_time = time.perf_counter()

        clusters = service.cluster_predicates(
            predicates=test_predicates,
            min_similarity=0.7,
            min_cluster_size=2,
            eps=0.3
        )

        elapsed = (time.perf_counter() - start_time) * 1000

        print("\nClustering Performance (10 predicates):")
        print(f"  Time: {elapsed:.2f}ms")
        print(f"  Clusters: {len(clusters)}")

        # Clustering should complete in reasonable time
        assert elapsed < 5000, \
            f"Clustering 10 predicates took {elapsed:.2f}ms (should be <5000ms)"

    def test_clustering_100_predicates(self, large_external_predicates_dataset):
        """
        Test clustering performance with 100 predicates.

        This is a more realistic workload for clustering operations.
        """
        manager, db_path = large_external_predicates_dataset
        service = PredicateSimilarityService(manager)

        # Create 100 test predicates with some semantic groupings
        test_predicates = []
        for i in range(100):
            category = i % 5  # Create 5 semantic categories
            test_predicates.append((
                f"pred_{i}",
                f"Category_{category}_predicate_{i}",
                f"A predicate in category {category} with index {i}"
            ))

        start_time = time.perf_counter()

        clusters = service.cluster_predicates(
            predicates=test_predicates,
            min_similarity=0.7,
            min_cluster_size=2,
            eps=0.3
        )

        elapsed = (time.perf_counter() - start_time) * 1000

        print("\nClustering Performance (100 predicates):")
        print(f"  Time: {elapsed:.2f}ms")
        print(f"  Clusters: {len(clusters)}")

        # Clustering should complete in reasonable time
        # Allow more time for 100 predicates (10x the data)
        assert elapsed < 30000, \
            f"Clustering 100 predicates took {elapsed:.2f}ms (should be <30000ms)"
