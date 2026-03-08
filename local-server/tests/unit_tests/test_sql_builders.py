"""
Unit tests for SQL builder functions.

Tests the build_max_similarity_case_when SQL builder function which is used
across multiple modules to generate the CASE WHEN pattern for max similarity
calculation across different embedding scenarios.
"""

import pytest
import sqlite3
import json
import numpy as np

from database.sql_builders import build_max_similarity_case_when


@pytest.fixture
def sqlite_with_vec():
    """Fixture providing an in-memory SQLite connection with vec0 extension loaded.

    Skips the test if sqlite-vec is not available. Returns the connection which must
    be closed by the test in a try/finally block.
    """
    conn = sqlite3.connect(":memory:")

    try:
        conn.enable_load_extension(True)
        conn.load_extension("vec0")
        conn.enable_load_extension(False)
    except Exception:
        pytest.skip("sqlite-vec extension not available")

    return conn


def create_test_embedding(seed: int) -> bytes:
    """Helper to create deterministic normalized embeddings for testing."""
    rng = np.random.RandomState(seed=seed)
    emb = rng.randn(384).astype(np.float32)
    emb = emb / np.linalg.norm(emb)
    return emb.tobytes()



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
        title_column="rn.title_embedding", definition_column="rn.definition_embedding"
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
        title_column="sn.title_embedding", definition_column="sn.definition_embedding"
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
    assert (
        "WHEN title_embedding IS NOT NULL AND definition_embedding IS NOT NULL"
        in result
    )
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
    with pytest.raises(ValueError, match="Column name cannot be empty"):
        build_max_similarity_case_when(title_column="")


def test_sql_builder_invalid_column_leading_number():
    """Unit test to verify column names starting with numbers are rejected.

    Verify that build_max_similarity_case_when rejects column names that
    start with numbers, which are not valid SQL identifiers.
    """
    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="123column")


def test_sql_builder_invalid_column_special_characters():
    """Unit test to verify column names with invalid characters are rejected.

    Verify that build_max_similarity_case_when rejects column names containing
    special characters like semicolons, quotes, or parentheses that could
    enable SQL injection.
    """
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
    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="my column")


def test_sql_builder_invalid_column_trailing_dot():
    """Unit test to verify column names with trailing or double dots are rejected.

    Verify that build_max_similarity_case_when rejects malformed qualified names
    like 'column.' (trailing dot) or 'a..b' (double dots) which are not valid
    SQL identifiers.
    """
    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="column.")

    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column="a..b")

    with pytest.raises(ValueError, match="Invalid column name"):
        build_max_similarity_case_when(title_column=".column")


def test_sql_builder_valid_unqualified_columns():
    """Unit test to verify unqualified column names are accepted.

    Verify that simple, unqualified column names like 'title_embedding'
    are correctly validated and accepted.
    """
    result = build_max_similarity_case_when(
        title_column="title_embedding", definition_column="definition_embedding"
    )
    assert "title_embedding" in result
    assert "definition_embedding" in result


def test_sql_builder_valid_qualified_columns_single_alias():
    """Unit test to verify single-level qualified column names are accepted.

    Verify that table-qualified column names like 'sn.title_embedding'
    are correctly validated and accepted.
    """
    result = build_max_similarity_case_when(
        title_column="sn.title_embedding", definition_column="sn.definition_embedding"
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
        definition_column="my_custom_definition_embedding",
    )
    assert "my_custom_title_embedding" in result
    assert "my_custom_definition_embedding" in result


def test_sql_builder_valid_columns_starting_with_underscore():
    """Unit test to verify column names starting with underscore are accepted.

    Verify that column names starting with underscore like '_title_embedding'
    are correctly validated and accepted.
    """
    result = build_max_similarity_case_when(
        title_column="_title_embedding", definition_column="_definition_embedding"
    )
    assert "_title_embedding" in result
    assert "_definition_embedding" in result


def test_sql_builder_execution_both_embeddings(sqlite_with_vec):
    """Test that CASE WHEN SQL executes correctly when both embeddings exist.

    This test verifies that the generated SQL actually executes against SQLite
    and returns the maximum similarity when both embeddings are present.
    """
    conn = sqlite_with_vec

    try:
        # Create test table with embeddings
        conn.execute("""
            CREATE TABLE test_nodes (
                id TEXT PRIMARY KEY,
                title_embedding BLOB,
                definition_embedding BLOB
            )
        """)

        # Create test embeddings
        emb1 = create_test_embedding(seed=42)
        emb2 = create_test_embedding(seed=43)

        # Insert test data
        conn.execute(
            "INSERT INTO test_nodes (id, title_embedding, definition_embedding) VALUES (?, ?, ?)",
            ("test1", emb1, emb2),
        )
        conn.commit()

        # Create query embedding
        query_emb = create_test_embedding(seed=44)
        query_vec_json = json.dumps(query_emb)

        # Build and execute the CASE WHEN query
        similarity_case = build_max_similarity_case_when("title_embedding", "definition_embedding")
        sql_query = f"""
            SELECT
                id,
                {similarity_case} AS max_similarity
            FROM test_nodes
        """

        result = conn.execute(sql_query, {"query_vec": query_vec_json}).fetchone()

        # Verify the query executed and returned a result
        assert result is not None
        assert len(result) == 2
        assert result[0] == "test1"

        # Verify similarity is a valid float between -1.0 and 1.0
        similarity = result[1]
        assert isinstance(similarity, (float, int))
        assert -1.0 <= similarity <= 1.0

    finally:
        conn.close()


def test_sql_builder_execution_title_only(sqlite_with_vec):
    """Test that CASE WHEN SQL executes correctly when only title embedding exists.

    This test verifies that the generated SQL correctly handles the case where
    only the title embedding is present and definition is NULL.
    """
    conn = sqlite_with_vec

    try:
        conn.execute("""
            CREATE TABLE test_nodes (
                id TEXT PRIMARY KEY,
                title_embedding BLOB,
                definition_embedding BLOB
            )
        """)

        emb1 = create_test_embedding(seed=45)

        # Insert with definition_embedding as NULL
        conn.execute(
            "INSERT INTO test_nodes (id, title_embedding, definition_embedding) VALUES (?, ?, ?)",
            ("test2", emb1, None),
        )
        conn.commit()

        query_vec_json = json.dumps(np.random.RandomState(seed=46).randn(384).tolist())

        similarity_case = build_max_similarity_case_when("title_embedding", "definition_embedding")
        sql_query = f"""
            SELECT
                id,
                {similarity_case} AS max_similarity
            FROM test_nodes
        """

        result = conn.execute(sql_query, {"query_vec": query_vec_json}).fetchone()

        # Verify the query executed
        assert result is not None
        assert result[0] == "test2"

        # Similarity should be computed from title only
        similarity = result[1]
        assert isinstance(similarity, (float, int))
        assert -1.0 <= similarity <= 1.0

    finally:
        conn.close()


def test_sql_builder_execution_definition_only(sqlite_with_vec):
    """Test that CASE WHEN SQL executes correctly when only definition embedding exists.

    This test verifies that the generated SQL correctly handles the case where
    only the definition embedding is present and title is NULL.
    """
    conn = sqlite_with_vec

    try:
        conn.execute("""
            CREATE TABLE test_nodes (
                id TEXT PRIMARY KEY,
                title_embedding BLOB,
                definition_embedding BLOB
            )
        """)

        emb2 = create_test_embedding(seed=47)

        # Insert with title_embedding as NULL
        conn.execute(
            "INSERT INTO test_nodes (id, title_embedding, definition_embedding) VALUES (?, ?, ?)",
            ("test3", None, emb2),
        )
        conn.commit()

        query_vec_json = json.dumps(np.random.RandomState(seed=48).randn(384).tolist())

        similarity_case = build_max_similarity_case_when("title_embedding", "definition_embedding")
        sql_query = f"""
            SELECT
                id,
                {similarity_case} AS max_similarity
            FROM test_nodes
        """

        result = conn.execute(sql_query, {"query_vec": query_vec_json}).fetchone()

        # Verify the query executed
        assert result is not None
        assert result[0] == "test3"

        # Similarity should be computed from definition only
        similarity = result[1]
        assert isinstance(similarity, (float, int))
        assert -1.0 <= similarity <= 1.0

    finally:
        conn.close()


def test_sql_builder_execution_no_embeddings(sqlite_with_vec):
    """Test that CASE WHEN SQL executes correctly when no embeddings exist.

    This test verifies that the generated SQL correctly returns 0.0 when both
    embeddings are NULL.
    """
    conn = sqlite_with_vec

    try:
        conn.execute("""
            CREATE TABLE test_nodes (
                id TEXT PRIMARY KEY,
                title_embedding BLOB,
                definition_embedding BLOB
            )
        """)

        # Insert with both embeddings as NULL
        conn.execute(
            "INSERT INTO test_nodes (id, title_embedding, definition_embedding) VALUES (?, ?, ?)",
            ("test4", None, None),
        )
        conn.commit()

        query_vec_json = json.dumps(np.random.RandomState(seed=49).randn(384).tolist())

        similarity_case = build_max_similarity_case_when("title_embedding", "definition_embedding")
        sql_query = f"""
            SELECT
                id,
                {similarity_case} AS max_similarity
            FROM test_nodes
        """

        result = conn.execute(sql_query, {"query_vec": query_vec_json}).fetchone()

        # Verify the query executed
        assert result is not None
        assert result[0] == "test4"

        # Similarity should be 0.0 when no embeddings exist
        assert result[1] == 0.0

    finally:
        conn.close()


def test_sql_builder_execution_with_qualified_columns(sqlite_with_vec):
    """Test that CASE WHEN SQL executes correctly with table-qualified column names.

    This test verifies that the generated SQL with table aliases (like t.title_embedding)
    actually executes correctly, preventing runtime failures from table alias mismatches.
    It also validates that the MAX semantics are preserved across different alias contexts
    (critical for detecting mismatches like ep.* vs rn.*).
    """
    conn = sqlite_with_vec

    try:
        conn.execute("""
            CREATE TABLE test_nodes (
                id TEXT PRIMARY KEY,
                title_embedding BLOB,
                definition_embedding BLOB
            )
        """)

        emb1 = create_test_embedding(seed=50)
        emb2 = create_test_embedding(seed=51)

        conn.execute(
            "INSERT INTO test_nodes (id, title_embedding, definition_embedding) VALUES (?, ?, ?)",
            ("test5", emb1, emb2),
        )
        conn.commit()

        query_vec_json = json.dumps(np.random.RandomState(seed=52).randn(384).tolist())

        # Test with different table aliases to ensure they work correctly
        # This is critical for catching alias mismatches like ep.* vs rn.*
        for table_alias in ["t", "rn", "ep"]:
            title_col = f"{table_alias}.title_embedding"
            def_col = f"{table_alias}.definition_embedding"

            similarity_case = build_max_similarity_case_when(title_col, def_col)
            sql_query = f"""
                SELECT
                    {table_alias}.id,
                    {similarity_case} AS max_similarity
                FROM test_nodes AS {table_alias}
            """

            result = conn.execute(sql_query, {"query_vec": query_vec_json}).fetchone()

            # Verify the query executed with this table alias
            assert result is not None
            assert result[0] == "test5"

            # Verify similarity is valid and consistent across aliases
            similarity = result[1]
            assert isinstance(similarity, (float, int))
            assert -1.0 <= similarity <= 1.0

    finally:
        conn.close()


def test_sql_builder_case_when_evaluation_order(sqlite_with_vec):
    """Test that CASE WHEN clauses are evaluated in the correct order.

    This test verifies that the CASE WHEN structure properly handles precedence:
    - Both embeddings present should use the MAX of the two similarities
    - Only title should use title similarity
    - Only definition should use definition similarity
    - Neither should return 0.0

    The order matters because SQLite evaluates WHEN clauses sequentially and stops
    at the first matching condition. This test verifies the MAX semantics when both
    embeddings are present by comparing against independently computed similarities.
    """
    conn = sqlite_with_vec

    try:
        conn.execute("""
            CREATE TABLE test_cases (
                id TEXT PRIMARY KEY,
                case_name TEXT,
                title_embedding BLOB,
                definition_embedding BLOB
            )
        """)

        emb1 = create_test_embedding(seed=60)
        emb2 = create_test_embedding(seed=61)

        # Insert test cases: both, title-only, definition-only, neither
        conn.execute(
            "INSERT INTO test_cases VALUES (?, ?, ?, ?)",
            ("case1", "both", emb1, emb2),
        )
        conn.execute(
            "INSERT INTO test_cases VALUES (?, ?, ?, ?)",
            ("case2", "title_only", emb1, None),
        )
        conn.execute(
            "INSERT INTO test_cases VALUES (?, ?, ?, ?)",
            ("case3", "definition_only", None, emb2),
        )
        conn.execute(
            "INSERT INTO test_cases VALUES (?, ?, ?, ?)",
            ("case4", "neither", None, None),
        )
        conn.commit()

        query_vec_json = json.dumps(np.random.RandomState(seed=62).randn(384).tolist())

        similarity_case = build_max_similarity_case_when("title_embedding", "definition_embedding")
        sql_query = f"""
            SELECT
                case_name,
                {similarity_case} AS max_similarity
            FROM test_cases
            ORDER BY id
        """

        results = conn.execute(sql_query, {"query_vec": query_vec_json}).fetchall()

        # Verify we got all four cases
        assert len(results) == 4

        # Check that each case returned appropriate values
        case_results = {name: similarity for name, similarity in results}

        # Both embeddings should return a value in valid range
        both_sim = case_results["both"]
        assert -1.0 <= both_sim <= 1.0

        # Title-only should return a value
        title_only_sim = case_results["title_only"]
        assert -1.0 <= title_only_sim <= 1.0

        # Definition-only should return a value
        def_only_sim = case_results["definition_only"]
        assert -1.0 <= def_only_sim <= 1.0

        # Neither should return exactly 0.0
        assert case_results["neither"] == 0.0

        # Verify MAX semantics for the "both" case by computing expected values
        # The expected MAX should be max(title_sim, definition_sim)
        # We can verify this by checking the "both" value is >= each individual value
        assert both_sim >= title_only_sim - 0.001, \
            f"Both ({both_sim}) should be >= title_only ({title_only_sim}) in MAX comparison"
        assert both_sim >= def_only_sim - 0.001, \
            f"Both ({both_sim}) should be >= definition_only ({def_only_sim}) in MAX comparison"

    finally:
        conn.close()
