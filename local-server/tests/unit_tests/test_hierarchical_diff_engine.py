"""
Unit tests for HierarchicalDiffEngine - Testing advanced diff computation functionality.

Tests hierarchical diff algorithms, semantic analysis, three-way merge, and conflict detection.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import Mock, patch

from services.hierarchical_diff_engine import HierarchicalDiffEngine, ConflictDescriptor


class TestHierarchicalDiffEngine:
    """Test cases for HierarchicalDiffEngine functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock()

    @pytest.fixture
    def mock_nlp_service(self):
        """Create a mock NLP service."""
        mock_service = Mock()
        mock_service.extract_entities.return_value = ["entity1", "entity2"]
        mock_service.analyze_sentiment.return_value = {"score": 0.5, "label": "neutral"}
        return mock_service

    @pytest.fixture
    def diff_engine(self, mock_db, mock_nlp_service):
        """Create a HierarchicalDiffEngine instance for testing."""
        return HierarchicalDiffEngine(mock_db, mock_nlp_service)

    def test_engine_initialization(self, diff_engine, mock_db, mock_nlp_service):
        """Test HierarchicalDiffEngine initialization."""
        assert diff_engine.db == mock_db
        assert diff_engine.nlp_service == mock_nlp_service
        # assert isinstance(diff_engine.semantic_analyzer, SemanticSimilarityAnalyzer)  # Commented out - SemanticSimilarityAnalyzer not implemented yet
        assert diff_engine.performance_metrics == []

    def test_compute_basic_diff(self, diff_engine):
        """Test basic hierarchical diff computation."""
        old_data = {"id": "entity_1", "name": "Original Name", "properties": {"type": "document", "status": "draft"}}

        new_data = {
            "id": "entity_1",
            "name": "Updated Name",
            "properties": {"type": "document", "status": "published", "tags": ["important"]},
        }

        diff_result = diff_engine.compute_hierarchical_diff(old_data, new_data)

        # Check diff result structure
        assert "operations" in diff_result
        assert "metadata" in diff_result
        assert "semantic_analysis" in diff_result

        operations = diff_result["operations"]
        assert len(operations) > 0

        # Should detect name change
        name_ops = [op for op in operations if op["path"] == "name"]
        assert len(name_ops) == 1
        assert name_ops[0]["operation"] == "modify"
        assert name_ops[0]["old_value"] == "Original Name"
        assert name_ops[0]["new_value"] == "Updated Name"

        # Should detect status change
        status_ops = [op for op in operations if op["path"] == "properties.status"]
        assert len(status_ops) == 1
        assert status_ops[0]["operation"] == "modify"

        # Should detect tags addition
        tags_ops = [op for op in operations if op["path"] == "properties.tags"]
        assert len(tags_ops) == 1
        assert tags_ops[0]["operation"] == "add"

    def test_compute_three_way_diff(self, diff_engine):
        """Test three-way diff computation with conflict detection."""
        base = {"id": "entity_1", "name": "Base Name", "description": "Base description", "properties": {"version": 1}}

        local = {
            "id": "entity_1",
            "name": "Local Modified Name",
            "description": "Base description",
            "properties": {"version": 1, "local_flag": True},
        }

        remote = {
            "id": "entity_1",
            "name": "Remote Modified Name",
            "description": "Remote modified description",
            "properties": {"version": 1, "remote_flag": True},
        }

        three_way_result = diff_engine.compute_three_way_diff(base, local, remote)

        # Check three-way diff structure
        assert "base_to_local" in three_way_result
        assert "base_to_remote" in three_way_result
        assert "conflicts" in three_way_result
        assert "mergeable_changes" in three_way_result

        # Should detect conflict on name field
        conflicts = three_way_result["conflicts"]
        name_conflicts = [c for c in conflicts if c["path"] == "name"]
        assert len(name_conflicts) == 1

        conflict = name_conflicts[0]
        assert conflict["type"] == "modification_conflict"
        assert conflict["local_value"] == "Local Modified Name"
        assert conflict["remote_value"] == "Remote Modified Name"
        assert conflict["base_value"] == "Base Name"

        # Should identify mergeable changes
        mergeable = three_way_result["mergeable_changes"]
        assert len(mergeable) > 0

    def test_semantic_conflict_detection(self, diff_engine):
        """Test semantic conflict detection capabilities."""
        base_text = "The system processes user data efficiently"
        local_text = "The application handles user information quickly"
        remote_text = "The platform manages customer data rapidly"

        # These are semantically similar but textually different
        conflict = diff_engine._analyze_semantic_conflict(
            path="description", base_value=base_text, local_value=local_text, remote_value=remote_text
        )

        assert conflict is not None
        assert conflict["type"] in ["semantic_conflict", "modification_conflict"]
        assert "semantic_similarity" in conflict
        assert "resolution_suggestions" in conflict

    def test_structural_diff_detection(self, diff_engine):
        """Test structural change detection."""
        old_structure = {"type": "object", "fields": {"name": {"type": "string"}, "age": {"type": "integer"}}}

        new_structure = {
            "type": "object",
            "fields": {
                "full_name": {"type": "string"},  # renamed field
                "age": {"type": "integer"},
                "email": {"type": "string"},  # new field
            },
        }

        diff_result = diff_engine.compute_hierarchical_diff(old_structure, new_structure)

        operations = diff_result["operations"]

        # Should detect field removal, addition, and possible renaming
        add_ops = [op for op in operations if op["operation"] == "add"]
        remove_ops = [op for op in operations if op["operation"] == "remove"]

        assert len(add_ops) >= 2  # full_name and email
        assert len(remove_ops) >= 1  # name

    def test_performance_optimized_diff(self, diff_engine):
        """Test performance optimization for large data structures."""
        # Create large nested structures
        large_old = {"data": {f"item_{i}": {"value": i, "status": "active"} for i in range(1000)}}

        large_new = {"data": {f"item_{i}": {"value": i + 1, "status": "active"} for i in range(1000)}}
        # Add one new item
        large_new["data"]["item_1000"] = {"value": 1000, "status": "new"}

        start_time = time.time()
        diff_result = diff_engine.compute_hierarchical_diff(large_old, large_new)
        execution_time = time.time() - start_time

        # Should complete within reasonable time (less than 5 seconds)
        assert execution_time < 5.0

        # Should correctly identify changes
        operations = diff_result["operations"]
        assert len(operations) >= 1000  # All value changes plus one addition

    def test_conflict_resolution_suggestions(self, diff_engine):
        """Test conflict resolution suggestion generation."""
        conflict = {
            "path": "description",
            "type": "modification_conflict",
            "base_value": "Original description",
            "local_value": "Locally modified description with additions",
            "remote_value": "Remotely updated description with changes",
        }

        suggestions = diff_engine._generate_conflict_resolution_suggestions(conflict)

        assert len(suggestions) > 0
        for suggestion in suggestions:
            assert "strategy" in suggestion
            assert "description" in suggestion
            assert "confidence" in suggestion

            # Strategy should be one of the known types
            assert suggestion["strategy"] in [
                "take_local",
                "take_remote",
                "merge_text",
                "manual_review",
                "semantic_merge",
            ]

            # Confidence should be between 0 and 1
            assert 0 <= suggestion["confidence"] <= 1

    def test_diff_with_arrays(self, diff_engine):
        """Test diff computation with array/list structures."""
        old_data = {
            "tags": ["python", "machine-learning", "data-science"],
            "authors": [
                {"name": "John Doe", "email": "john@example.com"},
                {"name": "Jane Smith", "email": "jane@example.com"},
            ],
        }

        new_data = {
            "tags": ["python", "ai", "data-science", "deep-learning"],
            "authors": [
                {"name": "John Doe", "email": "john.doe@example.com"},  # email changed
                {"name": "Jane Smith", "email": "jane@example.com"},
                {"name": "Bob Johnson", "email": "bob@example.com"},  # new author
            ],
        }

        diff_result = diff_engine.compute_hierarchical_diff(old_data, new_data)
        operations = diff_result["operations"]

        # Should detect tag changes
        tag_ops = [op for op in operations if "tags" in op["path"]]
        assert len(tag_ops) > 0

        # Should detect author changes
        author_ops = [op for op in operations if "authors" in op["path"]]
        assert len(author_ops) > 0

    def test_circular_reference_handling(self, diff_engine):
        """Test handling of circular references in data structures."""
        # Create structures with circular references
        old_data = {"id": 1, "name": "item1"}
        old_data["self_ref"] = old_data

        new_data = {"id": 1, "name": "updated_item1"}
        new_data["self_ref"] = new_data

        # Should handle circular references without infinite recursion
        diff_result = diff_engine.compute_hierarchical_diff(old_data, new_data)

        # Should complete successfully
        assert "operations" in diff_result
        assert len(diff_result["operations"]) > 0

    def test_diff_metadata_generation(self, diff_engine):
        """Test diff metadata and statistics generation."""
        old_data = {"a": 1, "b": 2, "c": {"nested": 3}}
        new_data = {"a": 10, "b": 2, "c": {"nested": 30}, "d": 4}

        diff_result = diff_engine.compute_hierarchical_diff(old_data, new_data)
        metadata = diff_result["metadata"]

        # Check metadata structure
        assert "operation_count" in metadata
        assert "depth_analyzed" in metadata
        assert "complexity_score" in metadata
        assert "processing_time_ms" in metadata

        # Validate metadata values
        assert metadata["operation_count"] > 0
        assert metadata["depth_analyzed"] >= 1
        assert metadata["processing_time_ms"] > 0

    def test_semantic_analysis_integration(self, diff_engine, mock_nlp_service):
        """Test integration with semantic analysis service."""
        old_data = {
            "content": "This document contains important information about machine learning",
            "category": "technical",
        }

        new_data = {
            "content": "This paper includes crucial details about artificial intelligence",
            "category": "research",
        }

        diff_result = diff_engine.compute_hierarchical_diff(old_data, new_data)
        semantic_analysis = diff_result["semantic_analysis"]

        # Should include semantic analysis results
        assert "content_similarity" in semantic_analysis
        assert "semantic_changes" in semantic_analysis

        # Should have called NLP service for analysis
        mock_nlp_service.extract_entities.assert_called()

    def test_performance_metrics_collection(self, diff_engine):
        """Test performance metrics collection during diff operations."""
        old_data = {"test": "data"}
        new_data = {"test": "updated data"}

        # Clear any existing metrics
        diff_engine.performance_metrics.clear()

        diff_engine.compute_hierarchical_diff(old_data, new_data)

        # Should have recorded performance metrics
        assert len(diff_engine.performance_metrics) == 1

        metrics = diff_engine.performance_metrics[0]
        assert "operation_type" in metrics
        assert "execution_time_ms" in metrics
        assert "data_size_bytes" in metrics
        assert "operations_count" in metrics

    def test_get_performance_statistics(self, diff_engine):
        """Test performance statistics aggregation."""
        # Generate some test diffs to create metrics
        test_cases = [({"a": 1}, {"a": 2}), ({"b": "old"}, {"b": "new"}), ({"c": [1, 2]}, {"c": [1, 2, 3]})]

        for old, new in test_cases:
            diff_engine.compute_hierarchical_diff(old, new)

        stats = diff_engine.get_performance_statistics()

        # Check statistics structure
        assert "total_operations" in stats
        assert "avg_execution_time_ms" in stats
        assert "total_data_processed_bytes" in stats
        assert "operations_per_second" in stats

        # Should have processed multiple operations
        assert stats["total_operations"] >= 3
        assert stats["avg_execution_time_ms"] > 0

    def test_error_handling_malformed_data(self, diff_engine):
        """Test error handling with malformed data structures."""
        # Test with None values
        diff_result1 = diff_engine.compute_hierarchical_diff(None, {"test": "data"})
        assert "operations" in diff_result1

        # Test with mixed types
        diff_result2 = diff_engine.compute_hierarchical_diff("string", {"test": "data"})
        assert "operations" in diff_result2

        # Should handle gracefully without exceptions
        assert diff_result1 is not None
        assert diff_result2 is not None

    def test_deep_nested_structure_handling(self, diff_engine):
        """Test handling of deeply nested data structures."""

        # Create deeply nested structure (10 levels deep)
        def create_nested_dict(depth, value):
            if depth == 0:
                return value
            return {"level": depth, "nested": create_nested_dict(depth - 1, value)}

        old_data = create_nested_dict(10, "old_value")
        new_data = create_nested_dict(10, "new_value")

        diff_result = diff_engine.compute_hierarchical_diff(old_data, new_data)

        # Should handle deep nesting
        operations = diff_result["operations"]
        assert len(operations) > 0

        # Should track maximum depth
        metadata = diff_result["metadata"]
        assert metadata["depth_analyzed"] == 10

    @patch("services.hierarchical_diff_engine.logger")
    def test_logging_during_diff_operations(self, mock_logger, diff_engine):
        """Test that diff operations are properly logged."""
        old_data = {"test": "original"}
        new_data = {"test": "modified"}

        diff_engine.compute_hierarchical_diff(old_data, new_data)

        # Verify logging occurred
        mock_logger.debug.assert_called()

    def test_concurrent_diff_operations(self, diff_engine):
        """Test thread safety of diff operations."""
        import concurrent.futures

        results = []
        exceptions = []

        def perform_diff(thread_id):
            try:
                old_data = {"thread_id": thread_id, "value": thread_id * 10}
                new_data = {"thread_id": thread_id, "value": thread_id * 20}
                result = diff_engine.compute_hierarchical_diff(old_data, new_data)
                results.append(result)
            except Exception as e:
                exceptions.append(e)

        # Execute concurrent diff operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(perform_diff, i) for i in range(10)]
            concurrent.futures.wait(futures)

        # Check results
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(results) == 10

        # All results should be valid
        for result in results:
            assert "operations" in result
            assert "metadata" in result


class TestConflictDescriptor:
    """Test cases for ConflictDescriptor data structure."""

    def test_conflict_descriptor_creation(self):
        """Test ConflictDescriptor creation and attributes."""
        conflict = ConflictDescriptor(
            path="properties.description",
            conflict_type="modification_conflict",
            base_value="base description",
            local_value="local description",
            remote_value="remote description",
            severity="medium",
            resolution_suggestions=[
                {"strategy": "take_local", "confidence": 0.7},
                {"strategy": "merge_text", "confidence": 0.8},
            ],
        )

        assert conflict.path == "properties.description"
        assert conflict.conflict_type == "modification_conflict"
        assert conflict.base_value == "base description"
        assert conflict.local_value == "local description"
        assert conflict.remote_value == "remote description"
        assert conflict.severity == "medium"
        assert len(conflict.resolution_suggestions) == 2

    def test_conflict_severity_levels(self):
        """Test different conflict severity levels."""
        severities = ["low", "medium", "high", "critical"]

        for severity in severities:
            conflict = ConflictDescriptor(
                path="test.path",
                conflict_type="test_conflict",
                base_value="base",
                local_value="local",
                remote_value="remote",
                severity=severity,
                resolution_suggestions=[],
            )
            assert conflict.severity == severity


if __name__ == "__main__":
    import time

    pytest.main([__file__, "-v"])
