"""
Configuration for the open spaCy-based individual extraction implementation.

The closed-loop optimization surface for the individuals flow: open-extraction
filter, predicate form, schema-grounding via the SchemaVectorIndex, similarity
threshold, and confidence calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from domain.ontology.ports import SchemaKind
from domain.pipelines.exceptions import PipelineInputError

_PREDICATE_FORMS = {"lemma", "surface"}
_SEARCH_KINDS = {"class", "property_definition", "relationship"}


@dataclass(frozen=True)
class IndividualOpenV1Config:
    """
    Typed, validated view of the open_v1 individual-extraction knobs the orchestrator reads.

    Built once from the raw config dict via ``from_dict``, which centralizes type
    coercion and range validation. Only the knobs the orchestrator actually
    consumes are represented; unknown/extra keys in the dict are ignored. Note the
    ``relation_confidence`` default (0.7) differs from the schema pipeline's (0.5).
    """

    relation_confidence: float
    predicate_form: str
    ground_to_schema: bool
    require_schema_match: bool
    similarity_threshold: float
    kinds_to_search: tuple[SchemaKind, ...]

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "IndividualOpenV1Config":
        """Read, coerce, and validate the knobs the individual orchestrator consumes."""
        predicate_form = str(config.get("predicate_form", "lemma"))
        if predicate_form not in _PREDICATE_FORMS:
            raise PipelineInputError(
                f"predicate_form must be one of {sorted(_PREDICATE_FORMS)}, got {predicate_form!r}"
            )
        raw_kinds = tuple(str(k) for k in config.get("kinds_to_search", ["class"]))
        invalid = [k for k in raw_kinds if k not in _SEARCH_KINDS]
        if invalid:
            raise PipelineInputError(
                f"kinds_to_search must be a subset of {sorted(_SEARCH_KINDS)}, got {invalid}"
            )
        kinds_to_search = cast(tuple[SchemaKind, ...], raw_kinds)
        relation_confidence = float(config.get("relation_confidence", 0.7))
        if not 0.0 <= relation_confidence <= 1.0:
            raise PipelineInputError(
                f"relation_confidence must be within [0, 1], got {relation_confidence}"
            )
        similarity_threshold = float(config.get("similarity_threshold", 0.45))
        if not 0.0 <= similarity_threshold <= 1.0:
            raise PipelineInputError(
                f"similarity_threshold must be within [0, 1], got {similarity_threshold}"
            )
        return cls(
            relation_confidence=relation_confidence,
            predicate_form=predicate_form,
            ground_to_schema=bool(config.get("ground_to_schema", False)),
            require_schema_match=bool(config.get("require_schema_match", False)),
            similarity_threshold=similarity_threshold,
            kinds_to_search=kinds_to_search,
        )


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
        "ground_to_schema": False,  # emit is_a triples for matched schema classes
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
