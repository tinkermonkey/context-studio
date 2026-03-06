"""
Port interfaces for the Graph bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""
from typing import Protocol, Optional, Sequence



class GraphEngine(Protocol):
    """Engine for graph computation.

    The engine maintains an internal graph representation.
    Call build_from_data to populate it, then use analysis methods.
    The engine does not persist anything — it's purely computational.
    """

    def build_from_data(
        self,
        nodes: Sequence[dict],      # [{id, title, node_type, ...}]
        edges: Sequence[dict],      # [{source_id, target_id, property_label, ...}]
    ) -> None:
        """Populate the graph from node and edge data."""
        ...

    def node_count(self) -> int:
        """Get the number of nodes in the graph."""
        ...

    def edge_count(self) -> int:
        """Get the number of edges in the graph."""
        ...

    def shortest_path(self, source_id: str, target_id: str) -> Optional[list[str]]:
        """Find shortest path between two nodes."""
        ...

    def all_paths(self, source_id: str, target_id: str, max_depth: int = 5) -> list[list[str]]:
        """Find all paths between two nodes up to max_depth."""
        ...

    def centrality(self, algorithm: str = "betweenness") -> dict[str, float]:
        """Compute node centrality using specified algorithm."""
        ...

    def degree_distribution(self) -> dict[str, int]:
        """Get the degree distribution of the graph."""
        ...

    def communities(self, algorithm: str = "louvain") -> list[set[str]]:
        """Detect communities in the graph."""
        ...

    def subgraph(self, node_ids: Sequence[str]) -> "GraphEngine":
        """Extract a subgraph containing only specified nodes."""
        ...

    def neighbors(self, node_id: str, depth: int = 1) -> set[str]:
        """Get all neighbors of a node up to specified depth."""
        ...

    def has_cycle(self, source_id: str, target_id: str) -> bool:
        """Check if there is a cycle in path from source to target."""
        ...


class SemanticQueryEngine(Protocol):
    """Engine for semantic/SPARQL queries.

    Maintains an RDF graph representation that can be queried with SPARQL.
    The engine is lazy-loaded — the RDF graph is built on first query.
    """

    def load_ontology(
        self,
        nodes: Sequence[dict],
        edges: Sequence[dict],
        property_definitions: Sequence[dict],
    ) -> None:
        """Load ontology data into RDF representation."""
        ...

    def execute_sparql(self, query: str) -> list[dict]:
        """Execute a SPARQL query and return results."""
        ...

    def get_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
    ) -> list[tuple[str, str, str]]:
        """Get RDF triples matching the given criteria."""
        ...

    def is_loaded(self) -> bool:
        """Check if ontology has been loaded."""
        ...

    def triple_count(self) -> int:
        """Get the total number of triples in the RDF graph."""
        ...
