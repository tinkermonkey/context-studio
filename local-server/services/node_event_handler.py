"""
NodeEvent Handler Service

This service provides centralized event handling for the unified node system.
It creates NodeEvent records for all node-related operations (create, update, delete)
and provides utilities for managing node events.
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import NodeEvent
from utils.logger import get_logger

logger = get_logger(__name__)


class NodeEventHandler:
    """Handler for creating and managing node events."""
    
    def __init__(self, db: Session):
        """
        Initialize the NodeEventHandler.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        
    def create_event(self, event_type: str, node_type: str, old_data: Optional[Dict[str, Any]] = None, new_data: Optional[Dict[str, Any]] = None) -> NodeEvent:
        """
        Create a new NodeEvent.
        
        Args:
            event_type: Type of event (create, update, delete)
            node_type: Type of node (layer, domain, term, node_link)
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
                old_data=old_data,
                new_data=new_data,
                timestamp=datetime.now(timezone.utc),
                processed=False
            )
            
            self.db.add(event)
            self.db.commit()
            
            logger.debug(f"Created NodeEvent: {event_type} {node_type} (id: {event.id})")
            return event
            
        except Exception as e:
            logger.error(f"Failed to create NodeEvent: {e}")
            self.db.rollback()
            raise
    
    def fire_node_event(self, event_type: str, node_type: str, old_data: Optional[Dict[str, Any]] = None, new_data: Optional[Dict[str, Any]] = None) -> NodeEvent:
        """
        Fire unified node event.
        
        Args:
            event_type: Type of event (create, update, delete)
            node_type: Type of node (layer, domain, term, node_link)
            old_data: Old data dictionary (for update/delete events)
            new_data: New data dictionary (for create/update events)
            
        Returns:
            The created NodeEvent
        """
        return self.create_event(event_type, node_type, old_data, new_data)
    
    def fire_node_created_event(self, node_type: str, node_data: Dict[str, Any]) -> NodeEvent:
        """
        Fire a node created event.
        
        Args:
            node_type: Type of node (layer, domain, term, node_link)
            node_data: The created node data
            
        Returns:
            The created NodeEvent
        """
        return self.fire_node_event('create', node_type, old_data=None, new_data=node_data)
    
    def fire_node_updated_event(self, node_type: str, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> NodeEvent:
        """
        Fire a node updated event.
        
        Args:
            node_type: Type of node (layer, domain, term, node_link)
            old_data: The original node data
            new_data: The updated node data
            
        Returns:
            The created NodeEvent
        """
        return self.fire_node_event('update', node_type, old_data=old_data, new_data=new_data)
    
    def fire_node_deleted_event(self, node_type: str, node_data: Dict[str, Any]) -> NodeEvent:
        """
        Fire a node deleted event.
        
        Args:
            node_type: Type of node (layer, domain, term, node_link)
            node_data: The deleted node data
            
        Returns:
            The created NodeEvent
        """
        return self.fire_node_event('delete', node_type, old_data=node_data, new_data=None)
    
    def get_unprocessed_events(self, limit: int = 100) -> list[NodeEvent]:
        """
        Get unprocessed node events.
        
        Args:
            limit: Maximum number of events to retrieve
            
        Returns:
            List of unprocessed NodeEvent objects
        """
        return (
            self.db.query(NodeEvent)
            .filter(NodeEvent.processed == False)
            .order_by(NodeEvent.timestamp.asc())
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
            event = self.db.query(NodeEvent).filter(NodeEvent.id == event_id).first()
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
        Get statistics about node events.
        
        Returns:
            Dictionary with event statistics
        """
        total_events = self.db.query(NodeEvent).count()
        processed_events = self.db.query(NodeEvent).filter(NodeEvent.processed == True).count()
        unprocessed_events = total_events - processed_events
        
        # Events by type
        event_types = {}
        for event_type, count in self.db.query(NodeEvent.event_type, func.count(NodeEvent.id)).group_by(NodeEvent.event_type).all():
            event_types[event_type] = count
        
        # Events by node type
        node_types = {}
        for node_type, count in self.db.query(NodeEvent.node_type, func.count(NodeEvent.id)).group_by(NodeEvent.node_type).all():
            node_types[node_type] = count
        
        return {
            'total_events': total_events,
            'processed_events': processed_events,
            'unprocessed_events': unprocessed_events,
            'events_by_type': event_types,
            'events_by_node_type': node_types
        }
