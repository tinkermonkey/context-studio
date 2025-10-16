"""
Rate-limited web search client for concept resolution.

Implements token bucket algorithm for rate limiting and provides
context-aware search queries.
"""
from typing import Optional, Dict, Any
import time
import threading
from dataclasses import dataclass
from datetime import datetime
import requests

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
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
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
        timeout_seconds: int = 10
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
        domain_context: Optional[str] = None,
        grammatical_context: Optional[str] = None
    ) -> Optional[SearchResult]:
        """
        Perform rate-limited web search.

        Args:
            query: Search query
            domain_context: Optional domain context to enrich query
            grammatical_context: Optional grammatical hints (verb relationships)

        Returns:
            SearchResult if successful, None if rate limited or failed
        """
        # Check session limit
        if not self.can_search():
            logger.warning(
                f"Web search session limit reached ({self.max_attempts_per_session}), "
                f"skipping query: {query}"
            )
            return None

        # Wait for rate limit token
        if not self.rate_limiter.consume():
            wait_time = self.rate_limiter.wait_time()
            logger.info(f"Rate limit reached, waiting {wait_time:.2f}s before search")
            time.sleep(wait_time)
            if not self.rate_limiter.consume():
                logger.warning(f"Failed to acquire rate limit token for query: {query}")
                return None

        # Increment session counter
        with self.session_lock:
            self.session_attempt_count += 1

        # Build context-aware query
        enriched_query = self._build_context_aware_query(
            query, domain_context, grammatical_context
        )

        logger.info(f"Performing web search (attempt {self.session_attempt_count}): {enriched_query}")

        try:
            # Perform search using DuckDuckGo Instant Answer API
            # This is a free API that doesn't require authentication
            result = self._search_duckduckgo(enriched_query)

            if result:
                logger.debug(f"Web search successful: {result.title}")
                return result
            else:
                logger.debug(f"Web search returned no results for: {enriched_query}")
                return None

        except Exception as e:
            logger.error(f"Web search failed for query '{enriched_query}': {e}")
            return None

    def _build_context_aware_query(
        self,
        query: str,
        domain_context: Optional[str],
        grammatical_context: Optional[str]
    ) -> str:
        """
        Build context-aware search query.

        Args:
            query: Base query
            domain_context: Domain context from recognized entities
            grammatical_context: Grammatical hints

        Returns:
            Enriched query string
        """
        parts = [query]

        if domain_context:
            parts.append(domain_context)

        if grammatical_context:
            parts.append(f"related to {grammatical_context}")

        # Add "definition" to get better results
        parts.append("definition")

        return " ".join(parts)

    def _search_duckduckgo(self, query: str) -> Optional[SearchResult]:
        """
        Search using DuckDuckGo Instant Answer API.

        Args:
            query: Search query

        Returns:
            SearchResult if found, None otherwise
        """
        try:
            # DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                'q': query,
                'format': 'json',
                'no_html': 1,
                'skip_disambig': 1
            }

            response = requests.get(
                url,
                params=params,
                timeout=self.timeout_seconds,
                headers={'User-Agent': 'ContextStudio/1.0 (Educational RAG System)'}
            )

            if response.status_code != 200:
                logger.warning(f"DuckDuckGo API returned status {response.status_code}")
                return None

            data = response.json()

            # Try to extract definition from various fields
            title = data.get('Heading', query)
            snippet = (
                data.get('AbstractText') or
                data.get('Abstract') or
                data.get('Definition', '')
            )

            if not snippet:
                # Try related topics
                related = data.get('RelatedTopics', [])
                if related and isinstance(related, list) and len(related) > 0:
                    first_topic = related[0]
                    if isinstance(first_topic, dict):
                        snippet = first_topic.get('Text', '')

            if not snippet:
                logger.debug(f"No definition found in DuckDuckGo response for: {query}")
                return None

            result = SearchResult(
                query=query,
                title=title,
                snippet=snippet,
                url=data.get('AbstractURL', ''),
                timestamp=datetime.now()
            )

            return result

        except requests.Timeout:
            logger.warning(f"Web search timeout for query: {query}")
            return None
        except Exception as e:
            logger.error(f"Error in DuckDuckGo search: {e}")
            return None

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get current session statistics.

        Returns:
            Dictionary with session stats
        """
        with self.session_lock:
            return {
                'attempts_used': self.session_attempt_count,
                'attempts_remaining': max(0, self.max_attempts_per_session - self.session_attempt_count),
                'max_attempts': self.max_attempts_per_session
            }
