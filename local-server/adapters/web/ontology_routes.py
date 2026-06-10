"""
FastAPI routes for the Ontology bounded context.

This module implements all HTTP endpoints for CRUD operations on ontology entities:
- Taxonomies
- ConceptSchemes
- Classes
- Relationships
- PropertyDefinitions
- Individuals

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

No business logic lives here—all validation and constraints are in the domain service.
Error handling translates domain exceptions to appropriate HTTP responses.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from adapters.web.dependencies import get_ontology_service
from adapters.web.schemas.ontology import (
    ClassCreateRequest,
    ClassMoveRequest,
    ClassResponse,
    ClassUpdateRequest,
    ConceptSchemeCreateRequest,
    ConceptSchemeResponse,
    ConceptSchemeUpdateRequest,
    DataPropertyValueResponse,
    IndividualClassListRequest,
    IndividualClassRequest,
    IndividualCreateRequest,
    IndividualResponse,
    IndividualUpdateRequest,
    ListResponse,
    PropertyDefinitionCreateRequest,
    PropertyDefinitionResponse,
    PropertyDefinitionUpdateRequest,
    PublishDiffStats,
    RelationshipCreateRequest,
    RelationshipResponse,
    TaxonomyCreateRequest,
    TaxonomyPublishRequest,
    TaxonomyResponse,
    TaxonomyUpdateRequest,
)
from domain.ontology.exceptions import (
    CircularReferenceError,
    DuplicateEntityError,
    EntityNotFoundError,
    IdentifierConflictError,
    OntologyError,
)
from domain.ontology.services import _UNSET, OntologyService
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["ontology"])

_logger = get_logger(__name__)


# ==================== Error Handler Utilities ====================


def _handle_domain_error(exc: Exception) -> tuple[int, str]:
    """
    Map domain exceptions to HTTP status codes and error messages.

    Args:
        exc: The domain exception

    Returns:
        Tuple of (status_code, error_message)
    """
    if isinstance(exc, EntityNotFoundError):
        return (status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, CircularReferenceError):
        return (status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    elif isinstance(exc, DuplicateEntityError):
        return (status.HTTP_409_CONFLICT, str(exc))
    elif isinstance(exc, IdentifierConflictError):
        return (status.HTTP_409_CONFLICT, str(exc))
    elif isinstance(exc, OntologyError):
        return (status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    elif isinstance(exc, ValueError):
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        # Log the original exception for unexpected errors
        _logger.error(f"Unexpected error in ontology endpoint: {exc}", exc_info=exc)
        return (status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")


# ==================== Taxonomy Endpoints ====================


@router.post("/taxonomies", response_model=TaxonomyResponse, status_code=status.HTTP_201_CREATED)
async def create_taxonomy(
    request: TaxonomyCreateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> TaxonomyResponse:
    """
    Create a new taxonomy.

    Args:
        request: TaxonomyCreateRequest with title and optional description
        service: OntologyService from dependency injection

    Returns:
        Created taxonomy as TaxonomyResponse

    Raises:
        HTTPException: 400 if title is empty, 409 if title already exists
    """
    try:
        taxonomy = await run_sync_in_executor(
            service.create_taxonomy,
            request.title,
            request.description,
            None,
        )
        return TaxonomyResponse.model_validate(taxonomy)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/taxonomies", response_model=ListResponse[TaxonomyResponse])
async def list_taxonomies(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    sort_by: Optional[str] = Query(
        None,
        pattern="^(title|created_at|last_modified)$",
        description="Field to sort by (title, created_at, last_modified)",
    ),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort direction"),
    q: Optional[str] = Query(None, description="Text search query on title"),
    service: OntologyService = Depends(get_ontology_service),
) -> ListResponse[TaxonomyResponse]:
    """
    Retrieve taxonomies with optional pagination, sorting, and text search.

    Args:
        limit: Maximum number of results (1-1000, default 100)
        offset: Number of results to skip (default 0)
        sort_by: Field to sort by (title, created_at, last_modified)
        sort_order: Sort direction (asc or desc, default asc)
        q: Text query for LIKE search on title
        service: OntologyService from dependency injection

    Returns:
        ListResponse containing matching taxonomies
    """
    try:
        taxonomies = await run_sync_in_executor(
            service.list_taxonomies,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            query=q,
        )
        total = await run_sync_in_executor(service.count_taxonomies, query=q)
        return ListResponse(
            items=[TaxonomyResponse.model_validate(t) for t in taxonomies],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/taxonomies/{taxonomy_id}", response_model=TaxonomyResponse)
async def get_taxonomy(
    taxonomy_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> TaxonomyResponse:
    """
    Retrieve a taxonomy by ID.

    Args:
        taxonomy_id: The taxonomy ID
        service: OntologyService from dependency injection

    Returns:
        TaxonomyResponse

    Raises:
        HTTPException: 404 if taxonomy not found
    """
    try:
        taxonomy = await run_sync_in_executor(service.get_taxonomy, taxonomy_id)
        return TaxonomyResponse.model_validate(taxonomy)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/taxonomies/{taxonomy_id}", response_model=TaxonomyResponse)
async def update_taxonomy(
    taxonomy_id: str,
    request: TaxonomyUpdateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> TaxonomyResponse:
    """
    Update a taxonomy's title and/or description.

    Args:
        taxonomy_id: The taxonomy ID
        request: TaxonomyUpdateRequest with optional fields to update
        service: OntologyService from dependency injection

    Returns:
        Updated TaxonomyResponse

    Raises:
        HTTPException: 400 if invalid input, 404 if not found, 409 if title exists
    """
    try:
        taxonomy = await run_sync_in_executor(
            service.update_taxonomy,
            taxonomy_id=taxonomy_id,
            title=request.title,
            description=request.description,
            color=request.color,
        )
        return TaxonomyResponse.model_validate(taxonomy)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/taxonomies/{taxonomy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_taxonomy(
    taxonomy_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> None:
    """
    Delete a taxonomy.

    Args:
        taxonomy_id: The taxonomy ID
        service: OntologyService from dependency injection

    Raises:
        HTTPException: 404 if not found, 422 if it has concept schemes
    """
    try:
        await run_sync_in_executor(service.delete_taxonomy, taxonomy_id)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/taxonomies/{taxonomy_id}/publish-diff", response_model=PublishDiffStats)
async def get_publish_diff_stats(
    taxonomy_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> PublishDiffStats:
    """
    Get diff statistics for publishing a taxonomy.

    Args:
        taxonomy_id: The taxonomy ID
        service: OntologyService from dependency injection

    Returns:
        PublishDiffStats with counts of added, modified, and removed classes

    Raises:
        HTTPException: 404 if not found
    """
    try:
        stats = await run_sync_in_executor(service.get_publish_diff_stats, taxonomy_id)
        return PublishDiffStats(**stats)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/taxonomies/{taxonomy_id}/publish", response_model=TaxonomyResponse)
async def publish_taxonomy(
    taxonomy_id: str,
    request: TaxonomyPublishRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> TaxonomyResponse:
    """
    Publish a taxonomy, transitioning status from draft to published.

    Args:
        taxonomy_id: The taxonomy ID
        request: TaxonomyPublishRequest with commit message
        service: OntologyService from dependency injection

    Returns:
        Updated TaxonomyResponse with status=published

    Raises:
        HTTPException: 404 if not found
    """
    try:
        taxonomy = await run_sync_in_executor(
            service.publish_taxonomy, taxonomy_id, request.commit_message
        )
        return TaxonomyResponse.model_validate(taxonomy)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== ConceptScheme Endpoints ====================


@router.post(
    "/taxonomies/{taxonomy_id}/schemes",
    response_model=ConceptSchemeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_concept_scheme(
    taxonomy_id: str,
    request: ConceptSchemeCreateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> ConceptSchemeResponse:
    """
    Create a new concept scheme within a taxonomy.

    Args:
        taxonomy_id: The parent taxonomy ID
        request: ConceptSchemeCreateRequest with title and optional description
        service: OntologyService from dependency injection

    Returns:
        Created ConceptSchemeResponse

    Raises:
        HTTPException: 400 if invalid, 404 if taxonomy not found, 409 if title exists
    """
    try:
        scheme = await run_sync_in_executor(
            service.create_scheme,
            taxonomy_id=taxonomy_id,
            title=request.title,
            description=request.description,
            color=None,
        )
        return ConceptSchemeResponse.model_validate(scheme)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/schemes", response_model=ListResponse[ConceptSchemeResponse])
async def list_concept_schemes(
    taxonomy_id: Optional[str] = Query(None, description="Optional taxonomy ID to filter by"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    sort_by: Optional[str] = Query(
        None,
        pattern="^(title|created_at|last_modified)$",
        description="Field to sort by (title, created_at, last_modified)",
    ),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort direction"),
    q: Optional[str] = Query(None, description="Text search query on title"),
    service: OntologyService = Depends(get_ontology_service),
) -> ListResponse[ConceptSchemeResponse]:
    """
    Retrieve concept schemes with optional filtering, pagination, sorting, and text search.

    Args:
        taxonomy_id: Optional taxonomy ID to filter by
        limit: Maximum number of results (1-1000, default 100)
        offset: Number of results to skip (default 0)
        sort_by: Field to sort by (title, created_at, last_modified)
        sort_order: Sort direction (asc or desc, default asc)
        q: Text query for LIKE search on title
        service: OntologyService from dependency injection

    Returns:
        ListResponse containing matching concept schemes
    """
    try:
        schemes = await run_sync_in_executor(
            service.list_concept_schemes,
            taxonomy_id=taxonomy_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            query=q,
        )
        total = await run_sync_in_executor(
            service.count_concept_schemes, taxonomy_id=taxonomy_id, query=q
        )
        return ListResponse(
            items=[ConceptSchemeResponse.model_validate(s) for s in schemes],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/schemes/{scheme_id}", response_model=ConceptSchemeResponse)
async def get_concept_scheme(
    scheme_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> ConceptSchemeResponse:
    """
    Retrieve a concept scheme by ID.

    Args:
        scheme_id: The concept scheme ID
        service: OntologyService from dependency injection

    Returns:
        ConceptSchemeResponse

    Raises:
        HTTPException: 404 if not found
    """
    try:
        scheme = service.get_concept_scheme(scheme_id)
        return ConceptSchemeResponse.model_validate(scheme)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/schemes/{scheme_id}", response_model=ConceptSchemeResponse)
async def update_concept_scheme(
    scheme_id: str,
    request: ConceptSchemeUpdateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> ConceptSchemeResponse:
    """
    Update a concept scheme's title and/or description.

    Args:
        scheme_id: The concept scheme ID
        request: ConceptSchemeUpdateRequest with optional fields to update
        service: OntologyService from dependency injection

    Returns:
        Updated ConceptSchemeResponse

    Raises:
        HTTPException: 400 if invalid, 404 if not found, 409 if title exists
    """
    try:
        scheme = service.update_concept_scheme(
            concept_scheme_id=scheme_id,
            title=request.title,
            description=request.description,
            color=request.color,
            taxonomy_id=request.taxonomy_id,
        )
        return ConceptSchemeResponse.model_validate(scheme)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/schemes/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_concept_scheme(
    scheme_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> None:
    """
    Delete a concept scheme.

    Args:
        scheme_id: The concept scheme ID
        service: OntologyService from dependency injection

    Raises:
        HTTPException: 404 if not found, 422 if it has classes
    """
    try:
        service.delete_scheme(scheme_id)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Class Endpoints ====================


@router.post(
    "/schemes/{scheme_id}/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_class(
    scheme_id: str,
    request: ClassCreateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> ClassResponse:
    """
    Create a new class within a concept scheme.

    Args:
        scheme_id: The parent concept scheme ID
        request: ClassCreateRequest with title and optional description/parent
        service: OntologyService from dependency injection

    Returns:
        Created ClassResponse

    Raises:
        HTTPException: 400 if invalid, 404 if scheme/parent not found, 409 if title exists
    """
    try:
        cls = service.create_class(
            concept_scheme_id=scheme_id,
            title=request.title,
            description=request.description,
            color=None,
            parent_class_id=request.parent_class_id,
        )
        return ClassResponse.model_validate(cls)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/classes", response_model=ListResponse[ClassResponse])
async def list_classes(
    concept_scheme_id: Optional[str] = Query(
        None, description="Optional concept scheme ID to filter by"
    ),
    parent_class_id: Optional[str] = Query(
        None, description="Optional parent class ID to filter by"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: OntologyService = Depends(get_ontology_service),
) -> ListResponse[ClassResponse]:
    """
    Retrieve classes with optional filtering and pagination.

    Args:
        concept_scheme_id: Optional concept scheme ID to filter by
        parent_class_id: Optional parent class ID to filter by
        limit: Maximum number of results (1-1000, default 100)
        offset: Number of results to skip (default 0)
        service: OntologyService from dependency injection

    Returns:
        ListResponse containing matching classes
    """
    try:
        classes = service.list_classes(
            concept_scheme_id=concept_scheme_id,
            parent_class_id=parent_class_id,
            limit=limit,
            offset=offset,
        )
        total = service.count_classes(concept_scheme_id=concept_scheme_id)
        return ListResponse(
            items=[ClassResponse.model_validate(c) for c in classes],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> ClassResponse:
    """
    Retrieve a class by ID.

    Args:
        class_id: The class ID
        service: OntologyService from dependency injection

    Returns:
        ClassResponse

    Raises:
        HTTPException: 404 if not found
    """
    try:
        cls = service.get_class(class_id)
        return ClassResponse.model_validate(cls)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/classes/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: str,
    request: ClassUpdateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> ClassResponse:
    """
    Update a class's title and/or description.

    Args:
        class_id: The class ID
        request: ClassUpdateRequest with optional fields to update
        service: OntologyService from dependency injection

    Returns:
        Updated ClassResponse

    Raises:
        HTTPException: 400 if invalid, 404 if not found, 409 if title exists
    """
    try:
        cls = service.update_class(
            class_id=class_id,
            title=request.title,
            description=request.description,
            color=request.color,
        )
        return ClassResponse.model_validate(cls)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/classes/{class_id}/move", response_model=ClassResponse)
async def move_class(
    class_id: str,
    request: ClassMoveRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> ClassResponse:
    """
    Move a class to a different concept scheme.

    Args:
        class_id: The class ID
        request: ClassMoveRequest with target_scheme_id
        service: OntologyService from dependency injection

    Returns:
        Updated ClassResponse with new concept_scheme_id

    Raises:
        HTTPException: 400 if invalid, 404 if not found
    """
    try:
        # Use the service method to move the class to a different scheme
        cls = await run_sync_in_executor(
            service.move_class_to_scheme,
            class_id,
            request.target_scheme_id,
        )
        return ClassResponse.model_validate(cls)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> None:
    """
    Delete a class.

    Args:
        class_id: The class ID
        service: OntologyService from dependency injection

    Raises:
        HTTPException: 404 if not found, 422 if it has subclasses or individuals
    """
    try:
        service.delete_class(class_id)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Relationship Endpoints ====================


@router.post(
    "/relationships",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_relationship(
    request: RelationshipCreateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> RelationshipResponse:
    """
    Create a new typed relationship between two entities.

    Args:
        request: RelationshipCreateRequest with source, target, and relationship_type
        service: OntologyService from dependency injection

    Returns:
        Created RelationshipResponse

    Raises:
        HTTPException: 400 if invalid (self-loop), 404 if entities not found, 409 if duplicate
    """
    try:
        # Get or create the property definition based on relationship_type
        prop_def = service.get_or_create_property_definition_by_identifier(
            identifier=request.relationship_type,
            title=request.relationship_type.replace("_", " ").title(),
        )

        relationship = service.create_relationship(
            source_id=request.source_id,
            target_id=request.target_id,
            property_definition_id=prop_def.id,
        )
        return RelationshipResponse.model_validate(relationship)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/relationships", response_model=ListResponse[RelationshipResponse])
async def list_relationships(
    source_id: Optional[str] = Query(None, description="Optional source entity ID to filter by"),
    target_id: Optional[str] = Query(None, description="Optional target entity ID to filter by"),
    property_id: Optional[str] = Query(
        None, description="Optional property definition ID to filter by"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    sort_by: Optional[str] = Query(
        None, pattern="^created_at$", description="Field to sort by (created_at)"
    ),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort direction"),
    service: OntologyService = Depends(get_ontology_service),
) -> ListResponse[RelationshipResponse]:
    """
    Retrieve relationships with optional filtering, pagination, and sorting.

    Args:
        source_id: Optional source entity ID to filter by
        target_id: Optional target entity ID to filter by
        property_id: Optional property definition ID to filter by
        limit: Maximum number of results (1-1000, default 100)
        offset: Number of results to skip (default 0)
        sort_by: Field to sort by (created_at)
        sort_order: Sort direction (asc or desc, default asc)
        service: OntologyService from dependency injection

    Returns:
        ListResponse containing matching relationships
    """
    try:
        relationships = await run_sync_in_executor(
            service.list_relationships,
            source_id=source_id,
            target_id=target_id,
            property_id=property_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            query=None,
        )
        total = await run_sync_in_executor(
            service.count_relationships,
            source_id=source_id,
            target_id=target_id,
            property_id=property_id,
        )
        return ListResponse(
            items=[RelationshipResponse.model_validate(r) for r in relationships],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/relationships/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(
    relationship_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> RelationshipResponse:
    """
    Retrieve a relationship by ID.

    Args:
        relationship_id: The relationship ID
        service: OntologyService from dependency injection

    Returns:
        RelationshipResponse

    Raises:
        HTTPException: 404 if not found
    """
    try:
        relationship = service.get_relationship(relationship_id)
        return RelationshipResponse.model_validate(relationship)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(
    relationship_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> None:
    """
    Delete a relationship.

    Args:
        relationship_id: The relationship ID
        service: OntologyService from dependency injection

    Raises:
        HTTPException: 404 if not found
    """
    try:
        service.delete_relationship(relationship_id)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== PropertyDefinition Endpoints ====================


@router.post(
    "/properties",
    response_model=PropertyDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_property_definition(
    request: PropertyDefinitionCreateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> PropertyDefinitionResponse:
    """
    Create a new property definition (relationship type).

    Args:
        request: PropertyDefinitionCreateRequest with identifier and title
        service: OntologyService from dependency injection

    Returns:
        Created PropertyDefinitionResponse

    Raises:
        HTTPException: 400 if invalid, 409 if identifier or title exists
    """
    try:
        prop_def = service.create_property_definition(
            identifier=request.identifier,
            title=request.title,
            description=request.description,
        )
        return PropertyDefinitionResponse.model_validate(prop_def)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/properties", response_model=ListResponse[PropertyDefinitionResponse])
async def list_property_definitions(
    is_relevant: Optional[bool] = Query(
        None, description="Optional filter for relevant properties"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    sort_by: Optional[str] = Query(
        None,
        pattern="^(title|created_at|last_modified)$",
        description="Field to sort by (title, created_at, last_modified)",
    ),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort direction"),
    q: Optional[str] = Query(None, description="Text search query on title"),
    service: OntologyService = Depends(get_ontology_service),
) -> ListResponse[PropertyDefinitionResponse]:
    """
    Retrieve property definitions with optional filtering, pagination, sorting, and text search.

    Args:
        is_relevant: Optional filter for relevant properties
        limit: Maximum number of results (1-1000, default 100)
        offset: Number of results to skip (default 0)
        sort_by: Field to sort by (title, created_at, last_modified)
        sort_order: Sort direction (asc or desc, default asc)
        q: Text query for LIKE search on title
        service: OntologyService from dependency injection

    Returns:
        ListResponse containing property definitions
    """
    try:
        properties = await run_sync_in_executor(
            service.list_property_definitions,
            is_relevant=is_relevant,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            query=q,
        )
        total = await run_sync_in_executor(
            service.count_property_definitions,
            is_relevant=is_relevant,
            query=q,
        )
        return ListResponse(
            items=[PropertyDefinitionResponse.model_validate(p) for p in properties],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/properties/{property_id}", response_model=PropertyDefinitionResponse)
async def get_property_definition(
    property_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> PropertyDefinitionResponse:
    """
    Retrieve a property definition by ID.

    Args:
        property_id: The property definition ID
        service: OntologyService from dependency injection

    Returns:
        PropertyDefinitionResponse

    Raises:
        HTTPException: 404 if not found
    """
    try:
        prop_def = service.get_property_definition(property_id)
        return PropertyDefinitionResponse.model_validate(prop_def)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/properties/{property_id}", response_model=PropertyDefinitionResponse)
async def update_property_definition(
    property_id: str,
    request: PropertyDefinitionUpdateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> PropertyDefinitionResponse:
    """
    Update a property definition's title and/or description.

    Note: identifier cannot be changed after creation.

    Args:
        property_id: The property definition ID
        request: PropertyDefinitionUpdateRequest with optional fields to update
        service: OntologyService from dependency injection

    Returns:
        Updated PropertyDefinitionResponse

    Raises:
        HTTPException: 400 if invalid, 404 if not found
    """
    try:
        is_relevant_arg = (
            request.is_relevant if "is_relevant" in request.model_fields_set else _UNSET
        )
        prop_def = service.update_property_definition(
            property_id=property_id,
            title=request.title,
            description=request.description,
            is_relevant=is_relevant_arg,
        )
        return PropertyDefinitionResponse.model_validate(prop_def)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property_definition(
    property_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> None:
    """
    Delete a property definition.

    Args:
        property_id: The property definition ID
        service: OntologyService from dependency injection

    Raises:
        HTTPException: 404 if not found
    """
    try:
        service.delete_property_definition(property_id)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Individual Endpoints ====================


@router.post(
    "/individuals",
    response_model=IndividualResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_individual(
    request: IndividualCreateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> IndividualResponse:
    """
    Create a new individual instance of one or more classes.

    Args:
        request: IndividualCreateRequest with class_ids and title
        service: OntologyService from dependency injection

    Returns:
        Created IndividualResponse

    Raises:
        HTTPException: 400 if invalid or invariant violated, 404 if class not found, 409 if title
        exists
    """
    try:
        individual = await run_sync_in_executor(
            service.create_individual,
            request.class_ids,
            request.title,
            request.description,
        )
        return IndividualResponse.model_validate(individual)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/individuals", response_model=ListResponse[IndividualResponse])
async def list_individuals(
    class_id: Optional[str] = Query(None, description="Optional class ID to filter by"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: OntologyService = Depends(get_ontology_service),
) -> ListResponse[IndividualResponse]:
    """
    Retrieve individuals with optional filtering and pagination.

    Args:
        class_id: Optional class ID to filter by (returns Individuals having this Class as a parent)
        limit: Maximum number of results (1-1000, default 100)
        offset: Number of results to skip (default 0)
        service: OntologyService from dependency injection

    Returns:
        ListResponse containing matching individuals
    """
    try:
        # For now, we get all individuals and apply pagination in memory
        # In the future, the repository should support limit/offset directly
        all_individuals = await run_sync_in_executor(service.list_individuals, class_id)
        total = len(all_individuals)
        paginated = all_individuals[offset : offset + limit]
        return ListResponse(
            items=[IndividualResponse.model_validate(i) for i in paginated],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/individuals/{individual_id}", response_model=IndividualResponse)
async def get_individual(
    individual_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> IndividualResponse:
    """
    Retrieve an individual by ID.

    Args:
        individual_id: The individual ID
        service: OntologyService from dependency injection

    Returns:
        IndividualResponse

    Raises:
        HTTPException: 404 if not found
    """
    try:
        individual = await run_sync_in_executor(service.get_individual, individual_id)
        return IndividualResponse.model_validate(individual)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/individuals/{individual_id}", response_model=IndividualResponse)
async def update_individual(
    individual_id: str,
    request: IndividualUpdateRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> IndividualResponse:
    """
    Update an individual's title and/or description.

    Note: class membership changes use dedicated endpoints; this endpoint is for data updates only.

    Args:
        individual_id: The individual ID
        request: IndividualUpdateRequest with optional fields to update
        service: OntologyService from dependency injection

    Returns:
        Updated IndividualResponse

    Raises:
        HTTPException: 400 if invalid, 404 if not found, 409 if title exists
    """
    try:
        individual = await run_sync_in_executor(
            service.update_individual,
            individual_id,
            request.title,
            request.description,
        )
        return IndividualResponse.model_validate(individual)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/individuals/{individual_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_individual(
    individual_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> None:
    """
    Delete an individual.

    Args:
        individual_id: The individual ID
        service: OntologyService from dependency injection

    Raises:
        HTTPException: 404 if not found
    """
    try:
        await run_sync_in_executor(service.delete_individual, individual_id)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post(
    "/individuals/{individual_id}/classes",
    response_model=IndividualResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_parent_class_to_individual(
    individual_id: str,
    request: IndividualClassRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> IndividualResponse:
    """
    Add a parent class to an individual (appended to the end of the class list).

    Args:
        individual_id: The individual ID
        request: IndividualClassRequest with class_id to add
        service: OntologyService from dependency injection

    Returns:
        Updated IndividualResponse

    Raises:
        HTTPException: 400 if class already a parent, 404 if individual or class not found
    """
    try:
        individual = await run_sync_in_executor(
            service.add_class_to_individual,
            individual_id,
            request.class_id,
        )
        return IndividualResponse.model_validate(individual)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete(
    "/individuals/{individual_id}/classes/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_parent_class_from_individual(
    individual_id: str,
    class_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> None:
    """
    Remove a parent class from an individual.

    Args:
        individual_id: The individual ID
        class_id: The class ID to remove
        service: OntologyService from dependency injection

    Raises:
        HTTPException: 400 if class not a parent or is last parent, 404 if individual not found
    """
    try:
        await run_sync_in_executor(
            service.remove_class_from_individual,
            individual_id,
            class_id,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/individuals/{individual_id}/classes", response_model=IndividualResponse)
async def reorder_individual_classes(
    individual_id: str,
    request: IndividualClassListRequest,
    service: OntologyService = Depends(get_ontology_service),
) -> IndividualResponse:
    """
    Reorder or replace the full ordered class list for an individual.

    The order matters for property attribute inheritance: when two parent Classes
    declare a property with the same name but conflicting type/constraints, the
    first parent (by class membership order) wins.

    Args:
        individual_id: The individual ID
        request: IndividualClassListRequest with ordered class_ids (full replacement)
        service: OntologyService from dependency injection

    Returns:
        Updated IndividualResponse

    Raises:
        HTTPException: 404 if individual not found, 422 if class list is invalid
    """
    try:
        individual = await run_sync_in_executor(
            service.reorder_individual_classes,
            individual_id,
            request.class_ids,
        )
        return IndividualResponse.model_validate(individual)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get(
    "/individuals/{individual_id}/inherited-properties",
    response_model=ListResponse[DataPropertyValueResponse],
)
async def get_individual_inherited_properties(
    individual_id: str,
    service: OntologyService = Depends(get_ontology_service),
) -> ListResponse[DataPropertyValueResponse]:
    """
    Get the deduplicated property attribute list for an individual.

    Returns the superset of data_properties declared on all parent Classes,
    with first-class-wins precedence on name collisions: when two parent Classes
    declare a property with the same name but conflicting type/constraints,
    the property from the first parent (by class membership order) wins.

    Args:
        individual_id: The individual ID
        service: OntologyService from dependency injection

    Returns:
        ListResponse containing deduplicated properties

    Raises:
        HTTPException: 404 if individual not found
    """
    try:
        properties = await run_sync_in_executor(
            service.get_individual_properties,
            individual_id,
        )
        return ListResponse(
            items=[DataPropertyValueResponse.model_validate(p) for p in properties],
            total=len(properties),
            limit=1000,
            offset=0,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
