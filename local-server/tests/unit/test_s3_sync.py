"""
Unit tests for S3SyncAdapter.

Tests cover ClientError handling in push(), pull() (both inner and outer blocks),
and get_sync_status() methods, as well as normal operation flows.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from domain.versioning.entities import ChangeEvent
from domain.versioning.value_objects import ChangeOperation


class MockClientError(Exception):
    """Mock botocore.exceptions.ClientError for testing."""

    def __init__(self, error_response, operation_name):
        self.response = error_response
        self.operation_name = operation_name
        super().__init__(f"{operation_name} failed: {error_response}")


class TestS3SyncAdapterClientErrorHandling:
    """Test ClientError exception handling in S3SyncAdapter methods."""

    @pytest.fixture
    def adapter(self):
        """Create an S3SyncAdapter instance with mocked components."""
        from adapters.sync.s3_sync import S3SyncAdapter

        # Create adapter instance manually, bypassing __init__
        adapter = S3SyncAdapter.__new__(S3SyncAdapter)
        adapter._bucket = "test-bucket"
        adapter._prefix = "test-prefix"
        adapter._region = "us-east-1"
        adapter._change_repo = None
        adapter._s3_client = Mock()
        adapter._client_error = MockClientError

        return adapter

    def test_push_raises_runtime_error_on_client_error(self, adapter):
        """Test that push() raises RuntimeError when S3 put_object raises ClientError."""

        adapter._s3_client.put_object.side_effect = MockClientError(
            {"Error": {"Code": "AccessDenied"}}, "PutObject"
        )

        event = ChangeEvent(
            id="event-1",
            entity_id="entity-1",
            entity_type="TaxonomyEntity",
            operation=ChangeOperation.CREATE,
            timestamp=datetime.now(timezone.utc),
            processed=False,
            user_id="user-1",
            change_reason="Test change",
            new_state={"name": "Test"},
            previous_state=None,
        )

        with pytest.raises(RuntimeError, match="Failed to push changes to S3"):
            adapter.push([event])

    def test_pull_raises_runtime_error_on_download_client_error(self, adapter):
        """Test that pull() raises RuntimeError when get_object raises ClientError."""
        # Mock paginator and list response
        mock_paginator = Mock()
        mock_page = {"Contents": [{"Key": "test-prefix/changes/2026-01-15/uuid-1.jsonl"}]}
        mock_paginator.paginate.return_value = [mock_page]
        adapter._s3_client.get_paginator.return_value = mock_paginator

        # Mock get_object to raise ClientError
        adapter._s3_client.get_object.side_effect = MockClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )

        with pytest.raises(RuntimeError, match="Failed to download S3 object"):
            adapter.pull()

    def test_pull_raises_runtime_error_on_listing_client_error(self, adapter):
        """Test that pull() raises RuntimeError when list_objects_v2 raises ClientError."""
        # Mock paginator to raise ClientError on paginate
        mock_paginator = Mock()
        mock_paginator.paginate.side_effect = MockClientError(
            {"Error": {"Code": "AccessDenied"}}, "ListObjects"
        )
        adapter._s3_client.get_paginator.return_value = mock_paginator

        with pytest.raises(RuntimeError, match="Failed to list S3 objects"):
            adapter.pull()

    def test_pull_raises_runtime_error_on_parse_error(self, adapter):
        """Test that pull() raises RuntimeError when JSON parsing fails."""
        # Mock paginator and list response
        mock_paginator = Mock()
        mock_page = {"Contents": [{"Key": "test-prefix/changes/2026-01-15/uuid-1.jsonl"}]}
        mock_paginator.paginate.return_value = [mock_page]
        adapter._s3_client.get_paginator.return_value = mock_paginator

        # Mock get_object to return invalid JSON
        mock_response = {"Body": Mock()}
        mock_response["Body"].read.return_value = b"invalid json{{"
        adapter._s3_client.get_object.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to parse S3 object"):
            adapter.pull()

    def test_get_sync_status_raises_runtime_error_on_client_error(self, adapter):
        """Test that get_sync_status() raises RuntimeError when list_objects_v2 raises
        ClientError."""
        # Mock paginator to raise ClientError on paginate
        mock_paginator = Mock()
        mock_paginator.paginate.side_effect = MockClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "ListObjects"
        )
        adapter._s3_client.get_paginator.return_value = mock_paginator

        with pytest.raises(RuntimeError, match="Failed to get sync status from S3"):
            adapter.get_sync_status()

    def test_push_success(self, adapter):
        """Test successful push operation."""
        adapter._s3_client.put_object.return_value = {}

        event = ChangeEvent(
            id="event-1",
            entity_id="entity-1",
            entity_type="TaxonomyEntity",
            operation=ChangeOperation.CREATE,
            timestamp=datetime.now(timezone.utc),
            processed=False,
            user_id="user-1",
            change_reason="Test change",
            new_state={"name": "Test"},
            previous_state=None,
        )

        result = adapter.push([event])

        assert result.pushed == 1
        assert result.pulled == 0
        assert len(result.pushed_event_ids) == 1
        assert result.pushed_event_ids[0] == "event-1"
        adapter._s3_client.put_object.assert_called_once()

    def test_pull_success(self, adapter):
        """Test successful pull operation with valid JSON."""
        # Mock paginator and list response
        mock_paginator = Mock()
        mock_page = {"Contents": [{"Key": "test-prefix/changes/2026-01-15/uuid-1.jsonl"}]}
        mock_paginator.paginate.return_value = [mock_page]
        adapter._s3_client.get_paginator.return_value = mock_paginator

        # Mock get_object to return valid JSON
        mock_response = {"Body": Mock()}
        json_data = (
            '{"id": "event-1", "entity_id": "entity-1", "entity_type":'
            ' "TaxonomyEntity", "operation": "create", "timestamp":'
            ' "2026-01-15T12:00:00+00:00", "processed": false, "user_id": "user-1",'
            ' "change_reason": "Test change", "new_state": {"name": "Test"},'
            ' "previous_state": null}'
        )
        mock_response["Body"].read.return_value = json_data.encode("utf-8")
        adapter._s3_client.get_object.return_value = mock_response

        events = adapter.pull()

        assert len(events) == 1
        assert events[0].id == "event-1"
        assert events[0].entity_id == "entity-1"

    def test_get_sync_status_success(self, adapter):
        """Test successful get_sync_status operation."""
        # Mock paginator and list response
        mock_paginator = Mock()
        mock_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_page = {
            "Contents": [
                {
                    "Key": "test-prefix/changes/2026-01-15/uuid-1.jsonl",
                    "LastModified": mock_time,
                }
            ]
        }
        mock_paginator.paginate.return_value = [mock_page]
        adapter._s3_client.get_paginator.return_value = mock_paginator

        status = adapter.get_sync_status()

        assert status.is_configured is True
        assert status.unprocessed_count == 0
