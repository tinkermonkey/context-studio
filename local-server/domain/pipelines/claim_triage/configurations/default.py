"""
Default configuration for the claim triage pipeline.

The decision model is the configured default instance (decision_model None).
The categories are DR's triage vocabulary (cli/scripts/spec-enrich/lib/
triage-types.ts CATEGORIES); a configuration for another taxonomy can list
its own.
"""

DR_CATEGORIES = {
    "attribute_typing": (
        "An attribute's type, required-ness or value format is wrong or inconsistent with how"
        " siblings or the standard treat it"
    ),
    "attribute_naming": (
        "An attribute's name is misleading, collides with another concept, or differs from"
        " siblings for no reason"
    ),
    "enum_gap": "An enum lacks values that real systems need, or mixes values from different axes",
    "missing_attribute": (
        "The type cannot capture something essential about its instances because an attribute"
        " is absent"
    ),
    "type_overlap": (
        "Two element types (in this or another layer) cover the same things and need a boundary"
        " or precedence rule"
    ),
    "definition_conflict": (
        "The type's definition contradicts its attributes, its relationships, or its layer's"
        " intent"
    ),
    "relationship_redundant": (
        "Two relationship types between the same pair express the same meaning"
    ),
    "relationship_direction": (
        "A relationship points the wrong way or uses a predicate whose semantics do not fit"
    ),
    "relationship_missing": "A relationship that real models need does not exist in the catalog",
    "classifier_concern": (
        "The concern is about whether a classifier can recognise instances from code, not about"
        " the spec's correctness"
    ),
    "other": "None of the above",
}


def get_default_config() -> dict:
    """Return the default triage configuration."""
    return {
        "description": "Triage questions per claim, answered by the default decision model",
        "decision_model": None,
        "context_policy": "summary",
        "categories": dict(DR_CATEGORIES),
    }
