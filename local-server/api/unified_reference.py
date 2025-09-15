"""FastAPI router for unified reference endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

from enrichment.unified.models import (
    UnifiedSearchRequest, UnifiedSearchResponse,
    UnifiedLinksRequest, UnifiedLinksResponse,
    UnifiedNode, ReferenceSource
)
from enrichment.unified.service import UnifiedReferenceService
from enrichment.exceptions import EnrichmentError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reference/unified", tags=["unified-reference"])

# Initialize unified service (singleton pattern)
_unified_service = None

def get_unified_service() -> UnifiedReferenceService:
    """Get unified reference service instance"""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedReferenceService()
    return _unified_service

def handle_service_error(e: Exception) -> HTTPException:
    """Convert service errors to appropriate HTTP exceptions"""
    if isinstance(e, EnrichmentError):
        return HTTPException(status_code=400, detail=str(e))
    else:
        logger.error(f"Unexpected error in unified reference: {e}")
        return HTTPException(status_code=500, detail="Internal server error")

@router.post("/search", response_model=UnifiedSearchResponse)
async def search(request: UnifiedSearchRequest):
    """
    Unified search across all reference sources

    Searches across multiple reference sources (ConceptNet, DBpedia, Wikidata,
    Schema.org, WordNet) and returns deduplicated, ranked results.

    Args:
        request: Search request with query and parameters

    Returns:
        Unified search response with ranked results
    """
    try:
        service = get_unified_service()
        response = await service.search(request)
        return response
    except Exception as e:
        raise handle_service_error(e)

@router.get("/search", response_model=UnifiedSearchResponse)
async def search_get(
    query: str = Query(..., description="Search query", min_length=1),
    search_type: str = Query("title", description="Search type", regex="^(title|definition|predicate)$"),
    sources: Optional[str] = Query(None, description="Comma-separated list of sources"),
    limit: int = Query(20, description="Maximum results", ge=1, le=100),
    offset: int = Query(0, description="Result offset", ge=0)
):
    """
    Unified search via GET request

    Alternative GET endpoint for unified search with query parameters.
    """
    try:
        # Parse sources parameter
        source_list = None
        if sources:
            source_names = [s.strip() for s in sources.split(',')]
            source_list = []
            for name in source_names:
                try:
                    source_list.append(ReferenceSource(name))
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid source: {name}")

        # Create request object
        request = UnifiedSearchRequest(
            query=query,
            search_type=search_type,
            sources=source_list,
            limit=limit,
            offset=offset
        )

        service = get_unified_service()
        response = await service.search(request)
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise handle_service_error(e)

@router.get("/node/{node_id}", response_model=UnifiedNode)
async def get_node(
    node_id: str = Path(..., description="Unified node ID")
):
    """
    Get details for a specific node

    Args:
        node_id: Unified node identifier

    Returns:
        Node details

    Raises:
        404: If node not found
    """
    try:
        service = get_unified_service()
        node = await service.get_node(node_id)

        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        return node

    except HTTPException:
        raise
    except Exception as e:
        raise handle_service_error(e)

@router.post("/links", response_model=UnifiedLinksResponse)
async def get_links(request: UnifiedLinksRequest):
    """
    Get links for a specific node

    Retrieves semantic relationships and links for a given node across
    all available reference sources.

    Args:
        request: Links request with node ID and parameters

    Returns:
        Links response with related nodes and relationships
    """
    try:
        service = get_unified_service()
        response = await service.get_links(request)
        return response
    except Exception as e:
        raise handle_service_error(e)

@router.get("/links", response_model=UnifiedLinksResponse)
async def get_links_get(
    node_id: str = Query(..., description="Node ID to get links for"),
    direction: str = Query("both", description="Link direction", regex="^(from|to|both)$"),
    sources: Optional[str] = Query(None, description="Comma-separated list of sources"),
    limit: int = Query(50, description="Maximum links", ge=1, le=200)
):
    """
    Get links via GET request

    Alternative GET endpoint for retrieving node links with query parameters.
    """
    try:
        # Parse sources parameter
        source_list = None
        if sources:
            source_names = [s.strip() for s in sources.split(',')]
            source_list = []
            for name in source_names:
                try:
                    source_list.append(ReferenceSource(name))
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid source: {name}")

        # Create request object
        request = UnifiedLinksRequest(
            node_id=node_id,
            direction=direction,
            sources=source_list,
            limit=limit
        )

        service = get_unified_service()
        response = await service.get_links(request)
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise handle_service_error(e)

@router.get("/sources")
async def get_available_sources():
    """
    Get list of available reference sources

    Returns:
        List of source identifiers and their availability status
    """
    try:
        service = get_unified_service()
        health = await service.get_health()

        sources = []
        for source in ReferenceSource:
            source_info = {
                "id": source.value,
                "name": source.value.replace('_', ' ').title(),
                "available": source.value in health.get("sources", {}),
                "status": health.get("sources", {}).get(source.value, "unknown")
            }
            sources.append(source_info)

        return {"sources": sources}

    except Exception as e:
        logger.error(f"Failed to get available sources: {e}")
        return {"sources": [], "error": str(e)}

@router.get("/health")
async def health_check():
    """
    Check health status of unified reference service

    Returns:
        Health status including source availability and circuit breaker states
    """
    try:
        service = get_unified_service()
        health = await service.get_health()
        return health

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "overall": "unhealthy",
                "error": str(e),
                "timestamp": None
            }
        )

@router.get("/stats")
async def get_stats():
    """
    Get service statistics

    Returns:
        Service statistics including cache performance and circuit breaker states
    """
    try:
        service = get_unified_service()
        stats = await service.get_stats()
        return stats

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"error": str(e)}

@router.post("/cache/clear")
async def clear_cache():
    """
    Clear the unified reference cache

    Clears both memory and database cache tiers.

    Returns:
        Success status
    """
    try:
        service = get_unified_service()
        await service.cache_manager.clear()
        return {"status": "success", "message": "Cache cleared"}

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics

    Returns:
        Cache performance metrics and statistics
    """
    try:
        service = get_unified_service()
        stats = await service.cache_manager.get_stats()
        return stats

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {"error": str(e)}