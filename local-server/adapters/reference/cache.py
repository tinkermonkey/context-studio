"""Caching decorator for reference sources."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from domain.extraction.ports import ReferenceSource, ReferenceResult, ReferenceRelation
from utils.logger import get_logger

logger = get_logger(__name__)


class CachedReferenceSource:
    """
    Decorator that wraps a ReferenceSource and caches results.

    Caches search results and relationships to an SQLite database for
    efficiency when querying the same terms repeatedly. TTL-based expiry
    ensures stale data is eventually refreshed.
    """

    def __init__(
        self,
        inner: ReferenceSource,
        cache_db_path: str = "./reference_api_cache.db",
        ttl_hours: int = 168,
    ):
        """
        Initialize the caching decorator.

        Automatically creates the cache database on initialization if it doesn't exist.

        Args:
            inner: The wrapped ReferenceSource implementation
            cache_db_path: Path to the SQLite cache database
            ttl_hours: Cache time-to-live in hours (default: 168 = 1 week)
        """
        self._inner = inner
        self._cache_db_path = cache_db_path
        self._ttl_hours = ttl_hours
        self._ensure_cache_db()

    def _ensure_cache_db(self) -> None:
        """
        Create cache database and tables if they don't exist.

        Creates two tables:
        - cache: Caches search results with TTL
        - relations_cache: Caches relationship queries with TTL
        """
        try:
            Path(self._cache_db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self._cache_db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        cached_at TEXT NOT NULL
                    )
                    """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS relations_cache (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        cached_at TEXT NOT NULL
                    )
                    """
                )

                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to initialize cache database: {e}")

    @property
    def source_name(self) -> str:
        """
        Get the name of the wrapped reference source.

        Returns:
            The inner source's name
        """
        return self._inner.source_name

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]:
        """
        Search for entities, using cache if available.

        Cache key is constructed from source name, term, and limit to ensure
        different limits get separate cache entries.

        Args:
            term: Search query
            limit: Maximum number of results

        Returns:
            List of ReferenceResult objects from cache or inner source
        """
        cache_key = f"search:{self.source_name}:{term}:{limit}"
        cached = self._get_cached(cache_key)

        if cached is not None:
            logger.debug(f"Cache hit for {cache_key}")
            return cached

        logger.debug(f"Cache miss for {cache_key}, calling inner source")
        results = self._inner.search(term, limit)
        self._set_cached(cache_key, results, is_relations=False)

        return results

    def get_relations(self, uri: str, limit: int = 10) -> list[ReferenceRelation]:
        """
        Get relationships for a URI, using cache if available.

        Cache key is constructed from source name, URI, and limit.

        Args:
            uri: URI to find relations for
            limit: Maximum number of relations

        Returns:
            List of ReferenceRelation objects from cache or inner source
        """
        cache_key = f"relations:{self.source_name}:{uri}:{limit}"
        cached = self._get_cached(cache_key, is_relations=True)

        if cached is not None:
            logger.debug(f"Cache hit for {cache_key}")
            return cached

        logger.debug(f"Cache miss for {cache_key}, calling inner source")
        relations = self._inner.get_relations(uri, limit)
        self._set_cached(cache_key, relations, is_relations=True)

        return relations

    def is_available(self) -> bool:
        """
        Check if the wrapped source is available.

        Returns:
            True if the inner source is available, False otherwise
        """
        return self._inner.is_available()

    def _get_cached(
        self, key: str, is_relations: bool = False
    ) -> list[ReferenceResult] | list[ReferenceRelation] | None:
        """
        Retrieve a value from cache if it exists and hasn't expired.

        Args:
            key: Cache key
            is_relations: If True, parse as ReferenceRelation; else as ReferenceResult

        Returns:
            Cached value if found and not expired, None otherwise
        """
        try:
            table = "relations_cache" if is_relations else "cache"

            with sqlite3.connect(self._cache_db_path) as conn:
                cursor = conn.execute(
                    f"SELECT value, cached_at FROM {table} WHERE key = ?",
                    (key,),
                )
                row = cursor.fetchone()

                if row is None:
                    return None

                value_json, cached_at_str = row

                # Check if entry has expired
                cached_at = datetime.fromisoformat(cached_at_str)
                expiry_at = cached_at + timedelta(hours=self._ttl_hours)

                if datetime.now() > expiry_at:
                    logger.debug(f"Cache entry expired: {key}")
                    conn.execute(f"DELETE FROM {table} WHERE key = ?", (key,))
                    conn.commit()
                    return None

                # Parse cached value
                data = json.loads(value_json)

                if is_relations:
                    return [
                        ReferenceRelation(
                            subject_uri=item["subject_uri"],
                            predicate=item["predicate"],
                            object_uri=item["object_uri"],
                            source=item.get("source", ""),
                        )
                        for item in data
                    ]
                else:
                    return [
                        ReferenceResult(
                            uri=item["uri"],
                            label=item["label"],
                            description=item.get("description"),
                            source=item.get("source", ""),
                        )
                        for item in data
                    ]

        except Exception as e:
            logger.warning(f"Failed to retrieve cache entry {key}: {e}")
            return None

    def _set_cached(
        self,
        key: str,
        value: list[ReferenceResult] | list[ReferenceRelation],
        is_relations: bool = False,
    ) -> None:
        """
        Store a value in cache.

        Args:
            key: Cache key
            value: Value to cache (list of results or relations)
            is_relations: If True, store in relations_cache; else in cache
        """
        try:
            table = "relations_cache" if is_relations else "cache"

            # Convert dataclass objects to dicts for JSON serialization
            serializable_value = []
            for item in value:
                if is_relations:
                    serializable_value.append(
                        {
                            "subject_uri": item.subject_uri,
                            "predicate": item.predicate,
                            "object_uri": item.object_uri,
                            "source": item.source,
                        }
                    )
                else:
                    serializable_value.append(
                        {
                            "uri": item.uri,
                            "label": item.label,
                            "description": item.description,
                            "source": item.source,
                        }
                    )

            value_json = json.dumps(serializable_value)
            cached_at = datetime.now().isoformat()

            with sqlite3.connect(self._cache_db_path) as conn:
                conn.execute(
                    f"INSERT OR REPLACE INTO {table} (key, value, cached_at) VALUES (?, ?, ?)",
                    (key, value_json, cached_at),
                )
                conn.commit()

        except Exception as e:
            logger.warning(f"Failed to cache entry {key}: {e}")
