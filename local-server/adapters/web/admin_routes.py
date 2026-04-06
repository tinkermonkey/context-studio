"""
HTTP route handlers for the System Administration bounded context.

Endpoints:
- GET  /api/v1/admin/health                 - Check system health
- GET  /api/v1/admin/health/database        - Get database component health
- GET  /api/v1/admin/health/services        - Get service-level metrics
- GET  /api/v1/admin/health/embedding       - Get embedding model component status
- GET  /api/v1/admin/health/nlp             - Get NLP pipeline component status
- GET  /api/v1/admin/health/tasks           - Get background task summary
- GET  /api/v1/admin/configuration          - Retrieve configuration
- PATCH /api/v1/admin/configuration/{section} - Update configuration section
- POST /api/v1/admin/configuration/reset    - Reset configuration to defaults
- GET  /api/v1/admin/tasks                  - List background tasks
- GET  /api/v1/admin/tasks/{task_id}        - Get background task details

All route handlers use run_sync_in_executor to prevent blocking the async event loop
when calling synchronous domain service methods.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from domain.admin.services import AdminService
from domain.admin.exceptions import ConfigurationError, TaskNotFoundError, AdminError
from adapters.web.dependencies import get_admin_service
from adapters.web.schemas.admin import (
    SystemHealthResponse,
    DatabaseHealthResponse,
    ServiceMetricsResponse,
    ComponentStatusResponse,
    BackgroundTaskSummaryResponse,
    AppConfigurationResponse,
    ConfigSectionUpdateRequest,
    BackgroundTaskResponse,
)
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _handle_admin_error(exc: Exception) -> tuple[int, str]:
    """
    Map admin domain exceptions to HTTP status codes and error messages.

    Args:
        exc: The domain exception

    Returns:
        Tuple of (status_code, error_message)
    """
    if isinstance(exc, ConfigurationError):
        logger.warning(f"Configuration error: {exc}")
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    elif isinstance(exc, TaskNotFoundError):
        logger.warning(f"Task not found: {exc}")
        return (status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, AdminError):
        logger.warning(f"Admin error: {exc}")
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        logger.error(f"Unexpected error in admin endpoint: {exc}", exc_info=exc)
        return (status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")


@router.get("/health", response_model=SystemHealthResponse)
async def check_health(
    service: AdminService = Depends(get_admin_service),
) -> SystemHealthResponse:
    """
    Check system health and component readiness.

    Returns the overall system health status along with the readiness of optional
    components (NLP pipeline, embedding model, LLM providers).

    Health status rules:
    - "healthy": All systems operational
    - "degraded": One or more issues detected (e.g., missing LLM providers, unavailable
      components, failed background tasks) but core systems functional
    - "unhealthy": Critical systems (database) unavailable

    Returns:
        SystemHealthResponse with status and component readiness

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        health = await run_sync_in_executor(service.check_health)
        return SystemHealthResponse.model_validate(health)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def get_database_health(
    service: AdminService = Depends(get_admin_service),
) -> DatabaseHealthResponse:
    """
    Get database component health status.

    Returns detailed health information about the database connection and any issues.

    Returns:
        DatabaseHealthResponse with connectivity status and issues list

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        db_health = await run_sync_in_executor(service.get_database_health)
        return DatabaseHealthResponse.model_validate(db_health)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/services", response_model=ServiceMetricsResponse)
async def get_service_metrics(
    service: AdminService = Depends(get_admin_service),
) -> ServiceMetricsResponse:
    """
    Get service-level metrics.

    Returns system uptime and list of available LLM providers.

    Returns:
        ServiceMetricsResponse with uptime and available providers

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        metrics = await run_sync_in_executor(service.get_service_metrics)
        return ServiceMetricsResponse.model_validate(metrics)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/embedding", response_model=ComponentStatusResponse)
async def get_embedding_status(
    service: AdminService = Depends(get_admin_service),
) -> ComponentStatusResponse:
    """
    Get embedding model component status.

    Returns availability and status details for the embedding model.

    Returns:
        ComponentStatusResponse with availability and details

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        component_status = await run_sync_in_executor(service.get_embedding_model_status)
        return ComponentStatusResponse.model_validate(component_status)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/nlp", response_model=ComponentStatusResponse)
async def get_nlp_status(
    service: AdminService = Depends(get_admin_service),
) -> ComponentStatusResponse:
    """
    Get NLP pipeline component status.

    Returns availability and status details for the NLP pipeline.

    Returns:
        ComponentStatusResponse with availability and details

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        component_status = await run_sync_in_executor(service.get_nlp_pipeline_status)
        return ComponentStatusResponse.model_validate(component_status)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/health/tasks", response_model=BackgroundTaskSummaryResponse)
async def get_task_summary(
    service: AdminService = Depends(get_admin_service),
) -> BackgroundTaskSummaryResponse:
    """
    Get summary of background task execution status.

    Returns counts of tasks grouped by status (pending, running, completed, failed).

    Returns:
        BackgroundTaskSummaryResponse with task counts by status

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        summary = await run_sync_in_executor(service.get_background_task_summary)
        return BackgroundTaskSummaryResponse.from_domain(summary)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/configuration", response_model=AppConfigurationResponse)
async def get_configuration(
    service: AdminService = Depends(get_admin_service),
) -> AppConfigurationResponse:
    """
    Retrieve current application configuration.

    Returns all configuration sections with sensitive values (API keys)
    masked in the API response to prevent exposure through the HTTP interface.

    Returns:
        AppConfigurationResponse with configuration sections and masked API keys

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        config = await run_sync_in_executor(service.get_configuration)
        return AppConfigurationResponse.from_domain(config)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.patch(
    "/configuration/{section}",
    response_model=AppConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
async def update_configuration(
    section: str,
    request: ConfigSectionUpdateRequest,
    service: AdminService = Depends(get_admin_service),
) -> AppConfigurationResponse:
    """
    Update a configuration section.

    Loads the current configuration, updates the specified section with new values,
    and persists the changes. Returns the updated configuration with masked API keys.

    Args:
        section: Name of the configuration section to update (e.g., "llm", "server")
        request: ConfigSectionUpdateRequest with key-value pairs to update
        service: Injected AdminService

    Returns:
        AppConfigurationResponse with updated configuration and masked API keys

    Raises:
        HTTPException 400: If the section does not exist
    """
    try:
        config = await run_sync_in_executor(
            service.update_configuration, section, request.updates
        )
        return AppConfigurationResponse.from_domain(config)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/configuration/reset", response_model=AppConfigurationResponse)
async def reset_configuration(
    service: AdminService = Depends(get_admin_service),
) -> AppConfigurationResponse:
    """
    Reset configuration to defaults while preserving credentials.

    Resets all configuration values to their defaults. Credential fields
    (API keys, secrets) are preserved. Returns configuration with masked credentials.

    Returns:
        AppConfigurationResponse with reset configuration and masked credentials

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        config = await run_sync_in_executor(service.reset_configuration)
        return AppConfigurationResponse.from_domain(config)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/tasks", response_model=list[BackgroundTaskResponse])
async def list_tasks(
    service: AdminService = Depends(get_admin_service),
) -> list[BackgroundTaskResponse]:
    """
    List all background tasks.

    Returns metadata and status for all registered background tasks,
    whether pending, running, completed, or failed.

    Returns:
        List of BackgroundTaskResponse objects

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        tasks = await run_sync_in_executor(service.list_tasks)
        return [BackgroundTaskResponse.model_validate(task) for task in tasks]
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/tasks/{task_id}", response_model=BackgroundTaskResponse)
async def get_task(
    task_id: str,
    service: AdminService = Depends(get_admin_service),
) -> BackgroundTaskResponse:
    """
    Retrieve background task details by ID.

    Returns metadata and current status for a specific background task.

    Args:
        task_id: Unique identifier of the task
        service: Injected AdminService

    Returns:
        BackgroundTaskResponse with task details and status

    Raises:
        HTTPException 404: If task_id does not exist
    """
    try:
        task = await run_sync_in_executor(service.get_task, task_id)
        return BackgroundTaskResponse.model_validate(task)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
