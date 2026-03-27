"""
RDFLib-based implementation of the SemanticQueryEngine port.

Provides RDF/SPARQL operations on ontology knowledge using RDFLib's in-memory graph,
supporting semantic queries, SPARQL execution, and triple pattern matching.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS
from rdflib.exceptions import ParserError

from domain.graph.exceptions import SPARQLValidationError

# Define namespaces for Context Studio ontology
CS = Namespace("http://context-studio.local/vocab/")
ENTITY = Namespace("http://context-studio.local/entity/")


class RDFLibQueryEngine:
    """
    Semantic query engine implementation using RDFLib for RDF/SPARQL operations.

    This engine provides the SemanticQueryEngine protocol interface by wrapping an
    RDFLib in-memory graph and supporting SPARQL queries with validation.
    """

    def __init__(self) -> None:
        """Initialize the RDFLib query engine with an empty in-memory graph."""
        self._graph = Graph()
        self._loaded = False

    def load_ontology(
        self, nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]], property_definitions: Sequence[dict[str, Any]]
    ) -> None:
        """
        Load ontology data into the RDF graph.

        Converts ontology entities to RDF triples using standard RDF vocabularies,
        then adds relationship triples using property definitions.

        Args:
            nodes: Sequence of ontology entity dictionaries (Taxonomy, ConceptScheme, Class, etc.)
            edges: Sequence of relationship dictionaries linking entities
            property_definitions: Sequence of property definition dictionaries for relationship types
        """
        # Clear any existing graph
        self._graph = Graph()

        # Bind namespaces for better readability
        self._graph.bind("cs", CS)
        self._graph.bind("entity", ENTITY)
        self._graph.bind("rdf", RDF)
        self._graph.bind("rdfs", RDFS)

        # Create a mapping of property definition IDs to URIs
        prop_def_map = {}
        for prop_def in property_definitions:
            prop_def_id = prop_def.get("id", "")
            prop_identifier = prop_def.get("identifier", "")
            prop_title = prop_def.get("title", "")

            if prop_def_id:
                # Create a property URI using the identifier or title
                prop_uri = CS[prop_identifier or prop_title or prop_def_id]
                prop_def_map[prop_def_id] = prop_uri

                # Add property definition as a type of RDF property
                self._graph.add((prop_uri, RDF.type, RDF.Property))
                if prop_title:
                    self._graph.add((prop_uri, RDFS.label, Literal(prop_title)))

        # Add node/entity triples
        for node in nodes:
            node_id = node.get("id", "")
            node_title = node.get("title", "")
            node_type = node.get("node_type", "")

            if node_id:
                subject = ENTITY[str(node_id)]

                # Add type triple based on node_type
                if node_type == "taxonomy":
                    self._graph.add((subject, RDF.type, CS.Taxonomy))
                elif node_type == "concept_scheme":
                    self._graph.add((subject, RDF.type, CS.ConceptScheme))
                elif node_type == "class":
                    self._graph.add((subject, RDF.type, CS.Class))
                else:
                    # Generic type for unknown node types
                    self._graph.add((subject, RDF.type, CS[node_type]))

                # Add label triple if title is available
                if node_title:
                    self._graph.add((subject, RDFS.label, Literal(node_title)))

        # Add relationship/edge triples
        for edge in edges:
            source_id = edge.get("source_id", "")
            target_id = edge.get("target_id", "")
            prop_def_id = edge.get("property_definition_id")

            if source_id and target_id:
                source = ENTITY[str(source_id)]
                target = ENTITY[str(target_id)]

                # Use the property definition URI if available, otherwise use a default
                if prop_def_id and prop_def_id in prop_def_map:
                    predicate = prop_def_map[prop_def_id]
                else:
                    # Default predicate for relationships
                    predicate = CS.hasRelation

                self._graph.add((source, predicate, target))

        self._loaded = True

    def execute_sparql(self, query: str) -> list[dict[str, Any]]:
        """
        Execute a SPARQL SELECT query against the RDF graph.

        Validates the query to ensure it is a read-only SELECT operation,
        then executes it and returns the results.

        Args:
            query: SPARQL query string (SELECT queries only)

        Returns:
            List of result dictionaries, where each dict maps variable names to values

        Raises:
            SPARQLValidationError: If the query contains forbidden keywords or has syntax errors
        """
        # Validate the query before executing
        self._validate_sparql(query)

        # Execute the SPARQL query
        try:
            results = self._graph.query(query)
        except ParserError as e:
            raise SPARQLValidationError(query, f"SPARQL syntax error: {str(e)}")

        # Convert results to list of dicts
        result_list = []
        for row in results:
            # RDFLib query results are Row objects with variable names
            # Convert to dict mapping variable names to their values (as strings)
            row_dict = {}
            if results.vars is not None:
                for var in results.vars:
                    value = row[var]  # type: ignore
                    row_dict[str(var)] = str(value) if value is not None else None
            result_list.append(row_dict)

        return result_list

    def get_triples(
        self, subject: str | None = None, predicate: str | None = None, object: str | None = None
    ) -> list[tuple[str, str, str]]:
        """
        Retrieve RDF triples matching the given pattern.

        Uses RDFLib's triple pattern matching to find matching triples.
        Any parameter may be None to match any value in that position.

        Args:
            subject: Optional subject URI/ID to match
            predicate: Optional predicate URI/property to match
            object: Optional object value to match

        Returns:
            List of matching triples, each as (subject, predicate, object)
        """
        results = []

        # Convert parameters to URIRefs or None
        subject_uri = URIRef(subject) if subject else None
        predicate_uri = URIRef(predicate) if predicate else None
        object_uri = URIRef(object) if object else None

        # Query triples using RDFLib's triple pattern matching
        for s, p, o in self._graph.triples((subject_uri, predicate_uri, object_uri)):
            results.append((str(s), str(p), str(o)))

        return results

    def is_loaded(self) -> bool:
        """
        Check if the RDF graph is currently loaded with data.

        Returns:
            True if load_ontology() has been called and the graph contains data
        """
        return self._loaded and len(self._graph) > 0

    def triple_count(self) -> int:
        """
        Get the number of triples in the RDF graph.

        Returns:
            Number of triples currently in the graph
        """
        return len(self._graph)

    def _validate_sparql(self, query: str) -> None:
        """
        Validate SPARQL query to prevent dangerous operations.

        Only SELECT queries are allowed. Queries containing INSERT, DELETE, DROP,
        CLEAR, LOAD, or CREATE operations are rejected for safety.

        Uses word-boundary regex matching to avoid false positives from substring
        matching (e.g., "CREATE" inside "CREATED_BY" string literal).

        Args:
            query: The SPARQL query to validate

        Raises:
            SPARQLValidationError: If the query contains forbidden keywords
        """
        forbidden_keywords = {"INSERT", "DELETE", "DROP", "CLEAR", "LOAD", "CREATE"}

        query_upper = query.upper()

        for keyword in forbidden_keywords:
            # Use word-boundary regex to match only complete keywords, not substrings
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, query_upper):
                raise SPARQLValidationError(query, f"Forbidden keyword: {keyword}")
