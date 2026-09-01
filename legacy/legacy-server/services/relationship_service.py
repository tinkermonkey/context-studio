"""
Relationship Service - Centralized business logic for relationship operations

This service implements the business logic for ontology_entity relationships,
ensuring that only compatible ontology_entities can be linked together.
"""

from typing import Any

from database.enums import NodeType
from database.models import OntologyEntity, Relationship
from sqlalchemy.orm import Session
from utils.logger import get_logger

from services.change_event_handler import ChangeEventHandler

logger = get_logger(__name__)


class RelationshipService:
    """Centralized business logic for relationship operations"""

    def __init__(self, db: Session):
        """
        Initialize the RelationshipService.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.event_handler = ChangeEventHandler(db)
        logger.info("RelationshipService initialized with event handling")

    def create_relationship(self, relationship_data: dict[str, Any]) -> Relationship:
        """
        Create a new relationship with validation.

        Args:
            relationship_data: Dictionary containing relationship data

        Returns:
            Created Relationship instance

        Raises:
            ValueError: If validation fails
        """
        logger.info(
            f"Creating relationship: {relationship_data.get('source_entity_id')} -> {relationship_data.get('target_entity_id')}"
        )

        # Validate required fields
        required_fields = ["source_entity_id", "target_entity_id", "predicate"]
        for field in required_fields:
            if field not in relationship_data:
                raise ValueError(f"{field} is required")

        source_id = relationship_data["source_entity_id"]
        target_id = relationship_data["target_entity_id"]
        predicate = relationship_data["predicate"]

        # Validate that source and target are different
        if source_id == target_id:
            raise ValueError("Source and target ontology_entities cannot be the same")

        # Get source and target ontology_entities
        source: OntologyEntity | None = (
            self.db.query(OntologyEntity).filter(OntologyEntity.id == source_id).first()
        )
        target: OntologyEntity | None = (
            self.db.query(OntologyEntity).filter(OntologyEntity.id == target_id).first()
        )

        if not source:
            raise ValueError(f"Source ontology_entity not found: {source_id}")
        if not target:
            raise ValueError(f"Target ontology_entity not found: {target_id}")

        # Validate same ontology_entity type constraint
        if source.node_type != target.node_type:
            raise ValueError(
                f"OntologyEntities can only be linked to entities of the same type. "
                f"Source is {source.node_type}, target is {target.node_type}"
            )

        # Check for duplicate relationships
        existing: Relationship | None = (
            self.db.query(Relationship)
            .filter(
                Relationship.source_entity_id == source_id,
                Relationship.target_entity_id == target_id,
                Relationship.predicate == predicate,
            )
            .first()
        )

        if existing:
            raise ValueError(
                f"Relationship already exists: {source_id} -> {target_id} ({predicate})"
            )

        # Create relationship
        relationship = Relationship(
            source_entity_id=source_id,
            target_entity_id=target_id,
            predicate=predicate,
            predicate_id=relationship_data.get("predicate_id"),
        )

        try:
            self.db.add(relationship)
            self.db.commit()
            self.db.refresh(relationship)

            logger.info(f"Successfully created relationship: {relationship.id}")

            # Fire relationship created event using new ChangeEventHandler
            relationship_dict = self._relationship_to_dict(relationship)
            from database.enums import RecordType

            self.event_handler.fire_created_event(
                RecordType.RELATIONSHIP, str(relationship.id), relationship_dict
            )

            return relationship

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create relationship: {e}")
            raise ValueError(f"Failed to create relationship: {e}")

    def update_relationship(
        self, relationship_id: str, relationship_data: dict[str, Any]
    ) -> Relationship:
        """
        Update an existing relationship.

        Args:
            relationship_id: ID of the relationship to update
            relationship_data: Dictionary containing updated relationship data

        Returns:
            Updated Relationship instance

        Raises:
            ValueError: If validation fails or relationship not found
        """
        logger.info(f"Updating relationship: {relationship_id}")

        # Get existing relationship
        relationship: Relationship | None = (
            self.db.query(Relationship)
            .filter(Relationship.id == relationship_id)
            .first()
        )
        if not relationship:
            raise ValueError(f"Relationship not found: {relationship_id}")

        # Validate updated fields
        if (
            "source_entity_id" in relationship_data
            or "target_entity_id" in relationship_data
        ):
            source_id = relationship_data.get(
                "source_entity_id", relationship.source_entity_id
            )
            target_id = relationship_data.get(
                "target_entity_id", relationship.target_entity_id
            )

            if source_id == target_id:
                raise ValueError(
                    "Source and target ontology_entities cannot be the same"
                )

            # Get ontology_entities to validate
            source: OntologyEntity | None = (
                self.db.query(OntologyEntity)
                .filter(OntologyEntity.id == source_id)
                .first()
            )
            target: OntologyEntity | None = (
                self.db.query(OntologyEntity)
                .filter(OntologyEntity.id == target_id)
                .first()
            )

            if not source:
                raise ValueError(f"Source ontology_entity not found: {source_id}")
            if not target:
                raise ValueError(f"Target ontology_entity not found: {target_id}")

            # Validate same ontology_entity type constraint
            if source.node_type != target.node_type:
                raise ValueError(
                    f"OntologyEntities can only be linked to entities of the same type. "
                    f"Source is {source.node_type}, target is {target.node_type}"
                )

            # Check for duplicate relationships (excluding current relationship)
            predicate = relationship_data.get("predicate", relationship.predicate)
            existing: Relationship | None = (
                self.db.query(Relationship)
                .filter(
                    Relationship.source_entity_id == source_id,
                    Relationship.target_entity_id == target_id,
                    Relationship.predicate == predicate,
                    Relationship.id != relationship_id,
                )
                .first()
            )

            if existing:
                raise ValueError(
                    f"Relationship already exists: {source_id} -> {target_id} ({predicate})"
                )

        # Store old data for event
        old_relationship_data = self._relationship_to_dict(relationship)

        # Update fields
        if "source_entity_id" in relationship_data:
            relationship.source_entity_id = relationship_data["source_entity_id"]

        if "target_entity_id" in relationship_data:
            relationship.target_entity_id = relationship_data["target_entity_id"]

        if "predicate" in relationship_data:
            relationship.predicate = relationship_data["predicate"]

        if "predicate_id" in relationship_data:
            relationship.predicate_id = relationship_data["predicate_id"]

        try:
            self.db.commit()
            self.db.refresh(relationship)

            logger.info(f"Successfully updated relationship: {relationship.id}")

            # Fire relationship updated event using new ChangeEventHandler
            new_relationship_data = self._relationship_to_dict(relationship)
            from database.enums import RecordType

            self.event_handler.fire_updated_event(
                RecordType.RELATIONSHIP,
                str(relationship.id),
                old_relationship_data,
                new_relationship_data,
            )

            return relationship

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update relationship: {e}")
            raise ValueError(f"Failed to update relationship: {e}")

    def delete_relationship(self, relationship_id: str) -> bool:
        """
        Delete a relationship.

        Args:
            relationship_id: ID of the relationship to delete

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If relationship not found
        """
        logger.info(f"Deleting relationship: {relationship_id}")

        relationship = (
            self.db.query(Relationship)
            .filter(Relationship.id == relationship_id)
            .first()
        )
        if not relationship:
            raise ValueError(f"Relationship not found: {relationship_id}")

        # Store relationship data for event before deletion
        relationship_data = self._relationship_to_dict(relationship)

        try:
            self.db.delete(relationship)
            self.db.commit()

            logger.info(f"Successfully deleted relationship: {relationship_id}")

            # Fire relationship deleted event using new ChangeEventHandler
            from database.enums import RecordType

            self.event_handler.fire_deleted_event(
                RecordType.RELATIONSHIP, relationship_id, relationship_data
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete relationship: {e}")
            raise ValueError(f"Failed to delete relationship: {e}")

    def get_relationship(self, relationship_id: str) -> Relationship | None:
        """
        Get a relationship by ID.

        Args:
            relationship_id: ID of the relationship to retrieve

        Returns:
            Relationship instance or None if not found
        """
        return (
            self.db.query(Relationship)
            .filter(Relationship.id == relationship_id)
            .first()
        )

    def list_relationships(
        self,
        source_entity_id: str | None = None,
        target_entity_id: str | None = None,
        predicate: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Relationship]:
        """
        List relationships with optional filtering.

        Args:
            source_entity_id: Optional source ontology_entity ID to filter by
            target_entity_id: Optional target ontology_entity ID to filter by
            predicate: Optional predicate to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Relationship instances
        """
        query = self.db.query(Relationship)

        if source_entity_id:
            query = query.filter(Relationship.source_entity_id == source_entity_id)

        if target_entity_id:
            query = query.filter(Relationship.target_entity_id == target_entity_id)

        if predicate:
            query = query.filter(Relationship.predicate == predicate)

        return (
            query.order_by(Relationship.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_relationships(
        self,
        source_entity_id: str | None = None,
        target_entity_id: str | None = None,
        predicate: str | None = None,
    ) -> int:
        """
        Count relationships with optional filtering.

        Args:
            source_entity_id: Optional source ontology_entity ID to filter by
            target_entity_id: Optional target ontology_entity ID to filter by
            predicate: Optional predicate to filter by

        Returns:
            Count of matching relationships
        """
        query = self.db.query(Relationship)

        if source_entity_id:
            query = query.filter(Relationship.source_entity_id == source_entity_id)

        if target_entity_id:
            query = query.filter(Relationship.target_entity_id == target_entity_id)

        if predicate:
            query = query.filter(Relationship.predicate == predicate)

        return query.count()

    def get_entity_relationships(
        self, entity_id: str, direction: str = "both"
    ) -> list[Relationship]:
        """
        Get all relationships for a specific ontology_entity.

        Args:
            entity_id: OntologyEntity ID to get relationships for
            direction: Direction of relationships to get ("outgoing", "incoming", "both")

        Returns:
            List of Relationship instances

        Raises:
            ValueError: If direction is invalid
        """
        if direction not in ["outgoing", "incoming", "both"]:
            raise ValueError("direction must be 'outgoing', 'incoming', or 'both'")

        query = self.db.query(Relationship)

        if direction == "outgoing":
            query = query.filter(Relationship.source_entity_id == entity_id)
        elif direction == "incoming":
            query = query.filter(Relationship.target_entity_id == entity_id)
        else:  # both
            query = query.filter(
                (Relationship.source_entity_id == entity_id)
                | (Relationship.target_entity_id == entity_id)
            )

        return query.order_by(Relationship.created_at.desc()).all()

    def get_related_entities(
        self,
        entity_id: str,
        direction: str = "both",
        node_type: NodeType | None = None,
    ) -> list[OntologyEntity]:
        """
        Get all ontology_entities related to a specific ontology_entity.

        Args:
            entity_id: OntologyEntity ID to get related entities for
            direction: Direction of relationships ("outgoing", "incoming", "both")
            node_type: Optional entity type to filter results by

        Returns:
            List of related OntologyEntity instances

        Raises:
            ValueError: If direction is invalid
        """
        if direction not in ["outgoing", "incoming", "both"]:
            raise ValueError("direction must be 'outgoing', 'incoming', or 'both'")

        # Get the relationships first
        relationships = self.get_entity_relationships(entity_id, direction)

        # Extract related entity IDs
        related_entity_ids = set()
        for relationship in relationships:
            if direction == "outgoing":
                related_entity_ids.add(relationship.target_entity_id)
            elif direction == "incoming":
                related_entity_ids.add(relationship.source_entity_id)
            else:  # both
                if relationship.source_entity_id != entity_id:
                    related_entity_ids.add(relationship.source_entity_id)
                if relationship.target_entity_id != entity_id:
                    related_entity_ids.add(relationship.target_entity_id)

        # Get the actual ontology_entities
        query = self.db.query(OntologyEntity).filter(
            OntologyEntity.id.in_(related_entity_ids)
        )

        if node_type:
            query = query.filter(OntologyEntity.node_type == node_type)

        return query.order_by(OntologyEntity.title).all()

    def validate_relationship_compatibility(
        self, source_entity_id: str, target_entity_id: str
    ) -> bool:
        """
        Validate if two ontology_entities can be linked together.

        Args:
            source_entity_id: Source ontology_entity ID
            target_entity_id: Target ontology_entity ID

        Returns:
            True if entities can be linked, False otherwise
        """
        if source_entity_id == target_entity_id:
            return False

        # Get ontology_entities
        source = (
            self.db.query(OntologyEntity)
            .filter(OntologyEntity.id == source_entity_id)
            .first()
        )
        target = (
            self.db.query(OntologyEntity)
            .filter(OntologyEntity.id == target_entity_id)
            .first()
        )

        if not source or not target:
            return False

        # Must be same entity type
        return source.node_type == target.node_type

    def get_relationship_statistics(self) -> dict[str, Any]:
        """
        Get statistics about relationships in the system.

        Returns:
            Dictionary containing relationship statistics
        """
        # Total relationships
        total_relationships = self.db.query(Relationship).count()

        # Relationships by predicate
        predicate_stats = {}
        predicates = self.db.query(Relationship.predicate).distinct().all()
        for (predicate,) in predicates:
            count = (
                self.db.query(Relationship)
                .filter(Relationship.predicate == predicate)
                .count()
            )
            predicate_stats[predicate] = count

        # Relationships by entity type (source)
        node_type_stats = {}
        for node_type in NodeType:
            count = (
                self.db.query(Relationship)
                .join(
                    OntologyEntity, Relationship.source_entity_id == OntologyEntity.id
                )
                .filter(OntologyEntity.node_type == node_type)
                .count()
            )
            node_type_stats[node_type.value] = count

        return {
            "total_relationships": total_relationships,
            "relationships_by_predicate": predicate_stats,
            "relationships_by_source_entity_type": node_type_stats,
        }

    def _relationship_to_dict(self, relationship: Relationship) -> dict[str, Any]:
        """Convert a Relationship instance to a dictionary"""
        return {
            "id": relationship.id,
            "source_entity_id": relationship.source_entity_id,
            "target_entity_id": relationship.target_entity_id,
            "predicate": relationship.predicate,
            "predicate_id": relationship.predicate_id,
            "created_at": (
                relationship.created_at.isoformat() if relationship.created_at else None
            ),
        }

    # Deprecated method wrappers for backward compatibility
    def create_link(self, link_data: dict[str, Any]) -> Relationship:
        """Deprecated: use create_relationship() instead"""
        # Translate old key names to new ones, preferring new names over old
        translated_data = {}

        # Handle source_entity_id (prefer new name, fall back to old name)
        if "source_entity_id" in link_data:
            translated_data["source_entity_id"] = link_data["source_entity_id"]
        elif "source_node_id" in link_data:
            translated_data["source_entity_id"] = link_data["source_node_id"]

        # Handle target_entity_id (prefer new name, fall back to old name)
        if "target_entity_id" in link_data:
            translated_data["target_entity_id"] = link_data["target_entity_id"]
        elif "target_node_id" in link_data:
            translated_data["target_entity_id"] = link_data["target_node_id"]

        # Add predicate and predicate_id if present
        if "predicate" in link_data:
            translated_data["predicate"] = link_data["predicate"]
        if "predicate_id" in link_data:
            translated_data["predicate_id"] = link_data["predicate_id"]

        return self.create_relationship(translated_data)

    def update_link(self, link_id: str, link_data: dict[str, Any]) -> Relationship:
        """Deprecated: use update_relationship() instead"""
        # Translate old key names to new ones
        translated_data = link_data.copy()
        if "source_node_id" in translated_data:
            translated_data["source_entity_id"] = translated_data.pop("source_node_id")
        if "target_node_id" in translated_data:
            translated_data["target_entity_id"] = translated_data.pop("target_node_id")
        return self.update_relationship(link_id, translated_data)

    def delete_link(self, *args, **kwargs):
        """Deprecated: use delete_relationship() instead"""
        return self.delete_relationship(*args, **kwargs)

    def _node_link_to_dict(self, relationship: Relationship) -> dict[str, Any]:
        """Deprecated: use _relationship_to_dict() instead"""
        result = self._relationship_to_dict(relationship)
        # Translate new keys back to old keys for backward compatibility
        return {
            "id": result["id"],
            "source_node_id": result["source_entity_id"],
            "target_node_id": result["target_entity_id"],
            "predicate": result["predicate"],
            "predicate_id": result["predicate_id"],
            "created_at": result["created_at"],
        }

    def get_link(self, link_id: str) -> Relationship | None:
        """Deprecated: use get_relationship() instead"""
        return self.get_relationship(link_id)

    def list_links(
        self,
        source_node_id: str | None = None,
        target_node_id: str | None = None,
        predicate: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Relationship]:
        """Deprecated: use list_relationships() instead"""
        # Translate old parameter names to new ones
        return self.list_relationships(
            source_entity_id=source_node_id,
            target_entity_id=target_node_id,
            predicate=predicate,
            skip=skip,
            limit=limit,
        )

    def count_links(
        self,
        source_node_id: str | None = None,
        target_node_id: str | None = None,
        predicate: str | None = None,
    ) -> int:
        """Deprecated: use count_relationships() instead"""
        # Translate old parameter names to new ones
        return self.count_relationships(
            source_entity_id=source_node_id,
            target_entity_id=target_node_id,
            predicate=predicate,
        )

    def get_node_links(
        self, node_id: str, direction: str = "both"
    ) -> list[Relationship]:
        """Deprecated: use get_entity_relationships() instead"""
        return self.get_entity_relationships(node_id, direction)

    def get_linked_nodes(
        self,
        node_id: str,
        direction: str = "both",
        node_type: NodeType | None = None,
    ) -> list[OntologyEntity]:
        """Deprecated: use get_related_entities() instead"""
        return self.get_related_entities(node_id, direction, node_type)

    def validate_link_compatibility(
        self, source_node_id: str, target_node_id: str
    ) -> bool:
        """Deprecated: use validate_relationship_compatibility() instead"""
        return self.validate_relationship_compatibility(source_node_id, target_node_id)
