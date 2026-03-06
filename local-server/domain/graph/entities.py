"""
Domain entities for the graph bounded context.

Entities represent graph-level concepts: metrics, paths, and the knowledge graph
as a whole. They import only from Python stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

    def __post_init__(self) -> None:
        """Validate graph metrics invariants."""
        if isinstance(self.node_count, bool) or not isinstance(self.node_count, int) or self.node_count < 0:
            raise ValueError("node_count must be a non-negative integer")
        if isinstance(self.edge_count, bool) or not isinstance(self.edge_count, int) or self.edge_count < 0:
            raise ValueError("edge_count must be a non-negative integer")
        if isinstance(self.density, bool) or not isinstance(self.density, (int, float)) or not (0.0 <= self.density <= 1.0):
            raise ValueError("density must be a number between 0.0 and 1.0")
        if isinstance(self.connected_components, bool) or not isinstance(self.connected_components, int) or self.connected_components < 1:
            raise ValueError("connected_components must be a positive integer")


@dataclass
class PathResult:
    """
    Represents a path between two nodes in the graph.

    Attributes:
        path: Tuple of node IDs forming the path from source to target (immutable).
        length: Number of hops in the path.
        weight: Total accumulated weight along the path.
    """

    path: tuple[str, ...] = ()
    length: int = 0
    weight: float = 0.0

    def __post_init__(self) -> None:
        """Validate path result invariants."""
        if not isinstance(self.path, tuple):
            raise TypeError("path must be a tuple of node IDs (immutable)")
        if len(self.path) > 0:
            for node_id in self.path:
                if not isinstance(node_id, str):
                    raise TypeError(f"All node IDs in path must be strings, got {type(node_id).__name__}")
        if isinstance(self.length, bool) or not isinstance(self.length, int) or self.length < 0:
            raise ValueError("length must be a non-negative integer")
        if len(self.path) > 0 and self.length != len(self.path) - 1:
            raise ValueError("length must equal number of edges (nodes - 1) in the path")
        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)):
            raise ValueError("weight must be a number")


@dataclass
class KnowledgeGraph:
    """
    Represents a knowledge graph within a taxonomy.

    Attributes:
        taxonomy_id: The taxonomy this graph belongs to.
        nodes: Tuple of node (Class) IDs in the graph (immutable).
        edges: Tuple of edge (Relationship) IDs in the graph (immutable).
        metrics: Optional graph metrics.
    """

    taxonomy_id: str
    nodes: tuple[str, ...] = ()
    edges: tuple[str, ...] = ()
    metrics: Optional[GraphMetrics] = None

    def __post_init__(self) -> None:
        """Validate knowledge graph invariants."""
        if not self.taxonomy_id or not isinstance(self.taxonomy_id, str):
            raise ValueError("taxonomy_id must be a non-empty string")
        if not isinstance(self.nodes, tuple):
            raise TypeError("nodes must be a tuple of node IDs (immutable)")
        for node_id in self.nodes:
            if not isinstance(node_id, str):
                raise TypeError(f"All node IDs must be strings, got {type(node_id).__name__}")
        if not isinstance(self.edges, tuple):
            raise TypeError("edges must be a tuple of edge IDs (immutable)")
        for edge_id in self.edges:
            if not isinstance(edge_id, str):
                raise TypeError(f"All edge IDs must be strings, got {type(edge_id).__name__}")
        if self.metrics is not None and not isinstance(self.metrics, GraphMetrics):
            raise TypeError("metrics must be None or a GraphMetrics instance")
