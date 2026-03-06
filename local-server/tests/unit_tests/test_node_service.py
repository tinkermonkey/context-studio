"""
Unit tests for NodeService - Service Layer Tests

Tests the business logic and validation rules for the unified NodeService
as specified in section 8.2 of the Great Normalization design.
"""

import sys
import os
import json
import pytest
import uuid
from unittest.mock import Mock

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa: E501
)

from services.node_service import NodeService  # noqa: E402
from database.models import StructureNode  # noqa: E402
from database.enums import NodeType  # noqa: E402
from graph.graph_service import GraphService  # noqa: E402
from services.exceptions import InvalidHierarchyError, CircularReferenceError, NotFoundError  # noqa: E402, E501
from api.models.structure_nodes import StructureNodeAttribute  # noqa: E402


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
        """Test layer validation rule: Layers cannot have parent structure_nodes."""  # noqa: E501
        # Setup mock for unique title check first (pass this check)
        mock_db.query.return_value.filter.return_value.first.return_value = None  # noqa: E501

        layer_data = {
            "node_type": "layer",
            "title": "Test Layer with Parent",
            "parent_node_id": str(uuid.uuid4()),
        }

        with pytest.raises(
            InvalidHierarchyError, match="Layers cannot have parent structure_nodes"  # noqa: E501
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

    def test_domain_validation_requires_parent(self, node_service, sample_domain_data):  # noqa: E501
        """Test domain validation rule: Domains must have a parent layer."""
        del sample_domain_data["parent_node_id"]

        with pytest.raises(InvalidHierarchyError, match="Domains must have a parent layer"):  # noqa: E501
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

        with pytest.raises(InvalidHierarchyError, match="Domain parent must be a layer"):  # noqa: E501
            node_service.create_node(sample_domain_data)

    def test_domain_validation_unique_title_within_layer(
        self, node_service, sample_domain_data, mock_db
    ):
        """Test domain validation rule: Domain titles must be unique within layer."""  # noqa: E501
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

    def test_term_validation_requires_parent(self, node_service, sample_term_data):  # noqa: E501
        """Test term validation rule: Terms must have a parent domain or term."""  # noqa: E501
        del sample_term_data["parent_node_id"]

        with pytest.raises(InvalidHierarchyError, match="Terms must have a parent domain or term"):  # noqa: E501
            node_service.create_node(sample_term_data)

    def test_term_validation_parent_must_be_domain_or_term(
        self, node_service, sample_term_data, mock_db
    ):
        """Test term validation rule: Term parent must be a domain or term."""
        # Setup mock to return layer parent (invalid for term)
        parent_layer = Mock(spec=StructureNode)
        parent_layer.node_type = NodeType.LAYER
        mock_db.query.return_value.filter.return_value.first.return_value = parent_layer  # noqa: E501

        with pytest.raises(InvalidHierarchyError, match="Term parent must be a domain or term"):  # noqa: E501
            node_service.create_node(sample_term_data)


class TestCircularReferenceValidation:
    """Test circular reference prevention as specified in the design."""

    def test_circular_reference_prevention_direct(self, node_service):
        """Test preventing direct circular reference: structure_node cannot be its own parent."""  # noqa: E501
        node_id = str(uuid.uuid4())

        with pytest.raises(CircularReferenceError, match="StructureNode cannot be its own parent"):  # noqa: E501
            node_service._validate_no_circular_reference(node_id, node_id)

    def test_circular_reference_prevention_indirect(self, node_service, mock_db):  # noqa: E501
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
        # This would create: term2 -> term1 -> domain -> layer, but term2 is already child of term1  # noqa: E501
        with pytest.raises(
            CircularReferenceError, match="Operation would create circular reference"  # noqa: E501
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

        # Mock database queries - first call gets the structure_node, second checks uniqueness  # noqa: E501
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
        node_service.update_node(node_id, update_data)

        # Verify updates
        assert existing_node.title == "New Title"
        assert existing_node.version == 2
        assert mock_db.commit.call_count == 2  # StructureNode update + NodeEvent  # noqa: E501
        mock_db.refresh.assert_called_once()

    def test_update_node_not_found(self, node_service, mock_db):
        """Test updating non-existent structure_node."""
        mock_db.query.return_value.filter.return_value.first.return_value = None  # noqa: E501

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
            # Second call: get descendants (should return empty list - no children)  # noqa: E501
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
        assert mock_db.commit.call_count == 2  # StructureNode deletion + NodeEvent  # noqa: E501

    def test_delete_node_not_found(self, node_service, mock_db):
        """Test deleting non-existent structure_node."""
        mock_db.query.return_value.filter.return_value.first.return_value = None  # noqa: E501

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
            node_type=NodeType.LAYER, parent_node_id=str(uuid.uuid4()), skip=0, limit=10  # noqa: E501
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
        expected_children = [Mock(spec=StructureNode), Mock(spec=StructureNode)]  # noqa: E501

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
        node_service._get_all_terms_in_domain = Mock(return_value=[str(uuid.uuid4())])  # noqa: E501

        result = node_service._check_title_uniqueness_in_domain(domain_id, title)  # noqa: E501

        assert result is True  # Title exists (not unique)

    def test_check_title_uniqueness_exclude_id(self, node_service, mock_db):
        """Test title uniqueness check with excluded ID (for updates)."""
        domain_id = str(uuid.uuid4())
        title = "Test Title"
        exclude_id = str(uuid.uuid4())

        # Setup query mocks - first filter call with multiple conditions, second filter for exclude_id  # noqa: E501
        query_mock = Mock()
        first_filter_mock = Mock()
        second_filter_mock = Mock()

        query_mock.filter.return_value = first_filter_mock
        first_filter_mock.filter.return_value = second_filter_mock
        second_filter_mock.first.return_value = None  # No other term with same title  # noqa: E501

        mock_db.query.return_value = query_mock

        # Mock to return some terms in the domain including the excluded one
        node_service._get_all_terms_in_domain = Mock(
            return_value=[exclude_id, str(uuid.uuid4())]
        )

        result = node_service._check_title_uniqueness_in_domain(
            domain_id, title, exclude_id=exclude_id
        )

        # Should be False because no other structure_nodes (excluding the specified one) have the title  # noqa: E501
        assert result is False


class TestMoveWithTypeConversion:
    """Test move operations with automatic type conversion."""

    def test_infer_node_type_from_parent_root(self, node_service):
        """Test type inference when moving to root (no parent)."""
        result = node_service._infer_node_type_from_parent(None)
        assert result == NodeType.LAYER

    def test_infer_node_type_from_parent_layer(self, node_service):
        """Test type inference when moving under a layer."""
        parent = Mock(spec=StructureNode)
        parent.node_type = NodeType.LAYER

        result = node_service._infer_node_type_from_parent(parent)
        assert result == NodeType.DOMAIN

    def test_infer_node_type_from_parent_domain(self, node_service):
        """Test type inference when moving under a domain."""
        parent = Mock(spec=StructureNode)
        parent.node_type = NodeType.DOMAIN

        result = node_service._infer_node_type_from_parent(parent)
        assert result == NodeType.TERM

    def test_infer_node_type_from_parent_term(self, node_service):
        """Test type inference when moving under a term."""
        parent = Mock(spec=StructureNode)
        parent.node_type = NodeType.TERM

        result = node_service._infer_node_type_from_parent(parent)
        assert result == NodeType.TERM

    def test_convert_node_type_no_change_needed(self, node_service, mock_db):
        """Test conversion when node already has correct type."""
        node = Mock(spec=StructureNode)
        node.id = str(uuid.uuid4())
        node.node_type = NodeType.DOMAIN

        converted_nodes = []

        # Mock query to return no children
        query_mock = Mock()
        query_mock.filter.return_value.all.return_value = []
        mock_db.query.return_value = query_mock

        node_service._convert_node_type_and_children(
            node, NodeType.DOMAIN, converted_nodes
        )

        # Node should not be in converted list since type didn't change
        assert len(converted_nodes) == 0
        assert node.node_type == NodeType.DOMAIN

    def test_convert_node_type_with_change(self, node_service, mock_db):
        """Test conversion when node type needs to change."""
        node = Mock(spec=StructureNode)
        node.id = str(uuid.uuid4())
        node.node_type = NodeType.DOMAIN

        converted_nodes = []

        # Mock query to return no children
        query_mock = Mock()
        query_mock.filter.return_value.all.return_value = []
        mock_db.query.return_value = query_mock

        node_service._convert_node_type_and_children(
            node, NodeType.TERM, converted_nodes
        )

        # Node should be converted to TERM
        assert node.node_type == NodeType.TERM
        assert len(converted_nodes) == 1
        assert converted_nodes[0] == node
        mock_db.add.assert_called_with(node)

    def test_convert_node_type_recursive_layer_to_domain(self, node_service, mock_db):  # noqa: E501
        """Test recursive conversion: layer becomes domain, children become domains."""  # noqa: E501
        parent_node = Mock(spec=StructureNode)
        parent_node.id = str(uuid.uuid4())
        parent_node.node_type = NodeType.LAYER

        child1 = Mock(spec=StructureNode)
        child1.id = str(uuid.uuid4())
        child1.node_type = NodeType.DOMAIN

        child2 = Mock(spec=StructureNode)
        child2.id = str(uuid.uuid4())
        child2.node_type = NodeType.DOMAIN

        converted_nodes = []

        # Mock query to return children
        def mock_query_side_effect(*args):
            query_mock = Mock()
            filter_mock = Mock()
            query_mock.filter.return_value = filter_mock

            # First call: parent's children
            if mock_db.query.call_count == 1:
                filter_mock.all.return_value = [child1, child2]
            # Second call: child1's children (none)
            elif mock_db.query.call_count == 2:
                filter_mock.all.return_value = []
            # Third call: child2's children (none)
            else:
                filter_mock.all.return_value = []

            return query_mock

        mock_db.query.side_effect = mock_query_side_effect

        # Convert layer to domain (children should become terms)
        node_service._convert_node_type_and_children(
            parent_node, NodeType.DOMAIN, converted_nodes
        )

        # Parent should be converted to DOMAIN
        assert parent_node.node_type == NodeType.DOMAIN
        # Children should be converted to TERM
        assert child1.node_type == NodeType.TERM
        assert child2.node_type == NodeType.TERM
        # All three nodes should be in converted list
        assert len(converted_nodes) == 3
        assert parent_node in converted_nodes
        assert child1 in converted_nodes
        assert child2 in converted_nodes

    def test_convert_node_type_recursive_deep_hierarchy(self, node_service, mock_db):  # noqa: E501
        """Test recursive conversion through multiple levels."""
        # Create hierarchy: domain -> term -> term (3 levels)
        domain = Mock(spec=StructureNode)
        domain.id = str(uuid.uuid4())
        domain.node_type = NodeType.DOMAIN

        term1 = Mock(spec=StructureNode)
        term1.id = str(uuid.uuid4())
        term1.node_type = NodeType.TERM

        term2 = Mock(spec=StructureNode)
        term2.id = str(uuid.uuid4())
        term2.node_type = NodeType.TERM

        converted_nodes = []

        # Mock query to return children at each level
        def mock_query_side_effect(*args):
            query_mock = Mock()
            filter_mock = Mock()
            query_mock.filter.return_value = filter_mock

            call_count = mock_db.query.call_count
            if call_count == 1:  # domain's children
                filter_mock.all.return_value = [term1]
            elif call_count == 2:  # term1's children
                filter_mock.all.return_value = [term2]
            else:  # term2's children (none)
                filter_mock.all.return_value = []

            return query_mock

        mock_db.query.side_effect = mock_query_side_effect

        # Convert domain to TERM (should cascade down)
        node_service._convert_node_type_and_children(
            domain, NodeType.TERM, converted_nodes
        )

        # Domain should be converted to TERM
        assert domain.node_type == NodeType.TERM
        # term1 and term2 should remain TERM (no change)
        assert term1.node_type == NodeType.TERM
        assert term2.node_type == NodeType.TERM
        # Only domain should be in converted list (others didn't change)
        assert len(converted_nodes) == 1
        assert domain in converted_nodes

    def test_check_move_conflicts_layer_global_uniqueness(self, node_service, mock_db):  # noqa: E501
        """Test conflict checking for layers (global uniqueness)."""
        node = Mock(spec=StructureNode)
        node.id = str(uuid.uuid4())
        node.title = "Existing Layer"

        # Mock existing layer with same title
        existing_layer = Mock(spec=StructureNode)
        existing_layer.title = "Existing Layer"

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = existing_layer
        mock_db.query.return_value = query_mock

        # Should detect conflict (handle_conflicts="error")
        with pytest.raises(ValueError, match="already exists at target location"):  # noqa: E501
            node_service._check_move_conflicts_with_type(
                node, None, NodeType.LAYER, "error"
            )

    def test_check_move_conflicts_domain_scoped_uniqueness(self, node_service, mock_db):  # noqa: E501
        """Test conflict checking for domains (unique within layer)."""
        node = Mock(spec=StructureNode)
        node.id = str(uuid.uuid4())
        node.title = "Existing Domain"

        target_layer_id = str(uuid.uuid4())

        # Mock existing domain with same title in same layer
        existing_domain = Mock(spec=StructureNode)
        existing_domain.title = "Existing Domain"
        existing_domain.parent_node_id = target_layer_id

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = existing_domain
        mock_db.query.return_value = query_mock

        # Should detect conflict with error mode
        with pytest.raises(ValueError, match="already exists at target location"):  # noqa: E501
            node_service._check_move_conflicts_with_type(
                node, target_layer_id, NodeType.DOMAIN, "error"
            )

    def test_check_move_conflicts_term_scoped_uniqueness(self, node_service, mock_db):  # noqa: E501
        """Test conflict checking for terms (unique within parent)."""
        node = Mock(spec=StructureNode)
        node.id = str(uuid.uuid4())
        node.title = "Existing Term"

        target_parent_id = str(uuid.uuid4())

        # Mock existing term with same title under same parent
        existing_term = Mock(spec=StructureNode)
        existing_term.title = "Existing Term"
        existing_term.parent_node_id = target_parent_id

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = existing_term
        mock_db.query.return_value = query_mock

        # Should detect conflict with error mode
        with pytest.raises(ValueError, match="already exists at target location"):  # noqa: E501
            node_service._check_move_conflicts_with_type(
                node, target_parent_id, NodeType.TERM, "error"
            )

    def test_check_move_conflicts_warn_mode(self, node_service, mock_db):
        """Test conflict checking with warn mode (returns warning)."""
        node = Mock(spec=StructureNode)
        node.id = str(uuid.uuid4())
        node.title = "Existing Layer"

        # Mock existing layer with same title
        existing_layer = Mock(spec=StructureNode)
        existing_layer.title = "Existing Layer"

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = existing_layer
        mock_db.query.return_value = query_mock

        # Should return warning instead of raising
        warning = node_service._check_move_conflicts_with_type(
            node, None, NodeType.LAYER, "warn"
        )

        assert warning is not None
        assert "already exists" in warning.lower()

    def test_check_move_conflicts_rename_mode(self, node_service, mock_db):
        """Test conflict checking with rename mode (renames node)."""
        node = Mock(spec=StructureNode)
        node.id = str(uuid.uuid4())
        node.title = "Conflicting Title"
        original_title = node.title

        # Mock existing layer with same title
        existing_layer = Mock(spec=StructureNode)
        existing_layer.title = "Conflicting Title"

        # Mock _title_exists_at_target to simulate finding conflict then no conflict  # noqa: E501
        def mock_title_exists(title, parent_id, target_type, exclude_id):
            return title == original_title

        node_service._title_exists_at_target = Mock(side_effect=mock_title_exists)  # noqa: E501

        query_mock = Mock()
        query_mock.filter.return_value.first.return_value = existing_layer
        mock_db.query.return_value = query_mock

        # Should rename the node
        warning = node_service._check_move_conflicts_with_type(
            node, None, NodeType.LAYER, "rename"
        )

        # Title should be changed (with suffix)
        assert node.title != original_title
        assert original_title in node.title
        assert warning is not None
        assert "renamed" in warning.lower()

    def test_validate_node_move_allows_term_under_term(self, node_service, mock_db):  # noqa: E501
        """Test that validation allows terms to be placed under other terms."""
        term = Mock(spec=StructureNode)
        term.id = str(uuid.uuid4())
        term.node_type = NodeType.TERM

        parent_term = Mock(spec=StructureNode)
        parent_term.id = str(uuid.uuid4())
        parent_term.node_type = NodeType.TERM
        parent_term.parent_node_id = str(uuid.uuid4())

        # Mock methods to avoid circular reference checks
        node_service.get_node_ancestors = Mock(return_value=[])
        node_service._get_all_descendants = Mock(return_value=[])

        # Should not raise any exception
        try:
            node_service._validate_node_move(term, parent_term)
        except InvalidHierarchyError:
            pytest.fail("Should allow term under term")

    def test_validate_node_move_term_requires_parent(self, node_service):
        """Test that terms cannot be moved to root."""
        term = Mock(spec=StructureNode)
        term.node_type = NodeType.TERM

        with pytest.raises(InvalidHierarchyError, match="Terms must have a parent"):  # noqa: E501
            node_service._validate_node_move(term, None)

    def test_validate_node_move_layer_no_parent(self, node_service):
        """Test that layers can only be moved to root."""
        layer = Mock(spec=StructureNode)
        layer.node_type = NodeType.LAYER

        parent = Mock(spec=StructureNode)
        parent.node_type = NodeType.LAYER

        with pytest.raises(InvalidHierarchyError, match="at root level"):
            node_service._validate_node_move(layer, parent)


class TestNodeAttributeParsing:
    """Test attribute parsing and serialization."""

    def test_parse_attributes_json_valid(self, node_service):
        """Test parsing valid JSON attributes."""
        attributes_json = '[{"key":"category","title":"Category","value":"legal","value_type":"string"}]'  # noqa: E501
        result = node_service._parse_attributes_json(attributes_json)

        assert len(result) == 1
        assert result[0].key == "category"
        assert result[0].value == "legal"
        assert result[0].value_type == "string"

    def test_parse_attributes_json_multiple(self, node_service):
        """Test parsing multiple attributes from JSON."""
        attributes_json = '''[
            {"key":"category","title":"Category","value":"legal","value_type":"string"},
            {"key":"jurisdiction","title":"Jurisdiction","value":"US Federal","value_type":"string"},  # noqa: E501
            {"key":"version","title":"Version","value":1,"value_type":"number"}
        ]'''
        result = node_service._parse_attributes_json(attributes_json)

        assert len(result) == 3
        assert result[0].key == "category"
        assert result[1].key == "jurisdiction"
        assert result[2].key == "version"

    def test_parse_attributes_json_empty_string(self, node_service):
        """Test parsing empty string returns empty list."""
        result = node_service._parse_attributes_json("")
        assert result == []

    def test_parse_attributes_json_none(self, node_service):
        """Test parsing None returns empty list."""
        result = node_service._parse_attributes_json(None)
        assert result == []

    def test_parse_attributes_json_invalid(self, node_service):
        """Test parsing invalid JSON raises ValueError for data corruption."""
        with pytest.raises(ValueError, match="Node has corrupted attribute data"):  # noqa: E501
            node_service._parse_attributes_json("{ invalid json }")

    def test_parse_attributes_json_invalid_structure(self, node_service):
        """Test parsing JSON with invalid attribute structure raises ValueError."""  # noqa: E501
        # JSON with missing required field 'key'
        invalid_attrs = json.dumps([{"title": "Name"}])
        with pytest.raises(ValueError, match="Node attributes are invalid"):
            node_service._parse_attributes_json(invalid_attrs)


class TestNodeAttributeOperations:
    """Test attribute setting, retrieval, and removal operations."""

    def test_set_node_attributes_success(self, node_service, mock_db):
        """Test successfully setting attributes on a node."""
        node_id = str(uuid.uuid4())

        # Create mock node
        node = Mock(spec=StructureNode)
        node.id = node_id
        node.version = 1
        node.attributes = None

        # Mock get_node
        node_service.get_node = Mock(return_value=node)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Create attributes
        attributes = [
            StructureNodeAttribute(key="category", title="Category", value="legal", value_type="string"),  # noqa: E501
            StructureNodeAttribute(key="jurisdiction", title="Jurisdiction", value="US Federal", value_type="string"),  # noqa: E501
        ]

        # Set attributes
        node_service.set_node_attributes(node_id, attributes)

        # Verify
        assert node.version == 2
        assert mock_db.commit.called
        assert mock_db.refresh.called
        assert "category" in node.attributes
        assert "jurisdiction" in node.attributes

    def test_set_node_attributes_empty_list(self, node_service, mock_db):
        """Test setting empty attributes list."""
        node_id = str(uuid.uuid4())

        node = Mock(spec=StructureNode)
        node.id = node_id
        node.version = 1

        node_service.get_node = Mock(return_value=node)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        node_service.set_node_attributes(node_id, [])

        assert node.attributes == "[]"
        assert mock_db.commit.called

    def test_set_node_attributes_node_not_found(self, node_service):
        """Test setting attributes on non-existent node."""
        node_id = str(uuid.uuid4())
        node_service.get_node = Mock(return_value=None)

        attributes = [StructureNodeAttribute(key="test", title="Test", value="value", value_type="string")]  # noqa: E501

        with pytest.raises(ValueError, match="not found"):
            node_service.set_node_attributes(node_id, attributes)

    def test_get_local_attributes_success(self, node_service):
        """Test retrieving only local attributes."""
        node_id = str(uuid.uuid4())

        node = Mock(spec=StructureNode)
        node.id = node_id
        node.attributes = '[{"key":"category","title":"Category","value":"legal","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=node)

        result = node_service.get_local_attributes(node_id)

        assert len(result) == 1
        assert result[0].key == "category"
        assert result[0].value == "legal"

    def test_get_local_attributes_empty(self, node_service):
        """Test retrieving local attributes when none exist."""
        node_id = str(uuid.uuid4())

        node = Mock(spec=StructureNode)
        node.id = node_id
        node.attributes = None

        node_service.get_node = Mock(return_value=node)

        result = node_service.get_local_attributes(node_id)

        assert result == []

    def test_get_local_attributes_node_not_found(self, node_service):
        """Test retrieving attributes from non-existent node."""
        node_id = str(uuid.uuid4())
        node_service.get_node = Mock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            node_service.get_local_attributes(node_id)

    def test_remove_node_attribute_success(self, node_service, mock_db):
        """Test removing specific attribute by key."""
        node_id = str(uuid.uuid4())

        node = Mock(spec=StructureNode)
        node.id = node_id
        node.version = 1
        node.attributes = '[{"key":"category","title":"Category","value":"legal","value_type":"string"},{"key":"jurisdiction","title":"Jurisdiction","value":"US","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=node)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        node_service.remove_node_attribute(node_id, "category")

        # Verify category was removed
        remaining = node_service._parse_attributes_json(node.attributes)
        assert len(remaining) == 1
        assert remaining[0].key == "jurisdiction"
        assert mock_db.commit.called

    def test_remove_node_attribute_not_found(self, node_service, mock_db):
        """Test removing non-existent attribute key."""
        node_id = str(uuid.uuid4())

        node = Mock(spec=StructureNode)
        node.id = node_id
        node.version = 1
        node.attributes = '[{"key":"category","title":"Category","value":"legal","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=node)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        node_service.remove_node_attribute(node_id, "nonexistent")

        # Attributes should remain unchanged
        remaining = node_service._parse_attributes_json(node.attributes)
        assert len(remaining) == 1
        assert remaining[0].key == "category"

    def test_remove_node_attribute_all_attributes(self, node_service, mock_db):
        """Test removing all attributes one by one."""
        node_id = str(uuid.uuid4())

        node = Mock(spec=StructureNode)
        node.id = node_id
        node.version = 1
        node.attributes = '[{"key":"test","title":"Test","value":"value","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=node)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        node_service.remove_node_attribute(node_id, "test")

        remaining = node_service._parse_attributes_json(node.attributes)
        assert len(remaining) == 0


class TestNodeAttributeInheritance:
    """Test attribute inheritance resolution."""

    def test_resolve_node_attributes_no_parent(self, node_service):
        """Test resolving attributes on single node without parent."""
        node_id = str(uuid.uuid4())

        node = Mock(spec=StructureNode)
        node.id = node_id
        node.attributes = '[{"key":"category","title":"Category","value":"legal","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=node)
        node_service.get_node_ancestors = Mock(return_value=[])

        result = node_service.resolve_node_attributes(node_id)

        assert len(result) == 1
        assert result[0].key == "category"
        assert result[0].value == "legal"
        assert result[0].inherited is False
        assert str(result[0].source_node_id) == node_id

    def test_resolve_node_attributes_with_inheritance(self, node_service):
        """Test resolving attributes with parent inheritance."""
        layer_id = str(uuid.uuid4())
        domain_id = str(uuid.uuid4())

        layer = Mock(spec=StructureNode)
        layer.id = layer_id
        layer.attributes = '[{"key":"category","title":"Category","value":"legal","value_type":"string"}]'  # noqa: E501

        domain = Mock(spec=StructureNode)
        domain.id = domain_id
        domain.attributes = '[{"key":"jurisdiction","title":"Jurisdiction","value":"US Federal","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=domain)
        node_service.get_node_ancestors = Mock(return_value=[layer])

        result = node_service.resolve_node_attributes(domain_id)

        assert len(result) == 2
        # Find inherited attribute
        inherited = [r for r in result if r.key == "category"][0]
        assert inherited.inherited is True
        assert str(inherited.source_node_id) == layer_id
        # Find local attribute
        local = [r for r in result if r.key == "jurisdiction"][0]
        assert local.inherited is False
        assert str(local.source_node_id) == domain_id

    def test_resolve_node_attributes_override(self, node_service):
        """Test child attribute overrides parent value."""
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())

        parent = Mock(spec=StructureNode)
        parent.id = parent_id
        parent.attributes = '[{"key":"jurisdiction","title":"Jurisdiction","value":"US Federal","value_type":"string"}]'  # noqa: E501

        child = Mock(spec=StructureNode)
        child.id = child_id
        child.attributes = '[{"key":"jurisdiction","title":"Jurisdiction","value":"New York State","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=child)
        node_service.get_node_ancestors = Mock(return_value=[parent])

        result = node_service.resolve_node_attributes(child_id)

        assert len(result) == 1
        assert result[0].key == "jurisdiction"
        assert result[0].value == "New York State"  # Child value wins
        assert result[0].inherited is False
        assert str(result[0].source_node_id) == child_id

    def test_resolve_node_attributes_deep_hierarchy(self, node_service):
        """Test attribute resolution with deep 5+ level hierarchy."""
        # Create: Layer -> Domain -> Term1 -> Term2 -> Term3
        layer_id = str(uuid.uuid4())
        domain_id = str(uuid.uuid4())
        term1_id = str(uuid.uuid4())
        term2_id = str(uuid.uuid4())
        term3_id = str(uuid.uuid4())

        layer = Mock(spec=StructureNode)
        layer.id = layer_id
        layer.attributes = '[{"key":"level","title":"Level","value":"layer","value_type":"string"}]'  # noqa: E501

        domain = Mock(spec=StructureNode)
        domain.id = domain_id
        domain.attributes = '[{"key":"domain_attr","title":"Domain Attr","value":"domain_val","value_type":"string"}]'  # noqa: E501

        term1 = Mock(spec=StructureNode)
        term1.id = term1_id
        term1.attributes = '[{"key":"term1_attr","title":"Term1 Attr","value":"term1_val","value_type":"string"}]'  # noqa: E501

        term2 = Mock(spec=StructureNode)
        term2.id = term2_id
        term2.attributes = '[{"key":"term2_attr","title":"Term2 Attr","value":"term2_val","value_type":"string"}]'  # noqa: E501

        term3 = Mock(spec=StructureNode)
        term3.id = term3_id
        term3.attributes = '[{"key":"term3_attr","title":"Term3 Attr","value":"term3_val","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=term3)
        node_service.get_node_ancestors = Mock(return_value=[layer, domain, term1, term2])  # noqa: E501

        result = node_service.resolve_node_attributes(term3_id)

        # Should have all attributes
        assert len(result) == 5
        keys = {r.key for r in result}
        assert keys == {"level", "domain_attr", "term1_attr", "term2_attr", "term3_attr"}  # noqa: E501
        # All but last should be inherited
        term3_attr = [r for r in result if r.key == "term3_attr"][0]
        assert term3_attr.inherited is False

    def test_resolve_node_attributes_multiple_keys(self, node_service):
        """Test inheritance with multiple attributes at each level."""
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())

        parent = Mock(spec=StructureNode)
        parent.id = parent_id
        parent.attributes = '[{"key":"attr1","title":"Attr 1","value":"parent1","value_type":"string"},{"key":"attr2","title":"Attr 2","value":"parent2","value_type":"string"}]'  # noqa: E501

        child = Mock(spec=StructureNode)
        child.id = child_id
        child.attributes = '[{"key":"attr3","title":"Attr 3","value":"child3","value_type":"string"}]'  # noqa: E501

        node_service.get_node = Mock(return_value=child)
        node_service.get_node_ancestors = Mock(return_value=[parent])

        result = node_service.resolve_node_attributes(child_id)

        assert len(result) == 3
        keys = {r.key for r in result}
        assert keys == {"attr1", "attr2", "attr3"}

    def test_resolve_node_attributes_node_not_found(self, node_service):
        """Test resolving attributes on non-existent node."""
        node_id = str(uuid.uuid4())
        node_service.get_node = Mock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            node_service.resolve_node_attributes(node_id)


class TestAttributeValueTypeValidation:
    """Test attribute value type validation."""

    def test_attribute_value_type_string(self, node_service):
        """Test string value type."""
        attr = StructureNodeAttribute(key="title", title="Title", value="Test String", value_type="string")  # noqa: E501
        assert attr.value_type == "string"

    def test_attribute_value_type_number(self, node_service):
        """Test number value type."""
        attr = StructureNodeAttribute(key="count", title="Count", value=42, value_type="number")  # noqa: E501
        assert attr.value_type == "number"

    def test_attribute_value_type_boolean(self, node_service):
        """Test boolean value type."""
        attr = StructureNodeAttribute(key="active", title="Active", value=True, value_type="boolean")  # noqa: E501
        assert attr.value_type == "boolean"

    def test_attribute_value_type_date(self, node_service):
        """Test date value type."""
        attr = StructureNodeAttribute(key="created", title="Created", value="2025-01-15", value_type="date")  # noqa: E501
        assert attr.value_type == "date"

    def test_attribute_value_type_url(self, node_service):
        """Test URL value type."""
        attr = StructureNodeAttribute(key="reference", title="Reference", value="https://example.com", value_type="url")  # noqa: E501
        assert attr.value_type == "url"


class TestLegalDomainHierarchyFixture:
    """Test realistic Legal Domain hierarchy from business requirements."""

    def test_legal_domain_hierarchy_structure(self, node_service):
        """Test the complete Legal Domain hierarchy example."""
        # Setup the hierarchy: Layer -> Domain -> Term structure
        layer_id = str(uuid.uuid4())
        domain_id = str(uuid.uuid4())
        term1_id = str(uuid.uuid4())
        term2_id = str(uuid.uuid4())

        # Legal Domain layer
        layer = Mock(spec=StructureNode)
        layer.id = layer_id
        layer.title = "Legal Domain"
        layer.attributes = '[{"key":"category","title":"Category","value":"domain_classification","value_type":"string"}]'  # noqa: E501

        # Contract Law domain
        domain = Mock(spec=StructureNode)
        domain.id = domain_id
        domain.title = "Contract Law"
        domain.parent_node_id = layer_id
        domain.attributes = '[{"key":"jurisdiction","title":"Jurisdiction","value":"US Federal","value_type":"string"}]'  # noqa: E501

        # Force Majeure term
        term1 = Mock(spec=StructureNode)
        term1.id = term1_id
        term1.title = "Force Majeure"
        term1.parent_node_id = domain_id
        term1.attributes = '[{"key":"jurisdiction","title":"Jurisdiction","value":"New York State","value_type":"string"},{"key":"definition_date","title":"Definition Date","value":"2025-01-15","value_type":"date"}]'  # noqa: E501

        # Indemnification term (no local attributes, inherits all)
        term2 = Mock(spec=StructureNode)
        term2.id = term2_id
        term2.title = "Indemnification"
        term2.parent_node_id = domain_id
        term2.attributes = '[]'

        # Test Force Majeure resolution (term with override)
        node_service.get_node = Mock(return_value=term1)
        node_service.get_node_ancestors = Mock(return_value=[layer, domain])

        result = node_service.resolve_node_attributes(term1_id)

        # Should have category (inherited), jurisdiction (overridden), and definition_date (local)  # noqa: E501
        assert len(result) == 3
        keys = {r.key for r in result}
        assert keys == {"category", "jurisdiction", "definition_date"}

        # Verify overrides
        jurisdiction = [r for r in result if r.key == "jurisdiction"][0]
        assert jurisdiction.value == "New York State"
        assert str(jurisdiction.source_node_id) == term1_id

        # Test Indemnification resolution (term with no local attributes)
        node_service.get_node = Mock(return_value=term2)
        node_service.get_node_ancestors = Mock(return_value=[layer, domain])

        result = node_service.resolve_node_attributes(term2_id)

        # Should inherit both attributes from ancestors
        assert len(result) == 2
        keys = {r.key for r in result}
        assert keys == {"category", "jurisdiction"}

        # Both should be inherited
        for attr in result:
            assert attr.inherited is True


def test_create_node_version_management_failure(mock_db, mock_graph_service):
    """Test that node creation is aborted when version management fails.

    When version_manager.create_version() or working_tree_manager.initialize_entity_in_working_tree()  # noqa: E501
    raise exceptions, the handler should:
    1. Log the error with full traceback
    2. Rollback the database
    3. Raise ValidationError with specific message (not ValueError)
    4. NOT catch and re-raise as ValueError

    This ensures the API consumer receives the correct error type and status code.  # noqa: E501
    """
    from services.exceptions import ValidationError

    # Create node service with mocked version management
    mock_version_manager = Mock()
    mock_working_tree_manager = Mock()
    node_service = NodeService(db=mock_db, graph_service=mock_graph_service)
    node_service.version_manager = mock_version_manager
    node_service.working_tree_manager = mock_working_tree_manager

    # Setup database mocks to pass validation checks
    # Query for unique title check should return None (no existing node)
    mock_query = Mock()
    mock_filter = Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = None
    mock_db.query.return_value = mock_query

    # Mock successful add, commit, and refresh
    test_node_id = str(uuid.uuid4())

    def refresh_side_effect(obj):
        # Set ID on the object when refresh is called
        if hasattr(obj, 'id'):
            obj.id = test_node_id

    mock_db.add = Mock()
    mock_db.commit = Mock()
    mock_db.refresh = Mock(side_effect=refresh_side_effect)
    mock_db.rollback = Mock()

    # Simulate version_manager.create_version() raising an exception
    version_error = Exception("Version database connection failed")
    mock_version_manager.create_version.side_effect = version_error

    # Attempt to create node
    with pytest.raises(ValidationError) as exc_info:
        node_service.create_node({
            "node_type": "layer",
            "title": "Unique Test Layer"
        })

    # Verify the error message is specific and informative
    assert "Cannot create node" in str(exc_info.value)
    assert "version management initialization failed" in str(exc_info.value)
    assert "database or configuration issue" in str(exc_info.value)

    # Verify rollback was called
    mock_db.rollback.assert_called()


def test_create_node_version_management_failure_working_tree(mock_db, mock_graph_service):  # noqa: E501
    """Test that node creation is aborted when working tree initialization fails.  # noqa: E501

    Similar to test_create_node_version_management_failure but tests the case where  # noqa: E501
    working_tree_manager.initialize_entity_in_working_tree() fails.
    """
    from services.exceptions import ValidationError

    # Create node service with mocked version management
    mock_version_manager = Mock()
    mock_working_tree_manager = Mock()
    node_service = NodeService(db=mock_db, graph_service=mock_graph_service)
    node_service.version_manager = mock_version_manager
    node_service.working_tree_manager = mock_working_tree_manager

    # Setup database mocks to pass validation checks
    # Query for unique title check should return None (no existing node)
    mock_query = Mock()
    mock_filter = Mock()
    mock_query.filter.return_value = mock_filter
    mock_filter.first.return_value = None
    mock_db.query.return_value = mock_query

    # Mock successful add, commit, and refresh
    test_node_id = str(uuid.uuid4())

    def refresh_side_effect(obj):
        # Set ID on the object when refresh is called
        if hasattr(obj, 'id'):
            obj.id = test_node_id

    mock_db.add = Mock()
    mock_db.commit = Mock()
    mock_db.refresh = Mock(side_effect=refresh_side_effect)
    mock_db.rollback = Mock()

    # Mock version_manager.create_version() to succeed but working tree init to fail  # noqa: E501
    mock_version = Mock()
    mock_version.id = uuid.uuid4()
    mock_version_manager.create_version.return_value = mock_version

    # Simulate working_tree_manager.initialize_entity_in_working_tree() raising an exception  # noqa: E501
    tree_error = Exception("Working tree database transaction failed")
    mock_working_tree_manager.initialize_entity_in_working_tree.side_effect = tree_error  # noqa: E501

    # Attempt to create node
    with pytest.raises(ValidationError) as exc_info:
        node_service.create_node({
            "node_type": "layer",
            "title": "Another Unique Layer"
        })

    # Verify the error message is specific and informative
    assert "Cannot create node" in str(exc_info.value)
    assert "version management initialization failed" in str(exc_info.value)

    # Verify rollback was called
    mock_db.rollback.assert_called()

    # Verify create_version was called
    mock_version_manager.create_version.assert_called_once()

    # Verify initialize_entity_in_working_tree was called
    mock_working_tree_manager.initialize_entity_in_working_tree.assert_called_once()  # noqa: E501
