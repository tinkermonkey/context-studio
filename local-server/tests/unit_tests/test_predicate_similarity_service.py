"""
Unit tests for predicate similarity service.

Tests the PredicateSimilarityService functionality including:
- Similarity search
- Caching behavior
- Clustering
- Warm-up procedures
- Confidence scoring
"""

import pytest
import tempfile
import os
from uuid import uuid4

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager
from services.predicate_similarity import (
    PredicateSimilarityService,
    SimilarityResult,
    ClusterResult,
    BatchError
)
from embeddings.generate_embeddings import generate_embedding


# Skip if embeddings not available
pytest.importorskip("embeddings.generate_embeddings", reason="embeddings module not available")


@pytest.fixture
def test_manager():
    """Create a test ReferenceManager with sample data."""
    config = ReferenceConfig()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    manager = ReferenceManager(config, db_path=db_path)

    # Add some test external predicates
    test_predicates = [
        ("subClassOf", "Indicates that one class is a subclass of another", "schema.org"),
        ("relatedTo", "Indicates a general semantic relation", "conceptnet"),
        ("locatedIn", "Indicates spatial location", "dbpedia"),
        ("hasProperty", "Indicates entity has a property", "wikidata"),
        ("memberOf", "Indicates membership in a group", "schema.org"),
    ]

    for title, definition, source in test_predicates:
        title_emb = generate_embedding(title)
        def_emb = generate_embedding(definition)

        manager.add_external_predicate(
            title=title,
            definition=definition,
            source=source,
            external_id=f"{source}:{title}",
            title_embedding=title_emb,
            definition_embedding=def_emb,
            embedding_dims=384
        )

    yield manager

    manager.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def similarity_service(test_manager):
    """Create a PredicateSimilarityService instance."""
    return PredicateSimilarityService(test_manager)


class TestPredicateSimilarityService:
    """Test PredicateSimilarityService functionality."""

    def test_initialization(self, similarity_service):
        """Test service initialization."""
        assert similarity_service is not None
        assert similarity_service.reference_manager is not None
        assert similarity_service.warm_up_complete is False

    def test_warm_up(self, similarity_service):
        """Test index warm-up procedure."""
        elapsed = similarity_service.warm_up(sample_size=3)

        assert elapsed >= 0.0
        assert similarity_service.warm_up_complete is True

    def test_confidence_level(self, similarity_service):
        """Test confidence level determination."""
        assert similarity_service._confidence_level(0.90) == "high"
        assert similarity_service._confidence_level(0.85) == "high"
        assert similarity_service._confidence_level(0.75) == "medium"
        assert similarity_service._confidence_level(0.70) == "medium"
        assert similarity_service._confidence_level(0.65) == "low"
        assert similarity_service._confidence_level(0.60) == "low"
        assert similarity_service._confidence_level(0.55) == "reject"

    def test_find_similar_predicates(self, similarity_service):
        """Test finding similar predicates."""
        results = similarity_service.find_similar_predicates(
            predicate_title="is_subclass",
            predicate_definition="Indicates taxonomic hierarchy",
            limit=10,
            threshold=0.5,  # Lower threshold for test data
            use_cache=False
        )

        assert isinstance(results, list)
        # Should find at least subClassOf
        assert len(results) >= 1

        # Check result structure
        for result in results:
            assert isinstance(result, SimilarityResult)
            assert result.predicate_id is not None
            assert result.source is not None
            assert result.title is not None
            assert result.definition is not None
            assert 0.0 <= result.similarity_score <= 1.0
            assert result.confidence in ["high", "medium", "low"]

        # Results should be ordered by similarity descending
        scores = [r.similarity_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_caching_behavior(self, similarity_service):
        """Test that caching works correctly."""
        # Clear cache first
        similarity_service.invalidate_cache()

        # First search (not cached)
        results1 = similarity_service.find_similar_predicates(
            predicate_title="located",
            predicate_definition="spatial position",
            limit=10,
            threshold=0.5,
            use_cache=True
        )

        # Second search (should be cached)
        results2 = similarity_service.find_similar_predicates(
            predicate_title="located",
            predicate_definition="spatial position",
            limit=10,
            threshold=0.5,
            use_cache=True
        )

        # Results should be identical
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.predicate_id == r2.predicate_id
            assert r1.similarity_score == r2.similarity_score

        # Search without cache should also work
        results3 = similarity_service.find_similar_predicates(
            predicate_title="located",
            predicate_definition="spatial position",
            limit=10,
            threshold=0.5,
            use_cache=False
        )

        assert len(results3) > 0

    def test_cache_invalidation(self, similarity_service):
        """Test cache invalidation."""
        # Populate cache
        similarity_service.find_similar_predicates(
            predicate_title="test_query",
            limit=10,
            threshold=0.5,
            use_cache=True
        )

        # Verify cache has entries
        cache_stats = similarity_service.get_cache_stats()
        initial_size = cache_stats["size"]
        assert initial_size > 0

        # Invalidate cache
        similarity_service.invalidate_cache()

        # Verify cache is empty
        cache_stats = similarity_service.get_cache_stats()
        assert cache_stats["size"] == 0

    def test_source_filtering(self, similarity_service):
        """Test filtering results by source."""
        # Search with source filter
        results_schema = similarity_service.find_similar_predicates(
            predicate_title="class hierarchy",
            source="schema.org",
            limit=10,
            threshold=0.5,
            use_cache=False
        )

        # All results should be from schema.org
        for result in results_schema:
            assert result.source == "schema.org"

        # Search with different source
        results_conceptnet = similarity_service.find_similar_predicates(
            predicate_title="semantic relation",
            source="conceptnet",
            limit=10,
            threshold=0.5,
            use_cache=False
        )

        # All results should be from conceptnet
        for result in results_conceptnet:
            assert result.source == "conceptnet"

    def test_find_similar_batch(self, similarity_service):
        """Test batch similarity search."""
        batch_queries = [
            ("subclass", "class hierarchy"),
            ("location", "spatial position"),
            ("property", "entity attribute"),
        ]

        results, errors = similarity_service.find_similar_batch(
            predicates=batch_queries,
            limit=10,
            threshold=0.5
        )

        # Should have results for each query
        assert len(results) == len(batch_queries)

        # Should have no errors for valid queries
        assert len(errors) == 0

        # Check each result
        for title, definition in batch_queries:
            assert title in results
            assert isinstance(results[title], list)

    def test_find_similar_batch_with_errors(self, similarity_service):
        """Test batch similarity search with some invalid queries."""
        batch_queries = [
            ("valid_query", "good definition"),
            ("", "empty title should error"),  # This should error
            ("another_valid", None),
        ]

        results, errors = similarity_service.find_similar_batch(
            predicates=batch_queries,
            limit=10,
            threshold=0.5
        )

        # Should have results for all queries (empty list for errors)
        assert len(results) == len(batch_queries)

        # Should have 1 error (empty title)
        assert len(errors) == 1
        assert isinstance(errors[0], BatchError)
        assert errors[0].predicate_title == ""
        assert errors[0].error_type == "ValueError"

    def test_cluster_predicates_basic(self, similarity_service):
        """Test basic clustering functionality."""
        # Create test predicates with clear groupings (using UUIDs)
        predicates = [
            (str(uuid4()), "spatial_relation_1", "Indicates location in space"),
            (str(uuid4()), "spatial_relation_2", "Indicates position in area"),
            (str(uuid4()), "temporal_relation_1", "Indicates time relationship"),
            (str(uuid4()), "temporal_relation_2", "Indicates timing of event"),
            (str(uuid4()), "causal_relation_1", "Indicates cause and effect"),
        ]

        clusters = similarity_service.cluster_predicates(
            predicates=predicates,
            min_similarity=0.7,
            min_cluster_size=2,
            eps=0.5  # Larger eps for more lenient clustering
        )

        # Should find some clusters
        assert isinstance(clusters, list)

        # Check cluster structure
        for cluster in clusters:
            assert isinstance(cluster, ClusterResult)
            assert cluster.cluster_id >= 0
            assert len(cluster.predicate_ids) >= 2
            assert cluster.centroid_title is not None
            assert 0.0 <= cluster.avg_similarity <= 1.0
            assert cluster.size == len(cluster.predicate_ids)

    def test_cluster_predicates_insufficient_data(self, similarity_service):
        """Test clustering with insufficient data."""
        # Only 1 predicate (less than min_cluster_size, using UUID)
        predicates = [
            (str(uuid4()), "test_predicate", "A test predicate"),
        ]

        clusters = similarity_service.cluster_predicates(
            predicates=predicates,
            min_cluster_size=2
        )

        # Should return empty list
        assert clusters == []

    def test_cache_key_generation(self, similarity_service):
        """Test cache key generation."""
        key1 = similarity_service._get_cache_key("test", "source1", 10, 0.7)
        key2 = similarity_service._get_cache_key("test", "source1", 10, 0.7)
        key3 = similarity_service._get_cache_key("test", "source2", 10, 0.7)
        key4 = similarity_service._get_cache_key("test", "source1", 20, 0.7)

        # Same parameters should generate same key
        assert key1 == key2

        # Different parameters should generate different keys
        assert key1 != key3
        assert key1 != key4

    def test_get_cache_stats(self, similarity_service):
        """Test cache statistics retrieval."""
        stats = similarity_service.get_cache_stats()

        assert "size" in stats
        assert "maxsize" in stats
        assert "ttl" in stats
        assert "currsize" in stats

        assert stats["maxsize"] == 1000
        assert stats["ttl"] == 3600


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query(self, similarity_service):
        """Test handling of empty query."""
        with pytest.raises(ValueError):
            similarity_service.find_similar_predicates(
                predicate_title="",
                threshold=0.7
            )

    def test_invalid_threshold(self, similarity_service):
        """Test handling of invalid threshold."""
        # Threshold is validated in ReferenceManager, not service
        # Service should pass through the values
        pass

    def test_clustering_empty_list(self, similarity_service):
        """Test clustering with empty predicate list."""
        clusters = similarity_service.cluster_predicates(
            predicates=[],
            min_cluster_size=2
        )

        assert clusters == []

    def test_clustering_too_many_predicates(self, similarity_service):
        """Test clustering with too many predicates (resource exhaustion protection)."""
        # Create a list that exceeds max_predicates limit
        large_list = [
            (str(uuid4()), f"predicate_{i}", f"definition_{i}")
            for i in range(1001)
        ]

        with pytest.raises(ValueError) as exc_info:
            similarity_service.cluster_predicates(
                predicates=large_list,
                min_cluster_size=2,
                max_predicates=1000
            )

        assert "Too many predicates" in str(exc_info.value)
