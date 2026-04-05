"""
HTTP route handlers for the System Administration bounded context.

Endpoints:
- GET  /api/v1/admin/health          - Check system health
- GET  /api/v1/admin/configuration   - Retrieve configuration
- PATCH /api/v1/admin/configuration/{section} - Update configuration section
- GET  /api/v1/admin/tasks           - List background tasks
- GET  /api/v1/admin/tasks/{task_id} - Get background task details

All route handlers use run_sync_in_executor to prevent blocking the async event loop
when calling synchronous domain service methods.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from domain.admin.services import AdminService
from domain.admin.exceptions import ConfigurationError, TaskNotFoundError, AdminError
from adapters.web.dependencies import get_admin_service
from adapters.web.schemas.admin import (
    SystemHealthResponse,
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
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    elif isinstance(exc, TaskNotFoundError):
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
    - "healthy": All core systems operational
    - "degraded": Optional components unavailable but system functional
    - "unhealthy": Critical systems (database) unavailable

    Returns:
        SystemHealthResponse with status and component readiness

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        health = await run_sync_in_executor(service.check_health)
        return SystemHealthResponse.model_validate(health.__dict__)
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
    masked to prevent exposure in logs.

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
        return [BackgroundTaskResponse.model_validate(task.__dict__) for task in tasks]
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
        return BackgroundTaskResponse.model_validate(task.__dict__)
    except Exception as exc:
        status_code, message = _handle_admin_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
