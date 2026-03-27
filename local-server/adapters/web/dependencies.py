"""
FastAPI dependency injection wiring.

Dependency functions extract services from the FastAPI app state and inject them
into route handlers. This pattern keeps services accessible while maintaining clean
separation between layers.

Each bounded context has getter functions for its services:
- get_ontology_service()
- get_graph_service()
- get_extraction_service()
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
