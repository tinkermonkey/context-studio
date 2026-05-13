"""
FastAPI routes for Reference Sources API.

This module implements HTTP endpoints for querying external reference sources:
- GET /api/reference/status — Check availability of reference sources
- POST /api/reference/search — Search references across sources
- POST /api/reference/relations — Get relationships for a reference URI
- GET /api/reference/grounding-workflows — List grounding workflows
- GET /api/reference/grounding-workflows/{id} — Get a grounding workflow
- POST /api/reference/grounding-workflows — Create a grounding workflow
- PUT /api/reference/grounding-workflows/{id} — Update a grounding workflow
- DELETE /api/reference/grounding-workflows/{id} — Delete a grounding workflow
- POST /api/reference/grounding-workflows/{id}/run — Trigger a workflow run
- GET /api/reference/grounding-workflows/{id}/runs — List runs for a workflow

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls reference sources with aggregation
3. Handles source-level failures gracefully
4. Returns response schema serialized as JSON

No business logic lives here—coordination of multiple sources is handled
by a simple aggregation pattern.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from adapters.persistence.sqlite.models import GroundingWorkflow, WorkflowRun
from adapters.web.dependencies import get_local_db_session, get_reference_sources
from adapters.web.schemas.reference import (
    GroundingWorkflowCreate,
    GroundingWorkflowResponse,
    GroundingWorkflowUpdate,
    ReferenceSearchRequest,
    ReferenceRelationsRequest,
    ReferenceSearchResponseSchema,
    ReferenceRelationsResponseSchema,
    ReferenceStatusResponseSchema,
    ReferenceSourceStatusSchema,
    ReferenceResultSchema,
    ReferenceRelationSchema,
    WorkflowRunResponse,
)
from domain.extraction.ports import ReferenceSource
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/reference", tags=["reference"])


# ==================== Status Endpoint ====================


@router.get(
    "/status",
    response_model=ReferenceStatusResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def reference_status(
    sources: list[ReferenceSource] = Depends(get_reference_sources),
) -> ReferenceStatusResponseSchema:
    """
    Check availability of all reference sources.

    Returns:
        ReferenceStatusResponseSchema with status of each source

    Raises:
        HTTPException: 500 if no sources are configured
    """
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No reference sources configured",
        )

    source_statuses = []
    available_count = 0

    # Use async availability checks in parallel
    async def check_source(
        source: ReferenceSource,
    ) -> tuple[ReferenceSourceStatusSchema, bool]:
        try:
            is_available = await source.is_available_async()

            return (
                ReferenceSourceStatusSchema(
                    name=source.source_name,
                    available=is_available,
                    last_checked=datetime.now(timezone.utc).isoformat(),
                ),
                is_available,
            )
        except Exception as e:
            logger.warning(f"Error checking availability of {source.source_name}: {e}")
            return (
                ReferenceSourceStatusSchema(
                    name=source.source_name,
                    available=False,
                    last_checked=datetime.now(timezone.utc).isoformat(),
                ),
                False,
            )

    # Run all checks concurrently
    results = await asyncio.gather(*[check_source(s) for s in sources])

    for status_schema, is_available in results:
        source_statuses.append(status_schema)
        if is_available:
            available_count += 1

    return ReferenceStatusResponseSchema(
        sources=source_statuses,
        sources_available=available_count,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ==================== Search Endpoint ====================


@router.post(
    "/search",
    response_model=ReferenceSearchResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def search_references(
    request: ReferenceSearchRequest,
    sources: list[ReferenceSource] = Depends(get_reference_sources),
) -> ReferenceSearchResponseSchema:
    """
    Search for references across multiple sources.

    Aggregates results from all available sources (or specified sources).
    Sources that fail or are unavailable are tracked but don't block the response.

    Args:
        request: ReferenceSearchRequest with search parameters
        sources: List of reference sources from dependency injection

    Returns:
        ReferenceSearchResponseSchema with aggregated results from all sources

    Raises:
        HTTPException: 400 if search term is invalid, 500 if no sources configured
    """
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No reference sources configured",
        )

    # Filter sources if specific ones were requested
    sources_to_query = sources
    if request.sources:
        sources_to_query = [s for s in sources if s.source_name in request.sources]
        if not sources_to_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"None of the requested sources are available: {request.sources}",
            )

    async def search_single_source(
        source: ReferenceSource,
    ) -> tuple[list[ReferenceResultSchema], str, bool]:
        """Search a single source and return results or error."""
        try:
            is_available = await source.is_available_async()

            if not is_available:
                return [], source.source_name, False

            source_results = await source.search_async(
                request.term, limit=request.limit
            )

            results = [
                ReferenceResultSchema(
                    uri=result.uri,
                    label=result.label,
                    description=result.description,
                    confidence=result.confidence,
                    source=result.source,
                )
                for result in source_results
            ]
            return results, source.source_name, True
        except Exception as e:
            logger.error(
                f"Error searching {source.source_name} for '{request.term}': {e}"
            )
            return [], source.source_name, False

    # Run all searches concurrently
    search_results = await asyncio.gather(
        *[search_single_source(s) for s in sources_to_query]
    )

    results = []
    sources_searched = []
    sources_failed = []

    for source_results, source_name, success in search_results:
        if success:
            sources_searched.append(source_name)
            results.extend(source_results)
        else:
            sources_failed.append(source_name)

    return ReferenceSearchResponseSchema(
        term=request.term,
        results=results,
        sources_searched=sources_searched,
        sources_failed=sources_failed,
        total_results=len(results),
    )


# ==================== Relations Endpoint ====================


@router.post(
    "/relations",
    response_model=ReferenceRelationsResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def get_reference_relations(
    request: ReferenceRelationsRequest,
    sources: list[ReferenceSource] = Depends(get_reference_sources),
) -> ReferenceRelationsResponseSchema:
    """
    Get relationships for a reference URI across multiple sources.

    Aggregates relationships from all available sources (or specified sources).
    Sources that fail or are unavailable are tracked but don't block the response.

    Args:
        request: ReferenceRelationsRequest with URI to query
        sources: List of reference sources from dependency injection

    Returns:
        ReferenceRelationsResponseSchema with aggregated relationships

    Raises:
        HTTPException: 400 if URI is invalid, 500 if no sources configured
    """
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No reference sources configured",
        )

    # Filter sources if specific ones were requested
    sources_to_query = sources
    if request.sources:
        sources_to_query = [s for s in sources if s.source_name in request.sources]
        if not sources_to_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"None of the requested sources are available: {request.sources}",
            )

    async def get_relations_from_source(
        source: ReferenceSource,
    ) -> tuple[list[ReferenceRelationSchema], str, bool]:
        """Get relations from a single source."""
        try:
            is_available = await source.is_available_async()

            if not is_available:
                return [], source.source_name, False

            source_relations = await source.get_relations_async(
                request.uri, limit=request.limit
            )

            relations = [
                ReferenceRelationSchema(
                    subject_uri=relation.subject_uri,
                    predicate=relation.predicate,
                    object_uri=relation.object_uri,
                    weight=relation.weight,
                    source=relation.source,
                )
                for relation in source_relations
            ]
            return relations, source.source_name, True
        except Exception as e:
            logger.error(
                f"Error getting relations from {source.source_name} for '{request.uri}': {e}"
            )
            return [], source.source_name, False

    # Run all relation queries concurrently
    relation_results = await asyncio.gather(
        *[get_relations_from_source(s) for s in sources_to_query]
    )

    relations = []
    sources_queried = []
    sources_failed = []

    for source_relations, source_name, success in relation_results:
        if success:
            sources_queried.append(source_name)
            relations.extend(source_relations)
        else:
            sources_failed.append(source_name)

    return ReferenceRelationsResponseSchema(
        uri=request.uri,
        relations=relations,
        sources_queried=sources_queried,
        sources_failed=sources_failed,
        total_relations=len(relations),
    )


# ==================== Grounding Workflow Endpoints ====================


def _workflow_to_response(workflow: GroundingWorkflow) -> GroundingWorkflowResponse:
    """Convert a GroundingWorkflow ORM model to a response schema."""
    return GroundingWorkflowResponse(
        id=cast(str, workflow.id),
        title=cast(str, workflow.title),
        description=cast(str | None, workflow.description),
        source=cast(str, workflow.source),
        class_scope=cast(list[str], workflow.class_scope or []),
        status=cast(str, workflow.status),
        last_run=cast(str | None, workflow.last_run.isoformat() if workflow.last_run else None),
        last_run_record_count=cast(int | None, workflow.last_run_record_count),
    )


def _run_to_response(run: WorkflowRun) -> WorkflowRunResponse:
    """Convert a WorkflowRun ORM model to a response schema."""
    return WorkflowRunResponse(
        id=cast(str, run.id),
        workflow_id=cast(str, run.workflow_id),
        status=cast(str, run.status),
        record_count=cast(int, run.record_count),
        timestamp=cast(str, run.timestamp.isoformat()),
        error_message=cast(str | None, run.error_message),
    )


@router.get(
    "/grounding-workflows",
    response_model=list[GroundingWorkflowResponse],
    status_code=status.HTTP_200_OK,
)
async def list_grounding_workflows(
    db: Session = Depends(get_local_db_session),
) -> list[GroundingWorkflowResponse]:
    """
    List all grounding workflows.

    Returns:
        List of GroundingWorkflowResponse objects
    """
    workflows = db.query(GroundingWorkflow).order_by(GroundingWorkflow.created_at).all()
    return [_workflow_to_response(w) for w in workflows]


@router.get(
    "/grounding-workflows/{workflow_id}",
    response_model=GroundingWorkflowResponse,
    status_code=status.HTTP_200_OK,
)
async def get_grounding_workflow(
    workflow_id: str,
    db: Session = Depends(get_local_db_session),
) -> GroundingWorkflowResponse:
    """
    Get a single grounding workflow by ID.

    Args:
        workflow_id: UUID of the workflow

    Returns:
        GroundingWorkflowResponse

    Raises:
        HTTPException: 404 if workflow not found
    """
    workflow = db.query(GroundingWorkflow).filter(
        GroundingWorkflow.id == workflow_id
    ).first()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grounding workflow '{workflow_id}' not found",
        )
    return _workflow_to_response(workflow)


@router.post(
    "/grounding-workflows",
    response_model=GroundingWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_grounding_workflow(
    request: GroundingWorkflowCreate,
    db: Session = Depends(get_local_db_session),
) -> GroundingWorkflowResponse:
    """
    Create a new grounding workflow.

    Args:
        request: GroundingWorkflowCreate with workflow details

    Returns:
        GroundingWorkflowResponse for the created workflow
    """
    workflow = GroundingWorkflow(
        id=str(uuid.uuid4()),
        title=request.title,
        description=request.description,
        source=request.source,
        class_scope=request.class_scope,
        status="inactive",
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return _workflow_to_response(workflow)


@router.put(
    "/grounding-workflows/{workflow_id}",
    response_model=GroundingWorkflowResponse,
    status_code=status.HTTP_200_OK,
)
async def update_grounding_workflow(
    workflow_id: str,
    request: GroundingWorkflowUpdate,
    db: Session = Depends(get_local_db_session),
) -> GroundingWorkflowResponse:
    """
    Update an existing grounding workflow.

    Args:
        workflow_id: UUID of the workflow to update
        request: GroundingWorkflowUpdate with fields to update

    Returns:
        Updated GroundingWorkflowResponse

    Raises:
        HTTPException: 404 if workflow not found
    """
    workflow = db.query(GroundingWorkflow).filter(
        GroundingWorkflow.id == workflow_id
    ).first()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grounding workflow '{workflow_id}' not found",
        )

    if request.title is not None:
        workflow.title = request.title
    if request.description is not None:
        workflow.description = request.description
    if request.source is not None:
        workflow.source = request.source
    if request.class_scope is not None:
        workflow.class_scope = request.class_scope
    if request.status is not None:
        workflow.status = request.status

    workflow.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(workflow)
    return _workflow_to_response(workflow)


@router.delete(
    "/grounding-workflows/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_grounding_workflow(
    workflow_id: str,
    db: Session = Depends(get_local_db_session),
) -> None:
    """
    Delete a grounding workflow and all its runs.

    Args:
        workflow_id: UUID of the workflow to delete

    Raises:
        HTTPException: 404 if workflow not found
    """
    workflow = db.query(GroundingWorkflow).filter(
        GroundingWorkflow.id == workflow_id
    ).first()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grounding workflow '{workflow_id}' not found",
        )
    db.delete(workflow)
    db.commit()


@router.post(
    "/grounding-workflows/{workflow_id}/run",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_grounding_workflow(
    workflow_id: str,
    db: Session = Depends(get_local_db_session),
) -> WorkflowRunResponse:
    """
    Trigger a grounding workflow run.

    Creates a WorkflowRun record with status 'running' and returns it immediately.
    Actual enrichment execution is out of scope for the current implementation.

    Args:
        workflow_id: UUID of the workflow to run

    Returns:
        WorkflowRunResponse with status 'running'

    Raises:
        HTTPException: 404 if workflow not found
    """
    workflow = db.query(GroundingWorkflow).filter(
        GroundingWorkflow.id == workflow_id
    ).first()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grounding workflow '{workflow_id}' not found",
        )

    run = WorkflowRun(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        status="running",
        record_count=0,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(run)

    # Update last_run on the workflow
    workflow.last_run = run.timestamp
    workflow.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(run)
    return _run_to_response(run)


@router.get(
    "/grounding-workflows/{workflow_id}/runs",
    response_model=list[WorkflowRunResponse],
    status_code=status.HTTP_200_OK,
)
async def list_workflow_runs(
    workflow_id: str,
    db: Session = Depends(get_local_db_session),
) -> list[WorkflowRunResponse]:
    """
    List all runs for a grounding workflow.

    Args:
        workflow_id: UUID of the workflow

    Returns:
        List of WorkflowRunResponse objects ordered by timestamp descending

    Raises:
        HTTPException: 404 if workflow not found
    """
    workflow = db.query(GroundingWorkflow).filter(
        GroundingWorkflow.id == workflow_id
    ).first()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grounding workflow '{workflow_id}' not found",
        )

    runs = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.timestamp.desc())  # type: ignore[attr-defined]
        .all()
    )
    return [_run_to_response(r) for r in runs]
