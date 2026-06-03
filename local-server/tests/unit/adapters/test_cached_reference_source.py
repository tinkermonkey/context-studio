"""Unit tests for CachedReferenceSource decorator."""

import tempfile
from pathlib import Path

from adapters.reference.cache import CachedReferenceSource
from domain.extraction.ports import ReferenceRelation, ReferenceResult


class FakeReferenceSource:
    """Mock ReferenceSource for testing."""

    def __init__(self):
        """Initialize the fake source."""
        self.search_call_count = 0
        self.relations_call_count = 0
        self._available = True

    @property
    def source_name(self) -> str:
        """Get source name."""
        return "TestSource"

    def is_available(self) -> bool:
        """Check if available."""
        return self._available

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """Search implementation."""
        self.search_call_count += 1
        return [
            ReferenceResult(
                uri=f"http://test.org/{term}_{i}",
                label=f"{term} {i}",
                description=f"Result for {term}",
                source=self.source_name,
            )
            for i in range(min(limit, 3))
        ]

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """Get relations implementation."""
        self.relations_call_count += 1
        return [
            ReferenceRelation(
                subject_uri=uri,
                predicate="isRelatedTo",
                object_uri=f"http://test.org/related_{i}",
                source=self.source_name,
            )
            for i in range(min(limit, 2))
        ]

    async def search_async(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """Async search implementation."""
        return self.search(term, limit)

    async def get_relations_async(
        self, uri: str, limit: int = 10
    ) -> list[ReferenceRelation]:
        """Async get relations implementation."""
        return self.get_relations(uri, limit)

    async def is_available_async(self) -> bool:
        """Async is available implementation."""
        return self.is_available()


class TestCachedReferenceSourceInit:
    """Test CachedReferenceSource initialization."""

    def test_init_creates_cache_db(self) -> None:
        """Test that initialization creates the cache database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()

            _cached = CachedReferenceSource(inner, str(cache_db))

            # Verify database was created
            assert cache_db.exists()

    def test_init_creates_cache_tables(self) -> None:
        """Test that initialization creates required tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()

            _cached = CachedReferenceSource(inner, str(cache_db))

            # Verify tables exist
            import sqlite3

            with sqlite3.connect(str(cache_db)) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row[0] for row in cursor.fetchall()]

                assert "cache" in tables
                assert "relations_cache" in tables


class TestCachedReferenceSourceSearch:
    """Test CachedReferenceSource search caching."""

    def test_search_cache_miss_calls_inner(self) -> None:
        """Test that cache miss calls the inner source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            results = cached.search("test", limit=5)

            assert inner.search_call_count == 1
            assert len(results) == 3  # FakeReferenceSource returns 3 results

    def test_search_cache_hit_does_not_call_inner(self) -> None:
        """Test that cache hit does not call the inner source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            # First call - cache miss
            results1 = cached.search("test", limit=5)
            assert inner.search_call_count == 1

            # Second call - cache hit
            results2 = cached.search("test", limit=5)
            assert inner.search_call_count == 1  # Not incremented

            # Results should be identical
            assert results1 == results2

    def test_search_different_terms_are_cached_separately(self) -> None:
        """Test that different search terms have separate cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            _results1 = cached.search("apple", limit=5)
            assert inner.search_call_count == 1

            _results2 = cached.search("banana", limit=5)
            assert inner.search_call_count == 2

            # Repeat first search - should use cache
            _results3 = cached.search("apple", limit=5)
            assert inner.search_call_count == 2

    def test_search_different_limits_are_cached_separately(self) -> None:
        """Test that different limits have separate cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            _results1 = cached.search("test", limit=5)
            assert inner.search_call_count == 1

            _results2 = cached.search("test", limit=10)
            assert inner.search_call_count == 2


class TestCachedReferenceSourceRelations:
    """Test CachedReferenceSource relation caching."""

    def test_get_relations_cache_miss_calls_inner(self) -> None:
        """Test that cache miss calls the inner source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            relations = cached.get_relations("http://test.org/entity", limit=5)

            assert inner.relations_call_count == 1
            assert len(relations) == 2  # FakeReferenceSource returns 2 relations

    def test_get_relations_cache_hit_does_not_call_inner(self) -> None:
        """Test that cache hit does not call the inner source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            uri = "http://test.org/entity"

            # First call - cache miss
            relations1 = cached.get_relations(uri, limit=5)
            assert inner.relations_call_count == 1

            # Second call - cache hit
            relations2 = cached.get_relations(uri, limit=5)
            assert inner.relations_call_count == 1  # Not incremented

            # Results should be identical
            assert relations1 == relations2

    def test_get_relations_different_uris_are_cached_separately(self) -> None:
        """Test that different URIs have separate cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            _relations1 = cached.get_relations("http://test.org/entity1", limit=5)
            assert inner.relations_call_count == 1

            _relations2 = cached.get_relations("http://test.org/entity2", limit=5)
            assert inner.relations_call_count == 2


class TestCachedReferenceSourceSourceName:
    """Test CachedReferenceSource source_name delegation."""

    def test_source_name_returns_inner_source_name(self) -> None:
        """Test that source_name returns the inner source's name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            assert cached.source_name == "TestSource"

    def test_is_available_returns_inner_availability(self) -> None:
        """Test that is_available delegates to inner source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = FakeReferenceSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            assert cached.is_available() is True

            inner._available = False
            assert cached.is_available() is False
