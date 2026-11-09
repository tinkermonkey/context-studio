"""
Reference proxy lifecycle.

Runs the reference-api-buddy caching proxy in-process so every ConceptNet, DBpedia
and Wikidata call is cached and rate limited per source. The source adapters send
their requests to `ReferenceProxy.base_url(source)`, which is the proxy while it
runs and the source's own API when the proxy is off or failed to start.
"""

import os
from typing import Any

from reference_api_buddy.cache.engine import CacheEngine
from reference_api_buddy.core.proxy import CachingProxy
from reference_api_buddy.database.models import CachedResponse

from config import ReferenceProxyConfig
from utils.logger import get_logger

logger = get_logger(__name__)

PROXY_HOST = "127.0.0.1"

# Longest the proxy holds a request to stay under a rate limit; past that it answers
# 429 at once. Kept well inside the source adapters' 10-30s request timeouts.
MAX_THROTTLE_DELAY_SECONDS = 5

# reference-api-buddy evicts past 1,000 entries by default, too few for bulk enrichment.
MAX_CACHE_ENTRIES = 100_000

MAX_CACHED_RESPONSE_BYTES = 10 * 1024 * 1024


class SuccessOnlyCacheEngine(CacheEngine):
    """
    Caches successful upstream responses only.

    reference-api-buddy 0.5.0 turns an upstream error into a 502 and caches it for
    the full TTL, so a single outage would blank a search term for a week.
    """

    def set(
        self, cache_key: str, response: CachedResponse, domain_key: str | None = None
    ) -> bool:
        """Store the response unless it is an error."""
        if response.status_code >= 400:
            return False
        return super().set(cache_key, response, domain_key=domain_key)


class ReferenceProxy:
    """Starts, stops and addresses the in-process reference proxy."""

    def __init__(self, config: ReferenceProxyConfig):
        """
        Initialize the proxy lifecycle.

        Args:
            config: The `reference.proxy` section of config.json
        """
        self._config = config
        self._proxy: CachingProxy | None = None

    @property
    def running(self) -> bool:
        """Whether the proxy is serving requests."""
        return self._proxy is not None

    @property
    def port(self) -> int | None:
        """The local port the proxy listens on, or None when it is not running."""
        if self._proxy is None or self._proxy.server is None:
            return None
        return self._proxy.server.server_address[1]

    def start(self) -> None:
        """
        Start the proxy on a free local port.

        Never raises: if the proxy is disabled or cannot start, it stays stopped and
        `base_url` hands out each source's own API instead.
        """
        if not self._config.enabled:
            logger.info("Reference proxy disabled; reference sources call their APIs directly")
            return
        if self._proxy is not None:
            return

        proxy: CachingProxy | None = None
        try:
            cache_dir = os.path.dirname(self._config.cache_db_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)

            proxy = CachingProxy(self._proxy_config())
            proxy.cache_engine = SuccessOnlyCacheEngine(
                proxy.db_manager,
                config=proxy.config,
                max_response_size=MAX_CACHED_RESPONSE_BYTES,
                max_cache_entries=MAX_CACHE_ENTRIES,
            )
            proxy.start(blocking=False)
        except Exception as e:
            logger.error(
                f"Reference proxy failed to start; reference sources will call their "
                f"APIs directly, without caching or rate limits: {e}"
            )
            if proxy is not None:
                try:
                    proxy.stop()
                except Exception as stop_error:
                    logger.warning(f"Error cleaning up the reference proxy: {stop_error}")
            return

        self._proxy = proxy
        logger.info(
            f"Reference proxy listening on {PROXY_HOST}:{self.port}, "
            f"cache at {self._config.cache_db_path}"
        )

    def stop(self) -> None:
        """Stop the proxy and close its cache database. Safe to call when stopped."""
        if self._proxy is None:
            return
        try:
            self._proxy.stop()
            logger.info("Reference proxy stopped")
        except Exception as e:
            logger.error(f"Error stopping the reference proxy: {e}")
        finally:
            self._proxy = None

    def base_url(self, source: str) -> str:
        """
        Where a source adapter should send its requests.

        Args:
            source: A key of `reference.proxy.sources` (conceptnet, dbpedia, wikidata)

        Returns:
            The proxy's URL for that source while the proxy runs, else the source's API
        """
        upstream = self.upstream_url(source)
        if self._proxy is None:
            return upstream
        return f"http://{PROXY_HOST}:{self.port}/{source}"

    def upstream_url(self, source: str) -> str:
        """The source's own API, from config."""
        return getattr(self._config.sources, source).upstream

    def _proxy_config(self) -> dict[str, Any]:
        """Translate the `reference.proxy` section into reference-api-buddy's config."""
        sources = dict(self._config.sources)
        return {
            "server": {"host": PROXY_HOST, "port": 0},
            "security": {"require_secure_key": False, "log_security_events": False},
            "cache": {
                "database_path": self._config.cache_db_path,
                "max_cache_response_size": MAX_CACHED_RESPONSE_BYTES,
                "default_ttl_seconds": self._config.cache_ttl_hours * 3600,
            },
            "domain_mappings": {name: {"upstream": src.upstream} for name, src in sources.items()},
            "throttling": {
                "progressive_max_delay": MAX_THROTTLE_DELAY_SECONDS,
                "domain_limits": {name: src.requests_per_hour for name, src in sources.items()},
            },
            "admin": {"enabled": False},
            "logging": {"level": "WARNING"},
        }
