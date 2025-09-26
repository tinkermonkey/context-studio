import threading
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from sqlalchemy import text

from database.enums import RecordType
from database.utils import (
    get_database_manager
)
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
    Event processor that handles ChangeEvent processing with optimized database connections.
    
    This processor handles the unified ChangeEvent system for processing
    change events (create, update, delete) for all record types including
    structure_nodes, structure_node_links, and predicates.
    
    Features:
    - Leverages DatabaseManager for optimized connection pooling
    - Environment-aware database configuration
    - Advanced performance monitoring integration
    - Coordinated resource lifecycle management
    - Integrated version management for entity changes
    """
    
    def __init__(self, 
                 database_url: str, 
                 poll_interval: float = 1.0, 
                 max_events: int = 100,
                 version_manager = None,
                 working_tree_manager = None):
        """
        Initialize the EventProcessor.
        
        Args:
            database_url: The database URL to connect to
            poll_interval: Polling interval in seconds for event checking
            max_events: Maximum number of events to process per batch
            version_manager: Optional VersionManager instance for version creation
            working_tree_manager: Optional WorkingTreeManager instance for working tree management
        """
        self.database_url = database_url
        self.poll_interval = poll_interval
        self.max_events = max_events
        self.version_manager = version_manager  # Will be injected for version creation
        self.working_tree_manager = working_tree_manager  # Will be injected for working tree management
        
        self._stop_event = threading.Event()
        self._thread = None
        self._cleanup_thread = None
        
        # Database Manager integration
        self.db_manager = get_database_manager()
        self.engine_id = f"event_processor_{id(self)}"
        
        # Ensure logger is always set
        self.logger = get_logger(__name__)
        
        # Track last processed event ID for efficiency
        self._last_processed_id = 0
        self._initialize_last_processed_id()
        
        # Performance tracking
        self._events_processed = 0
        self._last_performance_log = datetime.now()
        self._performance_log_interval = timedelta(minutes=5)
        
        # Register as global event processor for dataset switching
        set_global_event_processor(self)
        
        self.logger.info("EventProcessor initialized")
    
    def _get_optimized_session(self):
        """Get an optimized database session using Database Manager."""
        # Ensure we have an optimized engine for event processing
        if self.engine_id not in self.db_manager._engines:
            try:
                self.db_manager.create_optimized_engine(self.database_url, self.engine_id)
            except Exception as e:
                self.logger.error(f"Failed to create optimized engine '{self.engine_id}': {e}")
                raise

        try:
            return self.db_manager.get_optimized_session(self.engine_id, self.database_url)
        except Exception as e:
            self.logger.error(f"Failed to get optimized session for '{self.engine_id}': {e}")
            raise
    
    def _initialize_last_processed_id(self):
        """Initialize the last processed event ID from the database."""
        try:
            with self._get_optimized_session() as db:
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
            # Start from 0 if we can't get the last processed ID
            self._last_processed_id = 0

    def start(self):
        """Start the event processing loop in a background thread."""
        self.logger.debug("[EventProcessor] start() called")
        if self._thread is None or not self._thread.is_alive():
            # Create optimized engine before starting threads
            self.db_manager.create_optimized_engine(self.database_url, self.engine_id)
            
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
        old_engine_id = self.engine_id
        self.database_url = new_database_url
        self.engine_id = f"event_processor_{id(self)}_{int(time.time())}"  # New unique ID
        
        # Reset last processed ID for new database
        self._last_processed_id = 0
        self._initialize_last_processed_id()
        
        # Clean up old engine (optional, as Database Manager handles cleanup)
        # The old engine will be cleaned up by the Database Manager
        
        # Restart processing with new database
        self.start()
        self.logger.info("[EventProcessor] Dataset switch completed")

    def _run(self):
        """Main event processing loop with performance monitoring."""
        self.logger.debug("[EventProcessor] _run() loop starting")
        
        while not self._stop_event.is_set():
            try:
                events_processed = self.process_events()
                self._events_processed += events_processed
                
                # Log performance metrics periodically
                if datetime.now() - self._last_performance_log >= self._performance_log_interval:
                    self._log_performance_metrics()
                    
            except Exception as e:
                self.logger.error(f"[EventProcessor] Error: {e}")
                
            time.sleep(self.poll_interval)
            
        self.logger.debug("[EventProcessor] _run() loop exiting")
    
    def _log_performance_metrics(self):
        """Log performance metrics using Database Manager data."""
        try:
            # Get Database Manager metrics
            db_metrics = self.db_manager._get_metrics_summary()
            
            self.logger.info(
                f"[EventProcessor] Performance: "
                f"events_processed={self._events_processed}, "
                f"db_queries={db_metrics.get('total_queries_executed', 0)}, "
                f"avg_query_time={db_metrics.get('avg_query_time_ms', 0):.2f}ms, "
                f"pool_efficiency={db_metrics.get('pool_efficiency_percent', 0):.1f}%"
            )
            
            self._last_performance_log = datetime.now()
            
        except Exception as e:
            self.logger.warning(f"[EventProcessor] Failed to log performance metrics: {e}")

    def process_events(self) -> int:
        """
        Process unprocessed ChangeEvents using Database Manager.
        
        Returns:
            Number of events processed
        """
        events_processed = 0
        
        try:
            with self._get_optimized_session() as db:
                # Get unprocessed ChangeEvents since last processed ID
                events = db.execute(text("""
                    SELECT id, event_type, record_type, record_id, old_data, new_data, timestamp
                    FROM change_events 
                    WHERE processed = 0 AND id > :last_processed_id
                    ORDER BY id ASC 
                    LIMIT :max_events
                """), {"last_processed_id": self._last_processed_id, "max_events": self.max_events}).fetchall()
                
                for event in events:
                    try:
                        event_id, event_type, record_type, record_id, old_data, new_data, timestamp = event
                        
                        self._process_single_event(event_id, event_type, record_type, record_id, old_data, new_data, timestamp)
                        
                        # Mark as processed
                        db.execute(text("UPDATE change_events SET processed = 1 WHERE id = :event_id"), 
                                   {"event_id": event_id})
                        
                        self._last_processed_id = event_id
                        events_processed += 1
                        
                    except Exception as e:
                        self.logger.error(f"[EventProcessor] Failed to process event {event_id}: {e}")
                        # Continue processing other events even if one fails
                
                # Session commits automatically via context manager
                
        except Exception as e:
            self.logger.error(f"[EventProcessor] Error in process_events: {e}")
        
        return events_processed

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
                'operation': event_type,
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
        """Process structure_node-related events with version management integration."""
        self.logger.info(f"Processing structure_node event: {event.operation}")
        
        # Create version when entity is modified (only for create/update operations)
        if self.version_manager and event.operation in ['create', 'update'] and event.record_id:
            try:
                # Get the current entity data
                content = {}
                if event.new_data:
                    try:
                        content = json.loads(event.new_data) if isinstance(event.new_data, str) else event.new_data
                    except (json.JSONDecodeError, TypeError):
                        content = event.new_data if event.new_data else {}
                elif event.old_data:
                    try:
                        content = json.loads(event.old_data) if isinstance(event.old_data, str) else event.old_data
                    except (json.JSONDecodeError, TypeError):
                        content = event.old_data if event.old_data else {}
                
                if content:
                    from services.version_manager import ChangeState
                    
                    # Create version for this entity change
                    version = self.version_manager.create_version(
                        entity_type='structure_node',
                        entity_id=event.record_id,
                        content=content,
                        author_id='system',
                        state=ChangeState.WORKING
                    )
                    
                    # Link the change event to the created version
                    self._link_event_to_version(event.id, version.id, ChangeState.WORKING)
                    
                    # Update working tree if working tree manager is available
                    if self.working_tree_manager:
                        try:
                            if event.operation == 'create':
                                # Initialize new entity in working tree
                                self.working_tree_manager.initialize_entity_in_working_tree(
                                    entity_type='structure_node',
                                    entity_id=event.record_id,
                                    initial_version_id=version.id
                                )
                                self.logger.debug(f"[EventProcessor] Initialized working tree for new structure_node {event.record_id}")
                            else:
                                # Update existing entity's current version
                                self.working_tree_manager.update_current_version(
                                    entity_type='structure_node',
                                    entity_id=event.record_id,
                                    new_version_id=version.id
                                )
                                self.logger.debug(f"[EventProcessor] Updated working tree for structure_node {event.record_id}")
                        except Exception as wt_e:
                            self.logger.error(f"[EventProcessor] Failed to manage working tree: {wt_e}")
                    
                    self.logger.debug(f"[EventProcessor] Created version {version.version_number} for structure_node {event.record_id}")
                
            except Exception as e:
                self.logger.error(f"[EventProcessor] Failed to create version for structure_node {event.record_id}: {e}")
                # Continue processing even if version creation fails

    def process_structure_node_link_event(self, event):
        """Process structure_node_link-related events with version management integration."""
        self.logger.info(f"Processing structure_node_link event: {event.operation}")
        
        # Create version when entity is modified (only for create/update operations)
        if self.version_manager and event.operation in ['create', 'update'] and event.record_id:
            try:
                # Get the current entity data
                content = {}
                if event.new_data:
                    try:
                        content = json.loads(event.new_data) if isinstance(event.new_data, str) else event.new_data
                    except (json.JSONDecodeError, TypeError):
                        content = event.new_data if event.new_data else {}
                elif event.old_data:
                    try:
                        content = json.loads(event.old_data) if isinstance(event.old_data, str) else event.old_data
                    except (json.JSONDecodeError, TypeError):
                        content = event.old_data if event.old_data else {}
                
                if content:
                    from services.version_manager import ChangeState
                    
                    # Create version for this entity change
                    version = self.version_manager.create_version(
                        entity_type='structure_node_link',
                        entity_id=event.record_id,
                        content=content,
                        author_id='system',
                        state=ChangeState.WORKING
                    )
                    
                    # Link the change event to the created version
                    self._link_event_to_version(event.id, version.id, ChangeState.WORKING)
                    
                    # Update working tree if working tree manager is available
                    if self.working_tree_manager:
                        try:
                            if event.operation == 'create':
                                # Initialize new entity in working tree
                                self.working_tree_manager.initialize_entity_in_working_tree(
                                    entity_type='structure_node_link',
                                    entity_id=event.record_id,
                                    initial_version_id=version.id
                                )
                                self.logger.debug(f"[EventProcessor] Initialized working tree for new structure_node_link {event.record_id}")
                            else:
                                # Update existing entity's current version
                                self.working_tree_manager.update_current_version(
                                    entity_type='structure_node_link',
                                    entity_id=event.record_id,
                                    new_version_id=version.id
                                )
                                self.logger.debug(f"[EventProcessor] Updated working tree for structure_node_link {event.record_id}")
                        except Exception as wt_e:
                            self.logger.error(f"[EventProcessor] Failed to manage working tree: {wt_e}")
                    
                    self.logger.debug(f"[EventProcessor] Created version {version.version_number} for structure_node_link {event.record_id}")
                
            except Exception as e:
                self.logger.error(f"[EventProcessor] Failed to create version for structure_node_link {event.record_id}: {e}")
                # Continue processing even if version creation fails

    def process_predicate_event(self, event):
        """Process predicate-related events."""
        self.logger.info(f"Processing predicate event: {event.operation} id={event.id}")
        # New predicate-specific processing logic here
        # TODO: Implement predicate event handling as needed
    
    def _link_event_to_version(self, event_id: int, version_id: str, change_state):
        """Link a change event to its corresponding version."""
        try:
            with self._get_optimized_session() as db:
                db.execute(text("""
                    UPDATE change_events 
                    SET version_id = :version_id, change_state = :change_state
                    WHERE id = :event_id
                """), {
                    "version_id": version_id,
                    "change_state": change_state.value,
                    "event_id": event_id
                })
                # Session commits automatically via context manager
                
        except Exception as e:
            self.logger.error(f"[EventProcessor] Failed to link event {event_id} to version {version_id}: {e}")

    def _cleanup_loop(self):
        """Background loop for cleaning up old processed events."""
        self.logger.debug("[EventProcessor] _cleanup_loop() starting")
        
        while not self._stop_event.is_set():
            try:
                self.logger.debug("[EventProcessor] cleanup_old_events() running...")
                self.cleanup_old_events()
                
                # Also trigger Database Manager cleanup if needed
                if hasattr(self.db_manager, 'perform_health_check'):
                    health = self.db_manager.perform_health_check()
                    if health.get('overall_status') != 'healthy':
                        self.logger.warning(f"[EventProcessor] Database health issue: {health.get('overall_status')}")
                        
            except Exception as e:
                self.logger.error(f"[EventProcessor] Cleanup error: {e}")
                
            # Run once per day, but check stop event frequently
            sleep_interval = 60  # Check every minute
            total_sleep_time = 24 * 60 * 60  # 24 hours
            for _ in range(total_sleep_time // sleep_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(sleep_interval)
            
        self.logger.debug("[EventProcessor] _cleanup_loop() exiting")

    def cleanup_old_events(self, hours_to_keep: int = 48):
        """
        Clean up old processed events using Database Manager.
        
        Args:
            hours_to_keep: Number of hours to keep processed events (default: 48)
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_to_keep)
        
        try:
            with self._get_optimized_session() as db:
                # Delete old processed events
                result = db.execute(text("""
                    DELETE FROM change_events 
                    WHERE processed = 1 AND timestamp < :cutoff
                """), {"cutoff": cutoff.isoformat()})
                
                deleted_count = result.rowcount
                # Session commits automatically via context manager
                
                if deleted_count > 0:
                    self.logger.info(f"[EventProcessor] Deleted {deleted_count} old processed events.")
                    
        except Exception as e:
            self.logger.error(f"[EventProcessor] Error in cleanup_old_events: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get event processor statistics including database metrics."""
        try:
            with self._get_optimized_session() as db:
                # Get current unprocessed count
                unprocessed_result = db.execute(text("""
                    SELECT COUNT(*) FROM change_events WHERE processed = 0
                """)).fetchone()
                
                # Get current processed count
                processed_result = db.execute(text("""
                    SELECT COUNT(*) FROM change_events WHERE processed = 1
                """)).fetchone()
                
                # Get Database Manager metrics
                db_metrics = self.db_manager._get_metrics_summary()
                
                return {
                    "unprocessed_count": unprocessed_result[0] if unprocessed_result else 0,
                    "processed_count": processed_result[0] if processed_result else 0,
                    "events_processed_total": self._events_processed,
                    "last_processed_id": self._last_processed_id,
                    "is_running": self._thread is not None and self._thread.is_alive(),
                    "table_exists": True,
                    "engine_id": self.engine_id,
                    "database_metrics": db_metrics,
                    "optimized_features": {
                        "optimized_pooling": True,
                        "performance_monitoring": True,
                        "health_monitoring": True
                    }
                }
        except Exception as e:
            self.logger.error(f"[EventProcessor] Error in get_stats: {e}")
            return {
                "unprocessed_count": 0,
                "processed_count": 0,
                "events_processed_total": self._events_processed,
                "last_processed_id": self._last_processed_id,
                "is_running": self._thread is not None and self._thread.is_alive(),
                "table_exists": False,
                "engine_id": self.engine_id,
                "error": str(e),
                "optimized_features": {
                    "optimized_pooling": True,
                    "performance_monitoring": True,
                    "environment_aware": True,
                    "health_monitoring": True
                }
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status including database health."""
        try:
            # Get our own processor stats
            stats = self.get_stats()
            
            # Get Database Manager health
            db_health = self.db_manager.perform_health_check()
            
            # Determine overall processor health
            processor_health = "healthy"
            issues = []
            
            if stats["unprocessed_count"] > 1000:
                processor_health = "warning"
                issues.append(f"High unprocessed event count: {stats['unprocessed_count']}")
            
            if not stats["is_running"]:
                processor_health = "error"
                issues.append("Event processor is not running")
            
            if db_health.get("overall_status") != "healthy":
                processor_health = "warning" if processor_health == "healthy" else "error"
                issues.append(f"Database health issue: {db_health.get('overall_status')}")
            
            return {
                "timestamp": datetime.now().isoformat(),
                "processor_status": processor_health,
                "database_status": db_health.get("overall_status", "unknown"),
                "overall_status": processor_health,
                "issues": issues,
                "stats": stats,
                "database_health": db_health
            }
            
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "processor_status": "error",
                "database_status": "error", 
                "overall_status": "error",
                "issues": [f"Health check failed: {str(e)}"],
                "error": str(e)
            }


def create_event_processor(database_url: str, version_manager=None, working_tree_manager=None,
                          poll_interval: float = 1.0, 
                          max_events: int = 100) -> EventProcessor:
    """
    Factory function to create an EventProcessor with optimized database connections.
    
    Args:
        database_url: The database URL to connect to
        poll_interval: Polling interval in seconds for event checking  
        max_events: Maximum number of events to process per batch
        
    Returns:
        EventProcessor instance with optimized connection pooling
    """
    return EventProcessor(database_url, poll_interval, max_events, version_manager, working_tree_manager)


def EventProcessorFactory(database_url: str, **kwargs) -> EventProcessor:
    """Backward compatible factory that creates an optimized EventProcessor."""
    return create_event_processor(database_url, **kwargs)
