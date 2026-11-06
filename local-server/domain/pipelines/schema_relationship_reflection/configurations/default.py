"""
Default configuration for the schema relationship reflection pipeline.

The decision model is the configured default instance (decision_model None);
naming an instance here picks another one.
"""

# ArchiMate 3.2 core relationships, offered after a type's own predicates as
# DR's reflection offers them; a taxonomy that does not use one never sees it.
GENERAL_PREDICATES = [
    "realizes",
    "serves",
    "assigned-to",
    "composes",
    "aggregates",
    "accesses",
    "triggers",
    "flows-to",
    "uses",
    "depends-on",
    "associated-with",
    "specializes",
    "references",
]


def get_default_config() -> dict:
    """Return the default reflection configuration."""
    return {
        "description": (
            "Sorting questions per relationship type, answered by the default decision model"
        ),
        "decision_model": None,
        "top": 8,
        "context_policy": "summary",
        "general_predicates": list(GENERAL_PREDICATES),
    }
