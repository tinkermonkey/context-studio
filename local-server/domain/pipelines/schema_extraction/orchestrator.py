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
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, replace
from typing import Any, cast

from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.orchestration.base import (
    PipelineOrchestrator,
    PipelineState,
)
from domain.pipelines.ports import LLMProvider, PipelineRunStatusWriter

_logger = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 8000


@dataclass
class CandidateClass:
    """A candidate class extracted from text."""

    label: str
    proposed_definition: str | None = None
    confidence: float = 0.5
    provenance: list[dict[str, Any]] = field(default_factory=list)
    disambiguation_rationale: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "kind": "class",
            "label": self.label,
            "proposed_definition": self.proposed_definition,
            "confidence": self.confidence,
            "provenance": self.provenance,
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
    provenance: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "kind": "property_definition",
            "label": self.label,
            "proposed_definition": self.proposed_definition,
            "proposed_domain": self.proposed_domain,
            "proposed_range": self.proposed_range,
            "confidence": self.confidence,
            "provenance": self.provenance,
        }


@dataclass
class CandidateConnection:
    """A proposed connection between candidates."""

    subject_ref: str
    predicate: str
    object_ref: str
    confidence: float = 0.5
    provenance: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "subject_ref": self.subject_ref,
            "predicate": self.predicate,
            "object_ref": self.object_ref,
            "confidence": self.confidence,
            "provenance": self.provenance,
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
    candidate_properties: list[CandidatePropertyDefinition] = field(
        default_factory=list
    )
    proposed_connections: list[CandidateConnection] = field(default_factory=list)
    steps_completed: list[str] = field(default_factory=list)


class SchemaExtractionOrchestrator(PipelineOrchestrator):
    """
    Orchestrator for schema extraction using a 7-stage execution flow.

    Each stage processes the state sequentially and produces candidates or connections.
    Transitions are deterministic (no branching on LLM output).
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        ontology_repo=None,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
    ) -> None:
        """
        Initialize orchestrator with LLM provider and optional ontology repo.

        Args:
            llm_provider: LLM provider for completions
            ontology_repo: Optional OntologyRepository for existing-schema classification
            run_id: Pipeline run ID for writing RUNNING status
            status_writer: Optional port for writing run status to persistence
        """
        super().__init__(llm_provider, run_id, status_writer)
        self._ontology_repo = ontology_repo

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
        if not documents or not any(
            doc.strip() for doc in documents if isinstance(doc, str)
        ):
            exc = PipelineInputError(
                "documents is required and must contain at least one non-empty document"
            )
            schema_state = replace(
                schema_state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(exc)},
            )
            raise exc

        # Concatenate documents into single source text for processing
        source_text = " ".join(doc for doc in documents if isinstance(doc, str))

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

        except PipelineInputError:
            schema_state = replace(
                schema_state, current_status=PipelineRunStatus.FAILED
            )
            raise
        except PipelineExecutionError:
            schema_state = replace(
                schema_state, current_status=PipelineRunStatus.FAILED
            )
            raise
        except Exception as exc:
            _logger.error(
                f"Unexpected error during schema extraction: {exc}", exc_info=True
            )
            schema_state = replace(
                schema_state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": "Schema extraction encountered an unexpected error"},
            )
            raise PipelineExecutionError(
                "Schema extraction encountered an unexpected error"
            ) from exc

        return schema_state

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
        """
        Split text into chunks of at most max_chars on sentence boundaries.

        Args:
            text: Text to split
            max_chars: Maximum characters per chunk

        Returns:
            List of text chunks; always at least one element
        """
        if len(text) <= max_chars:
            return [text]

        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for sentence in sentences:
            if current_len + len(sentence) > max_chars and current:
                chunks.append(" ".join(current))
                current = [sentence]
                current_len = len(sentence)
            else:
                current.append(sentence)
                current_len += len(sentence)

        if current:
            chunks.append(" ".join(current))

        return chunks if chunks else [text]

    def _compute_confidence(self, label: str, source_text: str) -> float:
        """
        Compute evidence-based confidence for a candidate label.

        Factors: provenance presence (0.4) + term frequency capped at 0.4 + base 0.2.

        Args:
            label: Candidate label to score
            source_text: Original source text

        Returns:
            Confidence in [0.2, 1.0]
        """
        provenance_found = bool(self._find_provenance(label, source_text))
        term_freq = len(re.findall(re.escape(label), source_text, re.IGNORECASE))
        return min(
            1.0,
            0.2 + (0.4 if provenance_found else 0.0) + min(0.4, term_freq * 0.1),
        )

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------

    async def _stage_text_ingestion(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
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
        Falls back to regex extraction on JSON parse failure.
        """
        if not state.text_chunks:
            return replace(
                state,
                steps_completed=state.steps_completed + ["candidate_identification"],
            )

        system_prompt = (
            "You are an expert in ontology design and schema extraction. "
            "Extract candidate classes and key terms from the text. "
            "Return a JSON array of candidate labels. "
            "Be precise and extract technical/domain terms, not generic words."
        )

        seen: set[str] = set()
        all_candidates: list[str] = []

        for chunk in state.text_chunks:
            user_prompt = (
                f"Extract candidate classes and technical terms from this text:\n\n{chunk}\n\n"
                "Return a JSON array of strings (labels only). "
                'Example: ["Microservice", "Message Queue", "API Gateway"]'
            )

            response = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=state.input_data.get("model", "google/gemini-3-flash-preview"),
                temperature=0.0,
            )

            chunk_candidates: list[str] = []
            try:
                parsed = json.loads(response.content)
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
                chunk_candidates = re.findall(
                    r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", chunk
                )

            # Merge with global dedup (case-insensitive, keep first occurrence)
            for candidate in chunk_candidates:
                key = candidate.lower()
                if key not in seen:
                    seen.add(key)
                    all_candidates.append(candidate)

        return replace(
            state,
            candidate_concepts=all_candidates,
            steps_completed=state.steps_completed + ["candidate_identification"],
        )

    async def _stage_classification(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
        """
        Stage 3: Classify each candidate as existing (True) or new (False).

        If ontology_id is provided and an ontology_repo is wired in, fetches existing
        class labels and marks candidates that already exist. Otherwise marks all as new.
        """
        existing_labels: set[str] = set()

        ontology_id = state.input_data.get("ontology_id")
        if ontology_id and self._ontology_repo is not None:
            classes = self._ontology_repo.list_classes(limit=None)
            existing_labels = {cls.label.lower() for cls in classes}

        classified = {
            concept: concept.lower() in existing_labels
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
            return replace(
                state, steps_completed=state.steps_completed + ["definition_synthesis"]
            )

        labels = state.candidate_concepts
        label_list = ", ".join(f'"{label}"' for label in labels)
        example = ", ".join(f'"{label}": "definition..."' for label in labels[:2])

        system_prompt = (
            "You are an expert in ontology definition writing. "
            "Return a JSON object mapping each label to its definition (1-2 sentences). "
            "Only output the JSON object, nothing else."
        )
        user_prompt = (
            f"Define these classes for a technical ontology.\n\n"
            f"Labels: {label_list}\n\n"
            f"Context: {state.normalized_text[:3000]}\n\n"
            f"Return JSON: {{{example}, ...}}"
        )

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
            max_tokens=1000,
        )

        definitions_dict: dict[str, str] = {}
        try:
            parsed = json.loads(response.content)
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
            definition = (
                definitions_dict.get(concept) or f"{concept}: a domain concept."
            )
            provenance = self._find_provenance(concept, state.source_text)
            confidence = self._compute_confidence(concept, state.source_text)
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
            return replace(
                state, steps_completed=state.steps_completed + ["connection_proposal"]
            )

        connections: list[CandidateConnection] = []
        properties: list[CandidatePropertyDefinition] = []

        system_prompt = (
            "You are an expert in ontology design. "
            "Identify relationships and properties between the given classes. "
            'Return a JSON object with "relationships" and "properties" arrays.'
        )

        labels = [c.label for c in state.candidate_classes]
        user_prompt = (
            f"For these candidate classes, identify relationships and properties:\n\n"
            f"Classes: {', '.join(labels)}\n\n"
            f"Context: {state.normalized_text[:3000]}\n\n"
            "Return JSON:\n"
            "{\n"
            '  "relationships": [\n'
            '    {"subject": "Class1", "predicate": "subclass_of", '
            '"object": "Class2", "confidence": 0.8},\n'
            "    ...\n"
            "  ],\n"
            '  "properties": [\n'
            '    {"name": "Property1", "domain": "Class1", '
            '"range": "Class2", "confidence": 0.7},\n'
            "    ...\n"
            "  ]\n"
            "}"
        )

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
            max_tokens=500,
        )

        try:
            parsed = json.loads(response.content)
            if isinstance(parsed, dict):
                for rel in parsed.get("relationships", []):
                    subject = rel.get("subject", "")
                    obj = rel.get("object", "")
                    if not subject or not obj:
                        continue
                    # Compose provenance from subject + object, not from the predicate string
                    provenance = self._find_provenance(
                        subject, state.source_text
                    ) + self._find_provenance(obj, state.source_text)
                    conn = CandidateConnection(
                        subject_ref=subject,
                        predicate=rel.get("predicate", ""),
                        object_ref=obj,
                        confidence=rel.get("confidence", 0.5),
                        provenance=provenance,
                    )
                    connections.append(conn)

                for prop in parsed.get("properties", []):
                    provenance = self._find_provenance(
                        prop.get("name", ""), state.source_text
                    )
                    prop_def = CandidatePropertyDefinition(
                        label=prop.get("name", ""),
                        proposed_domain=prop.get("domain"),
                        proposed_range=prop.get("range"),
                        confidence=prop.get("confidence", 0.5),
                        provenance=provenance,
                    )
                    properties.append(prop_def)
            else:
                warning = {
                    "stage": "connection_proposal",
                    "error": (
                        f"Expected dict in JSON response, got {type(parsed).__name__}"
                    ),
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

    async def _stage_disambiguation(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
        """
        Stage 6: Handle multi-sense terms by creating separate candidates with rationale.
        """
        if not state.candidate_classes:
            return replace(
                state, steps_completed=state.steps_completed + ["disambiguation"]
            )

        system_prompt = (
            "You are an expert in word sense disambiguation. "
            "Identify if any of the given terms have multiple meanings or senses in the context. "
            "Return a JSON object with ambiguous terms and their senses."
        )

        labels = [c.label for c in state.candidate_classes]
        user_prompt = (
            f"Check these terms for multiple senses:\n\n"
            f"Terms: {', '.join(labels)}\n\n"
            f"Context: {state.normalized_text[:3000]}\n\n"
            "Return JSON:\n"
            "{\n"
            '  "ambiguous_terms": [\n'
            '    {"term": "Term1", "senses": ["Sense A", "Sense B"], "rationale": "Explanation"}\n'
            "  ]\n"
            "}"
        )

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
            max_tokens=500,
        )

        disambiguated = list(state.candidate_classes)
        try:
            parsed = json.loads(response.content)
            if isinstance(parsed, dict):
                for ambig in parsed.get("ambiguous_terms", []):
                    term = ambig.get("term", "")
                    senses = ambig.get("senses", [])
                    rationale = ambig.get("rationale", "")

                    original_idx = next(
                        (i for i, c in enumerate(disambiguated) if c.label == term), -1
                    )
                    if original_idx >= 0 and len(senses) > 1:
                        original = disambiguated[original_idx]
                        disambiguated_candidates = []
                        for i, sense in enumerate(senses):
                            new_label = f"{term} ({sense})" if sense else term
                            candidate = CandidateClass(
                                label=new_label,
                                proposed_definition=original.proposed_definition,
                                confidence=max(0.0, original.confidence - 0.1),
                                provenance=original.provenance,
                                disambiguation_rationale=f"Sense {i+1}: {rationale}",
                            )
                            disambiguated_candidates.append(candidate)

                        disambiguated = (
                            disambiguated[:original_idx]
                            + disambiguated_candidates
                            + disambiguated[original_idx + 1 :]
                        )
            else:
                warning = {
                    "stage": "disambiguation",
                    "error": (
                        f"Expected dict in JSON response, got {type(parsed).__name__}"
                    ),
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

    async def _stage_finalize(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
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
        }

        return replace(
            state,
            result=result,
            current_status=PipelineRunStatus.COMPLETED,
            steps_completed=state.steps_completed + ["finalize"],
        )

    def _find_provenance(self, text: str, source: str) -> list[dict[str, Any]]:
        """
        Find text offsets where a term appears in source.

        Args:
            text: Text to find
            source: Source text to search in

        Returns:
            List of provenance dicts with offsets and raw excerpt
        """
        if not text:
            return []

        provenance = []
        pattern = re.escape(text)
        for match in re.finditer(pattern, source, re.IGNORECASE):
            start = match.start()
            end = match.end()
            provenance.append(
                {
                    "text_offset_start": start,
                    "text_offset_end": end,
                    "raw": source[start:end],
                }
            )

        return provenance
