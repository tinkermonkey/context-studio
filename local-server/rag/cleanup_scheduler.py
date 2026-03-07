"""
RAG Observability Data Cleanup Scheduler

This module provides scheduled cleanup of old RAG observability data
based on retention policies (30 days for metrics, 7 days for traces).
"""
import asyncio
import sys
from datetime import datetime
from typing import Optional, TypeVar, Callable, Any
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from rag.observability_store import RAGObservabilityStore
from utils.logger import get_logger

logger = get_logger(__name__)

# Python version compatibility check
PYTHON_VERSION = sys.version_info
HAS_ASYNCIO_TO_THREAD = PYTHON_VERSION >= (3, 9)

# Thread pool executor for Python < 3.9 compatibility
_thread_pool_executor = None if HAS_ASYNCIO_TO_THREAD else ThreadPoolExecutor(max_workers=2)

T = TypeVar("T")


async def _run_in_thread(func: Callable[..., T], *args: Any) -> T:
    """
    Cross-version compatible way to run blocking code in a thread.

    Uses asyncio.to_thread in Python 3.9+ and ThreadPoolExecutor for older versions.
    """
    if HAS_ASYNCIO_TO_THREAD:
        return await asyncio.to_thread(func, *args)
    else:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_thread_pool_executor, func, *args)


class RAGCleanupScheduler:
    """
    Scheduler for periodic cleanup of RAG observability data.

    Runs cleanup task at configured intervals to remove data exceeding retention periods.
    """

    def __init__(
        self,
        ops_db_session: Session,
        cleanup_interval_hours: int = 24
    ):
        """
        Initialize RAG Cleanup Scheduler.

        Args:
            ops_db_session: Database session for operations.db
            cleanup_interval_hours: Hours between cleanup runs (default: 24)
        """
        self.ops_db_session = ops_db_session
        self.cleanup_interval_hours = cleanup_interval_hours
        self.observability_store = RAGObservabilityStore(ops_db_session)
        self._task: Optional[asyncio.Task] = None
        self._running = False
        logger.info(f"RAGCleanupScheduler initialized with interval={cleanup_interval_hours}h")

    def start(self):
        """Start the cleanup scheduler."""
        if self._running:
            logger.debug("Cleanup scheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("RAG cleanup scheduler started")

    async def stop(self):
        """Stop the cleanup scheduler gracefully."""
        if not self._running:
            return

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                # Properly await task completion to avoid race condition
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.CancelledError:
                # Expected when task is cancelled
                pass
            except asyncio.TimeoutError:
                logger.warning("Cleanup task did not complete within timeout, forcing termination")
            except Exception as e:
                logger.error(f"Error while stopping cleanup scheduler: {e}", exc_info=True)
        logger.info("RAG cleanup scheduler stopped")

    async def _cleanup_loop(self):
        """Main cleanup loop that runs periodically."""
        logger.info("RAG cleanup loop started")

        while self._running:
            try:
                # Wait for next cleanup interval
                await asyncio.sleep(self.cleanup_interval_hours * 3600)

                if not self._running:
                    break

                # Perform cleanup
                logger.info("Running scheduled RAG observability cleanup...")
                await self._run_cleanup()

            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def _run_cleanup(self):
        """Execute the cleanup operation."""
        try:
            start_time = datetime.now()

            # Run cleanup in thread to avoid blocking asyncio loop
            result = await _run_in_thread(self.observability_store.cleanup_old_data)

            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"RAG cleanup completed in {elapsed:.2f}s: "
                f"{result['metrics_deleted']} metrics, {result['traces_deleted']} traces deleted"
            )

        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}", exc_info=True)

    async def run_now(self) -> dict[str, int]:
        """
        Run cleanup immediately (for manual triggering).

        Returns:
            Dictionary with cleanup results
        """
        try:
            start_time = datetime.now()
            logger.info("Running manual RAG observability cleanup...")

            result = await _run_in_thread(self.observability_store.cleanup_old_data)

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Manual RAG cleanup completed in {elapsed:.2f}s: "
                f"{result['metrics_deleted']} metrics, {result['traces_deleted']} traces deleted"
            )

            return result
        except Exception as e:
            logger.error(f"Manual cleanup operation failed: {e}", exc_info=True)
            raise
