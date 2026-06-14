"""
Configuration for the open spaCy-based individual extraction implementation.

The closed-loop optimization surface for the individuals flow: open-extraction
filter, predicate form, schema-grounding via the SchemaVectorIndex, similarity
threshold, and confidence calibration.
"""


def get_open_v1_config() -> dict:
    """Return the default configuration for the open_v1 individual extraction pipeline."""
    return {
        # --- open spaCy extraction ---
        "spacy_model": "en_core_web_sm",
        "tf_idf_threshold": 0.0,
        # --- triple shaping ---
        # GT predicates use 3rd-person surface verbs ("improves"), so "surface"
        # matches more than "lemma"; both exposed as a tuning knob.
        "predicate_form": "surface",  # lemma | surface
        # --- schema grounding (SchemaVectorIndex) ---
        "ground_to_schema": False,  # emit rdf:type triples for matched schema classes
        "require_schema_match": False,  # keep only individuals matching a schema node
        "similarity_threshold": 0.45,
        "kinds_to_search": ["class"],
        # --- confidence calibration (Brier knob) ---
        "relation_confidence": 0.7,
        # --- optional LLM disambiguation (llm modes; needs cassettes) ---
        "llm_disambiguation": False,
        "provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 1500,
        "description": "Open spaCy extraction + dependency-triple individual extraction",
    }
