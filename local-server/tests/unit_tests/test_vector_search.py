"""
Unit tests for vector search functionality.

Tests the distance-to-similarity transformation, search_by_similarity method,
and get_node_links method.
"""

import pytest
import tempfile
import os
import numpy as np
from datetime import date
from uuid import uuid4

from reference_db.models import ReferenceNode, ReferenceLink
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager


class TestDistanceToSimilarity:
    """Test suite for distance-to-similarity transformation."""

    def test_distance_zero_returns_similarity_one(self):
        """
        Test edge case: distance 0.0 → similarity 1.0 (identical vectors).

        Validates TC-U002 requirement.
        """
        config = ReferenceConfig()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                similarity = manager._distance_to_similarity(0.0)
                assert similarity == 1.0, "Distance 0.0 should convert to similarity 1.0"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_distance_one_returns_similarity_zero(self):
        """
        Test edge case: distance 1.0 → similarity 0.0 (orthogonal vectors).

        Validates TC-U002 requirement.
        """
        config = ReferenceConfig()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                similarity = manager._distance_to_similarity(1.0)
                assert similarity == 0.0, "Distance 1.0 should convert to similarity 0.0"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_distance_two_returns_similarity_negative_one(self):
        """
        Test edge case: distance 2.0 → similarity -1.0 (opposite vectors).

        Validates TC-U002 requirement.
        """
        config = ReferenceConfig()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                similarity = manager._distance_to_similarity(2.0)
                assert similarity == -1.0, "Distance 2.0 should convert to similarity -1.0"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_intermediate_distance_values(self):
        """Test distance-to-similarity for intermediate values."""
        config = ReferenceConfig()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Test various intermediate values
                test_cases = [
                    (0.5, 0.5),
                    (0.25, 0.75),
                    (0.75, 0.25),
                    (1.5, -0.5),
                ]

                for distance, expected_similarity in test_cases:
                    similarity = manager._distance_to_similarity(distance)
                    assert abs(similarity - expected_similarity) < 1e-10, \
                        f"Distance {distance} should convert to similarity {expected_similarity}, got {similarity}"
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestSearchBySimilarity:
    """Test suite for search_by_similarity method."""

    @pytest.fixture
    def manager_with_data(self):
        """Create a manager with test data."""
        config = ReferenceConfig()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name

        manager = ReferenceManager(config, db_path=db_path)

        # Create simple embeddings (384 dimensions for sentence-transformers)
        def create_embedding(value: float) -> bytes:
            """Create a simple test embedding."""
            vec = np.full(384, value, dtype=np.float32)
            # Normalize to unit length
            vec = vec / np.linalg.norm(vec)
            return vec.tobytes()

        # Add test nodes with embeddings
        manager.add_reference_node(
            title="Person",
            definition="A human being",
            source="schema.org",
            external_id="Person",
            title_embedding=create_embedding(0.5),
            definition_embedding=create_embedding(0.5),
            embedding_dims=384
        )

        manager.add_reference_node(
            title="Organization",
            definition="An organized group of people",
            source="schema.org",
            external_id="Organization",
            title_embedding=create_embedding(0.6),
            definition_embedding=create_embedding(0.6),
            embedding_dims=384
        )

        manager.add_reference_node(
            title="Thing",
            definition="The most generic type",
            source="schema.org",
            external_id="Thing",
            title_embedding=create_embedding(0.1),
            definition_embedding=create_embedding(0.1),
            embedding_dims=384
        )

        yield manager, db_path, create_embedding

        manager.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_search_requires_query_text(self, manager_with_data):
        """Test that search_by_similarity requires non-empty query text."""
        manager, db_path, create_embedding = manager_with_data

        def embedding_gen(text: str) -> bytes:
            return create_embedding(0.5)

        with pytest.raises(ValueError, match="query_text cannot be empty"):
            manager.search_by_similarity("", embedding_generator=embedding_gen)

        with pytest.raises(ValueError, match="query_text cannot be empty"):
            manager.search_by_similarity("   ", embedding_generator=embedding_gen)

    def test_search_requires_embedding_generator(self, manager_with_data):
        """Test that search_by_similarity requires embedding_generator."""
        manager, db_path, create_embedding = manager_with_data

        with pytest.raises(ValueError, match="embedding_generator must be provided"):
            manager.search_by_similarity("test query", embedding_generator=None)

    def test_search_with_threshold_filtering(self, manager_with_data):
        """
        Test that search filters results by similarity threshold.

        Validates TC-U002 requirement for threshold filtering.
        """
        manager, db_path, create_embedding = manager_with_data

        def embedding_gen(text: str) -> bytes:
            # Query embedding that should match "Organization" best (0.6)
            return create_embedding(0.6)

        # Search with threshold 0.7 - should exclude results with similarity < 0.7
        results = manager.search_by_similarity(
            "organization",
            threshold=0.7,
            embedding_generator=embedding_gen
        )

        # With threshold 0.7, we should get very few or no results
        # since our test embeddings are simple and may not exceed 0.7 similarity
        # This validates that the HAVING clause is working
        assert isinstance(results, list), "Results should be a list"

        # All returned results must have similarity >= threshold
        for node, score in results:
            assert score >= 0.7, f"Result '{node.title}' has similarity score {score:.3f} which is less than threshold 0.7"

    def test_search_returns_ordered_results(self, manager_with_data):
        """Test that search returns results ordered by similarity descending."""
        manager, db_path, create_embedding = manager_with_data

        def embedding_gen(text: str) -> bytes:
            return create_embedding(0.5)

        results = manager.search_by_similarity(
            "test query",
            threshold=0.0,  # Low threshold to get all results
            embedding_generator=embedding_gen
        )

        # Verify results are ordered by similarity descending
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True), \
            f"Results should be ordered by similarity descending, got scores: {scores}"

    def test_search_respects_limit(self, manager_with_data):
        """Test that search respects the limit parameter."""
        manager, db_path, create_embedding = manager_with_data

        def embedding_gen(text: str) -> bytes:
            return create_embedding(0.5)

        results = manager.search_by_similarity(
            "test query",
            limit=2,
            threshold=0.0,
            embedding_generator=embedding_gen
        )

        assert len(results) <= 2, f"Results should not exceed limit of 2, got {len(results)} results"

    def test_search_filters_by_source(self, manager_with_data):
        """Test that search filters by source when provided."""
        manager, db_path, create_embedding = manager_with_data

        # Add a node from a different source
        manager.add_reference_node(
            title="Test Node",
            definition="Test definition",
            source="wikidata",
            external_id="Q123",
            title_embedding=create_embedding(0.5),
            definition_embedding=create_embedding(0.5),
            embedding_dims=384
        )

        def embedding_gen(text: str) -> bytes:
            return create_embedding(0.5)

        # Search only schema.org
        results = manager.search_by_similarity(
            "test query",
            source="schema.org",
            threshold=0.0,
            embedding_generator=embedding_gen
        )

        # All results should be from schema.org
        for node, score in results:
            assert node.source == "schema.org", \
                f"Result {node.title} is from {node.source}, expected schema.org"

    def test_search_invalid_threshold_raises_error(self, manager_with_data):
        """Test that invalid threshold values raise ValueError."""
        manager, db_path, create_embedding = manager_with_data

        def embedding_gen(text: str) -> bytes:
            return create_embedding(0.5)

        # Test threshold > 1.0
        with pytest.raises(ValueError, match="threshold must be between -1.0 and 1.0"):
            manager.search_by_similarity(
                "test query",
                threshold=1.5,
                embedding_generator=embedding_gen
            )

        # Test threshold < -1.0
        with pytest.raises(ValueError, match="threshold must be between -1.0 and 1.0"):
            manager.search_by_similarity(
                "test query",
                threshold=-1.5,
                embedding_generator=embedding_gen
            )

    def test_search_invalid_limit_raises_error(self, manager_with_data):
        """Test that invalid limit values raise ValueError."""
        manager, db_path, create_embedding = manager_with_data

        def embedding_gen(text: str) -> bytes:
            return create_embedding(0.5)

        # Test negative limit
        with pytest.raises(ValueError, match="limit must be a positive integer"):
            manager.search_by_similarity(
                "test query",
                limit=-1,
                embedding_generator=embedding_gen
            )

        # Test limit = 0
        with pytest.raises(ValueError, match="limit must be a positive integer"):
            manager.search_by_similarity(
                "test query",
                limit=0,
                embedding_generator=embedding_gen
            )

        # Test limit > 10000
        with pytest.raises(ValueError, match="limit must not exceed 10000"):
            manager.search_by_similarity(
                "test query",
                limit=10001,
                embedding_generator=embedding_gen
            )

    def test_search_empty_embedding_raises_error(self, manager_with_data):
        """Test that empty embedding from generator raises ValueError."""
        manager, db_path, create_embedding = manager_with_data

        def bad_embedding_gen(text: str) -> bytes:
            return b""

        with pytest.raises(ValueError, match="embedding_generator returned empty embedding"):
            manager.search_by_similarity(
                "test query",
                embedding_generator=bad_embedding_gen
            )


class TestGetNodeLinks:
    """Test suite for get_node_links method."""

    @pytest.fixture
    def manager_with_links(self):
        """Create a manager with test nodes and links."""
        config = ReferenceConfig()
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name

        manager = ReferenceManager(config, db_path=db_path)

        # Create test nodes
        node1 = manager.add_reference_node(
            title="Person",
            definition="A human being",
            source="schema.org",
            external_id="Person"
        )

        node2 = manager.add_reference_node(
            title="Organization",
            definition="An organized group of people",
            source="schema.org",
            external_id="Organization"
        )

        node3 = manager.add_reference_node(
            title="Thing",
            definition="The most generic type",
            source="schema.org",
            external_id="Thing"
        )

        # Create test links
        link1 = manager.add_reference_link(
            subject_node=node1.id,
            predicate="subClassOf",
            object_node=node3.id
        )

        link2 = manager.add_reference_link(
            subject_node=node2.id,
            predicate="subClassOf",
            object_node=node3.id
        )

        link3 = manager.add_reference_link(
            subject_node=node1.id,
            predicate="relatedTo",
            object_node=node2.id
        )

        yield manager, db_path, (node1, node2, node3), (link1, link2, link3)

        manager.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_get_outbound_links(self, manager_with_links):
        """Test retrieving outbound links."""
        manager, db_path, (node1, node2, node3), (link1, link2, link3) = manager_with_links

        # Get outbound links for node1
        links = manager.get_node_links(node1.id, direction="outbound")

        # Node1 has 2 outbound links
        assert len(links) == 2, f"Expected 2 outbound links for node1, got {len(links)}"

        # All links should have node1 as subject
        for link in links:
            assert link.subject_node == node1.id, \
                f"Outbound link should have query node {node1.id} as subject, got {link.subject_node}"

    def test_get_inbound_links(self, manager_with_links):
        """Test retrieving inbound links."""
        manager, db_path, (node1, node2, node3), (link1, link2, link3) = manager_with_links

        # Get inbound links for node3
        links = manager.get_node_links(node3.id, direction="inbound")

        # Node3 has 2 inbound links
        assert len(links) == 2, f"Expected 2 inbound links for node3, got {len(links)}"

        # All links should have node3 as object
        for link in links:
            assert link.object_node == node3.id, \
                f"Inbound link should have query node {node3.id} as object, got {link.object_node}"

    def test_get_both_direction_links(self, manager_with_links):
        """Test retrieving links in both directions."""
        manager, db_path, (node1, node2, node3), (link1, link2, link3) = manager_with_links

        # Get all links for node1
        links = manager.get_node_links(node1.id, direction="both")

        # Node1 has 2 outbound links and 0 inbound links
        assert len(links) == 2, f"Expected 2 total links for node1 (both directions), got {len(links)}"

    def test_get_links_with_predicate_filter(self, manager_with_links):
        """
        Test retrieving links filtered by predicate.

        Validates link retrieval with predicate filtering (exact match).
        """
        manager, db_path, (node1, node2, node3), (link1, link2, link3) = manager_with_links

        # Get only "subClassOf" links for node1
        links = manager.get_node_links(
            node1.id,
            direction="outbound",
            predicate="subClassOf"
        )

        # Node1 has 1 subClassOf link
        assert len(links) == 1, f"Expected 1 subClassOf link for node1, got {len(links)}"
        assert links[0].predicate == "subClassOf", \
            f"Filtered link should have predicate 'subClassOf', got '{links[0].predicate}'"

    def test_get_links_ordered_by_created_at_desc(self, manager_with_links):
        """
        Test that links are ordered by created_at DESC.

        Validates ordering requirement.
        """
        manager, db_path, (node1, node2, node3), (link1, link2, link3) = manager_with_links

        links = manager.get_node_links(node1.id, direction="outbound")

        # Verify ordering (newer links first)
        created_ats = [link.created_at for link in links]
        assert created_ats == sorted(created_ats, reverse=True), \
            f"Links should be ordered by created_at DESC, got timestamps: {created_ats}"

    def test_get_links_respects_limit(self, manager_with_links):
        """Test that get_node_links respects the limit parameter."""
        manager, db_path, (node1, node2, node3), (link1, link2, link3) = manager_with_links

        links = manager.get_node_links(node1.id, direction="outbound", limit=1)

        assert len(links) == 1, f"Should return only 1 link when limit=1, got {len(links)}"

    def test_get_links_invalid_direction_raises_error(self, manager_with_links):
        """Test that invalid direction raises ValueError."""
        manager, db_path, (node1, node2, node3), (link1, link2, link3) = manager_with_links

        with pytest.raises(ValueError, match="Invalid direction"):
            manager.get_node_links(node1.id, direction="invalid")

    def test_get_links_for_nonexistent_node_returns_empty(self, manager_with_links):
        """Test that querying links for non-existent node returns empty list."""
        manager, db_path, (node1, node2, node3), (link1, link2, link3) = manager_with_links

        links = manager.get_node_links("nonexistent-id", direction="both")

        assert links == [], f"Should return empty list for non-existent node, got {len(links)} links"
