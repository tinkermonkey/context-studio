"""
Unit tests for ReferenceLinkService.

Tests JSON operations, validation, and error handling for reference link management.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import json  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services.reference_link_service import ReferenceLinkService  # noqa: E402
from api.models.structure_nodes import ReferenceLink  # noqa: E402
from database.models import StructureNode  # noqa: E402
from database.enums import NodeType  # noqa: E402
from services.exceptions import (
    NotFoundError,
    ReferenceNotFoundError,
    ValidationError,
)  # noqa: E402, E501


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

    def test_add_reference_links_success(
        self, service, mock_db, sample_node, sample_links
    ):
        """Test successfully adding reference links to a node."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Mock reference validation
        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = (
                Mock()
            )  # Reference exists
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
        with pytest.raises(NotFoundError, match="StructureNode not found"):
            service.add_reference_links("nonexistent-node", sample_links)

    def test_add_reference_links_invalid_reference(
        self, service, mock_db, sample_node, sample_links
    ):
        """Test adding reference links with invalid reference."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Mock reference validation to return None (reference doesn't exist)
        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = None
            mock_ref_mgr.return_value = mock_manager

            # Execute & Assert
            with pytest.raises(
                ReferenceNotFoundError, match="Reference not found: schema.org:Person"
            ):
                service.add_reference_links("test-node-123", sample_links)

    def test_add_reference_links_prevents_duplicates(
        self, service, mock_db, sample_node
    ):
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

        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
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
        with pytest.raises(NotFoundError, match="StructureNode not found"):
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
            "",  # Empty string
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
        sample_node.reference_links = json.dumps(
            [
                {"source": "schema.org", "external_id": "Person"},  # Valid
                {"invalid": "data"},  # Invalid - missing required fields
            ]
        )

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_reference_links("test-node-123")

        # Assert - should return only valid link
        assert len(result) == 1
        assert result[0].source == "schema.org"

    def test_validate_reference_link_success(self, service):
        """Test successful reference validation."""
        # Mock reference manager
        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = (
                Mock()
            )  # Reference exists
            mock_ref_mgr.return_value = mock_manager

            # Execute - should not raise exception
            service.validate_reference_link("schema.org", "Person")

            # Assert - if we get here, validation succeeded
            mock_manager.get_reference_node_by_source.assert_called_once_with(
                "schema.org", "Person"
            )

    def test_validate_reference_link_not_found(self, service):
        """Test validation when reference doesn't exist."""
        # Mock reference manager
        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = None
            mock_ref_mgr.return_value = mock_manager

            # Execute & Assert
            with pytest.raises(
                ReferenceNotFoundError,
                match="Reference not found: schema.org:NonExistent",
            ):
                service.validate_reference_link("schema.org", "NonExistent")

    def test_commit_failure_rollback(self, service, mock_db, sample_node, sample_links):
        """Test that database rollback occurs on commit failure."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node
        mock_db.commit.side_effect = Exception("Database error")

        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = Mock()
            mock_ref_mgr.return_value = mock_manager

            # Execute & Assert
            with pytest.raises(ValidationError, match="Failed to add reference links"):
                service.add_reference_links("test-node-123", sample_links)

            # Verify rollback was called
            mock_db.rollback.assert_called_once()

    def test_validate_node_reference_links_success(self, service, mock_db, sample_node):
        """Test successful validation of node reference links."""
        # Setup - node with valid links
        links = [
            ReferenceLink(source="schema.org", external_id="Person"),
            ReferenceLink(source="wikidata", external_id="Q5"),
        ]
        sample_node.reference_links = json.dumps([link.model_dump() for link in links])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Mock reference validation
        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = (
                Mock()
            )  # All refs exist
            mock_ref_mgr.return_value = mock_manager

            # Execute
            result = service.validate_node_reference_links(
                "test-node-123", check_existence=True
            )

            # Assert
            assert result["node_id"] == "test-node-123"
            assert result["total_links"] == 2
            assert result["valid_links"] == 2
            assert len(result["orphaned_links"]) == 0
            assert len(result["malformed_links"]) == 0

    def test_validate_node_reference_links_orphaned(
        self, service, mock_db, sample_node
    ):
        """Test validation detects orphaned links."""
        # Setup - node with one valid and one orphaned link
        links = [
            ReferenceLink(source="schema.org", external_id="Person"),
            ReferenceLink(source="wikidata", external_id="Q_NONEXISTENT"),
        ]
        sample_node.reference_links = json.dumps([link.model_dump() for link in links])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Mock reference validation - first exists, second doesn't
        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_manager = Mock()

            def get_ref_node(source, external_id):
                if external_id == "Q_NONEXISTENT":
                    return None
                return Mock()

            mock_manager.get_reference_node_by_source.side_effect = get_ref_node
            mock_ref_mgr.return_value = mock_manager

            # Execute
            result = service.validate_node_reference_links(
                "test-node-123", check_existence=True
            )

            # Assert
            assert result["total_links"] == 2
            assert result["valid_links"] == 1
            assert len(result["orphaned_links"]) == 1
            assert result["orphaned_links"][0]["source"] == "wikidata"
            assert result["orphaned_links"][0]["external_id"] == "Q_NONEXISTENT"

    def test_validate_node_reference_links_malformed(
        self, service, mock_db, sample_node
    ):
        """Test validation detects malformed links."""
        # Setup - one valid, one malformed
        sample_node.reference_links = json.dumps(
            [
                {"source": "schema.org", "external_id": "Person"},  # Valid
                {"invalid_field": "bad_data"},  # Malformed
            ]
        )

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_manager = Mock()
            mock_manager.get_reference_node_by_source.return_value = Mock()
            mock_ref_mgr.return_value = mock_manager

            # Execute
            result = service.validate_node_reference_links(
                "test-node-123", check_existence=True
            )

            # Assert
            assert result["total_links"] == 2
            assert result["valid_links"] == 1
            assert len(result["malformed_links"]) == 1

    def test_validate_node_reference_links_no_existence_check(
        self, service, mock_db, sample_node
    ):
        """Test validation without checking existence."""
        # Setup
        links = [ReferenceLink(source="schema.org", external_id="Person")]
        sample_node.reference_links = json.dumps([link.model_dump() for link in links])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute - without existence check
        result = service.validate_node_reference_links(
            "test-node-123", check_existence=False
        )

        # Assert - should mark as valid without checking reference.db
        assert result["valid_links"] == 1
        assert len(result["orphaned_links"]) == 0

    def test_validate_node_reference_links_empty(self, service, mock_db, sample_node):
        """Test validation with no links."""
        # Setup
        sample_node.reference_links = None

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.validate_node_reference_links("test-node-123")

        # Assert
        assert result["total_links"] == 0
        assert result["valid_links"] == 0
        assert len(result["orphaned_links"]) == 0

    def test_validate_all_reference_links_success(self, service, mock_db):
        """Test bulk validation of all nodes."""
        # Setup - create mock nodes with links
        nodes = []
        for i in range(3):
            node = Mock(spec=StructureNode)
            node.id = f"node-{i}"
            node.title = f"Node {i}"
            node.node_type = "term"
            node.reference_links = json.dumps(
                [{"source": "schema.org", "external_id": f"Thing{i}"}]
            )
            nodes.append(node)

        # Setup query mock to support yield_per
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.yield_per.return_value = iter(nodes)
        mock_db.query.return_value = query_mock

        # Mock individual node validation
        with patch.object(service, "validate_node_reference_links") as mock_validate:
            mock_validate.return_value = {
                "node_id": "node-0",
                "total_links": 1,
                "valid_links": 1,
                "orphaned_links": [],
                "malformed_links": [],
            }

            with patch(
                "services.reference_link_service.get_reference_manager"
            ) as mock_ref_mgr:
                mock_ref_mgr.return_value = Mock()

                # Execute
                result = service.validate_all_reference_links(
                    check_existence=True, limit=10
                )

                # Assert
                assert result["total_nodes_checked"] == 3
                assert result["nodes_with_links"] == 3
                assert result["reference_db_available"] is True

    def test_validate_all_reference_links_unavailable_db(self, service, mock_db):
        """Test bulk validation gracefully handles unavailable reference.db."""
        # Setup - create mock nodes
        node = Mock(spec=StructureNode)
        node.id = "node-1"
        node.title = "Test Node"
        node.node_type = "term"
        node.reference_links = json.dumps(
            [{"source": "schema.org", "external_id": "Thing"}]
        )

        # Setup query mock to support yield_per
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.yield_per.return_value = iter([node])
        mock_db.query.return_value = query_mock

        # Mock reference manager to fail
        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_ref_mgr.side_effect = Exception("Database unavailable")

            with patch.object(
                service, "validate_node_reference_links"
            ) as mock_validate:
                mock_validate.return_value = {
                    "total_links": 1,
                    "valid_links": 1,
                    "orphaned_links": [],
                    "malformed_links": [],
                }

                # Execute
                result = service.validate_all_reference_links(check_existence=True)

                # Assert - should degrade gracefully
                assert result["reference_db_available"] is False
                # Validation should continue without checking existence
                mock_validate.assert_called_with("node-1", check_existence=False)

    def test_validate_node_reference_links_raises_on_missing_node(
        self, service, mock_db
    ):
        """Test that validation raises NotFoundError when node is not found."""
        # Setup - node doesn't exist
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert - should raise NotFoundError, not return error in dict
        with pytest.raises(NotFoundError, match="StructureNode not found"):
            service.validate_node_reference_links("nonexistent-node")

    def test_validate_all_reference_links_with_database_query_failure(
        self, service, mock_db
    ):
        """Test bulk validation handles database query failures."""
        # Setup - query fails
        query_mock = Mock()
        query_mock.filter.side_effect = Exception("Database connection lost")
        mock_db.query.return_value = query_mock

        # Execute
        result = service.validate_all_reference_links(check_existence=False)

        # Assert - should return result with error
        assert "error" in result
        assert "Database connection lost" in result["error"]

    def test_validate_all_reference_links_with_mixed_valid_invalid_nodes(
        self, service, mock_db
    ):
        """Test bulk validation with mixed valid and problematic nodes."""
        # Setup - create nodes with different validation results
        nodes = []
        for i in range(3):
            node = Mock(spec=StructureNode)
            node.id = f"node-{i}"
            node.title = f"Node {i}"
            node.node_type = "term"
            node.reference_links = json.dumps(
                [{"source": "schema.org", "external_id": f"Thing{i}"}]
            )
            nodes.append(node)

        # Setup query mock to support yield_per
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.yield_per.return_value = iter(nodes)
        mock_db.query.return_value = query_mock

        # Mock individual node validation with different results
        validation_results = [
            {  # Node 0: All valid
                "node_id": "node-0",
                "total_links": 1,
                "valid_links": 1,
                "orphaned_links": [],
                "malformed_links": [],
            },
            {  # Node 1: Has orphaned links
                "node_id": "node-1",
                "total_links": 2,
                "valid_links": 1,
                "orphaned_links": [
                    {
                        "source": "wikidata",
                        "external_id": "Q_BAD",
                        "reason": "Not found",
                    }
                ],
                "malformed_links": [],
            },
            {  # Node 2: Has malformed links
                "node_id": "node-2",
                "total_links": 2,
                "valid_links": 1,
                "orphaned_links": [],
                "malformed_links": [{"data": {}, "reason": "Parse error"}],
            },
        ]

        with patch.object(service, "validate_node_reference_links") as mock_validate:
            mock_validate.side_effect = validation_results

            with patch(
                "services.reference_link_service.get_reference_manager"
            ) as mock_ref_mgr:
                mock_ref_mgr.return_value = Mock()

                # Execute
                result = service.validate_all_reference_links(check_existence=True)

                # Assert
                assert result["total_nodes_checked"] == 3
                assert result["total_links"] == 5  # 1 + 2 + 2
                assert result["valid_links"] == 3  # 1 + 1 + 1
                assert result["orphaned_links"] == 1  # Node 1 has 1 orphaned
                assert result["malformed_links"] == 1  # Node 2 has 1 malformed
                assert len(result["problematic_nodes"]) == 2  # Nodes 1 and 2
                assert result["reference_db_available"] is True

    def test_validate_all_reference_links_performance_when_reference_db_unavailable(
        self, service, mock_db
    ):
        """Test that validation without reference.db access doesn't fail catastrophically."""
        # Setup - create many nodes
        nodes = []
        for i in range(50):
            node = Mock(spec=StructureNode)
            node.id = f"node-{i}"
            node.title = f"Node {i}"
            node.node_type = "term"
            node.reference_links = json.dumps(
                [{"source": "schema.org", "external_id": f"Thing{i}"}]
            )
            nodes.append(node)

        # Setup query mock to support yield_per
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.yield_per.return_value = iter(nodes)
        mock_db.query.return_value = query_mock

        # Mock reference manager to be unavailable
        with patch(
            "services.reference_link_service.get_reference_manager"
        ) as mock_ref_mgr:
            mock_ref_mgr.side_effect = Exception("reference.db not accessible")

            with patch.object(
                service, "validate_node_reference_links"
            ) as mock_validate:
                mock_validate.return_value = {
                    "total_links": 1,
                    "valid_links": 1,
                    "orphaned_links": [],
                    "malformed_links": [],
                }

                # Execute
                result = service.validate_all_reference_links(
                    check_existence=True, limit=50
                )

                # Assert - should complete without errors, just mark DB as unavailable
                assert result["reference_db_available"] is False
                assert result["total_nodes_checked"] == 50
                # Should have called validate_node_reference_links with check_existence=False
                # for all nodes after detecting DB unavailability
                for call in mock_validate.call_args_list:
                    assert call[1]["check_existence"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
