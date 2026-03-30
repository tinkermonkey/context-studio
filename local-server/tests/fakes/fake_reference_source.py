"""Fake implementation of ReferenceSource for testing."""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.extraction.ports import ReferenceRelation, ReferenceResult


class FakeReferenceSource:
    """Fake reference source that returns deterministic results for testing."""

    def __init__(self, name: str = "fake-source", should_fail: bool = False) -> None:
        """
        Initialize the fake reference source.

        Args:
            name: Name of the reference source
            should_fail: If True, raise RuntimeError on search() and get_relations() calls
        """
        self._name = name
        self.should_fail = should_fail
        self.call_count = 0
        self.last_search_term: str | None = None

    @property
    def source_name(self) -> str:
        """
        Get the name of this reference source.

        Returns:
            Human-readable name of the source
        """
        return self._name

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities matching a term.

        Returns a deterministic result for non-empty terms.

        Args:
            term: Search query
            limit: Maximum number of results

        Returns:
            List of matching ReferenceResult objects

        Raises:
            RuntimeError: If should_fail is True
        """
        if self.should_fail:
            raise RuntimeError("Reference source error")

        self.call_count += 1
        self.last_search_term = term

        if not term:
            return []

        # Create a deterministic URI from the search term
        uri = f"fake://{term.replace(' ', '_')}"

        return [
            ReferenceResult(
                uri=uri,
                label=term,
                description=f"Fake result for {term}",
                source=self._name,
            )
        ]

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships connected to a URI.

        Returns empty list for fake implementation.

        Args:
            uri: URI of the resource to find relations for
            limit: Maximum number of relations

        Returns:
            List of ReferenceRelation objects (empty for fake)

        Raises:
            RuntimeError: If should_fail is True
        """
        if self.should_fail:
            raise RuntimeError("Reference source error")

        return []

    def is_available(self) -> bool:
        """
        Check if this source is available.

        Returns:
            Always True for the fake implementation
        """
        return True

    async def search_async(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Async search for entities matching a term.

        Args:
            term: Search query
            limit: Maximum number of results

        Returns:
            List of matching ReferenceResult objects
        """
        return self.search(term, limit)

    async def get_relations_async(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Async get relationships connected to a URI.

        Args:
            uri: URI of the resource to find relations for
            limit: Maximum number of relations

        Returns:
            List of ReferenceRelation objects
        """
        return self.get_relations(uri, limit)

    async def is_available_async(self) -> bool:
        """
        Async check if this source is available.

        Returns:
            True for the fake implementation
        """
        return self.is_available()
