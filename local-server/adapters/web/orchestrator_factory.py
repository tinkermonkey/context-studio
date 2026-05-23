"""
Factory for instantiating pipeline orchestrators with proper dependency injection.

This module provides a factory function that instantiates orchestrators
based on pipeline type and available services. Orchestrators require
different dependencies depending on their implementation.
"""

from typing import Any, Type

from domain.extraction.services import ExtractionService
from domain.pipeline.ports import LLMProvider
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionOrchestrator
from domain.pipelines.orchestration.base import PipelineOrchestrator
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
from domain.pipelines.schema_node_grounding.scoring import GroundingScorer
from utils.logger import get_logger

_logger = get_logger(__name__)


def create_orchestrator(
    orchestrator_class: Type[PipelineOrchestrator],
    pipeline_type: PipelineType,
    llm_provider: LLMProvider,
    services: dict[str, Any] | None = None,
) -> PipelineOrchestrator:
    """
    Instantiate a pipeline orchestrator with proper dependencies.

    Determines which dependencies the orchestrator needs based on its type
    and instantiates it accordingly.

    Args:
        orchestrator_class: The orchestrator class to instantiate
        pipeline_type: The pipeline type (for routing logic)
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
