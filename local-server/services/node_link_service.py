"""
StructureNode Link Service - Centralized business logic for structure_node link operations

This service implements the business logic for structure_node relationships,
ensuring that only compatible structure_nodes can be linked together.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from database.models import StructureNode, StructureNodeLink
from database.enums import NodeType
from services.change_event_handler import ChangeEventHandler
from utils.logger import get_logger

logger = get_logger(__name__)


class NodeLinkService:
    """Centralized business logic for structure_node link operations"""

    def __init__(self, db: Session):
        """
        Initialize the NodeLinkService.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.event_handler = ChangeEventHandler(db)
        logger.info("NodeLinkService initialized with event handling")

    def create_link(self, link_data: Dict[str, Any]) -> StructureNodeLink:
        """
        Create a new structure_node link with validation.

        Args:
            link_data: Dictionary containing link data

        Returns:
            Created StructureNodeLink instance

        Raises:
            ValueError: If validation fails
        """
        logger.info(
            f"Creating structure_node link: {link_data.get('source_node_id')} -> {link_data.get('target_node_id')}"
        )

        # Validate required fields
        required_fields = ["source_node_id", "target_node_id", "predicate"]
        for field in required_fields:
            if field not in link_data:
                raise ValueError(f"{field} is required")

        source_id = link_data["source_node_id"]
        target_id = link_data["target_node_id"]
        predicate = link_data["predicate"]

        # Validate that source and target are different
        if source_id == target_id:
            raise ValueError("Source and target structure_nodes cannot be the same")

        # Get source and target structure_nodes
        source = (
            self.db.query(StructureNode).filter(StructureNode.id == source_id).first()
        )
        target = (
            self.db.query(StructureNode).filter(StructureNode.id == target_id).first()
        )

        if not source:
            raise ValueError(f"Source structure_node not found: {source_id}")
        if not target:
            raise ValueError(f"Target structure_node not found: {target_id}")

        # Validate same structure_node type constraint
        if source.node_type != target.node_type:
            raise ValueError(
                f"StructureNodes can only be linked to structure_nodes of the same type. "
                f"Source is {source.node_type}, target is {target.node_type}"
            )

        # Check for duplicate links
        existing = (
            self.db.query(StructureNodeLink)
            .filter(
                StructureNodeLink.source_node_id == source_id,
                StructureNodeLink.target_node_id == target_id,
                StructureNodeLink.predicate == predicate,
            )
            .first()
        )

        if existing:
            raise ValueError(
                f"Link already exists: {source_id} -> {target_id} ({predicate})"
            )

        # Create link
        link = StructureNodeLink(
            source_node_id=source_id,
            target_node_id=target_id,
            predicate=predicate,
            predicate_id=link_data.get("predicate_id"),
        )

        try:
            self.db.add(link)
            self.db.commit()
            self.db.refresh(link)

            logger.info(f"Successfully created structure_node link: {link.id}")

            # Fire structure_node link created event using new ChangeEventHandler
            link_dict = self._node_link_to_dict(link)
            from database.enums import RecordType

            self.event_handler.fire_created_event(
                RecordType.STRUCTURE_NODE_LINK, str(link.id), link_dict
            )

            return link

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create structure_node link: {e}")
            raise ValueError(f"Failed to create structure_node link: {e}")

    def update_link(self, link_id: str, link_data: Dict[str, Any]) -> StructureNodeLink:
        """
        Update an existing structure_node link.

        Args:
            link_id: ID of the link to update
            link_data: Dictionary containing updated link data

        Returns:
            Updated StructureNodeLink instance

        Raises:
            ValueError: If validation fails or link not found
        """
        logger.info(f"Updating structure_node link: {link_id}")

        # Get existing link
        link = (
            self.db.query(StructureNodeLink)
            .filter(StructureNodeLink.id == link_id)
            .first()
        )
        if not link:
            raise ValueError(f"StructureNode link not found: {link_id}")

        # Validate updated fields
        if "source_node_id" in link_data or "target_node_id" in link_data:
            source_id = link_data.get("source_node_id", link.source_node_id)
            target_id = link_data.get("target_node_id", link.target_node_id)

            if source_id == target_id:
                raise ValueError("Source and target structure_nodes cannot be the same")

            # Get structure_nodes to validate
            source = (
                self.db.query(StructureNode)
                .filter(StructureNode.id == source_id)
                .first()
            )
            target = (
                self.db.query(StructureNode)
                .filter(StructureNode.id == target_id)
                .first()
            )

            if not source:
                raise ValueError(f"Source structure_node not found: {source_id}")
            if not target:
                raise ValueError(f"Target structure_node not found: {target_id}")

            # Validate same structure_node type constraint
            if source.node_type != target.node_type:
                raise ValueError(
                    f"StructureNodes can only be linked to structure_nodes of the same type. "
                    f"Source is {source.node_type}, target is {target.node_type}"
                )

            # Check for duplicate links (excluding current link)
            predicate = link_data.get("predicate", link.predicate)
            existing = (
                self.db.query(StructureNodeLink)
                .filter(
                    StructureNodeLink.source_node_id == source_id,
                    StructureNodeLink.target_node_id == target_id,
                    StructureNodeLink.predicate == predicate,
                    StructureNodeLink.id != link_id,
                )
                .first()
            )

            if existing:
                raise ValueError(
                    f"Link already exists: {source_id} -> {target_id} ({predicate})"
                )

        # Store old data for event
        old_link_data = self._node_link_to_dict(link)

        # Update fields
        if "source_node_id" in link_data:
            link.source_node_id = link_data["source_node_id"]

        if "target_node_id" in link_data:
            link.target_node_id = link_data["target_node_id"]

        if "predicate" in link_data:
            link.predicate = link_data["predicate"]

        if "predicate_id" in link_data:
            link.predicate_id = link_data["predicate_id"]

        try:
            self.db.commit()
            self.db.refresh(link)

            logger.info(f"Successfully updated structure_node link: {link.id}")

            # Fire structure_node link updated event using new ChangeEventHandler
            new_link_data = self._node_link_to_dict(link)
            from database.enums import RecordType

            self.event_handler.fire_updated_event(
                RecordType.STRUCTURE_NODE_LINK,
                str(link.id),
                old_link_data,
                new_link_data,
            )

            return link

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update structure_node link: {e}")
            raise ValueError(f"Failed to update structure_node link: {e}")

    def delete_link(self, link_id: str) -> bool:
        """
        Delete a structure_node link.

        Args:
            link_id: ID of the link to delete

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If link not found
        """
        logger.info(f"Deleting structure_node link: {link_id}")

        link = (
            self.db.query(StructureNodeLink)
            .filter(StructureNodeLink.id == link_id)
            .first()
        )
        if not link:
            raise ValueError(f"StructureNode link not found: {link_id}")

        # Store link data for event before deletion
        link_data = self._node_link_to_dict(link)

        try:
            self.db.delete(link)
            self.db.commit()

            logger.info(f"Successfully deleted structure_node link: {link_id}")

            # Fire structure_node link deleted event using new ChangeEventHandler
            from database.enums import RecordType

            self.event_handler.fire_deleted_event(
                RecordType.STRUCTURE_NODE_LINK, link_id, link_data
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete structure_node link: {e}")
            raise ValueError(f"Failed to delete structure_node link: {e}")

    def get_link(self, link_id: str) -> Optional[StructureNodeLink]:
        """
        Get a structure_node link by ID.

        Args:
            link_id: ID of the link to retrieve

        Returns:
            StructureNodeLink instance or None if not found
        """
        return (
            self.db.query(StructureNodeLink)
            .filter(StructureNodeLink.id == link_id)
            .first()
        )

    def list_links(
        self,
        source_node_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
        predicate: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StructureNodeLink]:
        """
        List structure_node links with optional filtering.

        Args:
            source_node_id: Optional source structure_node ID to filter by
            target_node_id: Optional target structure_node ID to filter by
            predicate: Optional predicate to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of StructureNodeLink instances
        """
        query = self.db.query(StructureNodeLink)

        if source_node_id:
            query = query.filter(StructureNodeLink.source_node_id == source_node_id)

        if target_node_id:
            query = query.filter(StructureNodeLink.target_node_id == target_node_id)

        if predicate:
            query = query.filter(StructureNodeLink.predicate == predicate)

        return (
            query.order_by(StructureNodeLink.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_links(
        self,
        source_node_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
        predicate: Optional[str] = None,
    ) -> int:
        """
        Count structure_node links with optional filtering.

        Args:
            source_node_id: Optional source structure_node ID to filter by
            target_node_id: Optional target structure_node ID to filter by
            predicate: Optional predicate to filter by

        Returns:
            Count of matching links
        """
        query = self.db.query(StructureNodeLink)

        if source_node_id:
            query = query.filter(StructureNodeLink.source_node_id == source_node_id)

        if target_node_id:
            query = query.filter(StructureNodeLink.target_node_id == target_node_id)

        if predicate:
            query = query.filter(StructureNodeLink.predicate == predicate)

        return query.count()

    def get_node_links(
        self, node_id: str, direction: str = "both"
    ) -> List[StructureNodeLink]:
        """
        Get all links for a specific structure_node.

        Args:
            node_id: StructureNode ID to get links for
            direction: Direction of links to get ("outgoing", "incoming", "both")

        Returns:
            List of StructureNodeLink instances

        Raises:
            ValueError: If direction is invalid
        """
        if direction not in ["outgoing", "incoming", "both"]:
            raise ValueError("direction must be 'outgoing', 'incoming', or 'both'")

        query = self.db.query(StructureNodeLink)

        if direction == "outgoing":
            query = query.filter(StructureNodeLink.source_node_id == node_id)
        elif direction == "incoming":
            query = query.filter(StructureNodeLink.target_node_id == node_id)
        else:  # both
            query = query.filter(
                (StructureNodeLink.source_node_id == node_id)
                | (StructureNodeLink.target_node_id == node_id)
            )

        return query.order_by(StructureNodeLink.created_at.desc()).all()

    def get_linked_nodes(
        self,
        node_id: str,
        direction: str = "both",
        node_type: Optional[NodeType] = None,
    ) -> List[StructureNode]:
        """
        Get all structure_nodes linked to a specific structure_node.

        Args:
            node_id: StructureNode ID to get linked structure_nodes for
            direction: Direction of links ("outgoing", "incoming", "both")
            node_type: Optional structure_node type to filter results by

        Returns:
            List of linked StructureNode instances

        Raises:
            ValueError: If direction is invalid
        """
        if direction not in ["outgoing", "incoming", "both"]:
            raise ValueError("direction must be 'outgoing', 'incoming', or 'both'")

        # Get the links first
        links = self.get_node_links(node_id, direction)

        # Extract linked structure_node IDs
        linked_node_ids = set()
        for link in links:
            if direction == "outgoing":
                linked_node_ids.add(link.target_node_id)
            elif direction == "incoming":
                linked_node_ids.add(link.source_node_id)
            else:  # both
                if link.source_node_id != node_id:
                    linked_node_ids.add(link.source_node_id)
                if link.target_node_id != node_id:
                    linked_node_ids.add(link.target_node_id)

        # Get the actual structure_nodes
        query = self.db.query(StructureNode).filter(
            StructureNode.id.in_(linked_node_ids)
        )

        if node_type:
            query = query.filter(StructureNode.node_type == node_type)

        return query.order_by(StructureNode.title).all()

    def validate_link_compatibility(
        self, source_node_id: str, target_node_id: str
    ) -> bool:
        """
        Validate if two structure_nodes can be linked together.

        Args:
            source_node_id: Source structure_node ID
            target_node_id: Target structure_node ID

        Returns:
            True if structure_nodes can be linked, False otherwise
        """
        if source_node_id == target_node_id:
            return False

        # Get structure_nodes
        source = (
            self.db.query(StructureNode)
            .filter(StructureNode.id == source_node_id)
            .first()
        )
        target = (
            self.db.query(StructureNode)
            .filter(StructureNode.id == target_node_id)
            .first()
        )

        if not source or not target:
            return False

        # Must be same structure_node type
        return source.node_type == target.node_type

    def get_link_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about structure_node links in the system.

        Returns:
            Dictionary containing link statistics
        """
        # Total links
        total_links = self.db.query(StructureNodeLink).count()

        # Links by predicate
        predicate_stats = {}
        predicates = self.db.query(StructureNodeLink.predicate).distinct().all()
        for (predicate,) in predicates:
            count = (
                self.db.query(StructureNodeLink)
                .filter(StructureNodeLink.predicate == predicate)
                .count()
            )
            predicate_stats[predicate] = count

        # Links by structure_node type (source)
        node_type_stats = {}
        for node_type in NodeType:
            count = (
                self.db.query(StructureNodeLink)
                .join(
                    StructureNode, StructureNodeLink.source_node_id == StructureNode.id
                )
                .filter(StructureNode.node_type == node_type)
                .count()
            )
            node_type_stats[node_type.value] = count

        return {
            "total_links": total_links,
            "links_by_predicate": predicate_stats,
            "links_by_source_node_type": node_type_stats,
        }

    def _node_link_to_dict(self, link: StructureNodeLink) -> Dict[str, Any]:
        """Convert a StructureNodeLink instance to a dictionary"""
        return {
            "id": link.id,
            "source_node_id": link.source_node_id,
            "target_node_id": link.target_node_id,
            "predicate": link.predicate,
            "predicate_id": link.predicate_id,
            "created_at": link.created_at.isoformat() if link.created_at else None,
        }
