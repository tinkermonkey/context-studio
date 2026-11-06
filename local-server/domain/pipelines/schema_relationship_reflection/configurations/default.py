"""
Default configuration for the schema relationship reflection pipeline.

The decision model is the configured default instance (decision_model None);
naming an instance here picks another one.
"""


def get_default_config() -> dict:
    """Return the default reflection configuration."""
    return {
        "description": (
            "Sorting questions per relationship type, answered by the default decision model"
        ),
        "decision_model": None,
        "top": 8,
        "context_policy": "summary",
    }
