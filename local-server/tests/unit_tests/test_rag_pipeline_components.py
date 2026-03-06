"""
Unit tests for RAG pipeline components (registry, standard pipeline, test service).  # noqa: E501

These tests verify the core functionality without requiring full application initialization.  # noqa: E501
"""

import pytest
from unittest.mock import Mock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # noqa: E501


class TestPipelineRegistry:
    """Tests for PipelineRegistry singleton and registration."""

    def test_singleton_instance(self):
        """Test that PipelineRegistry is a singleton."""
        from rag.pipeline_registry import PipelineRegistry

        instance1 = PipelineRegistry()
        instance2 = PipelineRegistry()

        assert instance1 is instance2, "PipelineRegistry should return the same instance"  # noqa: E501

    def test_register_pipeline(self):
        """Test registering a pipeline class."""
        from rag.pipeline_registry import PipelineRegistry
        from rag.base_pipeline import BaseRAGPipeline

        # Create a mock pipeline class
        class MockPipeline(BaseRAGPipeline):
            @staticmethod
            def get_name():
                return "MockPipeline"

            @staticmethod
            def get_description():
                return "Mock pipeline for testing"

            async def extract_entities(self, text, enable_trace=False, enable_llm_layer=True):  # noqa: E501
                pass

            def get_config(self):
                return {}

        # Clear registry first
        PipelineRegistry.clear()

        # Register the mock pipeline
        PipelineRegistry.register(MockPipeline)

        # Verify it's in the registry
        assert "MockPipeline" in PipelineRegistry.list_pipelines()
        assert PipelineRegistry.get_pipeline_class("MockPipeline") == MockPipeline  # noqa: E501

    def test_get_pipeline_info(self):
        """Test retrieving pipeline information."""
        from rag.pipeline_registry import PipelineRegistry
        from rag.base_pipeline import BaseRAGPipeline

        class TestInfoPipeline(BaseRAGPipeline):
            @staticmethod
            def get_name():
                return "TestInfoPipeline"

            @staticmethod
            def get_description():
                return "Test description"

            async def extract_entities(self, text, enable_trace=False, enable_llm_layer=True):  # noqa: E501
                pass

            def get_config(self):
                return {}

        PipelineRegistry.clear()
        PipelineRegistry.register(TestInfoPipeline)

        info = PipelineRegistry.get_pipeline_info("TestInfoPipeline")

        assert info is not None
        assert info["name"] == "TestInfoPipeline"
        assert info["description"] == "Test description"
        assert info["class"] == "TestInfoPipeline"

    def test_unregister_pipeline(self):
        """Test unregistering a pipeline."""
        from rag.pipeline_registry import PipelineRegistry
        from rag.base_pipeline import BaseRAGPipeline

        class UnregisterTest(BaseRAGPipeline):
            @staticmethod
            def get_name():
                return "UnregisterTest"

            @staticmethod
            def get_description():
                return "Test"

            async def extract_entities(self, text, enable_trace=False, enable_llm_layer=True):  # noqa: E501
                pass

            def get_config(self):
                return {}

        PipelineRegistry.clear()
        PipelineRegistry.register(UnregisterTest)

        assert "UnregisterTest" in PipelineRegistry.list_pipelines()

        result = PipelineRegistry.unregister("UnregisterTest")

        assert result is True
        assert "UnregisterTest" not in PipelineRegistry.list_pipelines()


class TestStandardPipelineValidation:
    """Tests for StandardRAGPipeline configuration validation."""

    def test_invalid_kg_top_k(self):
        """Test that invalid kg_top_k raises ValueError."""
        from rag.standard_pipeline import StandardRAGPipeline

        mock_kg_session = Mock()
        mock_ops_session = Mock()

        with pytest.raises(ValueError, match="kg_top_k must be positive"):
            StandardRAGPipeline(
                kg_db_session=mock_kg_session,
                ops_db_session=mock_ops_session,
                config={"kg_top_k": 0}
            )

    def test_invalid_kg_vector_threshold(self):
        """Test that invalid kg_vector_threshold raises ValueError."""
        from rag.standard_pipeline import StandardRAGPipeline

        mock_kg_session = Mock()
        mock_ops_session = Mock()

        with pytest.raises(ValueError, match="kg_vector_threshold must be between 0 and 1"):  # noqa: E501
            StandardRAGPipeline(
                kg_db_session=mock_kg_session,
                ops_db_session=mock_ops_session,
                config={"kg_vector_threshold": 1.5}
            )

    def test_invalid_timeout(self):
        """Test that invalid timeout raises ValueError."""
        from rag.standard_pipeline import StandardRAGPipeline

        mock_kg_session = Mock()
        mock_ops_session = Mock()

        with pytest.raises(ValueError, match="timeout_layer_1 must be positive"):  # noqa: E501
            StandardRAGPipeline(
                kg_db_session=mock_kg_session,
                ops_db_session=mock_ops_session,
                config={"timeout_layer_1": -1}
            )

    def test_invalid_dedup_threshold(self):
        """Test that invalid dedup_similarity_threshold raises ValueError."""
        from rag.standard_pipeline import StandardRAGPipeline

        mock_kg_session = Mock()
        mock_ops_session = Mock()

        with pytest.raises(ValueError, match="dedup_similarity_threshold must be between 0 and 1"):  # noqa: E501
            StandardRAGPipeline(
                kg_db_session=mock_kg_session,
                ops_db_session=mock_ops_session,
                config={"dedup_similarity_threshold": 2.0}
            )


class TestRAGTestManagementService:
    """Tests for RAGTestManagementService core functions."""

    def test_create_test_paragraph(self):
        """Test creating a test paragraph."""
        from rag.test_service import RAGTestManagementService

        mock_kg_session = Mock()
        mock_ops_session = Mock()

        service = RAGTestManagementService(mock_kg_session, mock_ops_session)

        # Mock the commit
        mock_ops_session.add = Mock()
        mock_ops_session.commit = Mock()

        paragraph = service.create_test_paragraph(
            text="This is a test paragraph.",
            notes="Test notes"
        )

        assert paragraph.text == "This is a test paragraph."
        assert paragraph.notes == "Test notes"
        assert paragraph.id is not None
        mock_ops_session.add.assert_called_once()
        mock_ops_session.commit.assert_called_once()

    def test_validate_structure_node_id_exists(self):
        """Test structure_node_id validation when node exists."""
        from rag.test_service import RAGTestManagementService
        from database.models import StructureNode

        mock_kg_session = Mock()
        mock_ops_session = Mock()

        # Mock query to return a node
        mock_node = Mock(spec=StructureNode)
        mock_kg_session.query.return_value.filter.return_value.first.return_value = mock_node  # noqa: E501

        service = RAGTestManagementService(mock_kg_session, mock_ops_session)

        result = service._validate_structure_node_id("valid-node-id")

        assert result is True

    def test_validate_structure_node_id_not_exists(self):
        """Test structure_node_id validation when node doesn't exist."""
        from rag.test_service import RAGTestManagementService

        mock_kg_session = Mock()
        mock_ops_session = Mock()

        # Mock query to return None
        mock_kg_session.query.return_value.filter.return_value.first.return_value = None  # noqa: E501

        service = RAGTestManagementService(mock_kg_session, mock_ops_session)

        result = service._validate_structure_node_id("invalid-node-id")

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
