"""
Integration tests for concept resolution vector search functionality.

Tests the SQL CASE WHEN fix for max similarity calculation in concept_resolution.py
by validating the build_max_similarity_case_when SQL builder function.
"""

import pytest
from database.sql_builders import build_max_similarity_case_when


def test_sql_builder_case_when_default_columns():
    """Unit test of the SQL builder function with default column names.

    Verify that build_max_similarity_case_when generates the correct CASE WHEN
    pattern for concept_resolution.py usage.
    """
    result = build_max_similarity_case_when()
    assert "CASE" in result
    assert "title_embedding" in result
    assert "definition_embedding" in result
    assert "vec_distance_cosine" in result
    assert ":query_vec" in result


def test_sql_builder_case_when_custom_columns():
    """Unit test of the SQL builder function with custom column names.

    Verify that build_max_similarity_case_when supports custom column names
    for use in different database contexts.
    """
    result = build_max_similarity_case_when(
        title_column="rn.title_embedding",
        definition_column="rn.definition_embedding"
    )
    assert "rn.title_embedding" in result
    assert "rn.definition_embedding" in result
    assert "CASE" in result
    assert "vec_distance_cosine" in result


def test_sql_builder_case_when_structure():
    """Unit test to verify CASE WHEN structure generates correctly.

    Verify the structure of the generated SQL handles all cases:
    - Both embeddings present (max similarity)
    - Only title embedding (use title similarity)
    - Only definition embedding (use definition similarity)
    - No embeddings (similarity is 0.0)
    """
    result = build_max_similarity_case_when()

    # Verify CASE WHEN structure
    assert "WHEN title_embedding IS NOT NULL AND definition_embedding IS NOT NULL" in result
    assert "WHEN title_embedding IS NOT NULL THEN" in result
    assert "WHEN definition_embedding IS NOT NULL" in result
    assert "ELSE 0.0" in result
