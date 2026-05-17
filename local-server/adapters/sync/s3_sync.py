"""
S3-based synchronization adapter for the Version Control & Collaboration bounded context.

The S3SyncAdapter implements the SyncTarget port, enabling workspaces to synchronize
changes with remote S3 locations. Changes are serialized as JSON Lines and stored
with a key pattern: {prefix}/changes/{date}/{uuid}.jsonl

This adapter uses fail-fast error handling: S3 configuration errors and network
failures are propagated to the caller as RuntimeError, never suppressed.
The service layer wraps these into domain-level SyncError exceptions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
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


class _S3FileParseError(RuntimeError):
    """
    Internal exception used to distinguish file parsing errors from S3 listing errors.

    This exception is raised when a downloaded S3 object fails to parse as JSON Lines,
    and is caught by the outer exception handler to be re-raised as SyncError.
    """

    pass


class S3SyncAdapter:
    """
    Implements SyncTarget using AWS S3 for push/pull synchronization.

    Changes are serialized as JSON Lines (one event per line) and stored in S3
    with a predictable key structure that enables date-based filtering.

    This adapter uses fail-fast error handling: S3 configuration errors and access
    failures are propagated to the caller as RuntimeError. The caller (service layer)
    wraps these into SyncError domain exceptions. The app.py handles initialization
    failures by falling back to NoOpSyncTarget.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str,
        aws_access_key: str,
        aws_secret_key: str,
        region: str,
        change_repo: "ChangeRepository | None" = None,
    ) -> None:
        """
        Initialize the S3 sync adapter.

        Args:
            bucket: S3 bucket name
            prefix: Prefix path within the bucket (e.g., 'context-studio/workspace-1')
            aws_access_key: AWS access key ID
            aws_secret_key: AWS secret access key
            region: AWS region (e.g., 'us-east-1')
            change_repo: Optional ChangeRepository for querying unprocessed changes

        Raises:
            ImportError: If boto3 is not installed
        """
        try:
            import boto3
            import botocore.exceptions
        except ImportError:
            _logger.error(
                "boto3 is required for S3 sync adapter. Install with: pip install boto3"
            )
            raise

        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._region = region
        self._change_repo = change_repo
        self._client_error = botocore.exceptions.ClientError

        self._s3_client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )
        _logger.info(
            "S3SyncAdapter initialized (bucket=%s, prefix=%s, region=%s)",
            bucket,
            prefix,
            region,
        )

    def push(self, events: Sequence[ChangeEvent]) -> SyncResult:
        """
        Push local change events to S3.

        Serializes events as JSON Lines and uploads to S3 with key pattern:
        {prefix}/changes/{yyyy-mm-dd}/{uuid}.jsonl

        Args:
            events: Sequence of ChangeEvent objects to push

        Returns:
            SyncResult with count of pushed events and their IDs

        Raises:
            RuntimeError: If S3 put operation fails
        """
        with tracer.start_as_current_span("sync.push.s3") as span:
            span.set_attribute("sync.adapter", "s3")
            span.set_attribute("sync.direction", "push")
            span.set_attribute("sync.record_count", len(events))
            span.set_attribute("sync.format", "jsonl")

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

            pushed_event_ids = []
            try:
                # Serialize events as JSON Lines
                lines = []
                for event in events:
                    pushed_event_ids.append(event.id)
                    line = json.dumps(
                        {
                            "id": event.id,
                            "entity_id": event.entity_id,
                            "entity_type": event.entity_type,
                            "operation": event.operation.value,
                            "timestamp": event.timestamp.isoformat(),
                            "processed": event.processed,
                            "user_id": event.user_id,
                            "change_reason": event.change_reason,
                            "new_state": event.new_state,
                            "previous_state": event.previous_state,
                        }
                    )
                    lines.append(line)

                content = "\n".join(lines)

                # Generate S3 key with date and UUID
                now = datetime.now(timezone.utc)
                date_str = now.strftime("%Y-%m-%d")
                uuid_str = str(uuid4())
                key = f"{self._prefix}/changes/{date_str}/{uuid_str}.jsonl"

                # Upload to S3
                self._s3_client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=content,
                    ContentType="application/x-ndjson",
                )

                _logger.info(
                    "Pushed %d change events to S3 (key=%s)",
                    len(events),
                    key,
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

            except (ValueError, TypeError, KeyError, OSError, self._client_error) as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                error_msg = f"Failed to push changes to S3: {e}"
                _logger.error(error_msg)
                raise RuntimeError(error_msg) from e

    def pull(self, since: Optional[datetime] = None) -> list[ChangeEvent]:
        """
        Pull change events from S3.

        Lists objects in {prefix}/changes/ directory, filters by date if since provided,
        downloads and deserializes JSON Lines files. Deduplicates events by ID to prevent
        processing the same change multiple times.

        Args:
            since: Optional timestamp to fetch changes after

        Returns:
            List of deduplicated ChangeEvent objects from S3

        Raises:
            RuntimeError: If S3 listing fails, file download fails, or JSON parsing fails
        """
        with tracer.start_as_current_span("sync.pull.s3") as span:
            span.set_attribute("sync.adapter", "s3")
            span.set_attribute("sync.direction", "pull")
            span.set_attribute("sync.format", "jsonl")

            events: list[ChangeEvent] = []
            seen_ids: set[str] = set()
            prefix = f"{self._prefix}/changes/"

            try:
                # List all objects with the changes prefix
                paginator = self._s3_client.get_paginator("list_objects_v2")
                pages = paginator.paginate(Bucket=self._bucket, Prefix=prefix)

                for page in pages:
                    if "Contents" not in page:
                        continue

                    for obj in page["Contents"]:
                        key = obj["Key"]
                        # Filter by date if since provided
                        if since:
                            # Extract date from key: {prefix}/changes/{yyyy-mm-dd}/{uuid}.jsonl
                            parts = key.split("/")
                            if len(parts) >= 3:
                                try:
                                    date_str = parts[-2]
                                    file_date = datetime.strptime(
                                        date_str, "%Y-%m-%d"
                                    ).replace(tzinfo=timezone.utc)
                                    # Only skip if file date is before the date part of since
                                    # (file_date is at midnight, so compare dates not times)
                                    if file_date.date() < since.date():
                                        continue
                                except (ValueError, IndexError):
                                    # When since is provided, skip S3 objects with unparseable date paths
                                    _logger.warning(
                                        "Skipping S3 object with unparseable date path (key=%s)",
                                        key,
                                    )
                                    continue
                        # If since is None, process all objects regardless of date format

                        # Download the file
                        try:
                            response = self._s3_client.get_object(
                                Bucket=self._bucket, Key=key
                            )
                            content = response["Body"].read().decode("utf-8")
                        except (OSError, self._client_error) as e:
                            error_msg = f"Failed to download S3 object {key}: {e}"
                            _logger.error(error_msg)
                            raise _S3FileParseError(error_msg) from e

                        # Parse JSON Lines
                        try:
                            for line in content.strip().split("\n"):
                                if not line:
                                    continue
                                data = json.loads(line)
                                event_id = data["id"]

                                # Skip duplicate events
                                if event_id in seen_ids:
                                    _logger.debug(f"Skipping duplicate event {event_id}")
                                    continue

                                seen_ids.add(event_id)
                                event = ChangeEvent(
                                    id=event_id,
                                    entity_id=data["entity_id"],
                                    entity_type=data["entity_type"],
                                    operation=ChangeOperation(data["operation"]),
                                    timestamp=datetime.fromisoformat(data["timestamp"]),
                                    processed=data.get("processed", False),
                                    user_id=data.get("user_id"),
                                    change_reason=data.get("change_reason"),
                                    new_state=data.get("new_state"),
                                    previous_state=data.get("previous_state"),
                                )
                                events.append(event)
                        except (ValueError, TypeError, KeyError) as e:
                            error_msg = f"Failed to parse S3 object {key}: {e}"
                            _logger.error(error_msg)
                            raise _S3FileParseError(error_msg) from e

                _logger.info("Pulled %d change events from S3 (deduplicated)", len(events))
                span.set_attribute("sync.record_count", len(events))
                return events

            except _S3FileParseError as e:
                # File parsing error already wrapped and logged
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise RuntimeError(str(e)) from e.__cause__
            except (ValueError, TypeError, KeyError, OSError, self._client_error) as e:
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                error_msg = f"Failed to list S3 objects: {e}"
                _logger.error(error_msg)
                raise RuntimeError(error_msg) from e

    def is_configured(self) -> bool:
        """
        Check if S3 sync target is properly configured.

        Returns:
            True if S3 client is initialized, False otherwise
        """
        return self._s3_client is not None

    def get_sync_status(self) -> SyncStatus:
        """
        Get the status of remote synchronization.

        Returns:
            SyncStatus with last sync timestamps, pending changes count, and remote connectivity

        Raises:
            RuntimeError: If unable to check S3 connectivity
        """
        try:
            # Check S3 connectivity by listing objects to find most recent sync
            prefix = f"{self._prefix}/changes/"
            paginator = self._s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self._bucket, Prefix=prefix)

            last_sync = None
            unprocessed_count = 0
            is_degraded = False

            # Iterate through all pages to find the most recent object
            all_objects = []
            for page in pages:
                if "Contents" in page:
                    all_objects.extend(page["Contents"])

            # Find the most recent object by modification time
            if all_objects:
                most_recent = max(all_objects, key=lambda x: x["LastModified"])
                last_sync = most_recent["LastModified"]

            # Query repository for actual unprocessed count
            if self._change_repo:
                try:
                    unprocessed_count = self._change_repo.count_unprocessed()
                except (RuntimeError, OSError) as e:
                    _logger.warning("Failed to count unprocessed changes: %s", str(e))
                    is_degraded = True

            _logger.info("Retrieved sync status from S3")
            return SyncStatus(
                last_pushed_at=last_sync,
                last_pulled_at=last_sync,
                unprocessed_count=unprocessed_count,
                is_configured=self.is_configured(),
                is_degraded=is_degraded,
            )

        except (ValueError, TypeError, KeyError, OSError, self._client_error) as e:
            error_msg = f"Failed to get sync status from S3: {e}"
            _logger.error(error_msg)
            raise RuntimeError(error_msg) from e
