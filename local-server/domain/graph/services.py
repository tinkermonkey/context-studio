"""
Domain service for graph analysis operations.

GraphAnalysisService orchestrates all graph-based queries and analysis by
delegating to two ports: GraphEngine (for structural analysis) and
SemanticQueryEngine (for RDF/SPARQL operations). The service manages
cache invalidation via a stale-flag pattern triggered by GraphInvalidated events.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .entities import GraphMetrics, KnowledgeGraph, PathResult, SubgraphResult
from .exceptions import GraphError, InvalidAlgorithmError, NodeNotFoundError, SPARQLValidationError
from .ports import GraphEngine, SemanticQueryEngine

if TYPE_CHECKING:
    from ..ontology.ports import OntologyRepository

from ..ontology.events import GraphInvalidated

# Map domain entity class names to node_type strings
_NODE_TYPE_MAP = {
    "Taxonomy": "taxonomy",
    "ConceptScheme": "concept_scheme",
    "Class": "class",
}

# Valid centrality algorithms for graph analysis
_VALID_CENTRALITY_ALGORITHMS = ["pagerank", "betweenness", "closeness", "degree"]


class GraphAnalysisService:
    """
    Domain service for knowledge graph analysis.

    The service maintains two in-memory caches (via GraphEngine and SemanticQueryEngine)
    and uses a stale-flag pattern for lazy cache invalidation. Graphs are not built on
    construction — they are built on first access and rebuilt after GraphInvalidated events.

    This service is read-only — it writes nothing to the database and produces no events.
    """

    def __init__(
        self,
        repository: OntologyRepository,
        graph_engine: GraphEngine,
        query_engine: SemanticQueryEngine,
    ) -> None:
        """
        Initialize the graph analysis service.

        Args:
            repository: Port for reading ontology entities and relationships
            graph_engine: Port for structural graph operations (NetworkX, etc.)
            query_engine: Port for semantic/RDF operations (RDFLib, etc.)
        """
        self._repository = repository
        self._graph_engine = graph_engine
        self._query_engine = query_engine

        # Stale-flag pattern: graphs are not built on construction
        self._graph_stale = True
        self._rdf_stale = True

    @staticmethod
    def _derive_node_type(entity: object) -> str:
        """
        Derive node_type from the entity's class name.

        This avoids requiring a node_type attribute on domain entities.
        The class name is used as the key into _NODE_TYPE_MAP.

        Args:
            entity: Domain entity object

        Returns:
            Node type string (e.g., "taxonomy", "class", "concept_scheme")
        """
        class_name = entity.__class__.__name__
        return _NODE_TYPE_MAP.get(class_name, class_name.lower())

    def _ensure_graph(self) -> None:
        """
        Build the graph if it is stale.

        Reads all entities and relationships from the repository, converts them
        to dict format, passes to the graph engine, and clears the stale flag.
        """
        if not self._graph_stale:
            return

        # Fetch all entities and relationships from the repository
        entities, relationships = self._repository.get_all_entities_and_relationships()

        # Convert entities to node dicts
        nodes = []
        for entity in entities:
            node_dict = {
                "id": str(entity.id),
                "title": entity.title,
                "node_type": self._derive_node_type(entity),
            }
            nodes.append(node_dict)

        # Convert relationships to edge dicts
        edges = []
        for rel in relationships:
            edge_dict = {
                "id": str(rel.id),
                "source_id": str(rel.source_id),
                "target_id": str(rel.target_id),
                "property_definition_id": str(rel.property_definition_id) if rel.property_definition_id else None,
            }
            edges.append(edge_dict)

        # Build the graph
        self._graph_engine.build_from_data(nodes, edges)
        self._graph_stale = False

    def _ensure_rdf(self) -> None:
        """
        Load the RDF graph if it is stale.

        Reads all entities, relationships, and property definitions from the repository,
        converts them to dicts, passes to the query engine, and clears the stale flag.
        """
        if not self._rdf_stale:
            return

        # Fetch all ontology data from the repository
        entities, relationships = self._repository.get_all_entities_and_relationships()

        # Fetch property definitions separately
        property_definitions = self._repository.list_property_definitions()

        # Convert entities to node dicts
        nodes = []
        for entity in entities:
            node_dict = {
                "id": str(entity.id),
                "title": entity.title,
                "node_type": self._derive_node_type(entity),
            }
            nodes.append(node_dict)

        # Convert relationships to edge dicts
        edges = []
        for rel in relationships:
            edge_dict = {
                "id": str(rel.id),
                "source_id": str(rel.source_id),
                "target_id": str(rel.target_id),
                "property_definition_id": str(rel.property_definition_id) if rel.property_definition_id else None,
            }
            edges.append(edge_dict)

        # Convert property definitions to dicts
        prop_defs = []
        for prop_def in property_definitions:
            prop_dict = {
                "id": str(prop_def.id),
                "identifier": prop_def.identifier,
                "title": prop_def.title,
            }
            prop_defs.append(prop_dict)

        # Load the RDF graph
        self._query_engine.load_ontology(nodes, edges, prop_defs)
        self._rdf_stale = False

    def build_graph(self) -> KnowledgeGraph:
        """
        Explicitly build the in-memory graph from current ontology data.

        This endpoint allows clients to trigger graph construction on demand,
        which normally happens lazily on first query. Useful for validating
        that the graph can be built without errors and for explicit control
        over graph refresh timing.

        Returns:
            KnowledgeGraph descriptor with node count, edge count, and timestamp

        Raises:
            GraphError: If graph construction fails
        """
        self._ensure_graph()
        return KnowledgeGraph(
            node_count=self._graph_engine.node_count(),
            edge_count=self._graph_engine.edge_count(),
            is_directed=True,
            last_built=datetime.now(timezone.utc),
        )

    def get_degree_distribution(self) -> dict[str, int]:
        """
        Get the degree of each node in the graph.

        The degree is the number of edges connected to a node (in-degree + out-degree
        for directed graphs).

        Returns:
            Dictionary mapping node ID to degree

        Raises:
            GraphError: If graph construction fails
        """
        self._ensure_graph()
        return self._graph_engine.degree_distribution()

    def get_metrics(self, algorithm: str = "betweenness") -> GraphMetrics:
        """
        Compute structural metrics for the entire graph.

        Includes density, average degree, connected components, degree distribution,
        centrality scores, and community detection results.

        Args:
            algorithm: Centrality algorithm to use (default: betweenness)

        Returns:
            GraphMetrics object with computed metrics

        Raises:
            InvalidAlgorithmError: If algorithm is not recognized
        """
        # Validate algorithm upfront (same validation as get_centrality)
        if algorithm not in _VALID_CENTRALITY_ALGORITHMS:
            raise InvalidAlgorithmError(algorithm, _VALID_CENTRALITY_ALGORITHMS)

        self._ensure_graph()

        node_count = self._graph_engine.node_count()
        edge_count = self._graph_engine.edge_count()

        # Compute density: edges / max_possible_edges
        # For a directed graph: max = n * (n - 1)
        max_edges = node_count * (node_count - 1) if node_count > 0 else 0
        density = edge_count / max_edges if max_edges > 0 else 0.0

        # Compute average degree and degree distribution
        degree_dist = self._graph_engine.degree_distribution()
        avg_degree = sum(degree_dist.values()) / len(degree_dist) if degree_dist else 0.0

        # Count connected components using graph engine
        connected_components = self._graph_engine.connected_components()

        # Compute centrality scores using the specified algorithm
        centrality_scores = self._graph_engine.centrality(algorithm)

        # Detect communities using louvain algorithm
        communities = self._graph_engine.communities("louvain")

        # Convert communities from sets to sorted lists for JSON serialization
        communities_as_lists = [sorted(list(community)) for community in communities]

        return GraphMetrics(
            density=density,
            average_degree=avg_degree,
            connected_components=connected_components,
            degree_distribution=degree_dist,
            centrality=centrality_scores,
            communities=communities_as_lists,
            algorithm=algorithm,
            computed_at=datetime.now(timezone.utc),
        )

    def find_shortest_path(self, source_id: str, target_id: str) -> PathResult | None:
        """
        Find the shortest path between two nodes.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node

        Returns:
            PathResult if a path exists, None otherwise

        Raises:
            NodeNotFoundError: If either node does not exist in the graph
        """
        self._ensure_graph()

        # The graph engine will raise NodeNotFoundError if either node doesn't exist
        path = self._graph_engine.shortest_path(source_id, target_id)
        if path is None:
            return None

        # Build property definition map once for efficient lookup
        property_defs = self._repository.list_property_definitions()
        prop_def_map = {prop.id: prop.title for prop in property_defs}

        # Retrieve relationship labels for edges in the path
        relationships = self._get_path_relationships(path, prop_def_map)

        return PathResult(
            source_id=source_id,
            target_id=target_id,
            path=path,
            length=len(path) - 1,
            relationships=relationships,
        )

    def find_all_paths(self, source_id: str, target_id: str, max_depth: int = 5) -> list[PathResult]:
        """
        Find all simple paths between two nodes up to a maximum depth.

        Args:
            source_id: ID of the starting node
            target_id: ID of the ending node
            max_depth: Maximum path length to explore (number of edges)

        Returns:
            List of PathResult objects, one for each found path

        Raises:
            NodeNotFoundError: If either node does not exist in the graph
        """
        self._ensure_graph()

        # The graph engine will raise NodeNotFoundError if either node doesn't exist
        paths = self._graph_engine.all_paths(source_id, target_id, max_depth)

        # Build property definition map once for efficient lookup across all paths
        property_defs = self._repository.list_property_definitions()
        prop_def_map = {prop.id: prop.title for prop in property_defs}

        results = []
        for path in paths:
            # Retrieve relationship labels for edges in this path
            relationships = self._get_path_relationships(path, prop_def_map)

            result = PathResult(
                source_id=source_id,
                target_id=target_id,
                path=path,
                length=len(path) - 1,
                relationships=relationships,
            )
            results.append(result)

        return results

    def get_centrality(self, algorithm: str) -> dict[str, float]:
        """
        Compute centrality scores for all nodes using the specified algorithm.

        Args:
            algorithm: Name of the centrality algorithm

        Returns:
            Dictionary mapping node ID to centrality score

        Raises:
            InvalidAlgorithmError: If algorithm is not recognized
        """
        if algorithm not in _VALID_CENTRALITY_ALGORITHMS:
            raise InvalidAlgorithmError(algorithm, _VALID_CENTRALITY_ALGORITHMS)

        self._ensure_graph()
        return self._graph_engine.centrality(algorithm)

    def get_communities(self, algorithm: str) -> list[set[str]]:
        """
        Partition the graph into communities using the specified algorithm.

        Args:
            algorithm: Name of the community detection algorithm

        Returns:
            List of communities, each as a set of node IDs

        Raises:
            InvalidAlgorithmError: If algorithm is not recognized
        """
        valid_algorithms = ["louvain", "label_propagation"]
        if algorithm not in valid_algorithms:
            raise InvalidAlgorithmError(algorithm, valid_algorithms)

        self._ensure_graph()
        return self._graph_engine.communities(algorithm)

    def get_neighbors(self, node_id: str, direction: str = "both", depth: int = 1) -> set[str]:
        """
        Get all neighbors of a node up to a specified depth with optional directional filtering.

        Args:
            node_id: ID of the node
            direction: Direction of traversal: "in" (predecessors), "out" (successors), or "both" (default)
            depth: Maximum distance from center node (default 1). Depth 1 returns immediate neighbors,
                   depth 2 returns two hops away, etc.

        Returns:
            Set of neighboring node IDs (excludes the center node)

        Raises:
            NodeNotFoundError: If node_id does not exist in the graph
            InvalidAlgorithmError: If direction is not "in", "out", or "both"
        """
        # Validate direction parameter (same validation as get_centrality validates algorithm)
        valid_directions = ["in", "out", "both"]
        if direction not in valid_directions:
            raise InvalidAlgorithmError(direction, valid_directions)

        self._ensure_graph()
        # The graph engine will raise NodeNotFoundError if the node doesn't exist
        return self._graph_engine.neighbors(node_id, direction=direction, depth=depth)

    def check_cycle(self, source_id: str, target_id: str) -> bool:
        """
        Check if adding an edge from source_id to target_id would create a cycle.

        Args:
            source_id: ID of the proposed edge source
            target_id: ID of the proposed edge target

        Returns:
            True if adding the edge would create a cycle, False otherwise
        """
        self._ensure_graph()
        return self._graph_engine.has_cycle(source_id, target_id)

    def extract_subgraph(self, node_ids: list[str]) -> KnowledgeGraph:
        """
        Extract a subgraph containing the specified nodes and all edges between them.

        This method extracts a subgraph from a pre-computed list of node IDs.
        For depth-based neighborhood extraction, use extract_subgraph_by_depth() instead.

        Args:
            node_ids: List of node IDs to include in the subgraph

        Returns:
            KnowledgeGraph descriptor for the subgraph

        Raises:
            NodeNotFoundError: If any node in the list does not exist in the graph
        """
        self._ensure_graph()

        if not node_ids:
            raise ValueError("node_ids must contain at least one node ID")

        # Verify all nodes exist in the graph by attempting to get neighbors
        # neighbors() raises NodeNotFoundError if node doesn't exist
        for node_id in node_ids:
            try:
                self._graph_engine.neighbors(node_id)
            except NodeNotFoundError as exc:
                raise NodeNotFoundError(node_id) from exc

        # Extract subgraph with the specified nodes
        subgraph = self._graph_engine.subgraph(node_ids)

        return KnowledgeGraph(
            node_count=subgraph.node_count(),
            edge_count=subgraph.edge_count(),
            is_directed=True,
            last_built=datetime.now(timezone.utc),
        )

    def extract_subgraph_by_depth(self, center_node_id: str, depth: int) -> SubgraphResult:
        """
        Extract a subgraph containing a center node and all nodes within a specified depth.

        This implements the FR-9 specification for depth-based subgraph extraction.
        Depth 1 returns the center node and its immediate neighbors.
        Depth 2 returns the center node, immediate neighbors, and their neighbors, etc.

        Args:
            center_node_id: ID of the center node
            depth: Maximum distance from center node (must be >= 1)

        Returns:
            SubgraphResult containing the center node ID, node IDs, edge IDs, counts, depth, and extraction timestamp

        Raises:
            NodeNotFoundError: If the center node does not exist in the graph
            GraphError: If depth is less than 1
        """
        if depth < 1:
            raise GraphError("depth must be at least 1")

        self._ensure_graph()

        # Verify the center node exists by calling neighbors with default depth=1
        # neighbors() raises NodeNotFoundError if node_id does not exist in the graph
        try:
            self._graph_engine.neighbors(center_node_id)
        except NodeNotFoundError as exc:
            raise NodeNotFoundError(center_node_id) from exc

        # Get all nodes within the specified depth
        # neighbors() with depth=N returns all nodes within N hops (excluding the center node)
        neighborhood = self._graph_engine.neighbors(center_node_id, direction="both", depth=depth)

        # Create the subgraph with the center node plus all nodes in the neighborhood
        subgraph_nodes = {center_node_id} | neighborhood
        all_node_ids = [center_node_id] + sorted(list(neighborhood))
        subgraph = self._graph_engine.subgraph(list(subgraph_nodes))

        # Collect edge IDs from the subgraph using the edges() port method
        edge_ids = subgraph.edges()

        return SubgraphResult(
            center_node_id=center_node_id,
            node_ids=all_node_ids,
            edge_ids=edge_ids,
            node_count=subgraph.node_count(),
            edge_count=subgraph.edge_count(),
            depth=depth,
            extracted_at=datetime.now(timezone.utc),
        )

    def execute_sparql(self, query: str) -> list[dict[str, Any]]:
        """
        Execute a SPARQL SELECT query against the RDF graph.

        Args:
            query: SPARQL query string

        Returns:
            List of result dictionaries

        Raises:
            SPARQLValidationError: If the query is invalid or contains disallowed operations
        """
        self._ensure_rdf()
        # Validate query at domain level before delegating to adapter
        # This provides defense-in-depth: the adapter also validates in _validate_sparql_keywords
        self._validate_sparql(query)
        return self._query_engine.execute_sparql(query)

    def get_triple_count(self) -> int:
        """
        Get the number of RDF triples in the graph.

        Returns:
            Number of triples
        """
        self._ensure_rdf()
        return self._query_engine.triple_count()

    def get_triples(
        self, subject: str | None = None, predicate: str | None = None, object: str | None = None
    ) -> list[tuple[str, str, str]]:
        """
        Retrieve RDF triples matching the given pattern.

        Args:
            subject: Optional subject to match
            predicate: Optional predicate to match
            object: Optional object to match

        Returns:
            List of matching triples
        """
        self._ensure_rdf()
        return self._query_engine.get_triples(subject, predicate, object)

    def on_graph_invalidated(self, event: GraphInvalidated) -> None:
        """
        Handle GraphInvalidated events by marking caches as stale.

        This is a lazy-invalidation strategy: the graphs are not rebuilt immediately,
        but will be rebuilt on the next access that requires them.

        Args:
            event: The GraphInvalidated event
        """
        self._graph_stale = True
        self._rdf_stale = True

    def _get_path_relationships(self, path: list[str], prop_def_map: dict[str, str]) -> list[str]:
        """
        Get relationship labels for all edges in a path.

        For each consecutive pair of nodes in the path, retrieves the edge's
        property_definition_id and looks up the corresponding property definition
        title to use as the relationship label.

        Args:
            path: Ordered list of node IDs from source to target
            prop_def_map: Pre-built dictionary mapping property definition ID to title

        Returns:
            List of relationship labels, one for each edge in the path
        """
        relationships = []

        # Iterate through consecutive pairs of nodes in the path
        for i in range(len(path) - 1):
            source = path[i]
            target = path[i + 1]

            # Get edge attributes from graph engine
            edge_data = self._graph_engine.get_edge_data(source, target)
            prop_def_id = edge_data.get("property_definition_id")

            # Look up property definition title, or use identifier if available
            if prop_def_id and prop_def_id in prop_def_map:
                label = prop_def_map[prop_def_id]
            else:
                # Fallback: use property_definition_id as label if lookup fails
                label = prop_def_id if prop_def_id else "unknown"

            relationships.append(label)

        return relationships

    def _validate_sparql(self, query: str) -> None:
        """
        Validate SPARQL query for safety and correctness.

        Uses word-boundary regex matching to detect forbidden keywords, but excludes
        string literals to prevent false positives. For example, a query like
        `SELECT ?s WHERE { ?s rdfs:label "Please DELETE this item" }` should be allowed
        even though DELETE appears in a string literal.

        Args:
            query: SPARQL query string to validate.

        Raises:
            SPARQLValidationError: If query contains forbidden keywords
                                   or is considered unsafe.
        """
        # Forbidden keywords that indicate mutation or unsafe operations
        forbidden_keywords = {
            "INSERT", "DELETE", "DROP", "CLEAR", "LOAD", "CREATE"
        }

        # Remove string literals from the query to avoid matching keywords inside strings
        # This regex matches same-type quote pairs: double-quoted strings and single-quoted strings
        # This correctly handles apostrophes inside double-quoted strings and vice versa
        query_without_literals = re.sub(r'"[^"]*"|\'[^\']*\'', ' ', query)
        query_upper = query_without_literals.upper()

        for keyword in forbidden_keywords:
            # Use word-boundary regex to detect keywords, but not inside identifiers
            # Now that literals are removed, this won't match keywords in string values
            if re.search(rf"\b{keyword}\b", query_upper):
                raise SPARQLValidationError(
                    query,
                    f"Query contains forbidden keyword '{keyword}'. "
                    "Only SELECT queries are supported."
                )
