"""
Rate limiting middleware for API endpoints.

This module provides a simple rate limiting mechanism to prevent API abuse
and protect server resources.
"""

import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from utils.logger import get_logger

logger = get_logger("rate_limiter")


class RateLimiter:
    """
    Simple in-memory rate limiter using sliding window algorithm.

    This implementation tracks request timestamps for each client and
    enforces rate limits based on configurable time windows.

    Attributes:
        max_requests: Maximum requests allowed per time window
        time_window: Time window in seconds
        requests: Dictionary tracking request timestamps per client
    """

    def __init__(self, max_requests: int = 10, time_window: int = 60):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed per time window (default: 10)
            time_window: Time window in seconds (default: 60)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, list] = defaultdict(list)
        logger.info(
            f"RateLimiter initialized: max_requests={max_requests}, "
            f"time_window={time_window}s"
        )

    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        """
        Check if a request from the client is allowed.

        This method implements a sliding window algorithm that:
        1. Removes expired timestamps (older than time_window)
        2. Checks if request count exceeds limit
        3. Records new request timestamp if allowed

        Args:
            client_id: Unique identifier for the client (e.g., IP address)

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        current_time = time.time()
        client_requests = self.requests[client_id]

        # Remove expired requests (outside time window)
        cutoff_time = current_time - self.time_window
        client_requests[:] = [
            req_time for req_time in client_requests
            if req_time > cutoff_time
        ]

        # Check if limit exceeded
        if len(client_requests) >= self.max_requests:
            remaining = 0
            allowed = False
        else:
            # Record new request
            client_requests.append(current_time)
            remaining = self.max_requests - len(client_requests)
            allowed = True

        return allowed, remaining

    def get_reset_time(self, client_id: str) -> int:
        """
        Get the time until rate limit reset for a client.

        Args:
            client_id: Unique identifier for the client

        Returns:
            Seconds until the oldest request expires (rate limit resets)
        """
        client_requests = self.requests[client_id]
        if not client_requests:
            return 0

        oldest_request = min(client_requests)
        reset_time = int(oldest_request + self.time_window - time.time())
        return max(0, reset_time)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting specific endpoints.

    This middleware applies rate limiting to endpoints matching configured
    path prefixes. Rate-limited requests receive a 429 Too Many Requests
    response with Retry-After header.
    """

    def __init__(
        self,
        app,
        max_requests: int = 10,
        time_window: int = 60,
        protected_paths: list = None
    ):
        """
        Initialize the rate limiter middleware.

        Args:
            app: FastAPI application instance
            max_requests: Maximum requests allowed per time window (default: 10)
            time_window: Time window in seconds (default: 60)
            protected_paths: List of path prefixes to protect (default: ["/api/predicates"])
        """
        super().__init__(app)
        self.rate_limiter = RateLimiter(max_requests, time_window)
        self.protected_paths = protected_paths or [
            "/api/predicates/",
            "/api/predicates/cluster-predicates",
            "/api/predicates/discover"
        ]
        logger.info(
            f"RateLimiterMiddleware initialized: protected_paths={self.protected_paths}"
        )

    async def dispatch(self, request: Request, call_next):
        """
        Process request and apply rate limiting if needed.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response

        Raises:
            HTTPException: 429 Too Many Requests if rate limit exceeded
        """
        # Check if path should be rate limited
        path = request.url.path
        should_rate_limit = any(
            path.startswith(protected) or path.endswith(protected)
            for protected in self.protected_paths
        )

        if should_rate_limit:
            # Use client IP as identifier
            client_id = self._get_client_id(request)

            # Check rate limit
            allowed, remaining = self.rate_limiter.is_allowed(client_id)

            if not allowed:
                reset_time = self.rate_limiter.get_reset_time(client_id)
                logger.warning(
                    f"Rate limit exceeded for client {client_id} on path {path}"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {reset_time} seconds.",
                    headers={"Retry-After": str(reset_time)}
                )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.max_requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(
                int(time.time() + self.rate_limiter.time_window)
            )
            return response
        else:
            # No rate limiting for this path
            return await call_next(request)

    def _get_client_id(self, request: Request) -> str:
        """
        Extract client identifier from request.

        Attempts to get the real client IP from X-Forwarded-For header
        (for proxied requests) or falls back to direct client host.

        Args:
            request: HTTP request

        Returns:
            Client identifier (IP address)
        """
        # Try X-Forwarded-For header first (for proxied requests)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in list (original client)
            return forwarded.split(",")[0].strip()

        # Fall back to direct client host
        return request.client.host if request.client else "unknown"
