import sqlite3
import threading
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any

from utils.logger import get_logger


class EventProcessor:
    """
    Event processor that handles NodeEvent processing.
    
    This processor handles the new unified NodeEvent system for processing
    node-related events (create, update, delete) for all node types.
    """
    
    def __init__(self, db_path: str, poll_interval: float = 1.0, max_events: int = 100):
        """
        Initialize the EventProcessor.
        
        Args:
            db_path: Database file path
            poll_interval: Polling interval in seconds for event checking
            max_events: Maximum number of events to process per batch
        """
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.max_events = max_events
        self._stop_event = threading.Event()
        self._thread = None
        self._cleanup_thread = None
        
        # Ensure logger is always set
        self.logger = get_logger(__name__)
        
        # Track last processed event ID for efficiency
        self._last_processed_id = 0
        self._initialize_last_processed_id()

    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)
        
    def _initialize_last_processed_id(self):
        """Initialize the last processed event ID from the database."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM node_events 
                WHERE processed = 1 
                ORDER BY id DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                self._last_processed_id = result[0]
            conn.close()
        except Exception as e:
            self.logger.warning(f"Failed to initialize last processed ID: {e}")

    def start(self):
        """Start the event processing loop in a background thread."""
        self.logger.debug("[EventProcessor] start() called")
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self.logger.debug("[EventProcessor] main thread started")
            self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self._cleanup_thread.start()
            self.logger.debug("[EventProcessor] cleanup thread started")

    def stop(self):
        """Stop the event processing loop."""
        self.logger.debug("[EventProcessor] stop() called")
        self._stop_event.set()
        if self._thread:
            self.logger.debug("[EventProcessor] joining main thread...")
            self._thread.join(timeout=5)
            self.logger.debug("[EventProcessor] main thread joined")
        if self._cleanup_thread:
            self.logger.debug("[EventProcessor] joining cleanup thread...")
            self._cleanup_thread.join(timeout=5)
            self.logger.debug("[EventProcessor] cleanup thread joined")

    def _run(self):
        """Main event processing loop."""
        self.logger.debug("[EventProcessor] _run() loop starting")
        while not self._stop_event.is_set():
            try:
                self.logger.debug("[EventProcessor] processing events...")
                self.process_events()
            except Exception as e:
                self.logger.error(f"[EventProcessor] Error: {e}")
            time.sleep(self.poll_interval)
        self.logger.debug("[EventProcessor] _run() loop exiting")

    def process_events(self):
        """Process unprocessed NodeEvents."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get unprocessed NodeEvents since last processed ID
            cursor.execute("""
                SELECT id, event_type, node_type, old_data, new_data, timestamp
                FROM node_events 
                WHERE processed = 0 AND id > ?
                ORDER BY id ASC 
                LIMIT ?
            """, (self._last_processed_id, self.max_events))
            
            events = cursor.fetchall()
            
            for event in events:
                try:
                    event_id, event_type, node_type, old_data, new_data, timestamp = event
                    
                    # Extract node_id from new_data or old_data JSON
                    node_id = None
                    if new_data:
                        try:
                            new_data_dict = json.loads(new_data)
                            node_id = new_data_dict.get('id')
                        except (json.JSONDecodeError, AttributeError):
                            pass
                    if not node_id and old_data:
                        try:
                            old_data_dict = json.loads(old_data)
                            node_id = old_data_dict.get('id')
                        except (json.JSONDecodeError, AttributeError):
                            pass
                    
                    self._process_single_event(event_id, event_type, node_type, node_id, old_data, new_data, timestamp)
                    
                    # Mark as processed
                    cursor.execute("UPDATE node_events SET processed = 1 WHERE id = ?", (event_id,))
                    conn.commit()
                    
                    self._last_processed_id = event_id
                    
                except Exception as e:
                    self.logger.error(f"[EventProcessor] Failed to process event {event_id}: {e}")
                    conn.rollback()
                    
        finally:
            conn.close()

    def _process_single_event(self, event_id, event_type, node_type, node_id, old_data, new_data, timestamp):
        """Process a single NodeEvent."""
        self.logger.debug(f"[EventProcessor] Processing NodeEvent {event_id}: {event_type} {node_type}")
        
        # Route to specific handler based on node type
        handler = getattr(self, f"process_{node_type}_event", None)
        
        if handler:
            # Create a simple event object
            event_obj = type('Event', (), {
                'id': event_id,
                'event_type': event_type,
                'node_type': node_type,
                'node_id': node_id,
                'old_data': old_data,
                'new_data': new_data,
                'timestamp': timestamp
            })()
            handler(event_obj)
        else:
            self.logger.warning(f"[EventProcessor] No handler for node_type: {node_type}")

    def process_layer_event(self, event):
        """Process layer-related events."""
        self.logger.info(f"[EventProcessor] Processing layer event: {event.event_type} id={event.id}")
        # Add layer-specific processing logic here

    def process_domain_event(self, event):
        """Process domain-related events."""
        self.logger.info(f"[EventProcessor] Processing domain event: {event.event_type} id={event.id}")
        # Add domain-specific processing logic here

    def process_term_event(self, event):
        """Process term-related events."""
        self.logger.info(f"[EventProcessor] Processing term event: {event.event_type} id={event.id}")
        # Add term-specific processing logic here

    def process_node_link_event(self, event):
        """Process node link-related events."""
        self.logger.info(f"[EventProcessor] Processing node_link event: {event.event_type} id={event.id}")
        # Add node link-specific processing logic here

    def _cleanup_loop(self):
        """Background loop for cleaning up old processed events."""
        self.logger.debug("[EventProcessor] _cleanup_loop() starting")
        while not self._stop_event.is_set():
            try:
                self.logger.debug("[EventProcessor] cleanup_old_events() running...")
                self.cleanup_old_events()
            except Exception as e:
                self.logger.error(f"[EventProcessor] Cleanup error: {e}")
            # Run once per day
            time.sleep(24 * 60 * 60)
        self.logger.debug("[EventProcessor] _cleanup_loop() exiting")

    def cleanup_old_events(self, hours_to_keep: int = 48):
        """
        Clean up old processed events.
        
        Args:
            hours_to_keep: Number of hours to keep processed events (default: 48)
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_to_keep)
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete old processed events
            cursor.execute("""
                DELETE FROM node_events 
                WHERE processed = 1 AND timestamp < ?
            """, (cutoff.isoformat(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                self.logger.info(f"[EventProcessor] Deleted {deleted_count} old processed events.")
                
        except Exception as e:
            self.logger.error(f"[EventProcessor] Failed to cleanup old events: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get event processor statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get current unprocessed count
            cursor.execute("SELECT COUNT(*) FROM node_events WHERE processed = 0")
            unprocessed_count = cursor.fetchone()[0]
            
            # Get total processed count
            cursor.execute("SELECT COUNT(*) FROM node_events WHERE processed = 1")
            processed_count = cursor.fetchone()[0]
            
            return {
                'unprocessed_events': unprocessed_count,
                'processed_events': processed_count,
                'last_processed_id': self._last_processed_id,
                'running': self._thread is not None and self._thread.is_alive()
            }
            
        finally:
            conn.close()
