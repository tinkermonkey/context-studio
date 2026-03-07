"""
Unit tests for versioning domain entities.

Tests validate invariant enforcement, enum usage, and immutability of
change events, entity versions, conflicts, and conflict reports.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import types
import pytest

from domain.versioning.entities import (
    ChangeEvent,
    EntityVersion,
    Conflict,
    ConflictReport,
    MergeResult,
    ChangeState
)
from domain.versioning.enums import ChangeType


class TestChangeState:
    """Tests for ChangeState enum."""

    def test_change_state_values(self):
        """Test that ChangeState has all expected values."""
        assert ChangeState.PENDING.value == "pending"
        assert ChangeState.SYNCED.value == "synced"
        assert ChangeState.CONFLICT.value == "conflict"


class TestChangeType:
    """Tests for ChangeType enum."""

    def test_change_type_values(self):
        """Test that ChangeType has all expected values."""
        assert ChangeType.CREATED.value == "created"
        assert ChangeType.UPDATED.value == "updated"
        assert ChangeType.DELETED.value == "deleted"


class TestChangeEvent:
    """Tests for ChangeEvent entity."""

    def test_valid_change_event_created(self):
        """Test creating a valid change event for creation."""
        event = ChangeEvent(
            id="change-1",
            entity_type="Class",
            entity_id="class-123",
            change_type=ChangeType.CREATED,
            payload=types.MappingProxyType({"title": "NewClass"}),
            occurred_at="2025-03-06T00:00:00Z",
            state=ChangeState.PENDING
        )
        assert event.id == "change-1"
        assert event.entity_type == "Class"
        assert event.change_type == ChangeType.CREATED

    def test_valid_change_event_updated(self):
        """Test creating a valid change event for update."""
        event = ChangeEvent(
            id="change-2",
            entity_type="Relationship",
            entity_id="rel-456",
            change_type=ChangeType.UPDATED,
            payload=types.MappingProxyType({"old_label": "knows", "new_label": "knows_well"}),
            occurred_at="2025-03-06T00:01:00Z",
            state=ChangeState.SYNCED
        )
        assert event.change_type == ChangeType.UPDATED
        assert event.state == ChangeState.SYNCED

    def test_valid_change_event_deleted(self):
        """Test creating a valid change event for deletion."""
        event = ChangeEvent(
            id="change-3",
            entity_type="Property",
            entity_id="prop-789",
            change_type=ChangeType.DELETED,
            payload=types.MappingProxyType({"deleted_at": "2025-03-06T00:02:00Z"}),
            occurred_at="2025-03-06T00:02:00Z",
            state=ChangeState.CONFLICT
        )
        assert event.change_type == ChangeType.DELETED
        assert event.state == ChangeState.CONFLICT

    def test_change_event_payload_immutable(self):
        """Test that payload is immutable."""
        event = ChangeEvent(
            id="change-1",
            entity_type="Class",
            entity_id="class-123",
            change_type=ChangeType.CREATED,
            payload=types.MappingProxyType({"title": "NewClass"}),
            occurred_at="2025-03-06T00:00:00Z"
        )
        with pytest.raises(TypeError):
            event.payload["title"] = "OtherClass"

    def test_change_event_invalid_id(self):
        """Test that empty id raises ValueError."""
        with pytest.raises(ValueError, match="ChangeEvent id must be a non-empty string"):
            ChangeEvent(
                id="",
                entity_type="Class",
                entity_id="class-123",
                change_type=ChangeType.CREATED,
                payload=types.MappingProxyType({}),
                occurred_at="2025-03-06T00:00:00Z"
            )

    def test_change_event_invalid_entity_type(self):
        """Test that empty entity_type raises ValueError."""
        with pytest.raises(ValueError, match="entity_type must be a non-empty string"):
            ChangeEvent(
                id="change-1",
                entity_type="",
                entity_id="class-123",
                change_type=ChangeType.CREATED,
                payload=types.MappingProxyType({}),
                occurred_at="2025-03-06T00:00:00Z"
            )

    def test_change_event_invalid_change_type(self):
        """Test that non-enum change_type raises TypeError."""
        with pytest.raises(TypeError, match="change_type must be a ChangeType enum"):
            ChangeEvent(
                id="change-1",
                entity_type="Class",
                entity_id="class-123",
                change_type="created",  # String instead of enum
                payload=types.MappingProxyType({}),
                occurred_at="2025-03-06T00:00:00Z"
            )

    def test_change_event_invalid_payload(self):
        """Test that non-MappingProxyType payload raises TypeError."""
        with pytest.raises(TypeError, match="payload must be a MappingProxyType"):
            ChangeEvent(
                id="change-1",
                entity_type="Class",
                entity_id="class-123",
                change_type=ChangeType.CREATED,
                payload={"title": "NewClass"},  # Dict instead of MappingProxyType
                occurred_at="2025-03-06T00:00:00Z"
            )


class TestEntityVersion:
    """Tests for EntityVersion entity."""

    def test_valid_entity_version(self):
        """Test creating a valid entity version."""
        version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({"title": "Class1", "description": "A class"}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        assert version.entity_id == "class-123"
        assert version.version == 1
        assert version.snapshot["title"] == "Class1"

    def test_entity_version_multiple_versions(self):
        """Test entity versions with different version numbers."""
        v1 = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({"title": "ClassV1"}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        v2 = EntityVersion(
            entity_id="class-123",
            version=2,
            snapshot=types.MappingProxyType({"title": "ClassV2"}),
            recorded_at="2025-03-06T00:01:00Z"
        )
        assert v1.version < v2.version

    def test_entity_version_snapshot_immutable(self):
        """Test that snapshot is immutable."""
        version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({"title": "Class1"}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        with pytest.raises(TypeError):
            version.snapshot["title"] = "Class2"

    def test_entity_version_invalid_entity_id(self):
        """Test that empty entity_id raises ValueError."""
        with pytest.raises(ValueError, match="entity_id must be a non-empty string"):
            EntityVersion(
                entity_id="",
                version=1,
                snapshot=types.MappingProxyType({}),
                recorded_at="2025-03-06T00:00:00Z"
            )

    def test_entity_version_invalid_version(self):
        """Test that non-positive version raises ValueError."""
        # Invalid: 0
        with pytest.raises(ValueError, match="version must be a positive integer"):
            EntityVersion(
                entity_id="class-123",
                version=0,
                snapshot=types.MappingProxyType({}),
                recorded_at="2025-03-06T00:00:00Z"
            )

        # Invalid: negative
        with pytest.raises(ValueError, match="version must be a positive integer"):
            EntityVersion(
                entity_id="class-123",
                version=-1,
                snapshot=types.MappingProxyType({}),
                recorded_at="2025-03-06T00:00:00Z"
            )


class TestConflict:
    """Tests for Conflict entity."""

    def test_valid_conflict(self):
        """Test creating a valid conflict."""
        local_version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({"title": "LocalClass"}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        remote_version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({"title": "RemoteClass"}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        conflict = Conflict(
            entity_id="class-123",
            local_version=local_version,
            remote_version=remote_version,
            conflict_fields=("title",)
        )
        assert conflict.entity_id == "class-123"
        assert len(conflict.conflict_fields) == 1
        assert conflict.conflict_fields[0] == "title"

    def test_conflict_multiple_conflict_fields(self):
        """Test conflict with multiple conflicting fields."""
        local_version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({"title": "LocalClass", "description": "Local"}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        remote_version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({"title": "RemoteClass", "description": "Remote"}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        conflict = Conflict(
            entity_id="class-123",
            local_version=local_version,
            remote_version=remote_version,
            conflict_fields=("title", "description")
        )
        assert len(conflict.conflict_fields) == 2

    def test_conflict_no_conflict_fields(self):
        """Test conflict with empty conflict fields."""
        version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        conflict = Conflict(
            entity_id="class-123",
            local_version=version,
            remote_version=version,
            conflict_fields=()
        )
        assert conflict.conflict_fields == ()

    def test_conflict_fields_immutable(self):
        """Test that conflict_fields tuple is immutable."""
        version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        conflict = Conflict(
            entity_id="class-123",
            local_version=version,
            remote_version=version,
            conflict_fields=("title",)
        )
        with pytest.raises((TypeError, AttributeError)):
            conflict.conflict_fields[0] = "description"

    def test_conflict_invalid_entity_id(self):
        """Test that empty entity_id raises ValueError."""
        version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        with pytest.raises(ValueError, match="entity_id must be a non-empty string"):
            Conflict(
                entity_id="",
                local_version=version,
                remote_version=version,
                conflict_fields=()
            )

    def test_conflict_invalid_conflict_fields_element(self):
        """Test that non-string conflict_fields elements raise TypeError."""
        version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        with pytest.raises(TypeError, match="All conflict_fields must be strings"):
            Conflict(
                entity_id="class-123",
                local_version=version,
                remote_version=version,
                conflict_fields=(123,)  # Integer instead of string
            )


class TestConflictReport:
    """Tests for ConflictReport entity."""

    def test_valid_conflict_report(self):
        """Test creating a valid conflict report."""
        version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        conflict = Conflict(
            entity_id="class-123",
            local_version=version,
            remote_version=version,
            conflict_fields=("title",)
        )
        report = ConflictReport(
            sync_id="sync-001",
            conflicts=(conflict,),
            generated_at="2025-03-06T00:02:00Z"
        )
        assert report.sync_id == "sync-001"
        assert len(report.conflicts) == 1

    def test_conflict_report_no_conflicts(self):
        """Test conflict report with no conflicts."""
        report = ConflictReport(
            sync_id="sync-001",
            conflicts=(),
            generated_at="2025-03-06T00:00:00Z"
        )
        assert report.conflicts == ()

    def test_conflict_report_conflicts_immutable(self):
        """Test that conflicts tuple is immutable."""
        version = EntityVersion(
            entity_id="class-123",
            version=1,
            snapshot=types.MappingProxyType({}),
            recorded_at="2025-03-06T00:00:00Z"
        )
        conflict = Conflict(
            entity_id="class-123",
            local_version=version,
            remote_version=version,
            conflict_fields=()
        )
        report = ConflictReport(
            sync_id="sync-001",
            conflicts=(conflict,),
            generated_at="2025-03-06T00:02:00Z"
        )
        with pytest.raises((TypeError, AttributeError)):
            report.conflicts[0] = None

    def test_conflict_report_invalid_sync_id(self):
        """Test that empty sync_id raises ValueError."""
        with pytest.raises(ValueError, match="sync_id must be a non-empty string"):
            ConflictReport(
                sync_id="",
                conflicts=(),
                generated_at="2025-03-06T00:00:00Z"
            )

    def test_conflict_report_invalid_generated_at(self):
        """Test that empty generated_at raises ValueError."""
        with pytest.raises(ValueError, match="generated_at must be a non-empty timestamp string"):
            ConflictReport(
                sync_id="sync-001",
                conflicts=(),
                generated_at=""
            )


class TestMergeResult:
    """Tests for MergeResult entity."""

    def test_valid_merge_result(self):
        """Test creating a valid merge result."""
        result = MergeResult(
            sync_id="sync-001",
            merged_count=10,
            conflict_count=2,
            skipped_count=3
        )
        assert result.sync_id == "sync-001"
        assert result.merged_count == 10
        assert result.conflict_count == 2
        assert result.skipped_count == 3

    def test_merge_result_all_counts_zero(self):
        """Test merge result with all counts as zero."""
        result = MergeResult(
            sync_id="sync-001",
            merged_count=0,
            conflict_count=0,
            skipped_count=0
        )
        assert result.merged_count == 0

    def test_merge_result_invalid_sync_id(self):
        """Test that empty sync_id raises ValueError."""
        with pytest.raises(ValueError, match="sync_id must be a non-empty string"):
            MergeResult(
                sync_id="",
                merged_count=0,
                conflict_count=0,
                skipped_count=0
            )

    def test_merge_result_invalid_merged_count(self):
        """Test that negative merged_count raises ValueError."""
        with pytest.raises(ValueError, match="merged_count must be a non-negative integer"):
            MergeResult(
                sync_id="sync-001",
                merged_count=-1,
                conflict_count=0,
                skipped_count=0
            )

    def test_merge_result_invalid_conflict_count(self):
        """Test that negative conflict_count raises ValueError."""
        with pytest.raises(ValueError, match="conflict_count must be a non-negative integer"):
            MergeResult(
                sync_id="sync-001",
                merged_count=0,
                conflict_count=-1,
                skipped_count=0
            )

    def test_merge_result_invalid_skipped_count(self):
        """Test that negative skipped_count raises ValueError."""
        with pytest.raises(ValueError, match="skipped_count must be a non-negative integer"):
            MergeResult(
                sync_id="sync-001",
                merged_count=0,
                conflict_count=0,
                skipped_count=-1
            )
