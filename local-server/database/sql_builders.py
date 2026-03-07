"""SQL builder utilities for common query patterns."""


def build_max_similarity_case_when(
    title_column: str = "title_embedding",
    definition_column: str = "definition_embedding"
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
        title_column: Column name for title embedding (default: "title_embedding")
        definition_column: Column name for definition embedding (default: "definition_embedding")

    Returns:
        SQL CASE WHEN fragment as a string
    """
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
