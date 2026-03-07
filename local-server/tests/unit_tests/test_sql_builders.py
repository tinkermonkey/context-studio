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


def test_sql_builder_invalid_column_empty():
    """Unit test to verify empty column names are rejected.

    Verify that build_max_similarity_case_when rejects empty column names
    to prevent SQL injection or undefined column references.
    """
    import pytest
    with pytest.raises(ValueError, match="Column name cannot be empty"):
        build_max_similarity_case_when(title_column="")


def test_sql_builder_invalid_column_leading_number():
    """Unit test to verify column names starting with numbers are rejected.

    Verify that build_max_similarity_case_when rejects column names that
    start with numbers, which are not valid SQL identifiers.
    """
    import pytest
    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="123column")


def test_sql_builder_invalid_column_special_characters():
    """Unit test to verify column names with invalid characters are rejected.

    Verify that build_max_similarity_case_when rejects column names containing
    special characters like semicolons, quotes, or parentheses that could
    enable SQL injection.
    """
    import pytest
    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="column; DROP TABLE")

    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="column' OR '1'='1")

    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="column()")


def test_sql_builder_invalid_column_spaces():
    """Unit test to verify column names with spaces are rejected.

    Verify that build_max_similarity_case_when rejects column names containing
    spaces, which must be quoted as identifiers in SQL.
    """
    import pytest
    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="my column")


def test_sql_builder_valid_unqualified_columns():
    """Unit test to verify unqualified column names are accepted.

    Verify that simple, unqualified column names like 'title_embedding'
    are correctly validated and accepted.
    """
    result = build_max_similarity_case_when(
        title_column="title_embedding",
        definition_column="definition_embedding"
    )
    assert "title_embedding" in result
    assert "definition_embedding" in result


def test_sql_builder_valid_qualified_columns_single_alias():
    """Unit test to verify single-level qualified column names are accepted.

    Verify that table-qualified column names like 'sn.title_embedding'
    are correctly validated and accepted.
    """
    result = build_max_similarity_case_when(
        title_column="sn.title_embedding",
        definition_column="sn.definition_embedding"
    )
    assert "sn.title_embedding" in result
    assert "sn.definition_embedding" in result


def test_sql_builder_valid_columns_with_underscores():
    """Unit test to verify column names with underscores are accepted.

    Verify that column names with multiple underscores like 'my_custom_embedding'
    are correctly validated and accepted.
    """
    result = build_max_similarity_case_when(
        title_column="my_custom_title_embedding",
        definition_column="my_custom_definition_embedding"
    )
    assert "my_custom_title_embedding" in result
    assert "my_custom_definition_embedding" in result


def test_sql_builder_valid_columns_starting_with_underscore():
    """Unit test to verify column names starting with underscore are accepted.

    Verify that column names starting with underscore like '_title_embedding'
    are correctly validated and accepted.
    """
    result = build_max_similarity_case_when(
        title_column="_title_embedding",
        definition_column="_definition_embedding"
    )
    assert "_title_embedding" in result
    assert "_definition_embedding" in result
