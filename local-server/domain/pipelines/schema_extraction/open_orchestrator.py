"""
Open schema-extraction orchestrator (implementation "open_v1").

A spaCy-driven alternative to the LLM-only default: open extraction surfaces a
high-recall superset of concept/relation candidates, clustering distils them,
and a synthesis step turns cluster representatives into schema-node labels +
definitions. Coexists with the "default" implementation for A/B comparison via
the quality harness.

Pipeline: open extraction → embed → cluster → select representatives →
synthesize labels (rule | llm | hybrid) → top-N → relations → result contract.

The output uses the same CandidateClass / CandidatePropertyDefinition /
CandidateConnection contract as the default orchestrator, so the quality suite
runs against it unchanged.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from typing import Any

from domain.extraction.open_extraction import (
    ConceptCandidate,
    ConceptPriority,
    OpenExtractionParams,
    build_concept_candidates,
    build_relation_candidates,
    pascal_label,
    select_cluster_representatives,
    synthesize_label,
)
from domain.extraction.ports import ClusteringPort, NLPProcessor, ReferenceSource
from domain.ontology.ports import EmbeddingService
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import LLMProvider, PipelineRunStatusWriter
from domain.pipelines.schema_extraction.configurations.open_v1 import get_open_v1_config
from domain.pipelines.schema_extraction.orchestrator import (
    CandidateClass,
    CandidateConnection,
    CandidatePropertyDefinition,
)

_logger = logging.getLogger(__name__)


def _pascal(phrase: str) -> str:
    """PascalCase a surface phrase ('event loop' -> 'EventLoop')."""
    return "".join(word.capitalize() for word in phrase.split() if word)


def _concept_term(label: str) -> str:
    """PascalCase class label -> ConceptNet concept term ('ConsensusAlgorithm' -> 'consensus_algorithm')."""
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+", label)
    return "_".join(w.lower() for w in words) if words else label.lower()


def _extract_json_obj(content: str) -> str:
    """Extract the first {...} JSON object from an LLM response (tolerates code fences/prose)."""
    match = re.search(r"\{.*\}", content, re.DOTALL)
    return match.group(0) if match else content


def _concept_term_from_uri(uri: str) -> str | None:
    """Extract the concept term from a ConceptNet URI ('/c/en/algorithm/n' -> 'algorithm')."""
    parts = uri.split("/")
    # ['', 'c', 'en', '<term>', optional pos] -> term at index 3
    if len(parts) >= 4 and parts[1] == "c":
        return parts[3] or None
    return None


class OpenSchemaExtractionOrchestrator(PipelineOrchestrator):
    """
    Schema extraction via open spaCy extraction + clustering + synthesis.

    Injected ports keep the domain pure: an NLP processor (open extraction), an
    embedding service (cluster vectors), and a clustering port. The LLM provider
    is only used by the llm/hybrid synthesis modes.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None,
        nlp_processor: NLPProcessor,
        embedding_service: EmbeddingService,
        clusterer: ClusteringPort,
        ontology_repo: Any = None,
        reference_source: ReferenceSource | None = None,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(llm_provider, run_id, status_writer)
        self._nlp = nlp_processor
        self._embedding = embedding_service
        self._clusterer = clusterer
        self._ontology_repo = ontology_repo
        self._reference_source = reference_source
        self._config = config or get_open_v1_config()

    async def execute(self, state: PipelineState) -> PipelineState:
        """Run the open schema-extraction pipeline and populate state.result."""
        self._write_running_status()

        documents = state.input_data.get("documents", [])
        if not documents or not any(d.strip() for d in documents if isinstance(d, str)):
            raise PipelineInputError(
                "documents is required and must contain at least one non-empty document"
            )
        source_text = " ".join(d for d in documents if isinstance(d, str))

        try:
            open_result = self._nlp.process_open(source_text)
            params = OpenExtractionParams(
                tf_idf_threshold=float(self._config.get("tf_idf_threshold", 0.0)),
                include_standalone=bool(self._config.get("include_standalone", True)),
            )
            candidates = build_concept_candidates(open_result, params)
            representatives = self._cluster_and_select(candidates)
            top = representatives[: int(self._config.get("top_n", 8))]

            classes = await self._synthesize_classes(top, source_text)
            relations = build_relation_candidates(open_result)
            properties, connections = self._build_relations(relations, classes)

            if self._config.get("use_conceptnet") and self._reference_source is not None:
                classes, connections = await self._enrich_with_conceptnet(classes, connections)

            result = self._finalize(classes, properties, connections)
        except PipelineInputError:
            raise
        except Exception as exc:  # noqa: BLE001 - re-wrapped as a pipeline error
            _logger.error("Open schema extraction failed: %s", exc, exc_info=True)
            raise PipelineExecutionError(
                "Open schema extraction encountered an unexpected error"
            ) from exc

        return replace(state, result=result, current_status=PipelineRunStatus.COMPLETED)

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------

    def _cluster_and_select(self, candidates: list[ConceptCandidate]) -> list[ConceptCandidate]:
        """Embed candidate texts, cluster, and pick one representative per cluster."""
        if not candidates:
            return []
        vectors = self._embedding.embed_batch([c.text for c in candidates])
        assignments = self._clusterer.cluster(
            vectors,
            distance_threshold=float(self._config.get("cluster_distance_threshold", 0.25)),
            min_cluster_size=int(self._config.get("min_cluster_size", 1)),
        )
        return select_cluster_representatives(candidates, assignments)

    async def _synthesize_classes(
        self, representatives: list[ConceptCandidate], source_text: str
    ) -> list[CandidateClass]:
        """
        Turn cluster representatives into CandidateClass objects per synthesis_mode:

        - rule: rule-derived PascalCase labels + template definitions (offline).
        - hybrid: rule-derived labels + LLM-written definitions.
        - llm: the LLM proposes the canonical labels AND definitions (this is the
          lever that can move class_jaccard, since labels are no longer rule-bound).
        """
        mode = self._config.get("synthesis_mode", "rule")
        if mode == "llm" and self._llm_provider is not None:
            return await self._llm_synthesize_classes(representatives, source_text)

        # rule / hybrid: rule-derived PascalCase labels, de-duplicated in priority order.
        pairs: list[tuple[ConceptCandidate, str]] = []
        seen: set[str] = set()
        for rep in representatives:
            label = synthesize_label(rep)
            if label and label not in seen:
                seen.add(label)
                pairs.append((rep, label))

        definitions: dict[str, str] = {}
        if mode == "hybrid" and self._llm_provider is not None:
            definitions = await self._llm_definitions([label for _, label in pairs], source_text)

        classes: list[CandidateClass] = []
        for rep, label in pairs:
            definition = definitions.get(label) or f"{label}: a domain concept."
            classes.append(
                CandidateClass(
                    label=label,
                    proposed_definition=definition,
                    confidence=self._confidence(rep.priority),
                    provenance=self._provenance(rep, source_text),
                )
            )
        return classes

    async def _llm_synthesize_classes(
        self, representatives: list[ConceptCandidate], source_text: str
    ) -> list[CandidateClass]:
        """LLM proposes a canonical PascalCase label + definition per representative phrase."""
        rep_by_phrase: dict[str, ConceptCandidate] = {}
        phrases: list[str] = []
        for rep in representatives:
            text = rep.text.strip()
            if text and text not in rep_by_phrase:
                rep_by_phrase[text] = rep
                phrases.append(text)
        if not phrases:
            return []

        mapping = await self._llm_labels_and_definitions(phrases, source_text)

        classes: list[CandidateClass] = []
        seen_labels: set[str] = set()
        for phrase in phrases:
            rep = rep_by_phrase[phrase]
            entry = mapping.get(phrase) or {}
            label = (entry.get("label") or synthesize_label(rep)).strip()
            if not label or label in seen_labels:
                continue
            seen_labels.add(label)
            definition = entry.get("definition") or f"{label}: a domain concept."
            classes.append(
                CandidateClass(
                    label=label,
                    proposed_definition=definition,
                    confidence=self._confidence(rep.priority),
                    provenance=self._provenance(rep, source_text),
                )
            )
        return classes

    def _build_relations(
        self, relations, classes: list[CandidateClass]
    ) -> tuple[list[CandidatePropertyDefinition], list[CandidateConnection]]:
        """
        Build connections between synthesized classes and property definitions
        from their predicates. Only relations whose subject AND object map to a
        synthesized class are kept, to tie connections to the schema.
        """
        class_labels = {c.label for c in classes}
        rel_confidence = float(self._config.get("relation_confidence", 0.5))
        connections: list[CandidateConnection] = []
        properties: list[CandidatePropertyDefinition] = []
        seen_conn: set[tuple[str, str, str]] = set()
        seen_prop: set[str] = set()

        for rel in relations:
            # Match on the SAME lemma-derived PascalCase label that produced the
            # class labels (rel.subject/object are raw surface text and would
            # diverge on plurals/determiners, dropping every connection).
            subject = pascal_label(rel.subject_lemmas) or _pascal(rel.subject)
            obj = pascal_label(rel.object_lemmas) or _pascal(rel.object)
            if subject not in class_labels or obj not in class_labels:
                continue
            key = (subject, rel.predicate, obj)
            if key in seen_conn:
                continue
            seen_conn.add(key)
            connections.append(
                CandidateConnection(
                    subject_ref=subject,
                    predicate=rel.predicate,
                    object_ref=obj,
                    confidence=rel_confidence,
                )
            )
            if rel.predicate not in seen_prop:
                seen_prop.add(rel.predicate)
                properties.append(
                    CandidatePropertyDefinition(label=rel.predicate, confidence=rel_confidence)
                )

        return properties, connections

    async def _enrich_with_conceptnet(
        self, classes: list[CandidateClass], connections: list[CandidateConnection]
    ) -> tuple[list[CandidateClass], list[CandidateConnection]]:
        """
        Enrich the extracted schema with ConceptNet's external relation graph.

        For each synthesized class, query ConceptNet for the relations leaving its
        concept; when a related concept is ANOTHER extracted class, emit a
        ConceptNet-grounded connection between them (e.g. IsA / PartOf / RelatedTo).
        Classes ConceptNet recognizes (returns any relations for) get a small
        confidence boost. ConceptNet failures are non-fatal (the adapter returns
        empty on any error), so enrichment only ever adds signal.
        """
        assert self._reference_source is not None
        limit = int(self._config.get("conceptnet_relation_limit", 50))
        rel_confidence = float(self._config.get("conceptnet_confidence", 0.7))
        boost = float(self._config.get("conceptnet_confidence_boost", 0.1))

        # Map each class to its ConceptNet concept term ('ConsensusAlgorithm' ->
        # 'consensus_algorithm') and back, so related-concept URIs resolve to classes.
        term_by_label = {c.label: _concept_term(c.label) for c in classes}
        label_by_term = {term: label for label, term in term_by_label.items()}

        existing = {(c.subject_ref, c.predicate, c.object_ref) for c in connections}
        enriched = list(connections)
        boosted: list[CandidateClass] = []

        for cls in classes:
            uri = f"/c/en/{term_by_label[cls.label]}"
            relations = await self._reference_source.get_relations_async(uri, limit=limit)
            if relations:
                cls = replace(cls, confidence=min(1.0, cls.confidence + boost))
            boosted.append(cls)
            for rel in relations:
                obj_term = _concept_term_from_uri(rel.object_uri)
                obj_label = label_by_term.get(obj_term)
                if obj_label is None or obj_label == cls.label:
                    continue
                key = (cls.label, rel.predicate, obj_label)
                if key in existing:
                    continue
                existing.add(key)
                enriched.append(
                    CandidateConnection(
                        subject_ref=cls.label,
                        predicate=rel.predicate,
                        object_ref=obj_label,
                        confidence=rel_confidence,
                    )
                )

        return boosted, enriched

    def _finalize(
        self,
        classes: list[CandidateClass],
        properties: list[CandidatePropertyDefinition],
        connections: list[CandidateConnection],
    ) -> dict[str, Any]:
        """Assemble the schema-extraction result contract."""
        candidates = [c.to_dict() for c in classes] + [p.to_dict() for p in properties]
        return {
            "candidates": candidates,
            "connections": [c.to_dict() for c in connections],
            "candidate_count": len(classes),
            "property_count": len(properties),
            "connection_count": len(connections),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _confidence(self, priority: ConceptPriority) -> float:
        """Map a grammatical-role priority tier to a calibrated confidence."""
        return {
            ConceptPriority.CRITICAL: float(self._config.get("confidence_critical", 0.8)),
            ConceptPriority.IMPORTANT: float(self._config.get("confidence_important", 0.6)),
            ConceptPriority.CONTEXTUAL: float(self._config.get("confidence_contextual", 0.4)),
        }[priority]

    @staticmethod
    def _provenance(rep: ConceptCandidate, source_text: str) -> list[dict[str, Any]]:
        """Single provenance span for a representative's source offsets."""
        if 0 <= rep.start < rep.end <= len(source_text):
            return [
                {
                    "text_offset_start": rep.start,
                    "text_offset_end": rep.end,
                    "raw": source_text[rep.start : rep.end],
                }
            ]
        return []

    async def _llm_definitions(self, labels: list[str], source_text: str) -> dict[str, str]:
        """One batched LLM call producing a definition per label (llm/hybrid modes)."""
        if not labels or self._llm_provider is None:
            return {}
        label_list = ", ".join(f'"{label}"' for label in labels)
        system_prompt = (
            "You are an expert in ontology definition writing. Return a JSON object "
            "mapping each label to a concise 1-2 sentence definition. Output only JSON."
        )
        user_prompt = (
            f"Define these ontology classes.\n\nLabels: {label_list}\n\n"
            f"Context: {source_text[:3000]}\n\n"
            'Return JSON: {"Label": "definition", ...}'
        )
        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self._config.get("model", "google/gemini-3-flash-preview"),
            temperature=float(self._config.get("temperature", 0.0)),
            max_tokens=int(self._config.get("max_tokens", 1500)),
        )
        try:
            parsed = json.loads(_extract_json_obj(response.content))
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            _logger.warning("open_v1 definition synthesis: JSON parse failed; using fallbacks")
        return {}

    async def _llm_labels_and_definitions(
        self, phrases: list[str], source_text: str
    ) -> dict[str, dict[str, str]]:
        """
        One batched LLM call mapping each candidate phrase to a canonical
        PascalCase ontology label + a definition (llm synthesis mode).
        """
        if not phrases or self._llm_provider is None:
            return {}
        phrase_list = "\n".join(f"- {p}" for p in phrases)
        system_prompt = (
            "You are an ontology engineer. Given candidate concept phrases extracted from a "
            "text, produce a canonical ontology class label for each: PascalCase, singular, no "
            "spaces, merging synonyms/duplicates onto the same label. Return ONLY a JSON object "
            "mapping each input phrase EXACTLY as given to an object "
            '{"label": "PascalCaseLabel", "definition": "1-2 sentence definition"}.'
        )
        user_prompt = (
            f"Context:\n{source_text[:3000]}\n\nCandidate phrases:\n{phrase_list}\n\n"
            'Return the JSON object: {"<phrase>": {"label": "...", "definition": "..."}, ...}'
        )
        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self._config.get("model", "google/gemini-3-flash-preview"),
            temperature=float(self._config.get("temperature", 0.0)),
            max_tokens=int(self._config.get("max_tokens", 1500)),
        )
        out: dict[str, dict[str, str]] = {}
        try:
            parsed = json.loads(_extract_json_obj(response.content))
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if isinstance(value, dict):
                        out[str(key)] = {
                            "label": str(value.get("label", "")).strip(),
                            "definition": str(value.get("definition", "")).strip(),
                        }
        except json.JSONDecodeError:
            _logger.warning("open_v1 llm synthesis: JSON parse failed; falling back to rule labels")
        return out
