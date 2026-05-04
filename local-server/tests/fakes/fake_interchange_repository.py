"""
Fake in-memory implementation of ImportRunRepository for testing.

Provides a simple implementation suitable for integration tests
without requiring database persistence.
"""

from typing import Optional

from domain.interchange.entities import ImportRun, ImportRunStatus
from domain.interchange.value_objects import ChangeEvent


class FakeInterchangeRepository:
    """
    Fake in-memory repository for ImportRun entities.

    Stores all runs in memory and supports filtering by status.
    Suitable for unit and integration tests.
    """

    def __init__(self):
        """Initialize the repository with an empty store."""
        self.runs: dict[str, ImportRun] = {}
        self.change_events: dict[str, list[dict]] = {}

    def create(self, import_run: ImportRun) -> ImportRun:
        """
        Store a new import run.

        Args:
            import_run: The ImportRun to store

        Returns:
            The stored ImportRun
        """
        self.runs[import_run.id] = import_run
        # Initialize empty change events list for this run
        self.change_events[import_run.id] = []
        return import_run

    def get(self, import_run_id: str) -> Optional[ImportRun]:
        """
        Retrieve an import run by ID.

        Args:
            import_run_id: The ID of the ImportRun

        Returns:
            The ImportRun if found, None otherwise
        """
        return self.runs.get(import_run_id)

    def list_all(self, limit: int = 100, offset: int = 0) -> list[ImportRun]:
        """
        Retrieve all import runs with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of ImportRun entities sorted by creation time (newest first)
        """
        sorted_runs = sorted(
            self.runs.values(), key=lambda r: r.created_at, reverse=True
        )
        return sorted_runs[offset : offset + limit]

    def list_by_status(
        self, status: ImportRunStatus, limit: int = 100, offset: int = 0
    ) -> list[ImportRun]:
        """
        Retrieve import runs filtered by status.

        Args:
            status: The status to filter by
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of ImportRun entities with the given status
        """
        filtered = [r for r in self.runs.values() if r.status == status]
        sorted_runs = sorted(filtered, key=lambda r: r.created_at, reverse=True)
        return sorted_runs[offset : offset + limit]

    def update(self, import_run: ImportRun) -> ImportRun:
        """
        Update an existing import run.

        Args:
            import_run: The ImportRun with updated state

        Returns:
            The updated ImportRun

        Raises:
            RuntimeError: If the run does not exist
        """
        if import_run.id not in self.runs:
            raise RuntimeError(f"ImportRun {import_run.id} not found")
        self.runs[import_run.id] = import_run
        return import_run

    def count_all(self) -> int:
        """
        Count total number of import runs.

        Returns:
            Total count of all import runs
        """
        return len(self.runs)

    def count_by_status(self, status: ImportRunStatus) -> int:
        """
        Count import runs filtered by status.

        Args:
            status: The status to filter by

        Returns:
            Total count of import runs with the given status
        """
        return sum(1 for r in self.runs.values() if r.status == status)

    def get_change_events_for_run(self, import_run_id: str) -> list[ChangeEvent]:
        """
        Retrieve change events associated with an import run.

        Args:
            import_run_id: The ID of the import run

        Returns:
            List of ChangeEvent domain objects for the run
        """
        events = self.change_events.get(import_run_id, [])
        return [
            ChangeEvent(
                id=e["id"],
                timestamp=e["timestamp"],
                entity_id=e["entity_id"],
                entity_type=e["entity_type"],
                operation=e["operation"],
                new_state=e.get("new_state"),
                previous_state=e.get("previous_state"),
            )
            for e in events
        ]

    def add_change_event(self, import_run_id: str, event: dict) -> None:
        """
        Add a change event to an import run (for testing).

        Args:
            import_run_id: The ID of the import run
            event: The change event dict
        """
        if import_run_id not in self.change_events:
            self.change_events[import_run_id] = []
        self.change_events[import_run_id].append(event)
