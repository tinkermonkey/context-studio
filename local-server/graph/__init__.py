"""
Graph Data Model Package

This package provides graph-based data modeling and querying capabilities
for the Context Studio using both SPARQL (RDFLib) and NetworkX.

Components:
- sparql_service: SPARQL querying with RDFLib (temporarily disabled for Great Normalization)
- network: Graph analytics with NetworkX  
- graph_service: Combined service interface
"""

# TODO: Re-enable SPARQLService after updating it for unified nodes table
# from .sparql_service import SPARQLService
from .network_service import NetworkService
from .graph_service import GraphService

# TODO: Add SPARQLService back when updated
# __all__ = ["SPARQLService", "NetworkService", "GraphService"]
__all__ = ["NetworkService", "GraphService"]
