"""
Performance tests for predicate similarity search (Phase 3).

Tests that vector similarity search meets performance requirements:
- PT-VS-001: <200ms p95 for 10K predicates
- PT-VS-002: <200ms p95 for 50K predicates
- PT-VS-003: <800ms p95 for batch of 10 predicates
- PT-VS-004: <300ms p95 for 10 concurrent users
- PT-VS-006: <50ms p95 for cached searches
- PT-VS-007: <5 seconds for index warm-up
"""

import pytest
import tempfile
import os
import time
import statistics
import concurrent.futures
from datetime import date

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


class TestVectorSearchPerformance:
    """Test vector search performance against SLA targets."""

    def test_pt_vs_001_10k_predicates_latency(self, large_external_predicates_dataset):
        """
        PT-VS-001: Vector similarity search <200ms p95 for 10K predicates.

        This test verifies that searches complete within the SLA when searching
        across 10K external predicates.
        """
        manager, db_path = large_external_predicates_dataset
        service = PredicateSimilarityService(manager)

        # Warm up the index first
        service.warm_up(sample_size=10)

        # Test queries
        test_queries = [
            ("relationship", "A semantic relationship between concepts"),
            ("has_property", "Indicates that an entity has a specific property"),
            ("related_to", "General semantic relation between entities"),
            ("is_a", "Taxonomic relationship indicating class membership"),
            ("part_of", "Mereological relationship indicating composition"),
            ("located_in", "Spatial relationship indicating location"),
            ("derived_from", "Etymological or causal derivation"),
            ("causes", "Causal relationship between events"),
            ("similar_to", "Similarity relationship"),
            ("opposite_of", "Antonymy relationship"),
        ]

        search_times = []

        for title, definition in test_queries:
            start_time = time.perf_counter()

            results = service.find_similar_predicates(
                predicate_title=title,
                predicate_definition=definition,
                limit=100,
                threshold=0.7,
                use_cache=False  # Don't use cache for performance testing
            )

            end_time = time.perf_counter()
            search_time_ms = (end_time - start_time) * 1000
            search_times.append(search_time_ms)

        # Calculate statistics
        avg_time = statistics.mean(search_times)
        median_time = statistics.median(search_times)
        max_time = max(search_times)
        min_time = min(search_times)
        p95_time = statistics.quantiles(search_times, n=20)[18]  # 95th percentile

        print(f"\n{'='*70}")
        print(f"PT-VS-001: Vector Search Performance (10K predicates)")
        print(f"{'='*70}")
        print(f"Test queries: {len(test_queries)}")
        print(f"Dataset size: 10,000 predicates")
        print(f"\nLatency Statistics:")
        print(f"  Average:    {avg_time:7.2f} ms")
        print(f"  Median:     {median_time:7.2f} ms")
        print(f"  Min:        {min_time:7.2f} ms")
        print(f"  Max:        {max_time:7.2f} ms")
        print(f"  P95:        {p95_time:7.2f} ms")
        print(f"\nSLA Requirement: <200ms p95")
        print(f"Status: {'✓ PASS' if p95_time < 200.0 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        # Verify SLA
        assert p95_time < 200.0, \
            f"PT-VS-001 FAILED: P95 latency {p95_time:.2f}ms exceeds 200ms SLA"

        assert avg_time < 200.0, \
            f"PT-VS-001 FAILED: Average latency {avg_time:.2f}ms exceeds 200ms SLA"

    def test_pt_vs_003_batch_search_latency(self, large_external_predicates_dataset):
        """
        PT-VS-003: Batch search (10 predicates) <800ms p95.

        This test verifies that batch searches can process 10 predicates
        within the SLA.
        """
        manager, db_path = large_external_predicates_dataset
        service = PredicateSimilarityService(manager)

        # Warm up
        service.warm_up(sample_size=5)

        # Batch of 10 predicate queries
        batch_queries = [
            ("has_part", "Indicates a part-whole relationship"),
            ("located_at", "Specifies spatial location"),
            ("member_of", "Indicates membership in a group"),
            ("owns", "Indicates ownership relationship"),
            ("created_by", "Specifies creator or author"),
            ("used_for", "Indicates purpose or function"),
            ("made_of", "Specifies material composition"),
            ("works_for", "Indicates employment relationship"),
            ("related", "General semantic relation"),
            ("connected_to", "Indicates connection or link"),
        ]

        batch_times = []

        for _ in range(10):  # Run batch 10 times for statistics
            start_time = time.perf_counter()

            results = service.find_similar_batch(
                predicates=batch_queries,
                limit=100,
                threshold=0.7
            )

            end_time = time.perf_counter()
            batch_time_ms = (end_time - start_time) * 1000
            batch_times.append(batch_time_ms)

        # Calculate statistics
        avg_time = statistics.mean(batch_times)
        p95_time = statistics.quantiles(batch_times, n=20)[18]

        print(f"\n{'='*70}")
        print(f"PT-VS-003: Batch Search Performance")
        print(f"{'='*70}")
        print(f"Batch size: 10 predicates")
        print(f"Test runs: {len(batch_times)}")
        print(f"\nLatency Statistics:")
        print(f"  Average:    {avg_time:7.2f} ms")
        print(f"  P95:        {p95_time:7.2f} ms")
        print(f"\nSLA Requirement: <800ms p95")
        print(f"Status: {'✓ PASS' if p95_time < 800.0 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        # Verify SLA
        assert p95_time < 800.0, \
            f"PT-VS-003 FAILED: P95 batch latency {p95_time:.2f}ms exceeds 800ms SLA"

    def test_pt_vs_004_concurrent_search_latency(self, large_external_predicates_dataset):
        """
        PT-VS-004: Concurrent searches (10 users) <300ms p95.

        This test simulates 10 concurrent users performing searches and
        verifies that performance remains within SLA.
        """
        manager, db_path = large_external_predicates_dataset
        service = PredicateSimilarityService(manager)

        # Warm up
        service.warm_up(sample_size=5)

        # Test queries for concurrent execution
        test_queries = [
            ("relationship", "Semantic relationship"),
            ("property", "Entity property"),
            ("location", "Spatial relation"),
            ("temporal", "Time-based relation"),
            ("causal", "Cause-effect relationship"),
            ("similarity", "Similarity measure"),
            ("composition", "Part-whole structure"),
            ("attribution", "Attribution relation"),
            ("sequence", "Sequential ordering"),
            ("hierarchy", "Hierarchical structure"),
        ]

        def run_search(query_tuple):
            """Execute a single search and return timing."""
            title, definition = query_tuple
            start_time = time.perf_counter()

            service.find_similar_predicates(
                predicate_title=title,
                predicate_definition=definition,
                limit=100,
                threshold=0.7,
                use_cache=False
            )

            return (time.perf_counter() - start_time) * 1000

        # Run concurrent searches multiple times
        all_times = []

        for round_num in range(5):  # 5 rounds of concurrent execution
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(run_search, q) for q in test_queries]
                round_times = [f.result() for f in concurrent.futures.as_completed(futures)]
                all_times.extend(round_times)

        # Calculate statistics
        avg_time = statistics.mean(all_times)
        p95_time = statistics.quantiles(all_times, n=20)[18]
        max_time = max(all_times)

        print(f"\n{'='*70}")
        print(f"PT-VS-004: Concurrent Search Performance")
        print(f"{'='*70}")
        print(f"Concurrent users: 10")
        print(f"Test rounds: 5")
        print(f"Total searches: {len(all_times)}")
        print(f"\nLatency Statistics:")
        print(f"  Average:    {avg_time:7.2f} ms")
        print(f"  Max:        {max_time:7.2f} ms")
        print(f"  P95:        {p95_time:7.2f} ms")
        print(f"\nSLA Requirement: <300ms p95")
        print(f"Status: {'✓ PASS' if p95_time < 300.0 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        # Verify SLA
        assert p95_time < 300.0, \
            f"PT-VS-004 FAILED: P95 concurrent latency {p95_time:.2f}ms exceeds 300ms SLA"

    def test_pt_vs_006_cached_search_latency(self, large_external_predicates_dataset):
        """
        PT-VS-006: Cached searches <50ms p95.

        This test verifies that cached searches return results much faster
        than non-cached searches.
        """
        manager, db_path = large_external_predicates_dataset
        service = PredicateSimilarityService(manager)

        # Warm up and populate cache
        service.warm_up(sample_size=5)

        test_query = ("relationship", "A semantic relationship between concepts")

        # First search to populate cache
        service.find_similar_predicates(
            predicate_title=test_query[0],
            predicate_definition=test_query[1],
            limit=100,
            threshold=0.7,
            use_cache=True
        )

        # Now measure cached searches
        cached_times = []

        for _ in range(50):  # 50 cached searches
            start_time = time.perf_counter()

            service.find_similar_predicates(
                predicate_title=test_query[0],
                predicate_definition=test_query[1],
                limit=100,
                threshold=0.7,
                use_cache=True
            )

            end_time = time.perf_counter()
            cached_time_ms = (end_time - start_time) * 1000
            cached_times.append(cached_time_ms)

        # Calculate statistics
        avg_time = statistics.mean(cached_times)
        p95_time = statistics.quantiles(cached_times, n=20)[18]
        max_time = max(cached_times)
        min_time = min(cached_times)

        print(f"\n{'='*70}")
        print(f"PT-VS-006: Cached Search Performance")
        print(f"{'='*70}")
        print(f"Cached searches: {len(cached_times)}")
        print(f"\nLatency Statistics:")
        print(f"  Average:    {avg_time:7.2f} ms")
        print(f"  Min:        {min_time:7.2f} ms")
        print(f"  Max:        {max_time:7.2f} ms")
        print(f"  P95:        {p95_time:7.2f} ms")
        print(f"\nSLA Requirement: <50ms p95")
        print(f"Status: {'✓ PASS' if p95_time < 50.0 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        # Verify SLA
        assert p95_time < 50.0, \
            f"PT-VS-006 FAILED: P95 cached latency {p95_time:.2f}ms exceeds 50ms SLA"

        assert avg_time < 50.0, \
            f"PT-VS-006 FAILED: Average cached latency {avg_time:.2f}ms exceeds 50ms SLA"

    def test_pt_vs_007_index_warmup_time(self, large_external_predicates_dataset):
        """
        PT-VS-007: Index warm-up <5 seconds.

        This test verifies that the index warm-up procedure completes
        within the SLA on startup.
        """
        manager, db_path = large_external_predicates_dataset
        service = PredicateSimilarityService(manager)

        # Measure warm-up time
        start_time = time.perf_counter()
        elapsed = service.warm_up(sample_size=10)
        actual_elapsed = time.perf_counter() - start_time

        print(f"\n{'='*70}")
        print(f"PT-VS-007: Index Warm-up Performance")
        print(f"{'='*70}")
        print(f"Sample size: 10 queries")
        print(f"Warm-up time: {elapsed:.3f}s (reported)")
        print(f"Actual time: {actual_elapsed:.3f}s (measured)")
        print(f"\nSLA Requirement: <5 seconds")
        print(f"Status: {'✓ PASS' if elapsed < 5.0 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        # Verify SLA
        assert elapsed < 5.0, \
            f"PT-VS-007 FAILED: Warm-up time {elapsed:.3f}s exceeds 5s SLA"

        # Verify warm-up was actually completed
        assert service.warm_up_complete, \
            "PT-VS-007 FAILED: Warm-up not marked as complete"


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

        print(f"\nClustering Performance (10 predicates):")
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

        print(f"\nClustering Performance (100 predicates):")
        print(f"  Time: {elapsed:.2f}ms")
        print(f"  Clusters: {len(clusters)}")

        # Clustering should complete in reasonable time
        # Allow more time for 100 predicates (10x the data)
        assert elapsed < 30000, \
            f"Clustering 100 predicates took {elapsed:.2f}ms (should be <30000ms)"
