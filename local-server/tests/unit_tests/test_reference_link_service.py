"""
Unit tests for ReferenceLinkService.

Tests JSON operations, validation, and error handling for reference link management.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from services.reference_link_service import ReferenceLinkService
from api.models.structure_nodes import ReferenceLink
from database.models import StructureNode
from database.enums import NodeType


class TestReferenceLinkService:
    """Test suite for ReferenceLinkService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        """Create a ReferenceLinkService instance with mock database."""
        return ReferenceLinkService(mock_db)

    @pytest.fixture
    def sample_node(self):
        """Create a sample StructureNode for testing."""
        node = Mock(spec=StructureNode)
        node.id = "test-node-123"
        node.node_type = NodeType.TERM
        node.title = "Test Term"
        node.reference_links = None
        node.version = 1
        return node

    @pytest.fixture
    def sample_links(self):
        """Create sample reference links."""
        return [
            ReferenceLink(source="schema.org", external_id="Person"),
            ReferenceLink(source="wikidata", external_id="Q5"),
        ]

    def test_add_reference_links_success(self, service, mock_db, sample_node, sample_links):
        """Test successfully adding reference links to a node."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Mock reference validation
        with patch('services.reference_link_service.get_reference_manager') as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = Mock()  # Reference exists
            mock_ref_mgr.return_value = mock_manager

            # Execute
            result = service.add_reference_links("test-node-123", sample_links)

            # Assert
            assert len(result) == 2
            assert result[0].source == "schema.org"
            assert result[1].source == "wikidata"
            assert sample_node.version == 2
            mock_db.commit.assert_called_once()

    def test_add_reference_links_node_not_found(self, service, mock_db, sample_links):
        """Test adding reference links when node doesn't exist."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(ValueError, match="StructureNode not found"):
            service.add_reference_links("nonexistent-node", sample_links)

    def test_add_reference_links_invalid_reference(self, service, mock_db, sample_node, sample_links):
        """Test adding reference links with invalid reference."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Mock reference validation to return None (reference doesn't exist)
        with patch('services.reference_link_service.get_reference_manager') as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = None
            mock_ref_mgr.return_value = mock_manager

            # Execute & Assert
            with pytest.raises(ValueError, match="Reference not found in reference.db"):
                service.add_reference_links("test-node-123", sample_links)

    def test_add_reference_links_prevents_duplicates(self, service, mock_db, sample_node):
        """Test that duplicate links are not added."""
        # Setup - node already has one link
        existing_link = ReferenceLink(source="schema.org", external_id="Person")
        sample_node.reference_links = json.dumps([existing_link.model_dump()])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Try to add same link again plus a new one
        new_links = [
            ReferenceLink(source="schema.org", external_id="Person"),  # Duplicate
            ReferenceLink(source="wikidata", external_id="Q5"),  # New
        ]

        with patch('services.reference_link_service.get_reference_manager') as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = Mock()
            mock_ref_mgr.return_value = mock_manager

            # Execute
            result = service.add_reference_links("test-node-123", new_links)

            # Assert - should have 2 links (1 existing + 1 new), not 3
            assert len(result) == 2

    def test_remove_reference_links_success(self, service, mock_db, sample_node):
        """Test successfully removing reference links."""
        # Setup - node has two links
        links = [
            ReferenceLink(source="schema.org", external_id="Person"),
            ReferenceLink(source="wikidata", external_id="Q5"),
        ]
        sample_node.reference_links = json.dumps([link.model_dump() for link in links])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Remove one link
        links_to_remove = [ReferenceLink(source="schema.org", external_id="Person")]

        # Execute
        result = service.remove_reference_links("test-node-123", links_to_remove)

        # Assert
        assert len(result) == 1
        assert result[0].source == "wikidata"
        assert sample_node.version == 2
        mock_db.commit.assert_called_once()

    def test_remove_reference_links_node_not_found(self, service, mock_db):
        """Test removing links when node doesn't exist."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None

        links_to_remove = [ReferenceLink(source="schema.org", external_id="Person")]

        # Execute & Assert
        with pytest.raises(ValueError, match="StructureNode not found"):
            service.remove_reference_links("nonexistent-node", links_to_remove)

    def test_remove_reference_links_empty_result(self, service, mock_db, sample_node):
        """Test removing all links leaves empty array."""
        # Setup - node has one link
        link = ReferenceLink(source="schema.org", external_id="Person")
        sample_node.reference_links = json.dumps([link.model_dump()])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Remove the link
        links_to_remove = [link]

        # Execute
        result = service.remove_reference_links("test-node-123", links_to_remove)

        # Assert
        assert len(result) == 0
        # Verify JSON is empty array not null
        saved_json = json.loads(sample_node.reference_links)
        assert saved_json == []

    def test_get_reference_links_success(self, service, mock_db, sample_node):
        """Test successfully retrieving reference links."""
        # Setup
        links = [
            ReferenceLink(source="schema.org", external_id="Person"),
            ReferenceLink(source="wikidata", external_id="Q5"),
        ]
        sample_node.reference_links = json.dumps([link.model_dump() for link in links])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_reference_links("test-node-123")

        # Assert
        assert len(result) == 2
        assert result[0].source == "schema.org"
        assert result[1].source == "wikidata"

    def test_get_reference_links_empty(self, service, mock_db, sample_node):
        """Test retrieving links when node has none."""
        # Setup - various empty states
        test_cases = [
            None,  # NULL
            "",    # Empty string
            "[]",  # Empty JSON array
        ]

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        for empty_value in test_cases:
            sample_node.reference_links = empty_value

            # Execute
            result = service.get_reference_links("test-node-123")

            # Assert
            assert result == []

    def test_get_reference_links_malformed_json(self, service, mock_db, sample_node):
        """Test handling of malformed JSON."""
        # Setup
        sample_node.reference_links = "{invalid json"

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_reference_links("test-node-123")

        # Assert - should return empty list, not raise exception
        assert result == []

    def test_get_reference_links_not_array(self, service, mock_db, sample_node):
        """Test handling when JSON is not an array."""
        # Setup
        sample_node.reference_links = json.dumps({"not": "an array"})

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_reference_links("test-node-123")

        # Assert - should return empty list
        assert result == []

    def test_get_reference_links_invalid_link_data(self, service, mock_db, sample_node):
        """Test handling when link data is invalid."""
        # Setup - one valid link, one invalid
        sample_node.reference_links = json.dumps([
            {"source": "schema.org", "external_id": "Person"},  # Valid
            {"invalid": "data"},  # Invalid - missing required fields
        ])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_reference_links("test-node-123")

        # Assert - should return only valid link
        assert len(result) == 1
        assert result[0].source == "schema.org"

    def test_validate_reference_link_success(self, service):
        """Test successful reference validation."""
        # Mock reference manager
        with patch('services.reference_link_service.get_reference_manager') as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = Mock()  # Reference exists
            mock_ref_mgr.return_value = mock_manager

            # Execute
            result = service.validate_reference_link("schema.org", "Person")

            # Assert
            assert result is True

    def test_validate_reference_link_not_found(self, service):
        """Test validation when reference doesn't exist."""
        # Mock reference manager
        with patch('services.reference_link_service.get_reference_manager') as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = None
            mock_ref_mgr.return_value = mock_manager

            # Execute & Assert
            with pytest.raises(ValueError, match="Reference not found in reference.db"):
                service.validate_reference_link("schema.org", "NonExistent")

    def test_commit_failure_rollback(self, service, mock_db, sample_node, sample_links):
        """Test that database rollback occurs on commit failure."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node
        mock_db.commit.side_effect = Exception("Database error")

        with patch('services.reference_link_service.get_reference_manager') as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = Mock()
            mock_ref_mgr.return_value = mock_manager

            # Execute & Assert
            with pytest.raises(ValueError, match="Failed to add reference links"):
                service.add_reference_links("test-node-123", sample_links)

            # Verify rollback was called
            mock_db.rollback.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
