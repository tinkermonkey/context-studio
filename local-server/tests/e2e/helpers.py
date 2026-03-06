"""
Helper functions for E2E tests.

This module provides utility functions for common E2E test patterns,
including polling for asynchronous operations and event processing.
"""

import time
from typing import Callable, TypeVar, Optional, Any

T = TypeVar("T")


def poll_until(
    condition: Callable[[], T],
    timeout: float = 5.0,
    timeout_seconds: Optional[float] = None,
    interval: float = 0.1,
    description: str = "condition",
    error_message: Optional[str] = None,
) -> T:
    """
    Poll until a condition is met, with a timeout.

    This helper function repeatedly calls a condition function until it returns
    a truthy value or the timeout is exceeded. Useful for waiting for asynchronous  # noqa: E501
    operations or event processing to complete in E2E tests.

    Args:
        condition: A callable that returns a truthy value when the condition is met  # noqa: E501
        timeout: Maximum time to wait in seconds (default: 5.0)
        timeout_seconds: Alias for timeout (for backward compatibility)
        interval: Time to wait between poll attempts in seconds (default: 0.1)
        description: Human-readable description for error messages
        error_message: Custom error message (overrides default)

    Returns:
        The truthy value returned by the condition function

    Raises:
        TimeoutError: If the condition is not met within the timeout period
    """
    # Handle both timeout and timeout_seconds parameters
    effective_timeout = timeout_seconds if timeout_seconds is not None else timeout  # noqa: E501

    start_time = time.time()
    last_result: Any = None

    while True:
        try:
            result = condition()
            if result:
                return result
            last_result = result
        except Exception as e:
            # Log the exception but continue polling
            last_result = e

        # Check if timeout exceeded
        elapsed = time.time() - start_time
        if elapsed >= effective_timeout:
            if error_message:
                raise TimeoutError(error_message)
            raise TimeoutError(
                f"Timeout waiting for {description} after {effective_timeout:.1f}s. "  # noqa: E501
                f"Last result: {last_result}"
            )

        # Wait before next attempt
        time.sleep(interval)


def poll_until_no_exception(
    func: Callable[[], T],
    timeout: float = 5.0,
    interval: float = 0.1,
    description: str = "operation",
) -> T:
    """
    Poll until a function succeeds without raising an exception.

    This helper function repeatedly calls a function until it succeeds or
    the timeout is exceeded. Useful for waiting for operations that may
    temporarily fail due to asynchronous processing.

    Args:
        func: A callable to execute
        timeout: Maximum time to wait in seconds (default: 5.0)
        interval: Time to wait between poll attempts in seconds (default: 0.1)
        description: Human-readable description for error messages

    Returns:
        The return value of the function

    Raises:
        TimeoutError: If the function continues to raise exceptions after timeout  # noqa: E501
    """
    start_time = time.time()
    last_exception = None

    while True:
        try:
            return func()
        except Exception as e:
            last_exception = e

        # Check if timeout exceeded
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            raise TimeoutError(
                f"Timeout waiting for {description} after {timeout:.1f}s. "
                f"Last exception: {type(last_exception).__name__}: {last_exception}"  # noqa: E501
            ) from last_exception

        # Wait before next attempt
        time.sleep(interval)


def wait_for_async_processing(
    client,
    delay: float = 0.5,
) -> None:
    """
    Wait for asynchronous processing to complete.

    This is a simple delay function useful for tests that need to wait
    for background event processing or other async operations.

    Args:
        client: The TestClient instance (not used, for API consistency)
        delay: Time to wait in seconds (default: 0.5)
    """
    time.sleep(delay)
