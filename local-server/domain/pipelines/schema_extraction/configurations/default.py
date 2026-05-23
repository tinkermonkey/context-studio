"""
Default configuration for Schema Extraction pipeline.

Uses OpenRouter with google/gemini-3-flash-preview for reproducibility (temperature 0.0).
"""


def get_default_config() -> dict:
    """
    Return the default schema extraction configuration.

    Returns:
        Configuration dict with LLM settings and prompts
    """
    return {
        "provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 2000,
        "confidence_threshold": 0.5,
        "system_prompts": {
            "text_ingestion": (
                "You are a text normalization expert. "
                "Clean and normalize text while preserving semantic content."
            ),
            "candidate_identification": (
                "You are an expert in ontology design and schema extraction. "
                "Extract candidate classes and key terms from text. "
                "Return a JSON array of candidate labels."
            ),
            "classification": (
                "You are an ontology alignment expert. "
                "Classify candidates as new or existing in the target schema."
            ),
            "definition_synthesis": (
                "You are an expert in ontology definition writing. "
                "Create precise, concise definitions (1-2 sentences) for classes in a technical ontology."
            ),
            "connection_proposal": (
                "You are an expert in ontology design. "
                "Identify relationships and properties between the given classes."
            ),
            "disambiguation": (
                "You are an expert in word sense disambiguation. "
                "Identify if any of the given terms have multiple meanings or senses in the context."
            ),
            "confidence_scoring": (
                "You are an expert in information extraction. "
                "Assign confidence scores to extracted candidates based on linguistic evidence."
            ),
        },
        "description": "Default schema extraction pipeline with OpenRouter Gemini 3 Flash",
    }
