"""
NetworkX-based implementation of the GraphEngine port.

Provides structural graph analysis using NetworkX as the underlying graph library,
supporting shortest path queries, centrality analysis, community detection, and
cycle detection for directed graphs.
"""

from __future__ import annotations

from typing import Any, Sequence

import networkx as nx

from domain.graph.exceptions import CommunityDetectionError, NodeNotFoundError


class NetworkXGraphEngine:
    """
    Graph engine implementation using NetworkX DiGraph for directed graph operations.

    This engine provides the GraphEngine protocol interface by wrapping a NetworkX
    directed graph and dispatching operations to the appropriate NetworkX functions.
    """

    def __init__(self) -> None:
        """Initialize the NetworkX graph engine with an empty directed graph."""
        self._graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]

    def build_from_data(
        self, nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]]
    ) -> None:
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

        Raises:
            NodeNotFoundError: If either source_id or target_id does not exist in the graph
        """
        # Verify both nodes exist in the graph
        if source_id not in self._graph:
            raise NodeNotFoundError(source_id)
        if target_id not in self._graph:
            raise NodeNotFoundError(target_id)

        try:
            path = nx.shortest_path(self._graph, source_id, target_id)
            return list(path)
        except nx.NetworkXNoPath:
            # No path exists between the two nodes
            return None

    def all_paths(self, source_id: str, target_id: str, max_depth: int = 5) -> list[list[str]]:
        """
        Find all simple paths between two nodes up to a maximum depth.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node
            max_depth: Maximum path length to explore (default 5). This is the maximum number
                      of edges in any path (NetworkX's cutoff parameter).

        Returns:
            List of paths, where each path is an ordered list of node IDs

        Raises:
            NodeNotFoundError: If either source_id or target_id does not exist in the graph
        """
        # Verify both nodes exist in the graph
        if source_id not in self._graph:
            raise NodeNotFoundError(source_id)
        if target_id not in self._graph:
            raise NodeNotFoundError(target_id)

        try:
            # cutoff parameter in nx.all_simple_paths means paths with length <= cutoff edges
            # max_depth is the max number of edges, so we pass it directly as cutoff
            paths = nx.all_simple_paths(self._graph, source_id, target_id, cutoff=max_depth)
            return [list(path) for path in paths]
        except nx.NetworkXNoPath:
            # No paths exist between the two nodes
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

    def in_degree_distribution(self) -> dict[str, int]:
        """
        Get the in-degree of each node.

        Returns:
            Dictionary mapping node ID (str) to in-degree (int)
        """
        return dict(self._graph.in_degree())

    def out_degree_distribution(self) -> dict[str, int]:
        """
        Get the out-degree of each node.

        Returns:
            Dictionary mapping node ID (str) to out-degree (int)
        """
        return dict(self._graph.out_degree())

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
            CommunityDetectionError: If community detection fails (e.g., empty graph)
        """
        try:
            if algorithm == "louvain":
                louvain_communities = nx.community.louvain_communities(self._graph)
                return list(louvain_communities)
            elif algorithm == "label_propagation":
                # Label propagation requires an undirected graph
                undirected_graph = self._graph.to_undirected()
                label_communities = nx.community.label_propagation_communities(undirected_graph)
                return list(label_communities)
            else:
                raise ValueError(f"Unknown community detection algorithm: {algorithm}")
        except (ZeroDivisionError, nx.NetworkXError) as e:
            raise CommunityDetectionError(
                "Cannot detect communities in an empty or edgeless graph"
            ) from e

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

    def neighbors(self, node_id: str, direction: str = "both", depth: int = 1) -> set[str]:
        """
        Get all neighbors of a node up to a specified depth with optional directional filtering.

        Performs a breadth-first traversal from the specified node, collecting all nodes
        within the specified depth (excluding the center node itself).

        Args:
            node_id: ID of the center node
            direction: Direction of traversal: "in" (predecessors), "out" (successors), "both"
            (default)
            depth: Maximum distance from center node (default 1). Depth 1 returns immediate
            neighbors,
                   depth 2 returns two hops away, etc.

        Returns:
            Set of neighboring node IDs at the specified depth (excludes the center node)

        Raises:
            NodeNotFoundError: If node_id does not exist in the graph
        """
        # Verify node exists in the graph
        if node_id not in self._graph:
            raise NodeNotFoundError(node_id)

        if depth < 1:
            return set()

        neighbors_set: set[str] = set()
        visited: set[str] = {node_id}  # Track visited nodes to avoid revisiting
        current_level = {node_id}  # Nodes at current depth level

        for _ in range(depth):
            next_level: set[str] = set()

            for current_node in current_level:
                if direction in ("out", "both"):
                    # Successors: nodes that this node points to
                    successors = set(self._graph.successors(current_node))
                    next_level.update(successors - visited)

                if direction in ("in", "both"):
                    # Predecessors: nodes that point to this node
                    predecessors = set(self._graph.predecessors(current_node))
                    next_level.update(predecessors - visited)

            # Mark newly discovered nodes as visited
            visited.update(next_level)
            # Add newly discovered nodes to the result set
            neighbors_set.update(next_level)
            # Move to next level for next iteration
            current_level = next_level

            # If no new nodes discovered, stop
            if not next_level:
                break

        return neighbors_set

    def edges(self) -> list[tuple[str, str]]:
        """
        Get all edges in the graph as (source, target) tuples.

        Returns:
            List of edge tuples, where each tuple is (source_id, target_id)
        """
        return list(self._graph.edges())

    def has_cycle(self, source_id: str, target_id: str) -> bool:
        """
        Check if adding an edge from source_id to target_id would create a cycle.

        This is semantically equivalent to: would adding source -> target create a
        cycle? A cycle exists if:
        - source_id == target_id (self-loop), OR
        - there is already a path from target_id back to source_id in the graph

        Args:
            source_id: ID of the proposed edge source
            target_id: ID of the proposed edge target

        Returns:
            True if adding the edge would create a cycle, False otherwise
        """
        # Self-loop is always a cycle
        if source_id == target_id:
            return True

        # Check if a path already exists from target_id back to source_id
        # If yes, adding source_id -> target_id would create a cycle
        try:
            cycle_exists = nx.has_path(self._graph, target_id, source_id)
        except nx.NodeNotFound:
            # If either node doesn't exist, no cycle can be created
            cycle_exists = False

        return cycle_exists

    def get_edge_data(self, source_id: str, target_id: str) -> dict[str, Any]:
        """
        Get the attributes/properties of a specific edge.

        Args:
            source_id: ID of the edge source node
            target_id: ID of the edge target node

        Returns:
            Dictionary of edge attributes (e.g., property_definition_id), or empty dict if edge
            doesn't exist
        """
        if self._graph.has_edge(source_id, target_id):
            return dict(self._graph[source_id][target_id])
        return {}
