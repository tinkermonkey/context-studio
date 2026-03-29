"""
FastAPI dependency injection wiring.

Dependency functions extract services from the FastAPI app state and inject them
into route handlers. This pattern keeps services accessible while maintaining clean
separation between layers.

Database session management:
- get_local_db_session(): Creates and closes a per-request session for local.db
- get_operations_db_session(): Creates and closes a per-request session for operations.db

Service dependencies:
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

from collections.abc import AsyncGenerator
from typing import cast

from fastapi import Request
from sqlalchemy.orm import Session

from domain.ontology.services import OntologyService
from domain.graph.services import GraphAnalysisService
from domain.extraction.services import ExtractionService
from domain.extraction.ports import ReferenceSource
from domain.pipeline.services import PipelineService
from adapters.persistence.sqlite.connection import DatabaseManager


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


async def get_local_db_session(request: Request) -> AsyncGenerator[Session, None]:
    """
    Create and manage a per-request SQLAlchemy session for local.db.

    This dependency ensures each request gets its own isolated database session.
    The session is automatically closed when the request completes, preventing
    cross-request state leakage and data corruption.

    Args:
        request: FastAPI request object

    Returns:
        A new SQLAlchemy Session instance for local.db

    Raises:
        RuntimeError: If DatabaseManager is not initialized in app.state
    """
    db_manager = cast(
        DatabaseManager | None, getattr(request.app.state, "db_manager", None)
    )
    if db_manager is None:
        raise RuntimeError("DatabaseManager not initialized in app.state")

    session = db_manager.get_local_session()
    try:
        yield session
    finally:
        session.close()


async def get_operations_db_session(request: Request) -> AsyncGenerator[Session, None]:
    """
    Create and manage a per-request SQLAlchemy session for operations.db.

    This dependency ensures each request gets its own isolated database session.
    The session is automatically closed when the request completes, preventing
    cross-request state leakage and data corruption.

    Args:
        request: FastAPI request object

    Returns:
        A new SQLAlchemy Session instance for operations.db

    Raises:
        RuntimeError: If DatabaseManager is not initialized in app.state
    """
    db_manager = cast(
        DatabaseManager | None, getattr(request.app.state, "db_manager", None)
    )
    if db_manager is None:
        raise RuntimeError("DatabaseManager not initialized in app.state")

    session = db_manager.get_operations_session()
    try:
        yield session
    finally:
        session.close()
