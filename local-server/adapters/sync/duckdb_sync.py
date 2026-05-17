"""
DuckDB-based synchronization adapter for the Version Control & Collaboration bounded context.

The DuckDBSyncAdapter implements the SyncTarget port, enabling workspaces to synchronize
changes via date-partitioned Parquet files using DuckDB. This provides an efficient
batch-query sync mechanism for local-first scenarios.

Changes are serialized as Parquet with a directory structure: {output_dir}/changes/{date}/

This adapter uses fail-fast error handling: I/O errors are propagated to the caller as
RuntimeError, never suppressed. The service layer wraps these into domain-level SyncError
exceptions.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence, TYPE_CHECKING
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from domain.versioning.entities import ChangeEvent
from domain.versioning.value_objects import SyncResult, ChangeOperation, SyncStatus

if TYPE_CHECKING:
    from domain.versioning.ports import ChangeRepository

_logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class DuckDBSyncAdapter:
    """
    Implements SyncTarget using DuckDB and date-partitioned Parquet files.

    Changes are serialized as Parquet files and stored in date-partitioned
    directories, enabling efficient querying and batch synchronization via DuckDB.

    This adapter uses fail-fast error handling: I/O errors are propagated to
    the caller as RuntimeError. The caller (service layer) wraps these into
    SyncError domain exceptions.
    """

    def __init__(
        self, output_dir: str, change_repo: "ChangeRepository | None" = None
    ) -> None:
        """
        Initialize the sync adapter.

        Args:
            output_dir: Local directory path for storing Parquet files
            change_repo: Optional ChangeRepository for querying unprocessed changes

        Raises:
            ImportError: If duckdb or pyarrow is not installed
            RuntimeError: If sync directory cannot be created
        """
        if importlib.util.find_spec("duckdb") is None:
            _logger.error(
                "duckdb is required for sync adapter. Install with: pip install duckdb"
            )
            raise ImportError("duckdb is required for sync adapter")
        if importlib.util.find_spec("pyarrow") is None:
            _logger.error(
                "pyarrow is required for sync adapter. Install with: pip install pyarrow"
            )
            raise ImportError("pyarrow is required for sync adapter")

        self._output_dir = Path(output_dir).resolve()
        self._changes_dir = self._output_dir / "changes"
        self._change_repo = change_repo

        # Create directory structure if needed
        try:
            self._changes_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            error_msg = f"Failed to create sync directory {self._changes_dir}: {e}"
            _logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        _logger.info(
            "DuckDBSyncAdapter initialized (output_dir=%s)",
            self._output_dir,
        )

    def push(self, events: Sequence[ChangeEvent]) -> SyncResult:
        """
        Push local change events to Parquet files.

        Serializes events as Parquet and writes to date-partitioned directories
        with directory structure: {output_dir}/changes/{yyyy-mm-dd}/

        Args:
            events: Sequence of ChangeEvent objects to push

        Returns:
            SyncResult with count of pushed events and their IDs

        Raises:
            RuntimeError: If file I/O or serialization fails
        """
        with tracer.start_as_current_span("sync.push.duckdb") as span:
            span.set_attribute("sync.adapter", "duckdb")
            span.set_attribute("sync.direction", "push")
            span.set_attribute("sync.record_count", len(events))
            span.set_attribute("sync.format", "parquet")

            started_at = datetime.now(timezone.utc)
            if not events:
                completed_at = datetime.now(timezone.utc)
                return SyncResult(
                    pushed=0,
                    pulled=0,
                    errors=(),
                    pushed_event_ids=(),
                    started_at=started_at,
                    completed_at=completed_at,
                )

            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise RuntimeError(f"pyarrow is required for sync adapter: {e}")

            pushed_event_ids = []

            try:
                # Group events by date
                events_by_date: dict[str, list[dict]] = {}
                for event in events:
                    pushed_event_ids.append(event.id)
                    date_str = event.timestamp.strftime("%Y-%m-%d")

                    if date_str not in events_by_date:
                        events_by_date[date_str] = []

                    event_dict = {
                        "id": event.id,
                        "entity_id": event.entity_id,
                        "entity_type": event.entity_type,
                        "operation": event.operation.value,
                        "timestamp": event.timestamp.isoformat(),
                        "processed": event.processed,
                        "user_id": event.user_id,
                        "change_reason": event.change_reason,
                        "new_state": (
                            json.dumps(event.new_state) if event.new_state else None
                        ),
                        "previous_state": (
                            json.dumps(event.previous_state)
                            if event.previous_state
                            else None
                        ),
                    }
                    events_by_date[date_str].append(event_dict)

                # Write each date's events to its own Parquet file
                # DuckDB is used in the pull method for efficient Parquet reading and verification
                for date_str, date_events in events_by_date.items():
                    date_dir = self._changes_dir / date_str
                    date_dir.mkdir(parents=True, exist_ok=True)

                    # Create table from events using PyArrow
                    table = pa.table(
                        {
                            "id": [e["id"] for e in date_events],
                            "entity_id": [e["entity_id"] for e in date_events],
                            "entity_type": [e["entity_type"] for e in date_events],
                            "operation": [e["operation"] for e in date_events],
                            "timestamp": [e["timestamp"] for e in date_events],
                            "processed": [e["processed"] for e in date_events],
                            "user_id": [e["user_id"] for e in date_events],
                            "change_reason": [e["change_reason"] for e in date_events],
                            "new_state": [e["new_state"] for e in date_events],
                            "previous_state": [e["previous_state"] for e in date_events],
                        }
                    )

                    # Write Parquet file with UUID to prevent overwrites on repeated pushes
                    uuid_str = str(uuid4())
                    parquet_file = date_dir / f"{uuid_str}.parquet"
                    pq.write_table(table, str(parquet_file))

                _logger.info(
                    "Pushed %d change events to Parquet files (dates=%d)",
                    len(events),
                    len(events_by_date),
                )
                completed_at = datetime.now(timezone.utc)
                return SyncResult(
                    pushed=len(pushed_event_ids),
                    pulled=0,
                    errors=(),
                    pushed_event_ids=tuple(pushed_event_ids),
                    started_at=started_at,
                    completed_at=completed_at,
                )

            except OSError as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                error_msg = f"Failed to write Parquet files: {e}"
                _logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            except (ValueError, TypeError, KeyError) as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                error_msg = f"Failed to push change events: {e}"
                _logger.error(error_msg)
                raise RuntimeError(error_msg) from e

    def pull(self, since: Optional[datetime] = None) -> list[ChangeEvent]:
        """
        Pull change events from Parquet files.

        Lists date directories in {output_dir}/changes/, filters by date if since provided,
        reads and deserializes Parquet files using DuckDB. Deduplicates events by ID.

        Args:
            since: Optional timestamp to fetch changes after

        Returns:
            List of deduplicated ChangeEvent objects from Parquet files

        Raises:
            RuntimeError: If file listing fails, file read fails, or parsing fails
        """
        with tracer.start_as_current_span("sync.pull.duckdb") as span:
            span.set_attribute("sync.adapter", "duckdb")
            span.set_attribute("sync.direction", "pull")
            span.set_attribute("sync.format", "parquet")

            try:
                import duckdb
            except ImportError as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise RuntimeError("duckdb is required for sync adapter")

            events: list[ChangeEvent] = []
            seen_ids: set[str] = set()

            try:
                # List all date directories
                if not self._changes_dir.exists():
                    _logger.debug("Changes directory does not exist: %s", self._changes_dir)
                    return events

                for date_dir in sorted(self._changes_dir.iterdir()):
                    if not date_dir.is_dir():
                        continue

                    date_str = date_dir.name
                    file_date = None

                    # Filter by date if since provided
                    if since:
                        try:
                            # Parse directory date and compare with since date
                            # Include all files on or after the since date (by date only)
                            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                                tzinfo=timezone.utc
                            )
                            # Only skip if file date is before the date part of since
                            # (file_date is at midnight, so compare dates not times)
                            if file_date.date() < since.date():
                                continue
                        except ValueError:
                            # When since is provided, skip directories with unparseable dates
                            _logger.warning(
                                "Skipping directory with unparseable date (dir=%s)",
                                date_str,
                            )
                            continue
                    # If since is None, process all directories regardless of name format

                    # Read all Parquet files in this date directory
                    for parquet_file in date_dir.glob("*.parquet"):
                        try:
                            # Read Parquet file using DuckDB
                            relation = duckdb.read_parquet(str(parquet_file))

                            # Get column names to create dict from rows
                            column_names = relation.columns
                            rows = relation.fetchall()

                            for row_tuple in rows:
                                row = dict(zip(column_names, row_tuple))
                                event_id = row["id"]

                                # Skip duplicate events
                                if event_id in seen_ids:
                                    _logger.debug("Skipping duplicate event %s", event_id)
                                    continue

                                seen_ids.add(event_id)

                                # Filter by timestamp if since provided
                                event_timestamp = datetime.fromisoformat(row["timestamp"])
                                if since and event_timestamp < since:
                                    continue

                                # Parse JSON fields
                                new_state: dict[str, object] = {}
                                if row["new_state"]:
                                    try:
                                        new_state = json.loads(row["new_state"])
                                    except (json.JSONDecodeError, TypeError) as e:
                                        error_msg = f"Failed to parse new_state JSON for event {event_id} in {parquet_file}: {e}"
                                        _logger.error(error_msg)
                                        raise RuntimeError(error_msg) from e

                                previous_state = None
                                if row["previous_state"]:
                                    try:
                                        previous_state = json.loads(row["previous_state"])
                                    except (json.JSONDecodeError, TypeError) as e:
                                        error_msg = f"Failed to parse previous_state JSON for event {event_id} in {parquet_file}: {e}"
                                        _logger.error(error_msg)
                                        raise RuntimeError(error_msg) from e

                                event = ChangeEvent(
                                    id=event_id,
                                    entity_id=row["entity_id"],
                                    entity_type=row["entity_type"],
                                    operation=ChangeOperation(row["operation"]),
                                    timestamp=event_timestamp,
                                    processed=bool(row.get("processed", False)),
                                    user_id=row.get("user_id"),
                                    change_reason=row.get("change_reason"),
                                    new_state=new_state,
                                    previous_state=previous_state,
                                )
                                events.append(event)

                        except RuntimeError:
                            raise
                        except (ValueError, TypeError, KeyError, OSError) as e:
                            error_msg = f"Failed to read Parquet file {parquet_file}: {e}"
                            _logger.error(error_msg)
                            raise RuntimeError(error_msg) from e

                _logger.info(
                    "Pulled %d change events from Parquet files (deduplicated)", len(events)
                )
                span.set_attribute("sync.record_count", len(events))
                return events

            except RuntimeError:
                raise
            except (ValueError, TypeError, KeyError, OSError) as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                error_msg = f"Failed to read Parquet files: {e}"
                _logger.error(error_msg)
                raise RuntimeError(error_msg) from e

    def is_configured(self) -> bool:
        """
        Check if sync target is properly configured.

        Returns:
            True if output directory is accessible, False otherwise
        """
        try:
            return self._changes_dir.exists() and self._changes_dir.is_dir()
        except OSError as e:
            _logger.warning(
                "Failed to check sync directory status (dir=%s): %s",
                self._changes_dir,
                e,
            )
            return False

    def get_sync_status(self) -> SyncStatus:
        """
        Get the status of remote synchronization.

        Returns:
            SyncStatus with last sync timestamps, pending changes count, and remote connectivity

        Raises:
            RuntimeError: If unable to check directory status
        """
        try:
            last_sync = None
            unprocessed_count = 0
            is_degraded = False

            if self._changes_dir.exists() and self._changes_dir.is_dir():
                # Get the most recent file timestamp
                most_recent_mtime = None
                for date_dir in self._changes_dir.iterdir():
                    if date_dir.is_dir():
                        for parquet_file in date_dir.glob("*.parquet"):
                            mtime = datetime.fromtimestamp(
                                parquet_file.stat().st_mtime, tz=timezone.utc
                            )
                            if most_recent_mtime is None or mtime > most_recent_mtime:
                                most_recent_mtime = mtime

                last_sync = most_recent_mtime

            # Query repository for actual unprocessed count
            if self._change_repo:
                try:
                    unprocessed_count = self._change_repo.count_unprocessed()
                except (RuntimeError, OSError) as e:
                    _logger.warning("Failed to count unprocessed changes: %s", str(e))
                    is_degraded = True

            _logger.info("Retrieved sync status from local Parquet files")
            return SyncStatus(
                last_pushed_at=last_sync,
                last_pulled_at=last_sync,
                unprocessed_count=unprocessed_count,
                is_configured=self.is_configured(),
                is_degraded=is_degraded,
            )

        except (ValueError, TypeError, KeyError, OSError) as e:
            error_msg = f"Failed to get sync status: {e}"
            _logger.error(error_msg)
            raise RuntimeError(error_msg) from e
