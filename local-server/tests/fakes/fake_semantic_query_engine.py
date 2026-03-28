"""Fake in-memory implementation of SemanticQueryEngine for testing.

Provides a simple in-memory semantic/RDF query engine for unit testing.
Stores triples and provides minimal implementations of RDF operations.
"""

import sys
import os
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class FakeSemanticQueryEngine:
    """In-memory implementation of SemanticQueryEngine protocol for unit testing."""

    def __init__(self) -> None:
        """Initialize the fake semantic query engine with empty storage."""
        self._triples: list[tuple[str, str, str]] = []
        self._loaded = False

    def load_ontology(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], property_definitions: list[dict[str, Any]]
    ) -> None:
        """
        Load ontology data into the RDF graph.

        For the fake implementation, creates minimal triples from nodes.
        Each node becomes a triple: (node_id, "rdf:type", node_type)

        Args:
            nodes: Sequence of ontology entity dictionaries
            edges: Sequence of relationship dictionaries (unused in minimal fake)
            property_definitions: Sequence of property definition dictionaries (unused in fake)
        """
        self._triples = []

        # Create minimal triples from nodes
        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("node_type", "unknown")
            triple = (node_id, "rdf:type", node_type)
            self._triples.append(triple)

        # Create minimal triples from edges
        for edge in edges:
            source_id = edge.get("source_id", "")
            target_id = edge.get("target_id", "")
            prop_def_id = edge.get("property_definition_id", "relationship")
            if source_id and target_id:
                triple = (source_id, prop_def_id or "has_relationship", target_id)
                self._triples.append(triple)

        self._loaded = True

    def execute_sparql(self, query: str) -> list[dict[str, Any]]:
        """
        Execute a SPARQL SELECT query against the RDF graph.

        For the fake implementation, returns an empty list.
        Validation is performed by the domain service before invocation.

        Args:
            query: SPARQL query string

        Returns:
            Empty list (minimal fake implementation)
        """
        return []

    def get_triples(
        self, subject: str | None = None, predicate: str | None = None, object: str | None = None
    ) -> list[tuple[str, str, str]]:
        """
        Retrieve RDF triples matching the given pattern.

        Filters stored triples by subject, predicate, and/or object.
        None values match any value in that position.

        Args:
            subject: Optional subject to match
            predicate: Optional predicate to match
            object: Optional object to match

        Returns:
            List of matching triples
        """
        results = []
        for triple in self._triples:
            triple_subject, triple_predicate, triple_object = triple

            # Check each filter
            if subject is not None and triple_subject != subject:
                continue
            if predicate is not None and triple_predicate != predicate:
                continue
            if object is not None and triple_object != object:
                continue

            results.append(triple)

        return results

    def is_loaded(self) -> bool:
        """
        Check if the RDF graph is currently loaded with data.

        Returns:
            True if load_ontology() has been called, False otherwise
        """
        return self._loaded

    def triple_count(self) -> int:
        """
        Get the number of triples in the RDF graph.

        Returns:
            Number of triples currently in the graph
        """
        return len(self._triples)

