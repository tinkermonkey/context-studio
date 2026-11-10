"""
Default configuration for the notes-to-claims pipeline.

The categories are DR's triage vocabulary, shared with the claim triage
pipeline (cli/scripts/spec-enrich/lib/triage-types.ts CATEGORIES); a
configuration for another taxonomy can list its own.
"""

from domain.pipelines.claim_triage.configurations.default import DR_CATEGORIES


def get_default_config() -> dict:
    """Return the default notes-to-claims configuration."""
    return {
        "description": "Split notes into atomic claims with OpenRouter Gemini 3 Flash",
        "llm_provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 4000,
        # Notes split at once (DR's split-notes.ts default)
        "concurrency": 6,
        "categories": dict(DR_CATEGORIES),
    }
