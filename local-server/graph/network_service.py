# mypy: ignore-errors
"""
NetworkX Graph Service for Context Studio

This module provides graph analytics capabilities using NetworkX alongside
the SPARQL service for comprehensive graph operations.
"""

import networkx as nx
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from database.models import StructureNode, StructureNodeLink
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
        self.graph: nx.DiGraph[Any] = (
            nx.DiGraph()
        )  # Directed graph for hierarchical relationships
        self._graph_built = False  # Track if graph has been built
        # Don't build graph immediately - use lazy initialization

    def _ensure_graph_built(self):
        """Ensure the graph is built (lazy initialization)."""
        if not self._graph_built:
            self._build_graph()

    def _build_graph(self):
        """Build the NetworkX graph from unified structure_nodes table."""
        logger.info("Building NetworkX graph from unified structure_nodes table...")

        # Clear existing graph
        self.graph.clear()

        # Add all structure_nodes from the unified structure_nodes table
        self._add_unified_nodes()
        self._add_hierarchical_edges()
        self._add_node_link_edges()

        self._graph_built = True
        logger.info(
            f"NetworkX graph built with {self.graph.number_of_nodes()} structure_nodes and {self.graph.number_of_edges()} edges"
        )

    def _add_unified_nodes(self):
        """Add all structure_nodes from the unified structure_nodes table."""
        try:
            structure_nodes = self.db_session.query(StructureNode).all()
        except Exception as e:
            logger.warning(
                f"Failed to query structure_nodes table (may not exist yet): {e}"
            )
            structure_nodes = []

        for structure_node in structure_nodes:
            node_id = f"{structure_node.node_type.value}:{structure_node.id}"
            self.graph.add_node(
                node_id,
                type=structure_node.node_type.value,
                title=structure_node.title,
                definition=structure_node.definition,
                parent_node_id=structure_node.parent_node_id,
                structural_predicate_id=structure_node.structural_predicate_id,
                created_at=structure_node.created_at,
                version=structure_node.version,
                entity_id=structure_node.id,
                last_modified=structure_node.last_modified,
            )

    def _add_hierarchical_edges(self):
        """Add parent-child hierarchical edges."""
        try:
            structure_nodes = self.db_session.query(StructureNode).all()
        except Exception as e:
            logger.warning(
                f"Failed to query structure_nodes for hierarchical edges: {e}"
            )
            return

        for structure_node in structure_nodes:
            if structure_node.parent_node_id:
                parent_node_id = self._get_node_graph_id(structure_node.parent_node_id)
                child_node_id = f"{structure_node.node_type.value}:{structure_node.id}"

                if parent_node_id and self.graph.has_node(parent_node_id):
                    self.graph.add_edge(
                        parent_node_id,
                        child_node_id,
                        type="hierarchy",
                        relationship="parent_child",
                    )

    def _add_node_link_edges(self):
        """Add edges from the structure_node_links table."""
        try:
            links = self.db_session.query(StructureNodeLink).all()
        except Exception as e:
            logger.warning(
                f"Failed to query structure_node_links for node link edges: {e}"
            )
            return

        for link in links:
            source_node_id = self._get_node_graph_id(link.source_node_id)
            target_node_id = self._get_node_graph_id(link.target_node_id)

            if source_node_id and target_node_id:
                self.graph.add_edge(
                    source_node_id,
                    target_node_id,
                    type="structure_node_link",
                    predicate=link.predicate,
                    predicate_id=link.predicate_id,
                    created_at=link.created_at,
                )

    def _get_node_graph_id(self, node_db_id: str) -> Optional[str]:
        """Get the graph structure_node ID from database structure_node ID."""
        structure_node: Optional[StructureNode] = (
            self.db_session.query(StructureNode)
            .filter(StructureNode.id == node_db_id)
            .first()
        )
        if structure_node:
            return f"{structure_node.node_type.value}:{structure_node.id}"
        return None

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
        self._ensure_graph_built()  # Lazy initialization
        # Basic stats
        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "is_directed": self.graph.is_directed(),
            "is_connected": (
                nx.is_weakly_connected(self.graph)
                if self.graph.is_directed()
                else nx.is_connected(self.graph)
            ),
            "last_updated": datetime.now().isoformat(),
        }

        # StructureNode type counts
        node_types: Dict[str, int] = {}
        for structure_node, data in self.graph.nodes(data=True):  # type: ignore
            node_type = data.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        stats["node_types"] = node_types

        # Edge type counts
        edge_types: Dict[str, int] = {}
        for source, target, data in self.graph.edges(data=True):
            edge_type = data.get("type", "unknown")
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        stats["edge_types"] = edge_types

        # Connected components
        if self.graph.is_directed():
            stats["weakly_connected_components"] = (
                nx.number_weakly_connected_components(self.graph)
            )
            stats["strongly_connected_components"] = (
                nx.number_strongly_connected_components(self.graph)
            )
        else:
            stats["connected_components"] = nx.number_connected_components(self.graph)

        return stats

    def find_shortest_path(
        self,
        source_id: str,
        target_id: str,
        source_type: str = "term",
        target_type: str = "term",
    ) -> Optional[List[str]]:
        """
        Find the shortest path between two structure_nodes.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            source_type: Type of source entity (layer, domain, term)
            target_type: Type of target entity (layer, domain, term)

        Returns:
            List of structure_node IDs representing the shortest path, or None if no path exists
        """
        self._ensure_graph_built()  # Lazy initialization
        source_node = f"{source_type}:{source_id}"
        target_node = f"{target_type}:{target_id}"

        try:
            return nx.shortest_path(self.graph, source_node, target_node)
        except nx.NetworkXNoPath:
            return None

    def get_neighbors(
        self,
        entity_id: str,
        entity_type: str = "term",
        depth: int = 1,
        direction: str = "both",
    ) -> Dict[str, List[str]]:
        """
        Get neighbors of a structure_node at specified depth.

        Args:
            entity_id: Entity ID
            entity_type: Type of entity (layer, domain, term)
            depth: Maximum depth to traverse
            direction: Direction to traverse ("in", "out", "both")

        Returns:
            Dictionary with neighbors organized by depth
        """
        self._ensure_graph_built()  # Lazy initialization
        node_id = f"{entity_type}:{entity_id}"

        if node_id not in self.graph:
            return {}

        neighbors_by_depth = {}
        current_level = {node_id}
        visited = {node_id}

        for d in range(1, depth + 1):
            next_level: Set[Any] = set()

            for structure_node in current_level:
                if direction in ["out", "both"]:
                    # Outgoing neighbors
                    next_level.update(self.graph.successors(structure_node))

                if direction in ["in", "both"]:
                    # Incoming neighbors
                    next_level.update(self.graph.predecessors(structure_node))

            # Remove already visited structure_nodes
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
        Calculate structure_node centrality using various algorithms.

        Args:
            method: Centrality method ("pagerank", "betweenness", "closeness", "degree")

        Returns:
            Dictionary mapping structure_node IDs to centrality scores
        """
        self._ensure_graph_built()  # Lazy initialization
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
            List of sets, each containing structure_node IDs in a community
        """
        self._ensure_graph_built()  # Lazy initialization
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

        # Find all structure_nodes that can reach this domain (terms that belong to this domain)
        # Since edges go from child to parent, we use nx.ancestors to find terms
        # that have a path to this domain
        ancestor_nodes = nx.ancestors(self.graph, domain_node)

        # Filter to only term structure_nodes
        terms = []
        for structure_node in ancestor_nodes:
            if structure_node.startswith("term:"):
                term_id = structure_node.split(":", 1)[1]
                terms.append(term_id)

        return terms

    def get_node_hierarchy(
        self, node_id: str, node_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get the full hierarchy for any structure node (ancestors and descendants).
        This is node-type agnostic.

        Args:
            node_id: Node ID
            node_type: Node type (layer, domain, term). If not provided, will try all types.

        Returns:
            Dictionary with ancestors and descendants
        """
        # Try to find the node in the graph
        if node_type:
            graph_node_id = f"{node_type}:{node_id}"
            if graph_node_id not in self.graph:
                return {"ancestors": [], "descendants": []}
        else:
            # Try all types if not specified
            graph_node_id = None
            for ntype in ["layer", "domain", "term"]:
                candidate = f"{ntype}:{node_id}"
                if candidate in self.graph:
                    graph_node_id = candidate
                    break

            if not graph_node_id:
                return {"ancestors": [], "descendants": []}

        # Use NetworkX built-in functions to find ancestors and descendants
        # In our graph structure, edges go from parent to child (see _add_hierarchical_edges), so:
        # - Ancestors are nodes that can reach this node (ancestors in NetworkX terms)
        # - Descendants are reachable by following outgoing edges (descendants in NetworkX terms)

        ancestor_nodes = nx.ancestors(self.graph, graph_node_id)
        descendant_nodes = nx.descendants(self.graph, graph_node_id)

        # Build ancestor list with distances
        ancestors = []
        for structure_node in ancestor_nodes:
            node_data = self.graph.nodes[structure_node]
            try:
                # Distance from ancestor to node (following parent→child edges)
                distance = nx.shortest_path_length(
                    self.graph, structure_node, graph_node_id
                )
                ancestors.append(
                    {
                        "id": structure_node.split(":", 1)[1],
                        "type": node_data.get("type"),
                        "title": node_data.get("title"),
                        "definition": node_data.get("definition"),
                        "parent_node_id": node_data.get("parent_node_id"),
                        "distance": distance,
                    }
                )
            except nx.NetworkXNoPath:
                # This shouldn't happen since we got the structure_node from ancestors
                continue

        # Build descendant list with distances
        descendants = []
        for structure_node in descendant_nodes:
            node_data = self.graph.nodes[structure_node]
            try:
                # Distance from node to descendant (following parent→child edges)
                distance = nx.shortest_path_length(
                    self.graph, graph_node_id, structure_node
                )
                descendants.append(
                    {
                        "id": structure_node.split(":", 1)[1],
                        "type": node_data.get("type"),
                        "title": node_data.get("title"),
                        "definition": node_data.get("definition"),
                        "parent_node_id": node_data.get("parent_node_id"),
                        "distance": distance,
                    }
                )
            except nx.NetworkXNoPath:
                # This shouldn't happen since we got the structure_node from descendants
                continue

        # Sort by distance
        ancestors.sort(key=lambda x: x["distance"])
        descendants.sort(key=lambda x: x["distance"])

        return {"ancestors": ancestors, "descendants": descendants}

    def get_term_hierarchy(self, term_id: str) -> Dict[str, Any]:
        """
        Get the full hierarchy for a term (backwards compatibility wrapper).

        Args:
            term_id: Term ID

        Returns:
            Dictionary with ancestors and descendants
        """
        return self.get_node_hierarchy(term_id, "term")

    def export_to_graphml(self, filepath: str):
        """
        Export the graph to GraphML format for visualization tools.

        Args:
            filepath: Path to save the GraphML file
        """
        self._ensure_graph_built()  # Lazy initialization
        nx.write_graphml(self.graph, filepath)
        logger.info(f"Graph exported to {filepath}")

    def get_node_info(
        self, entity_id: str, entity_type: str = "term"
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific structure_node.

        Args:
            entity_id: Entity ID
            entity_type: Type of entity (layer, domain, term)

        Returns:
            StructureNode information dictionary or None if not found
        """
        self._ensure_graph_built()  # Lazy initialization
        node_id = f"{entity_type}:{entity_id}"

        if node_id not in self.graph:
            return None

        node_data = dict(self.graph.structure_nodes[node_id])

        # Add network metrics
        node_data.update(
            {
                "in_degree": self.graph.in_degree(node_id),
                "out_degree": self.graph.out_degree(node_id),
                "neighbors": {
                    "predecessors": list(self.graph.predecessors(node_id)),
                    "successors": list(self.graph.successors(node_id)),
                },
            }
        )

        return node_data
