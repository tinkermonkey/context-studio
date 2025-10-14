"""FastAPI router for reference endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body
from fastapi.responses import JSONResponse
from typing import Optional, Literal
from pydantic import BaseModel, Field
import logging

from api.dependencies.reference_services import get_reference_service
from reference_api.service import ReferenceService
from reference_api.models import (
    DBpediaResourceRequest, DBpediaSearchRequest, DBpediaSparqlRequest, ConceptNetQueryRequest,
    WikidataSparqlRequest, WikidataEntityRequest, WikidataSearchRequest, SchemaOrgEntityRequest,
    SchemaOrgPropertyRequest, SchemaOrgSearchRequest, ResponseFormat, SourceType, MultiSourceSearchRequest,
    MultiSourceSearchResponse
)
from reference_api.exceptions import ReferenceError, SourceError, SourceTimeoutError
from config import get_settings, Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reference", tags=["reference"])


# Request models for reference database endpoints
class ReferenceSearchRequest(BaseModel):
    """Request model for reference database search"""
    query: str = Field(..., min_length=1, description="Search query text")
    source: Optional[str] = Field(None, description="Filter by source (e.g., 'schema.org')")
    limit: int = Field(20, ge=1, le=10000, description="Maximum results")
    threshold: float = Field(0.7, ge=-1.0, le=1.0, description="Similarity threshold")


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


# Reference database vector search endpoints
@router.get("/ref-db/search")
async def reference_db_search(
    query: str = Query(..., description="Search query text", min_length=1),
    source: Optional[str] = Query(None, description="Filter by source (e.g., 'schema.org')"),
    limit: int = Query(20, ge=1, le=10000, description="Maximum results"),
    threshold: float = Query(0.7, ge=-1.0, le=1.0, description="Similarity threshold"),
):
    """
    Search reference database using semantic vector similarity.

    This endpoint uses vector embeddings for semantic search and returns results
    ranked by similarity score.
    """
    # Additional input validation
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty")

    if not -1.0 <= threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail=f"Threshold must be between -1.0 and 1.0, got {threshold}"
        )

    if limit < 1 or limit > 10000:
        raise HTTPException(
            status_code=400,
            detail=f"Limit must be between 1 and 10000, got {limit}"
        )

    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig
        from embeddings.generate_embeddings import generate_embedding

        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            # Create embedding generator
            def embedding_gen(text: str) -> bytes:
                return generate_embedding(text)

            # Execute search
            results_with_scores = manager.search_by_similarity(
                query_text=query,
                source=source,
                limit=limit,
                threshold=threshold,
                embedding_generator=embedding_gen
            )

            # Format response
            results = []
            for node, score in results_with_scores:
                results.append({
                    "id": node.id,
                    "title": node.title,
                    "definition": node.definition,
                    "source": node.source,
                    "external_id": node.external_id,
                    "similarity_score": score
                })

            return {
                "query": query,
                "total_results": len(results),
                "results": results
            }

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except ValueError as e:
        # Return 400 for validation errors from manager
        logger.warning(f"Invalid search parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Return 500 for database/vector search errors (fail fast)
        logger.error(f"Reference DB search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")


@router.post("/ref-db/search")
async def reference_db_search_post(
    request: ReferenceSearchRequest = Body(...),
):
    """
    Search reference database using semantic vector similarity (POST version).

    This endpoint uses vector embeddings for semantic search and returns results
    ranked by similarity score. Accepts a JSON body with search parameters.
    """
    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig
        from embeddings.generate_embeddings import generate_embedding

        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            # Create embedding generator
            def embedding_gen(text: str) -> bytes:
                return generate_embedding(text)

            # Execute search
            results_with_scores = manager.search_by_similarity(
                query_text=request.query,
                source=request.source,
                limit=request.limit,
                threshold=request.threshold,
                embedding_generator=embedding_gen
            )

            # Format response
            results = []
            for node, score in results_with_scores:
                results.append({
                    "id": node.id,
                    "title": node.title,
                    "definition": node.definition,
                    "source": node.source,
                    "external_id": node.external_id,
                    "similarity_score": score
                })

            return {
                "query": request.query,
                "total_results": len(results),
                "results": results
            }

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except ValueError as e:
        # Return 400 for validation errors from manager
        logger.warning(f"Invalid search parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Return 500 for database/vector search errors (fail fast)
        logger.error(f"Reference DB search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")


@router.get("/ref-db/entity/{source}/{external_id}")
async def get_reference_entity(
    source: str = Path(..., description="Source identifier (e.g., 'schema.org')"),
    external_id: str = Path(..., description="External identifier from source"),
):
    """
    Get a reference entity by source and external ID.

    This endpoint looks up entities from the reference database using their
    source identifier and external ID.
    """
    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig

        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            node = manager.get_reference_node_by_source(source, external_id)

            if not node:
                raise HTTPException(
                    status_code=404,
                    detail=f"Entity not found: {source}/{external_id}"
                )

            return {
                "id": node.id,
                "title": node.title,
                "definition": node.definition,
                "source": node.source,
                "external_id": node.external_id,
                "created_at": node.created_at,
                "updated_at": node.updated_at
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get reference entity failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ref-db/property/{source}/{external_id}")
async def get_reference_property(
    source: str = Path(..., description="Source identifier (e.g., 'schema.org')"),
    external_id: str = Path(..., description="External identifier from source"),
):
    """
    Get a reference property by source and external ID.

    This endpoint looks up properties from the reference database using their
    source identifier and external ID. Properties are stored as reference nodes
    with a type attribute indicating they are properties.
    """
    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig

        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            node = manager.get_reference_node_by_source(source, external_id)

            if not node:
                raise HTTPException(
                    status_code=404,
                    detail=f"Property not found: {source}/{external_id}"
                )

            return {
                "id": node.id,
                "title": node.title,
                "definition": node.definition,
                "source": node.source,
                "external_id": node.external_id,
                "created_at": node.created_at,
                "updated_at": node.updated_at
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get reference property failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ref-db/nodes/{node_id}")
async def get_reference_node(
    node_id: str = Path(..., description="Reference node ID"),
):
    """Get a reference node by ID."""
    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig

        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            node = manager.get_reference_node(node_id)

            if not node:
                raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

            return {
                "id": node.id,
                "title": node.title,
                "definition": node.definition,
                "source": node.source,
                "external_id": node.external_id,
                "created_at": node.created_at,
                "updated_at": node.updated_at
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get reference node failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ref-db/predicates/{source}/{external_id:path}/examples")
async def get_predicate_examples(
    source: str = Path(..., description="Predicate source (e.g., 'schema.org', 'dbpedia')"),
    external_id: str = Path(..., description="External predicate ID (can contain slashes)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of example uses to return"),
    service: ReferenceService = Depends(get_reference_service)
):
    """
    Get example uses of a predicate from the reference database or external APIs.
    
    Returns example links that use this predicate, including information about
    the subject and object nodes. This helps users understand how the predicate
    is used in the knowledge graph.
    
    Note: The external_id parameter accepts paths with slashes (e.g., '/r/RelatedTo' for ConceptNet).
    For DBpedia, uses SPARQL queries to fetch live examples from the public endpoint.
    """
    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig
        from reference_db.models import ReferenceLink
        
        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            # Get the external predicate to verify it exists
            predicate = manager.get_external_predicate_by_source(source, external_id)
            if not predicate:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Predicate not found: {source}/{external_id}"
                )
            
            examples = []
            
            # Use different strategies based on the source
            if source.lower() == 'dbpedia':
                # For DBpedia, query the live SPARQL endpoint directly
                import httpx
                
                sparql_query = f"""
                SELECT ?subject ?subjectLabel ?object ?objectLabel
                WHERE {{
                    ?subject <{external_id}> ?object .
                    OPTIONAL {{ ?subject rdfs:label ?subjectLabel . FILTER(LANG(?subjectLabel) = "en") }}
                    OPTIONAL {{ ?object rdfs:label ?objectLabel . FILTER(LANG(?objectLabel) = "en") }}
                }}
                LIMIT {limit}
                """
                
                try:
                    # Query DBpedia's public SPARQL endpoint directly
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            "https://dbpedia.org/sparql",
                            data={
                                "query": sparql_query,
                                "format": "application/json"
                            }
                        )
                        response.raise_for_status()
                        sparql_result = response.json()
                    
                    # Parse SPARQL results
                    if sparql_result.get("results") and sparql_result["results"].get("bindings"):
                        for binding in sparql_result["results"]["bindings"][:limit]:
                            subject_uri = binding.get("subject", {}).get("value", "")
                            object_uri = binding.get("object", {}).get("value", "")
                            subject_label = binding.get("subjectLabel", {}).get("value", subject_uri.split("/")[-1])
                            object_label = binding.get("objectLabel", {}).get("value", object_uri.split("/")[-1])
                            
                            examples.append({
                                "link_id": f"dbpedia-{len(examples)}",
                                "subject": {
                                    "id": subject_uri,
                                    "title": subject_label,
                                    "source": "dbpedia",
                                    "external_id": subject_uri
                                },
                                "predicate": {
                                    "title": predicate.title,
                                    "source": predicate.source,
                                    "external_id": predicate.external_id
                                },
                                "object": {
                                    "id": object_uri,
                                    "title": object_label,
                                    "source": "dbpedia",
                                    "external_id": object_uri
                                }
                            })
                except Exception as e:
                    logger.error(f"DBpedia SPARQL query failed: {e}")
                    # Fall through to local database query
            
            # For other sources or if DBpedia query failed, use local reference database
            if not examples:
                # Try exact match first
                links = manager.session.query(ReferenceLink).filter(
                    ReferenceLink.predicate == external_id
                ).limit(limit).all()
                
                # If no results and external_id looks like a URI, try extracting the predicate name
                if not links and '/' in external_id:
                    predicate_name = external_id.split('/')[-1]
                    if predicate_name:
                        links = manager.session.query(ReferenceLink).filter(
                            ReferenceLink.predicate == predicate_name
                        ).limit(limit).all()
                
                # Build response with node details
                for link in links:
                    subject = manager.get_reference_node(link.subject_node)
                    obj = manager.get_reference_node(link.object_node)
                    
                    if subject and obj:
                        examples.append({
                            "link_id": link.id,
                            "subject": {
                                "id": subject.id,
                                "title": subject.title,
                                "source": subject.source,
                                "external_id": subject.external_id
                            },
                            "predicate": {
                                "title": predicate.title,
                                "source": predicate.source,
                                "external_id": predicate.external_id
                            },
                            "object": {
                                "id": obj.id,
                                "title": obj.title,
                                "source": obj.source,
                                "external_id": obj.external_id
                            }
                        })
            
            return {
                "predicate": {
                    "id": predicate.id,
                    "title": predicate.title,
                    "definition": predicate.definition,
                    "source": predicate.source,
                    "external_id": predicate.external_id
                },
                "total_examples": len(examples),
                "examples": examples
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get predicate examples failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ref-db/nodes/{node_id}/links")
async def get_node_links(
    node_id: str = Path(..., description="Reference node ID"),
    direction: str = Query("both", description="Link direction: inbound, outbound, or both"),
    predicate: Optional[str] = Query(None, description="Filter by predicate (exact match)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Maximum results"),
    apply_relevance_filter: Optional[bool] = Query(None, description="Apply predicate relevance filtering (defaults to config setting)"),
    settings: Settings = Depends(get_settings),
):
    """
    Retrieve links connected to a reference node.

    Returns links ordered by created_at (descending).

    When apply_relevance_filter=True, filters links based on predicate relevance
    mappings from the global predicates table. If not specified, uses the
    enable_relevance_filtering setting from configuration.
    """
    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig
        from database.utils import get_db
        from services.reference_filter_service import ReferenceFilterService

        # Use configuration default if not explicitly provided
        if apply_relevance_filter is None:
            apply_relevance_filter = settings.reference_sources.enable_relevance_filtering

        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            # Verify node exists
            node = manager.get_reference_node(node_id)
            if not node:
                raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

            # Get links
            links = manager.get_node_links(
                node_id=node_id,
                direction=direction,
                predicate=predicate,
                limit=limit
            )

            # Apply relevance filtering if requested
            filter_stats = None
            if apply_relevance_filter:
                # Get local DB session for predicate access
                local_db = next(get_db())
                try:
                    filter_service = ReferenceFilterService(local_db, manager)
                    links, filter_stats = filter_service.filter_links(links)
                finally:
                    local_db.close()

            # Format response
            results = []
            for link in links:
                results.append({
                    "id": link.id,
                    "subject_node": link.subject_node,
                    "predicate": link.predicate,
                    "object_node": link.object_node,
                    "created_at": link.created_at
                })

            response = {
                "node_id": node_id,
                "direction": direction,
                "predicate": predicate,
                "total_links": len(results),
                "links": results,
                "filtering_applied": apply_relevance_filter
            }

            if filter_stats:
                response["filter_statistics"] = filter_stats

            return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Get node links failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


@router.get("/ref-db/health")
async def reference_db_health_check():
    """
    Check health status of the reference database.

    Returns comprehensive status information including:
    - status: "healthy", "degraded", or "missing"
    - node_count: Total number of reference nodes
    - vec_count: Number of nodes with embeddings
    - schema_version: Current database schema version
    - model_version: Embedding model version
    - last_import_at: Timestamp of last import
    - database_size: Size of database file in bytes

    Performance target: <200ms

    Test Case: TC-S002
    """
    import time
    start_time = time.time()

    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig

        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            status = manager.get_status()

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Add execution time to response
            status["execution_time_ms"] = round(execution_time_ms, 2)

            # Log warning if execution time exceeds target
            if execution_time_ms > 200:
                logger.warning(
                    f"Health check exceeded 200ms target: {execution_time_ms:.2f}ms"
                )

            return status

    except Exception as e:
        logger.error(f"Reference DB health check failed: {e}")
        execution_time_ms = (time.time() - start_time) * 1000
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": "Health check failed",
                "execution_time_ms": round(execution_time_ms, 2)
            }
        )


# Reference filter endpoints
@router.get("/ref-db/filter/statistics")
async def get_filter_statistics():
    """
    Get reference link filtering statistics.

    Returns information about the current predicate relevance configuration:
    - Number of relevant/irrelevant predicates
    - External predicate mappings
    - Filtering readiness status

    This endpoint helps users understand what will be filtered when
    they enable relevance filtering on reference queries.
    """
    try:
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig
        from database.utils import get_db
        from services.reference_filter_service import ReferenceFilterService

        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            local_db = next(get_db())
            try:
                filter_service = ReferenceFilterService(local_db, manager)
                stats = filter_service.get_filter_statistics()
                return stats
            finally:
                local_db.close()

    except Exception as e:
        logger.error(f"Get filter statistics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

