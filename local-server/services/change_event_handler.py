"""
ChangeEvent Handler Service

This service provides centralized event handling for the unified change event system.
It creates ChangeEvent records for all record-related operations (create, update, delete)
and provides utilities for managing change events across all record types.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import ChangeEvent
from database.enums import RecordType
from utils.logger import get_logger

logger = get_logger(__name__)


class ChangeEventHandler:
    """Handler for creating and managing change events across all record types."""

    def __init__(self, db: Session):
        """
        Initialize the ChangeEventHandler.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_event(
        self,
        event_type: str,
        record_type: RecordType,
        record_id: Optional[str] = None,
        old_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
    ) -> ChangeEvent:
        """
        Create a new ChangeEvent.

        Args:
            event_type: Type of event (create, update, delete)
            record_type: Type of record (RecordType enum)
            record_id: ID of the affected record
            old_data: Old data dictionary (for update/delete events)
            new_data: New data dictionary (for create/update events)

        Returns:
            The created ChangeEvent instance
        """
        try:
            # Create ChangeEvent - RecordTypeColumn will handle enum conversion automatically
            event = ChangeEvent(
                event_type=event_type,
                record_type=record_type,
                record_id=record_id,
                old_data=old_data,
                new_data=new_data,
                timestamp=datetime.now(timezone.utc),
                processed=False,
            )

            self.db.add(event)
            self.db.commit()

            logger.debug(
                f"Created ChangeEvent: {event_type} {record_type.value} (id: {event.id}, record_id: {record_id})"
            )
            return event

        except Exception as e:
            logger.error(f"Failed to create ChangeEvent: {e}")
            self.db.rollback()
            raise

    def fire_change_event(
        self,
        event_type: str,
        record_type: RecordType,
        record_id: Optional[str] = None,
        old_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
    ) -> ChangeEvent:
        """
        Fire unified change event.

        Args:
            event_type: Type of event (create, update, delete)
            record_type: Type of record (RecordType enum)
            record_id: ID of the affected record
            old_data: Old data dictionary (for update/delete events)
            new_data: New data dictionary (for create/update events)

        Returns:
            The created ChangeEvent
        """
        return self.create_event(event_type, record_type, record_id, old_data, new_data)

    def fire_created_event(
        self, record_type: RecordType, record_id: str, record_data: Dict[str, Any]
    ) -> ChangeEvent:
        """
        Fire a created event with type safety.

        Args:
            record_type: Type of record (RecordType enum)
            record_id: ID of the created record
            record_data: The created record data

        Returns:
            The created ChangeEvent
        """
        return self.create_event(
            "create",
            record_type,
            record_id=record_id,
            old_data=None,
            new_data=record_data,
        )

    def fire_updated_event(
        self,
        record_type: RecordType,
        record_id: str,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> ChangeEvent:
        """
        Fire an updated event with type safety.

        Args:
            record_type: Type of record (RecordType enum)
            record_id: ID of the updated record
            old_data: The old record data
            new_data: The updated record data

        Returns:
            The created ChangeEvent
        """
        return self.create_event(
            "update",
            record_type,
            record_id=record_id,
            old_data=old_data,
            new_data=new_data,
        )

    def fire_deleted_event(
        self, record_type: RecordType, record_id: str, record_data: Dict[str, Any]
    ) -> ChangeEvent:
        """
        Fire a deleted event with type safety.

        Args:
            record_type: Type of record (RecordType enum)
            record_id: ID of the deleted record
            record_data: The deleted record data

        Returns:
            The created ChangeEvent
        """
        return self.create_event(
            "delete",
            record_type,
            record_id=record_id,
            old_data=record_data,
            new_data=None,
        )

    # Convenience methods for specific record types
    def fire_predicate_created_event(
        self, predicate_id: str, predicate_data: Dict[str, Any]
    ) -> ChangeEvent:
        """Convenience method for predicate creation events."""
        return self.fire_created_event(
            RecordType.PREDICATE, predicate_id, predicate_data
        )

    def fire_structure_node_created_event(
        self, node_id: str, node_data: Dict[str, Any]
    ) -> ChangeEvent:
        """Convenience method for structure node creation events."""
        return self.fire_created_event(RecordType.STRUCTURE_NODE, node_id, node_data)

    def fire_structure_node_link_created_event(
        self, link_id: str, link_data: Dict[str, Any]
    ) -> ChangeEvent:
        """Convenience method for structure node link creation events."""
        return self.fire_created_event(
            RecordType.STRUCTURE_NODE_LINK, link_id, link_data
        )

    def get_unprocessed_events(
        self, record_type: Optional[RecordType] = None, limit: int = 100
    ) -> List[ChangeEvent]:
        """
        Get unprocessed change events, optionally filtered by record type.

        Args:
            record_type: Optional filter by record type
            limit: Maximum number of events to retrieve

        Returns:
            List of unprocessed ChangeEvent objects
        """
        query = self.db.query(ChangeEvent).filter(ChangeEvent.processed == False)

        if record_type is not None:
            query = query.filter(ChangeEvent.record_type == record_type)

        return query.order_by(ChangeEvent.timestamp.asc()).limit(limit).all()

    def get_events_for_record(
        self, record_id: str, limit: int = 100
    ) -> List[ChangeEvent]:
        """
        Get events for a specific record.

        Args:
            record_id: ID of the record to get events for
            limit: Maximum number of events to retrieve

        Returns:
            List of ChangeEvent objects for the specified record
        """
        return (
            self.db.query(ChangeEvent)
            .filter(ChangeEvent.record_id == record_id)
            .order_by(ChangeEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

    def mark_event_processed(self, event_id: int) -> bool:
        """
        Mark an event as processed.

        Args:
            event_id: The ID of the event to mark as processed

        Returns:
            True if successful, False otherwise
        """
        try:
            event = (
                self.db.query(ChangeEvent).filter(ChangeEvent.id == event_id).first()
            )
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
        Get statistics about change events.

        Returns:
            Dictionary with event statistics
        """
        total_events = self.db.query(ChangeEvent).count()
        processed_events = (
            self.db.query(ChangeEvent).filter(ChangeEvent.processed == True).count()
        )
        unprocessed_events = total_events - processed_events

        # Events by type
        event_types = {}
        for event_type, count in (
            self.db.query(ChangeEvent.event_type, func.count(ChangeEvent.id))
            .group_by(ChangeEvent.event_type)
            .all()
        ):
            event_types[event_type] = count

        # Events by record type
        record_types = {}
        for record_type, count in (
            self.db.query(ChangeEvent.record_type, func.count(ChangeEvent.id))
            .group_by(ChangeEvent.record_type)
            .all()
        ):
            record_types[
                record_type.value if hasattr(record_type, "value") else record_type
            ] = count

        return {
            "total_events": total_events,
            "processed_events": processed_events,
            "unprocessed_events": unprocessed_events,
            "events_by_type": event_types,
            "events_by_record_type": record_types,
        }


# Legacy alias for backwards compatibility during transition
NodeEventHandler = ChangeEventHandler
