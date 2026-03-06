"""
Unit tests for graph domain entities.

Tests validate invariant enforcement and immutability of
graph metrics, path results, and knowledge graph entities.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from domain.graph.entities import GraphMetrics, PathResult, KnowledgeGraph


class TestGraphMetrics:
    """Tests for GraphMetrics entity."""

    def test_valid_graph_metrics(self):
        """Test creating valid graph metrics."""
        metrics = GraphMetrics(
            node_count=100,
            edge_count=250,
            density=0.5,
            connected_components=1
        )
        assert metrics.node_count == 100
        assert metrics.edge_count == 250
        assert metrics.density == 0.5
        assert metrics.connected_components == 1

    def test_graph_metrics_single_component(self):
        """Test graph metrics with single connected component."""
        metrics = GraphMetrics(
            node_count=5,
            edge_count=4,
            density=0.2,
            connected_components=1
        )
        assert metrics.node_count == 5
        assert metrics.connected_components == 1

    def test_graph_metrics_single_node(self):
        """Test graph metrics for a single-node graph."""
        metrics = GraphMetrics(
            node_count=1,
            edge_count=0,
            density=0.0,
            connected_components=1
        )
        assert metrics.node_count == 1
        assert metrics.connected_components == 1

    def test_graph_metrics_density_boundaries(self):
        """Test graph metrics with boundary density values."""
        # Minimum density
        metrics = GraphMetrics(
            node_count=10,
            edge_count=0,
            density=0.0,
            connected_components=10
        )
        assert metrics.density == 0.0

        # Maximum density
        metrics = GraphMetrics(
            node_count=10,
            edge_count=45,  # Fully connected (10*9/2)
            density=1.0,
            connected_components=1
        )
        assert metrics.density == 1.0

    def test_graph_metrics_invalid_node_count(self):
        """Test that negative node_count raises ValueError."""
        with pytest.raises(ValueError, match="node_count must be a non-negative integer"):
            GraphMetrics(
                node_count=-1,
                edge_count=0,
                density=0.0,
                connected_components=1
            )

    def test_graph_metrics_invalid_edge_count(self):
        """Test that negative edge_count raises ValueError."""
        with pytest.raises(ValueError, match="edge_count must be a non-negative integer"):
            GraphMetrics(
                node_count=10,
                edge_count=-1,
                density=0.5,
                connected_components=1
            )

    def test_graph_metrics_invalid_density(self):
        """Test that invalid density raises ValueError."""
        # Density > 1.0
        with pytest.raises(ValueError, match="density must be a number between 0.0 and 1.0"):
            GraphMetrics(
                node_count=10,
                edge_count=25,
                density=1.5,
                connected_components=1
            )

        # Density < 0.0
        with pytest.raises(ValueError, match="density must be a number between 0.0 and 1.0"):
            GraphMetrics(
                node_count=10,
                edge_count=25,
                density=-0.1,
                connected_components=1
            )

        # Density is bool (even though bool is subclass of int)
        with pytest.raises(ValueError, match="density must be a number between 0.0 and 1.0"):
            GraphMetrics(
                node_count=10,
                edge_count=25,
                density=True,
                connected_components=1
            )

    def test_graph_metrics_invalid_connected_components(self):
        """Test that invalid connected_components raises ValueError."""
        with pytest.raises(ValueError, match="connected_components must be a positive integer"):
            GraphMetrics(
                node_count=10,
                edge_count=25,
                density=0.5,
                connected_components=0
            )


class TestPathResult:
    """Tests for PathResult entity."""

    def test_valid_path_result(self):
        """Test creating a valid path result."""
        path = PathResult(
            path=("node1", "node2", "node3"),
            length=2,
            weight=1.5
        )
        assert path.path == ("node1", "node2", "node3")
        assert path.length == 2
        assert path.weight == 1.5

    def test_path_result_single_node(self):
        """Test path result with a single node (zero edges)."""
        path = PathResult(
            path=("node1",),
            length=0,
            weight=0.0
        )
        assert path.path == ("node1",)
        assert path.length == 0

    def test_path_result_empty_path(self):
        """Test empty path result."""
        path = PathResult(
            path=(),
            length=0,
            weight=0.0
        )
        assert path.path == ()
        assert path.length == 0

    def test_path_result_long_path(self):
        """Test path result with multiple nodes."""
        nodes = tuple(f"node{i}" for i in range(10))
        path = PathResult(
            path=nodes,
            length=9,
            weight=4.5
        )
        assert len(path.path) == 10
        assert path.length == 9

    def test_path_result_path_immutable(self):
        """Test that path tuple is immutable."""
        path = PathResult(
            path=("node1", "node2", "node3"),
            length=2,
            weight=1.5
        )
        with pytest.raises((TypeError, AttributeError)):
            path.path[0] = "other_node"

    def test_path_result_invalid_path_type(self):
        """Test that non-tuple path raises TypeError."""
        with pytest.raises(TypeError, match="path must be a tuple"):
            PathResult(
                path=["node1", "node2"],  # List instead of tuple
                length=1,
                weight=1.0
            )

    def test_path_result_invalid_node_id(self):
        """Test that non-string node IDs raise TypeError."""
        with pytest.raises(TypeError, match="All node IDs in path must be strings"):
            PathResult(
                path=(123, "node2"),  # Integer instead of string
                length=1,
                weight=1.0
            )

    def test_path_result_invalid_length(self):
        """Test that invalid length raises ValueError."""
        with pytest.raises(ValueError, match="length must be a non-negative integer"):
            PathResult(
                path=("node1", "node2"),
                length=-1,  # Negative length
                weight=1.0
            )

    def test_path_result_length_validation(self):
        """Test that length is validated against path size."""
        # Valid: length = nodes - 1
        path = PathResult(
            path=("node1", "node2", "node3"),
            length=2,
            weight=1.5
        )
        assert path.length == len(path.path) - 1

        # Invalid: length != nodes - 1
        with pytest.raises(ValueError, match="length must equal number of edges"):
            PathResult(
                path=("node1", "node2", "node3"),
                length=1,  # Should be 2
                weight=1.5
            )

    def test_path_result_invalid_weight(self):
        """Test that non-numeric weight raises ValueError."""
        with pytest.raises(ValueError, match="weight must be a number"):
            PathResult(
                path=("node1", "node2"),
                length=1,
                weight="1.5"  # String instead of number
            )

        # Weight is bool (even though bool is subclass of int)
        with pytest.raises(ValueError, match="weight must be a number"):
            PathResult(
                path=("node1", "node2"),
                length=1,
                weight=True
            )


class TestKnowledgeGraph:
    """Tests for KnowledgeGraph entity."""

    def test_valid_knowledge_graph(self):
        """Test creating a valid knowledge graph."""
        graph = KnowledgeGraph(
            taxonomy_id="tax-001",
            nodes=("node1", "node2", "node3"),
            edges=("edge1", "edge2"),
            metrics=GraphMetrics(
                node_count=3,
                edge_count=2,
                density=0.5,
                connected_components=1
            )
        )
        assert graph.taxonomy_id == "tax-001"
        assert len(graph.nodes) == 3
        assert len(graph.edges) == 2

    def test_knowledge_graph_without_metrics(self):
        """Test knowledge graph without metrics."""
        graph = KnowledgeGraph(
            taxonomy_id="tax-001",
            nodes=("node1", "node2"),
            edges=("edge1",),
            metrics=None
        )
        assert graph.metrics is None

    def test_knowledge_graph_empty_nodes_and_edges(self):
        """Test knowledge graph with empty nodes and edges."""
        graph = KnowledgeGraph(
            taxonomy_id="tax-001",
            nodes=(),
            edges=(),
            metrics=None
        )
        assert graph.nodes == ()
        assert graph.edges == ()

    def test_knowledge_graph_nodes_immutable(self):
        """Test that nodes tuple is immutable."""
        graph = KnowledgeGraph(
            taxonomy_id="tax-001",
            nodes=("node1", "node2"),
            edges=("edge1",),
            metrics=None
        )
        with pytest.raises((TypeError, AttributeError)):
            graph.nodes[0] = "other_node"

    def test_knowledge_graph_edges_immutable(self):
        """Test that edges tuple is immutable."""
        graph = KnowledgeGraph(
            taxonomy_id="tax-001",
            nodes=("node1", "node2"),
            edges=("edge1",),
            metrics=None
        )
        with pytest.raises((TypeError, AttributeError)):
            graph.edges[0] = "other_edge"

    def test_knowledge_graph_invalid_taxonomy_id(self):
        """Test that empty taxonomy_id raises ValueError."""
        with pytest.raises(ValueError, match="taxonomy_id must be a non-empty string"):
            KnowledgeGraph(
                taxonomy_id="",
                nodes=("node1",),
                edges=(),
                metrics=None
            )

    def test_knowledge_graph_invalid_nodes_type(self):
        """Test that non-tuple nodes raises TypeError."""
        with pytest.raises(TypeError, match="nodes must be a tuple"):
            KnowledgeGraph(
                taxonomy_id="tax-001",
                nodes=["node1", "node2"],  # List instead of tuple
                edges=(),
                metrics=None
            )

    def test_knowledge_graph_invalid_node_id(self):
        """Test that non-string node IDs raise TypeError."""
        with pytest.raises(TypeError, match="All node IDs must be strings"):
            KnowledgeGraph(
                taxonomy_id="tax-001",
                nodes=(123, "node2"),  # Integer instead of string
                edges=(),
                metrics=None
            )

    def test_knowledge_graph_invalid_edges_type(self):
        """Test that non-tuple edges raises TypeError."""
        with pytest.raises(TypeError, match="edges must be a tuple"):
            KnowledgeGraph(
                taxonomy_id="tax-001",
                nodes=("node1",),
                edges=["edge1"],  # List instead of tuple
                metrics=None
            )

    def test_knowledge_graph_invalid_edge_id(self):
        """Test that non-string edge IDs raise TypeError."""
        with pytest.raises(TypeError, match="All edge IDs must be strings"):
            KnowledgeGraph(
                taxonomy_id="tax-001",
                nodes=("node1",),
                edges=(456, "edge2"),  # Integer instead of string
                metrics=None
            )

    def test_knowledge_graph_invalid_metrics(self):
        """Test that non-GraphMetrics metrics raises TypeError."""
        with pytest.raises(TypeError, match="metrics must be None or a GraphMetrics instance"):
            KnowledgeGraph(
                taxonomy_id="tax-001",
                nodes=("node1",),
                edges=(),
                metrics={"node_count": 1}  # Dict instead of GraphMetrics
            )
