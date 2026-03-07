"""
Helper functions for E2E tests.

This module provides utility functions for common E2E test patterns,
including polling for asynchronous operations, event processing, and
test data setup helpers.
"""

import time
from typing import Callable, Any, Dict, List


def poll_until(
    predicate: Callable[[], tuple[bool, Any]],
    timeout_seconds: float = 30,
    interval: float = 0.5,
    description: str = "condition",
) -> Any:
    """
    Poll a predicate function until it returns True or timeout.

    External services introduce latency. This helper replaces time.sleep with a polling
    pattern that repeatedly calls a predicate function until it returns (True, result)
    or the timeout is exceeded.

    Args:
        predicate: Callable that returns (success: bool, result: Any) tuple. Returns
                   (True, result_value) when the condition is met, (False, result)
                   otherwise.
        timeout_seconds: Maximum wait time in seconds (default: 30)
        interval: Seconds between polls (default: 0.5)
        description: What we're waiting for (used in error messages)

    Returns:
        The result from the predicate call when success is True

    Raises:
        TimeoutError: If predicate never returns True within timeout_seconds
    """
    deadline = time.time() + timeout_seconds
    last_result = None
    while time.time() < deadline:
        success, last_result = predicate()
        if success:
            return last_result
        time.sleep(interval)
    raise TimeoutError(
        f"Timed out after {timeout_seconds}s waiting for {description}. "
        f"Last result: {last_result}"
    )


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
