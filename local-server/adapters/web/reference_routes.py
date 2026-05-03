"""
FastAPI routes for Reference Sources API.

This module implements HTTP endpoints for querying external reference sources:
- GET /api/reference/status — Check availability of reference sources
- POST /api/reference/search — Search references across sources
- POST /api/reference/relations — Get relationships for a reference URI

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls reference sources with aggregation
3. Handles source-level failures gracefully
4. Returns response schema serialized as JSON

No business logic lives here—coordination of multiple sources is handled
by a simple aggregation pattern.
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from adapters.web.dependencies import get_reference_sources
from adapters.web.schemas.reference import (
    ReferenceSearchRequest,
    ReferenceRelationsRequest,
    ReferenceSearchResponseSchema,
    ReferenceRelationsResponseSchema,
    ReferenceStatusResponseSchema,
    ReferenceSourceStatusSchema,
    ReferenceResultSchema,
    ReferenceRelationSchema,
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
