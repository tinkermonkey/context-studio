"""
Helper functions for E2E tests.

This module provides utility functions for common E2E test patterns,
including polling for asynchronous operations, event processing, and
test data setup helpers.
"""

import functools
import time
from collections.abc import Callable
from typing import Any

import pytest

# Transient exceptions that warrant retry: network failures, temporary service unavailability
TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Covers network-related OSErrors
)


def retry_on_external_failure(max_retries: int = 2, delay: float = 5):
    """
    Decorator for retrying tests marked with @pytest.mark.reference on external failures.

    Tests that depend on external reference data sources may fail transiently due to
    network issues, temporary service unavailability, or rate limiting. This decorator
    automatically retries the test if it fails with a transient exception, allowing transient
    failures to be distinguished from real test failures. Genuine test failures (AssertionError)
    and programming bugs are never retried.

    Args:
        max_retries: Maximum number of retries after initial failure (default: 2).
                     Total attempts = 1 + max_retries.
        delay: Seconds to wait between retries (default: 5). Allows external services
               to recover before retrying.

    Example:
        @pytest.mark.reference
        @retry_on_external_failure(max_retries=2, delay=5)
        def test_reference_data_lookup():
            # Test code that may fail transiently due to external service issues
            pass

    Raises:
        pytest.skip: If all retries are exhausted, the test is skipped to distinguish
                     unavailable services from real test failures.
        AssertionError: Genuine test failures are re-raised immediately without retry.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1 + max_retries):
                try:
                    return func(*args, **kwargs)
                except AssertionError:
                    # Genuine test failures: re-raise immediately without retry
                    raise
                except TRANSIENT_EXCEPTIONS as e:
                    # Transient external failure: may retry
                    if attempt < max_retries:
                        time.sleep(delay)
                        continue
                    # All retries exhausted: skip test to distinguish from real failure
                    pytest.skip(
                        f"Skipped after {1 + max_retries} attempts due to "
                        f"unavailable external service: {type(e).__name__}: {e}"
                    )
            # Should not reach here, but fail safely if no exception was raised
            assert False, "Unexpected state in retry_on_external_failure"

        return wrapper

    return decorator


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
    or the timeout is exceeded. Only transient exceptions (connection, timeouts) are
    caught and retried; programming errors (TypeError, KeyError, AttributeError) are
    raised immediately to surface bugs quickly rather than hanging until timeout.

    Args:
        predicate: Callable that returns (success: bool, result: Any) tuple. Returns
                   (True, result_value) when the condition is met, (False, result)
                   otherwise. May raise transient exceptions but should not raise
                   programming errors (these indicate test bugs).
        timeout_seconds: Maximum wait time in seconds (default: 30)
        interval: Seconds between polls (default: 0.5)
        description: What we're waiting for (used in error messages)

    Returns:
        The result from the predicate call when success is True

    Raises:
        TimeoutError: If predicate never returns True within timeout_seconds and
                      no programming errors occurred.
        TypeError, KeyError, AttributeError: Programming errors in the predicate
                      are raised immediately without retry.
        ConnectionError, TimeoutError (from predicate): Transient external failures
                      are retried until timeout.
    """
    deadline = time.time() + timeout_seconds
    last_result = None
    last_exception = None
    while time.time() < deadline:
        try:
            success, last_result = predicate()
            if success:
                return last_result
        except TRANSIENT_EXCEPTIONS as e:
            # Transient external failure: capture but continue polling
            last_exception = e
        except (TypeError, KeyError, AttributeError, ValueError, IndexError):
            # Programming error: re-raise immediately to surface the bug quickly
            # rather than hanging until timeout
            raise
        time.sleep(interval)

    # Timeout reached: include exception info if we have it
    error_msg = f"Timed out after {timeout_seconds}s waiting for {description}. Last result: {last_result}"
    if last_exception:
        error_msg += (
            f". Last exception: {type(last_exception).__name__}: {last_exception}"
        )
    raise TimeoutError(error_msg)


def create_test_hierarchy(
    client,
    layer_title: str,
    layer_definition: str,
    scheme_title: str,
    scheme_definition: str,
    classes: list[dict[str, str]],
) -> dict[str, Any]:
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
    assert (
        layer_response.status_code == 201
    ), f"Failed to create layer: {layer_response.text}"
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
    assert (
        domain_response.status_code == 201
    ), f"Failed to create domain: {domain_response.text}"
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
        assert (
            term_response.status_code == 201
        ), f"Failed to create term '{cls['title']}': {term_response.text}"
        term_ids[cls["title"]] = term_response.json()["id"]

    return {
        "layer_id": layer_id,
        "domain_id": domain_id,
        "term_ids": term_ids,
    }


def create_test_hierarchy_new_api(
    client,
    taxonomy_data: dict[str, str] | None = None,
    scheme_data: dict[str, str] | None = None,
    class_data_list: list[dict[str, str]] | None = None,
) -> tuple:
    """
    Create a taxonomy → concept scheme → classes hierarchy using the new /api/ontology_entities/ routes.

    This helper creates entities using the new API terminology and field names, including
    parent_entity_id instead of parent_node_id and node_type values of taxonomy, concept_scheme,
    and class instead of layer, domain, and term.

    Args:
        client: FastAPI TestClient instance
        taxonomy_data: Dict with keys: node_type='taxonomy', title, definition
                      Defaults to a test taxonomy if not provided
        scheme_data: Dict with keys: node_type='concept_scheme', title, definition
                    Defaults to a test scheme if not provided
        class_data_list: List of dicts with keys: node_type='class', title, definition
                        Defaults to two test classes if not provided

    Returns:
        Tuple of (taxonomy_id, scheme_id, class_ids) where class_ids is a list of class IDs

    Raises:
        AssertionError: If any POST request returns a non-201 status code

    Example:
        taxonomy_id, scheme_id, class_ids = create_test_hierarchy_new_api(client)
        assert isinstance(class_ids, list)
        assert len(class_ids) == 2
    """
    if taxonomy_data is None:
        taxonomy_data = {
            "node_type": "taxonomy",
            "title": "Test Taxonomy",
            "definition": "A test taxonomy",
        }
    if scheme_data is None:
        scheme_data = {
            "node_type": "concept_scheme",
            "title": "Test Scheme",
            "definition": "A test scheme",
        }
    if class_data_list is None:
        class_data_list = [
            {"node_type": "class", "title": "Test Class 0", "definition": "Class 0"},
            {"node_type": "class", "title": "Test Class 1", "definition": "Class 1"},
        ]

    # Create taxonomy
    taxonomy_resp = client.post("/api/ontology_entities/", json=taxonomy_data)
    assert (
        taxonomy_resp.status_code == 201
    ), f"Failed to create taxonomy: {taxonomy_resp.status_code} {taxonomy_resp.text}"
    taxonomy_id = taxonomy_resp.json()["id"]

    # Create concept scheme under taxonomy (merge parent_entity_id without mutating caller's dict)
    scheme_payload = {**scheme_data, "parent_entity_id": taxonomy_id}
    scheme_resp = client.post("/api/ontology_entities/", json=scheme_payload)
    assert (
        scheme_resp.status_code == 201
    ), f"Failed to create concept scheme: {scheme_resp.status_code} {scheme_resp.text}"
    scheme_id = scheme_resp.json()["id"]

    # Create classes under concept scheme (merge parent_entity_id without mutating caller's dicts)
    class_ids = []
    for cls in class_data_list:
        cls_payload = {**cls, "parent_entity_id": scheme_id}
        cls_resp = client.post("/api/ontology_entities/", json=cls_payload)
        assert cls_resp.status_code == 201, (
            f"Failed to create class '{cls.get('title', 'Unknown')}': "
            f"{cls_resp.status_code} {cls_resp.text}"
        )
        class_ids.append(cls_resp.json()["id"])

    return taxonomy_id, scheme_id, class_ids
