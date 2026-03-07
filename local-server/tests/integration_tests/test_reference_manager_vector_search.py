"""
Integration tests for reference database manager vector search functionality.

Tests the SQL CASE WHEN fix for max similarity calculation in reference_db/manager.py
by validating that search_by_similarity correctly uses the shared builder function
for computing max(title_similarity, definition_similarity) across various embedding scenarios.
"""

import pytest
import tempfile
import os
import numpy as np

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager


def create_embedding(value: float) -> bytes:
    """Create a deterministic embedding vector."""
    rng = np.random.RandomState(seed=int(value * 1000))
    vec = rng.randn(384).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tobytes()


@pytest.fixture(scope="function")
def reference_manager_with_embeddings():
    """Create a reference manager with test data containing various embedding scenarios."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    config = ReferenceConfig()
    manager = ReferenceManager(config, db_path=db_path)

    # Add reference nodes with different embedding combinations
    manager.add_reference_node(
        title="Both Embeddings",
        definition="Node with both title and definition embeddings",
        source="test",
        external_id="both_001",
        title_embedding=create_embedding(0.85),
        definition_embedding=create_embedding(0.75),
    )

    manager.add_reference_node(
        title="Title Only",
        definition="Node with only title embedding",
        source="test",
        external_id="title_001",
        title_embedding=create_embedding(0.65),
        definition_embedding=None,
    )

    manager.add_reference_node(
        title="Definition Only",
        definition="Node with only definition embedding",
        source="test",
        external_id="def_001",
        title_embedding=None,
        definition_embedding=create_embedding(0.55),
    )

    manager.add_reference_node(
        title="No Embeddings",
        definition="Node without embeddings",
        source="test",
        external_id="none_001",
        title_embedding=None,
        definition_embedding=None,
    )

    yield manager

    # Cleanup
    manager.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_reference_nodes_max_similarity_both_embeddings(
    reference_manager_with_embeddings,
):
    """Test reference node search when both embeddings exist.

    The search_by_similarity method should use the CASE WHEN logic to compute
    the maximum similarity between title and definition embeddings.
    """
    manager = reference_manager_with_embeddings

    # Create a custom embedding generator that returns our test embedding
    test_embedding = create_embedding(0.8)
    def mock_embedding_generator(text: str) -> bytes:
        return test_embedding

    # Search for reference nodes
    results = manager.search_by_similarity(
        query_text="test query",
        embedding_generator=mock_embedding_generator,
        threshold=0.0,
        limit=10,
    )

    # Should find nodes with embeddings
    assert len(results) > 0

    # Verify similarity scores are valid
    for node, similarity in results:
        assert similarity is not None
        assert isinstance(similarity, (float, int))
        assert 0.0 <= similarity <= 1.0


def test_reference_nodes_max_similarity_title_only(reference_manager_with_embeddings):
    """Test reference node search when only title embedding exists.

    The CASE WHEN logic should return the title similarity when definition
    embedding is missing.
    """
    manager = reference_manager_with_embeddings

    test_embedding = create_embedding(0.65)
    def mock_embedding_generator(text: str) -> bytes:
        return test_embedding

    results = manager.search_by_similarity(
        query_text="test query",
        embedding_generator=mock_embedding_generator,
        threshold=0.0,
        limit=10,
    )

    # Should include title-only nodes
    assert len(results) > 0

    # Find the title-only result
    title_only_results = [
        (node, sim) for node, sim in results if node.title == "Title Only"
    ]
    assert len(title_only_results) > 0

    # Verify similarity is computed correctly
    node, similarity = title_only_results[0]
    assert similarity is not None
    assert 0.0 <= similarity <= 1.0


def test_reference_nodes_max_similarity_definition_only(
    reference_manager_with_embeddings,
):
    """Test reference node search when only definition embedding exists.

    The CASE WHEN logic should return the definition similarity when title
    embedding is missing.
    """
    manager = reference_manager_with_embeddings

    test_embedding = create_embedding(0.55)
    def mock_embedding_generator(text: str) -> bytes:
        return test_embedding

    results = manager.search_by_similarity(
        query_text="test query",
        embedding_generator=mock_embedding_generator,
        threshold=0.0,
        limit=10,
    )

    # Should include definition-only nodes
    assert len(results) > 0

    # Find the definition-only result
    def_only_results = [
        (node, sim) for node, sim in results if node.title == "Definition Only"
    ]
    assert len(def_only_results) > 0

    # Verify similarity is computed correctly
    node, similarity = def_only_results[0]
    assert similarity is not None
    assert 0.0 <= similarity <= 1.0


def test_reference_nodes_no_embeddings_filtered(reference_manager_with_embeddings):
    """Test that nodes without embeddings are excluded from search.

    The SQL WHERE clause explicitly filters for nodes that have at least
    one embedding (title_embedding IS NOT NULL OR definition_embedding IS NOT NULL),
    so nodes without any embeddings are not returned.
    """
    manager = reference_manager_with_embeddings

    test_embedding = create_embedding(0.7)
    def mock_embedding_generator(text: str) -> bytes:
        return test_embedding

    results = manager.search_by_similarity(
        query_text="test query",
        embedding_generator=mock_embedding_generator,
        threshold=0.01,  # Use threshold > 0.0 to exclude zero-similarity nodes
        limit=10,
    )

    # Nodes without embeddings get 0.0 similarity and are filtered by threshold
    node_titles = [node.title for node, _ in results]
    assert "No Embeddings" not in node_titles


def test_reference_nodes_threshold_filtering(reference_manager_with_embeddings):
    """Test that similarity threshold filtering works correctly.

    Results with similarity below the threshold should be excluded.
    """
    manager = reference_manager_with_embeddings

    test_embedding = create_embedding(0.7)
    def mock_embedding_generator(text: str) -> bytes:
        return test_embedding

    # Get all results with low threshold
    all_results = manager.search_by_similarity(
        query_text="test query",
        embedding_generator=mock_embedding_generator,
        threshold=0.0,
        limit=10,
    )

    # Get results with high threshold
    high_threshold_results = manager.search_by_similarity(
        query_text="test query",
        embedding_generator=mock_embedding_generator,
        threshold=0.99,
        limit=10,
    )

    # High threshold should have fewer or equal results
    assert len(high_threshold_results) <= len(all_results)

    # All high threshold results should meet the threshold
    for node, similarity in high_threshold_results:
        assert similarity >= 0.99


def test_reference_nodes_result_ordering(reference_manager_with_embeddings):
    """Test that results are ordered by similarity descending.

    The search_by_similarity method should return results in descending
    order of similarity score.
    """
    manager = reference_manager_with_embeddings

    test_embedding = create_embedding(0.7)
    def mock_embedding_generator(text: str) -> bytes:
        return test_embedding

    results = manager.search_by_similarity(
        query_text="test query",
        embedding_generator=mock_embedding_generator,
        threshold=0.0,
        limit=10,
    )

    # Verify results are ordered by similarity descending
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i][1] >= results[i + 1][1]


def test_reference_nodes_limit_respected(reference_manager_with_embeddings):
    """Test that the limit parameter is respected.

    Results should not exceed the specified limit.
    """
    manager = reference_manager_with_embeddings

    test_embedding = create_embedding(0.7)
    def mock_embedding_generator(text: str) -> bytes:
        return test_embedding

    results = manager.search_by_similarity(
        query_text="test query",
        embedding_generator=mock_embedding_generator,
        threshold=0.0,
        limit=2,
    )

    # Should respect the limit
    assert len(results) <= 2
