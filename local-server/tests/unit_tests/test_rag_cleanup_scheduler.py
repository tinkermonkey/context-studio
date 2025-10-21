"""
Unit tests for RAG Cleanup Scheduler.

Tests scheduled cleanup functionality for RAG observability data.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from rag.cleanup_scheduler import RAGCleanupScheduler


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = Mock()
    session.execute = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    return session


class TestRAGCleanupScheduler:
    """Test suite for RAG Cleanup Scheduler."""

    def test_initialization(self, mock_db_session):
        """Test scheduler initializes correctly."""
        scheduler = RAGCleanupScheduler(
            ops_db_session=mock_db_session,
            cleanup_interval_hours=12
        )

        assert scheduler.ops_db_session == mock_db_session
        assert scheduler.cleanup_interval_hours == 12
        assert scheduler._running is False
        assert scheduler._task is None
        assert scheduler.observability_store is not None

    def test_default_cleanup_interval(self, mock_db_session):
        """Test default cleanup interval is 24 hours."""
        scheduler = RAGCleanupScheduler(ops_db_session=mock_db_session)
        assert scheduler.cleanup_interval_hours == 24

    @pytest.mark.asyncio
    async def test_start_scheduler(self, mock_db_session):
        """Test starting the scheduler."""
        scheduler = RAGCleanupScheduler(
            ops_db_session=mock_db_session,
            cleanup_interval_hours=1
        )

        scheduler.start()

        assert scheduler._running is True
        assert scheduler._task is not None
        assert isinstance(scheduler._task, asyncio.Task)

        # Cleanup
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, mock_db_session):
        """Test starting scheduler when already running does nothing."""
        scheduler = RAGCleanupScheduler(
            ops_db_session=mock_db_session,
            cleanup_interval_hours=1
        )

        scheduler.start()
        first_task = scheduler._task

        # Try to start again
        scheduler.start()

        # Task should be the same
        assert scheduler._task is first_task

        # Cleanup
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, mock_db_session):
        """Test stopping the scheduler."""
        scheduler = RAGCleanupScheduler(
            ops_db_session=mock_db_session,
            cleanup_interval_hours=1
        )

        scheduler.start()
        assert scheduler._running is True

        await scheduler.stop()

        assert scheduler._running is False
        assert scheduler._task.cancelled() or scheduler._task.done()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, mock_db_session):
        """Test stopping scheduler when not running does nothing."""
        scheduler = RAGCleanupScheduler(
            ops_db_session=mock_db_session,
            cleanup_interval_hours=1
        )

        # Stop without starting
        await scheduler.stop()

        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_run_now(self, mock_db_session):
        """Test manual cleanup trigger."""
        with patch('rag.cleanup_scheduler.RAGObservabilityStore') as MockStore:
            mock_store = MockStore.return_value
            mock_store.cleanup_old_data.return_value = {
                "metrics_deleted": 10,
                "traces_deleted": 25
            }

            scheduler = RAGCleanupScheduler(
                ops_db_session=mock_db_session,
                cleanup_interval_hours=24
            )

            result = await scheduler.run_now()

            assert result["metrics_deleted"] == 10
            assert result["traces_deleted"] == 25
            mock_store.cleanup_old_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_loop_executes(self, mock_db_session):
        """Test that cleanup loop executes cleanup operation."""
        with patch('rag.cleanup_scheduler.RAGObservabilityStore') as MockStore:
            mock_store = MockStore.return_value
            mock_store.cleanup_old_data.return_value = {
                "metrics_deleted": 5,
                "traces_deleted": 15
            }

            # Use very short interval for testing
            scheduler = RAGCleanupScheduler(
                ops_db_session=mock_db_session,
                cleanup_interval_hours=0.0001  # ~0.36 seconds
            )

            scheduler.start()

            # Wait for at least one cleanup cycle
            await asyncio.sleep(1.0)

            # Stop the scheduler
            await scheduler.stop()

            # Verify cleanup was called
            assert mock_store.cleanup_old_data.call_count >= 1

    @pytest.mark.asyncio
    async def test_cleanup_loop_handles_errors(self, mock_db_session):
        """Test that cleanup loop continues despite errors."""
        with patch('rag.cleanup_scheduler.RAGObservabilityStore') as MockStore:
            mock_store = MockStore.return_value

            # First call raises exception, second succeeds
            mock_store.cleanup_old_data.side_effect = [
                Exception("Test error"),
                {"metrics_deleted": 1, "traces_deleted": 1}
            ]

            scheduler = RAGCleanupScheduler(
                ops_db_session=mock_db_session,
                cleanup_interval_hours=0.0001
            )

            scheduler.start()

            # Wait for multiple cleanup cycles
            await asyncio.sleep(2.0)

            # Stop the scheduler
            await scheduler.stop()

            # Verify cleanup was attempted multiple times despite error
            assert mock_store.cleanup_old_data.call_count >= 2

    @pytest.mark.asyncio
    async def test_cleanup_operation_logging(self, mock_db_session):
        """Test that cleanup operations are logged."""
        with patch('rag.cleanup_scheduler.RAGObservabilityStore') as MockStore, \
             patch('rag.cleanup_scheduler.logger') as mock_logger:

            mock_store = MockStore.return_value
            mock_store.cleanup_old_data.return_value = {
                "metrics_deleted": 3,
                "traces_deleted": 7
            }

            scheduler = RAGCleanupScheduler(
                ops_db_session=mock_db_session,
                cleanup_interval_hours=24
            )

            await scheduler.run_now()

            # Verify logging was called
            assert mock_logger.info.call_count >= 1

            # Check for cleanup completion log
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("cleanup completed" in str(call).lower() for call in log_calls)

    @pytest.mark.asyncio
    async def test_graceful_cancellation(self, mock_db_session):
        """Test that scheduler handles cancellation gracefully."""
        with patch('rag.cleanup_scheduler.RAGObservabilityStore') as MockStore:
            mock_store = MockStore.return_value
            mock_store.cleanup_old_data.return_value = {
                "metrics_deleted": 0,
                "traces_deleted": 0
            }

            scheduler = RAGCleanupScheduler(
                ops_db_session=mock_db_session,
                cleanup_interval_hours=24  # Long interval
            )

            scheduler.start()
            assert scheduler._running is True

            # Stop immediately (before first cleanup)
            await scheduler.stop()

            assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_stop_timeout_handling(self, mock_db_session):
        """Test stop handles timeout when task doesn't complete."""
        with patch('rag.cleanup_scheduler.RAGObservabilityStore') as MockStore, \
             patch('rag.cleanup_scheduler.logger') as mock_logger:

            mock_store = MockStore.return_value

            # Make cleanup_old_data take a long time
            async def slow_cleanup():
                await asyncio.sleep(10)
                return {"metrics_deleted": 0, "traces_deleted": 0}

            scheduler = RAGCleanupScheduler(
                ops_db_session=mock_db_session,
                cleanup_interval_hours=0.0001
            )

            scheduler.start()

            # Wait briefly
            await asyncio.sleep(0.1)

            # Stop should handle timeout
            await scheduler.stop()

            assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self, mock_db_session):
        """Test multiple start/stop cycles work correctly."""
        with patch('rag.cleanup_scheduler.RAGObservabilityStore') as MockStore:
            mock_store = MockStore.return_value
            mock_store.cleanup_old_data.return_value = {
                "metrics_deleted": 0,
                "traces_deleted": 0
            }

            scheduler = RAGCleanupScheduler(
                ops_db_session=mock_db_session,
                cleanup_interval_hours=24
            )

            # First cycle
            scheduler.start()
            assert scheduler._running is True
            await scheduler.stop()
            assert scheduler._running is False

            # Second cycle
            scheduler.start()
            assert scheduler._running is True
            await scheduler.stop()
            assert scheduler._running is False

            # Third cycle
            scheduler.start()
            assert scheduler._running is True
            await scheduler.stop()
            assert scheduler._running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
