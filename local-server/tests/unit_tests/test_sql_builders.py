"""
Unit tests for SQL builder functions.

Tests the build_max_similarity_case_when SQL builder function which is used
across multiple modules to generate the CASE WHEN pattern for max similarity
calculation across different embedding scenarios.
"""

from database.sql_builders import build_max_similarity_case_when


def test_sql_builder_case_when_default_columns():
    """Unit test of the SQL builder function with default column names.

    Verify that build_max_similarity_case_when generates the correct CASE WHEN
    pattern with default column names.
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


def test_sql_builder_case_when_with_qualified_columns():
    """Unit test of the SQL builder function with table-qualified column names.

    Verify that build_max_similarity_case_when generates the correct CASE WHEN
    pattern with table-qualified columns (e.g., sn.title_embedding).
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
