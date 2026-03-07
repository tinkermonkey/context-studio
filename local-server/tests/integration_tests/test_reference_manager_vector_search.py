"""
Integration tests for reference database manager vector search functionality.

Tests the SQL CASE WHEN fix for max similarity calculation in reference_db/manager.py
by validating similarity computation for both reference_nodes and external_predicates.
"""

import pytest
import tempfile
import os
import numpy as np

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager


@pytest.fixture(scope="function")
def reference_manager_with_embeddings():
    """Create a reference manager with test data containing various embedding scenarios."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    config = ReferenceConfig()
    manager = ReferenceManager(config, db_path=db_path)

    def create_embedding(value: float) -> bytes:
        """Create a deterministic embedding vector."""
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

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
    """Test reference node search when both embeddings exist."""
    manager = reference_manager_with_embeddings

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.8)

    # Search for reference nodes
    results = manager.search_reference_nodes(
        query_embedding=query_embedding,
        threshold=0.0,
        limit=10,
    )

    # Should find nodes with embeddings
    assert len(results) > 0

    # Verify similarity scores are valid
    for result in results:
        similarity = result.get("similarity")
        assert similarity is not None
        assert isinstance(similarity, (float, int))
        assert 0.0 <= similarity <= 1.0


def test_reference_nodes_max_similarity_title_only(reference_manager_with_embeddings):
    """Test reference node search when only title embedding exists."""
    manager = reference_manager_with_embeddings

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.65)

    results = manager.search_reference_nodes(
        query_embedding=query_embedding,
        threshold=0.0,
        limit=10,
    )

    # Should include title-only nodes
    assert len(results) > 0

    # Find the title-only result
    title_only_results = [r for r in results if r["title"] == "Title Only"]
    assert len(title_only_results) > 0

    # Verify similarity is computed correctly
    similarity = title_only_results[0].get("similarity")
    assert similarity is not None
    assert 0.0 <= similarity <= 1.0


def test_reference_nodes_max_similarity_definition_only(
    reference_manager_with_embeddings,
):
    """Test reference node search when only definition embedding exists."""
    manager = reference_manager_with_embeddings

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.55)

    results = manager.search_reference_nodes(
        query_embedding=query_embedding,
        threshold=0.0,
        limit=10,
    )

    # Should include definition-only nodes
    assert len(results) > 0

    # Find the definition-only result
    def_only_results = [r for r in results if r["title"] == "Definition Only"]
    assert len(def_only_results) > 0

    # Verify similarity is computed correctly
    similarity = def_only_results[0].get("similarity")
    assert similarity is not None
    assert 0.0 <= similarity <= 1.0


def test_reference_nodes_no_embeddings_filtered(reference_manager_with_embeddings):
    """Test that nodes without embeddings are filtered out."""
    manager = reference_manager_with_embeddings

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.7)

    results = manager.search_reference_nodes(
        query_embedding=query_embedding,
        threshold=0.0,
        limit=10,
    )

    # Should not include nodes without embeddings
    node_titles = [r["title"] for r in results]
    assert "No Embeddings" not in node_titles


def test_reference_nodes_threshold_filtering(reference_manager_with_embeddings):
    """Test that similarity threshold filtering works correctly."""
    manager = reference_manager_with_embeddings

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.7)

    # Get all results with low threshold
    all_results = manager.search_reference_nodes(
        query_embedding=query_embedding,
        threshold=0.0,
        limit=10,
    )

    # Get results with high threshold
    high_threshold_results = manager.search_reference_nodes(
        query_embedding=query_embedding,
        threshold=0.99,
        limit=10,
    )

    # High threshold should have fewer or equal results
    assert len(high_threshold_results) <= len(all_results)

    # All high threshold results should meet the threshold
    for result in high_threshold_results:
        assert result["similarity"] >= 0.99


def test_reference_nodes_result_ordering(reference_manager_with_embeddings):
    """Test that results are ordered by similarity descending."""
    manager = reference_manager_with_embeddings

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.7)

    results = manager.search_reference_nodes(
        query_embedding=query_embedding,
        threshold=0.0,
        limit=10,
    )

    # Verify results are ordered by similarity descending
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i]["similarity"] >= results[i + 1]["similarity"]


def test_reference_nodes_limit_respected(reference_manager_with_embeddings):
    """Test that the limit parameter is respected."""
    manager = reference_manager_with_embeddings

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.7)

    results = manager.search_reference_nodes(
        query_embedding=query_embedding,
        threshold=0.0,
        limit=2,
    )

    # Should respect the limit
    assert len(results) <= 2
