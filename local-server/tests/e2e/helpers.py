"""
Helper functions for E2E tests.

This module provides utility functions for common E2E test patterns,
including polling for asynchronous operations, event processing, and
test data setup helpers.
"""

import time
from typing import Callable, TypeVar, Optional, Any, Dict, List

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
