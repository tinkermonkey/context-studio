"""
NetworkX-based implementation of the GraphEngine port.

Provides structural graph analysis using NetworkX as the underlying graph library,
supporting shortest path queries, centrality analysis, community detection, and
cycle detection for directed graphs.
"""

from __future__ import annotations

import networkx as nx
from typing import Sequence


class NetworkXGraphEngine:
    """
    Graph engine implementation using NetworkX DiGraph for directed graph operations.

    This engine provides the GraphEngine protocol interface by wrapping a NetworkX
    directed graph and dispatching operations to the appropriate NetworkX functions.
    """

    def __init__(self) -> None:
        """Initialize the NetworkX graph engine with an empty directed graph."""
        self._graph = nx.DiGraph()

    def build_from_data(self, nodes: Sequence[dict], edges: Sequence[dict]) -> None:
        """
        Construct the graph from node and edge data.

        Clears any existing graph and builds a new one from scratch.

        Args:
            nodes: Sequence of node dictionaries. Each dict should contain at least
                   'id' (str) and may contain other attributes (title, node_type, etc.)
            edges: Sequence of edge dictionaries. Each dict should contain at least
                   'source_id' (str), 'target_id' (str), and may contain other
                   attributes (property_definition_id, etc.)
        """
        self._graph.clear()

        # Add nodes with attributes
        for node in nodes:
            node_id = node["id"]
            node_attrs = {k: v for k, v in node.items() if k != "id"}
            self._graph.add_node(node_id, **node_attrs)

        # Add edges with attributes
        for edge in edges:
            source_id = edge["source_id"]
            target_id = edge["target_id"]
            edge_attrs = {k: v for k, v in edge.items() if k not in ("source_id", "target_id")}
            self._graph.add_edge(source_id, target_id, **edge_attrs)

    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return self._graph.number_of_edges()

    def shortest_path(self, source_id: str, target_id: str) -> list[str] | None:
        """
        Find the shortest path between two nodes.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node

        Returns:
            Ordered list of node IDs from source to target (inclusive),
            or None if no path exists
        """
        try:
            path = nx.shortest_path(self._graph, source_id, target_id)
            return list(path)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def all_paths(self, source_id: str, target_id: str, max_depth: int = 5) -> list[list[str]]:
        """
        Find all simple paths between two nodes up to a maximum depth.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node
            max_depth: Maximum path length to explore (default 5)

        Returns:
            List of paths, where each path is an ordered list of node IDs
        """
        try:
            paths = nx.all_simple_paths(self._graph, source_id, target_id, cutoff=max_depth - 1)
            return [list(path) for path in paths]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def centrality(self, algorithm: str = "betweenness") -> dict[str, float]:
        """
        Compute centrality scores for all nodes using the specified algorithm.

        Args:
            algorithm: Name of the centrality algorithm ("pagerank", "betweenness",
                      "closeness", "degree")

        Returns:
            Dictionary mapping node ID (str) to centrality score (float)

        Raises:
            ValueError: If algorithm is not recognized
        """
        if algorithm == "pagerank":
            return dict(nx.pagerank(self._graph))
        elif algorithm == "betweenness":
            return dict(nx.betweenness_centrality(self._graph))
        elif algorithm == "closeness":
            return dict(nx.closeness_centrality(self._graph))
        elif algorithm == "degree":
            return dict(nx.degree_centrality(self._graph))
        else:
            raise ValueError(f"Unknown centrality algorithm: {algorithm}")

    def degree_distribution(self) -> dict[str, int]:
        """
        Get the degree of each node.

        For a directed graph, this returns the total degree (in-degree + out-degree).

        Returns:
            Dictionary mapping node ID (str) to degree (int)
        """
        return dict(self._graph.degree())

    def connected_components(self) -> int:
        """
        Count the number of connected components in the graph.

        For a directed graph, this counts weakly connected components.

        Returns:
            Number of connected components (isolated nodes count as separate components)
        """
        return nx.number_weakly_connected_components(self._graph)

    def communities(self, algorithm: str = "louvain") -> list[set[str]]:
        """
        Partition the graph into communities using the specified algorithm.

        Args:
            algorithm: Name of the community detection algorithm ("louvain", "label_propagation")

        Returns:
            List of communities, where each community is a set of node IDs

        Raises:
            ValueError: If algorithm is not recognized
        """
        if algorithm == "louvain":
            communities_generator = nx.community.louvain_communities(self._graph)
            return [set(community) for community in communities_generator]
        elif algorithm == "label_propagation":
            # Label propagation requires an undirected graph
            undirected_graph = self._graph.to_undirected()
            communities_generator = nx.community.label_propagation_communities(undirected_graph)
            return [set(community) for community in communities_generator]
        else:
            raise ValueError(f"Unknown community detection algorithm: {algorithm}")

    def subgraph(self, node_ids: Sequence[str]) -> NetworkXGraphEngine:
        """
        Extract a subgraph containing only the specified nodes and edges between them.

        Args:
            node_ids: IDs of nodes to include in the subgraph

        Returns:
            A new NetworkXGraphEngine instance wrapping the subgraph
        """
        subgraph_instance = NetworkXGraphEngine()
        # Create a subgraph view and copy it to a new DiGraph
        subgraph_view = self._graph.subgraph(node_ids)
        subgraph_instance._graph = nx.DiGraph(subgraph_view)
        return subgraph_instance

    def neighbors(self, node_id: str, direction: str = "both") -> set[str]:
        """
        Get all neighbors of a node with optional directional filtering.

        Args:
            node_id: ID of the node
            direction: Direction of traversal: "in" (predecessors), "out" (successors), "both" (default)

        Returns:
            Set of neighboring node IDs
        """
        neighbors_set = set()

        if direction in ("out", "both"):
            # Successors: nodes that this node points to
            neighbors_set.update(self._graph.successors(node_id))

        if direction in ("in", "both"):
            # Predecessors: nodes that point to this node
            neighbors_set.update(self._graph.predecessors(node_id))

        return neighbors_set

    def has_cycle(self, source_id: str, target_id: str) -> bool:
        """
        Check if adding an edge from source_id to target_id would create a cycle.

        This is semantically equivalent to: would adding source -> target create a
        reverse path from target back to source?

        Args:
            source_id: ID of the proposed edge source
            target_id: ID of the proposed edge target

        Returns:
            True if adding the edge would create a cycle, False otherwise
        """
        # Temporarily add the edge
        self._graph.add_edge(source_id, target_id)

        # Check if a reverse path exists (would indicate a cycle)
        try:
            cycle_exists = nx.has_path(self._graph, target_id, source_id)
        except nx.NodeNotFound:
            cycle_exists = False
        finally:
            # Remove the temporary edge
            self._graph.remove_edge(source_id, target_id)

        return cycle_exists
