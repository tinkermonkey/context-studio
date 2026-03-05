"""
Unit Tests for node_conversion module

Tests embedding deserialization from numpy binary format and node conversion utilities.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock
from datetime import datetime, timezone
from uuid import UUID
import numpy as np

from api.utils.node_conversion import to_node_out, to_node_link_out, nodes_to_paginated_response
from database.models import StructureNode, StructureNodeLink
from api.models.structure_nodes import NodeTypeEnum


class TestNodeConversionEmbeddingDeserialization:
    """Test suite for embedding deserialization from numpy binary format."""

    @pytest.fixture
    def sample_embedding_data(self):
        """Create sample numpy embedding data."""
        return np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)

    @pytest.fixture
    def sample_embedding_bytes(self, sample_embedding_data):
        """Convert numpy array to bytes using tobytes() method."""
        return sample_embedding_data.tobytes()

    def test_deserialize_title_embedding_from_numpy_bytes(self, sample_embedding_bytes):
        """Test deserialization of title embedding from numpy binary format."""
        # Create mock StructureNode with title embedding
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = None
        node.title_embedding = sample_embedding_bytes
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert to API model
        result = to_node_out(node, include_embeddings=True)

        # Verify embedding was deserialized correctly
        assert result.title_embedding is not None
        assert isinstance(result.title_embedding, list)
        assert len(result.title_embedding) == 5
        # Check values are close to original (accounting for float32 precision)
        assert abs(result.title_embedding[0] - 0.1) < 1e-6
        assert abs(result.title_embedding[1] - 0.2) < 1e-6
        assert abs(result.title_embedding[2] - 0.3) < 1e-6

    def test_deserialize_definition_embedding_from_numpy_bytes(self, sample_embedding_bytes):
        """Test deserialization of definition embedding from numpy binary format."""
        # Create mock StructureNode with definition embedding
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = "Test Definition"
        node.title_embedding = None
        node.definition_embedding = sample_embedding_bytes
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert to API model
        result = to_node_out(node, include_embeddings=True)

        # Verify embedding was deserialized correctly
        assert result.definition_embedding is not None
        assert isinstance(result.definition_embedding, list)
        assert len(result.definition_embedding) == 5

    def test_both_embeddings_deserialized_correctly(self, sample_embedding_bytes):
        """Test that both title and definition embeddings are deserialized."""
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = "Test Definition"
        node.title_embedding = sample_embedding_bytes
        node.definition_embedding = sample_embedding_bytes
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert to API model
        result = to_node_out(node, include_embeddings=True)

        # Verify both embeddings are present and correct
        assert result.title_embedding is not None
        assert result.definition_embedding is not None
        assert len(result.title_embedding) == 5
        assert len(result.definition_embedding) == 5

    def test_no_embeddings_when_include_embeddings_false(self, sample_embedding_bytes):
        """Test that embeddings are not processed when include_embeddings is False."""
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = None
        node.title_embedding = sample_embedding_bytes
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert to API model with include_embeddings=False
        result = to_node_out(node, include_embeddings=False)

        # Verify embeddings are None
        assert result.title_embedding is None
        assert result.definition_embedding is None

    def test_missing_embeddings_return_none(self):
        """Test that missing embeddings are handled gracefully."""
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = None
        node.title_embedding = None
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert to API model
        result = to_node_out(node, include_embeddings=True)

        # Verify missing embeddings are None
        assert result.title_embedding is None
        assert result.definition_embedding is None

    def test_malformed_embedding_bytes_handled_gracefully(self):
        """Test that malformed embedding bytes don't crash the conversion."""
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = None
        # Use invalid bytes for embedding (wrong size for float32)
        node.title_embedding = b'\x00\x01'  # Only 2 bytes, too small
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert to API model - should handle error gracefully
        result = to_node_out(node, include_embeddings=True)

        # Malformed embedding should be excluded
        assert result.title_embedding is None

    def test_embedding_attribute_not_loaded_skipped(self):
        """Test that deferred/unloaded embedding attributes are skipped."""
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = None
        # Simulate deferred attribute (hasattr returns False)
        del node.title_embedding  # Remove attribute entirely
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert to API model
        result = to_node_out(node, include_embeddings=True)

        # Should handle missing attribute gracefully
        assert result.title_embedding is None

    def test_large_embedding_array_deserialized_correctly(self):
        """Test deserialization of large embedding arrays (typical case: 768 dimensions)."""
        # Create a 768-dimensional embedding with fixed values for reproducibility
        large_embedding = np.linspace(0.0, 1.0, 768, dtype=np.float32)
        large_embedding_bytes = large_embedding.tobytes()

        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = None
        node.title_embedding = large_embedding_bytes
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert to API model
        result = to_node_out(node, include_embeddings=True)

        # Verify deserialization is correct
        assert result.title_embedding is not None
        assert len(result.title_embedding) == 768
        # Verify values match the original embedding
        deserialized = np.array(result.title_embedding, dtype=np.float32)
        assert np.allclose(deserialized, large_embedding, atol=1e-6)


class TestNodeConversionIntegration:
    """Test suite for node conversion integration scenarios."""

    def test_node_out_with_all_fields(self):
        """Test converting node with all fields populated."""
        node_id = UUID('12345678-1234-5678-1234-567812345678')
        parent_id = UUID('87654321-4321-8765-4321-876543218765')
        predicate_id = UUID('11111111-2222-3333-4444-555555555555')

        node = Mock(spec=StructureNode)
        node.id = node_id
        node.title = "Test Node"
        node.definition = "Test Definition"
        node.title_embedding = None
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = parent_id
        node.structural_predicate_id = predicate_id
        node.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        node.version = 5
        node.last_modified = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Convert to API model
        result = to_node_out(node, include_embeddings=False)

        # Verify all fields are properly converted
        assert result.id == node_id
        assert result.title == "Test Node"
        assert result.definition == "Test Definition"
        assert result.parent_node_id == parent_id
        assert result.structural_predicate_id == predicate_id
        assert result.version == 5
        assert result.node_type == NodeTypeEnum.TERM

    def test_paginated_response_excludes_embeddings(self):
        """Test that paginated list responses don't include embeddings."""
        embedding_bytes = np.array([0.1, 0.2], dtype=np.float32).tobytes()

        nodes = []
        for i in range(3):
            node = Mock(spec=StructureNode)
            node.id = UUID(f'12345678-1234-5678-1234-56781234567{i}')
            node.title = f"Node {i}"
            node.definition = None
            node.title_embedding = embedding_bytes
            node.definition_embedding = None
            node.node_type = Mock(value='term')
            node.parent_node_id = None
            node.structural_predicate_id = None
            node.created_at = datetime.now(timezone.utc)
            node.version = 1
            node.last_modified = datetime.now(timezone.utc)
            nodes.append(node)

        # Convert to paginated response
        result = nodes_to_paginated_response(nodes, total=10, skip=0, limit=3)

        # Verify embeddings are not included in list responses
        assert len(result['data']) == 3
        assert all(item.title_embedding is None for item in result['data'])
        assert all(item.definition_embedding is None for item in result['data'])
        assert result['total'] == 10
        assert result['skip'] == 0
        assert result['limit'] == 3

    def test_node_link_conversion(self):
        """Test converting structure node links."""
        link_id = UUID('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        source_id = UUID('12345678-1234-5678-1234-567812345678')
        target_id = UUID('87654321-4321-8765-4321-876543218765')
        predicate_id = UUID('11111111-2222-3333-4444-555555555555')

        link = Mock(spec=StructureNodeLink)
        link.id = link_id
        link.source_node_id = source_id
        link.target_node_id = target_id
        link.predicate = "subclass_of"
        link.predicate_id = predicate_id
        link.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Convert to API model
        result = to_node_link_out(link)

        # Verify all fields are properly converted
        assert result.id == link_id
        assert result.source_node_id == source_id
        assert result.target_node_id == target_id
        assert result.predicate == "subclass_of"
        assert result.predicate_id == predicate_id


class TestEmbeddingErrorRecovery:
    """Test suite for embedding deserialization error recovery."""

    def test_empty_embedding_bytes_returns_none(self):
        """Test that empty embedding bytes are handled gracefully."""
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = None
        # Empty bytes - will cause deserialization to fail
        node.title_embedding = b''
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert should succeed but exclude bad embedding
        result = to_node_out(node, include_embeddings=True)

        assert result.id is not None
        assert result.title == "Test Node"
        assert result.title_embedding is None  # Empty embedding should be None

    def test_mismatched_embedding_size_handled(self):
        """Test that embeddings with incorrect size are handled."""
        # Create bytes that don't align to float32 size (4 bytes per value)
        # 5 bytes is not divisible by 4
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = None
        # 5 bytes - not aligned to float32
        node.title_embedding = b'\x00\x01\x02\x03\x04'
        node.definition_embedding = None
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert should succeed but exclude bad embedding
        result = to_node_out(node, include_embeddings=True)

        assert result.id is not None
        assert result.title == "Test Node"
        assert result.title_embedding is None  # Misaligned embedding should be excluded when error occurs

    def test_node_returned_even_if_both_embeddings_fail(self):
        """Test that node is still returned even if both embeddings fail."""
        node = Mock(spec=StructureNode)
        node.id = UUID('12345678-1234-5678-1234-567812345678')
        node.title = "Test Node"
        node.definition = "Test Definition"
        node.title_embedding = b''  # Invalid
        node.definition_embedding = b''  # Invalid
        node.node_type = Mock(value='term')
        node.parent_node_id = None
        node.structural_predicate_id = None
        node.created_at = datetime.now(timezone.utc)
        node.version = 1
        node.last_modified = datetime.now(timezone.utc)

        # Convert should still succeed
        result = to_node_out(node, include_embeddings=True)

        # Node should be fully populated even with failed embeddings
        assert result.id is not None
        assert result.title == "Test Node"
        assert result.definition == "Test Definition"
        assert result.title_embedding is None
        assert result.definition_embedding is None
