"""
NodeEvent Handler Service

This service provides centralized event handling for the unified structure_node system.
It creates NodeEvent records for all structure_node-related operations (create, update, delete)
and provides utilities for managing structure_node events.
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import NodeEvent
from utils.logger import get_logger

logger = get_logger(__name__)


class NodeEventHandler:
    """Handler for creating and managing structure_node events."""

    def __init__(self, db: Session):
        """
        Initialize the NodeEventHandler.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_event(
        self,
        event_type: str,
        node_type: str,
        node_id: Optional[str] = None,
        old_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
    ) -> NodeEvent:
        """
        Create a new NodeEvent.

        Args:
            event_type: Type of event (create, update, delete)
            node_type: Type of structure_node (layer, domain, term, structure_node_link)
            node_id: ID of the affected structure_node or structure_node_link
            old_data: Old data dictionary (for update/delete events)
            new_data: New data dictionary (for create/update events)

        Returns:
            The created NodeEvent instance
        """
        try:
            # Create NodeEvent
            event = NodeEvent(
                event_type=event_type,
                node_type=node_type,
                node_id=node_id,
                old_data=old_data,
                new_data=new_data,
                timestamp=datetime.now(timezone.utc),
                processed=False,
            )

            self.db.add(event)
            self.db.commit()

            logger.debug(
                f"Created NodeEvent: {event_type} {node_type} (id: {event.id}, node_id: {node_id})"
            )
            return event

        except Exception as e:
            logger.error(f"Failed to create NodeEvent: {e}")
            self.db.rollback()
            raise

    def fire_node_event(
        self,
        event_type: str,
        node_type: str,
        node_id: Optional[str] = None,
        old_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
    ) -> NodeEvent:
        """
        Fire unified structure_node event.

        Args:
            event_type: Type of event (create, update, delete)
            node_type: Type of structure_node (layer, domain, term, structure_node_link)
            node_id: ID of the affected structure_node or structure_node_link
            old_data: Old data dictionary (for update/delete events)
            new_data: New data dictionary (for create/update events)

        Returns:
            The created NodeEvent
        """
        return self.create_event(event_type, node_type, node_id, old_data, new_data)

    def fire_node_created_event(
        self, node_type: str, node_id: str, node_data: Dict[str, Any]
    ) -> NodeEvent:
        """
        Fire a structure_node created event.

        Args:
            node_type: Type of structure_node (layer, domain, term, structure_node_link)
            node_id: ID of the created structure_node or structure_node_link
            node_data: The created structure_node data

        Returns:
            The created NodeEvent
        """
        return self.fire_node_event(
            "create", node_type, node_id=node_id, old_data=None, new_data=node_data
        )

    def fire_node_updated_event(
        self,
        node_type: str,
        node_id: str,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> NodeEvent:
        """
        Fire a structure_node updated event.

        Args:
            node_type: Type of structure_node (layer, domain, term, structure_node_link)
            node_id: ID of the updated structure_node or structure_node_link
            old_data: The original structure_node data
            new_data: The updated structure_node data

        Returns:
            The created NodeEvent
        """
        return self.fire_node_event(
            "update", node_type, node_id=node_id, old_data=old_data, new_data=new_data
        )

    def fire_node_deleted_event(
        self, node_type: str, node_id: str, node_data: Dict[str, Any]
    ) -> NodeEvent:
        """
        Fire a structure_node deleted event.

        Args:
            node_type: Type of structure_node (layer, domain, term, structure_node_link)
            node_id: ID of the deleted structure_node or structure_node_link
            node_data: The deleted structure_node data

        Returns:
            The created NodeEvent
        """
        return self.fire_node_event(
            "delete", node_type, node_id=node_id, old_data=node_data, new_data=None
        )

    def get_unprocessed_events(self, limit: int = 100) -> list[NodeEvent]:
        """
        Get unprocessed structure_node events.

        Args:
            limit: Maximum number of events to retrieve

        Returns:
            List of unprocessed NodeEvent objects
        """
        events: list[NodeEvent] = (
            self.db.query(NodeEvent)
            .filter(~NodeEvent.processed)
            .order_by(NodeEvent.timestamp.asc())
            .limit(limit)
            .all()
        )
        return events

    def get_events_for_node(self, node_id: str, limit: int = 100) -> list[NodeEvent]:
        """
        Get events for a specific structure_node.

        Args:
            node_id: ID of the structure_node to get events for
            limit: Maximum number of events to retrieve

        Returns:
            List of NodeEvent objects for the specified structure_node
        """
        events: list[NodeEvent] = (
            self.db.query(NodeEvent)
            .filter(NodeEvent.node_id == node_id)
            .order_by(NodeEvent.timestamp.desc())
            .limit(limit)
            .all()
        )
        return events

    def mark_event_processed(self, event_id: int) -> bool:
        """
        Mark an event as processed.

        Args:
            event_id: The ID of the event to mark as processed

        Returns:
            True if successful, False otherwise
        """
        try:
            event: Optional[NodeEvent] = self.db.query(NodeEvent).filter(NodeEvent.id == event_id).first()
            if event:
                event.processed = True
                self.db.commit()
                logger.debug(f"Event {event_id} marked as processed")
                return True
            else:
                logger.warning(f"Event {event_id} not found")
                return False
        except Exception as e:
            logger.error(f"Failed to mark event {event_id} as processed: {e}")
            self.db.rollback()
            return False

    def get_event_stats(self) -> Dict[str, Any]:
        """
        Get statistics about structure_node events.

        Returns:
            Dictionary with event statistics
        """
        total_events = self.db.query(NodeEvent).count()
        processed_events = (
            self.db.query(NodeEvent).filter(NodeEvent.processed).count()
        )
        unprocessed_events = total_events - processed_events

        # Events by type
        event_types: Dict[str, int] = {}
        for event_type, count in (
            self.db.query(NodeEvent.event_type, func.count(NodeEvent.id))
            .group_by(NodeEvent.event_type)
            .all()
        ):
            event_types[event_type] = count

        # Events by structure_node type
        node_types: Dict[str, int] = {}
        for node_type, count in (
            self.db.query(NodeEvent.node_type, func.count(NodeEvent.id))
            .group_by(NodeEvent.node_type)
            .all()
        ):
            node_types[node_type] = count

        return {
            "total_events": total_events,
            "processed_events": processed_events,
            "unprocessed_events": unprocessed_events,
            "events_by_type": event_types,
            "events_by_node_type": node_types,
        }
