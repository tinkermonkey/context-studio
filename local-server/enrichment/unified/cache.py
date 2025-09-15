"""Caching layer for unified reference facade"""

import json
import time
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

class MemoryCache:
    """Simple in-memory cache with TTL support"""

    def __init__(self, default_ttl: int = 300):
        """
        Initialize memory cache

        Args:
            default_ttl: Default time-to-live in seconds
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0
        }

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self._cache:
            entry = self._cache[key]
            if entry["expires_at"] > time.time():
                self._stats["hits"] += 1
                return entry["value"]
            else:
                # Expired entry
                del self._cache[key]
                self._stats["evictions"] += 1

        self._stats["misses"] += 1
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        ttl = ttl or self.default_ttl
        expires_at = time.time() + ttl

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": time.time()
        }
        self._stats["sets"] += 1

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._stats["evictions"] += len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0

        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "size": len(self._cache)
        }

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry["expires_at"] <= current_time
        ]

        for key in expired_keys:
            del self._cache[key]

        self._stats["evictions"] += len(expired_keys)
        return len(expired_keys)

class DatabaseCache:
    """SQLite-based persistent cache"""

    def __init__(self, db_path: str = "unified_cache.db", default_ttl: int = 300):
        """
        Initialize database cache

        Args:
            db_path: Path to SQLite database file
            default_ttl: Default time-to-live in seconds
        """
        self.db_path = db_path
        self.default_ttl = default_ttl
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS unified_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_unified_cache_expires
                ON unified_cache(expires_at)
            """)

    async def get(self, key: str) -> Optional[Any]:
        """Get value from database cache"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value FROM unified_cache WHERE key = ? AND expires_at > ?",
                    (key, datetime.utcnow())
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            logger.error(f"Database cache get error: {e}")

        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in database cache"""
        try:
            ttl = ttl or self.default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO unified_cache (key, value, expires_at)
                    VALUES (?, ?, ?)
                """, (key, json.dumps(value), expires_at))

        except Exception as e:
            logger.error(f"Database cache set error: {e}")

    async def delete(self, key: str) -> bool:
        """Delete value from database cache"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM unified_cache WHERE key = ?", (key,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Database cache delete error: {e}")
            return False

    async def clear(self) -> None:
        """Clear all cache entries"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM unified_cache")
        except Exception as e:
            logger.error(f"Database cache clear error: {e}")

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM unified_cache WHERE expires_at <= ?",
                    (datetime.utcnow(),)
                )
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Database cache cleanup error: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM unified_cache")
                total_entries = cursor.fetchone()[0]

                cursor = conn.execute(
                    "SELECT COUNT(*) FROM unified_cache WHERE expires_at > ?",
                    (datetime.utcnow(),)
                )
                valid_entries = cursor.fetchone()[0]

                return {
                    "total_entries": total_entries,
                    "valid_entries": valid_entries,
                    "expired_entries": total_entries - valid_entries
                }
        except Exception as e:
            logger.error(f"Database cache stats error: {e}")
            return {"error": str(e)}

class CacheManager:
    """Multi-level cache manager with memory and database tiers"""

    def __init__(
        self,
        memory_ttl: int = 300,
        db_ttl: int = 3600,
        db_path: str = "unified_cache.db"
    ):
        """
        Initialize cache manager

        Args:
            memory_ttl: Memory cache TTL in seconds
            db_ttl: Database cache TTL in seconds
            db_path: Path to cache database
        """
        self.memory_cache = MemoryCache(default_ttl=memory_ttl)
        self.db_cache = DatabaseCache(db_path=db_path, default_ttl=db_ttl)
        self._cleanup_task = None

    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop_cleanup_task(self):
        """Stop background cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _periodic_cleanup(self):
        """Periodic cleanup of expired entries"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                memory_cleaned = self.memory_cache.cleanup_expired()
                db_cleaned = self.db_cache.cleanup_expired()
                if memory_cleaned > 0 or db_cleaned > 0:
                    logger.info(f"Cache cleanup: {memory_cleaned} memory, {db_cleaned} database")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (memory first, then database)"""
        # Try memory cache first
        value = await self.memory_cache.get(key)
        if value is not None:
            return value

        # Try database cache
        value = await self.db_cache.get(key)
        if value is not None:
            # Populate memory cache for faster access
            await self.memory_cache.set(key, value)
            return value

        return None

    async def set(
        self,
        key: str,
        value: Any,
        memory_ttl: Optional[int] = None,
        db_ttl: Optional[int] = None
    ) -> None:
        """Set value in both cache tiers"""
        # Set in memory cache
        await self.memory_cache.set(key, value, memory_ttl)

        # Set in database cache
        await self.db_cache.set(key, value, db_ttl)

    async def delete(self, key: str) -> bool:
        """Delete value from both cache tiers"""
        memory_deleted = await self.memory_cache.delete(key)
        db_deleted = await self.db_cache.delete(key)
        return memory_deleted or db_deleted

    async def clear(self) -> None:
        """Clear both cache tiers"""
        await self.memory_cache.clear()
        await self.db_cache.clear()

    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        memory_stats = self.memory_cache.get_stats()
        db_stats = self.db_cache.get_stats()

        return {
            "memory": memory_stats,
            "database": db_stats,
            "total_hit_rate": memory_stats.get("hit_rate", 0)
        }