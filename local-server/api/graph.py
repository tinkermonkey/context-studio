"""
Graph API endpoints for Context Studio

This module provides FastAPI endpoints for graph operations using both
SPARQL and NetworkX capabilities.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from database.utils import get_session_local, get_engine
from graph.graph_service import GraphService
from utils.logger import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/graph", tags=["Graph"])

# Dependency to get database session
def get_db_session():
    engine = get_engine()
    SessionLocal = get_session_local(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

# Dependency to get graph service
def get_graph_service(db_session: Session = Depends(get_db_session)) -> GraphService:
    return GraphService(db_session)

# Pydantic models for request/response
class SPARQLQuery(BaseModel):
    query: str
    format: Optional[str] = "json"

class SearchRequest(BaseModel):
    term: str
    exact: Optional[bool] = False
    analysis_depth: Optional[int] = 1

class PathRequest(BaseModel):
    source_id: str
    target_id: str
    source_type: Optional[str] = "term"
    target_type: Optional[str] = "term"

class CentralityRequest(BaseModel):
    method: Optional[str] = "pagerank"

class NeighborsRequest(BaseModel):
    entity_id: str
    entity_type: Optional[str] = "term"
    depth: Optional[int] = 1
    direction: Optional[str] = "both"


# Graph statistics and information endpoints
@router.get("/stats")
async def get_graph_stats(graph_service: GraphService = Depends(get_graph_service)) -> Dict[str, Any]:
    """Get comprehensive graph statistics from both SPARQL and NetworkX services."""
    return graph_service.get_comprehensive_stats()

@router.post("/refresh")
async def refresh_graphs(graph_service: GraphService = Depends(get_graph_service)) -> Dict[str, str]:
    """Refresh both SPARQL and NetworkX graphs from the database."""
    graph_service.refresh()
    return {"status": "success", "message": "Graphs refreshed from database"}

# SPARQL endpoints
@router.post("/sparql/query")
async def execute_sparql_query(
    query_request: SPARQLQuery,
    graph_service: GraphService = Depends(get_graph_service)
) -> List[Dict[str, Any]]:
    """Execute a SPARQL query against the RDF graph."""
    try:
        results = graph_service.sparql_query(query_request.query)
        return results
    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        raise HTTPException(status_code=400, detail=f"SPARQL query failed: {str(e)}")

@router.get("/sparql/export")
async def export_rdf(
    format: str = Query("turtle", description="RDF serialization format"),
    graph_service: GraphService = Depends(get_graph_service)
) -> str:
    """Export the RDF graph in various formats."""
    try:
        return graph_service.serialize_rdf(format)
    except Exception as e:
        logger.error(f"RDF export failed: {e}")
        raise HTTPException(status_code=400, detail=f"RDF export failed: {str(e)}")

# Search and discovery endpoints
@router.get("/search/terms")
async def search_terms(
    title: str = Query(..., description="Term title to search for"),
    exact: bool = Query(False, description="Whether to do exact match"),
    graph_service: GraphService = Depends(get_graph_service)
) -> List[Dict[str, Any]]:
    """Search for terms by title using SPARQL."""
    return graph_service.find_terms_by_title(title, exact)

@router.post("/search/analyze")
async def search_and_analyze(
    search_request: SearchRequest,
    graph_service: GraphService = Depends(get_graph_service)
) -> Dict[str, Any]:
    """Search for terms and provide comprehensive analysis."""
    return graph_service.search_and_analyze(
        search_request.term, 
        search_request.analysis_depth
    )

# NetworkX analytics endpoints
@router.post("/analytics/centrality")
async def calculate_centrality(
    request: CentralityRequest,
    graph_service: GraphService = Depends(get_graph_service)
) -> Dict[str, float]:
    """Calculate node centrality using NetworkX algorithms."""
    try:
        return graph_service.calculate_centrality(request.method)
    except Exception as e:
        logger.error(f"Centrality calculation failed: {e}")
        raise HTTPException(status_code=400, detail=f"Centrality calculation failed: {str(e)}")

@router.get("/analytics/communities")
async def detect_communities(
    method: str = Query("louvain", description="Community detection method"),
    graph_service: GraphService = Depends(get_graph_service)
) -> List[List[str]]:
    """Detect communities in the graph using NetworkX algorithms."""
    try:
        return graph_service.detect_communities(method)
    except Exception as e:
        logger.error(f"Community detection failed: {e}")
        raise HTTPException(status_code=400, detail=f"Community detection failed: {str(e)}")

# Path and relationship endpoints
@router.post("/path/shortest")
async def find_shortest_path(
    path_request: PathRequest,
    graph_service: GraphService = Depends(get_graph_service)
) -> Optional[List[str]]:
    """Find the shortest path between two nodes."""
    return graph_service.find_shortest_path(
        path_request.source_id,
        path_request.target_id,
        path_request.source_type,
        path_request.target_type
    )

@router.post("/neighbors")
async def get_neighbors(
    neighbors_request: NeighborsRequest,
    graph_service: GraphService = Depends(get_graph_service)
) -> Dict[str, List[str]]:
    """Get neighbors of a node at specified depth."""
    return graph_service.get_neighbors(
        neighbors_request.entity_id,
        neighbors_request.entity_type,
        neighbors_request.depth,
        neighbors_request.direction
    )

@router.get("/terms/{term_id}/related")
async def find_related_terms(
    term_id: str,
    max_depth: int = Query(2, description="Maximum depth of relationships to traverse"),
    graph_service: GraphService = Depends(get_graph_service)
) -> Dict[str, Any]:
    """Find related terms using both SPARQL and NetworkX for comprehensive results."""
    return graph_service.find_related_terms_comprehensive(term_id, max_depth)

@router.get("/terms/{term_id}/hierarchy")
async def get_term_hierarchy(
    term_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> Dict[str, Any]:
    """Get the full hierarchy for a term (ancestors and descendants)."""
    return graph_service.get_term_hierarchy(term_id)

@router.get("/terms/{term_id}/info")
async def get_term_info(
    term_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific term."""
    result = graph_service.get_node_info(term_id, "term")
    if result is None:
        raise HTTPException(status_code=404, detail="Term not found")
    return result

# Domain and layer analysis endpoints
@router.get("/domains/{domain_id}/analyze")
async def analyze_domain(
    domain_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> Dict[str, Any]:
    """Comprehensive analysis of a domain's structure."""
    return graph_service.analyze_domain_structure(domain_id)

@router.get("/domains/hierarchy")
async def get_domain_hierarchy(
    layer_id: Optional[str] = Query(None, description="Optional layer ID to filter by"),
    graph_service: GraphService = Depends(get_graph_service)
) -> List[Dict[str, Any]]:
    """Get the domain hierarchy for a layer or all layers."""
    return graph_service.get_domain_hierarchy(layer_id)

@router.get("/layers/analytics")
async def get_layer_analytics(
    layer_id: Optional[str] = Query(None, description="Optional layer ID to analyze"),
    graph_service: GraphService = Depends(get_graph_service)
) -> Dict[str, Any]:
    """Get comprehensive analytics for a layer or all layers."""
    return graph_service.get_layer_analytics(layer_id)

@router.get("/layers/{layer_id}/info")
async def get_layer_info(
    layer_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific layer."""
    result = graph_service.get_node_info(layer_id, "layer")
    if result is None:
        raise HTTPException(status_code=404, detail="Layer not found")
    return result

@router.get("/domains/{domain_id}/info")
async def get_domain_info(
    domain_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific domain."""
    result = graph_service.get_node_info(domain_id, "domain")
    if result is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    return result

# Export endpoints
@router.get("/export")
async def export_graph_data(
    format: str = Query("json", description="Export format (json, turtle, graphml)"),
    graph_service: GraphService = Depends(get_graph_service)
) -> Any:
    """Export comprehensive graph data in various formats."""
    try:
        return graph_service.export_graph_data(format)
    except Exception as e:
        logger.error(f"Graph export failed: {e}")
        raise HTTPException(status_code=400, detail=f"Graph export failed: {str(e)}")

# Example SPARQL queries endpoint
@router.get("/examples/sparql")
async def get_sparql_examples() -> Dict[str, str]:
    """Get example SPARQL queries for the Context Studio graph."""
    return {
        "find_all_terms": """
            PREFIX cs: <http://context-studio.local/vocab/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?term ?title ?definition WHERE {
                ?term a cs:Term ;
                      rdfs:label ?title ;
                      rdfs:comment ?definition .
            }
            LIMIT 10
        """,
        "find_terms_in_domain": """
            PREFIX cs: <http://context-studio.local/vocab/>
            PREFIX entity: <http://context-studio.local/entity/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?term ?title WHERE {
                ?term a cs:Term ;
                      rdfs:label ?title ;
                      cs:is_a <http://context-studio.local/entity/domain/DOMAIN_ID> .
            }
        """,
        "find_hierarchical_relationships": """
            PREFIX cs: <http://context-studio.local/vocab/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            
            SELECT ?parent ?child ?parentLabel ?childLabel WHERE {
                ?child skos:broader ?parent .
                ?parent rdfs:label ?parentLabel .
                ?child rdfs:label ?childLabel .
            }
        """,
        "find_term_relationships": """
            PREFIX cs: <http://context-studio.local/vocab/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?source ?predicate ?target ?sourceLabel ?targetLabel WHERE {
                ?source ?predicate ?target .
                ?source a cs:Term ;
                        rdfs:label ?sourceLabel .
                ?target a cs:Term ;
                        rdfs:label ?targetLabel .
                FILTER(?predicate != rdf:type && ?predicate != rdfs:label && ?predicate != rdfs:comment)
            }
        """,
        "count_entities_by_type": """
            PREFIX cs: <http://context-studio.local/vocab/>
            
            SELECT ?type (COUNT(?entity) as ?count) WHERE {
                ?entity a ?type .
                FILTER(?type IN (cs:Layer, cs:Domain, cs:Term))
            }
            GROUP BY ?type
        """
    }
