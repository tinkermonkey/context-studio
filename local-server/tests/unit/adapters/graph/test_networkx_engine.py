"""
Unit tests for NetworkXGraphEngine adapter.

Tests verify:
- Graph construction from node and edge data
- Shortest path finding (exists and not exists cases)
- All paths enumeration with depth limiting
- Centrality algorithms (pagerank, betweenness, closeness, degree)
- Community detection (louvain and label_propagation)
- Neighbor discovery in all directions (in, out, both)
- Cycle detection for proposed edges
- Subgraph extraction
- Degree distribution calculation
- Connected component counting
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
from adapters.graph.networkx_engine import NetworkXGraphEngine
from domain.graph.exceptions import NodeNotFoundError


class TestNetworkXGraphEngineConstruction:
    """Tests for graph construction and basic properties."""

    def test_empty_graph_initialization(self):
        """A new engine starts with an empty graph."""
        engine = NetworkXGraphEngine()
        assert engine.node_count() == 0
        assert engine.edge_count() == 0

    def test_build_from_data_with_simple_nodes(self):
        """Graph construction correctly adds nodes with attributes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "taxonomy"},
        ]
        edges = []

        engine.build_from_data(nodes, edges)

        assert engine.node_count() == 2
        assert engine.edge_count() == 0

    def test_build_from_data_with_nodes_and_edges(self):
        """Graph construction correctly adds nodes and edges with attributes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "node-1", "title": "Alpha", "node_type": "class"},
            {"id": "node-2", "title": "Beta", "node_type": "class"},
            {"id": "node-3", "title": "Gamma", "node_type": "taxonomy"},
        ]
        edges = [
            {"id": "edge-1", "source_id": "node-1", "target_id": "node-2", "property_definition_id": "prop-1"},
            {"id": "edge-2", "source_id": "node-2", "target_id": "node-3", "property_definition_id": "prop-1"},
        ]

        engine.build_from_data(nodes, edges)

        assert engine.node_count() == 3
        assert engine.edge_count() == 2

    def test_build_from_data_clears_previous_graph(self):
        """Calling build_from_data again clears the previous graph."""
        engine = NetworkXGraphEngine()

        # First build
        nodes1 = [
            {"id": "node-1", "title": "Alpha"},
            {"id": "node-2", "title": "Beta"},
        ]
        engine.build_from_data(nodes1, [])
        assert engine.node_count() == 2

        # Second build
        nodes2 = [
            {"id": "node-3", "title": "Gamma"},
        ]
        engine.build_from_data(nodes2, [])
        assert engine.node_count() == 1
        assert engine.edge_count() == 0


class TestNetworkXGraphEngineShortestPath:
    """Tests for shortest path finding."""

    def test_shortest_path_between_adjacent_nodes(self):
        """Shortest path between adjacent nodes returns direct path."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "node-1", "title": "Start"},
            {"id": "node-2", "title": "End"},
        ]
        edges = [
            {"id": "edge-1", "source_id": "node-1", "target_id": "node-2"},
        ]

        engine.build_from_data(nodes, edges)
        path = engine.shortest_path("node-1", "node-2")

        assert path == ["node-1", "node-2"]

    def test_shortest_path_with_intermediate_nodes(self):
        """Shortest path returns the shortest route through intermediate nodes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "node-1"},
            {"id": "node-2"},
            {"id": "node-3"},
            {"id": "node-4"},
        ]
        edges = [
            {"source_id": "node-1", "target_id": "node-2"},
            {"source_id": "node-2", "target_id": "node-4"},
            {"source_id": "node-1", "target_id": "node-3"},
            {"source_id": "node-3", "target_id": "node-4"},
        ]

        engine.build_from_data(nodes, edges)
        path = engine.shortest_path("node-1", "node-4")

        # Both paths have the same length, but NetworkX returns one of them
        assert path is not None
        assert len(path) == 3
        assert path[0] == "node-1"
        assert path[-1] == "node-4"

    def test_shortest_path_nonexistent_returns_none(self):
        """Shortest path returns None when no path exists."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "node-1"},
            {"id": "node-2"},
            {"id": "node-3"},
        ]
        edges = [
            {"source_id": "node-1", "target_id": "node-2"},
        ]

        engine.build_from_data(nodes, edges)
        path = engine.shortest_path("node-2", "node-3")

        assert path is None

    def test_shortest_path_nonexistent_source_raises_error(self):
        """Shortest path raises NodeNotFoundError when source node does not exist."""
        engine = NetworkXGraphEngine()
        nodes = [{"id": "node-1"}]
        edges = []

        engine.build_from_data(nodes, edges)

        with pytest.raises(NodeNotFoundError) as exc_info:
            engine.shortest_path("nonexistent", "node-1")

        assert "nonexistent" in str(exc_info.value)

    def test_shortest_path_nonexistent_target_raises_error(self):
        """Shortest path raises NodeNotFoundError when target node does not exist."""
        engine = NetworkXGraphEngine()
        nodes = [{"id": "node-1"}]
        edges = []

        engine.build_from_data(nodes, edges)

        with pytest.raises(NodeNotFoundError) as exc_info:
            engine.shortest_path("node-1", "nonexistent")

        assert "nonexistent" in str(exc_info.value)


class TestNetworkXGraphEngineAllPaths:
    """Tests for all paths enumeration."""

    def test_all_paths_single_path(self):
        """All paths returns single path when only one exists."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "node-1"},
            {"id": "node-2"},
            {"id": "node-3"},
        ]
        edges = [
            {"source_id": "node-1", "target_id": "node-2"},
            {"source_id": "node-2", "target_id": "node-3"},
        ]

        engine.build_from_data(nodes, edges)
        paths = engine.all_paths("node-1", "node-3")

        assert len(paths) == 1
        assert paths[0] == ["node-1", "node-2", "node-3"]

    def test_all_paths_multiple_paths(self):
        """All paths returns multiple paths when they exist."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
            {"id": "d"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "a", "target_id": "c"},
            {"source_id": "b", "target_id": "d"},
            {"source_id": "c", "target_id": "d"},
        ]

        engine.build_from_data(nodes, edges)
        paths = engine.all_paths("a", "d")

        # Should find both paths: a->b->d and a->c->d
        assert len(paths) == 2
        path_lists = [list(p) for p in paths]
        assert ["a", "b", "d"] in path_lists
        assert ["a", "c", "d"] in path_lists

    def test_all_paths_respects_max_depth(self):
        """All paths respects max_depth parameter."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "1"},
            {"id": "2"},
            {"id": "3"},
            {"id": "4"},
            {"id": "5"},
        ]
        edges = [
            {"source_id": "1", "target_id": "2"},
            {"source_id": "2", "target_id": "3"},
            {"source_id": "3", "target_id": "4"},
            {"source_id": "4", "target_id": "5"},
        ]

        engine.build_from_data(nodes, edges)

        # With max_depth=2, only paths of length <= 2 edges are found
        # Path 1->5 has 4 edges, so it won't be found
        paths = engine.all_paths("1", "5", max_depth=2)
        assert len(paths) == 0

        # With max_depth=5, the full path should be found
        # (cutoff parameter is number of edges, not nodes)
        paths = engine.all_paths("1", "5", max_depth=5)
        assert len(paths) == 1
        assert paths[0] == ["1", "2", "3", "4", "5"]

    def test_all_paths_no_path_returns_empty_list(self):
        """All paths returns empty list when no path exists."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "node-1"},
            {"id": "node-2"},
            {"id": "node-3"},
        ]
        edges = [
            {"source_id": "node-1", "target_id": "node-2"},
        ]

        engine.build_from_data(nodes, edges)
        paths = engine.all_paths("node-2", "node-3")

        assert paths == []

    def test_all_paths_nonexistent_source_raises_error(self):
        """All paths raises NodeNotFoundError when source node does not exist."""
        engine = NetworkXGraphEngine()
        nodes = [{"id": "node-1"}]
        edges = []

        engine.build_from_data(nodes, edges)

        with pytest.raises(NodeNotFoundError) as exc_info:
            engine.all_paths("nonexistent", "node-1")

        assert "nonexistent" in str(exc_info.value)

    def test_all_paths_nonexistent_target_raises_error(self):
        """All paths raises NodeNotFoundError when target node does not exist."""
        engine = NetworkXGraphEngine()
        nodes = [{"id": "node-1"}]
        edges = []

        engine.build_from_data(nodes, edges)

        with pytest.raises(NodeNotFoundError) as exc_info:
            engine.all_paths("node-1", "nonexistent")

        assert "nonexistent" in str(exc_info.value)


class TestNetworkXGraphEngineCentrality:
    """Tests for centrality algorithm dispatch."""

    def test_centrality_pagerank(self):
        """Centrality with pagerank algorithm returns scores for all nodes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)
        scores = engine.centrality("pagerank")

        assert len(scores) == 3
        assert all(node_id in scores for node_id in ["a", "b", "c"])
        assert all(isinstance(score, float) for score in scores.values())

    def test_centrality_betweenness(self):
        """Centrality with betweenness algorithm returns scores for all nodes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)
        scores = engine.centrality("betweenness")

        assert len(scores) == 3
        assert all(node_id in scores for node_id in ["a", "b", "c"])
        # Middle node should have high betweenness
        assert scores["b"] > 0

    def test_centrality_closeness(self):
        """Centrality with closeness algorithm returns scores for all nodes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)
        scores = engine.centrality("closeness")

        assert len(scores) == 3
        assert all(node_id in scores for node_id in ["a", "b", "c"])

    def test_centrality_degree(self):
        """Centrality with degree algorithm returns normalized degree scores."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "a", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)
        scores = engine.centrality("degree")

        assert len(scores) == 3
        # Node 'a' has the highest degree
        assert scores["a"] > scores["b"]
        assert scores["a"] > scores["c"]

    def test_centrality_unknown_algorithm_raises_error(self):
        """Centrality with unknown algorithm raises ValueError."""
        engine = NetworkXGraphEngine()
        nodes = [{"id": "a"}]
        engine.build_from_data(nodes, [])

        with pytest.raises(ValueError) as exc_info:
            engine.centrality("unknown_algorithm")

        assert "unknown_algorithm" in str(exc_info.value).lower()


class TestNetworkXGraphEngineCommunities:
    """Tests for community detection algorithms."""

    def test_communities_louvain(self):
        """Communities with louvain algorithm partitions the graph."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
            {"id": "d"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
            {"source_id": "c", "target_id": "d"},
        ]

        engine.build_from_data(nodes, edges)
        communities = engine.communities("louvain")

        # Should have at least one community
        assert len(communities) > 0
        # Each community should be a set
        assert all(isinstance(community, set) for community in communities)
        # All nodes should be in exactly one community
        all_nodes = set().union(*communities)
        assert all_nodes == {"a", "b", "c", "d"}

    def test_communities_label_propagation(self):
        """Communities with label_propagation algorithm partitions the graph."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
            {"id": "d"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
            {"source_id": "c", "target_id": "d"},
        ]

        engine.build_from_data(nodes, edges)
        communities = engine.communities("label_propagation")

        assert len(communities) > 0
        assert all(isinstance(community, set) for community in communities)
        all_nodes = set().union(*communities)
        assert all_nodes == {"a", "b", "c", "d"}

    def test_communities_unknown_algorithm_raises_error(self):
        """Communities with unknown algorithm raises ValueError."""
        engine = NetworkXGraphEngine()
        nodes = [{"id": "a"}]
        engine.build_from_data(nodes, [])

        with pytest.raises(ValueError) as exc_info:
            engine.communities("unknown_algorithm")

        assert "unknown_algorithm" in str(exc_info.value).lower()


class TestNetworkXGraphEngineNeighbors:
    """Tests for neighbor discovery in all directions."""

    def test_neighbors_outgoing(self):
        """Neighbors with direction='out' returns successors."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "a", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)
        neighbors = engine.neighbors("a", "out")

        assert neighbors == {"b", "c"}

    def test_neighbors_incoming(self):
        """Neighbors with direction='in' returns predecessors."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "c"},
            {"source_id": "b", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)
        neighbors = engine.neighbors("c", "in")

        assert neighbors == {"a", "b"}

    def test_neighbors_both_directions(self):
        """Neighbors with direction='both' returns all adjacent nodes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
            {"id": "d"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "c", "target_id": "b"},
            {"source_id": "b", "target_id": "d"},
        ]

        engine.build_from_data(nodes, edges)
        neighbors = engine.neighbors("b", "both")

        # Should have incoming (a, c) and outgoing (d)
        assert neighbors == {"a", "c", "d"}

    def test_neighbors_isolated_node(self):
        """Neighbors of an isolated node returns empty set."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
        ]
        edges = []

        engine.build_from_data(nodes, edges)
        neighbors = engine.neighbors("a")

        assert neighbors == set()

    def test_neighbors_nonexistent_node_raises_error(self):
        """Neighbors raises NodeNotFoundError when node does not exist."""
        engine = NetworkXGraphEngine()
        nodes = [{"id": "a"}]
        edges = []

        engine.build_from_data(nodes, edges)

        with pytest.raises(NodeNotFoundError) as exc_info:
            engine.neighbors("nonexistent")

        assert "nonexistent" in str(exc_info.value)


class TestNetworkXGraphEngineHasCycle:
    """Tests for cycle detection."""

    def test_has_cycle_when_would_create_cycle(self):
        """has_cycle returns True when adding edge would create a cycle."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)

        # Adding c -> a would create cycle a -> b -> c -> a
        assert engine.has_cycle("c", "a") is True

    def test_has_cycle_when_would_not_create_cycle(self):
        """has_cycle returns False when adding edge would not create a cycle."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)

        # Adding a -> c does not create a cycle
        assert engine.has_cycle("a", "c") is False

    def test_has_cycle_does_not_modify_graph(self):
        """has_cycle checks without permanently modifying the graph."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
        ]

        engine.build_from_data(nodes, edges)
        initial_edge_count = engine.edge_count()

        # Check for cycle
        engine.has_cycle("b", "a")

        # Graph should be unchanged
        assert engine.edge_count() == initial_edge_count
        assert engine.shortest_path("a", "b") is not None
        assert engine.shortest_path("b", "a") is None

    def test_has_cycle_with_self_loop(self):
        """has_cycle detects self-loops."""
        engine = NetworkXGraphEngine()
        nodes = [{"id": "a"}]
        edges = []

        engine.build_from_data(nodes, edges)

        # Adding a -> a creates a self-loop (cycle)
        assert engine.has_cycle("a", "a") is True


class TestNetworkXGraphEngineSubgraph:
    """Tests for subgraph extraction."""

    def test_subgraph_extracts_specified_nodes(self):
        """Subgraph contains only specified nodes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
            {"id": "d"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
            {"source_id": "c", "target_id": "d"},
        ]

        engine.build_from_data(nodes, edges)
        subgraph = engine.subgraph(["a", "b", "c"])

        assert subgraph.node_count() == 3

    def test_subgraph_extracts_connecting_edges(self):
        """Subgraph contains edges between specified nodes."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
            {"id": "d"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
            {"source_id": "c", "target_id": "d"},
            {"source_id": "a", "target_id": "d"},
        ]

        engine.build_from_data(nodes, edges)
        subgraph = engine.subgraph(["a", "b", "c"])

        assert subgraph.edge_count() == 2
        # a->b and b->c exist
        assert subgraph.shortest_path("a", "c") is not None
        # a->d raises error because d is not in subgraph
        with pytest.raises(NodeNotFoundError):
            subgraph.shortest_path("a", "d")

    def test_subgraph_returns_new_engine(self):
        """Subgraph returns a new GraphEngine instance."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
        ]
        edges = [{"source_id": "a", "target_id": "b"}]

        engine.build_from_data(nodes, edges)
        subgraph = engine.subgraph(["a", "b"])

        # Should be a different instance
        assert subgraph is not engine
        assert isinstance(subgraph, NetworkXGraphEngine)


class TestNetworkXGraphEngineDegreeDistribution:
    """Tests for degree distribution."""

    def test_degree_distribution_empty_graph(self):
        """Degree distribution of empty graph returns empty dict."""
        engine = NetworkXGraphEngine()
        engine.build_from_data([], [])

        distribution = engine.degree_distribution()

        assert distribution == {}

    def test_degree_distribution_isolated_nodes(self):
        """Degree distribution counts isolated nodes as degree 0."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
        ]
        edges = []

        engine.build_from_data(nodes, edges)
        distribution = engine.degree_distribution()

        assert distribution == {"a": 0, "b": 0}

    def test_degree_distribution_with_edges(self):
        """Degree distribution counts both in and out degrees."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "a", "target_id": "c"},
            {"source_id": "b", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)
        distribution = engine.degree_distribution()

        assert distribution["a"] == 2  # out-degree 2, in-degree 0
        assert distribution["b"] == 2  # out-degree 1, in-degree 1
        assert distribution["c"] == 2  # out-degree 0, in-degree 2


class TestNetworkXGraphEngineConnectedComponents:
    """Tests for connected component counting."""

    def test_connected_components_single_connected_graph(self):
        """Connected components for connected graph returns 1."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "b", "target_id": "c"},
        ]

        engine.build_from_data(nodes, edges)
        components = engine.connected_components()

        assert components == 1

    def test_connected_components_disconnected_graph(self):
        """Connected components counts isolated groups."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
            {"id": "d"},
        ]
        edges = [
            {"source_id": "a", "target_id": "b"},
            {"source_id": "c", "target_id": "d"},
        ]

        engine.build_from_data(nodes, edges)
        components = engine.connected_components()

        assert components == 2

    def test_connected_components_isolated_nodes(self):
        """Connected components counts each isolated node as separate component."""
        engine = NetworkXGraphEngine()
        nodes = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
        edges = []

        engine.build_from_data(nodes, edges)
        components = engine.connected_components()

        assert components == 3

    def test_connected_components_empty_graph(self):
        """Connected components of empty graph returns 0."""
        engine = NetworkXGraphEngine()
        engine.build_from_data([], [])

        components = engine.connected_components()

        assert components == 0
