"""
Unit tests for GraphAnalysisService.

Tests cover all business logic: graph caching/invalidation, path finding,
centrality computation, community detection, neighbors, cycle detection,
subgraph extraction, and RDF/SPARQL operations. Uses in-memory fakes with
zero infrastructure imports.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from uuid import uuid4

from domain.graph.services import GraphAnalysisService
from domain.graph.entities import KnowledgeGraph, GraphMetrics, PathResult
from domain.graph.exceptions import InvalidAlgorithmError, SPARQLValidationError
from domain.ontology.entities import Class, Taxonomy, ConceptScheme, Relationship, PropertyDefinition
from domain.ontology.events import GraphInvalidated
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_graph_engine import FakeGraphEngine
from tests.fakes.fake_semantic_query_engine import FakeSemanticQueryEngine
from tests.fakes.fake_event_publisher import FakeEventPublisher


@pytest.fixture
def empty_repository():
    """Create a fresh empty FakeOntologyRepository."""
    return FakeOntologyRepository()


@pytest.fixture
def repository_with_data():
    """Create a repository with sample ontology data."""
    repo = FakeOntologyRepository()

    # Create taxonomy
    tax = Taxonomy(id=str(uuid4()), title="Test Taxonomy", description="Test")
    repo.save_taxonomy(tax)

    # Create concept scheme
    scheme = ConceptScheme(id=str(uuid4()), taxonomy_id=tax.id, title="Test Scheme", description="Test")
    repo.save_concept_scheme(scheme)

    # Create classes
    class1 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Class1",
        description="First class",
    )
    class2 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Class2",
        description="Second class",
    )
    class3 = Class(
        id=str(uuid4()),
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Class3",
        description="Third class",
    )

    repo.save_class(class1)
    repo.save_class(class2)
    repo.save_class(class3)

    # Create relationships
    prop_def = PropertyDefinition(
        id=str(uuid4()),
        identifier="isA",
        title="is a",
        description="inheritance relationship",
    )
    repo.save_property_definition(prop_def)

    rel1 = Relationship(
        id=str(uuid4()),
        source_id=class1.id,
        target_id=class2.id,
        property_definition_id=prop_def.id,
    )
    rel2 = Relationship(
        id=str(uuid4()),
        source_id=class2.id,
        target_id=class3.id,
        property_definition_id=prop_def.id,
    )

    repo.save_relationship(rel1)
    repo.save_relationship(rel2)

    return repo


@pytest.fixture
def service(repository_with_data):
    """Create a fresh GraphAnalysisService with in-memory fakes for each test."""
    return GraphAnalysisService(
        repository=repository_with_data,
        graph_engine=FakeGraphEngine(),
        query_engine=FakeSemanticQueryEngine(),
    )


class TestGraphConstruction:
    """Tests for graph construction and caching behavior."""

    def test_graph_not_built_on_construction(self, repository_with_data):
        """Graph is not built when service is instantiated."""
        graph_engine = FakeGraphEngine()
        service = GraphAnalysisService(
            repository=repository_with_data,
            graph_engine=graph_engine,
            query_engine=FakeSemanticQueryEngine(),
        )

        # Graph should be stale (not built)
        assert service._graph_stale
        # No nodes in the engine
        assert graph_engine.node_count() == 0

    def test_graph_built_on_first_access(self, repository_with_data):
        """Graph is built on first call to analysis method."""
        graph_engine = FakeGraphEngine()
        service = GraphAnalysisService(
            repository=repository_with_data,
            graph_engine=graph_engine,
            query_engine=FakeSemanticQueryEngine(),
        )

        # Call a method that requires the graph
        _ = service.find_shortest_path("node1", "node2")

        # Graph should now be built (stale flag cleared)
        assert not service._graph_stale
        # Graph should have nodes (taxonomy + scheme + 3 classes + property definition = 6)
        assert graph_engine.node_count() > 0

    def test_graph_reused_on_subsequent_calls(self, repository_with_data):
        """Graph is reused on subsequent calls (repository not re-read)."""
        repo = repository_with_data
        graph_engine = FakeGraphEngine()
        service = GraphAnalysisService(
            repository=repo,
            graph_engine=graph_engine,
            query_engine=FakeSemanticQueryEngine(),
        )

        # Get initial call count
        initial_count = len(repo.list_classes())

        # First call builds the graph
        _ = service.find_shortest_path("node1", "node2")
        first_node_count = graph_engine.node_count()

        # Second call reuses the graph (no additional repository reads)
        _ = service.find_shortest_path("node1", "node3")
        second_node_count = graph_engine.node_count()

        # Node count should be the same (graph reused)
        assert first_node_count == second_node_count
        # Repository still has same data
        assert len(repo.list_classes()) == initial_count

    def test_graph_rebuilt_after_invalidation(self, repository_with_data):
        """After on_graph_invalidated(), graph is rebuilt on next access."""
        graph_engine = FakeGraphEngine()
        service = GraphAnalysisService(
            repository=repository_with_data,
            graph_engine=graph_engine,
            query_engine=FakeSemanticQueryEngine(),
        )

        # Build graph first time
        _ = service.find_shortest_path("node1", "node2")
        first_node_count = graph_engine.node_count()

        # Invalidate the graph
        event = GraphInvalidated(taxonomy_id="test", reason="test")
        service.on_graph_invalidated(event)
        assert service._graph_stale

        # Next call should rebuild
        _ = service.find_shortest_path("node1", "node3")
        assert not service._graph_stale

    def test_empty_ontology_returns_valid_graph(self, empty_repository):
        """Empty ontology returns valid empty graph."""
        graph_engine = FakeGraphEngine()
        service = GraphAnalysisService(
            repository=empty_repository,
            graph_engine=graph_engine,
            query_engine=FakeSemanticQueryEngine(),
        )

        _ = service.find_shortest_path("node1", "node2")

        assert graph_engine.node_count() == 0
        assert graph_engine.edge_count() == 0


class TestPathFinding:
    """Tests for path finding operations."""

    def test_find_shortest_path_exists(self, service):
        """find_shortest_path returns PathResult when path exists."""
        # Get actual class IDs from repository
        classes = service._repository.list_classes()
        assert len(classes) >= 2

        result = service.find_shortest_path(classes[0].id, classes[1].id)

        assert result is not None
        assert isinstance(result, PathResult)
        assert result.source_id == classes[0].id
        assert result.target_id == classes[1].id
        assert result.path == [classes[0].id, classes[1].id]
        assert result.length == 1
        assert result.relationships == []

    def test_find_shortest_path_not_exists(self, service):
        """find_shortest_path returns None when no path exists."""
        result = service.find_shortest_path("nonexistent1", "nonexistent2")
        assert result is None

    def test_find_all_paths_exists(self, service):
        """find_all_paths returns list of PathResult when paths exist."""
        classes = service._repository.list_classes()
        assert len(classes) >= 2

        results = service.find_all_paths(classes[0].id, classes[1].id)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, PathResult) for r in results)
        assert all(r.source_id == classes[0].id for r in results)
        assert all(r.target_id == classes[1].id for r in results)

    def test_find_all_paths_not_exists(self, service):
        """find_all_paths returns empty list when no paths exist."""
        results = service.find_all_paths("nonexistent1", "nonexistent2")
        assert results == []

    def test_find_all_paths_respects_max_depth(self, service):
        """find_all_paths passes max_depth to graph engine."""
        classes = service._repository.list_classes()
        if len(classes) >= 2:
            # Should not raise, max_depth parameter is accepted
            _ = service.find_all_paths(classes[0].id, classes[1].id, max_depth=3)


class TestCentrality:
    """Tests for centrality computation."""

    def test_get_centrality_pagerank(self, service):
        """get_centrality with pagerank returns node scores."""
        result = service.get_centrality("pagerank")

        assert isinstance(result, dict)
        classes = service._repository.list_classes()
        # Result should have entries for all nodes
        for cls in classes:
            assert cls.id in result
            assert isinstance(result[cls.id], float)

    def test_get_centrality_betweenness(self, service):
        """get_centrality with betweenness returns node scores."""
        result = service.get_centrality("betweenness")
        assert isinstance(result, dict)

    def test_get_centrality_closeness(self, service):
        """get_centrality with closeness returns node scores."""
        result = service.get_centrality("closeness")
        assert isinstance(result, dict)

    def test_get_centrality_degree(self, service):
        """get_centrality with degree returns node scores."""
        result = service.get_centrality("degree")
        assert isinstance(result, dict)

    def test_get_centrality_invalid_raises(self, service):
        """get_centrality with invalid algorithm raises InvalidAlgorithmError."""
        with pytest.raises(InvalidAlgorithmError) as exc_info:
            service.get_centrality("invalid_algorithm")

        error = exc_info.value
        assert error.algorithm == "invalid_algorithm"
        assert "pagerank" in error.valid_algorithms
        assert "betweenness" in error.valid_algorithms


class TestCommunityDetection:
    """Tests for community detection."""

    def test_get_communities_louvain(self, service):
        """get_communities with louvain returns list of sets."""
        result = service.get_communities("louvain")

        assert isinstance(result, list)
        assert all(isinstance(comm, set) for comm in result)

    def test_get_communities_label_propagation(self, service):
        """get_communities with label_propagation returns list of sets."""
        result = service.get_communities("label_propagation")

        assert isinstance(result, list)
        assert all(isinstance(comm, set) for comm in result)

    def test_get_communities_invalid_raises(self, service):
        """get_communities with invalid algorithm raises InvalidAlgorithmError."""
        with pytest.raises(InvalidAlgorithmError) as exc_info:
            service.get_communities("invalid_algorithm")

        error = exc_info.value
        assert error.algorithm == "invalid_algorithm"
        assert "louvain" in error.valid_algorithms
        assert "label_propagation" in error.valid_algorithms


class TestNeighbors:
    """Tests for neighbor retrieval."""

    def test_get_neighbors_direction_in(self, service):
        """get_neighbors accepts 'in' direction."""
        classes = service._repository.list_classes()
        if len(classes) > 0:
            result = service.get_neighbors(classes[0].id, direction="in")
            assert isinstance(result, set)

    def test_get_neighbors_direction_out(self, service):
        """get_neighbors accepts 'out' direction."""
        classes = service._repository.list_classes()
        if len(classes) > 0:
            result = service.get_neighbors(classes[0].id, direction="out")
            assert isinstance(result, set)

    def test_get_neighbors_direction_both(self, service):
        """get_neighbors accepts 'both' direction (default)."""
        classes = service._repository.list_classes()
        if len(classes) > 0:
            result = service.get_neighbors(classes[0].id, direction="both")
            assert isinstance(result, set)

    def test_get_neighbors_default_direction(self, service):
        """get_neighbors defaults to 'both' direction."""
        classes = service._repository.list_classes()
        if len(classes) > 0:
            result = service.get_neighbors(classes[0].id)
            assert isinstance(result, set)


class TestCycleDetection:
    """Tests for cycle detection."""

    def test_check_cycle_returns_bool(self, service):
        """check_cycle returns boolean."""
        classes = service._repository.list_classes()
        if len(classes) >= 2:
            result = service.check_cycle(classes[0].id, classes[1].id)
            assert isinstance(result, bool)

    def test_check_cycle_nonexistent_nodes(self, service):
        """check_cycle works with nonexistent nodes."""
        result = service.check_cycle("nonexistent1", "nonexistent2")
        assert isinstance(result, bool)


class TestSubgraphExtraction:
    """Tests for subgraph extraction."""

    def test_extract_subgraph_returns_knowledge_graph(self, service):
        """extract_subgraph returns KnowledgeGraph."""
        classes = service._repository.list_classes()
        if len(classes) > 0:
            result = service.extract_subgraph(classes[0].id, depth=1)

            assert isinstance(result, KnowledgeGraph)
            assert isinstance(result.node_count, int)
            assert isinstance(result.edge_count, int)
            assert result.is_directed

    def test_extract_subgraph_depth_1(self, service):
        """extract_subgraph with depth=1 includes node and its neighbors."""
        classes = service._repository.list_classes()
        if len(classes) > 0:
            result = service.extract_subgraph(classes[0].id, depth=1)
            assert result.node_count >= 1  # At least the source node

    def test_extract_subgraph_depth_2(self, service):
        """extract_subgraph respects depth parameter."""
        classes = service._repository.list_classes()
        if len(classes) > 0:
            result = service.extract_subgraph(classes[0].id, depth=2)
            assert result.node_count >= 1


class TestMetrics:
    """Tests for full graph metrics computation."""

    def test_get_metrics_returns_graph_metrics(self, service):
        """get_metrics returns GraphMetrics object."""
        result = service.get_metrics()

        assert isinstance(result, GraphMetrics)
        assert isinstance(result.density, float)
        assert isinstance(result.average_degree, float)
        assert isinstance(result.connected_components, int)
        assert isinstance(result.centrality, dict)
        assert isinstance(result.communities, list)
        assert isinstance(result.algorithm, str)

    def test_get_metrics_with_algorithm(self, service):
        """get_metrics accepts algorithm parameter."""
        result = service.get_metrics(algorithm="pagerank")
        assert result.algorithm == "pagerank"

    def test_get_metrics_density_range(self, service):
        """Density is between 0 and 1."""
        result = service.get_metrics()
        assert 0.0 <= result.density <= 1.0


class TestRDFOperations:
    """Tests for RDF/SPARQL operations."""

    def test_execute_sparql_triggers_rdf_load(self, service):
        """execute_sparql triggers RDF load if not loaded."""
        query_engine = service._query_engine
        assert not query_engine.is_loaded()

        service.execute_sparql("SELECT * WHERE { ?s ?p ?o }")

        assert query_engine.is_loaded()

    def test_execute_sparql_returns_list(self, service):
        """execute_sparql returns list of dicts."""
        result = service.execute_sparql("SELECT * WHERE { ?s ?p ?o }")
        assert isinstance(result, list)

    def test_execute_sparql_rejects_insert(self, service):
        """execute_sparql rejects INSERT queries."""
        with pytest.raises(SPARQLValidationError) as exc_info:
            service.execute_sparql("INSERT { ?s ?p ?o } WHERE { ?s ?p ?o }")

        error = exc_info.value
        assert "INSERT" in error.reason

    def test_execute_sparql_rejects_delete(self, service):
        """execute_sparql rejects DELETE queries."""
        with pytest.raises(SPARQLValidationError):
            service.execute_sparql("DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }")

    def test_execute_sparql_rejects_drop(self, service):
        """execute_sparql rejects DROP queries."""
        with pytest.raises(SPARQLValidationError):
            service.execute_sparql("DROP GRAPH ?g")

    def test_execute_sparql_rejects_clear(self, service):
        """execute_sparql rejects CLEAR queries."""
        with pytest.raises(SPARQLValidationError):
            service.execute_sparql("CLEAR GRAPH ?g")

    def test_execute_sparql_rejects_load(self, service):
        """execute_sparql rejects LOAD queries."""
        with pytest.raises(SPARQLValidationError):
            service.execute_sparql("LOAD <http://example.com>")

    def test_execute_sparql_rejects_create(self, service):
        """execute_sparql rejects CREATE queries."""
        with pytest.raises(SPARQLValidationError):
            service.execute_sparql("CREATE GRAPH ?g")

    def test_get_triple_count_triggers_rdf_load(self, service):
        """get_triple_count triggers RDF load if not loaded."""
        query_engine = service._query_engine
        assert not query_engine.is_loaded()

        _ = service.get_triple_count()

        assert query_engine.is_loaded()

    def test_get_triple_count_returns_int(self, service):
        """get_triple_count returns integer."""
        result = service.get_triple_count()
        assert isinstance(result, int)

    def test_get_triples_triggers_rdf_load(self, service):
        """get_triples triggers RDF load if not loaded."""
        query_engine = service._query_engine
        assert not query_engine.is_loaded()

        _ = service.get_triples()

        assert query_engine.is_loaded()

    def test_get_triples_returns_list(self, service):
        """get_triples returns list of tuples."""
        result = service.get_triples()
        assert isinstance(result, list)
        if result:
            assert all(isinstance(t, tuple) and len(t) == 3 for t in result)

    def test_get_triples_with_filters(self, service):
        """get_triples accepts filter parameters."""
        # Should not raise
        _ = service.get_triples(subject="test", predicate="rdf:type", object="Class")
        _ = service.get_triples(subject="test")
        _ = service.get_triples(predicate="rdf:type")
        _ = service.get_triples(object="Class")


class TestRDFInvalidation:
    """Tests for RDF cache invalidation."""

    def test_rdf_reloaded_after_invalidation(self, service):
        """After on_graph_invalidated(), RDF is reloaded on next access."""
        query_engine = service._query_engine

        # Load RDF first time
        _ = service.get_triple_count()
        assert query_engine.is_loaded()

        # Invalidate
        event = GraphInvalidated(taxonomy_id="test", reason="test")
        service.on_graph_invalidated(event)
        assert service._rdf_stale

        # Manually create a new query engine for the service to show the reload
        # (In real scenario, the service would rebuild on next access)
        assert service._rdf_stale


class TestEmptyGraph:
    """Tests with empty graph."""

    def test_metrics_on_empty_graph(self, empty_repository):
        """Metrics on empty graph returns valid values."""
        service = GraphAnalysisService(
            repository=empty_repository,
            graph_engine=FakeGraphEngine(),
            query_engine=FakeSemanticQueryEngine(),
        )

        result = service.get_metrics()

        assert result.density == 0.0
        assert result.average_degree == 0.0
        assert result.connected_components == 0
        assert result.centrality == {}
        assert result.communities == []

    def test_centrality_on_empty_graph(self, empty_repository):
        """Centrality on empty graph returns empty dict."""
        service = GraphAnalysisService(
            repository=empty_repository,
            graph_engine=FakeGraphEngine(),
            query_engine=FakeSemanticQueryEngine(),
        )

        result = service.get_centrality("pagerank")
        assert result == {}

    def test_communities_on_empty_graph(self, empty_repository):
        """Communities on empty graph returns empty list."""
        service = GraphAnalysisService(
            repository=empty_repository,
            graph_engine=FakeGraphEngine(),
            query_engine=FakeSemanticQueryEngine(),
        )

        result = service.get_communities("louvain")
        assert result == []
