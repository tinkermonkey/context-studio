"""
StructureNode Service - Centralized business logic for structure_node operations

This service implements the business logic for the normalized structure_node structure,
handling type-specific validations and constraints for layers, domains, and terms.
"""

import json
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import ValidationError as PydanticValidationError

from database.models import StructureNode, ChangeEvent, Predicate
from api.models.structure_nodes import StructureNodeAttribute, ResolvedAttribute
from database.enums import NodeType
from graph.graph_service import GraphService
from embeddings.generate_embeddings import generate_embedding
from services.change_event_handler import ChangeEventHandler
from services.version_manager import VersionManager, ChangeState
from services.working_tree_manager import WorkingTreeManager
from services.exceptions import NotFoundError, ValidationError, ConflictError, CircularReferenceError, InvalidHierarchyError
from utils.logger import get_logger

logger = get_logger(__name__)


class NodeService:
    """Centralized business logic for structure_node operations"""

    def __init__(self, db: Session, graph_service: Optional[GraphService] = None,
                 version_manager: Optional[VersionManager] = None,
                 working_tree_manager: Optional[WorkingTreeManager] = None):
        """
        Initialize the NodeService.

        Args:
            db: SQLAlchemy database session
            graph_service: Optional graph service for graph operations
            version_manager: Optional version manager for versioning
            working_tree_manager: Optional working tree manager for state tracking
        """
        self.db = db
        self.graph_service = (
            graph_service  # Keep optional for now since GraphService needs updating
        )
        self.version_manager = version_manager
        self.working_tree_manager = working_tree_manager
        self.event_handler = ChangeEventHandler(db)
        logger.debug("NodeService initialized")

    def create_node(self, node_data: Dict[str, Any]) -> StructureNode:
        """
        Create a new structure_node with type-specific validation.

        Args:
            node_data: Dictionary containing structure_node data

        Returns:
            Created StructureNode instance

        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Creating structure_node with type: {node_data.get('node_type')}")

        # Validate required fields
        if "node_type" not in node_data:
            raise ValueError("node_type is required")
        if "title" not in node_data:
            raise ValueError("title is required")

        node_type = NodeType(node_data["node_type"])

        # Validate structural predicate ID if provided
        self._validate_structural_predicate_id(node_data.get("structural_predicate_id"))

        # Validate structure_node type specific rules
        self._validate_node_creation(node_data, node_type)

        # Check for circular references if parent is specified
        if node_data.get("parent_node_id"):
            self._validate_no_circular_reference(None, node_data["parent_node_id"])

        # Generate embeddings
        title_embedding = None
        definition_embedding = None

        if node_data.get("title"):
            try:
                title_embedding = generate_embedding(node_data["title"])
            except Exception as e:
                logger.error(
                    f"Failed to generate title embedding for '{node_data['title']}': {e}",
                    exc_info=True
                )
                raise ValidationError(
                    f"Cannot create node: embedding generation failed. "
                    f"This may indicate LLM service issues. Please try again or contact support. "
                    f"Error: {str(e)}"
                )

        if node_data.get("definition"):
            try:
                definition_embedding = generate_embedding(node_data["definition"])
            except Exception as e:
                logger.error(
                    f"Failed to generate definition embedding: {e}",
                    exc_info=True
                )
                raise ValidationError(
                    f"Cannot create node: definition embedding generation failed. "
                    f"Error: {str(e)}"
                )

        # Create structure_node
        structure_node = StructureNode(
            node_type=node_type,
            parent_node_id=node_data.get("parent_node_id"),
            title=node_data["title"],
            definition=node_data.get("definition"),
            structural_predicate_id=node_data.get("structural_predicate_id"),
            title_embedding=title_embedding,
            definition_embedding=definition_embedding,
        )

        try:
            self.db.add(structure_node)
            self.db.commit()
            self.db.refresh(structure_node)

            # Verify the ID was properly generated after refresh
            if not structure_node.id or not isinstance(structure_node.id, str):
                logger.error(
                    f"Invalid ID after db.refresh(): {repr(structure_node.id)} "
                    f"(type: {type(structure_node.id).__name__})"
                )
                raise ValueError(
                    f"Database failed to generate valid ID for structure_node. "
                    f"Got: {repr(structure_node.id)} (type: {type(structure_node.id).__name__})"
                )

            logger.info(
                f"Successfully created structure_node: {structure_node.id} ({structure_node.node_type})"
            )

            # Initialize version management and working tree state immediately
            if self.version_manager and self.working_tree_manager:
                try:
                    # Convert entity to dict for version content
                    node_dict = self._node_to_dict(structure_node)

                    # Create initial version
                    version = self.version_manager.create_version(
                        entity_type='structure_node',
                        entity_id=str(structure_node.id),
                        content=node_dict,
                        author_id='system',  # TODO: Get from request context
                        state=ChangeState.WORKING
                    )

                    # Initialize entity in working tree
                    self.working_tree_manager.initialize_entity_in_working_tree(
                        entity_type='structure_node',
                        entity_id=str(structure_node.id),
                        initial_version_id=version.id
                    )

                    logger.info(f"Initialized version management for structure_node: {structure_node.id}")

                except Exception as e:
                    logger.warning(f"Failed to initialize version management for {structure_node.id}: {e}")
                    # Don't fail the entity creation if version management fails

            # Fire structure_node created event using new ChangeEventHandler
            node_dict = self._node_to_dict(structure_node)
            from database.enums import RecordType

            self.event_handler.fire_created_event(
                RecordType.STRUCTURE_NODE, str(structure_node.id), node_dict
            )

            return structure_node

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create structure_node: {e}")
            raise ValueError(f"Failed to create structure_node: {e}")

    def update_node(self, node_id: str, node_data: Dict[str, Any]) -> StructureNode:
        """
        Update an existing structure_node with type-specific validation.

        Args:
            node_id: ID of the structure_node to update
            node_data: Dictionary containing updated structure_node data

        Returns:
            Updated StructureNode instance

        Raises:
            ValueError: If validation fails or structure_node not found
        """
        logger.info(f"Updating structure_node: {node_id}")

        # Get existing structure_node
        structure_node = (
            self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        )
        if not structure_node:
            raise NotFoundError("StructureNode", node_id)

        # Store old data for validation and events
        old_node_data = self._node_to_dict(structure_node)

        # Validate structural predicate ID if being updated
        if "structural_predicate_id" in node_data:
            self._validate_structural_predicate_id(node_data["structural_predicate_id"])

        # Validate updates based on structure_node type
        self._validate_node_update(structure_node, node_data)

        # Check for circular references if parent is being changed
        if (
            "parent_node_id" in node_data
            and node_data["parent_node_id"] != structure_node.parent_node_id
        ):
            self._validate_no_circular_reference(node_id, node_data["parent_node_id"])

        # Update fields
        if "title" in node_data:
            structure_node.title = node_data["title"]
            # Regenerate title embedding
            try:
                structure_node.title_embedding = generate_embedding(node_data["title"])
            except Exception as e:
                logger.warning(f"Failed to generate title embedding: {e}")

        if "definition" in node_data:
            structure_node.definition = node_data["definition"]
            # Regenerate definition embedding
            try:
                if node_data["definition"]:
                    structure_node.definition_embedding = generate_embedding(
                        node_data["definition"]
                    )
                else:
                    structure_node.definition_embedding = None
            except Exception as e:
                logger.warning(f"Failed to generate definition embedding: {e}")

        if "parent_node_id" in node_data:
            structure_node.parent_node_id = node_data["parent_node_id"]

        if "structural_predicate_id" in node_data:
            structure_node.structural_predicate_id = node_data[
                "structural_predicate_id"
            ]

        # Update version
        structure_node.version = structure_node.version + 1

        try:
            self.db.commit()
            self.db.refresh(structure_node)

            logger.info(f"Successfully updated structure_node: {structure_node.id}")

            # Fire structure_node updated event using new ChangeEventHandler
            new_node_data = self._node_to_dict(structure_node)
            from database.enums import RecordType

            self.event_handler.fire_updated_event(
                RecordType.STRUCTURE_NODE,
                str(structure_node.id),
                old_node_data,
                new_node_data,
            )

            return structure_node

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update structure_node: {e}")
            raise ValueError(f"Failed to update structure_node: {e}")

    def delete_node(self, node_id: str) -> bool:
        """
        Delete a structure_node and its children (cascade delete).

        Args:
            node_id: ID of the structure_node to delete

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If structure_node not found
        """
        logger.info(f"Deleting structure_node: {node_id}")

        structure_node = (
            self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        )
        if not structure_node:
            raise NotFoundError("StructureNode", node_id)

        # Store structure_node data for event before deletion
        node_data = self._node_to_dict(structure_node)
        node_type = structure_node.node_type.value

        # Get all descendant structure_nodes recursively
        all_descendants = self._get_all_descendants(node_id)
        total_children = len(all_descendants)

        try:
            # Delete all descendants first (bottom-up)
            for descendant in reversed(all_descendants):
                self.db.delete(descendant)

            # Then delete the structure_node itself
            self.db.delete(structure_node)
            self.db.commit()

            logger.info(
                f"Successfully deleted structure_node {node_id} and {total_children} children"
            )

            # Fire structure_node deleted event using new ChangeEventHandler
            from database.enums import RecordType

            self.event_handler.fire_deleted_event(
                RecordType.STRUCTURE_NODE, node_id, node_data
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete structure_node: {e}")
            raise ValueError(f"Failed to delete structure_node: {e}")

    def get_node(self, node_id: str) -> Optional[StructureNode]:
        """
        Get a structure_node by ID.

        Args:
            node_id: ID of the structure_node to retrieve

        Returns:
            StructureNode instance or None if not found
        """
        return self.db.query(StructureNode).filter(StructureNode.id == node_id).first()

    def list_nodes(
        self,
        node_type: Optional[NodeType] = None,
        parent_node_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StructureNode]:
        """
        List structure_nodes with optional filtering.

        Args:
            node_type: Optional structure_node type to filter by
            parent_node_id: Optional parent structure_node ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of StructureNode instances
        """
        # Defer expensive vector columns for list operations to improve performance
        from sqlalchemy.orm import defer
        import time
        from utils.logger import get_logger

        logger = get_logger(__name__)
        start_time = time.time()

        query = self.db.query(StructureNode).options(
            defer(StructureNode.title_embedding),
            defer(StructureNode.definition_embedding)
        )

        if node_type:
            query = query.filter(StructureNode.node_type == node_type)

        if parent_node_id:
            query = query.filter(StructureNode.parent_node_id == parent_node_id)

        query = query.order_by(StructureNode.title).offset(skip).limit(limit)

        query_build_time = time.time() - start_time
        logger.debug(f"Query build time: {query_build_time*1000:.2f}ms")

        execution_start = time.time()
        result = query.all()
        execution_time = time.time() - execution_start

        # Validate result type - should always be a list from SQLAlchemy
        if not isinstance(result, list):
            logger.error(
                f"Database query returned invalid type {type(result).__name__}, expected list. "
                f"This indicates a serious database or ORM failure. "
                f"Query params: node_type={node_type}, parent_node_id={parent_node_id}, skip={skip}, limit={limit}"
            )
            raise ValueError(
                f"Database query failed: expected list, got {type(result).__name__}. "
                f"This indicates a database connection or ORM issue."
            )

        result_length = len(result)
        logger.debug(f"Query execution time: {execution_time*1000:.2f}ms for {result_length} nodes (skip={skip})")

        return result

    def count_nodes(
        self, node_type: Optional[NodeType] = None, parent_node_id: Optional[str] = None
    ) -> int:
        """
        Count structure_nodes with optional filtering.

        Args:
            node_type: Optional structure_node type to filter by
            parent_node_id: Optional parent structure_node ID to filter by

        Returns:
            Count of matching structure_nodes
        """
        query = self.db.query(StructureNode)

        if node_type:
            query = query.filter(StructureNode.node_type == node_type)

        if parent_node_id:
            query = query.filter(StructureNode.parent_node_id == parent_node_id)

        return query.count()

    def get_nodes(
        self,
        node_type: Optional[NodeType] = None,
        parent_node_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[StructureNode]:
        """
        Get structure_nodes with optional filtering and pagination.

        Args:
            node_type: Optional structure_node type to filter by
            parent_node_id: Optional parent structure_node ID to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of matching structure_nodes
        """
        query = self.db.query(StructureNode)

        if node_type:
            query = query.filter(StructureNode.node_type == node_type)

        if parent_node_id:
            query = query.filter(StructureNode.parent_node_id == parent_node_id)

        query = query.order_by(StructureNode.title)

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_node_children(
        self, node_id: str, recursive: bool = False
    ) -> List[StructureNode]:
        """
        Get children of a structure_node.

        Args:
            node_id: Parent structure_node ID
            recursive: Whether to get all descendants or just direct children

        Returns:
            List of child StructureNode instances
        """
        if not recursive:
            return (
                self.db.query(StructureNode)
                .filter(StructureNode.parent_node_id == node_id)
                .order_by(StructureNode.title)
                .all()
            )

        # For recursive, we need to traverse the tree
        all_children = []
        direct_children = (
            self.db.query(StructureNode)
            .filter(StructureNode.parent_node_id == node_id)
            .all()
        )

        for child in direct_children:
            all_children.append(child)
            all_children.extend(self.get_node_children(child.id, recursive=True))

        return all_children

    def get_node_ancestors(self, node_id: str) -> List[StructureNode]:
        """
        Get all ancestors of a structure_node (up to root).

        Args:
            node_id: StructureNode ID to get ancestors for

        Returns:
            List of ancestor StructureNode instances (from immediate parent to root)
        """
        ancestors = []
        current_node = self.get_node(node_id)

        while current_node and current_node.parent_node_id:
            parent = self.get_node(current_node.parent_node_id)
            if parent:
                ancestors.append(parent)
                current_node = parent
            else:
                break

        return ancestors

    def _parse_attributes_json(self, attributes_json: Optional[str]) -> List[StructureNodeAttribute]:
        """
        Parse attributes JSON string into list of StructureNodeAttribute objects.

        Args:
            attributes_json: JSON string containing attributes array

        Returns:
            List of StructureNodeAttribute instances (empty list if attributes_json is None/empty)

        Raises:
            ValueError: If JSON is corrupted or attribute structure is invalid
        """
        if not attributes_json:
            return []

        try:
            data = json.loads(attributes_json)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted attribute JSON: {e}", exc_info=True)
            raise ValueError(f"Node has corrupted attribute data: {str(e)}")

        try:
            return [StructureNodeAttribute(**attr) for attr in data]
        except (TypeError, KeyError, ValueError, PydanticValidationError) as e:
            logger.error(f"Invalid attribute structure: {e}", exc_info=True)
            raise ValueError(f"Node attributes are invalid: {str(e)}")

    def set_node_attributes(self, node_id: UUID, attributes: List[StructureNodeAttribute]) -> StructureNode:
        """
        Set local attributes on a node, replacing existing attributes.

        Args:
            node_id: ID of the structure node
            attributes: List of StructureNodeAttribute instances to set

        Returns:
            Updated StructureNode instance

        Raises:
            ValueError: If node not found or validation fails
        """
        node = self.get_node(str(node_id))
        if not node:
            raise ValueError(f"Node {node_id} not found")

        # Serialize to JSON
        attributes_json = json.dumps([attr.model_dump(mode='json') for attr in attributes])
        node.attributes = attributes_json
        node.version = node.version + 1
        self.db.commit()
        self.db.refresh(node)
        return node

    def get_local_attributes(self, node_id: UUID) -> List[StructureNodeAttribute]:
        """
        Get only the node's own attributes (not inherited).

        Args:
            node_id: ID of the structure node

        Returns:
            List of StructureNodeAttribute instances for this node only

        Raises:
            ValueError: If node not found, or if attribute data is corrupted or invalid
        """
        node = self.get_node(str(node_id))
        if not node:
            raise ValueError(f"Node {node_id} not found")
        return self._parse_attributes_json(node.attributes)

    def resolve_node_attributes(self, node_id: UUID) -> List[ResolvedAttribute]:
        """
        Walk ancestor chain and return merged attributes with inheritance information.

        Child values override parent values for matching keys. The chain is walked
        from most distant ancestor to target node, with child values taking precedence.

        Args:
            node_id: ID of the structure node

        Returns:
            List of ResolvedAttribute instances with inherited flags and source node IDs

        Raises:
            ValueError: If node not found, or if attribute data is corrupted or invalid
        """
        node = self.get_node(str(node_id))
        if not node:
            raise ValueError(f"Node {node_id} not found")

        # Get all ancestors using existing method (no depth limit)
        ancestors = self.get_node_ancestors(str(node_id))

        # Build attribute map from most distant ancestor to target node
        attribute_map = {}
        for ancestor in reversed(ancestors):  # Most distant first
            ancestor_attrs = self._parse_attributes_json(ancestor.attributes)
            for attr in ancestor_attrs:
                attribute_map[attr.key] = ResolvedAttribute(
                    key=attr.key,
                    title=attr.title,
                    value=attr.value,
                    value_type=attr.value_type,
                    inherited=(ancestor.id != node.id),
                    source_node_id=UUID(ancestor.id)
                )

        # Add local attributes last (override inherited)
        local_attrs = self._parse_attributes_json(node.attributes)
        for attr in local_attrs:
            attribute_map[attr.key] = ResolvedAttribute(
                key=attr.key,
                title=attr.title,
                value=attr.value,
                value_type=attr.value_type,
                inherited=False,
                source_node_id=UUID(node.id)
            )

        return list(attribute_map.values())

    def remove_node_attribute(self, node_id: UUID, key: str) -> StructureNode:
        """
        Remove a specific attribute by key.

        Args:
            node_id: ID of the structure node
            key: Attribute key to remove

        Returns:
            Updated StructureNode instance

        Raises:
            ValueError: If node not found, or if attribute data is corrupted or invalid
        """
        node = self.get_node(str(node_id))
        if not node:
            raise ValueError(f"Node {node_id} not found")

        attributes = self._parse_attributes_json(node.attributes)
        attributes = [attr for attr in attributes if attr.key != key]

        attributes_json = json.dumps([attr.model_dump(mode='json') for attr in attributes])
        node.attributes = attributes_json
        node.version = node.version + 1
        self.db.commit()
        self.db.refresh(node)
        return node

    # Private validation methods

    def _validate_node_creation(self, node_data: Dict[str, Any], node_type: NodeType):
        """Validate structure_node creation based on type-specific rules"""
        if node_type == NodeType.LAYER:
            self._validate_layer_creation(node_data)
        elif node_type == NodeType.DOMAIN:
            self._validate_domain_creation(node_data)
        elif node_type == NodeType.TERM:
            self._validate_term_creation(node_data)

    def _validate_node_update(
        self, structure_node: StructureNode, node_data: Dict[str, Any]
    ):
        """Validate structure_node update based on type-specific rules"""
        if structure_node.node_type == NodeType.LAYER:
            self._validate_layer_update(structure_node, node_data)
        elif structure_node.node_type == NodeType.DOMAIN:
            self._validate_domain_update(structure_node, node_data)
        elif structure_node.node_type == NodeType.TERM:
            self._validate_term_update(structure_node, node_data)

    def _validate_layer_creation(self, node_data: Dict[str, Any]):
        """Validate layer creation rules"""
        # Layer titles must be unique globally
        existing = (
            self.db.query(StructureNode)
            .filter(
                StructureNode.node_type == NodeType.LAYER,
                StructureNode.title == node_data["title"],
            )
            .first()
        )

        if existing:
            raise ValueError("Layer title must be unique")

        # Layers should not have parents
        if node_data.get("parent_node_id"):
            raise InvalidHierarchyError("Layers cannot have parent structure_nodes")

    def _validate_layer_update(
        self, structure_node: StructureNode, node_data: Dict[str, Any]
    ):
        """Validate layer update rules"""
        # Check title uniqueness if title is being updated
        if "title" in node_data and node_data["title"] != structure_node.title:
            existing = (
                self.db.query(StructureNode)
                .filter(
                    StructureNode.node_type == NodeType.LAYER,
                    StructureNode.title == node_data["title"],
                    StructureNode.id != structure_node.id,
                )
                .first()
            )

            if existing:
                raise ValueError("Layer title must be unique")

        # Layers should not have parents
        if "parent_node_id" in node_data and node_data["parent_node_id"] is not None:
            raise InvalidHierarchyError("Layers cannot have parent structure_nodes")

    def _validate_domain_creation(self, node_data: Dict[str, Any]):
        """Validate domain creation rules"""
        parent_id = node_data.get("parent_node_id")
        if not parent_id:
            raise InvalidHierarchyError("Domains must have a parent layer")

        # Parent must be a layer
        parent = (
            self.db.query(StructureNode).filter(StructureNode.id == parent_id).first()
        )
        if not parent or parent.node_type != NodeType.LAYER:
            raise InvalidHierarchyError("Domain parent must be a layer")

        # Validate structural predicate ID if provided
        self._validate_structural_predicate_id(node_data.get("structural_predicate_id"))

        # Domain titles must be unique within the layer
        existing = (
            self.db.query(StructureNode)
            .filter(
                StructureNode.node_type == NodeType.DOMAIN,
                StructureNode.parent_node_id == parent_id,
                StructureNode.title == node_data["title"],
            )
            .first()
        )

        if existing:
            raise ValueError("Domain title must be unique within layer")

    def _validate_domain_update(
        self, structure_node: StructureNode, node_data: Dict[str, Any]
    ):
        """Validate domain update rules"""
        parent_id = node_data.get("parent_node_id", structure_node.parent_node_id)

        # Parent validation if changing parent
        if "parent_node_id" in node_data:
            if not parent_id:
                raise InvalidHierarchyError("Domains must have a parent layer")

            parent = (
                self.db.query(StructureNode)
                .filter(StructureNode.id == parent_id)
                .first()
            )
            if not parent or parent.node_type != NodeType.LAYER:
                raise InvalidHierarchyError("Domain parent must be a layer")

        # Validate structural predicate ID if being updated
        if "structural_predicate_id" in node_data:
            self._validate_structural_predicate_id(node_data["structural_predicate_id"])

        # Check title uniqueness within layer if title or parent is changing
        check_title_uniqueness = (
            "title" in node_data and node_data["title"] != structure_node.title
        ) or (
            "parent_node_id" in node_data
            and node_data["parent_node_id"] != structure_node.parent_node_id
        )

        if check_title_uniqueness:
            title = node_data.get("title", structure_node.title)
            existing = (
                self.db.query(StructureNode)
                .filter(
                    StructureNode.node_type == NodeType.DOMAIN,
                    StructureNode.parent_node_id == parent_id,
                    StructureNode.title == title,
                    StructureNode.id != structure_node.id,
                )
                .first()
            )

            if existing:
                raise ValueError("Domain title must be unique within layer")

    def _validate_term_creation(self, node_data: Dict[str, Any]):
        """Validate term creation rules"""
        parent_id = node_data.get("parent_node_id")
        if not parent_id:
            raise InvalidHierarchyError("Terms must have a parent domain or term")

        # Parent must be a domain or term
        parent = (
            self.db.query(StructureNode).filter(StructureNode.id == parent_id).first()
        )
        if not parent or parent.node_type not in [NodeType.DOMAIN, NodeType.TERM]:
            raise InvalidHierarchyError("Term parent must be a domain or term")

        # Get the domain (either direct parent or ancestor)
        domain = self._get_domain_ancestor(parent)
        if not domain:
            raise ValueError("Term must belong to a domain")

        # Term titles must be unique within the domain
        if self._check_title_uniqueness_in_domain(domain.id, node_data["title"]):
            raise ValueError("Term title must be unique within domain")

    def _validate_term_update(
        self, structure_node: StructureNode, node_data: Dict[str, Any]
    ):
        """Validate term update rules"""
        parent_id = node_data.get("parent_node_id", structure_node.parent_node_id)

        # Parent validation if changing parent
        if "parent_node_id" in node_data:
            if not parent_id:
                raise InvalidHierarchyError("Terms must have a parent domain or term")

            parent = (
                self.db.query(StructureNode)
                .filter(StructureNode.id == parent_id)
                .first()
            )
            if not parent or parent.node_type not in [NodeType.DOMAIN, NodeType.TERM]:
                raise InvalidHierarchyError("Term parent must be a domain or term")

        # Get the domain for uniqueness check
        if parent_id:
            parent = (
                self.db.query(StructureNode)
                .filter(StructureNode.id == parent_id)
                .first()
            )
            domain = self._get_domain_ancestor(parent) if parent else None
        else:
            domain = None

        if not domain:
            raise ValueError("Term must belong to a domain")

        # Check title uniqueness within domain if title or parent is changing
        check_title_uniqueness = (
            "title" in node_data and node_data["title"] != structure_node.title
        ) or (
            "parent_node_id" in node_data
            and node_data["parent_node_id"] != structure_node.parent_node_id
        )

        if check_title_uniqueness:
            title = node_data.get("title", structure_node.title)
            if self._check_title_uniqueness_in_domain(
                domain.id, title, exclude_id=structure_node.id
            ):
                raise ValueError("Term title must be unique within domain")

    def _validate_no_circular_reference(
        self, node_id: Optional[str], parent_id: Optional[str]
    ):
        """
        Validate no circular references.

        For now, this is a simple implementation. The Graph Service integration
        can be enhanced later for more sophisticated cycle detection.
        """
        if not parent_id or not node_id:
            return

        # Check if parent_id is the same as node_id
        if node_id == parent_id:
            raise CircularReferenceError("StructureNode cannot be its own parent")

        # Check if parent_id is a descendant of node_id
        ancestors = self.get_node_ancestors(parent_id)
        ancestor_ids = [ancestor.id for ancestor in ancestors]

        if node_id in ancestor_ids:
            raise CircularReferenceError("Operation would create circular reference")

    def _get_domain_ancestor(
        self, structure_node: StructureNode
    ) -> Optional[StructureNode]:
        """Get the domain ancestor of a structure_node"""
        current = structure_node
        while current:
            if current.node_type == NodeType.DOMAIN:
                return current
            if current.parent_node_id:
                current = (
                    self.db.query(StructureNode)
                    .filter(StructureNode.id == current.parent_node_id)
                    .first()
                )
            else:
                break
        return None

    def _check_title_uniqueness_in_domain(
        self, domain_id: str, title: str, exclude_id: Optional[str] = None
    ) -> bool:
        """
        Check if title is unique within domain.

        Args:
            domain_id: Domain ID to check within
            title: Title to check for uniqueness
            exclude_id: Optional structure_node ID to exclude from check (for updates)

        Returns:
            True if title already exists (not unique), False if unique
        """
        # Get all terms in the domain tree
        domain_terms = self._get_all_terms_in_domain(domain_id)

        # Check for title conflicts
        query = self.db.query(StructureNode).filter(
            StructureNode.node_type == NodeType.TERM,
            StructureNode.id.in_(domain_terms),
            StructureNode.title == title,
        )

        if exclude_id:
            query = query.filter(StructureNode.id != exclude_id)

        existing = query.first()
        return existing is not None

    def _get_all_terms_in_domain(self, domain_id: str) -> List[str]:
        """
        Get all term IDs that belong to a domain (including terms under other terms).

        Args:
            domain_id: Domain ID

        Returns:
            List of term IDs in the domain
        """
        # Get direct terms under the domain
        direct_terms = (
            self.db.query(StructureNode.id)
            .filter(
                StructureNode.node_type == NodeType.TERM,
                StructureNode.parent_node_id == domain_id,
            )
            .all()
        )

        all_term_ids = [term[0] for term in direct_terms]

        # Recursively get terms under terms
        for term_id in all_term_ids[
            :
        ]:  # Copy list to avoid modification during iteration
            child_terms = self._get_all_terms_under_term(term_id)
            all_term_ids.extend(child_terms)

        return all_term_ids

    def _get_all_terms_under_term(self, term_id: str) -> List[str]:
        """
        Recursively get all term IDs under a given term.

        Args:
            term_id: Parent term ID

        Returns:
            List of descendant term IDs
        """
        child_terms = (
            self.db.query(StructureNode.id)
            .filter(
                StructureNode.node_type == NodeType.TERM,
                StructureNode.parent_node_id == term_id,
            )
            .all()
        )

        all_child_ids = [term[0] for term in child_terms]

        # Recursively get children of children
        for child_id in all_child_ids[:]:
            grandchild_terms = self._get_all_terms_under_term(child_id)
            all_child_ids.extend(grandchild_terms)

        return all_child_ids

    def _node_to_dict(self, structure_node: StructureNode) -> Dict[str, Any]:
        """Convert a StructureNode instance to a dictionary"""
        return {
            "id": structure_node.id,
            "node_type": (
                structure_node.node_type.value
                if isinstance(structure_node.node_type, NodeType)
                else structure_node.node_type
            ),
            "parent_node_id": structure_node.parent_node_id,
            "title": structure_node.title,
            "definition": structure_node.definition,
            "structural_predicate_id": structure_node.structural_predicate_id,
            "created_at": (
                structure_node.created_at.isoformat()
                if structure_node.created_at
                else None
            ),
            "version": structure_node.version,
            "last_modified": (
                structure_node.last_modified.isoformat()
                if structure_node.last_modified
                else None
            ),
        }

    def _fire_node_event(
        self,
        event_type: str,
        node_type: str,
        old_data: Optional[Dict[str, Any]],
        new_data: Optional[Dict[str, Any]],
    ):
        """
        Fire a structure_node event manually (if needed).

        Note: Database triggers should handle this automatically, but this method
        is available for manual event firing if required.
        """
        try:
            event = ChangeEvent(
                event_type=event_type,
                record_type=node_type,  # Map node_type to record_type
                record_id=None,  # This would need to be set based on which node is being affected
                old_data=old_data,
                new_data=new_data,
            )

            self.db.add(event)
            self.db.commit()

        except Exception as e:
            logger.warning(f"Failed to fire structure_node event: {e}")

    def _get_all_descendants(self, node_id: str) -> List[StructureNode]:
        """
        Get all descendant structure_nodes recursively.

        Args:
            node_id: Parent structure_node ID

        Returns:
            List of all descendant StructureNode instances
        """
        all_descendants = []

        # Get direct children
        direct_children = (
            self.db.query(StructureNode)
            .filter(StructureNode.parent_node_id == node_id)
            .all()
        )

        for child in direct_children:
            # Add child to the list
            all_descendants.append(child)
            # Recursively add child's descendants
            all_descendants.extend(self._get_all_descendants(child.id))

        return all_descendants

    def move_nodes(
        self,
        node_ids: List[str],
        target_parent_id: Optional[str] = None,
        move_children: bool = True,
        handle_conflicts: str = "warn",
    ) -> Dict[str, Any]:
        """
        Move structure_nodes to a new parent with automatic type conversion.

        IMPORTANT: When a node is moved to a parent with a different type constraint,
        the node AND ALL ITS CHILDREN are automatically converted to the appropriate type.
        This conversion happens regardless of the move_children parameter.

        Args:
            node_ids: List of structure_node IDs to move
            target_parent_id: Target parent structure_node ID (None for root level)
            move_children: If True, include all descendants in the response.
                          Note: Children are ALWAYS type-converted, this only controls
                          whether they're included in the response.
            handle_conflicts: How to handle title conflicts ("warn", "rename", "error")

        Returns:
            Dictionary containing moved structure_nodes, updated children, warnings, and errors

        Raises:
            ValueError: If validation fails
        """
        logger.info(
            f"Moving {len(node_ids)} structure_nodes to parent {target_parent_id}"
        )

        moved_nodes = []
        updated_children = []
        converted_nodes = []
        warnings = []
        errors = []

        try:
            # Start transaction
            self.db.begin()

            # Validate target parent exists (if specified)
            target_parent = None
            if target_parent_id:
                target_parent = self.get_node(target_parent_id)
                if not target_parent:
                    raise ValueError("Target parent structure_node does not exist")

            # Process each structure_node
            for node_id in node_ids:
                try:
                    result = self._move_single_node(
                        node_id,
                        target_parent_id,
                        target_parent,
                        move_children,
                        handle_conflicts,
                    )

                    moved_nodes.append(result["moved_node"])
                    updated_children.extend(result["updated_children"])
                    converted_nodes.extend(result["converted_nodes"])
                    warnings.extend(result["warnings"])

                except ValueError as e:
                    errors.append(f"Failed to move structure_node {node_id}: {str(e)}")
                    logger.warning(f"Failed to move structure_node {node_id}: {e}")

            # Commit transaction
            self.db.commit()
            logger.info(f"Successfully moved {len(moved_nodes)} structure_nodes")

            return {
                "moved_nodes": moved_nodes,
                "updated_children": updated_children,
                "converted_nodes": converted_nodes,
                "warnings": warnings,
                "errors": errors,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Move operation failed: {e}")
            raise ValueError(f"Move operation failed: {str(e)}")

    def _move_single_node(
        self,
        node_id: str,
        target_parent_id: Optional[str],
        target_parent: Optional[StructureNode],
        move_children: bool,
        handle_conflicts: str,
    ) -> Dict[str, Any]:
        """
        Move a single structure_node with automatic type conversion.

        Args:
            node_id: StructureNode ID to move
            target_parent_id: Target parent structure_node ID
            target_parent: Target parent StructureNode instance (if any)
            move_children: Whether to move children
            handle_conflicts: How to handle conflicts

        Returns:
            Dictionary with moved structure_node, updated children, converted nodes, and warnings
        """
        warnings = []
        updated_children = []
        converted_nodes = []  # NEW: Track type conversions

        # Get the structure_node to move
        structure_node = self.get_node(node_id)
        if not structure_node:
            raise NotFoundError("StructureNode", node_id)

        # NEW: Infer target type from parent
        target_type = self._infer_node_type_from_parent(target_parent)

        # NEW: Validate with target type (pass as parameter instead of mutating node)
        self._validate_node_move(structure_node, target_parent, target_type=target_type)

        # Check for title conflicts with NEW type
        conflict_warning = self._check_move_conflicts_with_type(
            structure_node, target_parent_id, target_type, handle_conflicts
        )
        if conflict_warning:
            warnings.append(conflict_warning)

        # NEW: Convert node type and all children recursively BEFORE updating parent
        # This ensures database consistency - if conversion fails, parent isn't changed
        self._convert_node_type_and_children(structure_node, target_type, converted_nodes)

        # Update the structure_node's parent AFTER successful conversion
        old_parent_id = structure_node.parent_node_id
        structure_node.parent_node_id = target_parent_id

        # Save changes
        self.db.add(structure_node)
        self.db.flush()  # Ensure changes are visible within transaction

        # Move children if requested
        # NOTE: Children are ALWAYS type-converted along with their parent.
        # This flag only controls whether they're included in the response.
        if move_children:
            children = self._get_all_descendants(node_id)
            for child in children:
                # Children have already been type-converted, just track them for response
                updated_children.append(child)

        logger.info(
            f"Moved structure_node {node_id} from parent {old_parent_id} to {target_parent_id}, "
            f"converted {len(converted_nodes)} nodes"
        )

        return {
            "moved_node": structure_node,
            "updated_children": updated_children,
            "converted_nodes": converted_nodes,  # NEW
            "warnings": warnings,
        }

    def _validate_node_move(
        self,
        structure_node: StructureNode,
        target_parent: Optional[StructureNode],
        target_type: Optional[NodeType] = None
    ):
        """
        Validate that a structure_node move is allowed based on type hierarchy rules.

        Args:
            structure_node: StructureNode to move
            target_parent: Target parent StructureNode (None for root)
            target_type: The type the node will be converted to (if None, use current type)

        Raises:
            ValueError: If the move violates hierarchy rules
        """
        # Use target_type if provided, otherwise use current node type
        node_type = target_type if target_type else structure_node.node_type

        # Layer moves
        if node_type == NodeType.LAYER:
            if target_parent is not None:
                raise InvalidHierarchyError("Layers must be at root level (no parent)")

        # Domain moves
        elif node_type == NodeType.DOMAIN:
            if target_parent is None:
                raise InvalidHierarchyError("Domains must have a parent layer")
            if target_parent.node_type != NodeType.LAYER:
                raise InvalidHierarchyError("Domains can only be placed under layers")

        # Term moves
        elif node_type == NodeType.TERM:
            if target_parent is None:
                raise InvalidHierarchyError("Terms must have a parent")
            if target_parent.node_type not in [NodeType.DOMAIN, NodeType.TERM]:
                raise InvalidHierarchyError("Terms can only be placed under domains or other terms")

        # Prevent circular references
        if target_parent and self._would_create_cycle(
            structure_node.id, target_parent.id
        ):
            raise CircularReferenceError("Move would create circular reference")

    def _infer_node_type_from_parent(
        self,
        target_parent: Optional[StructureNode]
    ) -> NodeType:
        """
        Infer the appropriate node type based on the target parent.

        Args:
            target_parent: Target parent node (None for root)

        Returns:
            NodeType appropriate for the parent level
        """
        if target_parent is None:
            return NodeType.LAYER
        elif target_parent.node_type == NodeType.LAYER:
            return NodeType.DOMAIN
        elif target_parent.node_type in [NodeType.DOMAIN, NodeType.TERM]:
            return NodeType.TERM
        else:
            raise ValueError(f"Invalid parent type: {target_parent.node_type}")

    def _convert_node_type_and_children(
        self,
        node: StructureNode,
        new_type: NodeType,
        converted_nodes: List[StructureNode]
    ) -> None:
        """
        Recursively convert a node and all its descendants to appropriate types.

        Args:
            node: Node to convert
            new_type: Target type for this node
            converted_nodes: List to accumulate converted nodes for response
        """
        old_type = node.node_type

        # Only convert if type actually changes
        if old_type != new_type:
            logger.info(f"Converting node {node.id} from {old_type} to {new_type}")
            node.node_type = new_type
            converted_nodes.append(node)
            self.db.add(node)
            # Database trigger will generate 'update-type' event automatically

        # Recursively convert all direct children
        children = self.db.query(StructureNode).filter(
            StructureNode.parent_node_id == str(node.id)
        ).all()

        for child in children:
            # Determine child's new type based on parent's new type
            if new_type == NodeType.LAYER:
                child_new_type = NodeType.DOMAIN
            elif new_type in [NodeType.DOMAIN, NodeType.TERM]:
                child_new_type = NodeType.TERM
            else:
                continue

            self._convert_node_type_and_children(child, child_new_type, converted_nodes)

    def _check_move_conflicts(
        self,
        structure_node: StructureNode,
        target_parent_id: Optional[str],
        handle_conflicts: str,
    ) -> Optional[str]:
        """
        Check for title conflicts when moving a structure_node.

        Args:
            structure_node: StructureNode being moved
            target_parent_id: Target parent ID
            handle_conflicts: How to handle conflicts

        Returns:
            Warning message if conflict found, None otherwise

        Raises:
            ValueError: If handle_conflicts="error" and conflict found
        """
        # Check for existing structure_nodes with same title under target parent
        existing = (
            self.db.query(StructureNode)
            .filter(
                and_(
                    StructureNode.parent_node_id == target_parent_id,
                    StructureNode.title == structure_node.title,
                    StructureNode.node_type == structure_node.node_type,
                    StructureNode.id
                    != structure_node.id,  # Exclude the structure_node being moved
                )
            )
            .first()
        )

        if existing:
            conflict_msg = f"StructureNode with title '{structure_node.title}' already exists in target location"

            if handle_conflicts == "error":
                raise ValueError(conflict_msg)
            elif handle_conflicts == "rename":
                # Generate unique title
                counter = 1
                new_title = f"{structure_node.title} ({counter})"
                while (
                    self.db.query(StructureNode)
                    .filter(
                        and_(
                            StructureNode.parent_node_id == target_parent_id,
                            StructureNode.title == new_title,
                            StructureNode.node_type == structure_node.node_type,
                        )
                    )
                    .first()
                ):
                    counter += 1
                    new_title = f"{structure_node.title} ({counter})"

                structure_node.title = new_title
                return f"Renamed structure_node to '{new_title}' to avoid conflict"
            else:  # handle_conflicts == "warn"
                return conflict_msg

        return None

    def _check_move_conflicts_with_type(
        self,
        structure_node: StructureNode,
        target_parent_id: Optional[str],
        target_type: NodeType,
        handle_conflicts: str,
    ) -> Optional[str]:
        """
        Check for title conflicts using the TARGET type's uniqueness rules.

        Args:
            structure_node: Node being moved
            target_parent_id: Target parent ID
            target_type: Type the node will become
            handle_conflicts: How to handle conflicts

        Returns:
            Warning message if conflict found, None otherwise

        Raises:
            ValueError: If handle_conflicts="error" and conflict found
        """
        # Check uniqueness based on TARGET type
        if target_type == NodeType.LAYER:
            # Layers must be globally unique
            existing = (
                self.db.query(StructureNode)
                .filter(
                    StructureNode.title == structure_node.title,
                    StructureNode.node_type == NodeType.LAYER,
                    StructureNode.id != structure_node.id,
                )
                .first()
            )
        elif target_type == NodeType.DOMAIN:
            # Domains must be unique within layer
            existing = (
                self.db.query(StructureNode)
                .filter(
                    StructureNode.title == structure_node.title,
                    StructureNode.node_type == NodeType.DOMAIN,
                    StructureNode.parent_node_id == target_parent_id,
                    StructureNode.id != structure_node.id,
                )
                .first()
            )
        elif target_type == NodeType.TERM:
            # Terms must be unique within parent (domain or term)
            existing = (
                self.db.query(StructureNode)
                .filter(
                    StructureNode.title == structure_node.title,
                    StructureNode.node_type == NodeType.TERM,
                    StructureNode.parent_node_id == target_parent_id,
                    StructureNode.id != structure_node.id,
                )
                .first()
            )
        else:
            existing = None

        if existing:
            conflict_msg = (
                f"Node with title '{structure_node.title}' already exists "
                f"at target location as {target_type.value}"
            )

            if handle_conflicts == "error":
                raise ValueError(conflict_msg)
            elif handle_conflicts == "rename":
                # Generate unique title with TARGET type
                counter = 1
                new_title = f"{structure_node.title} ({counter})"
                while self._title_exists_at_target(new_title, target_parent_id, target_type, structure_node.id):
                    counter += 1
                    new_title = f"{structure_node.title} ({counter})"

                structure_node.title = new_title
                return f"Renamed node to '{new_title}' to avoid conflict with existing {target_type}"
            else:  # handle_conflicts == "warn"
                return conflict_msg

        return None

    def _title_exists_at_target(
        self, title: str, target_parent_id: Optional[str], target_type: NodeType, exclude_id: str
    ) -> bool:
        """Helper to check if a title exists at the target location."""
        if target_type == NodeType.LAYER:
            return self.db.query(StructureNode).filter(
                StructureNode.title == title,
                StructureNode.node_type == NodeType.LAYER,
                StructureNode.id != exclude_id,
            ).first() is not None
        elif target_type == NodeType.DOMAIN:
            return self.db.query(StructureNode).filter(
                StructureNode.title == title,
                StructureNode.node_type == NodeType.DOMAIN,
                StructureNode.parent_node_id == target_parent_id,
                StructureNode.id != exclude_id,
            ).first() is not None
        elif target_type == NodeType.TERM:
            return self.db.query(StructureNode).filter(
                StructureNode.title == title,
                StructureNode.node_type == NodeType.TERM,
                StructureNode.parent_node_id == target_parent_id,
                StructureNode.id != exclude_id,
            ).first() is not None
        return False

    def _would_create_cycle(self, node_id: str, target_parent_id: str) -> bool:
        """
        Check if moving a structure_node would create a circular reference.

        Args:
            node_id: StructureNode ID being moved
            target_parent_id: Target parent ID

        Returns:
            True if move would create a cycle, False otherwise
        """
        # If target_parent_id is in the descendants of node_id, it would create a cycle
        descendants = self._get_all_descendants(node_id)
        return any(descendant.id == target_parent_id for descendant in descendants)

    def _validate_structural_predicate_id(self, structural_predicate_id: str):
        """
        Validate that the structural predicate ID references an existing predicate.

        Args:
            structural_predicate_id: The predicate ID to validate

        Raises:
            ValueError: If predicate ID is invalid or doesn't exist
        """
        if structural_predicate_id:
            predicate = (
                self.db.query(Predicate)
                .filter(Predicate.id == structural_predicate_id)
                .first()
            )

            if not predicate:
                raise ValueError(
                    f"Invalid structural_predicate_id: predicate '{structural_predicate_id}' does not exist"
                )
