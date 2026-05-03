"""
Services for the Data Interchange bounded context.

Manages import runs and provides correlation context for tracking
import operations across domain layer boundaries.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from .entities import ImportRun
from .value_objects import SerializationScope

# Context variable for tracking the current import run ID across async boundaries
_import_run_context: ContextVar[Optional[str]] = ContextVar(
    "import_run_id", default=None
)


def get_current_import_run_id() -> Optional[str]:
    """
    Get the current import run ID from context.

    Returns None if no import is in progress.
    """
    return _import_run_context.get()


def set_import_run_context(import_run_id: Optional[str]) -> None:
    """
    Set the current import run ID in context.

    Args:
        import_run_id: The import run ID, or None to clear context
    """
    _import_run_context.set(import_run_id)


class ImportRunService:
    """
    Service for managing import run lifecycle.

    Provides methods to create, commit, fail, and rollback import runs,
    as well as querying run details and associated change events.
    """

    def start_run(
        self,
        format: str,
        source_hash: str,
        scope: SerializationScope,
        source_uri: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> ImportRun:
        """
        Create and start a new import run.

        Creates a fresh ImportRun entity in PENDING status. Callers should
        set the correlation context immediately after calling this method
        so that subsequent change recordings will be linked to this run.

        Args:
            format: Format of the imported file (skos, owl, graphml, etc.)
            source_hash: SHA256 hash of the imported bytes
            scope: Describes what is being imported
            source_uri: Optional URI or filename of the source
            created_by: Optional ID of the user initiating the import

        Returns:
            A new ImportRun entity in PENDING status

        Raises:
            ValueError: If format or scope is invalid
        """
        scope.validate()

        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            format=format,
            source_uri=source_uri,
            source_hash=source_hash,
            scope=scope,
        )

        return import_run

    def commit_run(self, import_run: ImportRun) -> ImportRun:
        """
        Mark an import run as committed.

        Transitions the run from PENDING to COMMITTED status.

        Args:
            import_run: The ImportRun to commit

        Returns:
            The updated ImportRun

        Raises:
            ValueError: If the run is already in a terminal state (COMMITTED, FAILED, or ROLLED_BACK)
        """
        import_run.mark_committed()
        return import_run

    def fail_run(self, import_run: ImportRun) -> ImportRun:
        """
        Mark an import run as failed.

        Transitions the run to FAILED status. A failed run cannot be
        committed or rolled back.

        Args:
            import_run: The ImportRun to fail

        Returns:
            The updated ImportRun

        Raises:
            ValueError: If the run is in a terminal state
        """
        import_run.mark_failed()
        return import_run

    def rollback_run(self, import_run: ImportRun) -> ImportRun:
        """
        Mark an import run as rolled back.

        Transitions the run to ROLLED_BACK status. A committed run cannot
        be rolled back. This method only changes status; actual undo of
        mutations is a follow-up feature.

        Args:
            import_run: The ImportRun to rollback

        Returns:
            The updated ImportRun

        Raises:
            ValueError: If the run is COMMITTED
        """
        import_run.mark_rolled_back()
        return import_run

    def get_context_import_run_id(self) -> Optional[str]:
        """
        Get the current import run ID from the correlation context.

        Returns:
            The import run ID if inside an import operation, None otherwise
        """
        return get_current_import_run_id()

    def set_context_import_run_id(self, import_run_id: Optional[str]) -> None:
        """
        Set the current import run ID in the correlation context.

        This is called by the ChangeEventRecorder to establish the link
        between change events and the import operation that caused them.

        Args:
            import_run_id: The import run ID, or None to clear context
        """
        set_import_run_context(import_run_id)
