"""
Port interfaces for the Graph bounded context.

Ports define the contracts between the domain core and infrastructure adapters.
They use typing.Protocol for structural subtyping and reference only domain entity types.
"""
from typing import Protocol, Optional, Sequence

from domain.graph.entities import KnowledgeGraph, PathResult, GraphMetrics
from domain.ontology.value_objects import SearchCriteria


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
    """Engine port for semantic search within ontology structures."""

    def semantic_search(self, criteria: SearchCriteria) -> Sequence[str]:
        """Perform semantic search and return matching Class IDs."""
        ...
