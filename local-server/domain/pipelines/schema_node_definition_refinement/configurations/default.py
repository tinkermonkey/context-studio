"""
Default configuration for Schema Node Definition Refinement pipeline.

Uses OpenRouter with google/gemini-3-flash-preview for generating refined
definitions based on schema neighborhood context.
"""


def get_default_config() -> dict:
    """
    Return the default definition refinement configuration.

    Uses OpenRouter + Gemini 3 Flash for generating 2-3 candidate refined
    definitions with rationale. Temperature 0.0 for consistency.

    Returns:
        Configuration dict with LLM settings and generation parameters
    """
    return {
        "description": (
            "Default schema node definition refinement with OpenRouter Gemini 3 Flash"
        ),
        "llm_provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 2000,
    }
