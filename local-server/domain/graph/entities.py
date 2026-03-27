"""
Domain entities for the Graph Analysis bounded context.

These dataclasses represent the results of graph analysis operations
(metrics, paths, subgraph descriptors). They are ephemeral value objects
with no persistence requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class KnowledgeGraph:
    """
    Lightweight descriptor of an in-memory knowledge graph state.

    This is not a persistent entity — it is a snapshot of the current
    graph structure used for reporting and analysis workflows.

    Attributes:
        node_count: Number of nodes in the graph
        edge_count: Number of edges in the graph
        is_directed: Whether the graph is directed (always True for ontology graphs)
        last_built: Timestamp when the graph was last constructed from ontology data
    """

    node_count: int
    edge_count: int
    is_directed: bool
    last_built: datetime


@dataclass
class GraphMetrics:
    """
    Computed structural metrics for an entire knowledge graph.

    Metrics are derived from the graph topology and include density,
    degree statistics, connected component analysis, degree distribution,
    centrality scores, and community detection results.

    Attributes:
        density: Edge density (number of edges / max possible edges)
        average_degree: Mean degree across all nodes
        connected_components: Number of connected components in the graph
        degree_distribution: Distribution of node degrees as dict[degree_count -> frequency]
        centrality: Centrality scores for all nodes, keyed by node ID
        communities: List of communities detected in the graph, each as a set of node IDs
        algorithm: Name of the centrality algorithm used
    """

    density: float
    average_degree: float
    connected_components: int
    degree_distribution: dict[str, int]
    centrality: dict[str, float]
    communities: list[set[str]]
    algorithm: str


@dataclass
class PathResult:
    """
    An ordered path traversal between two nodes in a knowledge graph.

    Represents a single path result from shortest-path or all-paths queries.

    Attributes:
        source_id: ID of the starting node
        target_id: ID of the ending node
        path: Ordered list of node IDs from source to target (inclusive)
        length: Number of edges in the path (path length = len(path) - 1)
        relationships: List of relationship labels/types traversed along the path
    """

    source_id: str
    target_id: str
    path: list[str]
    length: int
    relationships: list[str]
