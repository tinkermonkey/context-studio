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
from domain.graph.entities import KnowledgeGraph, GraphMetrics, PathResult, SubgraphResult
from domain.graph.exceptions import GraphError, InvalidAlgorithmError, SPARQLValidationError, NodeNotFoundError
from domain.ontology.entities import Class, Taxonomy, ConceptScheme, Relationship, PropertyDefinition
from domain.ontology.events import GraphInvalidated
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_graph_engine import FakeGraphEngine
from tests.fakes.fake_semantic_query_engine import FakeSemanticQueryEngine


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
    """Create a fresh GraphAnalysisService with in-memory fakes for each test.

    Returns a tuple of (service, graph_engine, query_engine) to allow
    tests to access collaborators without touching private service attributes.
    """
    graph_engine = FakeGraphEngine()
    query_engine = FakeSemanticQueryEngine()
    svc = GraphAnalysisService(
        repository=repository_with_data,
        graph_engine=graph_engine,
        query_engine=query_engine,
    )
    return svc, graph_engine, query_engine


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
        graph_engine.node_count()

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


class TestExplicitGraphBuildAndDegrees:
    """Tests for explicit graph building and degree distribution."""

    def test_build_graph_returns_knowledge_graph(self, service):
        """build_graph() returns KnowledgeGraph with node/edge counts."""
        svc, _, _ = service
        result = svc.build_graph()

        assert isinstance(result, KnowledgeGraph)
        assert result.node_count >= 0
        assert result.edge_count >= 0
        assert result.is_directed is True
        assert result.last_built is not None

    def test_build_graph_marks_graph_not_stale(self, service):
        """After build_graph(), graph is no longer marked stale."""
        svc, _, _ = service
        assert svc._graph_stale  # Initially stale

        svc.build_graph()

        assert not svc._graph_stale  # No longer stale

    def test_build_graph_with_data(self, service, repository_with_data):
        """build_graph() with ontology data returns correct counts."""
        svc, _, _ = service
        result = svc.build_graph()

        # Should have at least: 1 taxonomy + 1 scheme + 3 classes = 5 nodes
        # (property definition is also counted as a node in some configurations)
        assert result.node_count > 0
        assert result.edge_count >= 0

    def test_get_degree_distribution_returns_dict(self, service):
        """get_degree_distribution() returns dict of node_id -> degree."""
        svc, _, _ = service
        result = svc.get_degree_distribution()

        assert isinstance(result, dict)
        # Each value should be an int representing the degree
        for node_id, degree in result.items():
            assert isinstance(node_id, str)
            assert isinstance(degree, int)
            assert degree >= 0

    def test_get_degree_distribution_with_data(self, service, repository_with_data):
        """get_degree_distribution() with data includes all nodes."""
        svc, _, _ = service
        result = svc.get_degree_distribution()

        assert isinstance(result, dict)
        # Should have entries for taxonomy, scheme, and classes
        assert len(result) > 0

    def test_get_degree_distribution_marks_graph_not_stale(self, service):
        """After get_degree_distribution(), graph is no longer marked stale."""
        svc, _, _ = service
        assert svc._graph_stale  # Initially stale

        svc.get_degree_distribution()

        assert not svc._graph_stale  # No longer stale


class TestPathFinding:
    """Tests for path finding operations."""

    def test_find_shortest_path_exists(self, service, repository_with_data):
        """find_shortest_path returns PathResult when path exists."""
        svc, _, _ = service
        # Get actual class IDs from repository
        classes = repository_with_data.list_classes()
        assert len(classes) >= 2

        result = svc.find_shortest_path(classes[0].id, classes[1].id)

        assert result is not None
        assert isinstance(result, PathResult)
        assert result.source_id == classes[0].id
        assert result.target_id == classes[1].id
        assert result.path == [classes[0].id, classes[1].id]
        assert result.length == 1
        # Relationships should be populated from edge property definitions
        assert isinstance(result.relationships, list)
        assert len(result.relationships) == 1  # One edge in the path
        assert result.relationships[0] == "is a"  # Property definition title from fixture

    def test_find_shortest_path_not_exists(self, service):
        """find_shortest_path returns None when no path exists."""
        svc, _, _ = service
        result = svc.find_shortest_path("nonexistent1", "nonexistent2")
        assert result is None

    def test_find_all_paths_exists(self, service, repository_with_data):
        """find_all_paths returns list of PathResult when paths exist."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) >= 2

        results = svc.find_all_paths(classes[0].id, classes[1].id)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, PathResult) for r in results)
        assert all(r.source_id == classes[0].id for r in results)
        assert all(r.target_id == classes[1].id for r in results)

    def test_find_all_paths_not_exists(self, service):
        """find_all_paths returns empty list when no paths exist."""
        svc, _, _ = service
        results = svc.find_all_paths("nonexistent1", "nonexistent2")
        assert results == []

    def test_find_all_paths_respects_max_depth(self, service, repository_with_data):
        """find_all_paths passes max_depth to graph engine."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) >= 2
        # Should not raise, max_depth parameter is accepted
        _ = svc.find_all_paths(classes[0].id, classes[1].id, max_depth=3)


class TestCentrality:
    """Tests for centrality computation."""

    def test_get_centrality_pagerank(self, service, repository_with_data):
        """get_centrality with pagerank returns node scores."""
        svc, _, _ = service
        result = svc.get_centrality("pagerank")

        assert isinstance(result, dict)
        classes = repository_with_data.list_classes()
        # Result should have entries for all nodes
        for cls in classes:
            assert cls.id in result
            assert isinstance(result[cls.id], float)

    def test_get_centrality_betweenness(self, service, repository_with_data):
        """get_centrality with betweenness returns node scores."""
        svc, _, _ = service
        result = svc.get_centrality("betweenness")
        assert isinstance(result, dict)
        classes = repository_with_data.list_classes()
        for cls in classes:
            assert cls.id in result
            assert isinstance(result[cls.id], float)

    def test_get_centrality_closeness(self, service, repository_with_data):
        """get_centrality with closeness returns node scores."""
        svc, _, _ = service
        result = svc.get_centrality("closeness")
        assert isinstance(result, dict)
        classes = repository_with_data.list_classes()
        for cls in classes:
            assert cls.id in result
            assert isinstance(result[cls.id], float)

    def test_get_centrality_degree(self, service, repository_with_data):
        """get_centrality with degree returns node scores."""
        svc, _, _ = service
        result = svc.get_centrality("degree")
        assert isinstance(result, dict)
        classes = repository_with_data.list_classes()
        for cls in classes:
            assert cls.id in result
            assert isinstance(result[cls.id], (int, float))

    def test_get_centrality_invalid_raises(self, service):
        """get_centrality with invalid algorithm raises InvalidAlgorithmError."""
        svc, _, _ = service
        with pytest.raises(InvalidAlgorithmError) as exc_info:
            svc.get_centrality("invalid_algorithm")

        error = exc_info.value
        assert error.algorithm == "invalid_algorithm"
        assert "pagerank" in error.valid_algorithms
        assert "betweenness" in error.valid_algorithms


class TestCommunityDetection:
    """Tests for community detection."""

    def test_get_communities_louvain(self, service, repository_with_data):
        """get_communities with louvain returns list of sets."""
        svc, _, _ = service
        result = svc.get_communities("louvain")

        assert isinstance(result, list)
        assert all(isinstance(comm, set) for comm in result)
        # Each community should be non-empty
        assert all(len(comm) > 0 for comm in result)

    def test_get_communities_label_propagation(self, service, repository_with_data):
        """get_communities with label_propagation returns list of sets."""
        svc, _, _ = service
        result = svc.get_communities("label_propagation")

        assert isinstance(result, list)
        assert all(isinstance(comm, set) for comm in result)
        # Each community should be non-empty
        assert all(len(comm) > 0 for comm in result)

    def test_get_communities_invalid_raises(self, service):
        """get_communities with invalid algorithm raises InvalidAlgorithmError."""
        svc, _, _ = service
        with pytest.raises(InvalidAlgorithmError) as exc_info:
            svc.get_communities("invalid_algorithm")

        error = exc_info.value
        assert error.algorithm == "invalid_algorithm"
        assert "louvain" in error.valid_algorithms
        assert "label_propagation" in error.valid_algorithms


class TestNeighbors:
    """Tests for neighbor retrieval."""

    def test_get_neighbors_direction_in(self, service, repository_with_data):
        """get_neighbors accepts 'in' direction and returns node IDs."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        result = svc.get_neighbors(classes[0].id, direction="in")
        assert isinstance(result, set)
        # All neighbors should be valid node IDs
        all_class_ids = {cls.id for cls in classes}
        assert result.issubset(all_class_ids)

    def test_get_neighbors_direction_out(self, service, repository_with_data):
        """get_neighbors accepts 'out' direction and returns node IDs."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        result = svc.get_neighbors(classes[0].id, direction="out")
        assert isinstance(result, set)
        # All neighbors should be valid node IDs
        all_class_ids = {cls.id for cls in classes}
        assert result.issubset(all_class_ids)

    def test_get_neighbors_direction_both(self, service, repository_with_data):
        """get_neighbors accepts 'both' direction and returns node IDs."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        result = svc.get_neighbors(classes[0].id, direction="both")
        assert isinstance(result, set)
        # All neighbors should be valid node IDs
        all_class_ids = {cls.id for cls in classes}
        assert result.issubset(all_class_ids)

    def test_get_neighbors_default_direction(self, service, repository_with_data):
        """get_neighbors defaults to 'both' direction and returns node IDs."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        result = svc.get_neighbors(classes[0].id)
        assert isinstance(result, set)
        # All neighbors should be valid node IDs
        all_class_ids = {cls.id for cls in classes}
        assert result.issubset(all_class_ids)


class TestCycleDetection:
    """Tests for cycle detection."""

    def test_check_cycle_returns_bool(self, service, repository_with_data):
        """check_cycle returns boolean indicating if cycle would be created."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) >= 2
        result = svc.check_cycle(classes[0].id, classes[1].id)
        assert isinstance(result, bool)

    def test_check_cycle_nonexistent_nodes(self, service):
        """check_cycle returns False for nonexistent nodes."""
        svc, _, _ = service
        result = svc.check_cycle("nonexistent1", "nonexistent2")
        assert isinstance(result, bool)
        # No cycle can exist if nodes don't exist
        assert result is False

    def test_check_cycle_self_loop_detection(self, service, repository_with_data):
        """check_cycle detects self-loops (source == target) correctly."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        # A self-loop (same node as source and target) would create a cycle
        # The Relationship entity prevents source_id == target_id in __post_init__,
        # but the graph engine detects whether adding that edge would cause a cycle
        result = svc.check_cycle(classes[0].id, classes[0].id)
        # Self-loops always create cycles by definition
        assert result is True


class TestSubgraphExtraction:
    """Tests for subgraph extraction."""

    def test_extract_subgraph_returns_knowledge_graph(self, service, repository_with_data):
        """extract_subgraph returns KnowledgeGraph with valid counts."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 1
        node_ids = [classes[0].id, classes[1].id]
        result = svc.extract_subgraph(node_ids)

        assert isinstance(result, KnowledgeGraph)
        assert isinstance(result.node_count, int)
        assert isinstance(result.edge_count, int)
        assert result.is_directed
        # Counts should be non-negative
        assert result.node_count >= 0
        assert result.edge_count >= 0

    def test_extract_subgraph_single_node(self, service, repository_with_data):
        """extract_subgraph with single node returns subgraph with that node."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        result = svc.extract_subgraph([classes[0].id])
        assert result.node_count >= 1
        assert result.edge_count >= 0

    def test_extract_subgraph_multiple_nodes(self, service, repository_with_data):
        """extract_subgraph with multiple nodes returns subgraph containing those nodes."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 1
        node_ids = [classes[0].id, classes[1].id]
        result = svc.extract_subgraph(node_ids)
        assert isinstance(result, KnowledgeGraph)
        assert result.node_count >= len(node_ids)
        assert result.edge_count >= 0

    def test_extract_subgraph_by_depth_returns_subgraph_result(self, service, repository_with_data):
        """extract_subgraph_by_depth returns SubgraphResult with depth information."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        result = svc.extract_subgraph_by_depth(classes[0].id, depth=1)

        assert isinstance(result, SubgraphResult)
        assert result.center_node_id == classes[0].id
        assert result.depth == 1
        assert isinstance(result.node_count, int)
        assert isinstance(result.edge_count, int)
        assert result.node_count >= 1  # At least the center node

    def test_extract_subgraph_by_depth_includes_center_node(self, service, repository_with_data):
        """extract_subgraph_by_depth includes the center node in the subgraph."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        center_id = classes[0].id
        result = svc.extract_subgraph_by_depth(center_id, depth=1)
        assert result.node_count >= 1

    def test_extract_subgraph_by_depth_invalid_depth(self, service):
        """extract_subgraph_by_depth raises GraphError for invalid depth."""
        svc, _, _ = service
        with pytest.raises(GraphError):
            svc.extract_subgraph_by_depth("nonexistent", depth=0)

    def test_extract_subgraph_by_depth_nonexistent_center(self, service):
        """extract_subgraph_by_depth raises NodeNotFoundError for nonexistent center node."""
        svc, _, _ = service
        with pytest.raises(NodeNotFoundError):
            svc.extract_subgraph_by_depth("nonexistent-node-id", depth=1)

    def test_extract_subgraph_by_depth_includes_node_ids(self, service, repository_with_data):
        """extract_subgraph_by_depth includes actual node IDs in result."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        center_id = classes[0].id
        result = svc.extract_subgraph_by_depth(center_id, depth=1)

        assert hasattr(result, "node_ids")
        assert isinstance(result.node_ids, list)
        assert center_id in result.node_ids
        assert len(result.node_ids) == result.node_count

    def test_extract_subgraph_by_depth_includes_edge_ids(self, service, repository_with_data):
        """extract_subgraph_by_depth includes actual edge IDs in result."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        center_id = classes[0].id
        result = svc.extract_subgraph_by_depth(center_id, depth=1)

        assert hasattr(result, "edge_ids")
        assert isinstance(result.edge_ids, list)
        assert len(result.edge_ids) == result.edge_count

    def test_extract_subgraph_by_depth_depth_2_expands_neighborhood(self, service, repository_with_data):
        """extract_subgraph_by_depth with depth=2 returns nodes beyond immediate neighbors."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()

        # Get subgraph with depth=1 and depth=2 from the same node
        result_depth_1 = svc.extract_subgraph_by_depth(classes[0].id, depth=1)
        result_depth_2 = svc.extract_subgraph_by_depth(classes[0].id, depth=2)

        # Depth 2 should have at least as many nodes as depth 1
        assert result_depth_2.node_count >= result_depth_1.node_count
        assert result_depth_2.depth == 2

    def test_extract_subgraph_by_depth_depth_3_further_expansion(self, service, repository_with_data):
        """extract_subgraph_by_depth with depth=3 returns nodes at greater distance."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()

        # Get subgraph with depth=2 and depth=3 from the same node
        result_depth_2 = svc.extract_subgraph_by_depth(classes[0].id, depth=2)
        result_depth_3 = svc.extract_subgraph_by_depth(classes[0].id, depth=3)

        # Depth 3 should have at least as many nodes as depth 2
        assert result_depth_3.node_count >= result_depth_2.node_count
        assert result_depth_3.depth == 3

    def test_extract_subgraph_by_depth_node_ids_count_consistency(self, service, repository_with_data):
        """node_count must match the length of node_ids list."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        center_id = classes[0].id
        result = svc.extract_subgraph_by_depth(center_id, depth=2)

        assert result.node_count == len(result.node_ids)
        assert result.edge_count == len(result.edge_ids)

    def test_extract_subgraph_by_depth_edge_ids_valid_tuples(self, service, repository_with_data):
        """edge_ids are valid (source, target) tuples with both endpoints in node_ids."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        center_id = classes[0].id
        result = svc.extract_subgraph_by_depth(center_id, depth=2)

        node_id_set = set(result.node_ids)
        for edge_tuple in result.edge_ids:
            assert isinstance(edge_tuple, tuple)
            assert len(edge_tuple) == 2
            source_id, target_id = edge_tuple
            assert source_id in node_id_set, f"Edge source {source_id} not in node_ids"
            assert target_id in node_id_set, f"Edge target {target_id} not in node_ids"


class TestMetrics:
    """Tests for graph metrics computation."""

    def test_get_metrics_returns_graph_metrics(self, service):
        """get_metrics returns GraphMetrics."""
        svc, _, _ = service
        result = svc.get_metrics()

        assert isinstance(result, GraphMetrics)
        assert isinstance(result.density, float)
        assert isinstance(result.average_degree, float)
        assert isinstance(result.connected_components, int)
        assert isinstance(result.centrality, dict)
        assert isinstance(result.communities, list)
        assert isinstance(result.algorithm, str)

    def test_get_metrics_density_in_range(self, service):
        """get_metrics density is between 0 and 1."""
        svc, _, _ = service
        result = svc.get_metrics()
        assert 0.0 <= result.density <= 1.0

    def test_get_metrics_has_centrality(self, service):
        """get_metrics includes centrality scores."""
        svc, _, _ = service
        result = svc.get_metrics()
        # Should have some centrality scores
        assert isinstance(result.centrality, dict)


class TestRDFOperations:
    """Tests for RDF/SPARQL operations."""

    def test_get_triple_count_returns_int(self, service):
        """get_triple_count returns integer."""
        svc, _, query_engine = service
        result = svc.get_triple_count()
        assert isinstance(result, int)
        assert query_engine.is_loaded()

    def test_get_triple_count_consistent(self, service):
        """get_triple_count returns same value on subsequent calls."""
        svc, _, query_engine = service
        first_count = svc.get_triple_count()
        second_count = svc.get_triple_count()
        assert first_count == second_count

    def test_execute_sparql_triggers_rdf_load(self, service):
        """execute_sparql triggers RDF load if not loaded."""
        svc, _, query_engine = service
        # Query engine should not be loaded yet
        assert not query_engine.is_loaded()
        # Call execute_sparql
        _ = svc.execute_sparql("SELECT * WHERE { ?s ?p ?o }")
        # Query engine should now be loaded
        assert query_engine.is_loaded()

    def test_execute_sparql_returns_list(self, service):
        """execute_sparql returns list of results."""
        svc, _, _ = service
        results = svc.execute_sparql("SELECT * WHERE { ?s ?p ?o }")
        assert isinstance(results, list)

    def test_execute_sparql_empty_query(self, service):
        """execute_sparql handles empty results."""
        svc, _, _ = service
        results = svc.execute_sparql("SELECT * WHERE { ?s ?p ?o . FILTER(false) }")
        assert isinstance(results, list)

    def test_get_triples_triggers_rdf_load(self, service):
        """get_triples triggers RDF load if not loaded."""
        svc, _, query_engine = service
        # Query engine should not be loaded yet
        assert not query_engine.is_loaded()
        # Call get_triples
        _ = svc.get_triples()
        # Query engine should now be loaded
        assert query_engine.is_loaded()

    def test_get_triples_by_subject(self, service, repository_with_data):
        """get_triples filters by subject."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        triples = svc.get_triples(subject=classes[0].id)
        assert isinstance(triples, list)

    def test_get_triples_by_predicate(self, service):
        """get_triples filters by predicate."""
        svc, _, _ = service
        triples = svc.get_triples(predicate="rdf:type")
        assert isinstance(triples, list)

    def test_get_triples_by_object(self, service):
        """get_triples filters by object."""
        svc, _, _ = service
        triples = svc.get_triples(object="owl:Class")
        assert isinstance(triples, list)

    def test_get_triples_all_params(self, service, repository_with_data):
        """get_triples with all parameters filters correctly."""
        svc, _, _ = service
        classes = repository_with_data.list_classes()
        assert len(classes) > 0
        triples = svc.get_triples(
            subject=classes[0].id,
            predicate="rdf:type",
            object="owl:Class"
        )
        assert isinstance(triples, list)

    def test_execute_sparql_rejects_insert(self, service):
        """execute_sparql rejects INSERT keyword."""
        svc, _, _ = service
        with pytest.raises(SPARQLValidationError):
            svc.execute_sparql("INSERT DATA { <s> <p> <o> }")

    def test_execute_sparql_rejects_delete(self, service):
        """execute_sparql rejects DELETE keyword."""
        svc, _, _ = service
        with pytest.raises(SPARQLValidationError):
            svc.execute_sparql("DELETE DATA { <s> <p> <o> }")

    def test_execute_sparql_rejects_drop(self, service):
        """execute_sparql rejects DROP keyword."""
        svc, _, _ = service
        with pytest.raises(SPARQLValidationError):
            svc.execute_sparql("DROP GRAPH <graph>")

    def test_execute_sparql_rejects_clear(self, service):
        """execute_sparql rejects CLEAR keyword."""
        svc, _, _ = service
        with pytest.raises(SPARQLValidationError):
            svc.execute_sparql("CLEAR GRAPH <graph>")

    def test_execute_sparql_rejects_load(self, service):
        """execute_sparql rejects LOAD keyword."""
        svc, _, _ = service
        with pytest.raises(SPARQLValidationError):
            svc.execute_sparql("LOAD <http://example.org/data>")

    def test_execute_sparql_rejects_create(self, service):
        """execute_sparql rejects CREATE keyword."""
        svc, _, _ = service
        with pytest.raises(SPARQLValidationError):
            svc.execute_sparql("CREATE GRAPH <graph>")

    def test_execute_sparql_allows_created_by_substring(self, service):
        """Word-boundary regex allows 'CREATED_BY' inside string literals."""
        svc, _, _ = service
        # Should not raise — 'CREATED_BY' is not a keyword, it contains 'CREATE'
        # but is not a standalone CREATE keyword
        result = svc.execute_sparql(
            'SELECT ?s WHERE { ?s rdfs:label "CREATED_BY" }'
        )
        assert result is not None

    def test_execute_sparql_allows_created_date_identifier(self, service):
        """Word-boundary regex allows 'created_date' as identifier."""
        svc, _, _ = service
        # Should not raise — 'created_date' is not the CREATE keyword
        result = svc.execute_sparql(
            'SELECT ?created_date WHERE { ?s ex:created_date ?created_date }'
        )
        assert result is not None


class TestRDFInvalidation:
    """Tests for RDF cache invalidation."""

    def test_rdf_reloaded_after_invalidation(self, service):
        """After on_graph_invalidated(), RDF is reloaded on next access."""
        svc, _, query_engine = service

        # Load RDF first time
        first_count = svc.get_triple_count()
        assert query_engine.is_loaded()

        # Invalidate
        event = GraphInvalidated(taxonomy_id="test", reason="test")
        svc.on_graph_invalidated(event)
        assert svc._rdf_stale

        # Next call reloads RDF
        second_count = svc.get_triple_count()
        # Both calls should return same data (consistent reloads)
        assert first_count == second_count
        # Query engine should still be loaded
        assert query_engine.is_loaded()


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

    def test_rdf_on_empty_graph(self, empty_repository):
        """RDF operations on empty graph return empty results."""
        service = GraphAnalysisService(
            repository=empty_repository,
            graph_engine=FakeGraphEngine(),
            query_engine=FakeSemanticQueryEngine(),
        )

        assert service.get_triple_count() == 0
        assert service.execute_sparql("SELECT * WHERE { ?s ?p ?o }") == []
