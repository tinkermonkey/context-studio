"""
Default configuration for Schema Extraction pipeline.

Uses OpenRouter with google/gemini-3-flash-preview for reproducibility (temperature 0.0).
"""


def get_default_config() -> dict:
    """
    Return the default schema extraction configuration.

    Returns:
        Configuration dict with LLM settings
    """
    return {
        "provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 2000,
        "confidence_threshold": 0.5,
        "description": "Default schema extraction pipeline with OpenRouter Gemini 3 Flash",
    }
