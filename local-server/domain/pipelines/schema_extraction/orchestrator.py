"""
Schema Extraction pipeline orchestrator.

Analyzes text to extract schema structure: candidate Classes and PropertyDefinitions
with provenance, confidence scores, and disambiguation rationale.

State machine (7 stages):
1. Text ingestion — normalize, chunk if needed
2. Candidate concept identification — extract noun phrases/technical terms
3. Classification — match against existing schema or mark as new
4. Definition synthesis — generate/refine definitions
5. Connection proposal — suggest relationships and properties
6. Disambiguation — handle multi-sense terms with separate candidates
7. Confidence scoring — assign confidence in [0, 1]
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from typing import Any, cast

from domain.pipeline.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipeline.ports import LLMProvider
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState


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
    candidate_properties: list[CandidatePropertyDefinition] = field(default_factory=list)
    proposed_connections: list[CandidateConnection] = field(default_factory=list)
    steps_completed: list[str] = field(default_factory=list)


class SchemaExtractionOrchestrator(PipelineOrchestrator):
    """
    Orchestrator for schema extraction using a 7-stage LangGraph state machine.

    Each stage is a node that processes the state and produces candidates or connections.
    Transitions are deterministic (no branching on LLM output).
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        """Initialize orchestrator with LLM provider."""
        super().__init__(llm_provider)

    def build_graph(self) -> Any:
        """
        Build LangGraph state graph.

        For now, returns None (execution uses explicit stage methods).
        """
        return None

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
        schema_state = cast(SchemaExtractionState, state)

        # Extract documents from input
        documents = schema_state.input_data.get("documents", [])
        if not documents or not any(doc.strip() for doc in documents if isinstance(doc, str)):
            exc = PipelineInputError("documents is required and must contain at least one non-empty document")
            schema_state = replace(
                schema_state, current_status=PipelineRunStatus.FAILED, result={"error": str(exc)}
            )
            raise exc

        # Concatenate documents into single source text for processing
        source_text = " ".join(doc for doc in documents if isinstance(doc, str))

        schema_state = replace(
            schema_state, source_text=source_text, current_status=PipelineRunStatus.RUNNING
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

        except PipelineExecutionError:
            schema_state = replace(schema_state, current_status=PipelineRunStatus.FAILED)
            raise
        except Exception as exc:
            schema_state = replace(
                schema_state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(exc)},
            )
            raise PipelineExecutionError(f"Schema extraction failed: {str(exc)}") from exc

        return schema_state

    async def _stage_text_ingestion(self, state: SchemaExtractionState) -> SchemaExtractionState:
        """
        Stage 1: Normalize text and chunk if needed.

        Removes extra whitespace, preserves offsets.
        """
        # Normalize whitespace
        normalized = re.sub(r"\s+", " ", state.source_text).strip()

        # For MVP, treat entire text as single chunk
        chunks = [normalized]

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
        Stage 2: Identify candidate concepts (noun phrases, technical terms).

        Uses LLM to extract candidate class labels from text.
        """
        if not state.normalized_text:
            return replace(
                state,
                steps_completed=state.steps_completed + ["candidate_identification"],
            )

        # Ask LLM to identify candidate concepts
        system_prompt = """You are an expert in ontology design and schema extraction.
Extract candidate classes and key terms from the text. Return a JSON array of candidate labels.
Be precise and extract technical/domain terms, not generic words."""

        user_prompt = f"""Extract candidate classes and technical terms from this text:

{state.normalized_text}

Return a JSON array of strings (labels only). Example: ["Microservice", "Message Queue",
"API Gateway"]"""

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
        )

        # Parse LLM response
        candidates = []
        try:
            parsed = json.loads(response.content)
            if isinstance(parsed, list):
                candidates = [str(c).strip() for c in parsed if c]
        except json.JSONDecodeError as e:
            # Record warning and fall back to regex extraction
            warning = {
                "stage": "candidate_identification",
                "error": f"JSON parse error: {str(e)}",
                "response_preview": response.content[:200],
                "fallback_action": "regex extraction",
            }
            state = replace(state, parse_warnings=state.parse_warnings + [warning])
            # Fallback: extract all-caps words as candidates
            candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", state.normalized_text)

        return replace(
            state,
            candidate_concepts=candidates,
            steps_completed=state.steps_completed + ["candidate_identification"],
        )

    async def _stage_classification(self, state: SchemaExtractionState) -> SchemaExtractionState:
        """
        Stage 3: Classify each candidate as new or existing in target schema.

        For MVP, mark all as new (existing_schema integration is out of scope).
        """
        classified = {concept: False for concept in state.candidate_concepts}

        return replace(
            state,
            classified_concepts=classified,
            steps_completed=state.steps_completed + ["classification"],
        )

    async def _stage_definition_synthesis(
        self, state: SchemaExtractionState
    ) -> SchemaExtractionState:
        """
        Stage 4: Generate definitions for candidate classes.

        Uses LLM to create precise, concise definitions.
        """
        if not state.candidate_concepts:
            return replace(state, steps_completed=state.steps_completed + ["definition_synthesis"])

        candidates = []

        for concept in state.candidate_concepts:
            system_prompt = """You are an expert in ontology definition writing.
Create a precise, concise definition (1-2 sentences) for a class in a technical ontology."""

            user_prompt = f"""Define this class for a technical ontology:

Class: {concept}
Context: {state.normalized_text}

Provide a definition (1-2 sentences) suitable for an ontology."""

            response = await self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=state.input_data.get("model", "google/gemini-3-flash-preview"),
                temperature=0.0,
                max_tokens=200,
            )

            # Find provenance in original text
            provenance = self._find_provenance(concept, state.source_text)

            candidate = CandidateClass(
                label=concept,
                proposed_definition=response.content.strip(),
                confidence=0.8,
                provenance=provenance,
            )
            candidates.append(candidate)

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

        Identifies subclass-of relationships and property definitions.
        """
        if not state.candidate_classes:
            return replace(state, steps_completed=state.steps_completed + ["connection_proposal"])

        connections = []
        properties = []

        # Extract candidate properties from text
        system_prompt = """You are an expert in ontology design.
Identify relationships and properties between the given classes.
Return a JSON object with "relationships" and "properties" arrays."""

        labels = [c.label for c in state.candidate_classes]
        user_prompt = f"""For these candidate classes, identify relationships and properties:

Classes: {', '.join(labels)}

Context: {state.normalized_text}

Return JSON:
{{
  "relationships": [
    {{"subject": "Class1", "predicate": "subclass_of", "object": "Class2", "confidence": 0.8}},
    ...
  ],
  "properties": [
    {{"name": "Property1", "domain": "Class1", "range": "Class2", "confidence": 0.7}},
    ...
  ]
}}"""

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
            max_tokens=500,
        )

        # Parse connections
        try:
            parsed = json.loads(response.content)
            if not isinstance(parsed, dict):
                raise AttributeError(f"Expected dict, got {type(parsed).__name__}")

            # Process relationships
            for rel in parsed.get("relationships", []):
                provenance = self._find_provenance(
                    f"{rel.get('subject')} {rel.get('predicate')} {rel.get('object')}",
                    state.source_text,
                )
                conn = CandidateConnection(
                    subject_ref=rel.get("subject", ""),
                    predicate=rel.get("predicate", ""),
                    object_ref=rel.get("object", ""),
                    confidence=rel.get("confidence", 0.5),
                    provenance=provenance,
                )
                connections.append(conn)

            # Process properties
            for prop in parsed.get("properties", []):
                provenance = self._find_provenance(prop.get("name", ""), state.source_text)
                prop_def = CandidatePropertyDefinition(
                    label=prop.get("name", ""),
                    proposed_domain=prop.get("domain"),
                    proposed_range=prop.get("range"),
                    confidence=prop.get("confidence", 0.5),
                    provenance=provenance,
                )
                properties.append(prop_def)
        except (json.JSONDecodeError, AttributeError) as e:
            # Record warning but continue with empty connections
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
        Stage 6: Handle multi-sense terms by creating separate candidates with rationale.

        For each candidate, check if it has multiple senses and create disambiguated entries.
        """
        if not state.candidate_classes:
            return replace(state, steps_completed=state.steps_completed + ["disambiguation"])

        # Ask LLM to identify ambiguous terms
        system_prompt = """You are an expert in word sense disambiguation.
Identify if any of the given terms have multiple meanings or senses in the context.
Return a JSON object with ambiguous terms and their senses."""

        labels = [c.label for c in state.candidate_classes]
        user_prompt = f"""Check these terms for multiple senses:

Terms: {', '.join(labels)}

Context: {state.normalized_text}

Return JSON:
{{
  "ambiguous_terms": [
    {{"term": "Term1", "senses": ["Sense A", "Sense B"], "rationale": "Explanation"}}
  ]
}}"""

        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=state.input_data.get("model", "google/gemini-3-flash-preview"),
            temperature=0.0,
            max_tokens=500,
        )

        # Parse and create disambiguated candidates
        disambiguated = list(state.candidate_classes)
        try:
            parsed = json.loads(response.content)
            if not isinstance(parsed, dict):
                raise AttributeError(f"Expected dict, got {type(parsed).__name__}")

            for ambig in parsed.get("ambiguous_terms", []):
                term = ambig.get("term", "")
                senses = ambig.get("senses", [])
                rationale = ambig.get("rationale", "")

                # Find the original candidate and replace with disambiguated versions
                original_idx = next((i for i, c in enumerate(disambiguated) if c.label == term), -1)
                if original_idx >= 0 and len(senses) > 1:
                    original = disambiguated[original_idx]

                    # Create separate candidate for each sense
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

                    # Replace original with disambiguated versions
                    disambiguated = (
                        disambiguated[:original_idx]
                        + disambiguated_candidates
                        + disambiguated[original_idx + 1 :]
                    )
        except (json.JSONDecodeError, AttributeError) as e:
            # Record warning but continue without disambiguation
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
        Stage 7: Assign and refine confidence scores for all candidates.

        Ensures all candidates and connections have confidence in [0, 1].
        """
        # Create new instances with normalized confidence scores
        normalized_classes = [
            replace(
                candidate,
                confidence=max(0.0, min(1.0, candidate.confidence))
            )
            for candidate in state.candidate_classes
        ]

        normalized_properties = [
            replace(
                prop,
                confidence=max(0.0, min(1.0, prop.confidence))
            )
            for prop in state.candidate_properties
        ]

        normalized_connections = [
            replace(
                conn,
                confidence=max(0.0, min(1.0, conn.confidence))
            )
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

        Converts candidates to result dict.
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
        provenance = []

        # Case-insensitive search for the text
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
