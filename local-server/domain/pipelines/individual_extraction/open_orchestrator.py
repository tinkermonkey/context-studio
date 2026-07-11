"""
Open individual-extraction orchestrator (implementation "open_v1").

A spaCy-driven alternative to the LLM-only default: open extraction produces
subject--(verb)-->object dependency triples directly, formatted as individual
triples. Optionally grounds extracted individuals to existing schema classes via
the SchemaVectorIndex (semantic search over class titles/definitions).

Pipeline: open extraction → dependency relations → individual triples →
(optional) schema grounding → result contract.

Output uses the same {triples, warnings, metadata} contract as the default
implementation, so the quality suite runs against it unchanged. Coexists with
"default" for A/B comparison.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from domain.extraction.open_extraction import (
    RelationCandidate,
    build_relation_candidates,
    snake_label,
)
from domain.extraction.ports import NLPProcessor, OpenExtractionResult
from domain.ontology.ports import EmbeddingService, OntologyRepository, SchemaVectorIndex
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    IndividualOpenV1Config,
    get_open_v1_config,
)
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionState
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import LLMProvider, PipelineRunStatusWriter

_logger = logging.getLogger(__name__)


class OpenIndividualExtractionOrchestrator(PipelineOrchestrator):
    """
    Individual extraction via open spaCy dependency parsing + optional grounding.

    Injected ports keep the domain pure: an NLP processor (open extraction), an
    embedding service (grounding queries), and an optional SchemaVectorIndex
    (semantic search over existing schema nodes). The LLM provider is only used
    by the optional disambiguation pass.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None,
        nlp_processor: NLPProcessor,
        embedding_service: EmbeddingService,
        schema_index: SchemaVectorIndex | None = None,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
        config: dict[str, Any] | None = None,
        ontology_repo: OntologyRepository | None = None,
    ) -> None:
        super().__init__(llm_provider, run_id, status_writer)
        self._nlp = nlp_processor
        self._embedding = embedding_service
        self._schema_index = schema_index
        self._ontology_repo = ontology_repo
        self._cfg = IndividualOpenV1Config.from_dict(config or get_open_v1_config())

    async def execute(self, state: PipelineState) -> PipelineState:
        """Run the open individual-extraction pipeline and populate state.result."""
        self._write_running_status()

        text = state.input_data.get("text", "")
        if not text or not text.strip():
            raise PipelineInputError("text is required and cannot be empty")

        try:
            open_result = self._nlp.process_open(text)
            if text.strip() and not open_result.tokens:
                raise PipelineExecutionError(
                    "NLP produced no tokens for non-empty input; the spaCy model is "
                    "likely not available"
                )
            relations = build_relation_candidates(open_result)
            triples = self._build_triples(open_result, relations)

            if self._cfg.ground_to_schema or self._cfg.require_schema_match:
                triples = self._ground_to_schema(triples, state.input_data.get("ontology_id"))

            warnings: list[str] = []
            metadata: dict[str, Any] = {
                "implementation": "open_v1",
                "relation_count": len(relations),
                "triple_count": len(triples),
            }
        except (PipelineInputError, PipelineExecutionError):
            raise
        except Exception as exc:  # noqa: BLE001 - re-wrapped as a pipeline error
            _logger.error("Open individual extraction failed: %s", exc, exc_info=True)
            raise PipelineExecutionError(
                "Open individual extraction encountered an unexpected error"
            ) from exc

        if not isinstance(state, IndividualExtractionState):
            state = IndividualExtractionState(
                run_id=state.run_id,
                pipeline_type=state.pipeline_type,
                input_data=state.input_data,
                current_status=state.current_status,
                llm_provider=state.llm_provider,
                result=state.result,
            )
        return replace(
            state,
            extracted_triples=triples,
            warnings=warnings,
            metadata=metadata,
            result={"triples": triples, "warnings": warnings, "metadata": metadata},
            current_status=PipelineRunStatus.COMPLETED,
        )

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------

    def _build_triples(
        self, open_result: OpenExtractionResult, relations: list[RelationCandidate]
    ) -> list[dict[str, Any]]:
        """Format dependency relations as individual triples, de-duplicated."""
        confidence = self._cfg.relation_confidence
        predicate_form = self._cfg.predicate_form
        triples: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for rel in relations:
            subject = snake_label(rel.subject_lemmas) or _snake(rel.subject)
            obj = snake_label(rel.object_lemmas) or _snake(rel.object)
            if predicate_form == "surface":
                predicate = open_result.tokens[rel.verb_index].text.lower()
            else:
                predicate = rel.predicate
            if not subject or not predicate or not obj:
                continue
            key = (subject, predicate, obj)
            if key in seen:
                continue
            seen.add(key)
            triples.append(
                {
                    "subject": {"label": subject, "kind": "individual"},
                    "predicate": {"label": predicate, "kind": "property"},
                    "object": {"label": obj, "kind": "individual"},
                    "confidence": confidence,
                }
            )
        return triples

    def _ground_to_schema(
        self, triples: list[dict[str, Any]], ontology_id: str | None
    ) -> list[dict[str, Any]]:
        """
        Use the SchemaVectorIndex to match individuals to existing schema classes.

        Adds is_a triples for individuals whose phrase matches a class above the
        similarity threshold, with the matched class's external schema identifier
        (e.g. "motivation.goal") as the object when it has one. When
        require_schema_match is set, drops triples whose subject AND object both
        fail to match any schema node.

        Grounding is scoped to the ontology named by ``ontology_id`` (the
        scenario's source taxonomy). If there is no index, no repository, or the
        identifier does not resolve to a known taxonomy, grounding is skipped and
        the triples are returned unchanged — a single workspace can hold several
        imported ontologies, and matching across all of them would ground an
        individual to an unrelated ontology's class.
        """
        if self._schema_index is None:
            return triples

        taxonomy = (
            self._ontology_repo.get_by_identifier(ontology_id)
            if self._ontology_repo is not None and ontology_id
            else None
        )
        if taxonomy is None:
            return triples

        threshold = self._cfg.similarity_threshold
        kinds = list(self._cfg.kinds_to_search)
        emit_types = self._cfg.ground_to_schema
        require_match = self._cfg.require_schema_match

        # Resolve each distinct individual label to its best schema match.
        individuals = {t[role]["label"] for t in triples for role in ("subject", "object")}
        matched: dict[str, Any] = {}
        for label in individuals:
            query = self._embedding.embed(label.replace("_", " "))
            results = self._schema_index.search(
                query, kinds=kinds, top_k=1, threshold=threshold, taxonomy_id=taxonomy.id
            )
            if results:
                matched[label] = results[0]

        kept = triples
        if require_match:
            kept = [
                t
                for t in triples
                if t["subject"]["label"] in matched or t["object"]["label"] in matched
            ]

        if emit_types:
            # Only assert rdf:type for individuals that still appear in a kept
            # triple; require_schema_match may have dropped an individual's only
            # source triples, so it should not receive a type assertion.
            kept_labels = {t[role]["label"] for t in kept for role in ("subject", "object")}
            type_triples: list[dict[str, Any]] = []
            for label, match in matched.items():
                if label not in kept_labels:
                    continue
                # Object is the matched class's external schema identifier (e.g.
                # "motivation.goal") when it has one, so the grounding matches the
                # source ontology's vocabulary; the human-readable title is the
                # fallback. kind stays "class" (semantically honest; the scored
                # triple key ignores object kind).
                type_triples.append(
                    {
                        "subject": {"label": label, "kind": "individual"},
                        "predicate": {"label": "is_a", "kind": "property"},
                        "object": {
                            "label": match.external_id or match.label,
                            "kind": "class",
                        },
                        "confidence": round(match.score, 4),
                    }
                )
            kept = kept + type_triples

        return kept


def _snake(phrase: str) -> str:
    """Fallback snake_case from a surface phrase."""
    return "_".join(word.lower() for word in phrase.split() if word)
