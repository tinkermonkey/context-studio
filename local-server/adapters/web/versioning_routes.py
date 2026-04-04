"""
FastAPI routes for the Version Control & Collaboration bounded context.

This module implements HTTP endpoints for:
- Change history queries
- Changeset lifecycle management (create, stage, submit)
- Proposal workflow (approve, reject, merge)
- Conflict detection and resolution
- Remote synchronization (push, pull, status)

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

All service calls are wrapped in run_sync_in_executor() since services are synchronous.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from domain.versioning.services import VersioningService
from domain.versioning.exceptions import VersionNotFoundError, ChangesetStateError, ConflictResolutionError
from utils.logger import get_logger
from utils.async_executor import run_sync_in_executor

from adapters.web.dependencies import get_versioning_service
from adapters.web.schemas.versioning import (
    ChangesetCreateRequest,
    ChangesetResponse,
    ChangeHistoryResponse,
    ChangeEventResponse,
    EntityVersionResponse,
    ProposalResponse,
    RejectProposalRequest,
    ConflictReportResponse,
    ConflictResponse,
    ResolveConflictsRequest,
    MergeResultResponse,
    SyncStatusResponse,
    SyncResultResponse,
)

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
    if isinstance(exc, VersionNotFoundError):
        return (status.HTTP_404_NOT_FOUND, str(exc))
    elif isinstance(exc, ChangesetStateError):
        return (status.HTTP_409_CONFLICT, str(exc))
    elif isinstance(exc, ConflictResolutionError):
        return (status.HTTP_409_CONFLICT, str(exc))
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
            events=[ChangeEventResponse.model_validate(e) for e in result.events],
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
            events=[ChangeEventResponse.model_validate(e) for e in result.events],
            total=result.total,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/versioning/versions/{entity_id}", response_model=list[EntityVersionResponse])
async def list_versions(
    entity_id: str,
    service: VersioningService = Depends(get_versioning_service),
) -> list[EntityVersionResponse]:
    """
    List all versions of an entity.

    Args:
        entity_id: ID of the entity
        service: VersioningService from dependency injection

    Returns:
        List of entity versions

    Raises:
        HTTPException: 500 for internal errors
    """
    try:
        versions = await run_sync_in_executor(service.list_versions, entity_id)
        return [EntityVersionResponse.model_validate(v) for v in versions]
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/versioning/versions/{entity_id}/{version}", response_model=EntityVersionResponse)
async def get_entity_version(
    entity_id: str,
    version: int,
    service: VersioningService = Depends(get_versioning_service),
) -> EntityVersionResponse:
    """
    Get a specific version of an entity.

    Args:
        entity_id: ID of the entity
        version: Version number
        service: VersioningService from dependency injection

    Returns:
        The specific entity version

    Raises:
        HTTPException: 404 if version not found, 500 for internal errors
    """
    try:
        entity_version = await run_sync_in_executor(
            service.get_entity_version, entity_id, version
        )
        return EntityVersionResponse.model_validate(entity_version)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Changeset Endpoints ====================


@router.post("/versioning/changesets", response_model=ChangesetResponse, status_code=status.HTTP_201_CREATED)
async def create_changeset(
    request: ChangesetCreateRequest,
    service: VersioningService = Depends(get_versioning_service),
) -> ChangesetResponse:
    """
    Create a new changeset.

    Args:
        request: ChangesetCreateRequest with changeset details
        service: VersioningService from dependency injection

    Returns:
        Created ChangesetResponse with server-generated id

    Raises:
        HTTPException: 400 for invalid input, 500 for internal errors
    """
    try:
        changeset = await run_sync_in_executor(
            service.create_changeset,
            name=request.name,
            description=request.description,
            event_ids=request.event_ids,
        )
        return ChangesetResponse.model_validate(changeset)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/versioning/changesets/{changeset_id}", response_model=ChangesetResponse)
async def get_changeset(
    changeset_id: str,
    service: VersioningService = Depends(get_versioning_service),
) -> ChangesetResponse:
    """
    Retrieve a changeset by ID.

    Args:
        changeset_id: ID of the changeset
        service: VersioningService from dependency injection

    Returns:
        ChangesetResponse

    Raises:
        HTTPException: 404 if not found, 500 for internal errors
    """
    try:
        changeset = await run_sync_in_executor(service.get_changeset, changeset_id)
        return ChangesetResponse.model_validate(changeset)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/versioning/changesets/{changeset_id}/stage", response_model=ChangesetResponse)
async def stage_changeset(
    changeset_id: str,
    service: VersioningService = Depends(get_versioning_service),
) -> ChangesetResponse:
    """
    Transition a changeset from WORKING to STAGED.

    Args:
        changeset_id: ID of the changeset to stage
        service: VersioningService from dependency injection

    Returns:
        Updated ChangesetResponse in STAGED state

    Raises:
        HTTPException: 404 if not found, 409 for invalid state, 500 for internal errors
    """
    try:
        changeset = await run_sync_in_executor(service.stage_changeset, changeset_id)
        return ChangesetResponse.model_validate(changeset)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/versioning/changesets/{changeset_id}/submit", response_model=ProposalResponse)
async def submit_proposal(
    changeset_id: str,
    service: VersioningService = Depends(get_versioning_service),
) -> ProposalResponse:
    """
    Submit a changeset as a proposal for review.

    Transitions the changeset from STAGED to PROPOSED and creates a Proposal in 'open' state.

    Args:
        changeset_id: ID of the changeset to propose
        service: VersioningService from dependency injection

    Returns:
        Created ProposalResponse

    Raises:
        HTTPException: 404 if not found, 409 for invalid state, 500 for internal errors
    """
    try:
        proposal = await run_sync_in_executor(service.submit_proposal, changeset_id)
        return ProposalResponse.model_validate(proposal)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


# ==================== Proposal Workflow Endpoints ====================


@router.post("/versioning/proposals/{proposal_id}/approve", response_model=ProposalResponse)
async def approve_proposal(
    proposal_id: str,
    service: VersioningService = Depends(get_versioning_service),
) -> ProposalResponse:
    """
    Approve a proposal.

    Transitions the linked changeset from PROPOSED to APPROVED
    and updates the proposal state to 'approved'.

    Args:
        proposal_id: ID of the proposal to approve
        service: VersioningService from dependency injection

    Returns:
        Updated ProposalResponse in 'approved' state

    Raises:
        HTTPException: 404 if not found, 409 for invalid state, 500 for internal errors
    """
    try:
        proposal = await run_sync_in_executor(service.approve_proposal, proposal_id)
        return ProposalResponse.model_validate(proposal)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/versioning/proposals/{proposal_id}/reject", response_model=ProposalResponse)
async def reject_proposal(
    proposal_id: str,
    request: RejectProposalRequest,
    service: VersioningService = Depends(get_versioning_service),
) -> ProposalResponse:
    """
    Reject a proposal.

    Transitions the linked changeset back to WORKING state,
    records the rejection reason, and updates the proposal state to 'rejected'.

    Args:
        proposal_id: ID of the proposal to reject
        request: RejectProposalRequest with rejection reason
        service: VersioningService from dependency injection

    Returns:
        Updated ProposalResponse in 'rejected' state

    Raises:
        HTTPException: 404 if not found, 409 for invalid state, 500 for internal errors
    """
    try:
        proposal = await run_sync_in_executor(
            service.reject_proposal, proposal_id, request.reason
        )
        return ProposalResponse.model_validate(proposal)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.get("/versioning/proposals/{proposal_id}/conflicts", response_model=ConflictReportResponse)
async def detect_conflicts(
    proposal_id: str,
    service: VersioningService = Depends(get_versioning_service),
) -> ConflictReportResponse:
    """
    Detect field-level conflicts in a proposal.

    Compares change events in the changeset to identify conflicts.

    Args:
        proposal_id: ID of the proposal to check for conflicts
        service: VersioningService from dependency injection

    Returns:
        ConflictReportResponse with detected conflicts

    Raises:
        HTTPException: 404 if not found, 500 for internal errors
    """
    try:
        report = await run_sync_in_executor(service.detect_conflicts, proposal_id)
        return ConflictReportResponse(
            proposal_id=proposal_id,
            conflicts=[
                ConflictResponse(
                    entity_id=c.entity_id,
                    field_name=c.field_name,
                    base_value=c.base_value,
                    incoming_value=c.incoming_value,
                )
                for c in report.conflicts
            ],
            has_conflicts=report.has_conflicts,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/versioning/proposals/{proposal_id}/resolve", response_model=ConflictReportResponse)
async def resolve_conflicts(
    proposal_id: str,
    request: ResolveConflictsRequest,
    service: VersioningService = Depends(get_versioning_service),
) -> ConflictReportResponse:
    """
    Manually resolve conflicts in a proposal.

    Detects conflicts, applies the provided resolutions, and validates that
    all conflicts are covered.

    Args:
        proposal_id: ID of the proposal to resolve conflicts for
        request: ResolveConflictsRequest with conflict resolutions
        service: VersioningService from dependency injection

    Returns:
        ConflictReportResponse with all conflicts marked as resolved

    Raises:
        HTTPException: 404 if not found, 409 if unresolved conflicts remain, 500 for internal errors
    """
    try:
        report = await run_sync_in_executor(
            service.resolve_conflicts, proposal_id, request.resolutions
        )
        return ConflictReportResponse(
            proposal_id=proposal_id,
            conflicts=[
                ConflictResponse(
                    entity_id=c.entity_id,
                    field_name=c.field_name,
                    base_value=c.base_value,
                    incoming_value=c.incoming_value,
                )
                for c in report.conflicts
            ],
            has_conflicts=report.has_conflicts,
        )
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/versioning/proposals/{proposal_id}/merge", response_model=MergeResultResponse)
async def merge_proposal(
    proposal_id: str,
    service: VersioningService = Depends(get_versioning_service),
) -> MergeResultResponse:
    """
    Merge an approved proposal.

    Detects conflicts using any stored resolutions, and blocks the merge
    if unresolved conflicts exist. Transitions the changeset from APPROVED
    to MERGED.

    Args:
        proposal_id: ID of the proposal to merge
        service: VersioningService from dependency injection

    Returns:
        MergeResultResponse with details of the merge operation

    Raises:
        HTTPException: 404 if not found, 409 for invalid state or unresolved conflicts, 500 for internal errors
    """
    try:
        result = await run_sync_in_executor(service.merge_proposal, proposal_id)
        return MergeResultResponse.model_validate(result)
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
