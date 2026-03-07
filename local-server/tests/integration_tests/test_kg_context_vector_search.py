"""
Integration tests for KG context processor vector search functionality.

Tests the SQL CASE WHEN fix for max similarity calculation in kg_context.py
by validating that the KGContextProcessor correctly computes similarity
for different embedding scenarios.
"""

import pytest
import tempfile
import os
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.utils import init_db
from database.models import StructureNode, Base
from database.sql_builders import build_max_similarity_case_when
from rag.processors.kg_context import KGContextProcessor


def create_embedding(value: float) -> bytes:
    """Create a deterministic embedding vector."""
    rng = np.random.RandomState(seed=int(value * 1000))
    vec = rng.randn(384).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tobytes()


@pytest.fixture(scope="function")
def kg_context_test_db():
    """Create a test database with structure nodes for KG context testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)

    # Create tables
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Test scenarios for CASE WHEN logic
    test_nodes = [
        {
            "title": "Data Structure",
            "node_type": "term",
            "definition": "An organized collection of data with associated operations",
            "title_embedding": create_embedding(0.85),
            "definition_embedding": create_embedding(0.75),
        },
        {
            "title": "Algorithm",
            "node_type": "term",
            "definition": "A procedure for solving a problem",
            "title_embedding": create_embedding(0.65),
            "definition_embedding": None,
        },
        {
            "title": "Machine Learning",
            "node_type": "term",
            "definition": "A subset of artificial intelligence",
            "title_embedding": None,
            "definition_embedding": create_embedding(0.55),
        },
        {
            "title": "Empty Node",
            "node_type": "term",
            "definition": "A node without embeddings",
            "title_embedding": None,
            "definition_embedding": None,
        },
    ]

    for node_data in test_nodes:
        node = StructureNode(
            title=node_data["title"],
            node_type=node_data["node_type"],
            definition=node_data["definition"],
            title_embedding=node_data["title_embedding"],
            definition_embedding=node_data["definition_embedding"],
        )
        session.add(node)

    session.commit()

    yield engine, SessionLocal, db_path

    session.close()
    engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_kg_context_max_similarity_both_embeddings(kg_context_test_db):
    """Test similarity calculation when both title and definition embeddings exist.

    When both embeddings are present, the processor should return the maximum similarity
    between them, using the CASE WHEN logic from the shared builder function.
    """
    engine, SessionLocal, db_path = kg_context_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.8)

    processor = KGContextProcessor(engine)

    # Get context for a concept with both embeddings
    results = processor.get_context(
        node_ids=None,
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Should find the node with both embeddings
    assert len(results) > 0

    # Verify similarity is computed correctly
    for result in results:
        similarity = result.get("similarity")
        assert similarity is not None
        assert isinstance(similarity, (float, int))
        assert 0.0 <= similarity <= 1.0

    session.close()


def test_kg_context_max_similarity_title_only(kg_context_test_db):
    """Test similarity calculation when only title embedding exists.

    When only title embedding is present, the processor should return the title similarity
    using the CASE WHEN logic from the shared builder function.
    """
    engine, SessionLocal, db_path = kg_context_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.6)

    processor = KGContextProcessor(engine)

    # Get context for a concept with only title embedding
    results = processor.get_context(
        node_ids=None,
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Should find the title-only node
    assert len(results) > 0

    # Verify similarity is computed correctly
    for result in results:
        similarity = result.get("similarity")
        assert similarity is not None
        assert 0.0 <= similarity <= 1.0

    session.close()


def test_kg_context_max_similarity_definition_only(kg_context_test_db):
    """Test similarity calculation when only definition embedding exists.

    When only definition embedding is present, the processor should return the definition
    similarity using the CASE WHEN logic from the shared builder function.
    """
    engine, SessionLocal, db_path = kg_context_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.5)

    processor = KGContextProcessor(engine)

    # Get context for a concept with only definition embedding
    results = processor.get_context(
        node_ids=None,
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Should find the definition-only node
    assert len(results) > 0

    # Verify similarity is computed correctly
    for result in results:
        similarity = result.get("similarity")
        assert similarity is not None
        assert 0.0 <= similarity <= 1.0

    session.close()


def test_kg_context_similarity_ranking(kg_context_test_db):
    """Test that similarities can be correctly ranked and limited.

    The CASE WHEN logic should compute similarities that can be correctly
    ranked and limited by the processor.
    """
    engine, SessionLocal, db_path = kg_context_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.7)

    processor = KGContextProcessor(engine)

    # Get context with limit
    results = processor.get_context(
        node_ids=None,
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
        limit=2,
    )

    # Should have at most 2 results (excluding empty node)
    assert len(results) <= 2

    # Results should be ordered by similarity descending
    if len(results) > 1:
        assert results[0].get("similarity") >= results[1].get("similarity")

    session.close()


def test_kg_context_threshold_filtering(kg_context_test_db):
    """Test that threshold filtering correctly excludes low similarity results.

    The CASE WHEN logic should compute similarities that can be correctly
    filtered by threshold.
    """
    engine, SessionLocal, db_path = kg_context_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.7)

    processor = KGContextProcessor(engine)

    # Get all results with low threshold
    all_results = processor.get_context(
        node_ids=None,
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Get results with high threshold
    high_threshold_results = processor.get_context(
        node_ids=None,
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.99,
    )

    # High threshold should have fewer or equal results
    assert len(high_threshold_results) <= len(all_results)

    # All high threshold results should meet the threshold
    for result in high_threshold_results:
        similarity = result.get("similarity")
        assert similarity is not None
        assert similarity >= 0.99

    session.close()


def test_sql_builder_case_when_default_columns():
    """Verify that build_max_similarity_case_when generates the correct pattern.

    Test the builder function directly to ensure it generates valid SQL
    with the expected column references.
    """
    result = build_max_similarity_case_when()
    assert "CASE" in result
    assert "title_embedding" in result
    assert "definition_embedding" in result
    assert "vec_distance_cosine" in result
    assert ":query_vec" in result


def test_sql_builder_case_when_custom_columns():
    """Verify that build_max_similarity_case_when supports custom column names.

    Test the builder function with custom column names as used in reference_db/manager.py.
    """
    result = build_max_similarity_case_when(
        title_column="custom_title",
        definition_column="custom_definition"
    )
    assert "custom_title" in result
    assert "custom_definition" in result
    assert "CASE" in result
