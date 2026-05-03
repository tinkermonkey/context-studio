"""Fake in-memory implementation of GraphEngine for testing.

Provides a simple in-memory graph engine implementation for unit testing.
Uses plain dictionaries and lists to store nodes and edges, supporting
all GraphEngine protocol methods with straightforward implementations.
"""

import sys
import os
from typing import Any

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.graph.exceptions import NodeNotFoundError


class FakeGraphEngine:
    """In-memory implementation of GraphEngine protocol for unit testing."""

    def __init__(self) -> None:
        """Initialize the fake graph engine with empty storage."""
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []

    def build_from_data(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> None:
        """
        Construct the graph from node and edge data.

        Args:
            nodes: Sequence of node dictionaries with at least 'id' key
            edges: Sequence of edge dictionaries with 'source_id' and 'target_id' keys
        """
        self._nodes = {}
        self._edges = []

        # Store nodes as dict keyed by id
        for node in nodes:
            self._nodes[node["id"]] = node

        # Store edges as list
        self._edges = list(edges)

    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self._nodes)

    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return len(self._edges)

    def shortest_path(self, source_id: str, target_id: str) -> list[str] | None:
        """
        Find the shortest path between two nodes.

        For the fake implementation, returns [source_id, target_id] if both nodes
        exist and are connected, otherwise None. Raises NodeNotFoundError if either
        node does not exist.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node

        Returns:
            List [source_id, target_id] if both exist and connected, None otherwise

        Raises:
            NodeNotFoundError: If source_id or target_id does not exist
        """
        if source_id not in self._nodes:
            raise NodeNotFoundError(source_id)
        if target_id not in self._nodes:
            raise NodeNotFoundError(target_id)

        # For the fake, assume direct connection if both nodes exist
        # In a real implementation, this would use BFS/Dijkstra
        return [source_id, target_id]

    def all_paths(
        self, source_id: str, target_id: str, max_depth: int = 5
    ) -> list[list[str]]:
        """
        Find all simple paths between two nodes up to a maximum depth.

        For the fake implementation, returns [[source_id, target_id]] if both nodes
        exist and are connected, otherwise empty list. Raises NodeNotFoundError if
        either node does not exist.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node
            max_depth: Maximum path length to explore (unused in fake)

        Returns:
            List containing single path [[source_id, target_id]] if both exist and connected, else []

        Raises:
            NodeNotFoundError: If source_id or target_id does not exist
        """
        if source_id not in self._nodes:
            raise NodeNotFoundError(source_id)
        if target_id not in self._nodes:
            raise NodeNotFoundError(target_id)

        # For the fake, assume direct connection if both nodes exist
        # Return single path [[source_id, target_id]]
        return [[source_id, target_id]]

    def centrality(self, algorithm: str = "betweenness") -> dict[str, float]:
        """
        Compute centrality scores for all nodes.

        For the fake implementation, returns uniform centrality score
        (1.0 / node_count) for each node, regardless of algorithm.

        Args:
            algorithm: Name of the centrality algorithm (unused in fake)

        Returns:
            Dictionary mapping node ID to centrality score
        """
        if not self._nodes:
            return {}
        score = 1.0 / len(self._nodes)
        return {node_id: score for node_id in self._nodes}

    def degree_distribution(self) -> dict[str, int]:
        """
        Get the degree of each node.

        For a directed graph, returns the total degree (in-degree + out-degree) for each node.

        Returns:
            Dictionary mapping node ID to degree (int)
        """
        degree_dict = {node_id: 0 for node_id in self._nodes}

        # Count in-degree and out-degree for each node
        for edge in self._edges:
            source_id = edge["source_id"]
            target_id = edge["target_id"]

            # Out-degree for source
            if source_id in degree_dict:
                degree_dict[source_id] += 1

            # In-degree for target
            if target_id in degree_dict:
                degree_dict[target_id] += 1

        return degree_dict

    def in_degree_distribution(self) -> dict[str, int]:
        """
        Get the in-degree of each node.

        For a directed graph, in-degree is the number of edges pointing to a node.

        Returns:
            Dictionary mapping node ID to in-degree (int)
        """
        in_degree_dict = {node_id: 0 for node_id in self._nodes}

        # Count in-degree for each node
        for edge in self._edges:
            target_id = edge["target_id"]
            if target_id in in_degree_dict:
                in_degree_dict[target_id] += 1

        return in_degree_dict

    def out_degree_distribution(self) -> dict[str, int]:
        """
        Get the out-degree of each node.

        For a directed graph, out-degree is the number of edges pointing from a node.

        Returns:
            Dictionary mapping node ID to out-degree (int)
        """
        out_degree_dict = {node_id: 0 for node_id in self._nodes}

        # Count out-degree for each node
        for edge in self._edges:
            source_id = edge["source_id"]
            if source_id in out_degree_dict:
                out_degree_dict[source_id] += 1

        return out_degree_dict

    def connected_components(self) -> int:
        """
        Count the number of weakly connected components in the graph.

        For a directed graph, treats it as undirected for connectivity purposes
        (ignoring edge direction).

        Returns:
            Number of connected components
        """
        if not self._nodes:
            return 0

        # Build undirected adjacency for connectivity analysis
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in self._nodes}

        # Add edges in both directions (treating as undirected)
        for edge in self._edges:
            source_id = edge["source_id"]
            target_id = edge["target_id"]

            if source_id in adjacency and target_id in adjacency:
                adjacency[source_id].add(target_id)
                adjacency[target_id].add(source_id)

        # Count connected components using DFS
        visited: set[str] = set()
        component_count = 0

        def dfs(node_id: str) -> None:
            """Depth-first search to mark connected component."""
            visited.add(node_id)
            for neighbor in adjacency[node_id]:
                if neighbor not in visited:
                    dfs(neighbor)

        for node_id in self._nodes:
            if node_id not in visited:
                dfs(node_id)
                component_count += 1

        return component_count

    def communities(self, algorithm: str = "louvain") -> list[set[str]]:
        """
        Partition the graph into communities.

        For the fake implementation, returns each node as its own community.

        Args:
            algorithm: Name of the community detection algorithm (unused in fake)

        Returns:
            List of communities, each as a set of node IDs
        """
        return [{node_id} for node_id in self._nodes]

    def subgraph(self, node_ids: list[str]) -> "FakeGraphEngine":
        """
        Extract a subgraph containing only the specified nodes.

        Creates a new FakeGraphEngine with subset of nodes and edges
        that connect those nodes.

        Args:
            node_ids: IDs of nodes to include in the subgraph

        Returns:
            New FakeGraphEngine instance with the subgraph
        """
        subgraph = FakeGraphEngine()

        # Convert to set for O(1) membership testing instead of O(n)
        node_ids_set = set(node_ids)

        # Copy only the requested nodes using set-based filtering
        subgraph_nodes = [
            node for node in self._nodes.values() if node["id"] in node_ids_set
        ]

        # Copy only edges where both endpoints are in the subgraph
        subgraph_edges = [
            edge
            for edge in self._edges
            if edge["source_id"] in node_ids_set and edge["target_id"] in node_ids_set
        ]

        subgraph.build_from_data(subgraph_nodes, subgraph_edges)
        return subgraph

    def neighbors(
        self, node_id: str, direction: str = "both", depth: int = 1
    ) -> set[str]:
        """
        Get all neighbors of a node up to a specified depth with directional filtering.

        Uses breadth-first traversal to find all nodes within the specified depth.
        - "out": successors (nodes this node points to)
        - "in": predecessors (nodes that point to this node)
        - "both": all connected neighbors

        Args:
            node_id: ID of the center node
            direction: Direction of traversal: "in", "out", or "both"
            depth: Maximum distance from center node (default 1)

        Returns:
            Set of neighboring node IDs (excludes the center node)

        Raises:
            NodeNotFoundError: If node_id does not exist in the graph
        """
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)

        if depth < 1:
            return set()

        neighbors_set = set()
        visited = {node_id}  # Track visited nodes
        current_level = {node_id}  # Start from the center node

        for _ in range(depth):
            next_level = set()

            for current_node in current_level:
                for edge in self._edges:
                    if (
                        direction in ("out", "both")
                        and edge["source_id"] == current_node
                    ):
                        target = edge["target_id"]
                        if target not in visited:
                            next_level.add(target)

                    if (
                        direction in ("in", "both")
                        and edge["target_id"] == current_node
                    ):
                        source = edge["source_id"]
                        if source not in visited:
                            next_level.add(source)

            # Mark newly discovered nodes as visited
            visited.update(next_level)
            # Add newly discovered nodes to result
            neighbors_set.update(next_level)
            # Move to next level
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
        return [(edge["source_id"], edge["target_id"]) for edge in self._edges]

    def has_cycle(self, source_id: str, target_id: str) -> bool:
        """
        Check if adding an edge would create a cycle.

        Uses depth-first search to detect if a path exists from target_id
        to source_id. If such a path exists, adding source_id -> target_id
        would create a cycle.

        Args:
            source_id: ID of the proposed edge source
            target_id: ID of the proposed edge target

        Returns:
            True if a path exists from target_id to source_id, False otherwise
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            return False

        # Check if there's already a path from target_id to source_id
        # If yes, adding source_id -> target_id would create a cycle
        return self._has_path(target_id, source_id)

    def _has_path(self, start_id: str, end_id: str) -> bool:
        """
        Check if a path exists from start_id to end_id using DFS.

        Args:
            start_id: Starting node ID
            end_id: Target node ID

        Returns:
            True if path exists, False otherwise
        """
        if start_id == end_id:
            return True

        visited = set()
        stack = [start_id]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            if current == end_id:
                return True

            # Add all outgoing neighbors to stack
            for edge in self._edges:
                if edge["source_id"] == current and edge["target_id"] not in visited:
                    stack.append(edge["target_id"])

        return False

    def get_edge_data(self, source_id: str, target_id: str) -> dict[str, Any]:
        """
        Get the attributes/properties of a specific edge.

        Args:
            source_id: ID of the edge source node
            target_id: ID of the edge target node

        Returns:
            Dictionary of edge attributes, or empty dict if edge doesn't exist
        """
        for edge in self._edges:
            if edge["source_id"] == source_id and edge["target_id"] == target_id:
                # Return a copy of all attributes except source/target
                return {
                    k: v for k, v in edge.items() if k not in ("source_id", "target_id")
                }
        return {}
