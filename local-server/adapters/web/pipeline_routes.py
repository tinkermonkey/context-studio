"""
FastAPI routes for the LLM Pipeline Management bounded context.

This module implements HTTP endpoints for pipeline configuration and execution:
- POST   /api/pipelines              → Create pipeline configuration
- GET    /api/pipelines              → List all configurations
- GET    /api/pipelines/executions   → Retrieve all execution history (must be before /{id})
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

from typing import Optional, cast, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from domain.pipeline.services import PipelineService
from domain.pipeline.exceptions import (
    PipelineNotFoundError,
    PipelineError,
    LayerExecutionError,
)
from utils.logger import get_logger
from utils.async_executor import run_sync_in_executor

from adapters.web.dependencies import get_pipeline_service
from adapters.web.schemas.pipeline import (
    PipelineConfigurationCreate,
    PipelineConfigurationUpdate,
    PipelineConfigurationResponse,
    PipelineExecuteRequest,
    ExecutionResponse,
    ExecutionWithPipelineResponse,
)
from adapters.web.schemas.ontology import ListResponse

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


@router.get(
    "/pipelines/executions", response_model=ListResponse[ExecutionWithPipelineResponse]
)
async def list_all_pipeline_executions(
    status_filter: Optional[str] = Query(
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

    Raises:
        HTTPException: 400 if invalid status value
    """
    valid_statuses = {"success", "error", "timeout"}
    if status_filter is not None and status_filter not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: must be one of {valid_statuses}",
        )

    try:
        executions, pipeline_titles, total = await run_sync_in_executor(
            service.list_all_executions,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

        responses = [
            ExecutionWithPipelineResponse(
                id=exec.id,
                pipeline_config_id=exec.pipeline_config_id,
                pipeline_title=title,
                output_text=exec.output_text,
                provider=exec.provider,
                model=exec.model,
                tokens_in=exec.tokens_in,
                tokens_out=exec.tokens_out,
                duration_ms=exec.duration_ms,
                status=cast(Literal["success", "error", "timeout"], exec.status),
                error_message=exec.error_message,
                timestamp=exec.timestamp,
            )
            for exec, title in zip(executions, pipeline_titles)
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


@router.get(
    "/pipelines/{pipeline_id}/executions", response_model=list[ExecutionResponse]
)
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
        executions = await run_sync_in_executor(
            service.list_executions, pipeline_id, limit=50
        )
        return [ExecutionResponse.model_validate(e) for e in executions]
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
