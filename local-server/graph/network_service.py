"""
NetworkX Graph Service for Context Studio

This module provides graph analytics capabilities using NetworkX alongside
the SPARQL service for comprehensive graph operations.
"""

import networkx as nx
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Tuple, Optional, Set
import json
from datetime import datetime

from database.models import Layer, Domain, Term, TermRelationship
from utils.logger import get_logger

logger = get_logger(__name__)


class NetworkService:
    """
    NetworkX-based graph service for advanced graph analytics and algorithms.
    Works alongside the SPARQL service to provide comprehensive graph capabilities.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize the NetworkX service with a database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
        self.graph = nx.DiGraph()  # Directed graph for hierarchical relationships
        self._build_graph()
    
    def _build_graph(self):
        """Build the NetworkX graph from SQLite database data."""
        logger.info("Building NetworkX graph from database...")
        
        # Clear existing graph
        self.graph.clear()
        
        # Add nodes and edges
        self._add_layer_nodes()
        self._add_domain_nodes()
        self._add_term_nodes()
        self._add_hierarchical_edges()
        self._add_relationship_edges()
        
        logger.info(f"NetworkX graph built with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
    
    def _add_layer_nodes(self):
        """Add layer nodes to the graph."""
        layers = self.db_session.query(Layer).all()
        
        for layer in layers:
            node_id = f"layer:{layer.id}"
            self.graph.add_node(
                node_id,
                type="layer",
                title=layer.title,
                definition=layer.definition,
                primary_predicate=layer.primary_predicate,
                created_at=layer.created_at,
                version=layer.version,
                entity_id=layer.id
            )
    
    def _add_domain_nodes(self):
        """Add domain nodes to the graph."""
        domains = self.db_session.query(Domain).all()
        
        for domain in domains:
            node_id = f"domain:{domain.id}"
            self.graph.add_node(
                node_id,
                type="domain",
                title=domain.title,
                definition=domain.definition,
                layer_id=domain.layer_id,
                created_at=domain.created_at,
                version=domain.version,
                entity_id=domain.id
            )
    
    def _add_term_nodes(self):
        """Add term nodes to the graph."""
        terms = self.db_session.query(Term).all()
        
        for term in terms:
            node_id = f"term:{term.id}"
            self.graph.add_node(
                node_id,
                type="term",
                title=term.title,
                definition=term.definition,
                domain_id=term.domain_id,
                layer_id=term.layer_id,
                parent_term_id=term.parent_term_id,
                created_at=term.created_at,
                version=term.version,
                entity_id=term.id
            )
    
    def _add_hierarchical_edges(self):
        """Add hierarchical edges between layers, domains, and terms."""
        # Domain -> Layer edges
        domains = self.db_session.query(Domain).all()
        for domain in domains:
            domain_node = f"domain:{domain.id}"
            layer_node = f"layer:{domain.layer_id}"
            
            layer = self.db_session.query(Layer).filter(Layer.id == domain.layer_id).first()
            predicate = layer.primary_predicate if layer and layer.primary_predicate else "is_a"
            
            self.graph.add_edge(
                domain_node, layer_node,
                type="hierarchical",
                predicate=predicate,
                relationship="belongs_to"
            )
        
        # Term -> Domain edges
        terms = self.db_session.query(Term).all()
        for term in terms:
            term_node = f"term:{term.id}"
            domain_node = f"domain:{term.domain_id}"
            
            layer = self.db_session.query(Layer).filter(Layer.id == term.layer_id).first()
            predicate = layer.primary_predicate if layer and layer.primary_predicate else "is_a"
            
            self.graph.add_edge(
                term_node, domain_node,
                type="hierarchical",
                predicate=predicate,
                relationship="belongs_to"
            )
            
            # Term -> Parent Term edges
            if term.parent_term_id:
                parent_node = f"term:{term.parent_term_id}"
                self.graph.add_edge(
                    term_node, parent_node,
                    type="hierarchical",
                    predicate=predicate,
                    relationship="child_of"
                )
    
    def _add_relationship_edges(self):
        """Add term relationship edges to the graph."""
        relationships = self.db_session.query(TermRelationship).all()
        
        for rel in relationships:
            source_node = f"term:{rel.source_term_id}"
            target_node = f"term:{rel.target_term_id}"
            
            self.graph.add_edge(
                source_node, target_node,
                type="relationship",
                predicate=rel.predicate,
                relationship="related_to",
                created_at=rel.created_at
            )
    
    def refresh(self):
        """Refresh the NetworkX graph from the database."""
        logger.info("Refreshing NetworkX graph from database...")
        self._build_graph()
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the NetworkX graph.
        
        Returns:
            Dictionary with graph statistics
        """
        # Basic stats
        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "is_directed": self.graph.is_directed(),
            "is_connected": nx.is_weakly_connected(self.graph) if self.graph.is_directed() else nx.is_connected(self.graph),
            "last_updated": datetime.now().isoformat()
        }
        
        # Node type counts
        node_types = {}
        for node, data in self.graph.nodes(data=True):
            node_type = data.get('type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1
        stats["node_types"] = node_types
        
        # Edge type counts
        edge_types = {}
        for source, target, data in self.graph.edges(data=True):
            edge_type = data.get('type', 'unknown')
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        stats["edge_types"] = edge_types
        
        # Connected components
        if self.graph.is_directed():
            stats["weakly_connected_components"] = nx.number_weakly_connected_components(self.graph)
            stats["strongly_connected_components"] = nx.number_strongly_connected_components(self.graph)
        else:
            stats["connected_components"] = nx.number_connected_components(self.graph)
        
        return stats
    
    def find_shortest_path(self, source_id: str, target_id: str, source_type: str = "term", target_type: str = "term") -> Optional[List[str]]:
        """
        Find the shortest path between two nodes.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            source_type: Type of source entity (layer, domain, term)
            target_type: Type of target entity (layer, domain, term)
            
        Returns:
            List of node IDs representing the shortest path, or None if no path exists
        """
        source_node = f"{source_type}:{source_id}"
        target_node = f"{target_type}:{target_id}"
        
        try:
            return nx.shortest_path(self.graph, source_node, target_node)
        except nx.NetworkXNoPath:
            return None
    
    def get_neighbors(self, entity_id: str, entity_type: str = "term", depth: int = 1, direction: str = "both") -> Dict[str, List[str]]:
        """
        Get neighbors of a node at specified depth.
        
        Args:
            entity_id: Entity ID
            entity_type: Type of entity (layer, domain, term)
            depth: Maximum depth to traverse
            direction: Direction to traverse ("in", "out", "both")
            
        Returns:
            Dictionary with neighbors organized by depth
        """
        node_id = f"{entity_type}:{entity_id}"
        
        if node_id not in self.graph:
            return {}
        
        neighbors_by_depth = {}
        current_level = {node_id}
        visited = {node_id}
        
        for d in range(1, depth + 1):
            next_level = set()
            
            for node in current_level:
                if direction in ["out", "both"]:
                    # Outgoing neighbors
                    next_level.update(self.graph.successors(node))
                
                if direction in ["in", "both"]:
                    # Incoming neighbors
                    next_level.update(self.graph.predecessors(node))
            
            # Remove already visited nodes
            next_level = next_level - visited
            
            if next_level:
                neighbors_by_depth[f"depth_{d}"] = list(next_level)
                visited.update(next_level)
                current_level = next_level
            else:
                break
        
        return neighbors_by_depth
    
    def calculate_centrality(self, method: str = "pagerank") -> Dict[str, float]:
        """
        Calculate node centrality using various algorithms.
        
        Args:
            method: Centrality method ("pagerank", "betweenness", "closeness", "degree")
            
        Returns:
            Dictionary mapping node IDs to centrality scores
        """
        if method == "pagerank":
            return nx.pagerank(self.graph)
        elif method == "betweenness":
            return nx.betweenness_centrality(self.graph)
        elif method == "closeness":
            return nx.closeness_centrality(self.graph)
        elif method == "degree":
            return nx.degree_centrality(self.graph)
        else:
            raise ValueError(f"Unknown centrality method: {method}")
    
    def detect_communities(self, method: str = "louvain") -> List[Set[str]]:
        """
        Detect communities in the graph.
        
        Args:
            method: Community detection method ("louvain", "label_propagation")
            
        Returns:
            List of sets, each containing node IDs in a community
        """
        # Convert to undirected graph for community detection
        undirected_graph = self.graph.to_undirected()
        
        if method == "louvain":
            import networkx.algorithms.community as nx_comm
            return list(nx_comm.louvain_communities(undirected_graph))
        elif method == "label_propagation":
            import networkx.algorithms.community as nx_comm
            return list(nx_comm.label_propagation_communities(undirected_graph))
        else:
            raise ValueError(f"Unknown community detection method: {method}")
    
    def find_terms_in_domain_tree(self, domain_id: str) -> List[str]:
        """
        Find all terms that belong to a domain or its sub-domains.
        
        Args:
            domain_id: Domain ID to search from
            
        Returns:
            List of term IDs in the domain tree
        """
        domain_node = f"domain:{domain_id}"
        
        if domain_node not in self.graph:
            return []
        
        # Find all terms that have a path to this domain
        terms = []
        for node in self.graph.nodes():
            if node.startswith("term:"):
                try:
                    path = nx.shortest_path(self.graph, node, domain_node)
                    if path:  # If there's a path, the term belongs to this domain tree
                        term_id = node.split(":", 1)[1]
                        terms.append(term_id)
                except nx.NetworkXNoPath:
                    continue
        
        return terms
    
    def get_term_hierarchy(self, term_id: str) -> Dict[str, Any]:
        """
        Get the full hierarchy for a term (ancestors and descendants).
        
        Args:
            term_id: Term ID
            
        Returns:
            Dictionary with ancestors and descendants
        """
        term_node = f"term:{term_id}"
        
        if term_node not in self.graph:
            return {"ancestors": [], "descendants": []}
        
        # Find ancestors (nodes that have a path to this term)
        ancestors = []
        descendants = []
        
        for node in self.graph.nodes():
            try:
                # Check if there's a path from node to term (node is ancestor)
                path = nx.shortest_path(self.graph, node, term_node)
                if len(path) > 1:  # Don't include the term itself
                    node_data = self.graph.nodes[node]
                    ancestors.append({
                        "id": node.split(":", 1)[1],
                        "type": node_data.get("type"),
                        "title": node_data.get("title"),
                        "distance": len(path) - 1
                    })
            except nx.NetworkXNoPath:
                pass
            
            try:
                # Check if there's a path from term to node (node is descendant)
                path = nx.shortest_path(self.graph, term_node, node)
                if len(path) > 1:  # Don't include the term itself
                    node_data = self.graph.nodes[node]
                    descendants.append({
                        "id": node.split(":", 1)[1],
                        "type": node_data.get("type"),
                        "title": node_data.get("title"),
                        "distance": len(path) - 1
                    })
            except nx.NetworkXNoPath:
                pass
        
        # Sort by distance
        ancestors.sort(key=lambda x: x["distance"])
        descendants.sort(key=lambda x: x["distance"])
        
        return {
            "ancestors": ancestors,
            "descendants": descendants
        }
    
    def export_to_graphml(self, filepath: str):
        """
        Export the graph to GraphML format for visualization tools.
        
        Args:
            filepath: Path to save the GraphML file
        """
        nx.write_graphml(self.graph, filepath)
        logger.info(f"Graph exported to {filepath}")
    
    def get_node_info(self, entity_id: str, entity_type: str = "term") -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific node.
        
        Args:
            entity_id: Entity ID
            entity_type: Type of entity (layer, domain, term)
            
        Returns:
            Node information dictionary or None if not found
        """
        node_id = f"{entity_type}:{entity_id}"
        
        if node_id not in self.graph:
            return None
        
        node_data = dict(self.graph.nodes[node_id])
        
        # Add network metrics
        node_data.update({
            "in_degree": self.graph.in_degree(node_id),
            "out_degree": self.graph.out_degree(node_id),
            "neighbors": {
                "predecessors": list(self.graph.predecessors(node_id)),
                "successors": list(self.graph.successors(node_id))
            }
        })
        
        return node_data
