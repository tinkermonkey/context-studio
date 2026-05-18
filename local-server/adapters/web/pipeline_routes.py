"""
FastAPI routes for the LLM Pipeline Management bounded context.

This module implements HTTP endpoints for pipeline configuration and execution:
- POST   /api/pipelines              → Create pipeline configuration
- GET    /api/pipelines              → List all configurations
- GET    /api/pipelines/executions   → Retrieve all execution history (must be before /{id})
- GET    /api/pipelines/flavors      → Retrieve all flavors (must be before /{id})
- POST   /api/pipelines/flavors      → Create flavor (must be before /{id})
- GET    /api/pipelines/flavors/{id} → Retrieve single flavor
- PUT    /api/pipelines/flavors/{id} → Update flavor
- DELETE /api/pipelines/flavors/{id} → Delete flavor
- GET    /api/pipelines/{id}         → Retrieve single configuration
- PUT    /api/pipelines/{id}         → Update configuration
- DELETE /api/pipelines/{id}         → Delete configuration
- POST   /api/pipelines/{id}/execute → Execute pipeline
- GET    /api/pipelines/{id}/executions → Retrieve execution history for pipeline

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

No business logic lives here—all validation and constraints are in the domain service.
Error handling translates domain exceptions to appropriate HTTP responses.
"""

from typing import Literal, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status

from adapters.web.dependencies import get_pipeline_service
from adapters.web.schemas.ontology import ListResponse
from adapters.web.schemas.pipeline import (
    ExecutionResponse,
    ExecutionWithPipelineResponse,
    PipelineConfigurationCreate,
    PipelineConfigurationResponse,
    PipelineConfigurationUpdate,
    PipelineExecuteRequest,
    PipelineFlavorCreateRequest,
    PipelineFlavorResponse,
    PipelineFlavorUpdateRequest,
)
from domain.pipeline.entities import PipelineFlavor
from domain.pipeline.exceptions import (
    LayerExecutionError,
    PipelineError,
    PipelineNotFoundError,
)
from domain.pipeline.services import PipelineService
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["pipeline"])

_logger = get_logger(__name__)


# ==================== Error Handler Utilities ====================


def _handle_domain_error(exc: Exception) -> tuple[int, str]:
    """
    Map domain exceptions to HTTP status codes and error messages.

    Handles domain-level exceptions (PipelineError and subclasses) by mapping them to
    appropriate HTTP status codes. Unexpected exceptions (ValueError, TypeError, etc.)
    are logged as server errors with full context to aid in debugging.

    Exception Ordering:
        LayerExecutionError MUST be checked before PipelineError. Since LayerExecutionError
        is a subclass of PipelineError, checking PipelineError first would incorrectly
        return HTTP 400 instead of HTTP 500. The order is: PipelineNotFoundError →
        LayerExecutionError → PipelineError → other exceptions.

    Args:
        exc: The domain exception

    Returns:
        Tuple of (status_code, error_message)
    """
    if isinstance(exc, PipelineNotFoundError):
        return (status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, LayerExecutionError):
        _logger.error(f"Pipeline layer execution error: {exc}", exc_info=exc)
        return (
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Pipeline layer failed to execute",
        )
    elif isinstance(exc, PipelineError):
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        # All unexpected exceptions are server errors—log with full context
        _logger.error(f"Unexpected error in pipeline endpoint: {exc}", exc_info=exc)
        return (status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")


# ==================== Pipeline Configuration Endpoints ====================


@router.post(
    "/pipelines",
    response_model=PipelineConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pipeline_configuration(
    request: PipelineConfigurationCreate,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineConfigurationResponse:
    """
    Create a new pipeline configuration.

    Args:
        request: PipelineConfigurationCreate with configuration details
        service: PipelineService from dependency injection

    Returns:
        Created PipelineConfigurationResponse with server-generated id

    Raises:
        HTTPException: 400 if invalid input, 500 for internal errors
    """
    try:
        config = await run_sync_in_executor(
            service.create_config,
            pipeline=request.pipeline,
            title=request.title,
            provider=request.provider,
            model=request.model,
            config=request.config,
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            enabled=request.enabled,
        )
        return PipelineConfigurationResponse.model_validate(config)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/pipelines", response_model=list[PipelineConfigurationResponse])
async def list_pipeline_configurations(
    service: PipelineService = Depends(get_pipeline_service),
) -> list[PipelineConfigurationResponse]:
    """
    Retrieve all pipeline configurations.

    Returns:
        List of PipelineConfigurationResponse objects
    """
    try:
        configs = await run_sync_in_executor(service.list_configs)
        return [PipelineConfigurationResponse.model_validate(c) for c in configs]
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/pipelines/executions", response_model=ListResponse[ExecutionWithPipelineResponse])
async def list_all_pipeline_executions(
    status_filter: Optional[Literal["success", "error", "timeout"]] = Query(
        None, description="Optional status filter (success, error, timeout)"
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: PipelineService = Depends(get_pipeline_service),
) -> ListResponse[ExecutionWithPipelineResponse]:
    """
    Retrieve execution history across all pipeline configurations.

    Results are returned in reverse chronological order (most recent first).

    Args:
        status_filter: Optional status filter ("success", "error", "timeout")
        limit: Maximum number of executions to return (1-500, default 100)
        offset: Number of executions to skip for pagination (default 0)
        service: PipelineService from dependency injection

    Returns:
        Paginated list of ExecutionWithPipelineResponse objects with total count

    """
    try:
        executions_with_titles, total = await run_sync_in_executor(
            service.list_all_executions,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

        responses = [
            ExecutionWithPipelineResponse(
                id=item.execution.id,
                pipeline_config_id=item.execution.pipeline_config_id,
                pipeline_title=item.pipeline_title,
                output_text=item.execution.output_text,
                provider=item.execution.provider,
                model=item.execution.model,
                tokens_in=item.execution.tokens_in,
                tokens_out=item.execution.tokens_out,
                duration_ms=item.execution.duration_ms,
                status=cast(Literal["success", "error", "timeout"], item.execution.status),
                error_message=item.execution.error_message,
                timestamp=item.execution.timestamp,
            )
            for item in executions_with_titles
        ]

        return ListResponse(
            items=responses,
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Pipeline Flavor Endpoints ====================


@router.post(
    "/pipelines/flavors",
    response_model=PipelineFlavorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pipeline_flavor(
    request: PipelineFlavorCreateRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineFlavorResponse:
    """
    Create a new pipeline flavor.

    Args:
        request: PipelineFlavorCreateRequest with flavor details
        service: PipelineService from dependency injection

    Returns:
        Created PipelineFlavorResponse with server-generated id

    Raises:
        HTTPException: 400 if invalid input, 409 if name already exists
    """
    try:
        flavor = await run_sync_in_executor(
            service.create_flavor,
            name=request.name,
            description=request.description,
            steps=request.steps,
        )
        return _flavor_to_response(flavor)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/pipelines/flavors", response_model=list[PipelineFlavorResponse])
async def list_pipeline_flavors(
    service: PipelineService = Depends(get_pipeline_service),
) -> list[PipelineFlavorResponse]:
    """
    Retrieve all pipeline flavors.

    Returns:
        List of PipelineFlavorResponse objects
    """
    try:
        flavors = await run_sync_in_executor(service.list_flavors)
        return [_flavor_to_response(f) for f in flavors]
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/pipelines/flavors/{flavor_id}", response_model=PipelineFlavorResponse)
async def get_pipeline_flavor(
    flavor_id: str,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineFlavorResponse:
    """
    Retrieve a pipeline flavor by ID.

    Args:
        flavor_id: The pipeline flavor ID
        service: PipelineService from dependency injection

    Returns:
        PipelineFlavorResponse

    Raises:
        HTTPException: 404 if not found
    """
    try:
        flavor = await run_sync_in_executor(service.get_flavor, flavor_id)
        return _flavor_to_response(flavor)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/pipelines/flavors/{flavor_id}", response_model=PipelineFlavorResponse)
async def update_pipeline_flavor(
    flavor_id: str,
    request: PipelineFlavorUpdateRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineFlavorResponse:
    """
    Update a pipeline flavor.

    Args:
        flavor_id: The pipeline flavor ID
        request: PipelineFlavorUpdateRequest with optional fields to update
        service: PipelineService from dependency injection

    Returns:
        Updated PipelineFlavorResponse

    Raises:
        HTTPException: 400 if invalid, 404 if not found
    """
    try:
        flavor = await run_sync_in_executor(
            service.update_flavor,
            flavor_id=flavor_id,
            name=request.name,
            description=request.description,
            steps=request.steps,
        )
        return _flavor_to_response(flavor)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/pipelines/flavors/{flavor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_flavor(
    flavor_id: str,
    service: PipelineService = Depends(get_pipeline_service),
) -> None:
    """
    Delete a pipeline flavor.

    Args:
        flavor_id: The pipeline flavor ID
        service: PipelineService from dependency injection

    Raises:
        HTTPException: 404 if not found
    """
    try:
        await run_sync_in_executor(service.delete_flavor, flavor_id)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Pipeline Configuration Endpoints ====================


@router.get("/pipelines/{pipeline_id}", response_model=PipelineConfigurationResponse)
async def get_pipeline_configuration(
    pipeline_id: str,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineConfigurationResponse:
    """
    Retrieve a pipeline configuration by ID.

    Args:
        pipeline_id: The pipeline configuration ID
        service: PipelineService from dependency injection

    Returns:
        PipelineConfigurationResponse

    Raises:
        HTTPException: 404 if not found
    """
    try:
        config = await run_sync_in_executor(service.get_config, pipeline_id)
        return PipelineConfigurationResponse.model_validate(config)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.put("/pipelines/{pipeline_id}", response_model=PipelineConfigurationResponse)
async def update_pipeline_configuration(
    pipeline_id: str,
    request: PipelineConfigurationUpdate,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineConfigurationResponse:
    """
    Update a pipeline configuration's properties.

    Args:
        pipeline_id: The pipeline configuration ID
        request: PipelineConfigurationUpdate with optional fields to update
        service: PipelineService from dependency injection

    Returns:
        Updated PipelineConfigurationResponse

    Raises:
        HTTPException: 400 if invalid, 404 if not found
    """
    try:
        config = await run_sync_in_executor(
            service.update_config,
            config_id=pipeline_id,
            title=request.title,
            provider=request.provider,
            model=request.model,
            config=request.config,
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            enabled=request.enabled,
        )
        return PipelineConfigurationResponse.model_validate(config)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.delete("/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_configuration(
    pipeline_id: str,
    service: PipelineService = Depends(get_pipeline_service),
) -> None:
    """
    Delete a pipeline configuration.

    Args:
        pipeline_id: The pipeline configuration ID
        service: PipelineService from dependency injection

    Raises:
        HTTPException: 404 if not found
    """
    try:
        await run_sync_in_executor(service.delete_config, pipeline_id)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Pipeline Execution Endpoints ====================


@router.post("/pipelines/{pipeline_id}/execute", response_model=ExecutionResponse)
async def execute_pipeline(
    pipeline_id: str,
    request: PipelineExecuteRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> ExecutionResponse:
    """
    Execute a pipeline configuration with the given input.

    Args:
        pipeline_id: The pipeline configuration ID
        request: PipelineExecuteRequest with input_text
        service: PipelineService from dependency injection

    Returns:
        ExecutionResponse with output, tokens, duration, and status

    Raises:
        HTTPException: 400 if invalid, 404 if configuration not found
    """
    try:
        execution = await run_sync_in_executor(
            service.execute_pipeline,
            config_id=pipeline_id,
            input_text=request.input_text,
        )
        return ExecutionResponse.model_validate(execution)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/pipelines/{pipeline_id}/executions", response_model=list[ExecutionResponse])
async def get_pipeline_executions(
    pipeline_id: str,
    service: PipelineService = Depends(get_pipeline_service),
) -> list[ExecutionResponse]:
    """
    Retrieve execution history for a pipeline configuration.

    Results are returned in reverse chronological order (most recent first).

    Args:
        pipeline_id: The pipeline configuration ID
        service: PipelineService from dependency injection

    Returns:
        List of ExecutionResponse objects, up to 50 most recent

    Raises:
        HTTPException: 404 if configuration not found
    """
    try:
        executions = await run_sync_in_executor(service.list_executions, pipeline_id, limit=50)
        return [ExecutionResponse.model_validate(e) for e in executions]
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


def _flavor_to_response(flavor: PipelineFlavor) -> PipelineFlavorResponse:
    """Convert domain PipelineFlavor to response schema."""
    return PipelineFlavorResponse.model_validate(
        {
            "id": flavor.id,
            "name": flavor.name,
            "description": flavor.description,
            "steps": flavor.steps,
            "step_count": flavor.step_count,
            "created_at": flavor.created_at,
            "last_updated": flavor.last_updated,
        }
    )
