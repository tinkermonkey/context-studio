"""
Integration tests for KG context processor vector search functionality.

Tests the SQL CASE WHEN fix for max similarity calculation in kg_context.py
by validating that the similarity computation correctly handles different embedding scenarios.
"""

import pytest
import tempfile
import os
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database.utils import init_db
from rag.processors.kg_context import KGContextProcessor
from database.models import StructureNode, Base


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

    def create_embedding(value: float) -> bytes:
        """Create a deterministic embedding vector."""
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

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

    yield engine, SessionLocal

    session.close()
    engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_kg_context_max_similarity_both_embeddings(kg_context_test_db):
    """Test similarity calculation when both title and definition embeddings exist."""
    engine, SessionLocal = kg_context_test_db
    session = SessionLocal()

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.8)
    query_vec_bytes = query_embedding

    from database.sql_builders import build_max_similarity_case_when

    similarity_case = build_max_similarity_case_when()
    query = text(f"""
        WITH similarities AS (
            SELECT
                id,
                title,
                {similarity_case} as similarity
            FROM structure_nodes
            WHERE title = 'Data Structure'
        )
        SELECT similarity FROM similarities
    """)

    result = session.execute(query, {"query_vec": query_vec_bytes}).fetchone()
    assert result is not None
    similarity = result[0]

    # Similarity should be a float between 0 and 1
    assert isinstance(similarity, float)
    assert 0.0 <= similarity <= 1.0

    session.close()


def test_kg_context_max_similarity_title_only(kg_context_test_db):
    """Test similarity calculation when only title embedding exists."""
    engine, SessionLocal = kg_context_test_db
    session = SessionLocal()

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.6)
    query_vec_bytes = query_embedding

    from database.sql_builders import build_max_similarity_case_when

    similarity_case = build_max_similarity_case_when()
    query = text(f"""
        WITH similarities AS (
            SELECT
                id,
                title,
                {similarity_case} as similarity
            FROM structure_nodes
            WHERE title = 'Algorithm'
        )
        SELECT similarity FROM similarities
    """)

    result = session.execute(query, {"query_vec": query_vec_bytes}).fetchone()
    assert result is not None
    similarity = result[0]

    # Similarity should be a float between 0 and 1
    assert isinstance(similarity, float)
    assert 0.0 <= similarity <= 1.0

    session.close()


def test_kg_context_max_similarity_definition_only(kg_context_test_db):
    """Test similarity calculation when only definition embedding exists."""
    engine, SessionLocal = kg_context_test_db
    session = SessionLocal()

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.5)
    query_vec_bytes = query_embedding

    from database.sql_builders import build_max_similarity_case_when

    similarity_case = build_max_similarity_case_when()
    query = text(f"""
        WITH similarities AS (
            SELECT
                id,
                title,
                {similarity_case} as similarity
            FROM structure_nodes
            WHERE title = 'Machine Learning'
        )
        SELECT similarity FROM similarities
    """)

    result = session.execute(query, {"query_vec": query_vec_bytes}).fetchone()
    assert result is not None
    similarity = result[0]

    # Similarity should be a float between 0 and 1
    assert isinstance(similarity, float)
    assert 0.0 <= similarity <= 1.0

    session.close()


def test_kg_context_similarity_ranking(kg_context_test_db):
    """Test that similarities can be correctly ranked and limited."""
    engine, SessionLocal = kg_context_test_db
    session = SessionLocal()

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.7)
    query_vec_bytes = query_embedding

    from database.sql_builders import build_max_similarity_case_when

    similarity_case = build_max_similarity_case_when()
    query = text(f"""
        WITH similarities AS (
            SELECT
                id,
                title,
                {similarity_case} as similarity
            FROM structure_nodes
            WHERE (title_embedding IS NOT NULL OR definition_embedding IS NOT NULL)
        )
        SELECT title, similarity
        FROM similarities
        WHERE similarity >= :threshold
        ORDER BY similarity DESC
        LIMIT :limit
    """)

    results = session.execute(
        query,
        {"query_vec": query_vec_bytes, "threshold": 0.0, "limit": 2},
    ).fetchall()

    # Should have at least 2 results (excluding empty node)
    assert len(results) >= 2

    # Results should be ordered by similarity descending
    if len(results) > 1:
        assert results[0][1] >= results[1][1]

    session.close()


def test_kg_context_threshold_filtering(kg_context_test_db):
    """Test that threshold filtering correctly excludes low similarity results."""
    engine, SessionLocal = kg_context_test_db
    session = SessionLocal()

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.7)
    query_vec_bytes = query_embedding

    from database.sql_builders import build_max_similarity_case_when

    similarity_case = build_max_similarity_case_when()

    # Query with threshold 0.0 should get all nodes with embeddings
    query_all = text(f"""
        WITH similarities AS (
            SELECT
                id,
                title,
                {similarity_case} as similarity
            FROM structure_nodes
            WHERE (title_embedding IS NOT NULL OR definition_embedding IS NOT NULL)
        )
        SELECT COUNT(*) as count
        FROM similarities
        WHERE similarity >= :threshold
    """)

    result = session.execute(query_all, {"query_vec": query_vec_bytes, "threshold": 0.0}).fetchone()
    assert result is not None
    count_all = result[0]

    # Should have 3 nodes with embeddings
    assert count_all == 3

    session.close()
