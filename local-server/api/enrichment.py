"""FastAPI router for enrichment endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from enrichment.service import EnrichmentService
from config import EnrichmentConfig, get_settings
from enrichment.models import *
from enrichment.exceptions import EnrichmentError, SourceError, SourceTimeoutError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nlp_analysis/reference", tags=["enrichment"])


def get_enrichment_service() -> EnrichmentService:
    """Dependency to get enrichment service instance"""
    settings = get_settings()
    cfg = EnrichmentConfig(**getattr(settings, 'ENRICHMENT_CONFIG', {}))
    return EnrichmentService(cfg)


def handle_service_error(e: Exception) -> HTTPException:
    """Convert service errors to appropriate HTTP exceptions"""
    if isinstance(e, SourceTimeoutError):
        return HTTPException(status_code=504, detail=str(e))
    elif isinstance(e, SourceError):
        return HTTPException(status_code=503, detail=str(e))
    elif isinstance(e, EnrichmentError):
        return HTTPException(status_code=400, detail=str(e))
    else:
        logger.error(f"Unexpected error: {e}")
        return HTTPException(status_code=500, detail="Internal server error")


# DBpedia endpoints
@router.get("/dbpedia/resource", response_model=DBpediaResourceResponse)
async def dbpedia_get_resource(
    resource_url: str = Query(..., description="DBpedia resource URL"),
    format: ResponseFormat = Query(ResponseFormat.JSON, description="Response format"),
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Retrieve structured data from a DBpedia resource URL"""
    try:
        request = DBpediaResourceRequest(resource_url=resource_url, format=format)
        return await service.dbpedia_get_resource(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/dbpedia/search", response_model=DBpediaSearchResponse)
async def dbpedia_search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    format: ResponseFormat = Query(ResponseFormat.JSON, description="Response format"),
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Search DBpedia using the search API"""
    try:
        request = DBpediaSearchRequest(query=query, limit=limit, offset=offset, format=format)
        return await service.dbpedia_search(request)
    except Exception as e:
        raise handle_service_error(e)


@router.post("/dbpedia/sparql", response_model=DBpediaSparqlResponse)
async def dbpedia_sparql(
    request: DBpediaSparqlRequest,
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Execute SPARQL query against DBpedia"""
    try:
        return await service.dbpedia_sparql(request)
    except Exception as e:
        raise handle_service_error(e)


# ConceptNet endpoints
@router.get("/conceptnet/query", response_model=ConceptNetQueryResponse)
async def conceptnet_query(
    start: Optional[str] = Query(None, description="Starting concept"),
    end: Optional[str] = Query(None, description="Ending concept"),
    node: Optional[str] = Query(None, description="Any concept"),
    rel: Optional[str] = Query(None, description="Relation type"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    offset: int = Query(0, ge=0, description="Result offset"),
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Query ConceptNet with various parameters"""
    try:
        request = ConceptNetQueryRequest(
            start=start, end=end, node=node, rel=rel, limit=limit, offset=offset
        )
        return await service.conceptnet_query(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/conceptnet/concept/{concept_path:path}", response_model=ConceptNetConceptResponse)
async def conceptnet_get_concept(
    concept_path: str = Path(..., description="ConceptNet concept path"),
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Get data for a specific ConceptNet concept"""
    try:
        return await service.conceptnet_get_concept(concept_path)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/conceptnet/related/{concept_path:path}", response_model=ConceptNetRelatedResponse)
async def conceptnet_get_related(
    concept_path: str = Path(..., description="ConceptNet concept path"),
    filter: Optional[str] = Query(None, description="Filter for related concepts"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Get related concepts from ConceptNet"""
    try:
        return await service.conceptnet_get_related(concept_path, filter, limit)
    except Exception as e:
        raise handle_service_error(e)


# Wikidata endpoints
@router.post("/wikidata/sparql", response_model=WikidataSparqlResponse)
async def wikidata_sparql(
    request: WikidataSparqlRequest,
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Execute SPARQL query against Wikidata"""
    try:
        return await service.wikidata_sparql(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/wikidata/entity", response_model=WikidataEntityResponse)
async def wikidata_get_entity(
    entity_url: str = Query(..., description="Wikidata entity URL"),
    properties: Optional[str] = Query(None, description="Comma-separated property IDs"),
    format: ResponseFormat = Query(ResponseFormat.JSON, description="Response format"),
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Get structured data for a Wikidata entity"""
    try:
        property_list = properties.split(",") if properties else None
        request = WikidataEntityRequest(entity_url=entity_url, properties=property_list, format=format)
        return await service.wikidata_get_entity(request)
    except Exception as e:
        raise handle_service_error(e)


# Schema.org endpoints
@router.get("/schema-org/entity/{identifier}", response_model=SchemaOrgEntityResponse)
async def schema_org_get_entity(
    identifier: str = Path(..., description="Schema.org entity identifier"),
    include_inherited: bool = Query(True, description="Include inherited properties"),
    include_children: bool = Query(False, description="Include child entities"),
    service: EnrichmentService = Depends(get_enrichment_service)
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


@router.get("/schema-org/property/{identifier}", response_model=SchemaOrgPropertyResponse)
async def schema_org_get_property(
    identifier: str = Path(..., description="Schema.org property identifier"),
    include_usage: bool = Query(True, description="Include entities using this property"),
    service: EnrichmentService = Depends(get_enrichment_service)
):
    """Get Schema.org property definition and usage"""
    try:
        request = SchemaOrgPropertyRequest(identifier=identifier, include_usage=include_usage)
        return await service.schema_org_get_property(request)
    except Exception as e:
        raise handle_service_error(e)


@router.get("/schema-org/search", response_model=SchemaOrgSearchResponse)
async def schema_org_search(
    query: str = Query(..., description="Search query"),
    search_type: Literal["entities", "properties", "both"] = Query("both", description="Search type"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    offset: int = Query(0, ge=0, description="Result offset"),
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Similarity threshold"),
    service: EnrichmentService = Depends(get_enrichment_service)
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


# Health and status endpoints
@router.get("/health")
async def health_check(service: EnrichmentService = Depends(get_enrichment_service)):
    """Check health status of all reference API sources"""
    try:
        return await service.health_check()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"overall": "unhealthy", "error": str(e)}
        )

