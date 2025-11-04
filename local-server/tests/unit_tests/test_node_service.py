"""
Unit tests for NodeService - Service Layer Tests

Tests the business logic and validation rules for the unified NodeService
as specified in section 8.2 of the Great Normalization design.
"""

import sys
import os
import pytest
import uuid
from unittest.mock import Mock

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.node_service import NodeService
from database.models import StructureNode
from database.enums import NodeType
from graph.graph_service import GraphService
from services.exceptions import InvalidHierarchyError, CircularReferenceError, NotFoundError


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_graph_service():
    """Mock graph service."""
    return Mock(spec=GraphService)


@pytest.fixture
def node_service(mock_db, mock_graph_service):
    """NodeService instance with mocked dependencies."""
    return NodeService(db=mock_db, graph_service=mock_graph_service)


@pytest.fixture
def sample_layer_data():
    """Sample data for creating a layer."""
    return {
        "node_type": "layer",
        "title": "Test Layer",
        "definition": "Test layer definition",
    }


@pytest.fixture
def sample_domain_data():
    """Sample data for creating a domain."""
    return {
        "node_type": "domain",
        "title": "Test Domain",
        "definition": "Test domain definition",
        "parent_node_id": str(uuid.uuid4()),
    }


@pytest.fixture
def sample_term_data():
    """Sample data for creating a term."""
    return {
        "node_type": "term",
        "title": "Test Term",
        "definition": "Test term definition",
        "parent_node_id": str(uuid.uuid4()),
    }


class TestNodeServiceValidation:
    """Test NodeService validation rules as specified in the design."""

    def test_layer_validation_no_parent_allowed(self, node_service, mock_db):
        """Test layer validation rule: Layers cannot have parent structure_nodes."""
        # Setup mock for unique title check first (pass this check)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        layer_data = {
            "node_type": "layer",
            "title": "Test Layer with Parent",
            "parent_node_id": str(uuid.uuid4()),
        }

        with pytest.raises(
            InvalidHierarchyError, match="Layers cannot have parent structure_nodes"
        ):
            node_service.create_node(layer_data)

    def test_layer_validation_unique_title(
        self, node_service, sample_layer_data, mock_db
    ):
        """Test layer validation rule: Layer titles must be unique."""
        # Setup mock to return existing layer with same title
        existing_layer = Mock(spec=StructureNode)
        existing_layer.title = sample_layer_data["title"]
        mock_db.query.return_value.filter.return_value.first.return_value = (
            existing_layer
        )

        with pytest.raises(ValueError, match="Layer title must be unique"):
            node_service.create_node(sample_layer_data)

    def test_domain_validation_requires_parent(self, node_service, sample_domain_data):
        """Test domain validation rule: Domains must have a parent layer."""
        del sample_domain_data["parent_node_id"]

        with pytest.raises(InvalidHierarchyError, match="Domains must have a parent layer"):
            node_service.create_node(sample_domain_data)

    def test_domain_validation_parent_must_be_layer(
        self, node_service, sample_domain_data, mock_db
    ):
        """Test domain validation rule: Domain parent must be a layer."""
        # Setup mock to return non-layer parent
        parent_domain = Mock(spec=StructureNode)
        parent_domain.node_type = NodeType.DOMAIN
        mock_db.query.return_value.filter.return_value.first.return_value = (
            parent_domain
        )

        with pytest.raises(InvalidHierarchyError, match="Domain parent must be a layer"):
            node_service.create_node(sample_domain_data)

    def test_domain_validation_unique_title_within_layer(
        self, node_service, sample_domain_data, mock_db
    ):
        """Test domain validation rule: Domain titles must be unique within layer."""
        # Setup mocks
        parent_layer = Mock(spec=StructureNode)
        parent_layer.node_type = NodeType.LAYER

        existing_domain = Mock(spec=StructureNode)
        existing_domain.title = sample_domain_data["title"]
        existing_domain.parent_node_id = sample_domain_data["parent_node_id"]

        def mock_query_side_effect(*args):
            query_mock = Mock()
            filter_mock = Mock()
            query_mock.filter.return_value = filter_mock

            # First call gets the parent (layer validation)
            if mock_db.query.call_count == 1:
                filter_mock.first.return_value = parent_layer
            # Second call checks for existing domain with same title
            else:
                filter_mock.first.return_value = existing_domain

            return query_mock

        mock_db.query.side_effect = mock_query_side_effect

        with pytest.raises(
            ValueError, match="Domain title must be unique within layer"
        ):
            node_service.create_node(sample_domain_data)

    def test_term_validation_requires_parent(self, node_service, sample_term_data):
        """Test term validation rule: Terms must have a parent domain or term."""
        del sample_term_data["parent_node_id"]

        with pytest.raises(InvalidHierarchyError, match="Terms must have a parent domain or term"):
            node_service.create_node(sample_term_data)

    def test_term_validation_parent_must_be_domain_or_term(
        self, node_service, sample_term_data, mock_db
    ):
        """Test term validation rule: Term parent must be a domain or term."""
        # Setup mock to return layer parent (invalid for term)
        parent_layer = Mock(spec=StructureNode)
        parent_layer.node_type = NodeType.LAYER
        mock_db.query.return_value.filter.return_value.first.return_value = parent_layer

        with pytest.raises(InvalidHierarchyError, match="Term parent must be a domain or term"):
            node_service.create_node(sample_term_data)


class TestCircularReferenceValidation:
    """Test circular reference prevention as specified in the design."""

    def test_circular_reference_prevention_direct(self, node_service):
        """Test preventing direct circular reference: structure_node cannot be its own parent."""
        node_id = str(uuid.uuid4())

        with pytest.raises(CircularReferenceError, match="StructureNode cannot be its own parent"):
            node_service._validate_no_circular_reference(node_id, node_id)

    def test_circular_reference_prevention_indirect(self, node_service, mock_db):
        """Test preventing indirect circular reference using ancestor chain."""
        # Create hierarchy: Layer -> Domain -> Term1 -> Term2
        layer_id = str(uuid.uuid4())
        domain_id = str(uuid.uuid4())
        term1_id = str(uuid.uuid4())
        term2_id = str(uuid.uuid4())

        # Setup mock ancestors - term2 is descendant of term1
        layer = Mock(spec=StructureNode)
        layer.id = layer_id
        layer.parent_node_id = None

        domain = Mock(spec=StructureNode)
        domain.id = domain_id
        domain.parent_node_id = layer_id

        term1 = Mock(spec=StructureNode)
        term1.id = term1_id
        term1.parent_node_id = domain_id

        term2 = Mock(spec=StructureNode)
        term2.id = term2_id
        term2.parent_node_id = term1_id  # term2 is child of term1

        def mock_get_node(node_id):
            if node_id == layer_id:
                return layer
            elif node_id == domain_id:
                return domain
            elif node_id == term1_id:
                return term1
            elif node_id == term2_id:
                return term2
            return None

        # Mock the get_node method
        node_service.get_node = Mock(side_effect=mock_get_node)

        # Try to make term1 child of term2 - should detect circular reference
        # This would create: term2 -> term1 -> domain -> layer, but term2 is already child of term1
        with pytest.raises(
            CircularReferenceError, match="Operation would create circular reference"
        ):
            node_service._validate_no_circular_reference(term1_id, term2_id)


class TestNodeServiceCRUD:
    """Test basic CRUD operations of NodeService."""

    def test_create_node_missing_required_fields(self, node_service):
        """Test structure_node creation with missing required fields."""
        # Missing node_type
        with pytest.raises(ValueError, match="node_type is required"):
            node_service.create_node({"title": "Test"})

        # Missing title
        with pytest.raises(ValueError, match="title is required"):
            node_service.create_node({"node_type": "layer"})

    def test_update_node_success(self, node_service, mock_db):
        """Test successful structure_node update."""
        node_id = str(uuid.uuid4())

        # Setup existing structure_node
        existing_node = Mock(spec=StructureNode)
        existing_node.id = node_id
        existing_node.node_type = NodeType.LAYER
        existing_node.title = "Old Title"
        existing_node.version = 1

        # Mock database queries - first call gets the structure_node, second checks uniqueness
        def mock_query_side_effect(*args):
            query_mock = Mock()
            filter_mock = Mock()
            query_mock.filter.return_value = filter_mock

            # First call: get existing structure_node for update
            if mock_db.query.call_count == 1:
                filter_mock.first.return_value = existing_node
            # Second call: check title uniqueness (should return None = unique)
            else:
                filter_mock.first.return_value = None

            return query_mock

        mock_db.query.side_effect = mock_query_side_effect
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Test update
        update_data = {"title": "New Title"}
        result = node_service.update_node(node_id, update_data)

        # Verify updates
        assert existing_node.title == "New Title"
        assert existing_node.version == 2
        assert mock_db.commit.call_count == 2  # StructureNode update + NodeEvent
        mock_db.refresh.assert_called_once()

    def test_update_node_not_found(self, node_service, mock_db):
        """Test updating non-existent structure_node."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="StructureNode not found"):
            node_service.update_node(str(uuid.uuid4()), {"title": "New Title"})

    def test_delete_node_success(self, node_service, mock_db):
        """Test successful structure_node deletion."""
        node_id = str(uuid.uuid4())

        # Setup existing structure_node
        existing_node = Mock(spec=StructureNode)
        existing_node.id = node_id
        existing_node.node_type = NodeType.LAYER

        # Mock multiple query calls for different operations
        def mock_query_side_effect(*args):
            query_mock = Mock()
            filter_mock = Mock()
            query_mock.filter.return_value = filter_mock

            # First call: get structure_node for deletion
            if mock_db.query.call_count == 1:
                filter_mock.first.return_value = existing_node
            # Second call: get descendants (should return empty list - no children)
            elif mock_db.query.call_count == 2:
                filter_mock.all.return_value = []  # No descendants

            return query_mock

        mock_db.query.side_effect = mock_query_side_effect
        mock_db.delete = Mock()
        mock_db.commit = Mock()

        # Test deletion
        result = node_service.delete_node(node_id)

        assert result is True
        mock_db.delete.assert_called_once_with(existing_node)
        assert mock_db.commit.call_count == 2  # StructureNode deletion + NodeEvent

    def test_delete_node_not_found(self, node_service, mock_db):
        """Test deleting non-existent structure_node."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="StructureNode not found"):
            node_service.delete_node(str(uuid.uuid4()))

    def test_get_node(self, node_service, mock_db):
        """Test getting a structure_node by ID."""
        node_id = str(uuid.uuid4())
        expected_node = Mock(spec=StructureNode)
        mock_db.query.return_value.filter.return_value.first.return_value = (
            expected_node
        )

        result = node_service.get_node(node_id)

        assert result == expected_node

    def test_list_nodes_with_filters(self, node_service, mock_db):
        """Test listing structure_nodes with filtering."""
        expected_nodes = [Mock(spec=StructureNode), Mock(spec=StructureNode)]
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = expected_nodes
        # Also need to mock options() for deferred loading
        query_mock.options.return_value = query_mock
        mock_db.query.return_value = query_mock

        result = node_service.list_nodes(
            node_type=NodeType.LAYER, parent_node_id=str(uuid.uuid4()), skip=0, limit=10
        )

        assert result == expected_nodes
        # Verify filtering was applied
        assert query_mock.filter.call_count >= 1

    def test_count_nodes_with_filters(self, node_service, mock_db):
        """Test counting structure_nodes with filtering."""
        expected_count = 42
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.count.return_value = expected_count
        mock_db.query.return_value = query_mock

        result = node_service.count_nodes(node_type=NodeType.DOMAIN)

        assert result == expected_count


class TestNodeHierarchy:
    """Test structure_node hierarchy operations."""

    def test_get_node_children_direct(self, node_service, mock_db):
        """Test getting direct children of a structure_node."""
        parent_id = str(uuid.uuid4())
        expected_children = [Mock(spec=StructureNode), Mock(spec=StructureNode)]

        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value.all.return_value = expected_children
        mock_db.query.return_value = query_mock

        result = node_service.get_node_children(parent_id, recursive=False)

        assert result == expected_children

    def test_get_node_ancestors(self, node_service):
        """Test getting ancestors of a structure_node."""
        # Create hierarchy: Layer -> Domain -> Term
        layer_id = str(uuid.uuid4())
        domain_id = str(uuid.uuid4())
        term_id = str(uuid.uuid4())

        layer = Mock(spec=StructureNode)
        layer.id = layer_id
        layer.parent_node_id = None

        domain = Mock(spec=StructureNode)
        domain.id = domain_id
        domain.parent_node_id = layer_id

        term = Mock(spec=StructureNode)
        term.id = term_id
        term.parent_node_id = domain_id

        def mock_get_node(node_id):
            if node_id == layer_id:
                return layer
            elif node_id == domain_id:
                return domain
            elif node_id == term_id:
                return term
            return None

        node_service.get_node = Mock(side_effect=mock_get_node)

        ancestors = node_service.get_node_ancestors(term_id)

        assert len(ancestors) == 2
        assert ancestors[0] == domain  # Immediate parent
        assert ancestors[1] == layer  # Grandparent


class TestTitleUniquenessValidation:
    """Test title uniqueness validation within domains."""

    def test_check_title_uniqueness_in_domain(self, node_service, mock_db):
        """Test checking title uniqueness within a domain."""
        domain_id = str(uuid.uuid4())
        title = "Test Title"

        # Mock term exists with same title
        existing_term = Mock(spec=StructureNode)
        existing_term.title = title

        # Setup query mocks
        query_mock = Mock()
        filter_mock = Mock()
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = existing_term
        mock_db.query.return_value = query_mock

        # Mock _get_all_terms_in_domain to return some term IDs
        node_service._get_all_terms_in_domain = Mock(return_value=[str(uuid.uuid4())])

        result = node_service._check_title_uniqueness_in_domain(domain_id, title)

        assert result is True  # Title exists (not unique)

    def test_check_title_uniqueness_exclude_id(self, node_service, mock_db):
        """Test title uniqueness check with excluded ID (for updates)."""
        domain_id = str(uuid.uuid4())
        title = "Test Title"
        exclude_id = str(uuid.uuid4())

        # Setup query mocks - first filter call with multiple conditions, second filter for exclude_id
        query_mock = Mock()
        first_filter_mock = Mock()
        second_filter_mock = Mock()

        query_mock.filter.return_value = first_filter_mock
        first_filter_mock.filter.return_value = second_filter_mock
        second_filter_mock.first.return_value = None  # No other term with same title

        mock_db.query.return_value = query_mock

        # Mock to return some terms in the domain including the excluded one
        node_service._get_all_terms_in_domain = Mock(
            return_value=[exclude_id, str(uuid.uuid4())]
        )

        result = node_service._check_title_uniqueness_in_domain(
            domain_id, title, exclude_id=exclude_id
        )

        # Should be False because no other structure_nodes (excluding the specified one) have the title
        assert result is False
