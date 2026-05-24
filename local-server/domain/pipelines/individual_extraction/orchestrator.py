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
from dataclasses import dataclass, field, replace
from typing import Any

from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.ports import LLMProvider
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import ExtractionPort


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
        extraction_service: ExtractionPort,
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            llm_provider: Port implementation for LLM completions
            extraction_service: Port implementation for extraction logic
        """
        super().__init__(llm_provider)
        self._extraction_service = extraction_service

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
            PipelineInputError: If required input fields are missing
            PipelineExecutionError: If extraction fails
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
            exc = PipelineInputError("text is required and cannot be empty")
            state = replace(
                state, current_status=PipelineRunStatus.FAILED, result={"error": str(exc)}
            )
            raise exc
        if not ontology_id:
            exc = PipelineInputError("ontology_id is required")
            state = replace(
                state, current_status=PipelineRunStatus.FAILED, result={"error": str(exc)}
            )
            raise exc
        if not model:
            exc = PipelineInputError("model is required")
            state = replace(
                state, current_status=PipelineRunStatus.FAILED, result={"error": str(exc)}
            )
            raise exc

        # Update state with input data
        state = replace(
            state,
            source_text=text,
            source_text_hash=hashlib.sha256(text.encode()).hexdigest(),
            ontology_id=ontology_id,
            model=model,
            temperature=temperature,
            current_status=PipelineRunStatus.RUNNING,
        )

        try:
            # Call extraction service
            result = self._extraction_service.extract_triples(
                text=text,
                ontology_id=ontology_id,
                model=model,
                temperature=temperature,
            )

            # Populate result state
            state = replace(
                state,
                extracted_triples=result.triples,
                warnings=result.warnings,
                metadata=result.metadata,
                result={
                    "triples": result.triples,
                    "warnings": result.warnings,
                    "metadata": result.metadata,
                },
                current_status=PipelineRunStatus.COMPLETED,
            )

        except PipelineExecutionError:
            state = replace(state, current_status=PipelineRunStatus.FAILED)
            raise
        except Exception as exc:
            state = replace(
                state,
                current_status=PipelineRunStatus.FAILED,
                result={"error": str(exc)},
            )
            raise PipelineExecutionError(f"Individual extraction failed: {str(exc)}") from exc

        return state
