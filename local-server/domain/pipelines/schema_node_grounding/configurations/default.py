"""
Default configuration for Schema Node Grounding pipeline.

Uses OpenRouter with google/gemini-3-flash-preview for semantic scoring,
queries DBpedia and ConceptNet, and applies weighted scoring strategy.
"""


def get_default_config() -> dict:
    """
    Return the default schema node grounding configuration.

    Uses OpenRouter + Gemini 3 Flash for semantic similarity scoring,
    queries both DBpedia and ConceptNet in parallel, and combines scores
    using weighted average (0.3 source + 0.3 label_match + 0.4 semantic_sim).

    Returns:
        Configuration dict with LLM settings, source preferences, and scoring weights
    """
    return {
        "description": "Default schema node grounding with OpenRouter Gemini 3 Flash",
        "llm_provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 500,
        "sources": ["DBpedia", "ConceptNet"],
        "scoring_strategy": "weighted_average",
        "weights": {
            "source_score": 0.3,
            "label_match": 0.3,
            "semantic_similarity": 0.4,
        },
        "top_n": 10,
    }
