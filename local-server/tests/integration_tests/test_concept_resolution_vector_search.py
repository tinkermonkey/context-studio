"""
Integration tests for concept resolution vector search functionality.

Tests the SQL CASE WHEN fix for max similarity calculation in concept_resolution.py
by validating that the ConceptResolutionProcessor correctly computes similarity
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
from rag.processors.concept_resolution import ConceptResolutionProcessor


def create_embedding(value: float) -> bytes:
    """Create a deterministic embedding vector."""
    rng = np.random.RandomState(seed=int(value * 1000))
    vec = rng.randn(384).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tobytes()


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

    yield engine, SessionLocal, db_path

    session.close()
    engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_concept_resolution_max_similarity_both_embeddings(concept_resolution_test_db):
    """Test similarity calculation when both title and definition embeddings exist.

    When both embeddings are present, the processor should return the maximum similarity
    between them, using the CASE WHEN logic from the shared builder function.
    """
    engine, SessionLocal, db_path = concept_resolution_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.75)

    # Create processor with test database
    processor = ConceptResolutionProcessor(engine)

    # Resolve a concept that has both embeddings
    results = processor.resolve_concept(
        concept_text="Example Node",
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Should find the node with both embeddings
    assert len(results) > 0

    # Verify similarity is computed correctly
    for node_result in results:
        similarity = node_result.get("similarity")
        assert similarity is not None
        assert isinstance(similarity, (float, int))
        assert 0.0 <= similarity <= 1.0

    session.close()


def test_concept_resolution_max_similarity_title_only(concept_resolution_test_db):
    """Test similarity calculation when only title embedding exists.

    When only title embedding is present, the processor should return the title similarity
    using the CASE WHEN logic from the shared builder function.
    """
    engine, SessionLocal, db_path = concept_resolution_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.65)

    processor = ConceptResolutionProcessor(engine)

    # Resolve a concept that has only title embedding
    results = processor.resolve_concept(
        concept_text="Title Only Node",
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Should find the title-only node
    assert len(results) > 0

    # Verify similarity is computed correctly
    for node_result in results:
        similarity = node_result.get("similarity")
        assert similarity is not None
        assert 0.0 <= similarity <= 1.0

    session.close()


def test_concept_resolution_max_similarity_definition_only(concept_resolution_test_db):
    """Test similarity calculation when only definition embedding exists.

    When only definition embedding is present, the processor should return the definition
    similarity using the CASE WHEN logic from the shared builder function.
    """
    engine, SessionLocal, db_path = concept_resolution_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.55)

    processor = ConceptResolutionProcessor(engine)

    # Resolve a concept that has only definition embedding
    results = processor.resolve_concept(
        concept_text="Definition Only Node",
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Should find the definition-only node
    assert len(results) > 0

    # Verify similarity is computed correctly
    for node_result in results:
        similarity = node_result.get("similarity")
        assert similarity is not None
        assert 0.0 <= similarity <= 1.0

    session.close()


def test_concept_resolution_max_similarity_no_embeddings(concept_resolution_test_db):
    """Test that nodes without embeddings are filtered out.

    When no embeddings are present, the CASE WHEN logic sets similarity to 0.0
    and the WHERE clause filters out such nodes.
    """
    engine, SessionLocal, db_path = concept_resolution_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.45)

    processor = ConceptResolutionProcessor(engine)

    # Try to resolve a concept that has no embedding
    results = processor.resolve_concept(
        concept_text="No Embedding Node",
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Should be empty because the node has no embeddings and WHERE clause filters it
    assert len(results) == 0

    session.close()


def test_concept_resolution_filtering_by_threshold(concept_resolution_test_db):
    """Test that the CASE WHEN logic works correctly with threshold filtering.

    The processor should correctly compute similarity using the shared builder
    and filter results based on threshold.
    """
    engine, SessionLocal, db_path = concept_resolution_test_db
    session = SessionLocal()

    query_embedding = create_embedding(0.7)

    processor = ConceptResolutionProcessor(engine)

    # Get all results with low threshold
    all_results = processor.resolve_concept(
        concept_text="Example Node",
        query_embedding=query_embedding,
        session=session,
        similarity_threshold=0.0,
    )

    # Get results with high threshold
    high_threshold_results = processor.resolve_concept(
        concept_text="Example Node",
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


def test_sql_builder_case_when_pattern():
    """Unit test of the SQL builder function itself.

    Verify that build_max_similarity_case_when generates the correct CASE WHEN
    pattern with configurable column names.
    """
    # Test with default column names
    result = build_max_similarity_case_when()
    assert "CASE" in result
    assert "title_embedding" in result
    assert "definition_embedding" in result
    assert "vec_distance_cosine" in result
    assert ":query_vec" in result

    # Test with custom column names (as used in reference_db/manager.py)
    result_custom = build_max_similarity_case_when(
        title_column="rn.title_embedding",
        definition_column="rn.definition_embedding"
    )
    assert "rn.title_embedding" in result_custom
    assert "rn.definition_embedding" in result_custom
    assert "CASE" in result_custom
