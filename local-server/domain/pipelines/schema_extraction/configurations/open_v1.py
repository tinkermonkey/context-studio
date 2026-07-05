"""
Configuration for the open spaCy-based schema extraction implementation.

These keys are the closed-loop optimization surface: the open-extraction
filter, clustering parameters, synthesis mode, top-N truncation, confidence
calibration, and (for llm/hybrid synthesis) the LLM settings. The closed-loop
optimizer (Phase 6) sweeps these and re-runs the quality harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.pipelines.exceptions import PipelineInputError

_SYNTHESIS_MODES = {"rule", "llm", "hybrid"}


def _unit_interval(config: dict[str, Any], key: str, default: float) -> float:
    """Coerce a config value to a float and require it to lie within [0, 1]."""
    value = float(config.get(key, default))
    if not 0.0 <= value <= 1.0:
        raise PipelineInputError(f"{key} must be within [0, 1], got {value}")
    return value


def _non_negative(config: dict[str, Any], key: str, default: float) -> float:
    """Coerce a config value to a float and require it to be >= 0."""
    value = float(config.get(key, default))
    if value < 0.0:
        raise PipelineInputError(f"{key} must be >= 0, got {value}")
    return value


def _positive_int(config: dict[str, Any], key: str, default: int) -> int:
    """Coerce a config value to an int and require it to be > 0."""
    value = int(config.get(key, default))
    if value <= 0:
        raise PipelineInputError(f"{key} must be > 0, got {value}")
    return value


@dataclass(frozen=True)
class SchemaOpenV1Config:
    """
    Typed, validated view of the open_v1 schema-extraction knobs the orchestrator reads.

    Built once from the raw config dict via ``from_dict``, which centralizes type
    coercion and range validation. Only the knobs the orchestrator actually
    consumes are represented; unknown/extra keys in the dict are ignored.
    """

    tf_idf_threshold: float
    include_standalone: bool
    top_n: int
    cluster_distance_threshold: float
    min_cluster_size: int
    synthesis_mode: str
    relation_confidence: float
    use_conceptnet: bool
    conceptnet_relation_limit: int
    conceptnet_confidence: float
    conceptnet_confidence_boost: float
    confidence_critical: float
    confidence_important: float
    confidence_contextual: float
    model: str
    temperature: float
    max_tokens: int

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "SchemaOpenV1Config":
        """Read, coerce, and validate the knobs the schema orchestrator consumes."""
        synthesis_mode = str(config.get("synthesis_mode", "rule"))
        if synthesis_mode not in _SYNTHESIS_MODES:
            raise PipelineInputError(
                f"synthesis_mode must be one of {sorted(_SYNTHESIS_MODES)}, got {synthesis_mode!r}"
            )
        return cls(
            tf_idf_threshold=_non_negative(config, "tf_idf_threshold", 0.0),
            include_standalone=bool(config.get("include_standalone", True)),
            top_n=_positive_int(config, "top_n", 8),
            cluster_distance_threshold=_non_negative(config, "cluster_distance_threshold", 0.25),
            min_cluster_size=_positive_int(config, "min_cluster_size", 1),
            synthesis_mode=synthesis_mode,
            relation_confidence=_unit_interval(config, "relation_confidence", 0.5),
            use_conceptnet=bool(config.get("use_conceptnet", False)),
            conceptnet_relation_limit=_positive_int(config, "conceptnet_relation_limit", 50),
            conceptnet_confidence=_unit_interval(config, "conceptnet_confidence", 0.7),
            conceptnet_confidence_boost=_unit_interval(config, "conceptnet_confidence_boost", 0.1),
            confidence_critical=_unit_interval(config, "confidence_critical", 0.8),
            confidence_important=_unit_interval(config, "confidence_important", 0.6),
            confidence_contextual=_unit_interval(config, "confidence_contextual", 0.4),
            model=str(config.get("model", "google/gemini-3-flash-preview")),
            temperature=_non_negative(config, "temperature", 0.0),
            max_tokens=_positive_int(config, "max_tokens", 1500),
        )


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
        # --- ConceptNet enrichment (external knowledge; off by default for
        #     offline/deterministic runs — toggled by the closed loop) ---
        "use_conceptnet": False,
        "conceptnet_relation_limit": 50,
        "conceptnet_confidence": 0.7,  # confidence for ConceptNet-grounded connections
        "conceptnet_confidence_boost": 0.1,  # bump for classes ConceptNet recognizes
        "description": "Open spaCy extraction + clustering + synthesis schema extraction",
    }
