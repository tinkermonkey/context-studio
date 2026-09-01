"""
Rate-limited web search client for concept resolution.

Implements token bucket algorithm for rate limiting and provides
context-aware search queries. Uses the reference API caching proxy
when available for improved performance.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from config import get_settings
from nlp.proxy_manager import get_proxy_manager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Result from web search"""

    query: str
    title: str
    snippet: str
    url: str
    timestamp: datetime


class TokenBucket:
    """
    Token bucket implementation for rate limiting.

    Allows bursts up to bucket capacity while maintaining average rate.
    """

    def __init__(self, rate_per_minute: int):
        """
        Initialize token bucket.

        Args:
            rate_per_minute: Maximum requests per minute
        """
        self.capacity = rate_per_minute
        self.tokens = rate_per_minute
        self.rate = rate_per_minute / 60.0  # tokens per second
        self.last_update = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)  # type: ignore
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    def wait_time(self) -> float:
        """
        Calculate wait time until next token is available.

        Returns:
            Wait time in seconds
        """
        with self.lock:
            if self.tokens >= 1:
                return 0.0
            tokens_needed = 1 - self.tokens
            return tokens_needed / self.rate


class RateLimitedWebSearchClient:
    """
    Web search client with rate limiting and session limits.

    Implements token bucket rate limiting and per-session request limits.
    """

    def __init__(
        self,
        rate_limit_per_minute: int = 5,
        max_attempts_per_session: int = 10,
        timeout_seconds: int = 10,
    ):
        """
        Initialize rate-limited web search client.

        Args:
            rate_limit_per_minute: Maximum requests per minute (default: 5)
            max_attempts_per_session: Maximum requests per extraction session (default: 10)
            timeout_seconds: Request timeout in seconds (default: 10)
        """
        self.rate_limiter = TokenBucket(rate_limit_per_minute)
        self.max_attempts_per_session = max_attempts_per_session
        self.timeout_seconds = timeout_seconds
        self.session_attempt_count = 0
        self.session_lock = threading.Lock()

        logger.info(
            f"RateLimitedWebSearchClient initialized: "
            f"rate={rate_limit_per_minute}/min, max_per_session={max_attempts_per_session}"
        )

    def reset_session(self):
        """Reset session attempt counter for a new extraction session."""
        with self.session_lock:
            self.session_attempt_count = 0
            logger.debug("Web search session counter reset")

    def can_search(self) -> bool:
        """
        Check if search is allowed within session limits.

        Returns:
            True if search is allowed
        """
        with self.session_lock:
            return self.session_attempt_count < self.max_attempts_per_session

    def search(
        self,
        query: str,
        domain_context: str | None = None,
        grammatical_context: str | None = None,
    ) -> SearchResult | None:
        """
        Perform rate-limited web search.

        Args:
            query: Search query
            domain_context: Optional domain context to enrich query
            grammatical_context: Optional grammatical hints (verb relationships)

        Returns:
            SearchResult if successful (with query field populated),
            SearchResult with only query field if failed/rate-limited,
            None only if session limit exceeded
        """
        # Build context-aware query first (so we can always return it in trace)
        enriched_query = self._build_context_aware_query(
            query, domain_context, grammatical_context
        )

        # Check session limit
        if not self.can_search():
            logger.warning(
                f"Web search session limit reached ({self.max_attempts_per_session}), "
                f"skipping query: {enriched_query}"
            )
            return None

        # Wait for rate limit token
        if not self.rate_limiter.consume():
            wait_time = self.rate_limiter.wait_time()
            logger.info(f"Rate limit reached, waiting {wait_time:.2f}s before search")
            time.sleep(wait_time)
            if not self.rate_limiter.consume():
                logger.warning(
                    f"Failed to acquire rate limit token for query: {enriched_query}"
                )
                # Return SearchResult with just the query so it can be traced
                return SearchResult(
                    query=enriched_query,
                    title="",
                    snippet="",
                    url="",
                    timestamp=datetime.now(),
                )

        # Increment session counter
        with self.session_lock:
            self.session_attempt_count += 1

        logger.info(
            f"Performing web search (attempt {self.session_attempt_count}): {enriched_query}"
        )

        try:
            # Perform search using DuckDuckGo Instant Answer API
            # This is a free API that doesn't require authentication
            result = self._search_duckduckgo(enriched_query)

            if result:
                logger.debug(f"Web search successful: {result.title}")
                return result
            else:
                logger.debug(f"Web search returned no results for: {enriched_query}")
                # Return SearchResult with just the query so it can be traced
                return SearchResult(
                    query=enriched_query,
                    title="",
                    snippet="",
                    url="",
                    timestamp=datetime.now(),
                )

        except Exception as e:
            logger.error(f"Web search failed for query '{enriched_query}': {e}")
            # Return SearchResult with just the query so it can be traced
            return SearchResult(
                query=enriched_query,
                title="",
                snippet="",
                url="",
                timestamp=datetime.now(),
            )

    def _build_context_aware_query(
        self,
        query: str,
        domain_context: str | None,
        grammatical_context: str | None,
    ) -> str:
        """
        Build context-aware search query optimized for definition retrieval.

        DuckDuckGo Instant Answer API works best with simple, direct queries.
        The "definition of" prefix actually reduces results, so we use the term directly
        with optional domain context for disambiguation.

        Args:
            query: Base query (the term to define)
            domain_context: Domain context from recognized entities (for disambiguation)
            grammatical_context: Grammatical hints (verb relationships) - not currently used

        Returns:
            Enriched query string optimized for DuckDuckGo Instant Answer API
        """
        # DuckDuckGo works better with simple queries, not "definition of" prefix
        base_query = query

        # Add domain context only if provided (helps with disambiguation)
        # e.g., "python programming" vs "python snake"
        if domain_context and domain_context.strip():
            # Use first entity from domain context to avoid overly long queries
            context_words = domain_context.split(",")[0].strip()
            if context_words:
                base_query = f"{query} {context_words}"

        return base_query

    def _get_base_url(self) -> str:
        """
        Get the base URL for DuckDuckGo API, using proxy if available.

        Returns:
            Base URL (proxy URL if proxy is running, otherwise upstream URL)
        """
        settings = get_settings()
        duckduckgo_config = settings.get_source_config("duckduckgo")

        # Check if proxy should be used
        if duckduckgo_config.use_proxy:
            proxy_manager = get_proxy_manager()
            if proxy_manager.is_running:
                proxy_config = proxy_manager.get_proxy_config()
                if proxy_config and "domain_mappings" in proxy_config:
                    if "duckduckgo" in proxy_config["domain_mappings"]:
                        server_config = proxy_config.get("server", {})
                        host = server_config.get("host", "127.0.0.1")
                        port = server_config.get("port", 18080)
                        proxy_url = f"http://{host}:{port}/duckduckgo"
                        logger.debug(f"Using proxy for DuckDuckGo: {proxy_url}")
                        return proxy_url

        # Fallback to upstream URL
        return duckduckgo_config.upstream_url

    def _search_duckduckgo(self, query: str) -> SearchResult | None:
        """
        Search using DuckDuckGo Instant Answer API.

        Uses the reference API caching proxy when available for improved
        performance and reduced API calls.

        Args:
            query: Search query

        Returns:
            SearchResult if found, None otherwise
        """
        try:
            # Get base URL (proxy or upstream)
            base_url = self._get_base_url()

            # Build full URL with query parameters
            params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}

            response = requests.get(
                base_url,
                params=params,  # type: ignore
                timeout=self.timeout_seconds,
                headers={"User-Agent": "ContextStudio/1.0 (Educational RAG System)"},
            )

            # DuckDuckGo returns 202 (Accepted) for many queries, not 200
            if response.status_code not in [200, 202]:
                logger.warning(
                    f"DuckDuckGo API returned status {response.status_code} from {base_url}"
                )
                return None

            data = response.json()

            # Try to extract definition from various fields
            title = data.get("Heading", query)
            snippet = (
                data.get("AbstractText")
                or data.get("Abstract")
                or data.get("Definition", "")
            )

            if not snippet:
                # Try related topics
                related = data.get("RelatedTopics", [])
                if related and isinstance(related, list) and len(related) > 0:
                    first_topic = related[0]
                    if isinstance(first_topic, dict):
                        snippet = first_topic.get("Text", "")

            if not snippet:
                logger.debug(f"No definition found in DuckDuckGo response for: {query}")
                return None

            result = SearchResult(
                query=query,
                title=title,
                snippet=snippet,
                url=data.get("AbstractURL", ""),
                timestamp=datetime.now(),
            )

            return result

        except requests.Timeout:
            logger.warning(f"Web search timeout for query: {query}")
            return None
        except Exception as e:
            logger.error(f"Error in DuckDuckGo search: {e}")
            return None

    def get_session_stats(self) -> dict[str, Any]:
        """
        Get current session statistics.

        Returns:
            Dictionary with session stats
        """
        with self.session_lock:
            return {
                "attempts_used": self.session_attempt_count,
                "attempts_remaining": max(
                    0, self.max_attempts_per_session - self.session_attempt_count
                ),
                "max_attempts": self.max_attempts_per_session,
            }
