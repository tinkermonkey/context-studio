"""SQL builder utilities for common query patterns."""

import re


def _validate_column_name(column_name: str) -> None:
    """
    Validate that a column name matches safe SQL identifier pattern.

    Column names must start with a letter or underscore, followed by any combination
    of letters, numbers, underscores, and dots (for table-qualified names like 'table.column').

    Args:
        column_name: Column name to validate

    Raises:
        ValueError: If column name doesn't match safe pattern
    """
    if not column_name:
        raise ValueError("Column name cannot be empty")

    # Pattern ensures each dot-separated segment is itself a valid identifier.
    # This prevents trailing dots (column.), consecutive dots (a..b), etc.
    # Examples: 'title_embedding', 'sn.title_embedding', 'rn.definition_embedding'
    # Invalid: 'column.', 'a..b', 'table.', '.column'
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$"
    if not re.match(pattern, column_name):
        raise ValueError(
            f"Invalid column name '{column_name}'. Column names must start with a letter or underscore "
            f"and contain only alphanumeric characters, underscores, and dots (for table qualification)."
        )


def build_max_similarity_case_when(
    title_column: str = "title_embedding",
    definition_column: str = "definition_embedding",
) -> str:
    """
    Build a CASE WHEN SQL fragment that computes max similarity between title and definition embeddings.

    This handles the logic:
    - If both embeddings exist: return the maximum similarity
    - If only title exists: return title similarity
    - If only definition exists: return definition similarity
    - Otherwise: return 0.0

    The similarity is computed as (1.0 - cosine_distance) using vec_distance_cosine.

    Args:
        title_column: Column name for title embedding (default: "title_embedding").
            Must match pattern: ^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$ (e.g., 'title_embedding' or 'sn.title_embedding')
        definition_column: Column name for definition embedding (default: "definition_embedding").
            Must match pattern: ^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$ (e.g., 'definition_embedding' or 'sn.definition_embedding')

    Returns:
        SQL CASE WHEN fragment as a string

    Raises:
        ValueError: If column names don't match safe SQL identifier pattern
    """
    # Validate input column names to prevent SQL injection
    _validate_column_name(title_column)
    _validate_column_name(definition_column)
    return f"""CASE
                    WHEN {title_column} IS NOT NULL AND {definition_column} IS NOT NULL THEN
                        CASE
                            WHEN (1.0 - vec_distance_cosine({title_column}, :query_vec)) >=
                                 (1.0 - vec_distance_cosine({definition_column}, :query_vec))
                            THEN (1.0 - vec_distance_cosine({title_column}, :query_vec))
                            ELSE (1.0 - vec_distance_cosine({definition_column}, :query_vec))
                        END
                    WHEN {title_column} IS NOT NULL THEN
                        (1.0 - vec_distance_cosine({title_column}, :query_vec))
                    WHEN {definition_column} IS NOT NULL THEN
                        (1.0 - vec_distance_cosine({definition_column}, :query_vec))
                    ELSE 0.0
                END"""
