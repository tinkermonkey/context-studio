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
        computed_at: Timestamp when metrics were computed
    """

    density: float
    average_degree: float
    connected_components: int
    degree_distribution: dict[str, int]
    centrality: dict[str, float]
    communities: list[set[str]]
    algorithm: str
    computed_at: datetime


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


@dataclass
class Subgraph:
    """
    A subgraph containing specific nodes and edges.

    Represents a subgraph extracted from a larger knowledge graph,
    containing only the specified nodes and edges between them.

    Attributes:
        node_ids: IDs of all nodes in the subgraph
        edge_ids: List of (source_id, target_id) tuples for edges in the subgraph
        node_count: Number of nodes in the subgraph
        edge_count: Number of edges in the subgraph
    """

    node_ids: list[str]
    edge_ids: list[tuple[str, str]]
    node_count: int
    edge_count: int


@dataclass
class SubgraphResult:
    """
    A subgraph extracted around a center node.

    Represents the result of subgraph extraction operations, including the center node
    and all nodes/edges within a specified distance from it.

    Attributes:
        center_node_id: ID of the center node around which the subgraph was extracted
        node_ids: IDs of all nodes in the subgraph
        edge_ids: List of (source_id, target_id) tuples for edges in the subgraph
        node_count: Number of nodes in the subgraph
        edge_count: Number of edges in the subgraph
        depth: Maximum distance from center node that was included
        extracted_at: Timestamp when the subgraph was extracted
    """

    center_node_id: str
    node_ids: list[str]
    edge_ids: list[tuple[str, str]]
    node_count: int
    edge_count: int
    depth: int
    extracted_at: datetime


@dataclass
class GraphViewTaxonomy:
    """A taxonomy that groups the layers of a graph view."""

    id: str
    title: str
    identifier: str | None


@dataclass
class GraphViewLayer:
    """A concept scheme rendered as one layer of a graph view."""

    id: str
    title: str
    identifier: str | None
    taxonomy_id: str


@dataclass
class GraphViewNode:
    """
    A class or individual in a graph view, labelled and assigned to a layer.

    Individuals inherit concept_scheme_id and taxonomy_id from their first
    class that resolves to a known class.
    """

    id: str
    label: str
    node_type: str  # "class" | "individual"
    identifier: str | None
    description: str | None
    concept_scheme_id: str | None
    taxonomy_id: str | None
    class_ids: list[str]


@dataclass
class GraphViewEdge:
    """
    A directed, typed edge between two graph view nodes.

    edge_type is one of:
        relationship — an asserted Relationship (predicate = property definition title)
        schema       — a property definition's domain class -> range class
        instance_of  — individual -> class membership
        subclass_of  — class -> parent class
    """

    id: str
    source: str
    target: str
    edge_type: str
    predicate_id: str | None
    predicate: str | None


@dataclass
class GraphView:
    """Labelled read model of the ontology graph for visualization."""

    taxonomies: list[GraphViewTaxonomy]
    layers: list[GraphViewLayer]
    nodes: list[GraphViewNode]
    edges: list[GraphViewEdge]
