"""
Port interfaces (protocols) for the Graph Analysis bounded context.

Ports define contracts for graph infrastructure adapters (NetworkX, RDFLib, etc.).
Using typing.Protocol enables structural subtyping — implementations do not
explicitly inherit from these protocols.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence


class GraphEngine(Protocol):
    """
    Port for in-memory graph operations (shortest path, centrality, community detection, etc.).

    The GraphEngine wraps a graph library (e.g., NetworkX) and provides a unified
    interface for structural graph analysis. It is stateful — once build_from_data()
    is called, the engine holds the graph until build_from_data() is called again.
    """

    def build_from_data(
        self, nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]]
    ) -> None:
        """
        Construct the graph from node and edge data.

        This method clears any existing graph and builds a new one from scratch.
        The engine retains the graph until this method is called again.

        Args:
            nodes: Sequence of node dictionaries. Each dict should contain at least
                   'id' (str) and may contain other attributes (title, node_type, etc.)
            edges: Sequence of edge dictionaries. Each dict should contain at least
                   'source_id' (str), 'target_id' (str), and may contain other
                   attributes (property_definition_id, etc.)
        """
        ...

    def node_count(self) -> int:
        """
        Return the number of nodes in the graph.

        Returns:
            Number of nodes in the current graph
        """
        ...

    def edge_count(self) -> int:
        """
        Return the number of edges in the graph.

        Returns:
            Number of edges in the current graph
        """
        ...

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
            NodeNotFoundError: If source_id or target_id does not exist in the graph
        """
        ...

    def all_paths(self, source_id: str, target_id: str, max_depth: int = 5) -> list[list[str]]:
        """
        Find all simple paths between two nodes up to a maximum depth.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node
            max_depth: Maximum path length to explore (default 5)

        Returns:
            List of paths, where each path is an ordered list of node IDs

        Raises:
            NodeNotFoundError: If source_id or target_id does not exist in the graph
        """
        ...

    def centrality(self, algorithm: str = "betweenness") -> dict[str, float]:
        """
        Compute centrality scores for all nodes using the specified algorithm.

        Args:
            algorithm: Name of the centrality algorithm (e.g., "betweenness", "pagerank")

        Returns:
            Dictionary mapping node ID (str) to centrality score (float)
        """
        ...

    def degree_distribution(self) -> dict[str, int]:
        """
        Get the degree of each node.

        Returns:
            Dictionary mapping node ID (str) to degree (int)
        """
        ...

    def in_degree_distribution(self) -> dict[str, int]:
        """
        Get the in-degree of each node.

        Returns:
            Dictionary mapping node ID (str) to in-degree (int)
        """
        ...

    def out_degree_distribution(self) -> dict[str, int]:
        """
        Get the out-degree of each node.

        Returns:
            Dictionary mapping node ID (str) to out-degree (int)
        """
        ...

    def connected_components(self) -> int:
        """
        Count the number of connected components in the graph.

        Returns:
            Number of connected components (isolated nodes count as separate components)
        """
        ...

    def communities(self, algorithm: str = "louvain") -> list[set[str]]:
        """
        Partition the graph into communities using the specified algorithm.

        Args:
            algorithm: Name of the community detection algorithm (e.g., "louvain", "label_propagation")

        Returns:
            List of communities, where each community is a set of node IDs
        """
        ...

    def subgraph(self, node_ids: Sequence[str]) -> GraphEngine:
        """
        Extract a subgraph containing only the specified nodes and edges between them.

        Args:
            node_ids: IDs of nodes to include in the subgraph

        Returns:
            A new GraphEngine instance wrapping the subgraph
        """
        ...

    def neighbors(self, node_id: str, direction: str = "both", depth: int = 1) -> set[str]:
        """
        Get all neighbors of a node up to a specified depth with optional directional filtering.

        Args:
            node_id: ID of the center node
            direction: Direction of traversal: "in" (predecessors), "out" (successors), "both" (default)
            depth: Maximum distance from center node (default 1). Depth 1 returns immediate neighbors,
                   depth 2 returns two hops away, etc.

        Returns:
            Set of neighboring node IDs at the specified depth (excludes the center node)

        Raises:
            NodeNotFoundError: If node_id does not exist in the graph
        """
        ...

    def edges(self) -> list[tuple[str, str]]:
        """
        Get all edges in the graph as (source, target) tuples.

        Returns:
            List of edge tuples, where each tuple is (source_id, target_id)
        """
        ...

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
        ...

    def get_edge_data(self, source_id: str, target_id: str) -> dict[str, Any]:
        """
        Get the attributes/properties of a specific edge.

        Args:
            source_id: ID of the edge source node
            target_id: ID of the edge target node

        Returns:
            Dictionary of edge attributes (e.g., property_definition_id), or empty dict if edge doesn't exist
        """
        ...


class SemanticQueryEngine(Protocol):
    """
    Port for RDF/SPARQL operations on ontology knowledge.

    The SemanticQueryEngine wraps an RDF graph library (e.g., RDFLib) and provides
    a unified interface for semantic queries, SPARQL execution, and triple access.
    It is stateful — once load_ontology() is called, the engine retains the RDF graph.

    Contract: SPARQL validation (forbidden keyword checking) is performed by the
    domain GraphAnalysisService before execute_sparql() is invoked. Implementations
    focus on framework-specific concerns (exception translation, RDF operations)
    and can assume queries are pre-validated for safety.
    """

    def load_ontology(
        self,
        nodes: Sequence[dict[str, Any]],
        edges: Sequence[dict[str, Any]],
        property_definitions: Sequence[dict[str, Any]],
    ) -> None:
        """
        Load ontology data into the RDF graph.

        This method clears any existing RDF graph and builds a new one from
        ontology entities and relationships using standard RDF vocabularies.

        Args:
            nodes: Sequence of ontology entity dictionaries (Taxonomy, ConceptScheme, Class, etc.)
            edges: Sequence of relationship dictionaries linking entities
            property_definitions: Sequence of property definition dictionaries for relationship types
        """
        ...

    def execute_sparql(self, query: str) -> list[dict[str, Any]]:
        """
        Execute a SPARQL SELECT query against the RDF graph.

        Args:
            query: SPARQL query string (SELECT queries only)

        Returns:
            List of result dictionaries, where each dict maps variable names to values
        """
        ...

    def get_triples(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Retrieve RDF triples matching the given pattern.

        Any parameter may be None to match any value in that position.

        Args:
            subject: Optional subject URI/ID to match
            predicate: Optional predicate URI/property to match
            object: Optional object value to match

        Returns:
            List of matching triples, each as (subject, predicate, object)
        """
        ...

    def is_loaded(self) -> bool:
        """
        Check if the RDF graph is currently loaded with data.

        Returns:
            True if load_ontology() has been called and the graph contains data
        """
        ...

    def triple_count(self) -> int:
        """
        Get the number of triples in the RDF graph.

        Returns:
            Number of triples currently in the graph
        """
        ...
