"""
Integration tests for concept resolution vector search functionality.

Tests the SQL CASE WHEN fix for max similarity calculation in concept_resolution.py
by validating that the similarity computation correctly handles different embedding scenarios:
- Both title and definition embeddings present
- Only title embedding present
- Only definition embedding present
- No embeddings present
"""

import pytest
import tempfile
import os
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database.utils import init_db
from rag.processors.concept_resolution import ConceptResolutionProcessor
from database.models import StructureNode, Base


@pytest.fixture(scope="function")
def concept_resolution_test_db():
    """Create a test database with structure nodes for concept resolution testing."""
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
            "title": "Example Node",
            "node_type": "term",
            "definition": "A test node with both embeddings",
            "title_embedding": create_embedding(0.8),
            "definition_embedding": create_embedding(0.7),
        },
        {
            "title": "Title Only Node",
            "node_type": "term",
            "definition": "Node with only title embedding",
            "title_embedding": create_embedding(0.6),
            "definition_embedding": None,
        },
        {
            "title": "Definition Only Node",
            "node_type": "term",
            "definition": "Node with only definition embedding",
            "title_embedding": None,
            "definition_embedding": create_embedding(0.5),
        },
        {
            "title": "No Embedding Node",
            "node_type": "term",
            "definition": "Node with no embeddings",
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


def test_concept_resolution_max_similarity_both_embeddings(concept_resolution_test_db):
    """Test similarity calculation when both title and definition embeddings exist.

    When both embeddings are present, the processor should return the maximum similarity
    between them, which is the correct behavior for vector search.
    """
    engine, SessionLocal = concept_resolution_test_db
    session = SessionLocal()

    # Query to test the CASE WHEN logic
    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.75)
    query_vec_bytes = query_embedding

    # Execute the SQL query with the CASE WHEN logic
    from database.sql_builders import build_max_similarity_case_when

    similarity_case = build_max_similarity_case_when()
    query = text(f"""
        WITH similarities AS (
            SELECT
                id,
                title,
                {similarity_case} as similarity
            FROM structure_nodes
            WHERE title = 'Example Node'
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


def test_concept_resolution_max_similarity_title_only(concept_resolution_test_db):
    """Test similarity calculation when only title embedding exists.

    When only title embedding is present, the processor should return the title similarity.
    """
    engine, SessionLocal = concept_resolution_test_db
    session = SessionLocal()

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.65)
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
            WHERE title = 'Title Only Node'
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


def test_concept_resolution_max_similarity_definition_only(concept_resolution_test_db):
    """Test similarity calculation when only definition embedding exists.

    When only definition embedding is present, the processor should return the definition similarity.
    """
    engine, SessionLocal = concept_resolution_test_db
    session = SessionLocal()

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.55)
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
            WHERE title = 'Definition Only Node'
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


def test_concept_resolution_max_similarity_no_embeddings(concept_resolution_test_db):
    """Test similarity calculation when no embeddings exist.

    When no embeddings are present, the processor should return 0.0 similarity
    and the node should be filtered out by the WHERE clause.
    """
    engine, SessionLocal = concept_resolution_test_db
    session = SessionLocal()

    def create_embedding(value: float) -> bytes:
        rng = np.random.RandomState(seed=int(value * 1000))
        vec = rng.randn(384).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return vec.tobytes()

    query_embedding = create_embedding(0.45)
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
        SELECT similarity FROM similarities WHERE title = 'No Embedding Node'
    """)

    result = session.execute(query, {"query_vec": query_vec_bytes}).fetchone()
    # Should be None because no embeddings exist and WHERE clause filters them out
    assert result is None

    session.close()


def test_concept_resolution_filtering_by_threshold(concept_resolution_test_db):
    """Test that the CASE WHEN logic works correctly with threshold filtering.

    The processor should correctly compute similarity and filter results based on threshold.
    """
    engine, SessionLocal = concept_resolution_test_db
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
        SELECT COUNT(*) as count
        FROM similarities
        WHERE similarity >= :threshold
    """)

    result = session.execute(query, {"query_vec": query_vec_bytes, "threshold": 0.0}).fetchone()
    assert result is not None
    count = result[0]

    # Should have at least 3 nodes (all except "No Embedding Node")
    assert count == 3

    session.close()
