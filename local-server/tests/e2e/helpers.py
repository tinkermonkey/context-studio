"""
Helper functions for E2E tests.

This module provides utility functions for common E2E test patterns,
including polling for asynchronous operations, event processing, and
test data setup helpers.
"""

import functools
import time
from typing import Callable, TypeVar, Optional, Any, Dict, List

import pytest

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


def retry_on_external_failure(max_retries: int = 2, delay: float = 5):
    """
    Retry decorator for tests that depend on external APIs.

    Automatically retries a test function if it fails due to external API
    unavailability (ConnectionError, TimeoutError). Logs retry attempts
    and skips the test if all retries are exhausted.

    Args:
        max_retries: Maximum number of retry attempts (default: 2)
        delay: Seconds to wait between retry attempts (default: 5)

    Usage:
        @pytest.mark.llm
        @retry_on_external_failure(max_retries=3, delay=10)
        def test_with_llm_api(e2e_client):
            ...
    """
    def decorator(test_func):
        @functools.wraps(test_func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return test_func(*args, **kwargs)
                except (ConnectionError, TimeoutError) as e:
                    last_error = e
                    if attempt < max_retries:
                        time.sleep(delay)
            pytest.skip(
                f"External service unavailable after {max_retries} retries: {last_error}"
            )
        return wrapper
    return decorator


def create_test_hierarchy(
    client,
    layer_title: str,
    layer_definition: str,
    scheme_title: str,
    scheme_definition: str,
    classes: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Create a test hierarchy (layer → domain → terms) via POST requests.

    This helper eliminates boilerplate across all E2E tests by handling the
    sequential creation of a layer (taxonomy), domain (concept scheme), and
    terms (classes), returning a structured dict of IDs for further use.

    The helper validates all responses and raises AssertionError on failure,
    making it suitable for use within test functions.

    Args:
        client: FastAPI TestClient instance
        layer_title: Title for the layer (e.g., "Computer Science")
        layer_definition: Definition for the layer
        scheme_title: Title for the domain/scheme (e.g., "Data Management")
        scheme_definition: Definition for the domain/scheme
        classes: List of dicts with 'title' and 'definition' keys for terms

    Returns:
        Dict with structure:
        {
            "layer_id": str,
            "domain_id": str,
            "term_ids": {title: id, ...}
        }

    Raises:
        AssertionError: If any POST request returns a non-201 status code

    Example:
        hierarchy = create_test_hierarchy(
            client,
            "Computer Science",
            "The study of computation and information",
            "Data Management",
            "Technologies and methods for storing and retrieving data",
            [
                {"title": "Database", "definition": "An organized collection..."},
                {"title": "SQL", "definition": "Structured Query Language..."},
            ]
        )
        assert "Database" in hierarchy["term_ids"]
    """
    # Step 1: Create layer
    layer_response = client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "layer",
            "title": layer_title,
            "definition": layer_definition,
        },
    )
    assert layer_response.status_code == 201, f"Failed to create layer: {layer_response.text}"
    layer_id = layer_response.json()["id"]

    # Step 2: Create domain under layer
    domain_response = client.post(
        "/api/structure_nodes/",
        json={
            "node_type": "domain",
            "parent_node_id": layer_id,
            "title": scheme_title,
            "definition": scheme_definition,
        },
    )
    assert domain_response.status_code == 201, f"Failed to create domain: {domain_response.text}"
    domain_id = domain_response.json()["id"]

    # Step 3: Create all terms under domain
    term_ids = {}
    for cls in classes:
        term_response = client.post(
            "/api/structure_nodes/",
            json={
                "node_type": "term",
                "parent_node_id": domain_id,
                "title": cls["title"],
                "definition": cls["definition"],
            },
        )
        assert term_response.status_code == 201, (
            f"Failed to create term '{cls['title']}': {term_response.text}"
        )
        term_ids[cls["title"]] = term_response.json()["id"]

    return {
        "layer_id": layer_id,
        "domain_id": domain_id,
        "term_ids": term_ids,
    }
