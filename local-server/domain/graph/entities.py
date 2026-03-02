"""
Domain entities for the graph bounded context.

Entities represent graph-level concepts: metrics, paths, and the knowledge graph
as a whole. They import only from Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class GraphMetrics:
    """
    Metrics describing a knowledge graph's structural properties.

    Attributes:
        node_count: Total number of nodes in the graph.
        edge_count: Total number of edges in the graph.
        density: Graph density as a float between 0.0 and 1.0.
        connected_components: Number of connected components.
    """

    node_count: int
    edge_count: int
    density: float
    connected_components: int


@dataclass
class PathResult:
    """
    Represents a path between two nodes in the graph.

    Attributes:
        path: List of node IDs forming the path from source to target.
        length: Number of hops in the path.
        weight: Total accumulated weight along the path.
    """

    path: List[str]  # node IDs
    length: int
    weight: float


@dataclass
class KnowledgeGraph:
    """
    Represents a knowledge graph within a taxonomy.

    Attributes:
        taxonomy_id: The taxonomy this graph belongs to.
        nodes: List of node (Class) IDs in the graph.
        edges: List of edge (Relationship) IDs in the graph.
        metrics: Optional graph metrics.
    """

    taxonomy_id: str
    nodes: List[str]  # Class IDs
    edges: List[str]  # Relationship IDs
    metrics: Optional[GraphMetrics] = None
