"""
Combined Graph Service for Context Studio

This module provides a unified interface that combines both SPARQL querying
capabilities (via RDFLib) and graph analytics (via NetworkX) for comprehensive
graph operations on the Context Studio data.
"""

from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from .sparql_service import SPARQLService
from .network_service import NetworkService
from utils.logger import get_logger

logger = get_logger(__name__)


class GraphService:
    """
    Combined graph service that provides both SPARQL querying and NetworkX analytics.
    This is the main interface for graph operations in the Context Studio.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize the combined graph service.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
        self.sparql_service = SPARQLService(db_session)
        self.network_service = NetworkService(db_session)
        logger.info("GraphService initialized with SPARQL and NetworkX capabilities")
    
    def refresh(self):
        """Refresh both SPARQL and NetworkX graphs from the database."""
        logger.info("Refreshing both SPARQL and NetworkX graphs...")
        self.sparql_service.refresh()
        self.network_service.refresh()
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics from both graph representations.
        
        Returns:
            Combined statistics from SPARQL and NetworkX services
        """
        return {
            "sparql_stats": self.sparql_service.get_graph_stats(),
            "network_stats": self.network_service.get_graph_stats(),
            "service_info": {
                "sparql_triples": len(self.sparql_service.graph),
                "network_nodes": self.network_service.graph.number_of_nodes(),
                "network_edges": self.network_service.graph.number_of_edges(),
                "last_updated": datetime.now().isoformat()
            }
        }
    
    # SPARQL-based operations
    def sparql_query(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Execute a SPARQL query."""
        return self.sparql_service.query(query, **kwargs)
    
    def find_terms_by_title(self, title: str, exact: bool = False) -> List[Dict[str, Any]]:
        """Find terms by title using SPARQL."""
        return self.sparql_service.find_terms_by_title(title, exact)
    
    def get_domain_hierarchy(self, layer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get domain hierarchy using SPARQL."""
        return self.sparql_service.get_domain_hierarchy(layer_id)
    
    def serialize_rdf(self, format: str = "turtle") -> str:
        """Serialize the RDF graph."""
        return self.sparql_service.serialize(format)
    
    # NetworkX-based operations
    def calculate_centrality(self, method: str = "pagerank") -> Dict[str, float]:
        """Calculate node centrality using NetworkX."""
        return self.network_service.calculate_centrality(method)
    
    def find_shortest_path(self, source_id: str, target_id: str, 
                          source_type: str = "term", target_type: str = "term") -> Optional[List[str]]:
        """Find shortest path between nodes using NetworkX."""
        return self.network_service.find_shortest_path(source_id, target_id, source_type, target_type)
    
    def get_neighbors(self, entity_id: str, entity_type: str = "term", 
                     depth: int = 1, direction: str = "both") -> Dict[str, List[str]]:
        """Get neighbors using NetworkX."""
        return self.network_service.get_neighbors(entity_id, entity_type, depth, direction)
    
    def detect_communities(self, method: str = "louvain") -> List[List[str]]:
        """Detect communities using NetworkX."""
        communities = self.network_service.detect_communities(method)
        return [list(community) for community in communities]
    
    def get_term_hierarchy(self, term_id: str) -> Dict[str, Any]:
        """Get term hierarchy using NetworkX."""
        return self.network_service.get_term_hierarchy(term_id)
    
    def get_node_info(self, entity_id: str, entity_type: str = "term") -> Optional[Dict[str, Any]]:
        """Get detailed node information using NetworkX."""
        return self.network_service.get_node_info(entity_id, entity_type)
    
    # Combined operations that leverage both services
    def find_related_terms_comprehensive(self, term_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """
        Find related terms using both SPARQL and NetworkX for comprehensive results.
        
        Args:
            term_id: The ID of the term to find relations for
            max_depth: Maximum depth of relationships to traverse
            
        Returns:
            Combined results from both services
        """
        # Use SPARQL for semantic relationships
        sparql_results = self.sparql_service.find_related_terms(term_id, max_depth)
        
        # Use NetworkX for structural analysis
        network_neighbors = self.network_service.get_neighbors(term_id, "term", max_depth, "both")
        
        # Get centrality information
        centrality = self.network_service.calculate_centrality("pagerank")
        term_node = f"term:{term_id}"
        
        return {
            "term_id": term_id,
            "semantic_relationships": sparql_results,
            "structural_neighbors": network_neighbors,
            "centrality_score": centrality.get(term_node, 0.0),
            "hierarchy": self.network_service.get_term_hierarchy(term_id),
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def analyze_domain_structure(self, domain_id: str) -> Dict[str, Any]:
        """
        Comprehensive analysis of a domain's structure using both services.
        
        Args:
            domain_id: Domain ID to analyze
            
        Returns:
            Comprehensive domain analysis
        """
        # SPARQL query for domain metadata
        domain_query = f"""
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX entity: <http://context-studio.local/entity/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?domain ?title ?definition ?layer ?layerTitle WHERE {{
            BIND(<http://context-studio.local/entity/domain/{domain_id}> AS ?domain)
            ?domain a cs:Domain ;
                   rdfs:label ?title ;
                   rdfs:comment ?definition ;
                   cs:is_a ?layer .
            ?layer rdfs:label ?layerTitle .
        }}
        """
        
        domain_info = self.sparql_service.query(domain_query)
        
        # NetworkX analysis for terms in domain
        terms_in_domain = self.network_service.find_terms_in_domain_tree(domain_id)
        
        # Calculate centrality for domain terms
        centrality = self.network_service.calculate_centrality("pagerank")
        term_centralities = {
            term_id: centrality.get(f"term:{term_id}", 0.0) 
            for term_id in terms_in_domain
        }
        
        # Get domain node info
        domain_node_info = self.network_service.get_node_info(domain_id, "domain")
        
        return {
            "domain_metadata": domain_info[0] if domain_info else None,
            "terms_count": len(terms_in_domain),
            "terms_in_domain": terms_in_domain,
            "term_centralities": term_centralities,
            "domain_network_info": domain_node_info,
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def search_and_analyze(self, search_term: str, analysis_depth: int = 1) -> Dict[str, Any]:
        """
        Search for terms and provide comprehensive analysis.
        
        Args:
            search_term: Term to search for
            analysis_depth: Depth of analysis to perform
            
        Returns:
            Search results with comprehensive analysis
        """
        # Find matching terms using SPARQL
        matching_terms = self.sparql_service.find_terms_by_title(search_term, exact=False)
        
        # Analyze each matching term
        analyzed_terms = []
        for term in matching_terms:
            # Extract term ID from URI
            term_uri = term.get("term", "")
            if "term/" in term_uri:
                term_id = term_uri.split("term/")[-1]
                
                # Get comprehensive analysis
                analysis = self.find_related_terms_comprehensive(term_id, analysis_depth)
                
                analyzed_terms.append({
                    "term_info": term,
                    "analysis": analysis
                })
        
        return {
            "search_term": search_term,
            "matches_found": len(matching_terms),
            "analyzed_terms": analyzed_terms,
            "search_timestamp": datetime.now().isoformat()
        }
    
    def get_layer_analytics(self, layer_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a layer or all layers.
        
        Args:
            layer_id: Optional layer ID to analyze
            
        Returns:
            Layer analytics from both services
        """
        # Get domain hierarchy from SPARQL
        hierarchy = self.sparql_service.get_domain_hierarchy(layer_id)
        
        # Get network statistics
        network_stats = self.network_service.get_graph_stats()
        
        # Calculate layer-specific metrics
        layer_metrics = {}
        
        if layer_id:
            # Analyze specific layer
            layer_node = f"layer:{layer_id}"
            layer_info = self.network_service.get_node_info(layer_id, "layer")
            
            # Find all domains and terms in this layer
            domains_in_layer = []
            terms_in_layer = []
            
            for node in self.network_service.graph.nodes(data=True):
                node_id, node_data = node
                if node_data.get("type") == "domain" and node_data.get("layer_id") == layer_id:
                    domains_in_layer.append(node_data.get("entity_id"))
                elif node_data.get("type") == "term" and node_data.get("layer_id") == layer_id:
                    terms_in_layer.append(node_data.get("entity_id"))
            
            layer_metrics = {
                "layer_info": layer_info,
                "domains_count": len(domains_in_layer),
                "terms_count": len(terms_in_layer),
                "domains": domains_in_layer,
                "terms": terms_in_layer
            }
        
        return {
            "layer_id": layer_id,
            "hierarchy": hierarchy,
            "network_stats": network_stats,
            "layer_metrics": layer_metrics,
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def export_graph_data(self, format: str = "json") -> Union[str, Dict[str, Any]]:
        """
        Export comprehensive graph data in various formats.
        
        Args:
            format: Export format ("json", "turtle", "graphml")
            
        Returns:
            Exported graph data
        """
        if format == "json":
            return {
                "metadata": self.get_comprehensive_stats(),
                "rdf_data": self.sparql_service.serialize("json-ld"),
                "network_data": {
                    "nodes": list(self.network_service.graph.nodes(data=True)),
                    "edges": list(self.network_service.graph.edges(data=True))
                },
                "export_timestamp": datetime.now().isoformat()
            }
        elif format == "turtle":
            return self.sparql_service.serialize("turtle")
        elif format == "graphml":
            # This would need to be saved to a file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.graphml', delete=False) as f:
                self.network_service.export_to_graphml(f.name)
                with open(f.name, 'r') as graphml_file:
                    content = graphml_file.read()
                os.unlink(f.name)
                return content
        else:
            raise ValueError(f"Unsupported export format: {format}")
