"""Circuit breaker implementation for fault tolerance"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Awaitable
import logging

logger = logging.getLogger(__name__)

class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """Circuit breaker for external service calls"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 3
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            expected_exception: Exception type that counts as failure
            success_threshold: Successes needed in half-open to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open"""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open"""
        return self.state == CircuitState.HALF_OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed"""
        return self.state == CircuitState.CLOSED

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset from open to half-open"""
        return (
            self.state == CircuitState.OPEN and
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )

    def _record_success(self):
        """Record a successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._close_circuit()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Go back to open on any failure in half-open
            self._open_circuit()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._open_circuit()

    def _open_circuit(self):
        """Open the circuit"""
        logger.warning(f"Circuit breaker opening after {self.failure_count} failures")
        self.state = CircuitState.OPEN
        self.success_count = 0

    def _close_circuit(self):
        """Close the circuit"""
        logger.info("Circuit breaker closing after successful recovery")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0

    def _half_open_circuit(self):
        """Set circuit to half-open"""
        logger.info("Circuit breaker entering half-open state")
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0

    async def call(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from function
        """
        # Check if we should attempt reset
        if self._should_attempt_reset():
            self._half_open_circuit()

        # Reject calls if circuit is open
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit breaker is open. Last failure: {self.last_failure_time}"
            )

        try:
            # Execute the function
            result = await func(*args, **kwargs)
            self._record_success()
            return result

        except self.expected_exception as e:
            self._record_failure()
            raise e

    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "success_threshold": self.success_threshold
        }

    def reset(self):
        """Manually reset circuit breaker to closed state"""
        logger.info("Circuit breaker manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None