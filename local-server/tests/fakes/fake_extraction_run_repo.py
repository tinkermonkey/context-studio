"""Fake in-memory implementation of ExtractionRunRepository for testing."""

import os
import sys
from typing import Sequence
from domain.extraction.entities import ExtractionRun

class FakeExtractionRunRepository:
    """In-memory repository for extraction runs."""

    def __init__(self) -> None:
        self._runs: dict[str, ExtractionRun] = {}

    def save_extraction_run(self, run: ExtractionRun) -> ExtractionRun:
        """
        Save an extraction run to persistent storage.

        Args:
            run: The ExtractionRun to save

        Returns:
            The saved ExtractionRun
        """

        self._runs[run.id] = run
        return run

    def get_extraction_run(self, run_id: str) -> ExtractionRun | None:
        """
        Retrieve an extraction run by ID.

        Args:
            run_id: The ID of the extraction run

        Returns:
            The ExtractionRun or None if not found
        """
        return self._runs.get(run_id)

    def list_extraction_runs(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionRun]:
        """
        List extraction runs with pagination.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of ExtractionRun objects
        """
        runs = list(self._runs.values())
        # Sort by created_at descending (most recent first) - assuming ExtractionRun has created_at
        # For now, just return the requested slice
        return runs[offset : offset + limit]

    def update_extraction_run(self, run: ExtractionRun) -> ExtractionRun:
        """
        Update an existing extraction run.

        Args:
            run: The ExtractionRun with updated fields

        Returns:
            The updated ExtractionRun

        Raises:
            ValueError: If run not found
        """
        if run.id not in self._runs:
            raise ValueError(f"ExtractionRun with id {run.id} not found")
        self._runs[run.id] = run
        return run
