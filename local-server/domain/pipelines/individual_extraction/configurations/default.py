"""
Configurations of the two-pass, find-then-type and single-call Individual
Extraction implementations, loaded from the JSON files in configs/.

Each file's max_tokens is the most output tokens one model call of a run may
produce. Claude 5.5 models think before they answer and the thinking counts
toward it, so their limits are well above what the answer alone needs.
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

    Loads extraction-default.json, which uses Claude Haiku 5.5 through the
    Anthropic provider.

    Returns:
        Configuration dict with LLM settings (Anthropic provider)
    """
    config = _load_config_from_file("extraction-default.json")
    config["description"] = "Default individual extraction pipeline with Anthropic Claude Haiku 5.5"
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


def get_single_call_config() -> dict:
    """
    Return the configuration of the single-call implementation.

    Loads extraction-single-call.json: Claude Opus 5.5 through the Anthropic
    provider, the model of the head-to-head's one call. ``effort`` ("high") is
    what the call that finds the individuals asks for; the relate calls ask
    for the model's default. ``max_tokens`` (64,000) is for that call, which
    thinks and then lists every individual of a whole document: the
    Anthropic provider streams a request asking for more than 20,000.

    Returns:
        Configuration dict with LLM settings (Anthropic provider)
    """
    config = _load_config_from_file("extraction-single-call.json")
    config["description"] = (
        "Single-call individual extraction with Claude Opus 5.5: one call finds and types "
        "every individual of the text against the whole class catalog, then relationships "
        "are read chunk by chunk with the predicates each class allows"
    )
    return config
