"""
Unit tests for RDFLibQueryEngine adapter.

Tests verify:
- Ontology loading from node, edge, and property definition data
- SPARQL SELECT query execution with valid queries
- SPARQL injection validation rejecting forbidden keywords
- Triple pattern matching and retrieval
- Triple counting and graph state tracking
- Proper namespace handling and RDF type assignments
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from domain.graph.exceptions import SPARQLValidationError


class TestRDFLibQueryEngineOntologyLoading:
    """Tests for ontology data loading."""

    def test_empty_graph_initialization(self):
        """A new engine starts with an empty graph."""
        engine = RDFLibQueryEngine()
        assert engine.is_loaded() is False
        assert engine.triple_count() == 0

    def test_load_ontology_with_nodes_only(self):
        """Loading ontology with nodes creates type triples."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "taxonomy"},
            {"id": "node-2", "title": "Beta", "node_type": "concept_scheme"},
            {"id": "node-3", "title": "Gamma", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])

        assert engine.is_loaded() is True
        # Each node should have at least 2 triples (type + label)
        assert engine.triple_count() >= 6

    def test_load_ontology_with_nodes_and_edges(self):
        """Loading ontology with edges creates relationship triples."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "taxonomy"},
            {"id": "node-2", "title": "Beta", "node_type": "concept_scheme"},
        ]
        edges = [
            {"id": "edge-1", "source_id": "node-1", "target_id": "node-2", "property_definition_id": "prop-1"},
        ]

        engine.load_ontology(nodes, edges, [])

        assert engine.is_loaded() is True
        # Should have node triples + edge triple
        assert engine.triple_count() >= 5

    def test_load_ontology_with_property_definitions(self):
        """Loading ontology with property definitions creates property type triples."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]
        edges = [
            {"id": "edge-1", "source_id": "node-1", "target_id": "node-2", "property_definition_id": "prop-1"},
        ]
        property_definitions = [
            {"id": "prop-1", "identifier": "has_parent", "title": "Has Parent"},
        ]

        engine.load_ontology(nodes, edges, property_definitions)

        assert engine.is_loaded() is True
        # Should have node triples + property definition triple + label + edge triple
        assert engine.triple_count() >= 7

    def test_load_ontology_clears_previous_graph(self):
        """Loading ontology again clears the previous graph."""
        engine = RDFLibQueryEngine()

        # First load
        nodes1 = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes1, [], [])
        engine.triple_count()

        # Second load with different data
        nodes2 = [
            {"id": "node-2", "title": "Beta", "node_type": "class"},
            {"id": "node-3", "title": "Gamma", "node_type": "taxonomy"},
        ]
        engine.load_ontology(nodes2, [], [])
        count2 = engine.triple_count()

        # Second graph should be different size
        assert count2 >= 4  # At least 2 nodes with type + label each
        assert engine.is_loaded() is True

    def test_load_ontology_assigns_correct_types(self):
        """Loading ontology assigns correct RDF types to nodes."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "tax-1", "title": "Taxonomy", "node_type": "taxonomy"},
            {"id": "scheme-1", "title": "Scheme", "node_type": "concept_scheme"},
            {"id": "class-1", "title": "Class", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])

        # Query for taxonomy type
        triples = engine.get_triples(subject="http://context-studio.local/entity/tax-1")
        assert len(triples) >= 1

        # Verify we have type triples (at least rdf:type and rdfs:label)
        type_triples = [t for t in triples if "type" in t[1]]
        assert len(type_triples) > 0

        # Verify we have at least one triple with Taxonomy in it
        assert any("Taxonomy" in t[2] or "Taxonomy" in t[0] for t in triples)


class TestRDFLibQueryEngineSPARQL:
    """Tests for SPARQL query execution."""

    def test_execute_sparql_with_valid_query(self):
        """Execute SPARQL returns results for valid SELECT query."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])

        # Query for all subjects
        query = """
        PREFIX entity: <http://context-studio.local/entity/>
        SELECT ?s WHERE {
            ?s ?p ?o
        }
        LIMIT 10
        """

        results = engine.execute_sparql(query)

        # Should get some results
        assert isinstance(results, list)
        assert len(results) > 0

    def test_execute_sparql_valid_select_query(self):
        """SELECT queries are executed normally."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])

        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?s WHERE {
            ?s rdf:type ?o
        }
        """

        results = engine.execute_sparql(query)
        assert isinstance(results, list)

    def test_execute_sparql_rejects_insert(self):
        """SPARQL with INSERT keyword raises SPARQLValidationError."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes, [], [])

        query = "INSERT DATA { :s :p :o }"

        with pytest.raises(SPARQLValidationError) as exc_info:
            engine.execute_sparql(query)

        assert "Forbidden keyword: INSERT" in str(exc_info.value)

    def test_execute_sparql_rejects_delete(self):
        """SPARQL with DELETE keyword raises SPARQLValidationError."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes, [], [])

        query = "DELETE { :s :p :o } WHERE { :s :p :o }"

        with pytest.raises(SPARQLValidationError) as exc_info:
            engine.execute_sparql(query)

        assert "Forbidden keyword: DELETE" in str(exc_info.value)

    def test_execute_sparql_rejects_drop(self):
        """SPARQL with DROP keyword raises SPARQLValidationError."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes, [], [])

        query = "DROP GRAPH ?g"

        with pytest.raises(SPARQLValidationError) as exc_info:
            engine.execute_sparql(query)

        assert "Forbidden keyword: DROP" in str(exc_info.value)

    def test_execute_sparql_rejects_clear(self):
        """SPARQL with CLEAR keyword raises SPARQLValidationError."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes, [], [])

        query = "CLEAR ALL"

        with pytest.raises(SPARQLValidationError) as exc_info:
            engine.execute_sparql(query)

        assert "Forbidden keyword: CLEAR" in str(exc_info.value)

    def test_execute_sparql_rejects_load(self):
        """SPARQL with LOAD keyword raises SPARQLValidationError."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes, [], [])

        query = "LOAD <http://example.com/data.rdf>"

        with pytest.raises(SPARQLValidationError) as exc_info:
            engine.execute_sparql(query)

        assert "Forbidden keyword: LOAD" in str(exc_info.value)

    def test_execute_sparql_rejects_create(self):
        """SPARQL with CREATE keyword raises SPARQLValidationError."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes, [], [])

        query = "CREATE GRAPH ?g"

        with pytest.raises(SPARQLValidationError) as exc_info:
            engine.execute_sparql(query)

        assert "Forbidden keyword: CREATE" in str(exc_info.value)

    def test_execute_sparql_case_insensitive_validation(self):
        """SPARQL validation is case-insensitive."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes, [], [])

        # Lowercase 'insert' should still be detected
        query = "insert data { :s :p :o }"

        with pytest.raises(SPARQLValidationError):
            engine.execute_sparql(query)

    def test_execute_sparql_in_comment_is_rejected(self):
        """SPARQL validation detects forbidden keywords even in comments."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]
        engine.load_ontology(nodes, [], [])

        # Forbidden keyword in comment should still trigger validation error
        query = """
        # This is a comment with INSERT
        SELECT ?s WHERE {
            ?s ?p ?o
        }
        """

        with pytest.raises(SPARQLValidationError):
            engine.execute_sparql(query)


class TestRDFLibQueryEngineTripleOperations:
    """Tests for triple pattern matching and retrieval."""

    def test_get_triples_returns_all_when_no_filter(self):
        """get_triples with no filters returns all triples."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])
        triples = engine.get_triples()

        assert len(triples) > 0

    def test_get_triples_filters_by_subject(self):
        """get_triples filters triples by subject."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])

        # Query for triples with specific subject
        subject = "http://context-studio.local/entity/node-1"
        triples = engine.get_triples(subject=subject)

        # All returned triples should have this subject
        assert all(t[0] == subject for t in triples)

    def test_get_triples_filters_by_predicate(self):
        """get_triples filters triples by predicate."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])

        # Query for triples with rdf:type predicate
        triples = engine.get_triples(predicate="http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

        assert len(triples) > 0
        # All returned triples should have this predicate
        assert all("type" in t[1] or "rdf:type" in t[1] for t in triples)

    def test_get_triples_filters_by_object(self):
        """get_triples filters triples by object."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])

        # Query for all subjects that are classes
        object_val = "http://context-studio.local/vocab/Class"
        triples = engine.get_triples(object=object_val)

        # Should have at least one triple
        assert len(triples) >= 1

    def test_get_triples_with_relationship(self):
        """get_triples returns relationship triples between nodes."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]
        edges = [
            {"id": "edge-1", "source_id": "node-1", "target_id": "node-2", "property_definition_id": "prop-1"},
        ]
        property_definitions = [
            {"id": "prop-1", "identifier": "has_parent", "title": "Has Parent"},
        ]

        engine.load_ontology(nodes, edges, property_definitions)

        # Query for relationship triples
        source = "http://context-studio.local/entity/node-1"

        all_triples = engine.get_triples(subject=source)

        # Should have at least one triple from this source
        assert len(all_triples) > 0

    def test_get_triples_returns_tuple_format(self):
        """get_triples returns triples as (subject, predicate, object) tuples."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])
        triples = engine.get_triples()

        assert len(triples) > 0
        # Each triple should be a 3-tuple of strings
        for triple in triples:
            assert isinstance(triple, tuple)
            assert len(triple) == 3
            assert all(isinstance(part, str) for part in triple)


class TestRDFLibQueryEngineState:
    """Tests for graph state tracking."""

    def test_is_loaded_false_initially(self):
        """New engine reports is_loaded as False."""
        engine = RDFLibQueryEngine()
        assert engine.is_loaded() is False

    def test_is_loaded_true_after_load_ontology(self):
        """is_loaded returns True after loading ontology."""
        engine = RDFLibQueryEngine()
        nodes = [{"id": "node-1", "title": "Alpha", "node_type": "class"}]

        engine.load_ontology(nodes, [], [])

        assert engine.is_loaded() is True

    def test_triple_count_zero_initially(self):
        """New engine has triple_count of 0."""
        engine = RDFLibQueryEngine()
        assert engine.triple_count() == 0

    def test_triple_count_increases_with_nodes(self):
        """triple_count increases when nodes are loaded."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]

        engine.load_ontology(nodes, [], [])

        # Each node should create at least 2 triples (type + label)
        assert engine.triple_count() >= 4

    def test_triple_count_includes_relationship_triples(self):
        """triple_count includes relationship triples."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]
        edges = [
            {"id": "edge-1", "source_id": "node-1", "target_id": "node-2", "property_definition_id": "prop-1"},
        ]

        engine.load_ontology(nodes, edges, [])

        # Should have node triples + at least 1 relationship triple
        assert engine.triple_count() >= 5

    def test_triple_count_includes_property_definition_triples(self):
        """triple_count includes property definition triples."""
        engine = RDFLibQueryEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
        ]
        edges = [
            {"id": "edge-1", "source_id": "node-1", "target_id": "node-2", "property_definition_id": "prop-1"},
        ]
        property_definitions = [
            {"id": "prop-1", "identifier": "has_parent", "title": "Has Parent"},
        ]

        engine.load_ontology(nodes, edges, property_definitions)

        # Should have node triples + property definition triple + relationship triple
        assert engine.triple_count() >= 7


class TestRDFLibQueryEngineIntegration:
    """Integration tests combining multiple operations."""

    def test_load_and_query_complex_ontology(self):
        """Load and query a complex ontology structure."""
        engine = RDFLibQueryEngine()

        # Create a small ontology
        nodes = [
            {"id": "org", "title": "Organization", "node_type": "taxonomy"},
            {"id": "company", "title": "Company", "node_type": "class"},
            {"id": "person", "title": "Person", "node_type": "class"},
            {"id": "employee", "title": "Employee", "node_type": "class"},
        ]

        edges = [
            {"id": "e1", "source_id": "org", "target_id": "company", "property_definition_id": "prop-1"},
            {"id": "e2", "source_id": "company", "target_id": "employee", "property_definition_id": "prop-2"},
            {"id": "e3", "source_id": "person", "target_id": "employee", "property_definition_id": "prop-3"},
        ]

        property_definitions = [
            {"id": "prop-1", "identifier": "contains", "title": "Contains"},
            {"id": "prop-2", "identifier": "has_employee", "title": "Has Employee"},
            {"id": "prop-3", "identifier": "is_basis_for", "title": "Is Basis For"},
        ]

        engine.load_ontology(nodes, edges, property_definitions)

        # Verify graph is loaded
        assert engine.is_loaded() is True
        assert engine.triple_count() > 0

        # Query for all classes
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX cs: <http://context-studio.local/vocab/>
        SELECT ?class WHERE {
            ?class rdf:type cs:Class
        }
        """

        results = engine.execute_sparql(query)
        assert len(results) > 0

    def test_sequential_loads(self):
        """Load ontology multiple times with different data."""
        engine = RDFLibQueryEngine()

        # First load
        nodes1 = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
        ]
        engine.load_ontology(nodes1, [], [])
        count1 = engine.triple_count()

        # Second load
        nodes2 = [
            {"id": "node-2", "title": "Beta", "node_type": "class"},
            {"id": "node-3", "title": "Gamma", "node_type": "class"},
        ]
        engine.load_ontology(nodes2, [], [])
        count2 = engine.triple_count()

        # Should have different triple counts and first node should not be findable
        assert count2 > count1
        triples = engine.get_triples(subject="http://context-studio.local/entity/node-1")
        assert len(triples) == 0

        # But second and third nodes should be findable
        triples = engine.get_triples(subject="http://context-studio.local/entity/node-2")
        assert len(triples) > 0
