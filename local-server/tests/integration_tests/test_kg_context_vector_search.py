"""
Integration tests for KG context processor vector search functionality.

Tests the SQL CASE WHEN fix for max similarity calculation in kg_context.py
by validating the build_max_similarity_case_when SQL builder function.
"""

import pytest
from database.sql_builders import build_max_similarity_case_when


def test_sql_builder_case_when_with_qualified_columns():
    """Unit test of the SQL builder function with qualified column names.

    Verify that build_max_similarity_case_when generates the correct CASE WHEN
    pattern for kg_context.py usage with table-qualified columns.
    """
    result = build_max_similarity_case_when(
        title_column="sn.title_embedding",
        definition_column="sn.definition_embedding"
    )
    assert "sn.title_embedding" in result
    assert "sn.definition_embedding" in result
    assert "CASE" in result
    assert "vec_distance_cosine" in result
    assert ":query_vec" in result


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


def test_sql_builder_parameter_injection():
    """Unit test to verify parameter binding is correct.

    Verify that the builder generates proper parameterized SQL
    using :query_vec for the query embedding binding.
    """
    result = build_max_similarity_case_when()
    assert ":query_vec" in result
    # Should appear multiple times (once for each embedding case)
    assert result.count(":query_vec") >= 2
