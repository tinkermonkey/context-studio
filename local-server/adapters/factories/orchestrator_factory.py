"""
Factory for instantiating pipeline orchestrators with proper dependency injection.

This module provides factory functions that instantiate orchestrators
and pipeline states based on pipeline type and available services.
"""

from hashlib import sha256
from typing import Any, Callable, Type

from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator, NoOpPipelineState
from domain.pipelines.ports import LLMProvider
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.schema_extraction.orchestrator import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
)
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
    ConnectionRefinementState,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
    DefinitionRefinementState,
)
from domain.pipelines.schema_node_grounding.orchestrator import (
    SchemaGroundingOrchestrator,
    SchemaGroundingState,
)
from utils.logger import get_logger

_logger = get_logger(__name__)


def _build_noop(llm_provider: LLMProvider, services: dict[str, Any]) -> PipelineOrchestrator:
    return NoOpPipelineOrchestrator(llm_provider=llm_provider)


def _build_individual_extraction(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    extraction_service = services.get("extraction_service")
    if not extraction_service:
        raise ValueError("extraction_service is required for IndividualExtractionOrchestrator")
    return IndividualExtractionOrchestrator(
        llm_provider=llm_provider,
        extraction_service=extraction_service,
    )


def _build_schema_extraction(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    return SchemaExtractionOrchestrator(
        llm_provider=llm_provider,
        ontology_repo=services.get("ontology_repo"),
    )


def _build_schema_grounding(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    grounding_adapter = services.get("grounding_adapter")
    if not grounding_adapter:
        raise ValueError("grounding_adapter is required for SchemaGroundingOrchestrator")
    scorer = services.get("scorer")
    if not scorer:
        raise ValueError("scorer is required for SchemaGroundingOrchestrator")
    return SchemaGroundingOrchestrator(
        llm_provider=llm_provider,
        grounding_adapter=grounding_adapter,
        scorer=scorer,
        config=services.get("grounding_config", {}),
    )


def _build_definition_refinement(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    ontology_repo = services.get("ontology_repo")
    if not ontology_repo:
        raise ValueError("ontology_repo is required for DefinitionRefinementOrchestrator")
    traversal = SchemaNeighborhoodTraversal(
        ontology_repo=ontology_repo,
        extraction_repo=services.get("extraction_repo"),
    )
    return DefinitionRefinementOrchestrator(
        llm_provider=llm_provider,
        traversal=traversal,
        config=services.get("refinement_config", {}),
    )


def _build_connection_refinement(
    llm_provider: LLMProvider, services: dict[str, Any]
) -> PipelineOrchestrator:
    ontology_repo = services.get("ontology_repo")
    if not ontology_repo:
        raise ValueError("ontology_repo is required for ConnectionRefinementOrchestrator")
    traversal = SchemaNeighborhoodTraversal(
        ontology_repo=ontology_repo,
        extraction_repo=services.get("extraction_repo"),
    )
    return ConnectionRefinementOrchestrator(
        llm_provider=llm_provider,
        traversal=traversal,
        config=services.get("refinement_config", {}),
    )


_ORCHESTRATOR_BUILDERS: dict[
    Type[PipelineOrchestrator], Callable[[LLMProvider, dict[str, Any]], PipelineOrchestrator]
] = {
    NoOpPipelineOrchestrator: _build_noop,
    IndividualExtractionOrchestrator: _build_individual_extraction,
    SchemaExtractionOrchestrator: _build_schema_extraction,
    SchemaGroundingOrchestrator: _build_schema_grounding,
    DefinitionRefinementOrchestrator: _build_definition_refinement,
    ConnectionRefinementOrchestrator: _build_connection_refinement,
}

_PIPELINE_TYPE_TO_STATE: dict[PipelineType, Type[PipelineState]] = {
    PipelineType.NO_OP: NoOpPipelineState,
    PipelineType.INDIVIDUAL_EXTRACTION: IndividualExtractionState,
    PipelineType.SCHEMA_EXTRACTION: SchemaExtractionState,
    PipelineType.SCHEMA_NODE_GROUNDING: SchemaGroundingState,
    PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT: DefinitionRefinementState,
    PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT: ConnectionRefinementState,
}


def create_orchestrator(
    orchestrator_class: Type[PipelineOrchestrator],
    llm_provider: LLMProvider,
    services: dict[str, Any] | None = None,
) -> PipelineOrchestrator:
    """
    Instantiate a pipeline orchestrator with proper dependencies.

    Args:
        orchestrator_class: The orchestrator class to instantiate
        llm_provider: LLM provider for completions
        services: Dict of available services (extraction_service, grounding_adapter, etc.)

    Returns:
        Instantiated orchestrator with all dependencies injected

    Raises:
        ValueError: If the orchestrator class is unknown or required dependencies are missing
    """
    builder = _ORCHESTRATOR_BUILDERS.get(orchestrator_class)
    if builder is None:
        raise ValueError(f"Unknown orchestrator class: {orchestrator_class.__name__}")
    return builder(llm_provider, services or {})


def create_pipeline_state(
    run_id: str,
    pipeline_type: PipelineType,
    input_data: dict[str, Any],
    llm_provider: Any,
) -> PipelineState:
    """
    Create a pipeline state for the given pipeline type.

    Args:
        run_id: Pipeline run ID
        pipeline_type: Type of pipeline
        input_data: Input data dict
        llm_provider: LLM provider instance

    Returns:
        PipelineState instance (or appropriate subclass)

    Raises:
        ValueError: If the pipeline type has no registered state class
    """
    state_class = _PIPELINE_TYPE_TO_STATE.get(pipeline_type)
    if state_class is None:
        raise ValueError(f"No state class registered for pipeline type: {pipeline_type.value}")
    return state_class(
        run_id=run_id,
        pipeline_type=pipeline_type,
        input_data=input_data,
        current_status=PipelineRunStatus.PENDING,
        llm_provider=llm_provider,
        result=None,
    )


def build_run_specific_data(
    pipeline_type: PipelineType,
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the type-specific fields dict to pass to the pipeline run repository.

    Encapsulates any input-derived data transformations (e.g. hashing) so that
    route handlers remain thin adapters with no domain-level computation.

    Args:
        pipeline_type: The pipeline type being run
        input_data: The raw input_data from the request

    Returns:
        Dict of type-specific fields (may be empty for types with no extra fields)
    """
    if pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION:
        text = input_data.get("text", "")
        specific: dict[str, Any] = {"source_text_hash": sha256(text.encode()).hexdigest()}
        source_document_uri = input_data.get("source_document_uri")
        if source_document_uri:
            specific["source_document_uri"] = source_document_uri
        return specific
    return {}
