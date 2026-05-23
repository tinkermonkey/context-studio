"""
Individual Extraction pipeline orchestrator.

Wraps Wave A's ExtractionService.extract_triples() as a PipelineOrchestrator,
maintaining backward compatibility with existing extraction logic while
integrating with the new pipeline framework.

This is a single-node orchestrator (minimal refactoring) that delegates to
the existing extraction service rather than reimplementing extraction logic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from domain.extraction.services import ExtractionService
from domain.pipeline.ports import LLMProvider
from domain.pipelines.entities import PipelineType
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState


@dataclass
class IndividualExtractionState(PipelineState):
    """
    State for individual extraction pipeline execution.

    Extends PipelineState with fields specific to text extraction.
    """

    source_text: str = ""
    source_text_hash: str = ""
    ontology_id: str = ""
    model: str = ""
    temperature: float = 0.0
    extracted_triples: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class IndividualExtractionOrchestrator(PipelineOrchestrator):
    """
    Orchestrator for individual text extraction operations.

    Wraps ExtractionService.extract_triples() to extract RDF triples from
    text scoped to a specific ontology. This is a minimal-refactoring wrapper
    that maintains Wave A's extraction logic while integrating with the new
    pipeline framework.

    Single-node execution:
    - Validate inputs (text, ontology_id)
    - Call ExtractionService.extract_triples()
    - Populate PipelineRun.output_summary and llm_metadata
    - Return extracted triples with confidence and provenance
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        extraction_service: ExtractionService,
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            llm_provider: Port implementation for LLM completions
            extraction_service: Service for extraction logic
        """
        super().__init__(llm_provider)
        self._extraction_service = extraction_service
        self._graph = None

    def build_graph(self) -> Any:
        """
        Build and return the LangGraph state graph.

        For this single-node implementation, the graph is minimal.
        Returns None for now; can be extended to LangGraph if needed.

        Returns:
            None (single-node execution, no explicit graph)
        """
        return None

    async def execute(self, state: PipelineState) -> PipelineState:
        """
        Execute the individual extraction pipeline.

        Args:
            state: IndividualExtractionState with input_data containing:
                - text: Source text to extract from
                - ontology_id: Target ontology identifier
                - model: LLM model name
                - temperature: Sampling temperature (0.0–2.0)

        Returns:
            Updated IndividualExtractionState with extracted triples and metadata

        Raises:
            ValueError: If required input fields are missing
            ExtractionError: If extraction fails
        """
        # Cast to subclass for type checking
        if not isinstance(state, IndividualExtractionState):
            state = IndividualExtractionState(
                run_id=state.run_id,
                pipeline_type=state.pipeline_type,
                input_data=state.input_data,
                current_status=state.current_status,
                llm_provider=state.llm_provider,
                result=state.result,
            )

        # Extract input parameters
        text = state.input_data.get("text", "")
        ontology_id = state.input_data.get("ontology_id", "")
        model = state.input_data.get("model", "")
        temperature = state.input_data.get("temperature", 0.0)

        # Validate required inputs
        if not text or not text.strip():
            raise ValueError("text is required and cannot be empty")
        if not ontology_id:
            raise ValueError("ontology_id is required")
        if not model:
            raise ValueError("model is required")

        # Update state with input data
        state.source_text = text
        state.source_text_hash = hashlib.sha256(text.encode()).hexdigest()
        state.ontology_id = ontology_id
        state.model = model
        state.temperature = temperature
        state.current_status = "running"

        try:
            # Call extraction service
            result = self._extraction_service.extract_triples(
                text=text,
                ontology_id=ontology_id,
                model=model,
                temperature=temperature,
            )

            # Populate result state
            state.extracted_triples = result.triples
            state.warnings = result.warnings
            state.metadata = result.metadata

            # Set result for PipelineRun
            state.result = {
                "triples": result.triples,
                "warnings": result.warnings,
                "metadata": result.metadata,
            }

            state.current_status = "completed"

        except Exception as exc:
            state.current_status = "failed"
            state.warnings.append(f"Extraction error: {str(exc)}")
            state.result = {
                "triples": [],
                "warnings": state.warnings,
                "metadata": {},
            }
            raise

        return state
