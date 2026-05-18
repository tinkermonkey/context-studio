"""Fake in-memory implementation of ExtractionRepository for testing."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Sequence

from domain.extraction.entities import ExtractionResult


class FakeExtractionRepository:
    """In-memory repository for extraction results."""

    def __init__(self) -> None:
        self._results: dict[str, ExtractionResult] = {}

    def save_extraction_result(self, result: ExtractionResult) -> ExtractionResult:
        """
        Save an extraction result to persistent storage.

        Args:
            result: The ExtractionResult to save

        Returns:
            The saved ExtractionResult (may have updated metadata like id or timestamp)
        """
        self._results[result.id] = result
        return result

    def get_extraction_result(self, result_id: str) -> ExtractionResult | None:
        """
        Retrieve an extraction result by ID.

        Args:
            result_id: The ID of the extraction result

        Returns:
            The ExtractionResult or None if not found
        """
        return self._results.get(result_id)

    def list_extraction_results(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionResult]:
        """
        List extraction results with pagination.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Sequence of ExtractionResult objects
        """
        results = list(self._results.values())
        # Sort by created_at descending (most recent first)
        sorted_results = sorted(results, key=lambda r: r.created_at, reverse=True)
        return sorted_results[offset : offset + limit]
