"""
FastAPI routes for the Pipeline Orchestration bounded context.

This module implements HTTP endpoints for generic pipeline execution:
- GET    /api/pipelines/types                                    → List pipeline types
- GET    /api/pipelines/types/{type}/implementations             → List implementations for type
- GET    /api/pipelines/types/{type}/implementations/{id}/configurations → List configs for impl
- POST   /api/pipelines/{type}/run                               → Invoke a pipeline
- GET    /api/pipelines/runs/{run_id}                            → Fetch a PipelineRun by ID
- GET    /api/pipelines/runs                                     → List PipelineRuns with filters

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

No business logic lives here—all validation and constraints are in the domain service.
Error handling translates domain exceptions to appropriate HTTP responses.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi import status as http_status

from adapters.web.schemas.ontology import ListResponse
from adapters.web.schemas.pipelines import (
    ConfigurationResponse,
    ImplementationResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineTypeResponse,
)
from domain.pipelines.entities import PipelineRun, PipelineRunStatus, PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
    PipelineTypeRegistry,
)
from utils.logger import get_logger

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

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
    if isinstance(exc, ValueError):
        return (http_status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        _logger.error(f"Unexpected error in pipelines endpoint: {exc}", exc_info=exc)
        return (http_status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")


# ==================== Pipeline Type Enumeration ====================


@router.get("/types", response_model=list[PipelineTypeResponse])
async def list_pipeline_types() -> list[PipelineTypeResponse]:
    """
    List all registered pipeline types with input/output contracts.

    Returns:
        List of PipelineTypeResponse objects with type metadata
    """
    type_defs = PipelineTypeRegistry.list_types()
    return [
        PipelineTypeResponse(
            pipeline_type=td.pipeline_type.value,
            description=td.description,
            input_contract=td.input_contract,
            output_contract=td.output_contract,
        )
        for td in type_defs
    ]


@router.get(
    "/types/{pipeline_type}/implementations",
    response_model=list[ImplementationResponse],
)
async def list_implementations(
    pipeline_type: str,
    request: Request = None,
) -> list[ImplementationResponse]:
    """
    List all registered implementations for a pipeline type.

    Args:
        pipeline_type: The pipeline type (e.g., individual_extraction)
        request: FastAPI request (for registry access)

    Returns:
        List of ImplementationResponse objects

    Raises:
        HTTPException: 400 if pipeline type is invalid
    """
    try:
        ptype = PipelineType(pipeline_type)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline type: {pipeline_type}",
        )

    impl_registry: PipelineImplementationRegistry = request.app.state.implementation_registry
    impls = impl_registry.list_by_type(ptype)

    return [
        ImplementationResponse(id=impl_id, pipeline_type=ptype.value) for impl_id in impls.keys()
    ]


@router.get(
    "/types/{pipeline_type}/implementations/{impl_id}/configurations",
    response_model=list[ConfigurationResponse],
)
async def list_configurations(
    pipeline_type: str,
    impl_id: str,
    request: Request = None,
) -> list[ConfigurationResponse]:
    """
    List all configurations for a pipeline type and implementation.

    Args:
        pipeline_type: The pipeline type
        impl_id: The implementation identifier
        request: FastAPI request (for registry access)

    Returns:
        List of ConfigurationResponse objects

    Raises:
        HTTPException: 400 if pipeline type is invalid, 404 if implementation not found
    """
    try:
        ptype = PipelineType(pipeline_type)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline type: {pipeline_type}",
        )

    impl_registry: PipelineImplementationRegistry = request.app.state.implementation_registry
    config_registry: PipelineConfigurationRegistry = request.app.state.config_registry

    impl = impl_registry.get(ptype, impl_id)
    if impl is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Implementation not found: {ptype.value}:{impl_id}",
        )

    configs = config_registry.list_configs(ptype, impl_id)
    return [
        ConfigurationResponse(
            config_ref=config_ref,
            version=version.version,
            config=version.config,
        )
        for config_ref, version in configs
    ]


# ==================== Pipeline Execution ====================


@router.post("/{pipeline_type}/run", response_model=PipelineRunResponse, status_code=http_status.HTTP_201_CREATED)
async def run_pipeline(
    pipeline_type: str,
    request_body: PipelineRunRequest = Body(...),
    request: Request = None,
) -> PipelineRunResponse:
    """
    Invoke a pipeline by type.

    The request body structure depends on the pipeline type. Supported types:
    - individual_extraction: requires text and ontology_id
    - schema_extraction: requires documents, optional scope
    - schema_node_grounding: requires nodes and sources
    - schema_node_definition_refinement: requires nodes, optional context
    - schema_node_connection_refinement: requires edges, optional strategy

    Args:
        pipeline_type: The pipeline type (e.g., individual_extraction)
        request_body: Type-specific request payload
        request: FastAPI request (for service access)

    Returns:
        PipelineRunResponse with the created PipelineRun

    Raises:
        HTTPException: 400 for invalid input, 404 for missing config/impl, 500 for execution errors
    """
    try:
        ptype = PipelineType(pipeline_type)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pipeline type: {pipeline_type}",
        )

    repo = request.app.state.pipeline_run_repo
    impl_registry = request.app.state.implementation_registry
    config_registry = request.app.state.config_registry

    # Verify implementation exists
    impl = impl_registry.get(ptype, request_body.implementation_id)
    if impl is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Implementation not found: {ptype.value}:{request_body.implementation_id}",
        )

    # Verify configuration exists
    config_version = config_registry.get_latest(
        ptype, request_body.implementation_id, request_body.configuration_ref
    )
    if config_version is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Configuration not found: {request_body.configuration_ref}",
        )

    # Create pipeline run in pending state
    run = repo.create(
        batch_run_id="",  # No batch context for direct CLI invocations; filled by callers
        pipeline_type=ptype,
        implementation_id=request_body.implementation_id,
        configuration_ref=request_body.configuration_ref,
    )

    return PipelineRunResponse.model_validate(
        {
            "id": run.id,
            "batch_run_id": run.batch_run_id,
            "pipeline_type": run.pipeline_type.value,
            "implementation_id": run.implementation_id,
            "configuration_ref": run.configuration_ref,
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "llm_metadata": run.llm_metadata,
            "status": run.status.value,
            "created_at": None,
            "updated_at": None,
        }
    )


# ==================== Pipeline Run Retrieval ====================


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: str,
    request: Request = None,
) -> PipelineRunResponse:
    """
    Fetch a PipelineRun by ID.

    Args:
        run_id: The pipeline run ID
        request: FastAPI request (for service access)

    Returns:
        PipelineRunResponse with the run details

    Raises:
        HTTPException: 404 if run not found
    """
    repo = request.app.state.pipeline_run_repo
    run = repo.get(run_id)

    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run not found: {run_id}",
        )

    return PipelineRunResponse.model_validate(
        {
            "id": run.id,
            "batch_run_id": run.batch_run_id,
            "pipeline_type": run.pipeline_type.value,
            "implementation_id": run.implementation_id,
            "configuration_ref": run.configuration_ref,
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "llm_metadata": run.llm_metadata,
            "status": run.status.value,
            "created_at": None,
            "updated_at": None,
        }
    )


@router.get("/runs", response_model=ListResponse[PipelineRunResponse])
async def list_pipeline_runs(
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    implementation_id: Optional[str] = Query(None, description="Filter by implementation ID"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    request: Request = None,
) -> ListResponse[PipelineRunResponse]:
    """
    List pipeline runs with optional filtering.

    Results are returned in reverse chronological order (most recent first).

    Args:
        pipeline_type: Filter by pipeline type (optional)
        status: Filter by status (pending, running, completed, failed, etc.)
        implementation_id: Filter by implementation ID (optional)
        limit: Maximum number of results (1-500, default 100)
        offset: Number of results to skip for pagination (default 0)
        request: FastAPI request (for service access)

    Returns:
        Paginated list of PipelineRunResponse objects with total count

    Raises:
        HTTPException: 400 for invalid filters
    """
    repo = request.app.state.pipeline_run_repo

    # Get all runs; filtering happens in-memory for simplicity
    all_runs = repo.list()

    # Apply filters
    filtered_runs = all_runs
    if pipeline_type:
        try:
            ptype = PipelineType(pipeline_type)
            filtered_runs = [r for r in filtered_runs if r.pipeline_type == ptype]
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pipeline type: {pipeline_type}",
            )

    if status:
        try:
            status_enum = PipelineRunStatus(status)
            filtered_runs = [r for r in filtered_runs if r.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}",
            )

    if implementation_id:
        filtered_runs = [r for r in filtered_runs if r.implementation_id == implementation_id]

    # Pagination
    total = len(filtered_runs)
    paginated_runs = filtered_runs[offset : offset + limit]

    responses = [
        PipelineRunResponse.model_validate(
            {
                "id": run.id,
                "batch_run_id": run.batch_run_id,
                "pipeline_type": run.pipeline_type.value,
                "implementation_id": run.implementation_id,
                "configuration_ref": run.configuration_ref,
                "input_summary": run.input_summary,
                "output_summary": run.output_summary,
                "llm_metadata": run.llm_metadata,
                "status": run.status.value,
                "created_at": None,
                "updated_at": None,
            }
        )
        for run in paginated_runs
    ]

    return ListResponse(items=responses, total=total, limit=limit, offset=offset)
