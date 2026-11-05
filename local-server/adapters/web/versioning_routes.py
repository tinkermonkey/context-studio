"""
FastAPI routes for the Version Control & Collaboration bounded context.

This module implements HTTP endpoints for:
- Change history queries
- Remote synchronization (push, pull, status)

Reviewing and applying changes is handled by the change proposal routes
(proposals_routes.py).

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

All service calls are wrapped in run_sync_in_executor() since services are synchronous.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from adapters.web.dependencies import get_versioning_service
from adapters.web.schemas.versioning import (
    ChangeHistoryResponse,
    SyncResultResponse,
    SyncStatusResponse,
    VersioningChangeEventResponse,
)
from domain.versioning.exceptions import SyncError
from domain.versioning.services import VersioningService
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

router = APIRouter(prefix="/api/v1", tags=["versioning"])

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
    if isinstance(exc, SyncError):
        _logger.error(f"Sync operation failed: {exc}", exc_info=exc)
        return (status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))
    else:
        _logger.error(f"Unexpected error in versioning endpoint: {exc}", exc_info=exc)
        return (status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")


# ==================== Change History Endpoints ====================


@router.get("/versioning/changes", response_model=ChangeHistoryResponse)
async def get_change_history_all(
    service: VersioningService = Depends(get_versioning_service),
    limit: int = 100,
) -> ChangeHistoryResponse:
    """
    Get all change history events.

    Args:
        service: VersioningService from dependency injection
        limit: Maximum number of results to return

    Returns:
        ChangeHistoryResponse with all changes

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        result = await run_sync_in_executor(service.get_change_history, limit=limit)
        return ChangeHistoryResponse(
            events=[VersioningChangeEventResponse.model_validate(e) for e in result.events],
            total=result.total,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/versioning/changes/{entity_id}", response_model=ChangeHistoryResponse)
async def get_change_history_by_entity(
    entity_id: str,
    service: VersioningService = Depends(get_versioning_service),
    limit: int = 100,
) -> ChangeHistoryResponse:
    """
    Get change history for a specific entity.

    Args:
        entity_id: ID of the entity to get changes for
        service: VersioningService from dependency injection
        limit: Maximum number of results to return

    Returns:
        ChangeHistoryResponse with filtered changes

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        result = await run_sync_in_executor(
            service.get_change_history, entity_id=entity_id, limit=limit
        )
        return ChangeHistoryResponse(
            events=[VersioningChangeEventResponse.model_validate(e) for e in result.events],
            total=result.total,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Sync Endpoints ====================


@router.get("/versioning/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    service: VersioningService = Depends(get_versioning_service),
) -> SyncStatusResponse:
    """
    Get the current synchronization status.

    Returns information about unprocessed changes and sync configuration.

    Args:
        service: VersioningService from dependency injection

    Returns:
        SyncStatusResponse with sync status

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        sync_status = await run_sync_in_executor(service.get_sync_status)
        return SyncStatusResponse.model_validate(sync_status)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/versioning/sync/push", response_model=SyncResultResponse)
async def push_changes(
    service: VersioningService = Depends(get_versioning_service),
) -> SyncResultResponse:
    """
    Push local unprocessed changes to the remote sync target.

    Args:
        service: VersioningService from dependency injection

    Returns:
        SyncResultResponse with push results

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        result = await run_sync_in_executor(service.push_changes)
        return SyncResultResponse.model_validate(result)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/versioning/sync/pull", response_model=SyncResultResponse)
async def pull_changes(
    service: VersioningService = Depends(get_versioning_service),
) -> SyncResultResponse:
    """
    Pull remote changes and record them locally.

    Args:
        service: VersioningService from dependency injection

    Returns:
        SyncResultResponse with pull results

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        result = await run_sync_in_executor(service.pull_changes)
        return SyncResultResponse.model_validate(result)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
