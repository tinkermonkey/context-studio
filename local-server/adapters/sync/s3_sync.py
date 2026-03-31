"""
S3-based synchronization adapter for the Version Control & Collaboration bounded context.

The S3SyncAdapter implements the SyncTarget port, enabling workspaces to synchronize
changes with remote S3 locations. Changes are serialized as JSON Lines and stored
with a key pattern: {prefix}/changes/{date}/{uuid}.jsonl

This adapter gracefully handles S3 configuration errors and network failures.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import uuid4

from domain.versioning.entities import ChangeEvent
from domain.versioning.value_objects import SyncResult

_logger = logging.getLogger(__name__)


class S3SyncAdapter:
    """
    Implements SyncTarget using AWS S3 for push/pull synchronization.

    Changes are serialized as JSON Lines (one event per line) and stored in S3
    with a predictable key structure that enables date-based filtering.

    This adapter is fault-tolerant: S3 errors are caught and returned in SyncResult,
    never propagated to the caller.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str,
        aws_access_key: str,
        aws_secret_key: str,
        region: str,
    ) -> None:
        """
        Initialize the S3 sync adapter.

        Args:
            bucket: S3 bucket name
            prefix: Prefix path within the bucket (e.g., 'context-studio/workspace-1')
            aws_access_key: AWS access key ID
            aws_secret_key: AWS secret access key
            region: AWS region (e.g., 'us-east-1')

        Raises:
            ImportError: If boto3 is not installed
        """
        try:
            import boto3
        except ImportError:
            _logger.error("boto3 is required for S3 sync adapter. Install with: pip install boto3")
            raise

        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._region = region

        try:
            self._s3_client = boto3.client(
                "s3",
                region_name=region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
            )
            # Test connectivity
            self._s3_client.head_bucket(Bucket=bucket)
            _logger.info(
                "S3SyncAdapter initialized (bucket=%s, prefix=%s, region=%s)",
                bucket,
                prefix,
                region,
            )
            self._configured = True
        except Exception as e:
            _logger.error(f"Failed to initialize S3 client: {e}")
            self._configured = False
            self._s3_client = None

    def push(self, events: Sequence[ChangeEvent]) -> SyncResult:
        """
        Push local change events to S3.

        Serializes events as JSON Lines and uploads to S3 with key pattern:
        {prefix}/changes/{yyyy-mm-dd}/{uuid}.jsonl

        Args:
            events: Sequence of ChangeEvent objects to push

        Returns:
            SyncResult with count of pushed events and any errors
        """
        if not self._configured or self._s3_client is None:
            _logger.debug("S3 not configured, skipping push")
            return SyncResult(pushed=0, pulled=0, errors=[])

        if not events:
            return SyncResult(pushed=0, pulled=0, errors=[])

        try:
            # Serialize events as JSON Lines
            lines = []
            for event in events:
                line = json.dumps(
                    {
                        "id": event.id,
                        "entity_id": event.entity_id,
                        "entity_type": event.entity_type,
                        "operation": event.operation,
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
            return SyncResult(pushed=len(events), pulled=0, errors=[])

        except Exception as e:
            error_msg = f"Failed to push changes to S3: {e}"
            _logger.error(error_msg)
            return SyncResult(pushed=0, pulled=0, errors=[error_msg])

    def pull(self, since: Optional[datetime] = None) -> list[ChangeEvent]:
        """
        Pull change events from S3.

        Lists objects in {prefix}/changes/ directory, filters by date if since provided,
        downloads and deserializes JSON Lines files.

        Args:
            since: Optional timestamp to fetch changes after

        Returns:
            List of deserialized ChangeEvent objects from S3
        """
        if not self._configured or self._s3_client is None:
            _logger.debug("S3 not configured, skipping pull")
            return []

        try:
            events: list[ChangeEvent] = []
            prefix = f"{self._prefix}/changes/"

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
                                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                                    tzinfo=timezone.utc
                                )
                                if file_date < since:
                                    continue
                            except (ValueError, IndexError):
                                continue

                    # Download and deserialize the file
                    try:
                        response = self._s3_client.get_object(Bucket=self._bucket, Key=key)
                        content = response["Body"].read().decode("utf-8")

                        # Parse JSON Lines
                        for line in content.strip().split("\n"):
                            if not line:
                                continue
                            data = json.loads(line)
                            event = ChangeEvent(
                                id=data["id"],
                                entity_id=data["entity_id"],
                                entity_type=data["entity_type"],
                                operation=data["operation"],
                                timestamp=datetime.fromisoformat(data["timestamp"]),
                                processed=data.get("processed", False),
                                user_id=data.get("user_id"),
                                change_reason=data.get("change_reason"),
                                new_state=data.get("new_state"),
                                previous_state=data.get("previous_state"),
                            )
                            events.append(event)
                    except Exception as e:
                        _logger.error(f"Failed to parse S3 object {key}: {e}")
                        continue

            _logger.info("Pulled %d change events from S3", len(events))
            return events

        except Exception as e:
            error_msg = f"Failed to pull changes from S3: {e}"
            _logger.error(error_msg)
            return []

    def is_configured(self) -> bool:
        """
        Check if S3 sync target is properly configured.

        Returns:
            True if S3 client is initialized and bucket is accessible, False otherwise
        """
        return self._configured
