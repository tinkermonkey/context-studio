"""Fake in-memory implementation of GraphEngine for testing.

Provides a simple in-memory graph engine implementation for unit testing.
Uses plain dictionaries and lists to store nodes and edges, supporting
all GraphEngine protocol methods with straightforward implementations.
"""

import sys
import os
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeGraphEngine:
    """In-memory implementation of GraphEngine protocol for unit testing."""

    def __init__(self) -> None:
        """Initialize the fake graph engine with empty storage."""
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []

    def build_from_data(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
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
        exist, otherwise None.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node

        Returns:
            List [source_id, target_id] if both exist, None otherwise
        """
        if source_id in self._nodes and target_id in self._nodes:
            return [source_id, target_id]
        return None

    def all_paths(self, source_id: str, target_id: str, max_depth: int = 5) -> list[list[str]]:
        """
        Find all simple paths between two nodes up to a maximum depth.

        For the fake implementation, returns [[source_id, target_id]] if both nodes
        exist, otherwise empty list.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node
            max_depth: Maximum path length to explore (unused in fake)

        Returns:
            List containing single path [[source_id, target_id]] if both exist, else []
        """
        if source_id in self._nodes and target_id in self._nodes:
            return [[source_id, target_id]]
        return []

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

        For the fake implementation, returns 0 for all nodes (no edges tracked).

        Returns:
            Dictionary mapping node ID to degree (all zeros in fake)
        """
        return {node_id: 0 for node_id in self._nodes}

    def connected_components(self) -> int:
        """
        Count the number of connected components in the graph.

        For the fake implementation, always returns 1 if there are nodes, 0 otherwise.

        Returns:
            Number of connected components
        """
        return 1 if self._nodes else 0

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

        # Copy only the requested nodes
        subgraph_nodes = [node for node in self._nodes.values() if node["id"] in node_ids]

        # Copy only edges where both endpoints are in the subgraph
        node_ids_set = set(node_ids)
        subgraph_edges = [
            edge for edge in self._edges
            if edge["source_id"] in node_ids_set and edge["target_id"] in node_ids_set
        ]

        subgraph.build_from_data(subgraph_nodes, subgraph_edges)
        return subgraph

    def neighbors(self, node_id: str, direction: str = "both") -> set[str]:
        """
        Get all neighbors of a node with directional filtering.

        Returns neighbors based on stored edges and the direction parameter.
        - "out": nodes that this node points to
        - "in": nodes that point to this node
        - "both": all connected neighbors

        Args:
            node_id: ID of the node
            direction: Direction of traversal: "in", "out", or "both"

        Returns:
            Set of neighboring node IDs
        """
        neighbors_set = set()

        for edge in self._edges:
            if direction in ("out", "both") and edge["source_id"] == node_id:
                neighbors_set.add(edge["target_id"])
            if direction in ("in", "both") and edge["target_id"] == node_id:
                neighbors_set.add(edge["source_id"])

        return neighbors_set

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
