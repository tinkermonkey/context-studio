"""
RAG Observability Data Cleanup Scheduler

This module provides scheduled cleanup of old RAG observability data
based on retention policies (30 days for metrics, 7 days for traces).
"""
import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from rag.observability_store import RAGObservabilityStore
from utils.logger import get_logger

logger = get_logger(__name__)


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
            logger.warning("Cleanup scheduler is already running")
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
                await self._task
            except asyncio.CancelledError:
                pass
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
            result = await asyncio.to_thread(self.observability_store.cleanup_old_data)

            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"RAG cleanup completed in {elapsed:.2f}s: "
                f"{result['metrics_deleted']} metrics, {result['traces_deleted']} traces deleted"
            )

        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}", exc_info=True)

    async def run_now(self) -> dict:
        """
        Run cleanup immediately (for manual triggering).

        Returns:
            Dictionary with cleanup results
        """
        logger.info("Running manual RAG observability cleanup...")
        return await asyncio.to_thread(self.observability_store.cleanup_old_data)
