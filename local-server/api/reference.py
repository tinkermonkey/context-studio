"""FastAPI router for reference endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
from typing import Optional, Literal
import logging

from api.dependencies.reference_services import get_reference_service
from reference.service import ReferenceService
from reference.models import (
    DBpediaResourceRequest, DBpediaSearchRequest, DBpediaSparqlRequest, ConceptNetQueryRequest,
    WikidataSparqlRequest, WikidataEntityRequest, WikidataSearchRequest, SchemaOrgEntityRequest,
    SchemaOrgPropertyRequest, SchemaOrgSearchRequest, ResponseFormat, SourceType, MultiSourceSearchRequest,
    MultiSourceSearchResponse
)
from reference.exceptions import ReferenceError, SourceError, SourceTimeoutError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reference", tags=["reference"])


def handle_service_error(e: Exception) -> HTTPException:
    """Convert service errors to appropriate HTTP exceptions"""
    if isinstance(e, SourceTimeoutError):
        return HTTPException(status_code=504, detail=str(e))
    elif isinstance(e, SourceError):
        return HTTPException(status_code=503, detail=str(e))
    elif isinstance(e, ReferenceError):
        return HTTPException(status_code=400, detail=str(e))
    else:
        logger.error(f"Unexpected error: {e}")
        return HTTPException(status_code=500, detail="Internal server error")


# DBpedia endpoints
@router.get("/dbpedia/resource", response_model=MultiSourceSearchResponse)
async def dbpedia_get_resource(
    resource_url: str = Query(..., description="DBpedia resource URL"),
    format: ResponseFormat = Query(ResponseFormat.JSON, description="Response format"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Retrieve structured data from a DBpedia resource URL"""
    try:
        request = DBpediaResourceRequest(resource_url=resource_url, format=format)
        return await service.dbpedia_get_resource(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/dbpedia/search", response_model=MultiSourceSearchResponse)
async def dbpedia_search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    format: ResponseFormat = Query(ResponseFormat.JSON, description="Response format"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Search DBpedia using the search API"""
    try:
        request = DBpediaSearchRequest(query=query, limit=limit, offset=offset, format=format)
        return await service.dbpedia_search(request)
    except Exception as e:
        raise handle_service_error(e)


@router.post("/dbpedia/sparql", response_model=MultiSourceSearchResponse)
async def dbpedia_sparql(
    request: DBpediaSparqlRequest,
    service: ReferenceService = Depends(get_reference_service)
):
    """Execute SPARQL query against DBpedia"""
    try:
        return await service.dbpedia_sparql(request)
    except Exception as e:
        raise handle_service_error(e)


# ConceptNet endpoints
@router.get("/conceptnet/search", response_model=MultiSourceSearchResponse)
async def conceptnet_search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    offset: int = Query(0, ge=0, description="Result offset"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Search ConceptNet for concepts matching the query"""
    try:
        # Format the query as a ConceptNet concept path for English
        # ConceptNet expects concepts in format /c/en/word
        formatted_query = f"/c/en/{query.lower().replace(' ', '_')}"

        # Use the node parameter to search for concepts containing the query
        request = ConceptNetQueryRequest(
            node=formatted_query, limit=limit, offset=offset
        )
        return await service.conceptnet_query(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/conceptnet/query", response_model=MultiSourceSearchResponse)
async def conceptnet_query(
    start: Optional[str] = Query(None, description="Starting concept"),
    end: Optional[str] = Query(None, description="Ending concept"),
    node: Optional[str] = Query(None, description="Any concept"),
    rel: Optional[str] = Query(None, description="Relation type"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    offset: int = Query(0, ge=0, description="Result offset"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Query ConceptNet with various parameters"""
    try:
        request = ConceptNetQueryRequest(
            start=start, end=end, node=node, rel=rel, limit=limit, offset=offset
        )
        return await service.conceptnet_query(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/conceptnet/concept/{concept_path:path}", response_model=MultiSourceSearchResponse)
async def conceptnet_get_concept(
    concept_path: str = Path(..., description="ConceptNet concept path"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Get data for a specific ConceptNet concept"""
    try:
        return await service.conceptnet_get_concept(concept_path)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/conceptnet/related/{concept_path:path}", response_model=MultiSourceSearchResponse)
async def conceptnet_get_related(
    concept_path: str = Path(..., description="ConceptNet concept path"),
    filter: Optional[str] = Query(None, description="Filter for related concepts"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Get related concepts from ConceptNet"""
    try:
        return await service.conceptnet_get_related(concept_path, filter, limit)
    except Exception as e:
        raise handle_service_error(e)


# Wikidata endpoints
@router.get("/wikidata/search", response_model=MultiSourceSearchResponse)
async def wikidata_search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Result limit (max 50)"),
    offset: int = Query(0, ge=0, description="Result offset"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Search Wikidata entities"""
    try:
        request = WikidataSearchRequest(query=query, limit=limit, offset=offset)
        return await service.wikidata_search(request)
    except Exception as e:
        raise handle_service_error(e)


@router.post("/wikidata/sparql", response_model=MultiSourceSearchResponse)
async def wikidata_sparql(
    request: WikidataSparqlRequest,
    service: ReferenceService = Depends(get_reference_service)
):
    """Execute SPARQL query against Wikidata"""
    try:
        return await service.wikidata_sparql(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/wikidata/entity", response_model=MultiSourceSearchResponse)
async def wikidata_get_entity(
    entity_url: str = Query(..., description="Wikidata entity URL"),
    properties: Optional[str] = Query(None, description="Comma-separated property IDs"),
    format: ResponseFormat = Query(ResponseFormat.JSON, description="Response format"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Get structured data for a Wikidata entity"""
    try:
        property_list = properties.split(",") if properties else None
        request = WikidataEntityRequest(entity_url=entity_url, properties=property_list, format=format)
        return await service.wikidata_get_entity(request)
    except Exception as e:
        raise handle_service_error(e)


# Schema.org endpoints
@router.get("/schema-org/entity/{identifier}", response_model=MultiSourceSearchResponse)
async def schema_org_get_entity(
    identifier: str = Path(..., description="Schema.org entity identifier"),
    include_inherited: bool = Query(True, description="Include inherited properties"),
    include_children: bool = Query(False, description="Include child entities"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Get Schema.org entity with properties and inheritance"""
    try:
        request = SchemaOrgEntityRequest(
            identifier=identifier,
            include_inherited=include_inherited,
            include_children=include_children
        )
        return await service.schema_org_get_entity(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/schema-org/property/{identifier}", response_model=MultiSourceSearchResponse)
async def schema_org_get_property(
    identifier: str = Path(..., description="Schema.org property identifier"),
    include_usage: bool = Query(True, description="Include entities using this property"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Get Schema.org property definition and usage"""
    try:
        request = SchemaOrgPropertyRequest(identifier=identifier, include_usage=include_usage)
        return await service.schema_org_get_property(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/schema-org/search", response_model=MultiSourceSearchResponse)
async def schema_org_search(
    query: str = Query(..., description="Search query"),
    search_type: Literal["entities", "properties", "both"] = Query("both", description="Search type"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    offset: int = Query(0, ge=0, description="Result offset"),
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Similarity threshold"),
    service: ReferenceService = Depends(get_reference_service)
):
    """Search Schema.org entities and properties"""
    try:
        request = SchemaOrgSearchRequest(
            query=query,
            search_type=search_type,
            limit=limit,
            offset=offset,
            similarity_threshold=similarity_threshold
        )
        return await service.schema_org_search(request)
    except Exception as e:
        raise handle_service_error(e)


# Multi-source search endpoint
@router.post("/search", response_model=MultiSourceSearchResponse)
async def multi_source_search(
    request: MultiSourceSearchRequest,
    service: ReferenceService = Depends(get_reference_service)
):
    """
    Search across multiple reference sources

    Searches across specified sources (or all enabled sources if none specified)
    and returns aggregated results without deduplication or ranking.
    """
    try:
        return await service.search(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/search", response_model=MultiSourceSearchResponse)
async def multi_source_search_get(
    query: str = Query(..., description="Search query", min_length=1),
    sources: Optional[str] = Query(None, description="Comma-separated list of source types"),
    limit: int = Query(20, description="Maximum results per source", ge=1, le=100),
    offset: int = Query(0, description="Result offset", ge=0),
    service: ReferenceService = Depends(get_reference_service)
):
    """
    Search across multiple reference sources via GET request

    Alternative GET endpoint for multi-source search with query parameters.
    """
    try:
        # Parse sources parameter
        source_list = None
        if sources:
            source_names = [s.strip() for s in sources.split(',')]
            source_list = []
            for name in source_names:
                try:
                    source_list.append(SourceType(name))
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid source: {name}")

        # Create request object
        request = MultiSourceSearchRequest(
            query=query,
            sources=source_list,
            limit=limit,
            offset=offset
        )

        return await service.search(request)
    except HTTPException:
        raise
    except Exception as e:
        raise handle_service_error(e)


# Health and status endpoints
@router.get("/health")
async def health_check(service: ReferenceService = Depends(get_reference_service)):
    """Check health status of all reference API sources"""
    try:
        return await service.health_check()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"overall": "unhealthy", "error": str(e)}
        )

