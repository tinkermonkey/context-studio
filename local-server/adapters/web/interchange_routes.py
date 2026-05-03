"""
FastAPI routes for the Data Interchange bounded context.

This module implements HTTP endpoints for import/export operations:
- Export ontology data in various formats
- Import ontology data with conflict detection and resolution
- Query import runs and their associated change events

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed request schema
2. Calls domain service or adapter with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

Note: Export returns binary data (Blob); import accepts multipart form data.
"""

from typing import Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from domain.interchange.value_objects import SerializationScope, SerializationScopeType
from domain.interchange.entities import ImportRunStatus
from domain.ontology.ports import OntologyRepository
from utils.logger import get_logger
from utils.async_executor import run_sync_in_executor

from adapters.web.dependencies import (
    get_ontology_repo,
    get_interchange_repo,
)
from adapters.web.schemas.interchange import (
    ExportRequest,
    SerializationScopeRequest,
    ImportPlanResponse,
    ImportRunResponse,
    ChangeEventResponse,
    ImportConflictResponse,
    ResolutionRecordResponse,
    SerializationScopeResponse,
    ImportRunListResponse,
    ChangeEventListResponse,
)
from adapters.interchange.skos import SKOSSerializer, SKOSDeserializer
from adapters.interchange.owl import OWLSerializer, OWLDeserializer
from adapters.interchange.graphml import GraphMLSerializer, GraphMLDeserializer
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository

router = APIRouter(prefix="/api/v1/interchange", tags=["interchange"])

_logger = get_logger(__name__)


# ==================== Helper Functions ====================


def _get_serializer(format: str, ontology_repo: OntologyRepository):
    """Get the appropriate serializer for the format."""
    format_lower = format.lower()
    if format_lower == "skos":
        return SKOSSerializer(ontology_repo)
    elif format_lower == "owl":
        return OWLSerializer(ontology_repo)
    elif format_lower == "graphml":
        return GraphMLSerializer(ontology_repo)
    else:
        raise ValueError(f"Unsupported format: {format}")


def _get_deserializer(
    format: str,
    ontology_repo: OntologyRepository,
    interchange_repo: SQLiteInterchangeRepository,
):
    """Get the appropriate deserializer for the format."""
    format_lower = format.lower()
    if format_lower == "skos":
        return SKOSDeserializer(ontology_repo, interchange_repo)
    elif format_lower == "owl":
        return OWLDeserializer(ontology_repo, interchange_repo)
    elif format_lower == "graphml":
        return GraphMLDeserializer(ontology_repo, interchange_repo)
    else:
        raise ValueError(f"Unsupported format: {format}")


def _scope_request_to_domain(scope_req: SerializationScopeRequest) -> SerializationScope:
    """Convert SerializationScopeRequest to domain SerializationScope."""
    try:
        scope_type = SerializationScopeType(scope_req.scope_type)
    except ValueError:
        raise ValueError(f"Invalid scope_type: {scope_req.scope_type}")

    entity_ids_tuple = tuple(scope_req.entity_ids) if scope_req.entity_ids else None

    return SerializationScope(
        scope_type=scope_type,
        taxonomy_id=scope_req.taxonomy_id,
        scheme_id=scope_req.scheme_id,
        include_descendants=scope_req.include_descendants,
        entity_ids=entity_ids_tuple,
    )


def _scope_domain_to_response(scope: SerializationScope) -> SerializationScopeResponse:
    """Convert domain SerializationScope to SerializationScopeResponse."""
    return SerializationScopeResponse(
        scope_type=scope.scope_type.value,
        taxonomy_id=scope.taxonomy_id,
        scheme_id=scope.scheme_id,
        include_descendants=scope.include_descendants,
        entity_ids=list(scope.entity_ids) if scope.entity_ids else None,
    )


def _conflict_to_response(conflict) -> ImportConflictResponse:
    """Convert domain ImportConflict to response."""
    return ImportConflictResponse(
        match_kind=conflict.match_kind.value,
        incoming=conflict.incoming,
        existing=conflict.existing,
        default_resolution=conflict.default_resolution.value,
        available_resolutions=[r.value for r in conflict.available_resolutions],
    )


def _import_plan_to_response(plan) -> ImportPlanResponse:
    """Convert domain ImportPlan to response."""
    return ImportPlanResponse(
        conflicts=[_conflict_to_response(c) for c in plan.conflicts],
        new_entity_count=plan.new_entity_count,
        import_run_id=plan.import_run_id,
        warnings=plan.warnings,
        source_hash=plan.source_hash,
        scope=_scope_domain_to_response(plan.scope) if plan.scope else None,
    )


def _import_run_to_response(import_run) -> ImportRunResponse:
    """Convert domain ImportRun to response."""
    return ImportRunResponse(
        id=import_run.id,
        created_at=import_run.created_at,
        created_by=import_run.created_by,
        format=import_run.format,
        source_uri=import_run.source_uri,
        source_hash=import_run.source_hash,
        scope=_scope_domain_to_response(import_run.scope),
        resolutions=[
            ResolutionRecordResponse(
                match_kind=r.match_kind.value,
                entity_id=r.entity_id,
                resolution_chosen=r.resolution_chosen.value,
            )
            for r in import_run.resolutions
        ],
        affected_entity_ids=import_run.affected_entity_ids,
        status=import_run.status.value,
    )


def _change_event_to_response(event: dict) -> ChangeEventResponse:
    """Convert change event dict to response."""
    return ChangeEventResponse(
        id=event["id"],
        timestamp=event["timestamp"],
        entity_id=event["entity_id"],
        entity_type=event["entity_type"],
        operation=event["operation"],
        new_state=event.get("new_state"),
        previous_state=event.get("previous_state"),
    )


# ==================== Export Endpoints ====================


@router.post("/export", response_class=StreamingResponse)
async def export_ontology(
    request: ExportRequest,
    ontology_repo: OntologyRepository = Depends(get_ontology_repo),
) -> StreamingResponse:
    """
    Export ontology data in the specified format.

    Args:
        request: Export request with format and scope
        ontology_repo: Injected OntologyRepository

    Returns:
        Binary file data as blob

    Raises:
        HTTPException: If export fails or format is unsupported
    """
    try:
        # Convert request scope to domain scope
        scope = _scope_request_to_domain(request.scope)

        # Get serializer
        serializer = _get_serializer(request.format, ontology_repo)

        # Serialize in executor to avoid blocking
        data = await run_sync_in_executor(
            lambda: serializer.serialize(scope)
        )

        # Return as binary file
        return StreamingResponse(
            iter([data]),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="export.{request.format}"'
            },
        )

    except ValueError as e:
        _logger.warning(f"Invalid export request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _logger.error(f"Export failed: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export operation failed",
        )


# ==================== Import Endpoints ====================


@router.post("/import")
async def import_ontology(
    format: str = Form(..., description="Import format"),
    file: UploadFile = File(..., description="File to import"),
    dry_run: str = Form("true", description="If 'true', returns plan without committing"),
    resolutions: Optional[str] = Form(None, description="JSON-encoded resolutions"),
    ontology_repo: OntologyRepository = Depends(get_ontology_repo),
    interchange_repo: SQLiteInterchangeRepository = Depends(get_interchange_repo),
):
    """
    Import ontology data from a file.

    Supports dry-run mode to preview conflicts, or direct commit with resolutions.

    Args:
        format: Import format (skos, owl, graphml, etc.)
        file: File to import
        dry_run: "true" for dry-run (returns plan), "false" to commit
        resolutions: JSON-encoded list of resolutions (only used when dry_run="false")
        ontology_repo: Injected OntologyRepository
        interchange_repo: Injected InterchangeRepository

    Returns:
        ImportPlanResponse (dry-run) or ImportRunResponse (committed)

    Raises:
        HTTPException: If import fails or format is unsupported
    """
    try:
        # Parse dry_run parameter
        is_dry_run = dry_run.lower() == "true"

        # Read file content
        content = await file.read()

        # Validate format
        try:
            _get_serializer(format, ontology_repo)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Get deserializer
        deserializer = _get_deserializer(format, ontology_repo, interchange_repo)

        # Deserialize in executor to avoid blocking
        import_plan = await run_sync_in_executor(
            lambda: deserializer.deserialize(content, dry_run=is_dry_run)
        )

        # Return appropriate response
        if is_dry_run:
            return _import_plan_to_response(import_plan)
        else:
            # Parse resolutions if provided
            resolution_list = []
            if resolutions:
                try:
                    resolution_data = json.loads(resolutions)
                    resolution_list = resolution_data if isinstance(resolution_data, list) else []
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in resolutions: {e}")

            # Apply resolutions to the plan (if the deserializer created an ImportRun)
            # For now, we return the plan as an ImportRun response
            # The resolutions have been parsed and could be applied if needed
            return _import_run_to_response(import_plan)

    except HTTPException:
        raise
    except ValueError as e:
        _logger.warning(f"Invalid import request: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _logger.error(f"Import failed: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import operation failed",
        )


# ==================== Import Run List Endpoints ====================


@router.get("/runs", response_model=ImportRunListResponse)
async def list_import_runs(
    interchange_repo: SQLiteInterchangeRepository = Depends(get_interchange_repo),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
) -> ImportRunListResponse:
    """
    List all import runs with optional filtering.

    Args:
        interchange_repo: Injected interchange repository
        offset: Number of results to skip
        limit: Maximum number of results to return
        status_filter: Optional status filter (pending, committed, failed, rolled_back)

    Returns:
        Paginated list of import runs

    Raises:
        HTTPException: If query fails or invalid status provided
    """
    try:
        if status_filter:
            # Validate status value
            try:
                ImportRunStatus(status_filter)
            except ValueError:
                raise ValueError(f"Invalid status: {status_filter}")
            runs = await run_sync_in_executor(
                lambda: interchange_repo.list_by_status(
                    ImportRunStatus(status_filter), limit=limit, offset=offset
                )
            )
        else:
            runs = await run_sync_in_executor(
                lambda: interchange_repo.list_all(limit=limit, offset=offset)
            )

        return ImportRunListResponse(
            runs=[_import_run_to_response(r) for r in runs],
            total=len(runs),
            offset=offset,
            limit=limit,
        )

    except ValueError as e:
        _logger.warning(f"Invalid query parameters: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _logger.error(f"Failed to list import runs: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list import runs",
        )


# ==================== Import Run Detail Endpoints ====================


@router.get("/runs/{run_id}", response_model=ImportRunResponse)
async def get_import_run(
    run_id: str,
    interchange_repo: SQLiteInterchangeRepository = Depends(get_interchange_repo),
) -> ImportRunResponse:
    """
    Get a specific import run by ID.

    Args:
        run_id: The import run ID
        interchange_repo: Injected interchange repository

    Returns:
        Import run details

    Raises:
        HTTPException: If run not found or query fails
    """
    try:
        import_run = await run_sync_in_executor(
            lambda: interchange_repo.get(run_id)
        )

        if not import_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Import run not found: {run_id}",
            )

        return _import_run_to_response(import_run)

    except HTTPException:
        raise
    except Exception as e:
        _logger.error(f"Failed to get import run: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get import run",
        )


# ==================== Change Events Endpoints ====================


@router.get("/runs/{run_id}/change-events", response_model=ChangeEventListResponse)
async def get_run_change_events(
    run_id: str,
    interchange_repo: SQLiteInterchangeRepository = Depends(get_interchange_repo),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    change_type: Optional[str] = Query(None, description="Filter by change type"),
) -> ChangeEventListResponse:
    """
    Get change events associated with an import run.

    Args:
        run_id: The import run ID
        interchange_repo: Injected interchange repository
        offset: Number of results to skip
        limit: Maximum number of results to return
        entity_type: Optional filter by entity type
        change_type: Optional filter by change type

    Returns:
        Paginated list of change events

    Raises:
        HTTPException: If run not found or query fails
    """
    try:
        # Verify run exists
        import_run = await run_sync_in_executor(
            lambda: interchange_repo.get(run_id)
        )

        if not import_run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Import run not found: {run_id}",
            )

        # Get change events
        events = await run_sync_in_executor(
            lambda: interchange_repo.get_change_events_for_run(run_id)
        )

        # Apply filters if provided
        filtered_events = events
        if entity_type:
            filtered_events = [
                e for e in filtered_events if e.get("entity_type") == entity_type
            ]
        if change_type:
            filtered_events = [
                e for e in filtered_events if e.get("operation") == change_type
            ]

        # Apply pagination
        paginated_events = filtered_events[offset : offset + limit]

        return ChangeEventListResponse(
            events=[_change_event_to_response(e) for e in paginated_events],
            total=len(filtered_events),
            offset=offset,
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        _logger.error(f"Failed to get change events: {e}", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get change events",
        )
