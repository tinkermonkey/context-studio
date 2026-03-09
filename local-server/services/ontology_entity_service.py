# mypy: ignore-errors
"""
Ontology Entity Service - Centralized business logic for ontology_entity operations

This service implements the business logic for the normalized ontology_entity structure,
handling type-specific validations and constraints for layers, domains, and terms.
"""

import json
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import ValidationError as PydanticValidationError

from database.models import OntologyEntity, ChangeEvent, PropertyDefinition
from api.models.structure_nodes import StructureNodeAttribute, ResolvedAttribute
from database.enums import NodeType
from graph.graph_service import GraphService
from embeddings.generate_embeddings import generate_embedding
from services.change_event_handler import ChangeEventHandler
from services.version_manager import VersionManager, ChangeState
from services.working_tree_manager import WorkingTreeManager
from services.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError, CircularReferenceError, InvalidHierarchyError
from utils.logger import get_logger

logger = get_logger(__name__)


class OntologyEntityService:
    """Centralized business logic for ontology_entity operations"""

    def __init__(self, db: Session, graph_service: Optional[GraphService] = None,
                 version_manager: Optional[VersionManager] = None,
                 working_tree_manager: Optional[WorkingTreeManager] = None):
        """
        Initialize the OntologyEntityService.

        Args:
            db: SQLAlchemy database session
            graph_service: Optional graph service for graph operations
            version_manager: Optional version manager for versioning
            working_tree_manager: Optional working tree manager for state tracking
        """
        self.db = db
        self.graph_service = graph_service
        self.version_manager = version_manager
        self.working_tree_manager = working_tree_manager
        self.event_handler = ChangeEventHandler(db)
        logger.debug("OntologyEntityService initialized")

    def create_entity(self, entity_data: Dict[str, Any]) -> OntologyEntity:
        """
        Create a new ontology_entity with type-specific validation.

        Args:
            entity_data: Dictionary containing ontology_entity data

        Returns:
            Created OntologyEntity instance

        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Creating ontology_entity with type: {entity_data.get('node_type')}")

        # Validate required fields
        if "node_type" not in entity_data:
            raise ValueError("node_type is required")
        if "title" not in entity_data:
            raise ValueError("title is required")

        node_type = NodeType(entity_data["node_type"])

        # Validate structural predicate ID if provided
        self._validate_entity_creation(entity_data, node_type)  # type: ignore

        # Check for circular references if parent is specified
        if entity_data.get("parent_entity_id"):
            self._validate_no_circular_reference(None, entity_data["parent_entity_id"])

        # Generate embeddings
        title_embedding = None
        definition_embedding = None

        if entity_data.get("title"):
            try:
                title_embedding = generate_embedding(entity_data["title"])
            except Exception as e:
                logger.error(
                    f"Failed to generate title embedding for '{entity_data['title']}': {e}",
                    exc_info=True
                )
                raise ValidationError(
                    f"Cannot create entity: embedding generation failed. "
                    f"This may indicate LLM service issues. Please try again or contact support. "
                    f"Error: {str(e)}"
                )

        if entity_data.get("definition"):
            try:
                definition_embedding = generate_embedding(entity_data["definition"])
            except Exception as e:
                logger.error(
                    f"Failed to generate definition embedding: {e}",
                    exc_info=True
                )
                raise ValidationError(
                    f"Cannot create entity: definition embedding generation failed. "
                    f"Error: {str(e)}"
                )

        # Create ontology_entity
        ontology_entity = OntologyEntity(
            node_type=node_type,
            parent_entity_id=entity_data.get("parent_entity_id"),
            title=entity_data["title"],
            definition=entity_data.get("definition"),
            structural_predicate_id=entity_data.get("structural_predicate_id"),
            title_embedding=title_embedding,
            definition_embedding=definition_embedding,
        )

        try:
            self.db.add(ontology_entity)
            self.db.commit()
            self.db.refresh(ontology_entity)

            # Verify the ID was properly generated after refresh
            if not ontology_entity.id or not isinstance(ontology_entity.id, str):
                logger.error(
                    f"Invalid ID after db.refresh(): {repr(ontology_entity.id)} "
                    f"(type: {type(ontology_entity.id).__name__})"
                )
                raise ValueError(
                    f"Database failed to generate valid ID for ontology_entity. "
                    f"Got: {repr(ontology_entity.id)} (type: {type(ontology_entity.id).__name__})"
                )

            logger.info(
                f"Successfully created ontology_entity: {ontology_entity.id} ({ontology_entity.node_type})"
            )

            # Initialize version management and working tree state immediately
            if self.version_manager and self.working_tree_manager:
                try:
                    # Convert entity to dict for version content
                    entity_dict = self._entity_to_dict(ontology_entity)

                    # Create initial version
                    # Note: Use 'structure_node' for backward compatibility with version manager and working tree
                    version = self.version_manager.create_version(
                        entity_type='structure_node',
                        entity_id=str(ontology_entity.id),
                        content=entity_dict,
                        author_id='system',  # System represents automatic creation during entity initialization
                        state=ChangeState.WORKING
                    )

                    # Initialize entity in working tree
                    # Note: Use 'structure_node' for backward compatibility with version manager and working tree
                    self.working_tree_manager.initialize_entity_in_working_tree(
                        entity_type='structure_node',
                        entity_id=str(ontology_entity.id),
                        initial_version_id=version.id
                    )

                    logger.info(f"Initialized version management for ontology_entity: {ontology_entity.id}")

                except Exception as e:
                    logger.error(f"Failed to initialize version management: {e}", exc_info=True)
                    self.db.rollback()
                    raise ValidationError(
                        f"Cannot create entity: version management initialization failed. "
                        f"This indicates a database or configuration issue. Error: {str(e)}"
                    )

            # Fire ontology_entity created event using new ChangeEventHandler
            entity_dict = self._entity_to_dict(ontology_entity)
            from database.enums import RecordType

            self.event_handler.fire_created_event(
                RecordType.ONTOLOGY_ENTITY, str(ontology_entity.id), entity_dict
            )

            return ontology_entity

        except ServiceError:
            # Re-raise service errors (ValidationError, etc.) without wrapping
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create ontology_entity: {e}")
            raise ValueError(f"Failed to create ontology_entity: {e}")

    def update_entity(self, entity_id: str, entity_data: Dict[str, Any]) -> OntologyEntity:
        """
        Update an existing ontology_entity with type-specific validation.

        Args:
            entity_id: ID of the ontology_entity to update
            entity_data: Dictionary containing updated ontology_entity data

        Returns:
            Updated OntologyEntity instance

        Raises:
            ValueError: If validation fails or ontology_entity not found
        """
        logger.info(f"Updating ontology_entity: {entity_id}")

        # Get existing ontology_entity
        ontology_entity = (
            self.db.query(OntologyEntity).filter(OntologyEntity.id == entity_id).first()
        )
        if not ontology_entity:
            raise NotFoundError("OntologyEntity", entity_id)

        # Store old data for validation and events
        old_entity_data = self._entity_to_dict(ontology_entity)

        # Validate structural predicate ID if being updated
        if "structural_predicate_id" in entity_data:
            self._validate_structural_predicate_id(entity_data["structural_predicate_id"])

        # Validate updates based on ontology_entity type
        self._validate_entity_update(ontology_entity, entity_data)

        # Check for circular references if parent is being changed
        if (
            "parent_entity_id" in entity_data
            and entity_data["parent_entity_id"] != ontology_entity.parent_entity_id
        ):
            self._validate_no_circular_reference(entity_id, entity_data["parent_entity_id"])

        # Update fields
        if "title" in entity_data:
            ontology_entity.title = entity_data["title"]
            # Regenerate title embedding
            try:
                ontology_entity.title_embedding = generate_embedding(entity_data["title"])
            except Exception as e:
                logger.error(
                    f"Failed to generate title embedding for '{entity_data['title']}': {e}",
                    exc_info=True
                )
                raise ValidationError(
                    f"Cannot update entity: title embedding generation failed. "
                    f"This may indicate LLM service issues. Please try again or contact support. "
                    f"Error: {str(e)}"
                )

        if "definition" in entity_data:
            ontology_entity.definition = entity_data["definition"]
            # Regenerate definition embedding
            try:
                if entity_data["definition"]:
                    ontology_entity.definition_embedding = generate_embedding(
                        entity_data["definition"]
                    )
                else:
                    ontology_entity.definition_embedding = None  # type: ignore
            except Exception as e:
                logger.error(
                    f"Failed to generate definition embedding: {e}",
                    exc_info=True
                )
                raise ValidationError(
                    f"Cannot update entity: definition embedding generation failed. "
                    f"This may indicate LLM service issues. Please try again or contact support. "
                    f"Error: {str(e)}"
                )

        if "parent_entity_id" in entity_data:
            ontology_entity.parent_entity_id = entity_data["parent_entity_id"]

        if "structural_predicate_id" in entity_data:
            ontology_entity.structural_predicate_id = entity_data[
                "structural_predicate_id"
            ]

        # Update version
        ontology_entity.version = ontology_entity.version + 1  # type: ignore

        try:
            self.db.commit()
            self.db.refresh(ontology_entity)

            logger.info(f"Successfully updated ontology_entity: {ontology_entity.id}")

            # Fire ontology_entity updated event using new ChangeEventHandler
            new_entity_data = self._entity_to_dict(ontology_entity)
            from database.enums import RecordType

            self.event_handler.fire_updated_event(
                RecordType.ONTOLOGY_ENTITY,
                str(ontology_entity.id),
                old_entity_data,
                new_entity_data,
            )

            return ontology_entity

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update ontology_entity: {e}")
            raise ValueError(f"Failed to update ontology_entity: {e}")

    def delete_entity(self, entity_id: str) -> bool:
        """
        Delete an ontology_entity and its children (cascade delete).

        Args:
            entity_id: ID of the ontology_entity to delete

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If ontology_entity not found
        """
        logger.info(f"Deleting ontology_entity: {entity_id}")

        ontology_entity = (
            self.db.query(OntologyEntity).filter(OntologyEntity.id == entity_id).first()
        )
        if not ontology_entity:
            raise NotFoundError("OntologyEntity", entity_id)

        # Store ontology_entity data for event before deletion
        entity_data = self._entity_to_dict(ontology_entity)

        # Get all descendant ontology_entities recursively
        all_descendants = self._get_all_descendants(entity_id)
        total_children = len(all_descendants)

        try:
            # Delete all descendants first (bottom-up)
            for descendant in reversed(all_descendants):
                self.db.delete(descendant)

            # Then delete the ontology_entity itself
            self.db.delete(ontology_entity)
            self.db.commit()

            logger.info(
                f"Successfully deleted ontology_entity {entity_id} and {total_children} children"
            )

            # Fire ontology_entity deleted event using new ChangeEventHandler
            from database.enums import RecordType

            self.event_handler.fire_deleted_event(
                RecordType.ONTOLOGY_ENTITY, entity_id, entity_data
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete ontology_entity: {e}")
            raise ValueError(f"Failed to delete ontology_entity: {e}")

    def get_entity(self, entity_id: str) -> Optional[OntologyEntity]:
        """
        Get an ontology_entity by ID.

        Args:
            entity_id: ID of the ontology_entity to retrieve

        Returns:
            OntologyEntity instance or None if not found
        """
        return self.db.query(OntologyEntity).filter(OntologyEntity.id == entity_id).first()

    def list_entities(
        self,
        node_type: Optional[NodeType] = None,
        parent_entity_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[OntologyEntity]:
        """
        List ontology_entities with optional filtering.

        Args:
            node_type: Optional ontology_entity type to filter by
            parent_entity_id: Optional parent ontology_entity ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of OntologyEntity instances
        """
        # Defer expensive vector columns for list operations to improve performance
        from sqlalchemy.orm import defer
        import time
        from utils.logger import get_logger

        logger = get_logger(__name__)
        start_time = time.time()

        query = self.db.query(OntologyEntity).options(
            defer(OntologyEntity.title_embedding),  # type: ignore
            defer(OntologyEntity.definition_embedding)  # type: ignore
        )

        if node_type:
            query = query.filter(OntologyEntity.node_type == node_type)

        if parent_entity_id:
            query = query.filter(OntologyEntity.parent_entity_id == parent_entity_id)

        query = query.order_by(OntologyEntity.title).offset(skip).limit(limit)

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
                f"Query params: node_type={node_type}, parent_entity_id={parent_entity_id}, skip={skip}, limit={limit}"
            )
            raise ValueError(
                f"Database query failed: expected list, got {type(result).__name__}. "
                f"This indicates a database connection or ORM issue."
            )

        result_length = len(result)
        logger.debug(f"Query execution time: {execution_time*1000:.2f}ms for {result_length} entities (skip={skip})")

        return result

    def count_entities(
        self, node_type: Optional[NodeType] = None, parent_entity_id: Optional[str] = None
    ) -> int:
        """
        Count ontology_entities with optional filtering.

        Args:
            node_type: Optional ontology_entity type to filter by
            parent_entity_id: Optional parent ontology_entity ID to filter by

        Returns:
            Count of matching ontology_entities
        """
        query = self.db.query(OntologyEntity)

        if node_type:
            query = query.filter(OntologyEntity.node_type == node_type)

        if parent_entity_id:
            query = query.filter(OntologyEntity.parent_entity_id == parent_entity_id)

        return query.count()

    def get_entities(
        self,
        node_type: Optional[NodeType] = None,
        parent_entity_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[OntologyEntity]:
        """
        Get ontology_entities with optional filtering and pagination.

        Args:
            node_type: Optional ontology_entity type to filter by
            parent_entity_id: Optional parent ontology_entity ID to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of matching ontology_entities
        """
        query = self.db.query(OntologyEntity)

        if node_type:
            query = query.filter(OntologyEntity.node_type == node_type)

        if parent_entity_id:
            query = query.filter(OntologyEntity.parent_entity_id == parent_entity_id)

        query = query.order_by(OntologyEntity.title)

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_entity_children(
        self, entity_id: str, recursive: bool = False
    ) -> List[OntologyEntity]:
        """
        Get children of an ontology_entity.

        Args:
            entity_id: Parent ontology_entity ID
            recursive: Whether to get all descendants or just direct children

        Returns:
            List of child OntologyEntity instances
        """
        if not recursive:
            return (
                self.db.query(OntologyEntity)
                .filter(OntologyEntity.parent_entity_id == entity_id)
                .order_by(OntologyEntity.title)
                .all()
            )

        # For recursive, we need to traverse the tree
        all_children = []
        direct_children = (
            self.db.query(OntologyEntity)
            .filter(OntologyEntity.parent_entity_id == entity_id)
            .all()
        )

        for child in direct_children:
            all_children.append(child)
            all_children.extend(self.get_entity_children(child.id, recursive=True))  # type: ignore

        return all_children

    def get_entity_ancestors(self, entity_id: str) -> List[OntologyEntity]:
        """
        Get all ancestors of an ontology_entity (up to root).

        Args:
            entity_id: OntologyEntity ID to get ancestors for

        Returns:
            List of ancestor OntologyEntity instances (from immediate parent to root)
        """
        ancestors = []
        current_entity = self.get_entity(entity_id)

        while current_entity and current_entity.parent_entity_id:
            parent = self.get_entity(current_entity.parent_entity_id)  # type: ignore
            if parent:
                ancestors.append(parent)
                current_entity = parent
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
            raise ValueError(f"Entity has corrupted attribute data: {str(e)}")

        try:
            return [StructureNodeAttribute(**attr) for attr in data]
        except (TypeError, KeyError, ValueError, PydanticValidationError) as e:
            logger.error(f"Invalid attribute structure: {e}", exc_info=True)
            raise ValueError(f"Entity attributes are invalid: {str(e)}")

    def set_entity_attributes(self, entity_id: UUID, attributes: List[StructureNodeAttribute], expected_version: Optional[int] = None) -> OntologyEntity:
        """
        Set local attributes on an entity, replacing existing attributes.

        Implements optimistic locking to prevent lost updates in concurrent scenarios.
        If expected_version is provided, the update will only succeed if the current
        version matches the expected version.

        Args:
            entity_id: ID of the ontology entity
            attributes: List of StructureNodeAttribute instances to set
            expected_version: Optional version number for optimistic locking. If provided,
                            raises ConflictError if current version doesn't match.

        Returns:
            Updated OntologyEntity instance

        Raises:
            ValueError: If entity not found
            ConflictError: If expected_version is provided and doesn't match current version
        """
        entity = self.get_entity(str(entity_id))
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        # Optimistic locking check
        if expected_version is not None and entity.version != expected_version:
            raise ConflictError(
                f"Entity was modified by another user. "
                f"Please refresh and try again. "
                f"(Expected version {expected_version}, current version {entity.version})"
            )

        # Serialize to JSON
        attributes_json = json.dumps([attr.model_dump(mode='json') for attr in attributes])
        entity.attributes = attributes_json  # type: ignore
        entity.version = entity.version + 1  # type: ignore
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def get_local_attributes(self, entity_id: UUID) -> List[StructureNodeAttribute]:
        """
        Get only the entity's own attributes (not inherited).

        Args:
            entity_id: ID of the ontology entity

        Returns:
            List of StructureNodeAttribute instances for this entity only

        Raises:
            ValueError: If entity not found, or if attribute data is corrupted or invalid
        """
        entity = self.get_entity(str(entity_id))
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")
        return self._parse_attributes_json(entity.attributes)  # type: ignore

    def resolve_entity_attributes(self, entity_id: UUID) -> List[ResolvedAttribute]:
        """
        Walk ancestor chain and return merged attributes with inheritance information.

        Child values override parent values for matching keys. The chain is walked
        from most distant ancestor to target entity, with child values taking precedence.

        Args:
            entity_id: ID of the ontology entity

        Returns:
            List of ResolvedAttribute instances with inherited flags and source entity IDs

        Raises:
            ValueError: If entity not found, or if attribute data is corrupted or invalid
        """
        entity = self.get_entity(str(entity_id))
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        # Get all ancestors using existing method (no depth limit)
        ancestors = self.get_entity_ancestors(str(entity_id))

        # Build attribute map from most distant ancestor to target entity
        attribute_map = {}
        for ancestor in reversed(ancestors):  # Most distant first
            ancestor_attrs = self._parse_attributes_json(ancestor.attributes)  # type: ignore
            for attr in ancestor_attrs:
                attribute_map[attr.key] = ResolvedAttribute(
                    key=attr.key,
                    title=attr.title,
                    value=attr.value,
                    value_type=attr.value_type,
                    inherited=(ancestor.id != entity.id),  # type: ignore
                    source_node_id=UUID(ancestor.id)  # type: ignore
                )

        # Add local attributes last (override inherited)
        local_attrs = self._parse_attributes_json(entity.attributes)  # type: ignore
        for attr in local_attrs:
            attribute_map[attr.key] = ResolvedAttribute(
                key=attr.key,
                title=attr.title,
                value=attr.value,
                value_type=attr.value_type,
                inherited=False,
                source_node_id=UUID(entity.id)  # type: ignore
            )

        return list(attribute_map.values())

    def remove_entity_attribute(self, entity_id: UUID, key: str) -> OntologyEntity:
        """
        Remove a specific attribute by key.

        Args:
            entity_id: ID of the ontology entity
            key: Attribute key to remove

        Returns:
            Updated OntologyEntity instance

        Raises:
            ValueError: If entity not found, or if attribute data is corrupted or invalid
        """
        entity = self.get_entity(str(entity_id))
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        attributes = self._parse_attributes_json(entity.attributes)  # type: ignore
        attributes = [attr for attr in attributes if attr.key != key]

        attributes_json = json.dumps([attr.model_dump(mode='json') for attr in attributes])
        entity.attributes = attributes_json  # type: ignore
        entity.version = entity.version + 1  # type: ignore
        self.db.commit()
        self.db.refresh(entity)
        return entity

    # Private validation methods

    def _validate_entity_creation(self, entity_data: Dict[str, Any], node_type: NodeType):
        """Validate ontology_entity creation based on type-specific rules"""
        if node_type == NodeType.LAYER:
            self._validate_layer_creation(entity_data)
        elif node_type == NodeType.DOMAIN:
            self._validate_domain_creation(entity_data)
        elif node_type == NodeType.TERM:
            self._validate_term_creation(entity_data)

    def _validate_entity_update(
        self, ontology_entity: OntologyEntity, entity_data: Dict[str, Any]
    ):
        """Validate ontology_entity update based on type-specific rules"""
        if ontology_entity.node_type == NodeType.LAYER:
            self._validate_layer_update(ontology_entity, entity_data)
        elif ontology_entity.node_type == NodeType.DOMAIN:
            self._validate_domain_update(ontology_entity, entity_data)
        elif ontology_entity.node_type == NodeType.TERM:
            self._validate_term_update(ontology_entity, entity_data)

    def _validate_layer_creation(self, entity_data: Dict[str, Any]):
        """Validate layer creation rules"""
        # Layer titles must be unique globally
        existing = (
            self.db.query(OntologyEntity)
            .filter(
                OntologyEntity.node_type == NodeType.LAYER,
                OntologyEntity.title == entity_data["title"],
            )
            .first()
        )

        if existing:
            raise ValueError("Layer title must be unique")

        # Layers should not have parents
        if entity_data.get("parent_entity_id"):
            raise InvalidHierarchyError("Layers cannot have parent structure_nodes")

    def _validate_layer_update(
        self, ontology_entity: OntologyEntity, entity_data: Dict[str, Any]
    ):
        """Validate layer update rules"""
        # Check title uniqueness if title is being updated
        if "title" in entity_data and entity_data["title"] != ontology_entity.title:
            existing = (
                self.db.query(OntologyEntity)
                .filter(
                    OntologyEntity.node_type == NodeType.LAYER,
                    OntologyEntity.title == entity_data["title"],
                    OntologyEntity.id != ontology_entity.id,
                )
                .first()
            )

            if existing:
                raise ValueError("Layer title must be unique")

        # Layers should not have parents
        if "parent_entity_id" in entity_data and entity_data["parent_entity_id"] is not None:
            raise InvalidHierarchyError("Layers cannot have parent structure_nodes")

    def _validate_domain_creation(self, entity_data: Dict[str, Any]):
        """Validate domain creation rules"""
        parent_id = entity_data.get("parent_entity_id")
        if not parent_id:
            raise InvalidHierarchyError("Domains must have a parent layer")

        # Parent must be a layer
        parent = (
            self.db.query(OntologyEntity).filter(OntologyEntity.id == parent_id).first()
        )
        if not parent or parent.node_type != NodeType.LAYER:
            raise InvalidHierarchyError("Domain parent must be a layer")

        # Validate structural predicate ID if provided
        self._validate_structural_predicate_id(entity_data.get("structural_predicate_id"))  # type: ignore

        # Domain titles must be unique within the layer
        existing = (
            self.db.query(OntologyEntity)
            .filter(
                OntologyEntity.node_type == NodeType.DOMAIN,
                OntologyEntity.parent_entity_id == parent_id,
                OntologyEntity.title == entity_data["title"],
            )
            .first()
        )

        if existing:
            raise ValueError("Domain title must be unique within layer")

    def _validate_domain_update(
        self, ontology_entity: OntologyEntity, entity_data: Dict[str, Any]
    ):
        """Validate domain update rules"""
        parent_id = entity_data.get("parent_entity_id", ontology_entity.parent_entity_id)

        # Parent validation if changing parent
        if "parent_entity_id" in entity_data:
            if not parent_id:
                raise InvalidHierarchyError("Domains must have a parent layer")

            parent = (
                self.db.query(OntologyEntity)
                .filter(OntologyEntity.id == parent_id)
                .first()
            )
            if not parent or parent.node_type != NodeType.LAYER:
                raise InvalidHierarchyError("Domain parent must be a layer")

        # Validate structural predicate ID if being updated
        if "structural_predicate_id" in entity_data:
            self._validate_structural_predicate_id(entity_data["structural_predicate_id"])

        # Check title uniqueness within layer if title or parent is changing
        check_title_uniqueness = (
            "title" in entity_data and entity_data["title"] != ontology_entity.title
        ) or (
            "parent_entity_id" in entity_data
            and entity_data["parent_entity_id"] != ontology_entity.parent_entity_id
        )

        if check_title_uniqueness:
            title = entity_data.get("title", ontology_entity.title)
            existing = (
                self.db.query(OntologyEntity)
                .filter(
                    OntologyEntity.node_type == NodeType.DOMAIN,
                    OntologyEntity.parent_entity_id == parent_id,
                    OntologyEntity.title == title,
                    OntologyEntity.id != ontology_entity.id,
                )
                .first()
            )

            if existing:
                raise ValueError("Domain title must be unique within layer")

    def _validate_term_creation(self, entity_data: Dict[str, Any]):
        """Validate term creation rules"""
        parent_id = entity_data.get("parent_entity_id")
        if not parent_id:
            raise InvalidHierarchyError("Terms must have a parent domain or term")

        # Parent must be a domain or term
        parent = (
            self.db.query(OntologyEntity).filter(OntologyEntity.id == parent_id).first()
        )
        if not parent or parent.node_type not in [NodeType.DOMAIN, NodeType.TERM]:
            raise InvalidHierarchyError("Term parent must be a domain or term")

        # Get the domain (either direct parent or ancestor)
        domain = self._get_domain_ancestor(parent)
        if not domain:
            raise ValueError("Term must belong to a domain")

        # Term titles must be unique within the domain
        if self._check_title_uniqueness_in_domain(domain.id, entity_data["title"]):
            raise ValueError("Term title must be unique within domain")

    def _validate_term_update(
        self, ontology_entity: OntologyEntity, entity_data: Dict[str, Any]
    ):
        """Validate term update rules"""
        parent_id = entity_data.get("parent_entity_id", ontology_entity.parent_entity_id)

        # Parent validation if changing parent
        if "parent_entity_id" in entity_data:
            if not parent_id:
                raise InvalidHierarchyError("Terms must have a parent domain or term")

            parent = (
                self.db.query(OntologyEntity)
                .filter(OntologyEntity.id == parent_id)
                .first()
            )
            if not parent or parent.node_type not in [NodeType.DOMAIN, NodeType.TERM]:
                raise InvalidHierarchyError("Term parent must be a domain or term")

        # Get the domain for uniqueness check
        if parent_id:
            parent = (
                self.db.query(OntologyEntity)
                .filter(OntologyEntity.id == parent_id)
                .first()
            )
            domain = self._get_domain_ancestor(parent) if parent else None
        else:
            domain = None

        if not domain:
            raise ValueError("Term must belong to a domain")

        # Check title uniqueness within domain if title or parent is changing
        check_title_uniqueness = (
            "title" in entity_data and entity_data["title"] != ontology_entity.title
        ) or (
            "parent_entity_id" in entity_data
            and entity_data["parent_entity_id"] != ontology_entity.parent_entity_id
        )

        if check_title_uniqueness:
            title = entity_data.get("title", ontology_entity.title)
            if self._check_title_uniqueness_in_domain(
                domain.id, title, exclude_id=ontology_entity.id
            ):
                raise ValueError("Term title must be unique within domain")

    def _validate_no_circular_reference(
        self, entity_id: Optional[str], parent_id: Optional[str]
    ):
        """
        Validate no circular references.

        For now, this is a simple implementation. The Graph Service integration
        can be enhanced later for more sophisticated cycle detection.
        """
        if not parent_id or not entity_id:
            return

        # Check if parent_id is the same as entity_id
        if entity_id == parent_id:
            raise CircularReferenceError("StructureNode cannot be its own parent")

        # Check if parent_id is a descendant of entity_id
        ancestors = self.get_entity_ancestors(parent_id)
        ancestor_ids = [ancestor.id for ancestor in ancestors]

        if entity_id in ancestor_ids:
            raise CircularReferenceError("Operation would create circular reference")

    def _get_domain_ancestor(
        self, ontology_entity: OntologyEntity
    ) -> Optional[OntologyEntity]:
        """Get the domain ancestor of an ontology_entity"""
        current = ontology_entity
        while current:
            if current.node_type == NodeType.DOMAIN:
                return current
            if current.parent_entity_id:
                current = (
                    self.db.query(OntologyEntity)
                    .filter(OntologyEntity.id == current.parent_entity_id)
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
            exclude_id: Optional ontology_entity ID to exclude from check (for updates)

        Returns:
            True if title already exists (not unique), False if unique
        """
        # Get all terms in the domain tree
        domain_terms = self._get_all_terms_in_domain(domain_id)

        # Check for title conflicts
        query = self.db.query(OntologyEntity).filter(
            OntologyEntity.node_type == NodeType.TERM,
            OntologyEntity.id.in_(domain_terms),
            OntologyEntity.title == title,
        )

        if exclude_id:
            query = query.filter(OntologyEntity.id != exclude_id)

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
            self.db.query(OntologyEntity.id)
            .filter(
                OntologyEntity.node_type == NodeType.TERM,
                OntologyEntity.parent_entity_id == domain_id,
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
            self.db.query(OntologyEntity.id)
            .filter(
                OntologyEntity.node_type == NodeType.TERM,
                OntologyEntity.parent_entity_id == term_id,
            )
            .all()
        )

        all_child_ids = [term[0] for term in child_terms]

        # Recursively get children of children
        for child_id in all_child_ids[:]:
            grandchild_terms = self._get_all_terms_under_term(child_id)
            all_child_ids.extend(grandchild_terms)

        return all_child_ids

    def _entity_to_dict(self, ontology_entity: OntologyEntity) -> Dict[str, Any]:
        """Convert an OntologyEntity instance to a dictionary"""
        return {
            "id": ontology_entity.id,
            "node_type": (
                ontology_entity.node_type.value
                if isinstance(ontology_entity.node_type, NodeType)
                else ontology_entity.node_type
            ),
            "parent_entity_id": ontology_entity.parent_entity_id,
            "title": ontology_entity.title,
            "definition": ontology_entity.definition,
            "structural_predicate_id": ontology_entity.structural_predicate_id,
            "created_at": (
                ontology_entity.created_at.isoformat()
                if ontology_entity.created_at
                else None
            ),
            "version": ontology_entity.version,
            "last_modified": (
                ontology_entity.last_modified.isoformat()
                if ontology_entity.last_modified
                else None
            ),
        }

    def _fire_entity_event(
        self,
        event_type: str,
        entity_type: str,
        old_data: Optional[Dict[str, Any]],
        new_data: Optional[Dict[str, Any]],
    ):
        """
        Fire an ontology_entity event manually (if needed).

        Note: Database triggers should handle this automatically, but this method
        is available for manual event firing if required.
        """
        try:
            event = ChangeEvent(
                event_type=event_type,
                record_type=entity_type,  # Map entity_type to record_type
                record_id=None,  # This would need to be set based on which entity is being affected
                old_data=old_data,
                new_data=new_data,
            )

            self.db.add(event)
            self.db.commit()

        except Exception as e:
            logger.warning(f"Failed to fire ontology_entity event: {e}")

    def _get_all_descendants(self, entity_id: str) -> List[OntologyEntity]:
        """
        Get all descendant ontology_entities recursively.

        Args:
            entity_id: Parent ontology_entity ID

        Returns:
            List of all descendant OntologyEntity instances
        """
        all_descendants = []

        # Get direct children
        direct_children = (
            self.db.query(OntologyEntity)
            .filter(OntologyEntity.parent_entity_id == entity_id)
            .all()
        )

        for child in direct_children:
            # Add child to the list
            all_descendants.append(child)
            # Recursively add child's descendants
            all_descendants.extend(self._get_all_descendants(child.id))

        return all_descendants

    def move_entities(
        self,
        entity_ids: List[str],
        target_parent_id: Optional[str] = None,
        move_children: bool = True,
        handle_conflicts: str = "warn",
    ) -> Dict[str, Any]:
        """
        Move ontology_entities to a new parent with automatic type conversion.

        IMPORTANT: When an entity is moved to a parent with a different type constraint,
        the entity AND ALL ITS CHILDREN are automatically converted to the appropriate type.
        This conversion happens regardless of the move_children parameter.

        Args:
            entity_ids: List of ontology_entity IDs to move
            target_parent_id: Target parent ontology_entity ID (None for root level)
            move_children: If True, include all descendants in the response.
                          Note: Children are ALWAYS type-converted, this only controls
                          whether they're included in the response.
            handle_conflicts: How to handle title conflicts ("warn", "rename", "error")

        Returns:
            Dictionary containing moved ontology_entities, updated children, warnings, and errors

        Raises:
            ValueError: If validation fails
        """
        logger.info(
            f"Moving {len(entity_ids)} ontology_entities to parent {target_parent_id}"
        )

        moved_entities = []
        updated_children = []
        converted_entities = []
        warnings = []
        errors = []

        try:
            # Start transaction
            self.db.begin()

            # Validate target parent exists (if specified)
            target_parent = None
            if target_parent_id:
                target_parent = self.get_entity(target_parent_id)
                if not target_parent:
                    raise ValueError("Target parent ontology_entity does not exist")

            # Process each ontology_entity
            for entity_id in entity_ids:
                try:
                    result = self._move_single_entity(
                        entity_id,
                        target_parent_id,
                        target_parent,
                        move_children,
                        handle_conflicts,
                    )

                    moved_entities.append(result["moved_entity"])
                    updated_children.extend(result["updated_children"])
                    converted_entities.extend(result["converted_entities"])
                    warnings.extend(result["warnings"])

                except ValueError as e:
                    errors.append(f"Failed to move ontology_entity {entity_id}: {str(e)}")
                    logger.warning(f"Failed to move ontology_entity {entity_id}: {e}")

            # Commit transaction
            self.db.commit()
            logger.info(f"Successfully moved {len(moved_entities)} ontology_entities")

            return {
                "moved_entities": moved_entities,
                "updated_children": updated_children,
                "converted_entities": converted_entities,
                "warnings": warnings,
                "errors": errors,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Move operation failed: {e}")
            raise ValueError(f"Move operation failed: {str(e)}")

    def _move_single_entity(
        self,
        entity_id: str,
        target_parent_id: Optional[str],
        target_parent: Optional[OntologyEntity],
        move_children: bool,
        handle_conflicts: str,
    ) -> Dict[str, Any]:
        """
        Move a single ontology_entity with automatic type conversion.

        Args:
            entity_id: OntologyEntity ID to move
            target_parent_id: Target parent ontology_entity ID
            target_parent: Target parent OntologyEntity instance (if any)
            move_children: Whether to move children
            handle_conflicts: How to handle conflicts

        Returns:
            Dictionary with moved ontology_entity, updated children, converted entities, and warnings
        """
        warnings = []
        updated_children = []
        converted_entities = []

        # Get the ontology_entity to move
        ontology_entity = self.get_entity(entity_id)
        if not ontology_entity:
            raise NotFoundError("OntologyEntity", entity_id)

        # Infer target type from parent
        target_type = self._infer_entity_type_from_parent(target_parent)

        # Validate with target type
        self._validate_entity_move(ontology_entity, target_parent, target_type=target_type)

        # Check for title conflicts with target type
        conflict_warning = self._check_move_conflicts_with_type(
            ontology_entity, target_parent_id, target_type, handle_conflicts
        )
        if conflict_warning:
            warnings.append(conflict_warning)

        # Convert entity type and all children recursively BEFORE updating parent
        self._convert_entity_type_and_children(ontology_entity, target_type, converted_entities)

        # Update the ontology_entity's parent AFTER successful conversion
        old_parent_id = ontology_entity.parent_entity_id
        ontology_entity.parent_entity_id = target_parent_id

        # Save changes
        self.db.add(ontology_entity)
        self.db.flush()

        # Move children if requested
        if move_children:
            children = self._get_all_descendants(entity_id)
            for child in children:
                updated_children.append(child)

        logger.info(
            f"Moved ontology_entity {entity_id} from parent {old_parent_id} to {target_parent_id}, "
            f"converted {len(converted_entities)} entities"
        )

        return {
            "moved_entity": ontology_entity,
            "updated_children": updated_children,
            "converted_entities": converted_entities,
            "warnings": warnings,
        }

    def _validate_entity_move(
        self,
        ontology_entity: OntologyEntity,
        target_parent: Optional[OntologyEntity],
        target_type: Optional[NodeType] = None
    ):
        """
        Validate that an ontology_entity move is allowed based on type hierarchy rules.

        Args:
            ontology_entity: OntologyEntity to move
            target_parent: Target parent OntologyEntity (None for root)
            target_type: The type the entity will be converted to (if None, use current type)

        Raises:
            ValueError: If the move violates hierarchy rules
        """
        # Use target_type if provided, otherwise use current entity type
        entity_type = target_type if target_type else ontology_entity.node_type

        # Layer moves
        if entity_type == NodeType.LAYER:
            if target_parent is not None:
                raise InvalidHierarchyError("Layers must be at root level (no parent)")

        # Domain moves
        elif entity_type == NodeType.DOMAIN:
            if target_parent is None:
                raise InvalidHierarchyError("Domains must have a parent layer")
            if target_parent.node_type != NodeType.LAYER:
                raise InvalidHierarchyError("Domains can only be placed under layers")

        # Term moves
        elif entity_type == NodeType.TERM:
            if target_parent is None:
                raise InvalidHierarchyError("Terms must have a parent")
            if target_parent.node_type not in [NodeType.DOMAIN, NodeType.TERM]:
                raise InvalidHierarchyError("Terms can only be placed under domains or other terms")

        # Prevent circular references
        if target_parent and self._would_create_cycle(
            ontology_entity.id, target_parent.id
        ):
            raise CircularReferenceError("Move would create circular reference")

    def _infer_entity_type_from_parent(
        self,
        target_parent: Optional[OntologyEntity]
    ) -> NodeType:
        """
        Infer the appropriate entity type based on the target parent.

        Args:
            target_parent: Target parent entity (None for root)

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

    def _convert_entity_type_and_children(
        self,
        entity: OntologyEntity,
        new_type: NodeType,
        converted_entities: List[OntologyEntity]
    ) -> None:
        """
        Recursively convert an entity and all its descendants to appropriate types.

        Args:
            entity: Entity to convert
            new_type: Target type for this entity
            converted_entities: List to accumulate converted entities for response
        """
        old_type = entity.node_type

        # Only convert if type actually changes
        if old_type != new_type:
            logger.info(f"Converting entity {entity.id} from {old_type} to {new_type}")
            entity.node_type = new_type
            converted_entities.append(entity)
            self.db.add(entity)

        # Recursively convert all direct children
        children = self.db.query(OntologyEntity).filter(
            OntologyEntity.parent_entity_id == str(entity.id)
        ).all()

        for child in children:
            # Determine child's new type based on parent's new type
            if new_type == NodeType.LAYER:
                child_new_type = NodeType.DOMAIN
            elif new_type in [NodeType.DOMAIN, NodeType.TERM]:
                child_new_type = NodeType.TERM
            else:
                continue

            self._convert_entity_type_and_children(child, child_new_type, converted_entities)

    def _check_move_conflicts_with_type(
        self,
        ontology_entity: OntologyEntity,
        target_parent_id: Optional[str],
        target_type: NodeType,
        handle_conflicts: str,
    ) -> Optional[str]:
        """
        Check for title conflicts using the TARGET type's uniqueness rules.

        Args:
            ontology_entity: Entity being moved
            target_parent_id: Target parent ID
            target_type: Type the entity will become
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
                self.db.query(OntologyEntity)
                .filter(
                    OntologyEntity.title == ontology_entity.title,
                    OntologyEntity.node_type == NodeType.LAYER,
                    OntologyEntity.id != ontology_entity.id,
                )
                .first()
            )
        elif target_type == NodeType.DOMAIN:
            # Domains must be unique within layer
            existing = (
                self.db.query(OntologyEntity)
                .filter(
                    OntologyEntity.title == ontology_entity.title,
                    OntologyEntity.node_type == NodeType.DOMAIN,
                    OntologyEntity.parent_entity_id == target_parent_id,
                    OntologyEntity.id != ontology_entity.id,
                )
                .first()
            )
        elif target_type == NodeType.TERM:
            # Terms must be unique within parent (domain or term)
            existing = (
                self.db.query(OntologyEntity)
                .filter(
                    OntologyEntity.title == ontology_entity.title,
                    OntologyEntity.node_type == NodeType.TERM,
                    OntologyEntity.parent_entity_id == target_parent_id,
                    OntologyEntity.id != ontology_entity.id,
                )
                .first()
            )
        else:
            existing = None

        if existing:
            conflict_msg = (
                f"Entity with title '{ontology_entity.title}' already exists "
                f"at target location as {target_type.value}"
            )

            if handle_conflicts == "error":
                raise ValueError(conflict_msg)
            elif handle_conflicts == "rename":
                # Generate unique title with TARGET type
                counter = 1
                new_title = f"{ontology_entity.title} ({counter})"
                while self._title_exists_at_target(new_title, target_parent_id, target_type, ontology_entity.id):
                    counter += 1
                    new_title = f"{ontology_entity.title} ({counter})"

                ontology_entity.title = new_title
                return f"Renamed entity to '{new_title}' to avoid conflict with existing {target_type}"
            else:  # handle_conflicts == "warn"
                return conflict_msg

        return None

    def _title_exists_at_target(
        self, title: str, target_parent_id: Optional[str], target_type: NodeType, exclude_id: str
    ) -> bool:
        """Helper to check if a title exists at the target location."""
        if target_type == NodeType.LAYER:
            return self.db.query(OntologyEntity).filter(
                OntologyEntity.title == title,
                OntologyEntity.node_type == NodeType.LAYER,
                OntologyEntity.id != exclude_id,
            ).first() is not None
        elif target_type == NodeType.DOMAIN:
            return self.db.query(OntologyEntity).filter(
                OntologyEntity.title == title,
                OntologyEntity.node_type == NodeType.DOMAIN,
                OntologyEntity.parent_entity_id == target_parent_id,
                OntologyEntity.id != exclude_id,
            ).first() is not None
        elif target_type == NodeType.TERM:
            return self.db.query(OntologyEntity).filter(
                OntologyEntity.title == title,
                OntologyEntity.node_type == NodeType.TERM,
                OntologyEntity.parent_entity_id == target_parent_id,
                OntologyEntity.id != exclude_id,
            ).first() is not None
        return False

    def _would_create_cycle(self, entity_id: str, target_parent_id: str) -> bool:
        """
        Check if moving an ontology_entity would create a circular reference.

        Args:
            entity_id: OntologyEntity ID being moved
            target_parent_id: Target parent ID

        Returns:
            True if move would create a cycle, False otherwise
        """
        # If target_parent_id is in the descendants of entity_id, it would create a cycle
        descendants = self._get_all_descendants(entity_id)
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
                self.db.query(PropertyDefinition)
                .filter(PropertyDefinition.id == structural_predicate_id)
                .first()
            )

            if not predicate:
                raise ValueError(
                    f"Invalid structural_predicate_id: predicate '{structural_predicate_id}' does not exist"
                )

    # Deprecated method wrappers for backward compatibility
    def create_node(self, node_data: Dict[str, Any]) -> OntologyEntity:
        """Deprecated: use create_entity() instead"""
        # Translate old key names to new ones
        translated_data = node_data.copy()
        if "parent_node_id" in translated_data:
            translated_data["parent_entity_id"] = translated_data.pop("parent_node_id")
        return self.create_entity(translated_data)

    def update_node(self, node_id: str, node_data: Dict[str, Any]) -> OntologyEntity:
        """Deprecated: use update_entity() instead"""
        # Translate old key names to new ones
        translated_data = node_data.copy()
        if "parent_node_id" in translated_data:
            translated_data["parent_entity_id"] = translated_data.pop("parent_node_id")
        return self.update_entity(node_id, translated_data)

    def delete_node(self, *args, **kwargs):
        """Deprecated: use delete_entity() instead"""
        return self.delete_entity(*args, **kwargs)

    def get_node(self, *args, **kwargs):
        """Deprecated: use get_entity() instead"""
        return self.get_entity(*args, **kwargs)

    def list_nodes(self, *args, **kwargs):
        """Deprecated: use list_entities() instead"""
        # Translate old kwarg names to new ones
        if "parent_node_id" in kwargs:
            kwargs["parent_entity_id"] = kwargs.pop("parent_node_id")
        return self.list_entities(*args, **kwargs)

    def get_nodes(self, *args, **kwargs):
        """Deprecated: use get_entities() instead"""
        return self.get_entities(*args, **kwargs)

    def count_nodes(self, *args, **kwargs):
        """Deprecated: use count_entities() instead"""
        # Translate old kwarg names to new ones
        if "parent_node_id" in kwargs:
            kwargs["parent_entity_id"] = kwargs.pop("parent_node_id")
        return self.count_entities(*args, **kwargs)

    def get_node_children(self, *args, **kwargs):
        """Deprecated: use get_entity_children() instead"""
        # Translate old kwarg names to new ones
        if "parent_node_id" in kwargs:
            kwargs["parent_entity_id"] = kwargs.pop("parent_node_id")
        return self.get_entity_children(*args, **kwargs)

    def get_node_ancestors(self, *args, **kwargs):
        """Deprecated: use get_entity_ancestors() instead"""
        return self.get_entity_ancestors(*args, **kwargs)

    def set_node_attributes(self, *args, **kwargs):
        """Deprecated: use set_entity_attributes() instead"""
        return self.set_entity_attributes(*args, **kwargs)


    def resolve_node_attributes(self, *args, **kwargs):
        """Deprecated: use resolve_entity_attributes() instead"""
        return self.resolve_entity_attributes(*args, **kwargs)

    def remove_node_attribute(self, *args, **kwargs):
        """Deprecated: use remove_entity_attribute() instead"""
        return self.remove_entity_attribute(*args, **kwargs)

    def move_nodes(
        self,
        node_ids: List[str],
        target_parent_id: Optional[str] = None,
        move_children: bool = True,
        handle_conflicts: str = "warn",
    ) -> Dict[str, Any]:
        """Deprecated: use move_entities() instead"""
        return self.move_entities(
            entity_ids=node_ids,
            target_parent_id=target_parent_id,
            move_children=move_children,
            handle_conflicts=handle_conflicts
        )

    def _validate_node_creation(self, *args, **kwargs):
        """Deprecated: use _validate_entity_creation() instead"""
        return self._validate_entity_creation(*args, **kwargs)

    def _validate_node_update(self, *args, **kwargs):
        """Deprecated: use _validate_entity_update() instead"""
        return self._validate_entity_update(*args, **kwargs)

    def _node_to_dict(self, *args, **kwargs):
        """Deprecated: use _entity_to_dict() instead"""
        return self._entity_to_dict(*args, **kwargs)

    def _validate_node_move(self, *args, **kwargs):
        """Deprecated: use _validate_entity_move() instead"""
        return self._validate_entity_move(*args, **kwargs)

    def _convert_node_type_and_children(self, *args, **kwargs):
        """Deprecated: use _convert_entity_type_and_children() instead"""
        return self._convert_entity_type_and_children(*args, **kwargs)
