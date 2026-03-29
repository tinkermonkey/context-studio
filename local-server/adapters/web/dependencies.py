"""
FastAPI dependency injection wiring.

Dependency functions extract services from the FastAPI app state and inject them
into route handlers. This pattern keeps services accessible while maintaining clean
separation between layers.

Each bounded context has getter functions for its services:
- get_ontology_service()
- get_graph_service()
- get_extraction_service()
- get_reference_sources()
- etc.

Usage in route handlers:

    @router.post("/classes")
    async def create_class(
        request: ClassCreateRequest,
        service: OntologyService = Depends(get_ontology_service),
    ) -> ClassResponse:
        # service is now injected from app.state
        pass
"""

from fastapi import Request

from domain.ontology.services import OntologyService
from domain.graph.services import GraphAnalysisService
from domain.extraction.services import ExtractionService
from domain.extraction.ports import ReferenceSource
from domain.pipeline.services import PipelineService


async def get_ontology_service(request: Request) -> OntologyService:
    """
    Extract the OntologyService from app state.

    Args:
        request: FastAPI request object

    Returns:
        The OntologyService instance from app.state

    Raises:
        RuntimeError: If service is not initialized in app.state
    """
    service = getattr(request.app.state, "ontology_service", None)
    if service is None:
        raise RuntimeError("OntologyService not initialized in app.state")
    return service


async def get_graph_service(request: Request) -> GraphAnalysisService:
    """
    Extract the GraphAnalysisService from app state.

    Args:
        request: FastAPI request object

    Returns:
        The GraphAnalysisService instance from app.state

    Raises:
        RuntimeError: If service is not initialized in app.state
    """
    service = getattr(request.app.state, "graph_service", None)
    if service is None:
        raise RuntimeError("GraphAnalysisService not initialized in app.state")
    return service


async def get_extraction_service(request: Request) -> ExtractionService:
    """
    Extract the ExtractionService from app state.

    Args:
        request: FastAPI request object

    Returns:
        The ExtractionService instance from app.state

    Raises:
        RuntimeError: If service is not initialized in app.state
    """
    service = getattr(request.app.state, "extraction_service", None)
    if service is None:
        raise RuntimeError("ExtractionService not initialized in app.state")
    return service


async def get_pipeline_service(request: Request) -> PipelineService:
    """
    Extract the PipelineService from app state.

    Args:
        request: FastAPI request object

    Returns:
        The PipelineService instance from app.state

    Raises:
        RuntimeError: If service is not initialized in app.state
    """
    service = getattr(request.app.state, "pipeline_service", None)
    if service is None:
        raise RuntimeError("PipelineService not initialized in app.state")
    return service


async def get_reference_sources(request: Request) -> list[ReferenceSource]:
    """
    Extract the list of reference sources from app state.

    Args:
        request: FastAPI request object

    Returns:
        The list of ReferenceSource instances from app.state

    Raises:
        RuntimeError: If reference sources are not initialized in app.state
    """
    sources = getattr(request.app.state, "reference_sources", None)
    if sources is None:
        raise RuntimeError("Reference sources not initialized in app.state")
    return sources
