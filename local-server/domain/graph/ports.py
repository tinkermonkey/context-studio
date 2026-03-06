"""
Port interfaces for the Graph bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""
from typing import Protocol, Optional, Sequence

from domain.graph.entities import KnowledgeGraph, PathResult, GraphMetrics


class GraphEngine(Protocol):
    """Engine port for building and querying knowledge graphs."""

    def build_graph(self, taxonomy_id: str) -> KnowledgeGraph:
        """Build a knowledge graph from a taxonomy."""
        ...

    def find_path(
        self, source_id: str, target_id: str, taxonomy_id: str
    ) -> Optional[PathResult]:
        """Find a path between two nodes in a knowledge graph."""
        ...

    def get_metrics(self, taxonomy_id: str) -> GraphMetrics:
        """Get metrics for a knowledge graph."""
        ...

    def invalidate(self, taxonomy_id: str) -> None:
        """Invalidate the cached graph for a taxonomy."""
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
