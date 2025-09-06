import threading
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from database.models import ChangeEvent
from database.enums import RecordType
from utils.logger import get_logger

# Global reference to the active EventProcessor for dataset switching
_global_event_processor: Optional['EventProcessor'] = None


def get_global_event_processor() -> Optional['EventProcessor']:
    """Get the global EventProcessor instance."""
    return _global_event_processor


def set_global_event_processor(processor: Optional['EventProcessor']):
    """Set the global EventProcessor instance."""
    global _global_event_processor
    _global_event_processor = processor


class EventProcessor:
    """
    Event processor that handles ChangeEvent processing.
    
    This processor handles the new unified ChangeEvent system for processing
    change events (create, update, delete) for all record types including
    structure_nodes, structure_node_links, and predicates.
    """
    
    def __init__(self, database_url: str, poll_interval: float = 1.0, max_events: int = 100):
        """
        Initialize the EventProcessor.
        
        Args:
            database_url: The database URL to connect to
            poll_interval: Polling interval in seconds for event checking
            max_events: Maximum number of events to process per batch
        """
        self.database_url = database_url
        self.poll_interval = poll_interval
        self.max_events = max_events
        self._stop_event = threading.Event()
        self._thread = None
        self._cleanup_thread = None
        
        # Thread-local storage for engine and session
        self._thread_local = threading.local()
        
        # Ensure logger is always set
        self.logger = get_logger(__name__)
        
        # Track last processed event ID for efficiency
        self._last_processed_id = 0
        self._initialize_last_processed_id()
        
        # Register as global event processor for dataset switching
        set_global_event_processor(self)

    def _get_thread_session(self):
        """Get or create a thread-local database session."""
        if not hasattr(self._thread_local, 'session'):
            from database.utils import get_engine
            
            # Create a fresh engine for this thread (but don't re-initialize with init_db)
            engine = get_engine(
                database_url=self.database_url,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                    "isolation_level": None,
                }
            )
            
            # Note: We skip init_db() here because:
            # 1. The main application already initialized the database and SQLite extensions
            # 2. Calling init_db() on every poll causes repeated extension loading
            # 3. The engine from get_engine() should be sufficient for basic SQL operations
            
            # Create session factory
            SessionLocal = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=engine, 
                expire_on_commit=False
            )
            
            self._thread_local.session = SessionLocal
            self._thread_local.engine = engine
            
        return self._thread_local.session

    def _initialize_last_processed_id(self):
        """Initialize the last processed event ID from the database."""
        try:
            SessionLocal = self._get_thread_session()
            with SessionLocal() as db:
                result = db.execute(text("""
                    SELECT id FROM change_events 
                    WHERE processed = 1 
                    ORDER BY id DESC 
                    LIMIT 1
                """)).fetchone()
                
                if result:
                    self._last_processed_id = result[0]
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
        
        # Clean up thread-local resources
        self._cleanup_thread_local_resources()
        
        # Clear global reference if we're the current global processor
        if get_global_event_processor() is self:
            set_global_event_processor(None)

    def switch_dataset(self, new_database_url: str):
        """
        Switch to a different dataset database.
        
        Args:
            new_database_url: The new database URL to connect to
        """
        self.logger.info(f"[EventProcessor] Switching dataset from {self.database_url} to {new_database_url}")
        
        # Stop current processing
        self.stop()
        
        # Update database URL
        self.database_url = new_database_url
        
        # Reset last processed ID for new database
        self._last_processed_id = 0
        self._initialize_last_processed_id()
        
        # Restart processing with new database
        self.start()
        self.logger.info("[EventProcessor] Dataset switch completed")

    def _cleanup_thread_local_resources(self):
        """Clean up any thread-local database connections."""
        try:
            if hasattr(self._thread_local, 'engine'):
                self.logger.debug("[EventProcessor] Disposing of thread-local engine")
                self._thread_local.engine.dispose()
                delattr(self._thread_local, 'engine')
            
            if hasattr(self._thread_local, 'session'):
                self.logger.debug("[EventProcessor] Clearing thread-local session")
                delattr(self._thread_local, 'session')
                
        except Exception as e:
            self.logger.warning(f"[EventProcessor] Error cleaning up thread-local resources: {e}")

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
        """Process unprocessed ChangeEvents."""
        try:
            SessionLocal = self._get_thread_session()
            with SessionLocal() as db:
                # Get unprocessed ChangeEvents since last processed ID
                events = db.execute(text("""
                    SELECT id, event_type, record_type, record_id, old_data, new_data, timestamp
                    FROM change_events 
                    WHERE processed = 0 AND id > :last_id
                    ORDER BY id ASC 
                    LIMIT :max_events
                """), {"last_id": self._last_processed_id, "max_events": self.max_events}).fetchall()
                
                for event in events:
                    try:
                        event_id, event_type, record_type, record_id, old_data, new_data, timestamp = event
                        
                        self._process_single_event(event_id, event_type, record_type, record_id, old_data, new_data, timestamp)
                        
                        # Mark as processed
                        db.execute(text("UPDATE change_events SET processed = 1 WHERE id = :event_id"), 
                                   {"event_id": event_id})
                        
                        self._last_processed_id = event_id
                        
                    except Exception as e:
                        self.logger.error(f"[EventProcessor] Failed to process event {event_id}: {e}")
                        # Continue processing other events even if one fails
                
                # Commit all changes
                db.commit()
        except Exception as e:
            self.logger.error(f"[EventProcessor] Error in process_events: {e}")

    def _process_single_event(self, event_id, event_type, record_type, record_id, old_data, new_data, timestamp):
        """Process a single ChangeEvent using record_type routing."""
        self.logger.debug(f"[EventProcessor] Processing ChangeEvent {event_id}: {event_type} {record_type}")
        
        # Convert string back to enum if needed (for database compatibility)
        if isinstance(record_type, str):
            try:
                record_type = RecordType(record_type)
            except ValueError:
                self.logger.warning(f"[EventProcessor] Unknown record_type: {record_type}")
                return
        
        # Route to specific handler based on record type
        handler_name = f"process_{record_type.value}_event"
        handler = getattr(self, handler_name, None)
        
        if handler:
            # Create a simple event object
            event_obj = type('Event', (), {
                'id': event_id,
                'event_type': event_type,
                'record_type': record_type,
                'record_id': record_id,
                'old_data': old_data,
                'new_data': new_data,
                'timestamp': timestamp
            })()
            handler(event_obj)
        else:
            self.logger.warning(f"[EventProcessor] No handler for record_type: {record_type.value}")

    def process_structure_node_event(self, event):
        """Process structure_node-related events (layers, domains, terms)."""
        self.logger.info(f"[EventProcessor] Processing structure_node event: {event.event_type} id={event.id}")
        # Enhanced logic that can distinguish between layer/domain/term from event data
        # Can inspect event.new_data or event.old_data to determine specific node_type if needed

    def process_structure_node_link_event(self, event):
        """Process structure_node_link-related events."""
        self.logger.info(f"[EventProcessor] Processing structure_node_link event: {event.event_type} id={event.id}")
        # Add structure_node link-specific processing logic here

    def process_predicate_event(self, event):
        """Process predicate-related events."""
        self.logger.info(f"[EventProcessor] Processing predicate event: {event.event_type} id={event.id}")
        # New predicate-specific processing logic here

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
        
        try:
            SessionLocal = self._get_thread_session()
            with SessionLocal() as db:
                # Delete old processed events
                result = db.execute(text("""
                    DELETE FROM change_events 
                    WHERE processed = 1 AND timestamp < :cutoff
                """), {"cutoff": cutoff.isoformat()})
                
                deleted_count = result.rowcount
                db.commit()
                
                if deleted_count > 0:
                    self.logger.info(f"[EventProcessor] Deleted {deleted_count} old processed events.")
        except Exception as e:
            self.logger.error(f"[EventProcessor] Error in cleanup_old_events: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get event processor statistics."""
        try:
            SessionLocal = self._get_thread_session()
            with SessionLocal() as db:
                # Get current unprocessed count
                unprocessed_result = db.execute(text("""
                    SELECT COUNT(*) FROM change_events WHERE processed = 0
                """)).fetchone()
                
                # Get current processed count
                processed_result = db.execute(text("""
                    SELECT COUNT(*) FROM change_events WHERE processed = 1
                """)).fetchone()
                
                return {
                    "unprocessed_count": unprocessed_result[0] if unprocessed_result else 0,
                    "processed_count": processed_result[0] if processed_result else 0,
                    "last_processed_id": self._last_processed_id,
                    "is_running": self._thread is not None and self._thread.is_alive(),
                    "table_exists": True
                }
        except Exception as e:
            self.logger.error(f"[EventProcessor] Error in get_stats: {e}")
            return {
                "unprocessed_count": 0,
                "processed_count": 0,
                "last_processed_id": self._last_processed_id,
                "is_running": self._thread is not None and self._thread.is_alive(),
                "table_exists": False,
                "error": str(e)
            }
