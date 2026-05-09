import threading
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from sqlalchemy import text

from database.enums import RecordType
from database.utils import get_database_manager
from utils.logger import get_logger

# Global reference to the active EventProcessor for dataset switching
# This singleton pattern enables coordination across modules when switching active datasets.  # noqa: E501
# Thread safety is ensured by the set/get functions which maintain a simple reference  # noqa: E501
# without concurrent mutations during normal operation.
_global_event_processor: Optional["EventProcessor"] = None


def get_global_event_processor() -> Optional["EventProcessor"]:
    """Get the global EventProcessor instance."""
    return _global_event_processor


def set_global_event_processor(processor: Optional["EventProcessor"]):
    """Set the global EventProcessor instance."""
    global _global_event_processor
    _global_event_processor = processor


class EventProcessor:
    """
    Event processor that handles ChangeEvent processing with optimized database connections.  # noqa: E501

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

    # Configuration constants
    NLP_PIPELINE_FLAVOR = "analyze_text"
    MAX_TITLE_LENGTH = 500
    NLP_RETRY_ATTEMPTS = 3
    NLP_RETRY_DELAY = 1.0  # seconds, will use exponential backoff

    def __init__(
        self,
        database_url: str,
        poll_interval: float = 1.0,
        max_events: int = 100,
        version_manager=None,
        working_tree_manager=None,
    ):
        """
        Initialize the EventProcessor.

        Args:
            database_url: The database URL to connect to
            poll_interval: Polling interval in seconds for event checking
            max_events: Maximum number of events to process per batch
            version_manager: Optional VersionManager instance for version creation  # noqa: E501
            working_tree_manager: Optional WorkingTreeManager instance for working tree management  # noqa: E501
        """
        self.database_url = database_url
        self.poll_interval = poll_interval
        self.max_events = max_events
        self.version_manager = (
            version_manager  # Will be injected for version creation  # noqa: E501
        )
        self.working_tree_manager = working_tree_manager  # Will be injected for working tree management  # noqa: E501

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

        # Node-level locks for preventing concurrent title change updates
        self._title_change_locks: Dict[str, threading.Lock] = {}
        self._title_change_locks_mutex = threading.Lock()

        # Register as global event processor for dataset switching
        set_global_event_processor(self)

        self.logger.info("EventProcessor initialized")

    def _get_managed_session(self):
        """Get an optimized database session using Database Manager."""
        # Ensure we have an optimized engine for event processing
        if self.engine_id not in self.db_manager._engines:
            try:
                self.db_manager.create_managed_engine(
                    self.database_url, self.engine_id
                )  # noqa: E501
            except Exception as e:
                self.logger.error(
                    f"Failed to create optimized engine '{self.engine_id}': {e}"
                )  # noqa: E501
                raise

        try:
            return self.db_manager.get_session(
                self.engine_id, self.database_url
            )  # noqa: E501
        except Exception as e:
            self.logger.error(
                f"Failed to get optimized session for '{self.engine_id}': {e}"
            )  # noqa: E501
            raise

    def _initialize_last_processed_id(self):
        """Initialize the last processed event ID from the database."""
        try:
            with self._get_managed_session() as db:
                result = db.execute(text("""
                    SELECT id FROM change_events
                    WHERE processed = 1
                    ORDER BY id DESC
                    LIMIT 1
                """)).fetchone()

                if result:
                    self._last_processed_id = result[0]
                    self.logger.debug(
                        f"Last processed ID initialized to {self._last_processed_id}"
                    )  # noqa: E501
                else:
                    self.logger.debug(
                        "No processed events found; starting from ID 0"
                    )  # noqa: E501

        except Exception as e:
            self.logger.debug(
                f"Could not initialize last processed ID from database (expected on first run): {e}"
            )  # noqa: E501
            # Start from 0 if we can't get the last processed ID
            self._last_processed_id = 0

    def start(self):
        """Start the event processing loop in a background thread."""
        self.logger.debug("[EventProcessor] start() called")
        if self._thread is None or not self._thread.is_alive():
            # Create optimized engine before starting threads
            self.db_manager.create_managed_engine(
                self.database_url, self.engine_id
            )  # noqa: E501

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self.logger.debug("[EventProcessor] main thread started")

            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop, daemon=True
            )  # noqa: E501
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
        self.logger.info(
            f"[EventProcessor] Switching dataset from {self.database_url} to {new_database_url}"
        )  # noqa: E501

        # Stop current processing
        self.stop()

        # Update database URL
        self.database_url = new_database_url
        self.engine_id = f"event_processor_{id(self)}_{int(time.time())}"  # New unique ID  # noqa: E501

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
                if (
                    datetime.now() - self._last_performance_log
                    >= self._performance_log_interval
                ):  # noqa: E501
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

            self.logger.debug(
                f"[EventProcessor] Performance: "
                f"events_processed={self._events_processed}, "
                f"db_queries={db_metrics.get('total_queries_executed', 0)}, "
                f"avg_query_time={db_metrics.get('avg_query_time_ms', 0):.2f}ms, "  # noqa: E501
                f"pool_efficiency={db_metrics.get('pool_efficiency_percent', 0):.1f}%"  # noqa: E501
            )

            self._last_performance_log = datetime.now()

        except Exception as e:
            self.logger.warning(
                f"[EventProcessor] Failed to log performance metrics: {e}"
            )  # noqa: E501

    def process_events(self) -> int:
        """
        Process unprocessed ChangeEvents using Database Manager.

        Returns:
            Number of events processed
        """
        events_processed = 0

        try:
            with self._get_managed_session() as db:
                # Get unprocessed ChangeEvents since last processed ID
                events = db.execute(
                    text("""
                    SELECT id, event_type, record_type, record_id, old_data, new_data, timestamp
                    FROM change_events
                    WHERE processed = 0 AND id > :last_processed_id
                    ORDER BY id ASC
                    LIMIT :max_events
                """),
                    {
                        "last_processed_id": self._last_processed_id,
                        "max_events": self.max_events,
                    },
                ).fetchall()  # noqa: E501

                for event in events:
                    try:
                        (
                            event_id,
                            event_type,
                            record_type,
                            record_id,
                            old_data,
                            new_data,
                            timestamp,
                        ) = event  # noqa: E501

                        self._process_single_event(
                            event_id,
                            event_type,
                            record_type,
                            record_id,
                            old_data,
                            new_data,
                            timestamp,
                        )  # noqa: E501

                        # Mark as processed
                        db.execute(
                            text(
                                "UPDATE change_events SET processed = 1 WHERE id = :event_id"
                            ),  # noqa: E501
                            {"event_id": event_id},
                        )

                        self._last_processed_id = event_id
                        events_processed += 1

                    except Exception as e:
                        self.logger.error(
                            f"[EventProcessor] Failed to process event {event_id}: {e}"
                        )  # noqa: E501
                        # Continue processing other events even if one fails

                # Session commits automatically via context manager

        except Exception as e:
            self.logger.error(f"[EventProcessor] Error in process_events: {e}")

        return events_processed

    def _process_single_event(
        self,
        event_id,
        event_type,
        record_type,
        record_id,
        old_data,
        new_data,
        timestamp,
    ):  # noqa: E501
        """Process a single ChangeEvent using record_type routing."""
        self.logger.debug(
            f"[EventProcessor] Processing ChangeEvent {event_id}: {event_type} {record_type}"
        )  # noqa: E501

        # Convert string back to enum if needed (for database compatibility)
        if isinstance(record_type, str):
            try:
                record_type = RecordType(record_type)
            except ValueError:
                valid_types = [rt.value for rt in RecordType]
                self.logger.error(
                    f"[EventProcessor] Event {event_id} has invalid record_type '{record_type}'. "  # noqa: E501
                    f"Valid types: {valid_types}. This event will be skipped."
                )
                return

        # Route to specific handler based on record type
        handler_name = f"process_{record_type.value}_event"
        handler = getattr(self, handler_name, None)

        if handler:
            # Create a simple event object
            event_obj = type(
                "Event",
                (),
                {
                    "id": event_id,
                    "operation": event_type,
                    "record_type": record_type,
                    "record_id": record_id,
                    "old_data": old_data,
                    "new_data": new_data,
                    "timestamp": timestamp,
                },
            )()
            handler(event_obj)
        else:
            self.logger.error(
                f"[EventProcessor] No handler found for record_type: {record_type.value}. "  # noqa: E501
                f"Event {event_id} will be skipped."
            )

    def process_structure_node_event(self, event):
        """Process structure_node-related events with version management integration."""  # noqa: E501
        self.logger.info(f"Processing structure_node event: {event.operation}")

        # Create version when entity is modified (only for create/update operations)  # noqa: E501
        if (
            self.version_manager
            and event.operation in ["create", "update"]
            and event.record_id
        ):  # noqa: E501
            try:
                # Get the current entity data
                content = {}
                if event.new_data:
                    try:
                        content = (
                            json.loads(event.new_data)
                            if isinstance(event.new_data, str)
                            else event.new_data
                        )  # noqa: E501
                    except (json.JSONDecodeError, TypeError):
                        content = event.new_data if event.new_data else {}
                elif event.old_data:
                    try:
                        content = (
                            json.loads(event.old_data)
                            if isinstance(event.old_data, str)
                            else event.old_data
                        )  # noqa: E501
                    except (json.JSONDecodeError, TypeError):
                        content = event.old_data if event.old_data else {}

                if content:
                    from services.version_manager import ChangeState

                    # Create version for this entity change
                    version = self.version_manager.create_version(
                        entity_type="structure_node",
                        entity_id=event.record_id,
                        content=content,
                        author_id="system",
                        state=ChangeState.WORKING,
                    )

                    # Link the change event to the created version
                    self._link_event_to_version(
                        event.id, version.id, ChangeState.WORKING
                    )  # noqa: E501

                    # Update working tree if working tree manager is available
                    if self.working_tree_manager:
                        try:
                            # Check if entity already exists in working tree
                            existing_entry = self.working_tree_manager.get_working_tree_entry(  # noqa: E501
                                entity_type="structure_node", entity_id=event.record_id
                            )

                            if existing_entry:
                                # Entity already tracked - update current version  # noqa: E501
                                self.working_tree_manager.update_current_version(  # noqa: E501
                                    entity_type="structure_node",
                                    entity_id=event.record_id,
                                    new_version_id=version.id,
                                )
                                self.logger.debug(
                                    f"[EventProcessor] Updated working tree for structure_node {event.record_id}"
                                )  # noqa: E501
                            else:
                                # Entity not yet tracked - initialize it
                                self.working_tree_manager.initialize_entity_in_working_tree(  # noqa: E501
                                    entity_type="structure_node",
                                    entity_id=event.record_id,
                                    initial_version_id=version.id,
                                )
                                self.logger.debug(
                                    f"[EventProcessor] Initialized working tree for new structure_node {event.record_id}"
                                )  # noqa: E501
                        except Exception as wt_e:
                            self.logger.error(
                                f"[EventProcessor] Failed to manage working tree: {wt_e}"
                            )  # noqa: E501

                    self.logger.debug(
                        f"[EventProcessor] Created version {version.version_number} for structure_node {event.record_id}"
                    )  # noqa: E501

            except Exception as e:
                self.logger.error(
                    f"[EventProcessor] Failed to create version for structure_node {event.record_id}: {e}"
                )  # noqa: E501
                # Continue processing even if version creation fails

        # Detect title changes and trigger NLP re-analysis
        if event.operation == "update" and event.old_data and event.new_data:
            try:
                self._handle_title_change(event)
            except Exception as e:
                self.logger.error(
                    f"[EventProcessor] Failed to handle title change for structure_node {event.record_id}: {e}"
                )  # noqa: E501
                # Continue processing even if title change handling fails

    def process_structure_node_link_event(self, event):
        """Process structure_node_link-related events with version management integration."""  # noqa: E501
        self.logger.info(
            f"Processing structure_node_link event: {event.operation}"
        )  # noqa: E501

        # Create version when entity is modified (only for create/update operations)  # noqa: E501
        if (
            self.version_manager
            and event.operation in ["create", "update"]
            and event.record_id
        ):  # noqa: E501
            try:
                # Get the current entity data
                content = {}
                if event.new_data:
                    try:
                        content = (
                            json.loads(event.new_data)
                            if isinstance(event.new_data, str)
                            else event.new_data
                        )  # noqa: E501
                    except (json.JSONDecodeError, TypeError):
                        content = event.new_data if event.new_data else {}
                elif event.old_data:
                    try:
                        content = (
                            json.loads(event.old_data)
                            if isinstance(event.old_data, str)
                            else event.old_data
                        )  # noqa: E501
                    except (json.JSONDecodeError, TypeError):
                        content = event.old_data if event.old_data else {}

                if content:
                    from services.version_manager import ChangeState

                    # Create version for this entity change
                    version = self.version_manager.create_version(
                        entity_type="structure_node_link",
                        entity_id=event.record_id,
                        content=content,
                        author_id="system",
                        state=ChangeState.WORKING,
                    )

                    # Link the change event to the created version
                    self._link_event_to_version(
                        event.id, version.id, ChangeState.WORKING
                    )  # noqa: E501

                    # Update working tree if working tree manager is available
                    if self.working_tree_manager:
                        try:
                            # Check if entity already exists in working tree
                            existing_entry = self.working_tree_manager.get_working_tree_entry(  # noqa: E501
                                entity_type="structure_node_link",
                                entity_id=event.record_id,
                            )

                            if existing_entry:
                                # Entity already tracked - update current version  # noqa: E501
                                self.working_tree_manager.update_current_version(  # noqa: E501
                                    entity_type="structure_node_link",
                                    entity_id=event.record_id,
                                    new_version_id=version.id,
                                )
                                self.logger.debug(
                                    f"[EventProcessor] Updated working tree for structure_node_link {event.record_id}"
                                )  # noqa: E501
                            else:
                                # Entity not yet tracked - initialize it
                                self.working_tree_manager.initialize_entity_in_working_tree(  # noqa: E501
                                    entity_type="structure_node_link",
                                    entity_id=event.record_id,
                                    initial_version_id=version.id,
                                )
                                self.logger.debug(
                                    f"[EventProcessor] Initialized working tree for new structure_node_link {event.record_id}"
                                )  # noqa: E501
                        except Exception as wt_e:
                            self.logger.error(
                                f"[EventProcessor] Failed to manage working tree: {wt_e}"
                            )  # noqa: E501

                    self.logger.debug(
                        f"[EventProcessor] Created version {version.version_number} for structure_node_link {event.record_id}"
                    )  # noqa: E501

            except Exception as e:
                self.logger.error(
                    f"[EventProcessor] Failed to create version for structure_node_link {event.record_id}: {e}"
                )  # noqa: E501
                # Continue processing even if version creation fails

    def process_predicate_event(self, event):
        """Process predicate-related events."""
        self.logger.info(
            f"Processing predicate event: {event.operation} id={event.id}"
        )  # noqa: E501
        # Predicate changes are logged via ChangeEvent but do not require
        # additional processing (unlike structure_nodes which need version tracking)  # noqa: E501

    def _link_event_to_version(
        self, event_id: int, version_id: str, change_state
    ):  # noqa: E501
        """Link a change event to its corresponding version."""
        try:
            with self._get_managed_session() as db:
                db.execute(
                    text("""
                    UPDATE change_events
                    SET version_id = :version_id, change_state = :change_state
                    WHERE id = :event_id
                """),
                    {
                        "version_id": version_id,
                        "change_state": change_state.value,
                        "event_id": event_id,
                    },
                )
                # Session commits automatically via context manager

        except Exception as e:
            self.logger.error(
                f"[EventProcessor] Failed to link event {event_id} to version {version_id}: {e}"
            )  # noqa: E501

    def _get_node_lock(self, node_id: str) -> threading.Lock:
        """
        Get or create a lock for a specific node ID to prevent concurrent updates.  # noqa: E501

        Args:
            node_id: The structure node ID

        Returns:
            Threading lock for this node
        """
        with self._title_change_locks_mutex:
            if node_id not in self._title_change_locks:
                self._title_change_locks[node_id] = threading.Lock()
            return self._title_change_locks[node_id]

    def _handle_title_change(self, event):
        """
        Detect title changes and trigger asynchronous NLP re-analysis.

        Args:
            event: The structure_node update event
        """
        try:
            # Parse old and new data
            old_data = (
                json.loads(event.old_data)
                if isinstance(event.old_data, str)
                else event.old_data
            )  # noqa: E501
            new_data = (
                json.loads(event.new_data)
                if isinstance(event.new_data, str)
                else event.new_data
            )  # noqa: E501

            old_title = old_data.get("title", "") if old_data else ""
            new_title = new_data.get("title", "") if new_data else ""

            # Check if title has actually changed
            if old_title and new_title and old_title != new_title:
                # Validate new title
                if not new_title.strip():
                    raise ValueError(
                        f"Empty title detected for structure_node {event.record_id}"
                    )  # noqa: E501

                if len(new_title) > self.MAX_TITLE_LENGTH:
                    raise ValueError(
                        f"Title exceeds maximum length ({len(new_title)} > {self.MAX_TITLE_LENGTH}) "  # noqa: E501
                        f"for structure_node {event.record_id}"
                    )

                self.logger.info(
                    f"[EventProcessor] Title change detected for structure_node {event.record_id}: "  # noqa: E501
                    f"'{old_title}' -> '{new_title}'"
                )

                # Acquire node-specific lock to prevent concurrent updates
                node_lock = self._get_node_lock(event.record_id)

                # Try to acquire lock without blocking
                if node_lock.acquire(blocking=False):
                    try:
                        # Enqueue async NLP re-analysis task
                        self._enqueue_nlp_reanalysis(
                            event.record_id, new_title
                        )  # noqa: E501
                    finally:
                        node_lock.release()
                else:
                    self.logger.info(
                        f"[EventProcessor] Skipping title change for node {event.record_id}: "  # noqa: E501
                        f"already processing another title change"
                    )

        except json.JSONDecodeError as e:
            self.logger.error(
                f"[EventProcessor] Failed to parse event data for title change detection: {e}",  # noqa: E501
                exc_info=True,
            )
        except ValueError as e:
            # Expected validation errors
            self.logger.warning(
                f"[EventProcessor] Title validation error: {e}"
            )  # noqa: E501
        except RuntimeError as e:
            # Expected runtime errors (e.g., TaskManager not initialized)
            self.logger.warning(
                f"[EventProcessor] Runtime error in title change handling: {e}"
            )  # noqa: E501
        except Exception as e:
            # Unexpected system errors
            self.logger.error(
                f"[EventProcessor] Unexpected error in title change detection for node {event.record_id}: {e}",  # noqa: E501
                exc_info=True,
            )

    def _enqueue_nlp_reanalysis(self, node_id: str, new_title: str):
        """
        Enqueue an asynchronous NLP re-analysis task for a structure node.

        Args:
            node_id: The structure node ID
            new_title: The new title to analyze
        """
        try:
            # Get the task manager (will be None if not initialized)
            from services.task_manager import get_task_manager

            try:
                task_manager = get_task_manager()
            except RuntimeError:
                self.logger.warning(
                    f"[EventProcessor] TaskManager not initialized, skipping NLP re-analysis for node {node_id}"  # noqa: E501
                )
                return

            # Import asyncio for creating the coroutine
            import asyncio

            # Create the async task coroutine
            async def nlp_reanalysis_task():
                return await self._perform_nlp_reanalysis(node_id, new_title)

            # Submit the task asynchronously (this is called from sync context)
            # We need to use asyncio.create_task or submit it to the task manager  # noqa: E501
            # Since EventProcessor runs in a background thread, we need to handle this carefully  # noqa: E501

            # Get or create an event loop for this thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in current thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Submit the task to the task manager
            async def submit_task():
                await task_manager.submit_task(
                    task_type="nlp_reanalysis",
                    coroutine=nlp_reanalysis_task(),
                    metadata={"node_id": node_id, "new_title": new_title},
                )

            # Run the submission in the event loop
            asyncio.run_coroutine_threadsafe(submit_task(), loop)

            self.logger.info(
                f"[EventProcessor] Enqueued NLP re-analysis task for node {node_id}"
            )  # noqa: E501

        except Exception as e:
            self.logger.error(
                f"[EventProcessor] Failed to enqueue NLP re-analysis task: {e}"
            )  # noqa: E501

    async def _perform_nlp_reanalysis(self, node_id: str, new_title: str):
        """
        Perform NLP re-analysis and update word senses for a structure node with retry logic.  # noqa: E501

        Args:
            node_id: The structure node ID
            new_title: The new title to analyze

        Returns:
            Dictionary with results
        """
        import asyncio

        last_error = None

        # Retry loop with exponential backoff
        for attempt in range(1, self.NLP_RETRY_ATTEMPTS + 1):
            try:
                self.logger.info(
                    f"[EventProcessor] Starting NLP re-analysis for node {node_id} (attempt {attempt}/{self.NLP_RETRY_ATTEMPTS})"  # noqa: E501
                )

                # Import required modules
                from nlp.pipeline import get_pipeline
                from nlp.processors import process_nlp_result
                from services.word_sense_service import WordSenseService

                # Get NLP pipeline
                pipeline = get_pipeline()
                if not pipeline.is_initialized():
                    raise RuntimeError("NLP pipeline not initialized")

                nlp = pipeline.get_nlp()
                if not nlp:
                    raise RuntimeError("NLP pipeline unavailable")

                # Process the new title
                doc = nlp(new_title)
                nlp_response = process_nlp_result(new_title, doc)

                # Extract word senses from NLP analysis with transaction
                with self._get_managed_session() as db:
                    word_sense_service = WordSenseService(db)

                    # Extract new senses
                    new_senses = word_sense_service.extract_word_senses(
                        nlp_response
                    )  # noqa: E501

                    self.logger.debug(
                        f"[EventProcessor] Extracted {len(new_senses)} word senses from NLP analysis"  # noqa: E501
                    )

                    # Begin explicit transaction for atomic word sense updates
                    with db.begin():
                        # Update word senses with conservative filtering
                        # This will preserve existing senses that match and remove only obsolete ones  # noqa: E501
                        updated_senses = word_sense_service.update_word_senses(
                            node_id=node_id, new_senses=new_senses, conservative=True
                        )

                        self.logger.info(
                            f"[EventProcessor] Successfully updated word senses for node {node_id}: "  # noqa: E501
                            f"{len(updated_senses)} total senses"
                        )

                    # Success - return results
                    return {
                        "success": True,
                        "node_id": node_id,
                        "new_title": new_title,
                        "senses_count": len(updated_senses),
                        "attempts": attempt,
                    }

            except (RuntimeError, ConnectionError, TimeoutError) as e:
                # Transient errors - retry with exponential backoff
                last_error = e
                self.logger.warning(
                    f"[EventProcessor] NLP re-analysis attempt {attempt} failed for node {node_id} "  # noqa: E501
                    f"with transient error: {e}"
                )

                if attempt < self.NLP_RETRY_ATTEMPTS:
                    delay = self.NLP_RETRY_DELAY * (2 ** (attempt - 1))
                    self.logger.info(
                        f"[EventProcessor] Retrying in {delay} seconds..."
                    )  # noqa: E501
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"[EventProcessor] NLP re-analysis failed for node {node_id} after {attempt} attempts",  # noqa: E501
                        exc_info=True,
                    )

            except Exception as e:
                # Non-transient errors - fail immediately
                self.logger.error(
                    f"[EventProcessor] NLP re-analysis failed for node {node_id} with non-retryable error: {e}",  # noqa: E501
                    exc_info=True,
                )
                return {
                    "success": False,
                    "node_id": node_id,
                    "new_title": new_title,
                    "error": str(e),
                    "attempts": attempt,
                }

        # All retries exhausted
        return {
            "success": False,
            "node_id": node_id,
            "new_title": new_title,
            "error": (
                str(last_error) if last_error else "Unknown error after retries"
            ),  # noqa: E501
            "attempts": self.NLP_RETRY_ATTEMPTS,
        }

    def _cleanup_loop(self):
        """Background loop for cleaning up old processed events."""
        self.logger.debug("[EventProcessor] _cleanup_loop() starting")

        while not self._stop_event.is_set():
            try:
                self.logger.debug(
                    "[EventProcessor] cleanup_old_events() running..."
                )  # noqa: E501
                self.cleanup_old_events()

                # Also trigger Database Manager health check if available
                if hasattr(self.db_manager, "perform_health_check"):
                    health = self.db_manager.perform_health_check()
                    overall_status = health.get("overall_status")

                    # Only log warnings for actual errors, not degraded status from slow queries  # noqa: E501
                    if overall_status == "error":
                        errors = health.get("errors", [])
                        self.logger.warning(
                            f"[EventProcessor] Database health error detected: {errors}"  # noqa: E501
                        )
                    elif overall_status == "degraded":
                        # Degraded can be expected during high load; log at debug level  # noqa: E501
                        warnings = health.get("warnings", [])
                        self.logger.debug(
                            f"[EventProcessor] Database performance degraded: {warnings}"  # noqa: E501
                        )

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
            hours_to_keep: Number of hours to keep processed events (default: 48)  # noqa: E501
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_to_keep)

        try:
            with self._get_managed_session() as db:
                # Delete old processed events
                result = db.execute(
                    text("""
                    DELETE FROM change_events
                    WHERE processed = 1 AND timestamp < :cutoff
                """),
                    {"cutoff": cutoff.isoformat()},
                )

                deleted_count = result.rowcount
                # Session commits automatically via context manager

                if deleted_count > 0:
                    self.logger.info(
                        f"[EventProcessor] Deleted {deleted_count} old processed events."
                    )  # noqa: E501

        except Exception as e:
            self.logger.error(
                f"[EventProcessor] Error in cleanup_old_events: {e}"
            )  # noqa: E501

    def get_stats(self) -> Dict[str, Any]:
        """Get event processor statistics including database metrics."""
        try:
            with self._get_managed_session() as db:
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
                    "unprocessed_count": (
                        unprocessed_result[0] if unprocessed_result else 0
                    ),  # noqa: E501
                    "processed_count": (
                        processed_result[0] if processed_result else 0
                    ),  # noqa: E501
                    "events_processed_total": self._events_processed,
                    "last_processed_id": self._last_processed_id,
                    "is_running": self._thread is not None
                    and self._thread.is_alive(),  # noqa: E501
                    "table_exists": True,
                    "engine_id": self.engine_id,
                    "database_metrics": db_metrics,
                    "optimized_features": {
                        "optimized_pooling": True,
                        "performance_monitoring": True,
                        "health_monitoring": True,
                    },
                }
        except Exception as e:
            self.logger.error(f"[EventProcessor] Error in get_stats: {e}")
            return {
                "unprocessed_count": 0,
                "processed_count": 0,
                "events_processed_total": self._events_processed,
                "last_processed_id": self._last_processed_id,
                "is_running": self._thread is not None
                and self._thread.is_alive(),  # noqa: E501
                "table_exists": False,
                "engine_id": self.engine_id,
                "error": str(e),
                "optimized_features": {
                    "optimized_pooling": True,
                    "performance_monitoring": True,
                    "environment_aware": True,
                    "health_monitoring": True,
                },
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
                issues.append(
                    f"High unprocessed event count: {stats['unprocessed_count']}"
                )  # noqa: E501

            if not stats["is_running"]:
                processor_health = "error"
                issues.append("Event processor is not running")

            if db_health.get("overall_status") != "healthy":
                processor_health = (
                    "warning" if processor_health == "healthy" else "error"
                )  # noqa: E501
                issues.append(
                    f"Database health issue: {db_health.get('overall_status')}"
                )  # noqa: E501

            return {
                "timestamp": datetime.now().isoformat(),
                "processor_status": processor_health,
                "database_status": db_health.get("overall_status", "unknown"),
                "overall_status": processor_health,
                "issues": issues,
                "stats": stats,
                "database_health": db_health,
            }

        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "processor_status": "error",
                "database_status": "error",
                "overall_status": "error",
                "issues": [f"Health check failed: {str(e)}"],
                "error": str(e),
            }


def create_event_processor(
    database_url: str,
    version_manager=None,
    working_tree_manager=None,  # noqa: E501
    poll_interval: float = 1.0,  # noqa: E128
    max_events: int = 100,
) -> EventProcessor:  # noqa: E128, E501
    """
    Factory function to create an EventProcessor with optimized database connections.  # noqa: E501

    Args:
        database_url: The database URL to connect to
        poll_interval: Polling interval in seconds for event checking
        max_events: Maximum number of events to process per batch

    Returns:
        EventProcessor instance with optimized connection pooling
    """
    return EventProcessor(
        database_url, poll_interval, max_events, version_manager, working_tree_manager
    )  # noqa: E501


def EventProcessorFactory(database_url: str, **kwargs) -> EventProcessor:
    """Backward compatible factory that creates an optimized EventProcessor."""
    return create_event_processor(database_url, **kwargs)
