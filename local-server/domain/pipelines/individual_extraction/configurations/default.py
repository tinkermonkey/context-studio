"""
Default configuration for Individual Extraction pipeline.

Loads Wave A's extraction-default.json configuration, preserving the original
Anthropic/Claude Opus provider and model choice.
"""

import json
from pathlib import Path


def _load_config_from_file(filename: str) -> dict:
    """Load configuration from JSON file in configs/ directory."""
    config_path = Path(__file__).parent.parent.parent.parent.parent / "configs" / filename
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r") as f:
        return json.load(f)


def get_default_config() -> dict:
    """
    Return the default individual extraction configuration.

    Loads the existing Wave A extraction-default.json, preserving
    backward compatibility with existing extraction runs and benchmarks.

    Returns:
        Configuration dict with LLM settings (Anthropic provider)
    """
    config = _load_config_from_file("extraction-default.json")
    config["description"] = (
        "Default individual extraction pipeline with Anthropic Claude Opus (Wave A compatible)"
    )
    return config


def get_openrouter_config() -> dict:
    """
    Return the OpenRouter-based individual extraction configuration.

    Loads extraction-openrouter-default.json which uses google/gemini-3-flash-preview
    via OpenRouter, matching the framework default for Phase 4B.

    Returns:
        Configuration dict with LLM settings (OpenRouter provider)
    """
    config = _load_config_from_file("extraction-openrouter-default.json")
    config["description"] = "Individual extraction pipeline with OpenRouter Gemini 3 Flash"
    return config


def get_find_then_type_config() -> dict:
    """
    Return the configuration of the find-then-type implementation.

    Loads extraction-find-then-type.json, which uses Claude Haiku 5.5 through
    the Anthropic provider: that provider caches the class catalog every typing
    call of a run shares, which is what keeps one call per mention affordable.

    Returns:
        Configuration dict with LLM settings (Anthropic provider)
    """
    config = _load_config_from_file("extraction-find-then-type.json")
    config["description"] = (
        "Find-then-type individual extraction with Claude Haiku 5.5: finds what the "
        "text mentions, then types each mention against the whole class catalog"
    )
    return config
