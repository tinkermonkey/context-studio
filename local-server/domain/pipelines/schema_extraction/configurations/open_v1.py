"""
Configuration for the open spaCy-based schema extraction implementation.

These keys are the closed-loop optimization surface: the open-extraction
filter, clustering parameters, synthesis mode, top-N truncation, confidence
calibration, and (for llm/hybrid synthesis) the LLM settings. The closed-loop
optimizer (Phase 6) sweeps these and re-runs the quality harness.
"""


def get_open_v1_config() -> dict:
    """Return the default configuration for the open_v1 schema extraction pipeline."""
    return {
        # --- open spaCy extraction ---
        "spacy_model": "en_core_web_sm",
        "tf_idf_threshold": 0.0,  # openness dial; 0.0 = keep all candidates
        "include_standalone": True,
        # --- clustering (distillation) ---
        "cluster_algorithm": "agglomerative",
        "cluster_distance_threshold": 0.25,
        "min_cluster_size": 1,
        # --- synthesis ---
        "synthesis_mode": "rule",  # rule | llm | hybrid
        "top_n": 8,
        # --- LLM settings (used by llm/hybrid synthesis) ---
        "provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 1500,
        # --- confidence calibration by grammatical-role priority (Brier knob) ---
        "confidence_critical": 0.8,
        "confidence_important": 0.6,
        "confidence_contextual": 0.4,
        "relation_confidence": 0.5,
        "description": "Open spaCy extraction + clustering + synthesis schema extraction",
    }
