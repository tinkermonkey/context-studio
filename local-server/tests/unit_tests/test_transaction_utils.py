"""Unit tests for transaction utilities"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
from unittest.mock import Mock, MagicMock
from datetime import datetime

from database.transaction_utils import (
    atomic_transaction,
    check_optimistic_lock,
    create_audit_log,
    get_audit_history,
    invalidate_entity_cache,
    register_cache_invalidation_callback,
    OptimisticLockException,
    TransactionException
)
from database.models import AuditLog


class TestAtomicTransaction:
    """Test cases for atomic_transaction context manager."""

    def test_successful_transaction_commits(self):
        """Test that successful transaction commits changes."""
        mock_session = Mock()
        mock_session.execute = Mock()
        mock_session.commit = Mock()

        with atomic_transaction(mock_session):
            pass  # Successful transaction

        mock_session.commit.assert_called_once()

    def test_failed_transaction_rolls_back(self):
        """Test that failed transaction rolls back changes."""
        mock_session = Mock()
        mock_session.execute = Mock()
        mock_session.rollback = Mock()

        with pytest.raises(ValueError):
            with atomic_transaction(mock_session):
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()


class TestOptimisticLock:
    """Test cases for optimistic locking."""

    def test_optimistic_lock_success(self):
        """Test successful optimistic lock check."""
        mock_session = Mock()
        mock_entity = Mock()
        mock_entity.version = 5

        # Should not raise exception
        check_optimistic_lock(mock_session, mock_entity, 5)

    def test_optimistic_lock_failure(self):
        """Test failed optimistic lock check."""
        mock_session = Mock()
        mock_entity = Mock()
        mock_entity.version = 6

        with pytest.raises(OptimisticLockException) as exc_info:
            check_optimistic_lock(mock_session, mock_entity, 5)

        assert "expected version 5" in str(exc_info.value)
        assert "current version is 6" in str(exc_info.value)

    def test_optimistic_lock_missing_version_field(self):
        """Test optimistic lock with entity lacking version field."""
        mock_session = Mock()
        mock_entity = Mock(spec=[])  # Entity without version attribute

        # Should not raise exception (logs warning instead)
        check_optimistic_lock(mock_session, mock_entity, 5)


class TestCreateAuditLog:
    """Test cases for audit log creation."""

    def test_create_audit_log_basic(self):
        """Test basic audit log creation."""
        mock_session = Mock()
        mock_session.add = Mock()

        result = create_audit_log(
            mock_session,
            entity_type="predicate",
            entity_id="test-id",
            action="update",
            old_value={"field": "old"},
            new_value={"field": "new"}
        )

        mock_session.add.assert_called_once()
        assert isinstance(result, AuditLog)
        assert result.entity_type == "predicate"
        assert result.entity_id == "test-id"
        assert result.action == "update"

    def test_create_audit_log_with_execution_time(self):
        """Test audit log creation with execution time."""
        mock_session = Mock()
        mock_session.add = Mock()

        result = create_audit_log(
            mock_session,
            entity_type="predicate",
            entity_id="test-id",
            action="update",
            execution_time_ms=50
        )

        assert result.execution_time_ms == 50

    def test_create_audit_log_serializes_json(self):
        """Test that audit log properly serializes complex objects."""
        mock_session = Mock()
        mock_session.add = Mock()

        complex_value = {
            "nested": {"field": "value"},
            "array": [1, 2, 3]
        }

        result = create_audit_log(
            mock_session,
            entity_type="predicate",
            entity_id="test-id",
            action="create",
            new_value=complex_value
        )

        # Verify JSON serialization worked
        assert result.new_value is not None
        parsed = json.loads(result.new_value)
        assert parsed == complex_value


class TestCacheInvalidation:
    """Test cases for cache invalidation."""

    def test_register_cache_callback(self):
        """Test registering cache invalidation callback."""
        callback = Mock()

        register_cache_invalidation_callback("predicate", callback)

        # Verify callback is registered (will be called on invalidation)
        invalidate_entity_cache("predicate", "test-id")
        callback.assert_called_once_with("test-id")

    def test_cache_invalidation_handles_errors(self):
        """Test that cache invalidation handles callback errors gracefully."""
        def failing_callback(entity_id):
            raise ValueError("Test error")

        register_cache_invalidation_callback("predicate", failing_callback)

        # Should not raise exception
        invalidate_entity_cache("predicate", "test-id")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
