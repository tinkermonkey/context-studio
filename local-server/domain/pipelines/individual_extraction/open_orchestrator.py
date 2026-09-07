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

import json
import logging
import re
from dataclasses import replace
from typing import Any

from domain.extraction.open_extraction import (
    RelationCandidate,
    build_relation_candidates,
    build_wider_relation_candidates,
    snake_label,
    unconsumed_noun_chunk_heads,
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

# Minimum class-match similarity for a mention to be offered to the
# canonicalization LLM. Held constant (not the tuning knob `similarity_threshold`)
# so the prompt — and therefore the recorded cassette hash — is stable across the
# tournament's knob sweep.
_CANON_GROUNDING_THRESHOLD = 0.45


def _extract_json_obj(content: str) -> str:
    """Extract the first {...} JSON object from an LLM response (tolerates fences/prose)."""
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        return content
    return content[start : end + 1]


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

            ontology_id = state.input_data.get("ontology_id")
            if self._cfg.llm_canonicalization and self._llm_provider is not None:
                triples = await self._canonicalize_labels(triples, text, ontology_id)

            # Runs AFTER canonicalization (so the entities it surfaces don't
            # perturb the canonicalization prompt) and BEFORE predicate/schema
            # grounding (so the surfaced triples still flow through those
            # stages). Needs the spaCy structure + SVO relations to find
            # unconsumed chunks and derive their relations.
            if self._cfg.coverage_completion:
                triples = self._complete_coverage(
                    triples, open_result, relations, ontology_id
                )

            # Runs before _ground_to_schema so it only sees relation triples (no
            # is_a type triples exist yet), and after canonicalization since that
            # stage only rewrites subject/object labels, never predicates.
            if self._cfg.ground_predicates:
                triples = self._ground_predicates(triples, ontology_id)

            if self._cfg.nlp_grounded_typing and self._llm_provider is not None:
                triples = await self._type_individuals_nlp_grounded(
                    triples, text, ontology_id
                )
            elif self._cfg.ground_to_schema or self._cfg.require_schema_match:
                triples = self._ground_to_schema(triples, ontology_id)

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

    def _complete_coverage(
        self,
        triples: list[dict[str, Any]],
        open_result: OpenExtractionResult,
        relations: list[RelationCandidate],
        ontology_id: str | None,
    ) -> list[dict[str, Any]]:
        """
        Surface unconsumed noun chunks AND derive their relations in one pass.

        The dominant miss class is ``candidate_missing``: entities the SVO
        triples never surface. This stage completes their coverage without
        letting them dangle — the failure mode that regressed a prior attempt,
        where surfaced candidates lacked relations and ``relation_not_derived``
        jumped. It:

        1. Finds noun chunks unconsumed by the SVO relations.
        2. Grounds each unconsumed chunk against the schema's class vocabulary
           via the SchemaVectorIndex, keeping only those that match above the
           similarity threshold — so generic chunks are dropped and only real
           domain entities are surfaced.
        3. Runs wider dependency capture (ccomp/xcomp/acomp, passive agent,
           conjunct fan-out) scoped to those grounded chunk roots, so each
           surfaced candidate arrives WITH a derived subject--verb--object
           relation instead of as a bare individual.

        New triples are merged into the existing set, de-duplicated on
        (subject, predicate, object) exactly as ``_build_triples`` does. Runs
        after label canonicalization (so the entities it surfaces don't perturb
        that stage's cached prompt) and before predicate/schema grounding (so
        the surfaced triples still flow through those stages).

        Self-skips (returns the triples untouched) when there is no schema
        index, no repository, or the ontology id does not resolve to a known
        taxonomy — mirroring how the grounding stages degrade — and when no
        unconsumed chunk grounds or no relation is derived for a surfaced head.
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

        heads = unconsumed_noun_chunk_heads(open_result, relations)
        if not heads:
            return triples

        threshold = self._cfg.similarity_threshold
        grounded_heads: set[int] = set()
        for root_index, phrase in heads:
            query = self._embedding.embed(phrase.replace("_", " "))
            results = self._schema_index.search(
                query, kinds=["class"], top_k=1, threshold=threshold, taxonomy_id=taxonomy.id
            )
            if results:
                grounded_heads.add(root_index)
        if not grounded_heads:
            return triples

        wider = build_wider_relation_candidates(
            open_result, relations, restrict_to_heads=frozenset(grounded_heads)
        )
        if not wider:
            return triples

        new_triples = self._build_triples(open_result, wider)
        merged = list(triples)
        seen = {
            (t["subject"]["label"], t["predicate"]["label"], t["object"]["label"])
            for t in triples
        }
        for triple in new_triples:
            key = (
                triple["subject"]["label"],
                triple["predicate"]["label"],
                triple["object"]["label"],
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(triple)
        return merged

    async def _canonicalize_labels(
        self, triples: list[dict[str, Any]], text: str, ontology_id: str | None
    ) -> list[dict[str, Any]]:
        """
        Rewrite each individual's snake_case label to its canonical surface form.

        The rule pipeline proposes triples whose subject/object labels are
        snake_cased spaCy lemmas ("technician_route"), while the ground truth uses
        the entity's canonical surface name as written in the source
        ("Technician Route"). This stage issues ONE cheap LLM call per document
        that maps each extracted mention to that surface form, grounded against
        the ontology vocabulary: only mentions the schema vector index resolves to
        a class (with the matched class title supplied as a type hint) are offered
        for canonicalization, so the LLM restores the names of real domain
        entities and leaves generic tokens alone.

        Runs before grounding so the canonical names flow into the is_a triples
        the grounding stage emits (whose subject then matches the ground truth
        exactly). Self-skips (returns the triples untouched) when there is no
        schema index, no repository, an unresolvable ontology, or no grounded
        mention, mirroring how grounding degrades. Any LLM or parse failure is
        swallowed and leaves the triples unchanged, so a stale cassette can never
        crash the pipeline.
        """
        if self._schema_index is None or self._ontology_repo is None or not ontology_id:
            return triples
        taxonomy = self._ontology_repo.get_by_identifier(ontology_id)
        if taxonomy is None:
            return triples

        mentions = sorted(
            {t[role]["label"] for t in triples for role in ("subject", "object")}
        )
        type_hints: dict[str, str] = {}
        for mention in mentions:
            query = self._embedding.embed(mention.replace("_", " "))
            results = self._schema_index.search(
                query,
                kinds=["class"],
                top_k=1,
                threshold=_CANON_GROUNDING_THRESHOLD,
                taxonomy_id=taxonomy.id,
            )
            if results and results[0].label:
                type_hints[mention] = results[0].label

        if not type_hints:
            return triples

        mapping = await self._request_canonical_labels(type_hints, text)
        if not mapping:
            return triples
        return self._apply_label_mapping(triples, mapping)

    async def _request_canonical_labels(
        self, type_hints: dict[str, str], text: str
    ) -> dict[str, str]:
        """
        One LLM call mapping each grounded mention to its canonical surface name.

        The prompt is built only from scenario-fixed inputs (the sorted grounded
        mentions, their ontology type hints, and the source text), so it is
        identical across every knob combination the tournament sweeps — one
        recorded cassette per scenario replays for the whole sweep. A returned
        label is accepted only when it is the mention itself or a span that
        actually occurs in the source text, so the LLM cannot inject a
        hallucinated name. Returns an empty map on any LLM or JSON failure, which
        the caller treats as "leave the labels unchanged".
        """
        lines = [
            f'- "{mention}" (a {type_hints[mention]})' for mention in sorted(type_hints)
        ]
        mention_block = "\n".join(lines)
        system_prompt = (
            "You canonicalize extracted entity labels. Each snake_case mention is "
            "tagged with its ontology type. For each mention, return its canonical "
            "name exactly as it appears in the source text, using the original "
            "capitalization and spacing (e.g. \"technician_route\" -> "
            '"Technician Route"). If the mention is not a distinct named entity in '
            "the text, keep it unchanged. Never invent a name that is not present "
            "in the source text. Return ONLY a JSON object mapping each mention to "
            "its canonical name."
        )
        user_prompt = (
            f"Source text:\n{text[:2000]}\n\n"
            f"Mentions with ontology types:\n{mention_block}\n\n"
            'Return JSON: {"<mention>": "<canonical name or original mention>", ...}'
        )
        try:
            response = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self._cfg.model,
                temperature=self._cfg.temperature,
                max_tokens=self._cfg.max_tokens,
            )
            parsed = json.loads(_extract_json_obj(response.content))
        except Exception as exc:  # noqa: BLE001 - canonicalization is best-effort
            _logger.warning("open_v1 label canonicalization skipped: %s", exc)
            return {}
        if not isinstance(parsed, dict):
            return {}
        lowered_text = text.lower()
        mapping: dict[str, str] = {}
        for mention, chosen in parsed.items():
            key = str(mention)
            if key not in type_hints:
                continue
            value = str(chosen).strip()
            # Accept the mention unchanged, or a name that actually occurs in the
            # source text — never a label the model invented out of nothing.
            if value and (value == key or value.lower() in lowered_text):
                mapping[key] = value
        return mapping

    @staticmethod
    def _apply_label_mapping(
        triples: list[dict[str, Any]], mapping: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Rewrite subject/object labels via ``mapping`` and drop duplicates."""
        rewritten: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for triple in triples:
            subject = dict(triple["subject"])
            obj = dict(triple["object"])
            subject["label"] = mapping.get(subject["label"], subject["label"])
            obj["label"] = mapping.get(obj["label"], obj["label"])
            key = (subject["label"], triple["predicate"]["label"], obj["label"])
            if key in seen:
                continue
            seen.add(key)
            new_triple = dict(triple)
            new_triple["subject"] = subject
            new_triple["object"] = obj
            rewritten.append(new_triple)
        return rewritten

    def _ground_predicates(
        self, triples: list[dict[str, Any]], ontology_id: str | None
    ) -> list[dict[str, Any]]:
        """
        Clamp each triple's predicate onto the ontology's object-property vocabulary.

        The rule pipeline proposes free-form predicate verbs (surface/lemma spaCy
        tokens like "navigate" or "develops"). This stage matches each distinct
        predicate against the schema's property definitions via the
        SchemaVectorIndex — which scores the extracted verb against each property
        definition's curated title AND definition embeddings — and rewrites the
        predicate to the matched property's bare canonical verb (e.g. "navigate"
        -> "navigates-to"), the form the ground truth uses. This is the
        definition-driven predicate clamping that keeps free-form extraction from
        drifting off the defined vocabulary.

        A match is applied only when it carries a bare `predicate` token (property
        definitions whose title does not follow the canonical
        "source predicate destination" shape expose none, so nothing is rewritten
        to a wrong value). Predicates that match nothing above the threshold are
        left unchanged. Runs on relation triples only (before is_a emission).

        Self-skips (returns the triples untouched) when there is no schema index,
        no repository, or the ontology id does not resolve to a known taxonomy —
        mirroring how _ground_to_schema degrades. Scoped to the scenario's
        taxonomy so predicates cannot ground against an unrelated ontology.
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

        threshold = self._cfg.predicate_similarity_threshold
        predicates = {t["predicate"]["label"] for t in triples}
        mapping: dict[str, str] = {}
        for predicate in predicates:
            query = self._embedding.embed(predicate.replace("_", " "))
            results = self._schema_index.search(
                query,
                kinds=["property_definition"],
                top_k=1,
                threshold=threshold,
                taxonomy_id=taxonomy.id,
            )
            if results and results[0].predicate:
                mapping[predicate] = results[0].predicate

        if not mapping:
            return triples

        # Rewriting can collapse two distinct predicates onto the same canonical
        # verb, so de-duplicate on the rewritten (subject, predicate, object) key
        # exactly as _build_triples / _apply_label_mapping do.
        rewritten: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for triple in triples:
            predicate = dict(triple["predicate"])
            predicate["label"] = mapping.get(predicate["label"], predicate["label"])
            key = (triple["subject"]["label"], predicate["label"], triple["object"]["label"])
            if key in seen:
                continue
            seen.add(key)
            new_triple = dict(triple)
            new_triple["predicate"] = predicate
            rewritten.append(new_triple)
        return rewritten

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
                            "label": match.external_id or match.identifier or match.label,
                            "kind": "class",
                        },
                        "confidence": round(match.score, 4),
                    }
                )
            kept = kept + type_triples

        return kept

    async def _type_individuals_nlp_grounded(
        self,
        triples: list[dict[str, Any]],
        text: str,
        ontology_id: str | None,
    ) -> list[dict[str, Any]]:
        """
        Phase-2 typing via spaCy noun chunks + vector retrieval + LLM confirmation.

        For each noun chunk spaCy finds (headed by a NOUN/PROPN, non-stopword),
        the chunk plus its sentence is embedded and the vector index retrieves
        top-K candidate ontology classes; the LLM then confirms which candidate
        the chunk instantiates in that sentence, or none. A confirmed chunk
        becomes an ``is_a`` typing triple whose subject label is the chunk text
        (verbatim, no transformation) and whose object is the matched class's
        external reference. Labels are case-identical to source spans;
        case-insensitive duplicate chunk text produces only one typing triple.

        Self-skips (returns the triples untouched) when there is no schema
        index, no repository, no LLM provider, or the ontology id does not
        resolve to a known taxonomy — mirroring how grounding stages degrade.
        """
        if self._schema_index is None or self._ontology_repo is None:
            return triples
        if not ontology_id:
            return triples

        taxonomy = self._ontology_repo.get_by_identifier(ontology_id)
        if taxonomy is None:
            return triples

        open_result = self._nlp.process_open(text)
        if not open_result.tokens:
            return triples

        tokens = list(open_result.tokens)
        sentences = self._sentence_texts(text, tokens)
        taxonomy_id = str(getattr(taxonomy, "id", "") or "") or None

        typing_triples: list[dict[str, Any]] = []
        seen: set[str] = set()

        for chunk in open_result.noun_chunks:
            root = tokens[chunk.root_index] if 0 <= chunk.root_index < len(tokens) else None
            if root is None or root.pos not in ("NOUN", "PROPN") or root.is_stop:
                continue

            label = chunk.text.strip()
            if not label or label.lower() in seen:
                continue

            sentence = sentences.get(chunk.sentence_index, "")
            query_text = f"{label}. {sentence}".strip() if sentence else label
            query_embedding = self._embedding.embed(query_text)

            results = self._schema_index.search(
                query_embedding,
                kinds=["class"],
                top_k=self._cfg.nlp_typing_top_k,
                threshold=self._cfg.nlp_typing_threshold,
                taxonomy_id=taxonomy_id,
                matching_mode=self._cfg.nlp_typing_matching_mode,
            )
            if not results:
                continue

            chosen = await self._confirm_class_for_chunk(label, sentence, results)
            if chosen is None:
                continue

            seen.add(label.lower())
            typing_triple = self._make_typing_triple(label, chosen)
            typing_triples.append(typing_triple)

        return triples + typing_triples

    @staticmethod
    def _sentence_texts(text: str, tokens: list) -> dict[int, str]:
        """Reconstruct each sentence's text (by ``sentence_index``) from token char spans."""
        bounds: dict[int, tuple[int, int]] = {}
        for tok in tokens:
            start, end = bounds.get(tok.sentence_index, (tok.start, tok.end))
            bounds[tok.sentence_index] = (min(start, tok.start), max(end, tok.end))
        return {idx: text[start:end] for idx, (start, end) in bounds.items()}

    async def _confirm_class_for_chunk(
        self, label: str, sentence: str, matches: list[Any]
    ) -> Any | None:
        """
        Ask the LLM which retrieved candidate class the noun chunk instantiates.

        The LLM's only job is disambiguation-in-context: it picks the best-fitting
        candidate (by its exact external_id/identifier/label) or "none" — it never
        invents a class. Returns the chosen SchemaMatch or None if no match is
        accepted or all candidates lack a valid reference.
        """
        candidates: list[tuple[str, Any]] = []
        lines: list[str] = []

        for match in matches:
            ref = match.external_id or match.identifier or match.label
            if not ref:
                continue
            definition = ""
            if self._ontology_repo is not None:
                cls = self._ontology_repo.get_class(match.entity_id)
                if cls:
                    definition = (getattr(cls, "description", None) or "").strip()
            title = match.label or ref
            candidates.append((ref, match))
            lines.append(f"- {ref} ({title})" + (f": {definition}" if definition else ""))

        if not candidates:
            return None

        system_prompt = (
            "You are a knowledge-graph typing assistant. Given a phrase from a "
            "text, its sentence, and a list of candidate ontology classes, decide "
            "which single class the phrase is an INSTANCE of in that sentence. "
            'Choose the exact reference of the best-fitting candidate, or "none" '
            "if the phrase is not an instance of any of them. Do not invent "
            'classes. Respond with only JSON: {"class": "<exact reference or none>"}.'
        )
        user_prompt = (
            f'Phrase: "{label}"\n'
            f'Sentence: "{sentence}"\n\n'
            "Candidate classes (reference (title): definition):\n" + "\n".join(lines)
        )

        try:
            response = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self._cfg.model,
                temperature=self._cfg.temperature,
                max_tokens=200,
            )
            choice = ""
            payload = re.search(r"\{.*\}", response.content or "", re.S)
            if payload:
                try:
                    choice = str(json.loads(payload.group(0)).get("class", "")).strip()
                except (ValueError, TypeError):
                    choice = ""

            if not choice or choice.lower() == "none":
                return None

            choice_lower = choice.lower()
            for ref, match in candidates:
                if ref.lower() == choice_lower or (match.label or "").lower() == choice_lower:
                    return match
            return None
        except Exception as exc:  # noqa: BLE001 - typing is best-effort
            _logger.warning("nlp_grounded typing LLM call failed: %s", exc)
            return None

    @staticmethod
    def _make_typing_triple(label: str, match: Any) -> dict[str, Any]:
        """Build an ``is_a`` typing triple from a confirmed class match."""
        class_ref = match.external_id or match.identifier or match.label
        return {
            "subject": {"label": label, "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": class_ref, "kind": "class"},
            "confidence": round(float(getattr(match, "score", 0.0) or 0.0), 4),
        }


def _snake(phrase: str) -> str:
    """Fallback snake_case from a surface phrase."""
    return "_".join(word.lower() for word in phrase.split() if word)
