"""
Test script to demonstrate the SPARQL and NetworkX graph services.

This script shows how to use the combined graph services for various
graph operations on the Context Studio data.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.utils import get_engine, get_session_local, init_db
from graph.graph_service import GraphService
from utils.logger import get_logger
import json

logger = get_logger(__name__)


def test_graph_services():
    """Test the graph services with sample operations."""
    logger.info("Starting graph services test...")
    
    # Initialize database and get session
    try:
        engine = get_engine()
        init_db(engine)
        SessionLocal = get_session_local(engine)
        session = SessionLocal()
        
        # Initialize graph service
        logger.info("Initializing GraphService...")
        graph_service = GraphService(session)
        
        # Test 1: Get comprehensive statistics
        logger.info("Test 1: Getting comprehensive statistics...")
        stats = graph_service.get_comprehensive_stats()
        print("\n=== COMPREHENSIVE GRAPH STATISTICS ===")
        print(json.dumps(stats, indent=2, default=str))
        
        # Test 2: Execute sample SPARQL queries
        logger.info("Test 2: Executing SPARQL queries...")
        
        # Query to count all entities by type
        count_query = """
        PREFIX cs: <http://context-studio.local/vocab/>
        
        SELECT ?type (COUNT(?entity) as ?count) WHERE {
            ?entity a ?type .
            FILTER(?type IN (cs:Layer, cs:Domain, cs:Term))
        }
        GROUP BY ?type
        """
        
        count_results = graph_service.sparql_query(count_query)
        print("\n=== ENTITY COUNTS BY TYPE ===")
        for result in count_results:
            print(f"{result.get('type', 'Unknown')}: {result.get('count', 0)}")
        
        # Query to find all terms
        terms_query = """
        PREFIX cs: <http://context-studio.local/vocab/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?term ?title ?definition WHERE {
            ?term a cs:Term ;
                  rdfs:label ?title ;
                  rdfs:comment ?definition .
        }
        LIMIT 5
        """
        
        terms_results = graph_service.sparql_query(terms_query)
        print("\n=== SAMPLE TERMS ===")
        for term in terms_results:
            print(f"Term: {term.get('title', 'N/A')}")
            print(f"Definition: {term.get('definition', 'N/A')[:100]}...")
            print("---")
        
        # Test 3: NetworkX analytics
        logger.info("Test 3: Running NetworkX analytics...")
        
        # Calculate centrality
        try:
            centrality = graph_service.calculate_centrality("pagerank")
            print("\n=== TOP 5 NODES BY PAGERANK CENTRALITY ===")
            sorted_centrality = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
            for node, score in sorted_centrality[:5]:
                print(f"{node}: {score:.6f}")
        except Exception as e:
            print(f"Centrality calculation failed: {e}")
        
        # Detect communities
        try:
            communities = graph_service.detect_communities("louvain")
            print(f"\n=== COMMUNITY DETECTION ===")
            print(f"Found {len(communities)} communities")
            for i, community in enumerate(communities[:3]):  # Show first 3 communities
                print(f"Community {i+1}: {len(community)} nodes")
                print(f"Sample nodes: {community[:5]}")
        except Exception as e:
            print(f"Community detection failed: {e}")
        
        # Test 4: Search functionality
        logger.info("Test 4: Testing search functionality...")
        
        # Search for terms (this will work if there are terms in the database)
        try:
            search_results = graph_service.find_terms_by_title("test", exact=False)
            print(f"\n=== SEARCH RESULTS FOR 'test' ===")
            print(f"Found {len(search_results)} matching terms")
            for result in search_results[:3]:
                print(f"- {result.get('title', 'N/A')}")
        except Exception as e:
            print(f"Search failed: {e}")
        
        # Test 5: Export capabilities
        logger.info("Test 5: Testing export capabilities...")
        
        try:
            # Export as Turtle RDF
            turtle_export = graph_service.serialize_rdf("turtle")
            print(f"\n=== RDF EXPORT (TURTLE) - First 500 chars ===")
            print(turtle_export[:500] + "..." if len(turtle_export) > 500 else turtle_export)
        except Exception as e:
            print(f"RDF export failed: {e}")
        
        # Test 6: Hierarchy analysis (if terms exist)
        logger.info("Test 6: Testing hierarchy analysis...")
        
        # Get all domain hierarchy
        try:
            hierarchy = graph_service.get_domain_hierarchy()
            print(f"\n=== DOMAIN HIERARCHY ===")
            print(f"Found {len(hierarchy)} domain-layer relationships")
            for rel in hierarchy[:5]:  # Show first 5
                print(f"Domain: {rel.get('domainTitle', 'N/A')} -> Layer: {rel.get('layerTitle', 'N/A')}")
        except Exception as e:
            print(f"Hierarchy analysis failed: {e}")
        
        logger.info("Graph services test completed successfully!")
        
        session.close()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


def test_individual_services():
    """Test individual SPARQL and NetworkX services."""
    logger.info("Testing individual services...")
    
    try:
        engine = get_engine()
        init_db(engine)
        SessionLocal = get_session_local(engine)
        session = SessionLocal()
        
        from graph.sparql_service import SPARQLService
        from graph.network_service import NetworkService
        
        # Test SPARQL service
        logger.info("Testing SPARQL service...")
        sparql_service = SPARQLService(session)
        sparql_stats = sparql_service.get_graph_stats()
        print(f"\n=== SPARQL SERVICE STATS ===")
        print(f"Total triples: {sparql_stats['total_triples']}")
        print(f"Total subjects: {sparql_stats['total_subjects']}")
        print(f"Total predicates: {sparql_stats['total_predicates']}")
        
        # Test NetworkX service
        logger.info("Testing NetworkX service...")
        network_service = NetworkService(session)
        network_stats = network_service.get_graph_stats()
        print(f"\n=== NETWORKX SERVICE STATS ===")
        print(f"Total nodes: {network_stats['total_nodes']}")
        print(f"Total edges: {network_stats['total_edges']}")
        print(f"Node types: {network_stats.get('node_types', {})}")
        print(f"Edge types: {network_stats.get('edge_types', {})}")
        
        session.close()
        
    except Exception as e:
        logger.error(f"Individual services test failed: {e}")
        raise


if __name__ == "__main__":
    print("Context Studio Graph Services Test")
    print("===================================")
    
    try:
        # Test individual services first
        test_individual_services()
        
        print("\n" + "="*50)
        
        # Test combined services
        test_graph_services()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        sys.exit(1)
