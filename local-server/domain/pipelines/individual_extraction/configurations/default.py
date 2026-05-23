"""
Default configuration for Individual Extraction pipeline.

Loads Wave A's extraction-default.json configuration, preserving the original
Anthropic/Claude Opus provider and model choice.
"""


def get_default_config() -> dict:
    """
    Return the default individual extraction configuration.

    This loads the existing Wave A extraction-default.json, preserving
    backward compatibility with existing extraction runs and benchmarks.

    Returns:
        Configuration dict with LLM settings (Anthropic provider)
    """
    return {
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "temperature": 0.0,
        "max_tokens": 4096,
        "system_prompt": "You are a knowledge graph extraction assistant. Extract structured triples from text that conform to the provided ontology. Return only triples that are explicitly supported by the text.",
        "user_prompt_template": "Extract triples from the following text using the ontology provided.\n\nOntology classes and properties:\n{ontology}\n\nText:\n{text}\n\nReturn a JSON array of triples with subject, predicate, object, confidence (0-1), and provenance (text offsets).",
        "seed": None,
        "description": "Default individual extraction pipeline with Anthropic Claude Opus (Wave A compatible)",
    }


def get_openrouter_config() -> dict:
    """
    Return the OpenRouter-based individual extraction configuration.

    This is a new variant that uses google/gemini-3-flash-preview via OpenRouter,
    matching the framework default for Phase 4B.

    Returns:
        Configuration dict with LLM settings (OpenRouter provider)
    """
    return {
        "provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 4096,
        "system_prompt": "You are a knowledge graph extraction assistant. Extract structured triples from text that conform to the provided ontology. Return only triples that are explicitly supported by the text.",
        "user_prompt_template": "Extract triples from the following text using the ontology provided.\n\nOntology classes and properties:\n{ontology}\n\nText:\n{text}\n\nReturn a JSON array of triples with subject, predicate, object, confidence (0-1), and provenance (text offsets).",
        "seed": None,
        "description": "Individual extraction pipeline with OpenRouter Gemini 3 Flash",
    }
