"""
Schema Extraction pipeline orchestrator.

Analyzes text to extract schema structure: candidate Classes and PropertyDefinitions
with provenance, confidence scores, and disambiguation rationale.

Execution flow (7 stages):
1. Text ingestion — normalize, chunk if needed
2. Candidate concept identification — extract noun phrases/technical terms (per chunk, merged)
3. Classification — match against existing schema or mark as new
4. Definition synthesis — generate definitions in one batched LLM call
5. Connection proposal — suggest relationships and properties
6. Disambiguation — handle multi-sense terms with separate candidates
7. Confidence scoring — clamp confidence to [0, 1]

A run on a source (#1552) may name `pages` (with the source's `page_starts`):
only text on those pages is read, and provenance is found only there (offsets
still index the whole text). It ends in one change proposal of its class and
property candidates when a proposer is wired (see
domain/pipelines/source_proposals.py); the run's `proposal_id` names it.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, cast

from domain.extraction.chunking import MAX_CHUNK_CHARS, chunk_text
from domain.extraction.span_resolution import find_all_spans
from domain.extraction.value_objects import SourceSpan
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.llm_json import extract_json
from domain.pipelines.orchestration.base import (
    PipelineOrchestrator,
    PipelineState,
)
from domain.pipelines.ports import LLMProvider, PipelineRunStatusWriter
from domain.pipelines.schema_extraction.apply_service import class_title_key, taxonomy_classes
from domain.pipelines.schema_extraction.prompts import SCHEMA_EXTRACTION_STAGES
from domain.pipelines.stage_prompts import render, resolve_stage_prompts

if TYPE_CHECKING:
    from domain.pipelines.source_proposals import SourceProposer

_logger = logging.getLogger(__name__)


def _serialize_provenance(spans: list[SourceSpan]) -> list[dict[str, Any]]:
    """
    Serialize SourceSpan objects to dict format with quote, start, and end fields.

    Preserves both fully-resolved spans (with character offsets) and quote-only spans
    (where start/end are None represent fuzzy-matched or unresolved provenance). All
    spans with a quote are included in the serialization.

    Args:
        spans: List of SourceSpan objects

    Returns:
        List of dicts with quote, start, and end fields
    """
    provenance_dicts: list[dict[str, Any]] = []
    for span in spans:
        # Include all spans that have a quote, whether or not they have offsets
        if span.quote is not None:
            provenance_dicts.append(
                {
                    "quote": span.quote,
                    "start": span.start,
                    "end": span.end,
                }
            )
    return provenance_dicts


_MAX_QUALIFIER_WORDS = 3


def _is_false(value: Any) -> bool:
    """True for a boolean false or a string the LLM used to mean false."""
    if isinstance(value, str):
        return value.strip().lower() in {"false", "no", "0"}
    return value is False


def _in_text_senses(raw_senses: Any) -> list[tuple[str, str | None]]:
    """
    Normalize a disambiguation reply's senses to ``(qualifier, definition)`` pairs,
    keeping only senses the text uses.

    Structured senses carry ``used_in_text``; a sense marked false (boolean or
    the strings "false"/"no"/"0") is dropped. Plain-string senses (the older reply
    shape) count as used. Qualifiers are capped at three words so a definition can
    never become a label; a longer or missing qualifier falls back to "sense N",
    numbered among the kept senses. Duplicate qualifiers are dropped.
    """
    pairs: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for sense in raw_senses if isinstance(raw_senses, list) else []:
        if isinstance(sense, dict):
            if _is_false(sense.get("used_in_text")):
                continue
            qualifier = str(sense.get("qualifier") or "").strip()
            definition = str(sense.get("definition") or "").strip() or None
        else:
            qualifier = str(sense or "").strip()
            definition = qualifier or None
        if not qualifier or len(qualifier.split()) > _MAX_QUALIFIER_WORDS:
            qualifier = f"sense {len(pairs) + 1}"
        if qualifier.lower() in seen:
            continue
        seen.add(qualifier.lower())
        pairs.append((qualifier, definition))
    return pairs


def join_documents(documents: Any) -> str:
    """
    Concatenate schema-extraction input documents into the single source text.

    Provenance span offsets index into this text, so it is also the text
    persisted on the run for reopened reviews.
    """
    if not isinstance(documents, list):
        return ""
    return " ".join(doc for doc in documents if isinstance(doc, str))


def _selected_pages(text: str, input_data: dict[str, Any]) -> str:
    """
    The text with everything off the selected `pages` blanked out (as spaces),
    so offsets still index the whole text and nothing off those pages is read
    or found; the text itself without a selection.

    Raises:
        PipelineInputError: If the selection or page_starts is malformed, or
            the selected pages hold no text
    """
    pages = input_data.get("pages")
    if pages is None or pages == "":
        return text
    try:
        chunks = chunk_text(
            text, page_starts=input_data.get("page_starts") or None, pages=str(pages)
        )
    except (TypeError, ValueError) as error:
        raise PipelineInputError(str(error)) from error
    if not chunks:
        raise PipelineInputError("The selected pages hold no text")
    parts: list[str] = []
    position = 0
    for chunk in chunks:
        parts += [" " * (chunk.start - position), text[chunk.start : chunk.end]]
        position = chunk.end
    parts.append(" " * (len(text) - position))
    return "".join(parts)


@dataclass
class CandidateClass:
    """A candidate class extracted from text."""

    label: str
    proposed_definition: str | None = None
    confidence: float = 0.5
    provenance: list[SourceSpan] = field(default_factory=list)
    disambiguation_rationale: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "kind": "class",
            "label": self.label,
            "proposed_definition": self.proposed_definition,
            "confidence": self.confidence,
            "provenance": _serialize_provenance(self.provenance),
            "disambiguation_rationale": self.disambiguation_rationale,
        }


@dataclass
class CandidatePropertyDefinition:
    """A candidate property definition."""

    label: str
    proposed_definition: str | None = None
    proposed_domain: str | None = None
    proposed_range: str | None = None
    confidence: float = 0.5
    provenance: list[SourceSpan] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "kind": "property_definition",
            "label": self.label,
            "proposed_definition": self.proposed_definition,
            "proposed_domain": self.proposed_domain,
            "proposed_range": self.proposed_range,
            "confidence": self.confidence,
            "provenance": _serialize_provenance(self.provenance),
        }


@dataclass
class CandidateConnection:
    """A proposed connection between candidates."""

    subject_ref: str
    predicate: str
    object_ref: str
    confidence: float = 0.5
    provenance: list[SourceSpan] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "subject_ref": self.subject_ref,
            "predicate": self.predicate,
            "object_ref": self.object_ref,
            "confidence": self.confidence,
            "provenance": _serialize_provenance(self.provenance),
        }


@dataclass
class SchemaExtractionState(PipelineState):
    """State for schema extraction pipeline execution."""

    source_text: str = ""
    normalized_text: str = ""
    text_chunks: list[str] = field(default_factory=list)
    candidate_concepts: list[str] = field(default_factory=list)
    classified_concepts: dict[str, bool] = field(default_factory=dict)
    candidate_classes: list[CandidateClass] = field(default_factory=list)
    candidate_properties: list[CandidatePropertyDefinition] = field(default_factory=list)
    proposed_connections: list[CandidateConnection] = field(default_factory=list)
    steps_completed: list[str] = field(default_factory=list)


class SchemaExtractionOrchestrator(PipelineOrchestrator):
    """
    Orchestrator for schema extraction using a 7-stage execution flow.

    Each stage processes the state sequentially and produces candidates or connections.
    Transitions are deterministic (no branching on LLM output).
    """

    # The LLM stages and their default prompts; a configuration's
    # ``stage_prompts`` override them.
    STAGE_PROMPTS = SCHEMA_EXTRACTION_STAGES

    def __init__(
        self,
        llm_provider: LLMProvider,
        ontology_repo=None,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
        config: dict[str, Any] | None = None,
        proposer: "SourceProposer | None" = None,
    ) -> None:
        """
        Initialize orchestrator with LLM provider and optional ontology repo.

        Args:
            llm_provider: LLM provider for completions
            ontology_repo: Optional OntologyRepository for existing-schema classification
            run_id: Pipeline run ID for writing RUNNING status
            status_writer: Optional port for writing run status to persistence
            config: The run's configuration; its ``stage_prompts`` override the
                default stage prompts
            proposer: Proposes a run on a source (input `source_id`) as one
                change proposal; without one, it proposes nothing
        """
        super().__init__(llm_provider, run_id, status_writer)
        self._ontology_repo = ontology_repo
        self._prompts = resolve_stage_prompts(
            self.STAGE_PROMPTS, (config or {}).get("stage_prompts")
        )
        self._proposer = proposer

    async def execute(self, state: PipelineState) -> PipelineState:
        """
        Execute the schema extraction pipeline.

        Args:
            state: SchemaExtractionState with input_data

        Returns:
            Updated state with candidates, connections, and confidence scores

        Raises:
            PipelineInputError: If required inputs are missing or invalid
            PipelineExecutionError: If pipeline execution fails
        """
        self._write_running_status()

        schema_state = cast(SchemaExtractionState, state)

        # Extract documents from input
        documents = schema_state.input_data.get("documents", [])
        if not documents or not any(doc.strip() for doc in documents if isinstance(doc, str)):
            exc = PipelineInputError(
                "documents is required and must contain at least one non-empty document"
            )
            schema_state = replace(
                schema_state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(exc)},
            )
            raise exc

        source_text = _selected_pages(join_documents(documents), schema_state.input_data)
        proposer = self._proposer if schema_state.input_data.get("source_id") else None
        proposing = proposer is not None
        if proposer is not None:
            # Before any model call: a mirrored taxonomy's client proposes its schema changes
            proposer.check_may_propose(
                str(schema_state.input_data.get("scope") or ""), schema_state.input_data
            )

        schema_state = replace(
            schema_state,
            source_text=source_text,
            current_status=PipelineRunStatus.RUNNING,
        )

        try:
            # Stage 1: Text ingestion
            schema_state = await self._stage_text_ingestion(schema_state)

            # Stage 2: Candidate concept identification
            schema_state = await self._stage_candidate_identification(schema_state)

            # Stage 3: Classification
            schema_state = await self._stage_classification(schema_state)

            # Stage 4: Definition synthesis
            schema_state = await self._stage_definition_synthesis(schema_state)

            # Stage 5: Connection proposal
            schema_state = await self._stage_connection_proposal(schema_state)

            # Stage 6: Disambiguation
            schema_state = await self._stage_disambiguation(schema_state)

            # Stage 7: Confidence scoring
            schema_state = await self._stage_confidence_scoring(schema_state)

            # Finalize
            schema_state = await self._stage_finalize(schema_state)

            # A run on a source ends in one proposal of its candidates
            if proposing:
                schema_state = self._propose(schema_state)

        except PipelineInputError:
            schema_state = replace(schema_state, current_status=PipelineRunStatus.FAILED)
            raise
        except PipelineExecutionError:
            schema_state = replace(schema_state, current_status=PipelineRunStatus.FAILED)
            raise
        except Exception as exc:
            _logger.error(f"Unexpected error during schema extraction: {exc}", exc_info=True)
            schema_state = replace(
                schema_state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": "Schema extraction encountered an unexpected error"},
            )
            raise PipelineExecutionError(
                "Schema extraction encountered an unexpected error"
            ) from exc

        return schema_state

    def _propose(self, state: SchemaExtractionState) -> SchemaExtractionState:
        """Propose the run's candidates; the result gains the proposal's id and counts."""
        assert self._proposer is not None
        result = dict(state.result or {})
        try:
            outcome = self._proposer.propose_schema(
                state.run_id, state.input_data, result.get("candidates") or []
            )
        except Exception as exc:
            raise PipelineExecutionError(
                f"Proposing the extracted candidates failed: {exc}"
            ) from exc
        warnings = [{"stage": "propose", "error": warning} for warning in outcome.warnings]
        return replace(
            state,
            result={**result, **outcome.to_json()},
            parse_warnings=[*state.parse_warnings, *warnings],
        )

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
        """
        Split text into chunks of at most max_chars on sentence boundaries.

        Args:
            text: Text to split
            max_chars: Maximum characters per chunk

        Returns:
            List of text chunks; always at least one element
        """
        chunks = chunk_text(text, max_chars=max_chars)
        return [text[chunk.start : chunk.end] for chunk in chunks] or [text]

    def _has_concrete_provenance(self, spans: list[SourceSpan]) -> bool:
        """
        Check if provenance has at least one concrete (resolved) span.

        Concrete spans have both start and end positions. Quote-only spans
        (start=None, end=None) are not considered concrete.

        Args:
            spans: List of SourceSpan objects

        Returns:
            True if at least one span has concrete positions, False otherwise
        """
        return any(span.start is not None and span.end is not None for span in spans)

    def _compute_confidence(
        self, label: str, source_text: str, provenance_spans: list[SourceSpan] | None = None
    ) -> float:
        """
        Compute evidence-based confidence for a candidate label.

        Factors: provenance presence (0.4) + term frequency capped at 0.4 + base 0.2.

        Args:
            label: Candidate label to score
            source_text: Original source text
            provenance_spans: Pre-computed provenance spans. If None, will call _find_provenance.

        Returns:
            Confidence in [0.2, 1.0]
        """
        if provenance_spans is None:
            provenance_spans = self._find_provenance(label, source_text)
        provenance_found = self._has_concrete_provenance(provenance_spans)
        term_freq = len(re.findall(re.escape(label), source_text, re.IGNORECASE))
        return min(
            1.0,
            0.2 + (0.4 if provenance_found else 0.0) + min(0.4, term_freq * 0.1),
        )

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------

    async def _stage_text_ingestion(self, state: SchemaExtractionState) -> SchemaExtractionState:
        """
        Stage 1: Normalize text and chunk if needed.

        Removes extra whitespace; splits into max-8000-char chunks on sentence boundaries.
        """
        normalized = re.sub(r"\s+", " ", state.source_text).strip()
        chunks = self._chunk_text(normalized)

        return replace(
            state,
            normalized_text=normalized,
            text_chunks=chunks,
            steps_completed=state.steps_completed + ["text_ingestion"],
        )

    async def _stage_candidate_identification(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
        """
        Stage 2: Identify candidate concepts per chunk; merge and deduplicate results.

        Calls LLM once per chunk; deduplicates case-insensitively across chunks.
        Falls back to regex extraction on JSON parse failure. Progress is
        reported per chunk (items_done of items_total chunks).
        """
        if not state.text_chunks:
            return replace(
                state,
                steps_completed=state.steps_completed + ["candidate_identification"],
            )

        prompt = self._prompts["candidate_identification"]

        seen: set[str] = set()
        all_candidates: list[str] = []
        total = len(state.text_chunks)
        self._report_progress(0, total)

        for done, chunk in enumerate(state.text_chunks, start=1):
            user_prompt = render(prompt.user, {"chunk": chunk})

            # No response_format="json" here: providers map it to JSON-object mode,
            # which forbids the top-level array this stage asks for.
            response = await self._call_llm(
                system_prompt=prompt.system,
                user_prompt=user_prompt,
                model=state.input_data.get("model", "google/gemini-3-flash-preview"),
                temperature=0.0,
            )

            chunk_candidates: list[str] = []
            try:
                parsed = extract_json(response.content)
                if isinstance(parsed, list):
                    chunk_candidates = [s for c in parsed if (s := str(c).strip())]
            except json.JSONDecodeError as e:
                warning = {
                    "stage": "candidate_identification",
                    "error": f"JSON parse error: {str(e)}",
                    "response_preview": response.content[:200],
                    "fallback_action": "regex extraction",
                }
                state = replace(state, parse_warnings=state.parse_warnings + [warning])
                chunk_candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", chunk)

            # Merge with global dedup (case-insensitive, keep first occurrence)
            for candidate in chunk_candidates:
                key = candidate.lower()
                if key not in seen:
                    seen.add(key)
                    all_candidates.append(candidate)
            self._report_progress(done, total)

        return replace(
            state,
            candidate_concepts=all_candidates,
            steps_completed=state.steps_completed + ["candidate_identification"],
        )

    async def _stage_classification(self, state: SchemaExtractionState) -> SchemaExtractionState:
        """
        Stage 3: Classify each candidate as existing (True) or new (False).

        If ontology_id (a taxonomy id) is provided and an ontology_repo is wired in,
        marks candidates whose title (by ``class_title_key``) a class in that taxonomy
        has, the rule apply dedups by. Otherwise marks all as new.
        """
        existing_titles: set[str] = set()

        ontology_id = state.input_data.get("ontology_id")
        if ontology_id and self._ontology_repo is not None:
            existing_titles = {
                class_title_key(cls.title)
                for cls in taxonomy_classes(self._ontology_repo, str(ontology_id))
            }

        classified = {
            concept: class_title_key(concept) in existing_titles
            for concept in state.candidate_concepts
        }

        return replace(
            state,
            classified_concepts=classified,
            steps_completed=state.steps_completed + ["classification"],
        )

    async def _stage_definition_synthesis(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
        """
        Stage 4: Generate definitions for all candidates in a single batched LLM call.

        Confidence is evidence-based: provenance presence + term frequency rather than
        a hardcoded constant.
        """
        if not state.candidate_concepts:
            return replace(state, steps_completed=state.steps_completed + ["definition_synthesis"])

        labels = state.candidate_concepts
        label_list = ", ".join(f'"{label}"' for label in labels)
        example = ", ".join(f'"{label}": "definition..."' for label in labels[:2])

        prompt = self._prompts["definition_synthesis"]
        system_prompt = prompt.system
        user_prompt = render(
            prompt.user,
            {"labels": label_list, "context": state.normalized_text[:3000], "example": example},
        )

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
            max_tokens=3000,
            response_format="json",
        )

        definitions_dict: dict[str, str] = {}
        try:
            parsed = extract_json(response.content)
            if isinstance(parsed, dict):
                definitions_dict = {k: str(v) for k, v in parsed.items()}
            else:
                raise ValueError(f"Expected dict, got {type(parsed).__name__}")
        except (json.JSONDecodeError, ValueError) as e:
            warning = {
                "stage": "definition_synthesis",
                "error": f"JSON parse error: {str(e)}",
                "response_preview": response.content[:200],
                "fallback_action": "generic definition per candidate",
            }
            state = replace(state, parse_warnings=state.parse_warnings + [warning])

        missing_keys = [c for c in labels if c not in definitions_dict]
        if missing_keys:
            state = replace(
                state,
                parse_warnings=state.parse_warnings
                + [
                    {
                        "stage": "definition_synthesis",
                        "error": f"LLM response missing {len(missing_keys)} label(s)",
                        "missing_labels": missing_keys,
                        "fallback_action": "generic definition per missing candidate",
                    }
                ],
            )

        candidates: list[CandidateClass] = []
        for concept in labels:
            definition = definitions_dict.get(concept) or f"{concept}: a domain concept."
            provenance = self._find_provenance(concept, state.source_text)
            confidence = self._compute_confidence(concept, state.source_text, provenance)

            # Warn if provenance is empty or contains only quote-only (unresolved) spans
            if not self._has_concrete_provenance(provenance):
                warning = {
                    "stage": "definition_synthesis",
                    "error": f"Candidate class '{concept}' has no provenance in source text",
                    "fallback_action": "use candidate without concrete provenance",
                }
                state = replace(state, parse_warnings=state.parse_warnings + [warning])

            candidates.append(
                CandidateClass(
                    label=concept,
                    proposed_definition=definition,
                    confidence=confidence,
                    provenance=provenance,
                )
            )

        return replace(
            state,
            candidate_classes=candidates,
            steps_completed=state.steps_completed + ["definition_synthesis"],
        )

    async def _stage_connection_proposal(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
        """
        Stage 5: Propose connections between candidates.

        Connection provenance is assembled from subject and object provenance separately,
        not from the predicate string.
        """
        if not state.candidate_classes:
            return replace(state, steps_completed=state.steps_completed + ["connection_proposal"])

        connections: list[CandidateConnection] = []
        properties: list[CandidatePropertyDefinition] = []

        labels = [c.label for c in state.candidate_classes]
        prompt = self._prompts["connection_proposal"]
        system_prompt = prompt.system
        user_prompt = render(
            prompt.user,
            {"classes": ", ".join(labels), "context": state.normalized_text[:3000]},
        )

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
            max_tokens=4000,
            response_format="json",
        )
        if response.finish_reason == "length":
            warning = {
                "stage": "connection_proposal",
                "error": "LLM reply was cut off at max_tokens",
                "response_preview": response.content[-200:],
                "fallback_action": "connections and properties may be incomplete",
            }
            state = replace(state, parse_warnings=state.parse_warnings + [warning])

        try:
            parsed = extract_json(response.content)
            if isinstance(parsed, dict):
                for rel in parsed.get("relationships", []):
                    subject = rel.get("subject", "")
                    obj = rel.get("object", "")
                    if not subject or not obj:
                        continue
                    # Compose provenance from subject + object, not from the predicate string
                    subject_provenance = self._find_provenance(subject, state.source_text)
                    object_provenance = self._find_provenance(obj, state.source_text)
                    provenance = subject_provenance + object_provenance

                    # Warn if provenance has no concrete (resolved) spans
                    if not self._has_concrete_provenance(provenance):
                        warning = {
                            "stage": "connection_proposal",
                            "error": (
                                f"Connection '{subject}' -> '{obj}' "
                                "has no provenance in source text"
                            ),
                            "fallback_action": "use connection without concrete provenance",
                        }
                        state = replace(state, parse_warnings=state.parse_warnings + [warning])

                    conn = CandidateConnection(
                        subject_ref=subject,
                        predicate=rel.get("predicate", ""),
                        object_ref=obj,
                        confidence=rel.get("confidence", 0.5),
                        provenance=provenance,
                    )
                    connections.append(conn)

                for prop in parsed.get("properties", []):
                    prop_name = prop.get("name", "")
                    provenance = self._find_provenance(prop_name, state.source_text)

                    # Warn if provenance has no concrete (resolved) spans
                    if not self._has_concrete_provenance(provenance):
                        warning = {
                            "stage": "connection_proposal",
                            "error": f"Property '{prop_name}' has no provenance in source text",
                            "fallback_action": "use property without concrete provenance",
                        }
                        state = replace(state, parse_warnings=state.parse_warnings + [warning])

                    prop_def = CandidatePropertyDefinition(
                        label=prop_name,
                        proposed_domain=prop.get("domain"),
                        proposed_range=prop.get("range"),
                        confidence=prop.get("confidence", 0.5),
                        provenance=provenance,
                    )
                    properties.append(prop_def)
            else:
                warning = {
                    "stage": "connection_proposal",
                    "error": f"Expected dict in JSON response, got {type(parsed).__name__}",
                    "response_preview": response.content[:200],
                    "fallback_action": "no connections extracted",
                }
                state = replace(state, parse_warnings=state.parse_warnings + [warning])
        except json.JSONDecodeError as e:
            warning = {
                "stage": "connection_proposal",
                "error": f"JSON parse error: {str(e)}",
                "response_preview": response.content[:200],
                "fallback_action": "no connections extracted",
            }
            state = replace(state, parse_warnings=state.parse_warnings + [warning])

        return replace(
            state,
            proposed_connections=connections,
            candidate_properties=properties,
            steps_completed=state.steps_completed + ["connection_proposal"],
        )

    async def _stage_disambiguation(self, state: SchemaExtractionState) -> SchemaExtractionState:
        """
        Stage 6: Add sense candidates for a term only when the text itself uses
        it in more than one sense. The original term is kept.

        Senses the text does not use (dictionary meanings such as "Python (a
        snake)" in a programming text) are dropped. A term with fewer than two
        in-text senses is left as it is. When a term is split, each sense's
        definition goes into ``proposed_definition``; the label stays the term
        plus a short qualifier (at most three words), never the definition.
        """
        if not state.candidate_classes:
            return replace(state, steps_completed=state.steps_completed + ["disambiguation"])

        labels = [c.label for c in state.candidate_classes]
        prompt = self._prompts["disambiguation"]
        system_prompt = prompt.system
        user_prompt = render(
            prompt.user,
            {"terms": ", ".join(labels), "context": state.normalized_text[:3000]},
        )

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
            max_tokens=2000,
            response_format="json",
        )

        disambiguated = list(state.candidate_classes)
        try:
            parsed = extract_json(response.content)
            if isinstance(parsed, dict):
                for ambig in parsed.get("ambiguous_terms", []) or []:
                    if not isinstance(ambig, dict):
                        continue
                    term = str(ambig.get("term") or "").strip()
                    rationale = ambig.get("rationale", "") or ""
                    senses = _in_text_senses(ambig.get("senses", []))

                    original_idx = next(
                        (
                            i
                            for i, c in enumerate(disambiguated)
                            if c.label.strip().lower() == term.lower()
                        ),
                        -1,
                    )
                    if original_idx < 0 or len(senses) < 2:
                        continue

                    original = disambiguated[original_idx]
                    # Keep the original term: connection proposal (stage 5) ran
                    # before this stage and refers to it by label, so removing it
                    # would leave those connections pointing at no class and apply
                    # would silently drop them. The senses follow it as narrower
                    # candidates the reviewer can accept or reject.
                    split = [original] + [
                        CandidateClass(
                            label=f"{original.label} ({qualifier})",
                            proposed_definition=definition or original.proposed_definition,
                            confidence=max(0.0, original.confidence - 0.1),
                            provenance=original.provenance,
                            disambiguation_rationale=f"Sense {i + 1}: {rationale}",
                        )
                        for i, (qualifier, definition) in enumerate(senses)
                    ]
                    disambiguated = (
                        disambiguated[:original_idx] + split + disambiguated[original_idx + 1 :]
                    )
            else:
                warning = {
                    "stage": "disambiguation",
                    "error": f"Expected dict in JSON response, got {type(parsed).__name__}",
                    "response_preview": response.content[:200],
                    "fallback_action": "skipping disambiguation",
                }
                state = replace(state, parse_warnings=state.parse_warnings + [warning])
        except json.JSONDecodeError as e:
            warning = {
                "stage": "disambiguation",
                "error": f"JSON parse error: {str(e)}",
                "response_preview": response.content[:200],
                "fallback_action": "skipping disambiguation",
            }
            state = replace(state, parse_warnings=state.parse_warnings + [warning])

        return replace(
            state,
            candidate_classes=disambiguated,
            steps_completed=state.steps_completed + ["disambiguation"],
        )

    async def _stage_confidence_scoring(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
        """
        Stage 7: Clamp all confidence scores to [0, 1].
        """
        normalized_classes = [
            replace(candidate, confidence=max(0.0, min(1.0, candidate.confidence)))
            for candidate in state.candidate_classes
        ]
        normalized_properties = [
            replace(prop, confidence=max(0.0, min(1.0, prop.confidence)))
            for prop in state.candidate_properties
        ]
        normalized_connections = [
            replace(conn, confidence=max(0.0, min(1.0, conn.confidence)))
            for conn in state.proposed_connections
        ]

        return replace(
            state,
            candidate_classes=normalized_classes,
            candidate_properties=normalized_properties,
            proposed_connections=normalized_connections,
            steps_completed=state.steps_completed + ["confidence_scoring"],
        )

    async def _stage_finalize(self, state: SchemaExtractionState) -> SchemaExtractionState:
        """
        Stage 8: Finalize and prepare output.
        """
        candidates = []
        candidates.extend([c.to_dict() for c in state.candidate_classes])
        candidates.extend([p.to_dict() for p in state.candidate_properties])

        connections = [c.to_dict() for c in state.proposed_connections]

        result = {
            "candidates": candidates,
            "connections": connections,
            "candidate_count": len(state.candidate_classes),
            "property_count": len(state.candidate_properties),
            "connection_count": len(state.proposed_connections),
            "warnings": state.parse_warnings,
        }

        return replace(
            state,
            result=result,
            current_status=PipelineRunStatus.COMPLETED,
            steps_completed=state.steps_completed + ["finalize"],
        )

    def _find_provenance(self, text: str, source: str) -> list[SourceSpan]:
        """
        Find all occurrences of a term in source text using span resolution.

        Delegates to find_all_spans() which uses exact and normalized matching
        to locate all occurrences of the term in the source text.

        Args:
            text: Text to find
            source: Source text to search in

        Returns:
            List of SourceSpan objects representing each occurrence.
            Returns empty list if term is not found.
        """
        return find_all_spans(text, source)
