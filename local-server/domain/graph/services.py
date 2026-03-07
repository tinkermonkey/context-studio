"""
Domain service for the Graph bounded context.

Provides business logic for graph analysis operations: building graphs from ontology data,
analyzing structure, finding paths, and executing semantic queries.

Uses dependency injection to receive port implementations at runtime.
Imports only from Python stdlib and domain entities/ports — zero infrastructure dependencies.
"""

from typing import Optional, Sequence

from domain.graph.entities import GraphMetrics, KnowledgeGraph, PathResult
from domain.graph.ports import GraphEngine, SemanticQueryEngine


class GraphAnalysisService:
    """
    Service for analyzing knowledge graphs.

    Responsibilities:
    - Build in-memory graphs from ontology data
    - Compute graph metrics (density, connectivity, etc.)
    - Find paths between nodes
    - Analyze network structure (centrality, communities, etc.)
    - Execute SPARQL/semantic queries

    The service is constructed with port implementations injected by the composition root
    (typically app.py), not with concrete adapters.
    """

    def __init__(
        self,
        repository: "OntologyRepository",  # OntologyRepository port for reading ontology data
        graph_engine: GraphEngine,  # GraphEngine port for graph computation
        query_engine: SemanticQueryEngine,  # SemanticQueryEngine port for SPARQL queries
    ) -> None:
        """
        Initialize the graph analysis service.

        Args:
            repository: Port implementation for reading ontology data.
            graph_engine: Port implementation for graph computation (e.g., NetworkX).
            query_engine: Port implementation for semantic queries (e.g., RDFLib).
        """
        self.repository = repository
        self.graph_engine = graph_engine
        self.query_engine = query_engine

    def build_graph(self, taxonomy_id: str) -> KnowledgeGraph:
        """
        Build a knowledge graph from ontology data for a given taxonomy.

        Reads all classes and relationships from the ontology repository,
        builds an in-memory graph using the graph engine, and returns metrics.

        Args:
            taxonomy_id: The taxonomy to build a graph for.

        Returns:
            KnowledgeGraph entity with nodes, edges, and metrics.

        Raises:
            ValueError: If the taxonomy does not exist or has no nodes.
        """
        # Fetch ontology data from repository
        classes = self.repository.list_classes()
        relationships = self.repository.list_relationships()

        if not classes:
            raise ValueError(f"No classes found for taxonomy {taxonomy_id}")

        # Convert to data dictionaries for graph engine
        node_data = [
            {
                "id": cls.id,
                "title": cls.title,
                "node_type": getattr(cls, "node_type", "unknown"),
            }
            for cls in classes
        ]
        edge_data = [
            {
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "property_label": rel.property_label,
            }
            for rel in relationships
        ]

        # Build graph in memory
        self.graph_engine.build_from_data(node_data, edge_data)

        # Compute metrics
        metrics = GraphMetrics(
            node_count=self.graph_engine.node_count(),
            edge_count=self.graph_engine.edge_count(),
            density=self._compute_density(),
            connected_components=self._count_connected_components(),
        )

        # Collect node and edge IDs as tuples (immutable)
        node_ids = tuple(cls.id for cls in classes)
        edge_ids = tuple(rel.id for rel in relationships)

        return KnowledgeGraph(
            taxonomy_id=taxonomy_id,
            nodes=node_ids,
            edges=edge_ids,
            metrics=metrics,
        )

    def find_shortest_path(
        self, source_id: str, target_id: str
    ) -> Optional[PathResult]:
        """
        Find the shortest path between two nodes in the graph.

        Args:
            source_id: The starting node ID.
            target_id: The ending node ID.

        Returns:
            PathResult with the path and metadata, or None if no path exists.
        """
        path = self.graph_engine.shortest_path(source_id, target_id)

        if path is None:
            return None

        path_tuple = tuple(path)
        length = len(path_tuple) - 1 if path_tuple else 0

        return PathResult(path=path_tuple, length=length, weight=0.0)

    def find_all_paths(
        self, source_id: str, target_id: str, max_depth: int = 5
    ) -> list[PathResult]:
        """
        Find all paths between two nodes up to a maximum depth.

        Args:
            source_id: The starting node ID.
            target_id: The ending node ID.
            max_depth: Maximum path length to search.

        Returns:
            List of PathResult objects representing all found paths.
        """
        paths = self.graph_engine.all_paths(source_id, target_id, max_depth)
        results = []

        for path in paths:
            path_tuple = tuple(path)
            length = len(path_tuple) - 1 if path_tuple else 0
            results.append(PathResult(path=path_tuple, length=length, weight=0.0))

        return results

    def get_centrality(self, algorithm: str = "betweenness") -> dict[str, float]:
        """
        Compute node centrality using the specified algorithm.

        Args:
            algorithm: The centrality algorithm to use (e.g., "betweenness", "closeness").

        Returns:
            Dictionary mapping node IDs to their centrality scores.
        """
        return self.graph_engine.centrality(algorithm)

    def get_communities(self, algorithm: str = "louvain") -> list[set[str]]:
        """
        Detect communities in the graph.

        Args:
            algorithm: The community detection algorithm to use (e.g., "louvain").

        Returns:
            List of sets, where each set represents a community of node IDs.
        """
        return self.graph_engine.communities(algorithm)

    def get_neighbors(self, node_id: str, depth: int = 1) -> set[str]:
        """
        Get all neighbors of a node up to a specified depth.

        Args:
            node_id: The node ID to find neighbors for.
            depth: How many hops away to search.

        Returns:
            Set of neighbor node IDs.
        """
        return self.graph_engine.neighbors(node_id, depth)

    def has_cycle(self, source_id: str, target_id: str) -> bool:
        """
        Check if there is a cycle in the path from source to target.

        Args:
            source_id: The starting node ID.
            target_id: The ending node ID.

        Returns:
            True if a cycle exists, False otherwise.
        """
        return self.graph_engine.has_cycle(source_id, target_id)

    def execute_sparql(self, query: str) -> list[dict]:
        """
        Execute a SPARQL query against the ontology.

        Args:
            query: A SPARQL query string.

        Returns:
            List of result dictionaries from the query execution.

        Raises:
            ValueError: If the query is invalid or ontology is not loaded.
        """
        # Ensure ontology is loaded for SPARQL queries
        if not self.query_engine.is_loaded():
            self._load_ontology_for_sparql()

        return self.query_engine.execute_sparql(query)

    def _compute_density(self) -> float:
        """
        Compute graph density.

        Density = 2 * edge_count / (node_count * (node_count - 1))
        for undirected graphs.

        Returns:
            Graph density as a float between 0.0 and 1.0.
        """
        node_count = self.graph_engine.node_count()
        edge_count = self.graph_engine.edge_count()

        if node_count <= 1:
            return 0.0

        max_edges = node_count * (node_count - 1) / 2
        return edge_count / max_edges if max_edges > 0 else 0.0

    def _count_connected_components(self) -> int:
        """
        Count the number of connected components in the graph.

        For now, returns a placeholder value of 1.
        A full implementation would traverse the graph to count components.

        Returns:
            Number of connected components.
        """
        # Placeholder: GraphEngine may need a method for this
        # For now, assume a single component
        return 1

    def _load_ontology_for_sparql(self) -> None:
        """
        Load ontology data into the SPARQL query engine.

        Fetches all ontology data from the repository and loads it
        into the semantic query engine's RDF representation.
        """
        classes = self.repository.list_classes()
        relationships = self.repository.list_relationships()
        property_definitions = self.repository.list_property_definitions()

        node_data = [
            {
                "id": cls.id,
                "title": cls.title,
                "node_type": getattr(cls, "node_type", "unknown"),
            }
            for cls in classes
        ]
        edge_data = [
            {
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "property_label": rel.property_label,
            }
            for rel in relationships
        ]
        prop_data = [
            {
                "id": prop.id,
                "label": prop.label,
            }
            for prop in property_definitions
        ]

        self.query_engine.load_ontology(node_data, edge_data, prop_data)
