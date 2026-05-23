"""
Default configuration for Schema Node Connection Refinement pipeline.

Uses OpenRouter with google/gemini-3-flash-preview for proposing connection
deltas to improve schema relationships.
"""


def get_default_config() -> dict:
    """
    Return the default connection refinement configuration.

    Uses OpenRouter + Gemini 3 Flash for proposing connection deltas
    (add/remove/modify relationships). Temperature 0.0 for consistency.

    Returns:
        Configuration dict with LLM settings and proposal parameters
    """
    return {
        "description": "Default schema node connection refinement with OpenRouter Gemini 3 Flash",
        "llm_provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 2000,
        "max_deltas": 5,
    }
