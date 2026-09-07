"""
Configuration for the open spaCy-based individual extraction implementation.

The closed-loop optimization surface for the individuals flow: open-extraction
filter, predicate form, schema-grounding via the SchemaVectorIndex, similarity
threshold, and confidence calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from domain.ontology.ports import MatchingMode, SchemaKind
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
    llm_canonicalization: bool
    ground_predicates: bool
    coverage_completion: bool
    predicate_similarity_threshold: float
    model: str
    temperature: float
    max_tokens: int
    nlp_grounded_typing: bool
    nlp_typing_top_k: int
    nlp_typing_threshold: float
    nlp_typing_matching_mode: MatchingMode | None

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
        # Held separately from similarity_threshold: a bare predicate verb queried
        # against a property definition's "source predicate destination" title sits
        # in a different similarity regime than a noun phrase against a class title,
        # so predicate grounding needs its own calibration (Loop A tunes it apart).
        predicate_similarity_threshold = float(config.get("predicate_similarity_threshold", 0.45))
        if not 0.0 <= predicate_similarity_threshold <= 1.0:
            raise PipelineInputError(
                "predicate_similarity_threshold must be within [0, 1], got "
                f"{predicate_similarity_threshold}"
            )

        nlp_grounded_typing = bool(config.get("nlp_grounded_typing", False))
        ground_to_schema = bool(config.get("ground_to_schema", False))
        require_schema_match = bool(config.get("require_schema_match", False))

        if nlp_grounded_typing and (ground_to_schema or require_schema_match):
            raise PipelineInputError(
                "nlp_grounded_typing is mutually exclusive with "
                "ground_to_schema and require_schema_match"
            )

        nlp_typing_top_k = int(config.get("nlp_typing_top_k", 8))
        if nlp_typing_top_k < 1:
            raise PipelineInputError(f"nlp_typing_top_k must be >= 1, got {nlp_typing_top_k}")

        nlp_typing_threshold = float(config.get("nlp_typing_threshold", 0.2))
        if not 0.0 <= nlp_typing_threshold <= 1.0:
            raise PipelineInputError(
                f"nlp_typing_threshold must be within [0, 1], got {nlp_typing_threshold}"
            )

        nlp_typing_matching_mode: MatchingMode | None = None
        if config.get("nlp_typing_matching_mode") is not None:
            matching_mode_str = str(config.get("nlp_typing_matching_mode"))
            if matching_mode_str not in {"max", "definition_preferred"}:
                raise PipelineInputError(
                    f"nlp_typing_matching_mode must be 'max' or 'definition_preferred', "
                    f"got {matching_mode_str!r}"
                )
            nlp_typing_matching_mode = cast(MatchingMode, matching_mode_str)

        return cls(
            relation_confidence=relation_confidence,
            predicate_form=predicate_form,
            ground_to_schema=ground_to_schema,
            require_schema_match=require_schema_match,
            similarity_threshold=similarity_threshold,
            kinds_to_search=kinds_to_search,
            llm_canonicalization=bool(config.get("llm_canonicalization", False)),
            ground_predicates=bool(config.get("ground_predicates", False)),
            coverage_completion=bool(config.get("coverage_completion", False)),
            predicate_similarity_threshold=predicate_similarity_threshold,
            model=str(config.get("model", "google/gemini-3-flash-preview")),
            temperature=float(config.get("temperature", 0.0)),
            max_tokens=int(config.get("max_tokens", 1500)),
            nlp_grounded_typing=nlp_grounded_typing,
            nlp_typing_top_k=nlp_typing_top_k,
            nlp_typing_threshold=nlp_typing_threshold,
            nlp_typing_matching_mode=nlp_typing_matching_mode,
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
        # --- predicate grounding (SchemaVectorIndex, property_definition kind) ---
        # Clamp each extracted triple's free-form predicate onto the ontology's
        # defined object-property vocabulary by matching it against property
        # definitions' curated title+definition embeddings. Off by default;
        # self-skips with no index / no repo / unresolvable ontology.
        "ground_predicates": False,
        "predicate_similarity_threshold": 0.45,
        # --- coverage completion (unconsumed noun chunks + wider dependency capture) ---
        # The dominant miss class is candidate_missing: entities the SVO triples
        # never surface. This stage emits noun chunks left unconsumed by the SVO
        # dependency triples as candidate individuals — but only after grounding
        # each against the schema class vocabulary (so generic chunks are dropped)
        # AND deriving their relations in the same pass via wider dependency
        # capture (ccomp/xcomp/acomp, passive agent, conjunct fan-out). A surfaced
        # candidate is emitted only WITH a derived relation, never as a bare
        # dangling individual — surfacing without deriving relations regresses the
        # metric (relation_not_derived jumps). Off by default; self-skips with no
        # index / no repo / unresolvable ontology.
        "coverage_completion": False,
        # --- NLP-grounded typing ---
        # Noun chunks are typed via vector retrieval + LLM confirmation, restricted
        # to picking from retrieved candidate classes only (never generating labels).
        # Mutually exclusive with ground_to_schema / require_schema_match. Off by
        # default; self-skips with no schema index / no LLM provider / unresolvable
        # ontology. Runs in place of _ground_to_schema when enabled.
        "nlp_grounded_typing": False,
        "nlp_typing_top_k": 8,  # candidates retrieved per chunk
        "nlp_typing_threshold": 0.2,  # minimum similarity for a candidate
        "nlp_typing_matching_mode": (
            None
        ),  # override index's matching mode (max / definition_preferred)
        # --- confidence calibration (Brier knob) ---
        "relation_confidence": 0.7,
        # --- LLM label canonicalization (needs an LLM provider + cassettes) ---
        # One cheap LLM call per document rewrites each extracted individual's
        # snake_case label to its canonical ontology title, chosen from the
        # schema vocabulary. Off by default: self-skips with no LLM provider or
        # no resolvable ontology, so offline rule-mode runs are unaffected.
        "llm_canonicalization": False,
        # --- optional LLM disambiguation (llm modes; needs cassettes) ---
        "llm_disambiguation": False,
        "provider": "openrouter",
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "max_tokens": 1500,
        "description": "Open spaCy extraction + dependency-triple individual extraction",
    }
