"""
Factory for instantiating pipeline orchestrators with proper dependency injection.

This module provides factory functions that instantiate orchestrators
and pipeline states based on pipeline type and available services.
"""

from typing import Any, Type

from domain.pipeline.ports import LLMProvider
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionOrchestrator
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionOrchestrator
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
)
from domain.pipelines.schema_node_grounding.orchestrator import SchemaGroundingOrchestrator
from utils.logger import get_logger

_logger = get_logger(__name__)


def create_orchestrator(
    orchestrator_class: Type[PipelineOrchestrator],
    llm_provider: LLMProvider,
    services: dict[str, Any] | None = None,
) -> PipelineOrchestrator:
    """
    Instantiate a pipeline orchestrator with proper dependencies.

    Determines which dependencies the orchestrator needs based on its type
    and instantiates it accordingly.

    Args:
        orchestrator_class: The orchestrator class to instantiate
        llm_provider: LLM provider for completions
        services: Dict of available services (extraction_service, grounding_adapter, etc.)

    Returns:
        Instantiated orchestrator with all dependencies injected

    Raises:
        ValueError: If required dependencies are missing
    """
    services = services or {}

    if orchestrator_class == NoOpPipelineOrchestrator:
        return NoOpPipelineOrchestrator(llm_provider=llm_provider)

    elif orchestrator_class == IndividualExtractionOrchestrator:
        extraction_service = services.get("extraction_service")
        if not extraction_service:
            raise ValueError("extraction_service is required for IndividualExtractionOrchestrator")
        return IndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            extraction_service=extraction_service,
        )

    elif orchestrator_class == SchemaExtractionOrchestrator:
        return SchemaExtractionOrchestrator(
            llm_provider=llm_provider,
        )

    elif orchestrator_class == SchemaGroundingOrchestrator:
        grounding_adapter = services.get("grounding_adapter")
        if not grounding_adapter:
            raise ValueError("grounding_adapter is required for SchemaGroundingOrchestrator")
        scorer = services.get("scorer")
        if not scorer:
            raise ValueError("scorer is required for SchemaGroundingOrchestrator")
        config = services.get("grounding_config", {})
        return SchemaGroundingOrchestrator(
            llm_provider=llm_provider,
            grounding_adapter=grounding_adapter,
            scorer=scorer,
            config=config,
        )

    elif orchestrator_class == DefinitionRefinementOrchestrator:
        ontology_repo = services.get("ontology_repo")
        if not ontology_repo:
            raise ValueError("ontology_repo is required for DefinitionRefinementOrchestrator")
        traversal = SchemaNeighborhoodTraversal(
            ontology_repo=ontology_repo,
            extraction_repo=services.get("extraction_repo"),
        )
        config = services.get("refinement_config", {})
        return DefinitionRefinementOrchestrator(
            llm_provider=llm_provider,
            traversal=traversal,
            config=config,
        )

    elif orchestrator_class == ConnectionRefinementOrchestrator:
        ontology_repo = services.get("ontology_repo")
        if not ontology_repo:
            raise ValueError("ontology_repo is required for ConnectionRefinementOrchestrator")
        traversal = SchemaNeighborhoodTraversal(
            ontology_repo=ontology_repo,
            extraction_repo=services.get("extraction_repo"),
        )
        config = services.get("refinement_config", {})
        return ConnectionRefinementOrchestrator(
            llm_provider=llm_provider,
            traversal=traversal,
            config=config,
        )

    else:
        raise ValueError(f"Unknown orchestrator class: {orchestrator_class.__name__}")


def create_pipeline_state(
    run_id: str,
    pipeline_type: PipelineType,
    input_data: dict[str, Any],
    llm_provider: Any,
) -> PipelineState:
    """
    Create a pipeline state for the given pipeline type.

    Different pipeline types require different state subclasses.
    This factory creates the appropriate state type based on the pipeline type.

    Args:
        run_id: Pipeline run ID
        pipeline_type: Type of pipeline
        input_data: Input data dict
        llm_provider: LLM provider instance

    Returns:
        PipelineState instance (or appropriate subclass)
    """
    if pipeline_type == PipelineType.NO_OP:
        from domain.pipelines.orchestration.noop import NoOpPipelineState
        return NoOpPipelineState(
            run_id=run_id,
            pipeline_type=pipeline_type,
            input_data=input_data,
            current_status="pending",
            llm_provider=llm_provider,
            result=None,
        )
    elif pipeline_type == PipelineType.SCHEMA_EXTRACTION:
        from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionState
        return SchemaExtractionState(
            run_id=run_id,
            pipeline_type=pipeline_type,
            input_data=input_data,
            current_status="pending",
            llm_provider=llm_provider,
            result=None,
        )
    elif pipeline_type == PipelineType.SCHEMA_NODE_GROUNDING:
        from domain.pipelines.schema_node_grounding.orchestrator import SchemaGroundingState
        return SchemaGroundingState(
            run_id=run_id,
            pipeline_type=pipeline_type,
            input_data=input_data,
            current_status="pending",
            llm_provider=llm_provider,
            result=None,
        )
    elif pipeline_type == PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT:
        from domain.pipelines.schema_node_definition_refinement.orchestrator import (
            DefinitionRefinementState,
        )
        return DefinitionRefinementState(
            run_id=run_id,
            pipeline_type=pipeline_type,
            input_data=input_data,
            current_status="pending",
            llm_provider=llm_provider,
            result=None,
        )
    elif pipeline_type == PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT:
        from domain.pipelines.schema_node_connection_refinement.orchestrator import (
            ConnectionRefinementState,
        )
        return ConnectionRefinementState(
            run_id=run_id,
            pipeline_type=pipeline_type,
            input_data=input_data,
            current_status="pending",
            llm_provider=llm_provider,
            result=None,
        )
    elif pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION:
        from domain.pipelines.individual_extraction.orchestrator import (
            IndividualExtractionState,
        )
        return IndividualExtractionState(
            run_id=run_id,
            pipeline_type=pipeline_type,
            input_data=input_data,
            current_status="pending",
            llm_provider=llm_provider,
            result=None,
        )
    else:
        return PipelineState(
            run_id=run_id,
            pipeline_type=pipeline_type,
            input_data=input_data,
            current_status="pending",
            llm_provider=llm_provider,
            result=None,
        )
