"""
Regression tests for Phase 4: Backward Compatibility

Tests that existing API endpoints remain functional and backward-compatible
after Phase 4 changes.

Test Cases:
- TC-R001: Existing entity lookup endpoint returns expected structure
- TC-R002: Existing property lookup endpoint returns expected structure
- TC-R003: Search endpoint backward compatibility (with/without similarity scores)
- TC-R004: Existing error handling remains consistent
- TC-R005: Performance regressions not introduced
"""

import pytest
import time
from typing import Dict, Any


class TestBackwardCompatibility:
    """Test suite for backward compatibility of existing endpoints."""

    def test_entity_lookup_structure(self, client, test_db_with_data):
        """
        TC-R001: Verify entity lookup endpoint maintains expected response structure.

        Validates that existing consumers of the entity lookup API will not break.
        """
        # Look up a known entity (Person from schema.org)
        response = client.get("/api/reference/ref-db/entity/schema.org/Person")

        assert response.status_code == 200, "Entity lookup should succeed"

        data = response.json()

        # Verify expected fields exist
        assert "id" in data, "Response must include 'id' field"
        assert "title" in data, "Response must include 'title' field"
        assert "definition" in data, "Response must include 'definition' field"
        assert "source" in data, "Response must include 'source' field"
        assert "external_id" in data, "Response must include 'external_id' field"

        # Verify field types
        assert isinstance(data["id"], str), "'id' must be string"
        assert isinstance(data["title"], str), "'title' must be string"
        assert isinstance(data["source"], str), "'source' must be string"
        assert isinstance(data["external_id"], str), "'external_id' must be string"

        # Verify specific values
        assert data["source"] == "schema.org"
        assert data["external_id"] == "Person"

    def test_property_lookup_structure(self, client, test_db_with_data):
        """
        TC-R002: Verify property lookup endpoint maintains expected response structure.

        Validates that existing consumers of the property lookup API will not break.
        """
        # Look up a known property (name from schema.org)
        response = client.get("/api/reference/ref-db/property/schema.org/name")

        assert response.status_code == 200, "Property lookup should succeed"

        data = response.json()

        # Verify expected fields exist
        assert "id" in data, "Response must include 'id' field"
        assert "title" in data, "Response must include 'title' field"
        assert "definition" in data, "Response must include 'definition' field"
        assert "source" in data, "Response must include 'source' field"
        assert "external_id" in data, "Response must include 'external_id' field"

        # Verify field types
        assert isinstance(data["id"], str), "'id' must be string"
        assert isinstance(data["title"], str), "'title' must be string"
        assert isinstance(data["source"], str), "'source' must be string"
        assert isinstance(data["external_id"], str), "'external_id' must be string"

    def test_search_backward_compatibility(self, client, test_db_with_data):
        """
        TC-R003: Verify search endpoint maintains backward compatibility.

        Validates that search results include similarity_score field (new in Phase 4)
        while maintaining all existing fields.
        """
        # Perform a search
        response = client.post(
            "/api/reference/ref-db/search",
            json={
                "query": "person",
                "limit": 5
            }
        )

        assert response.status_code == 200, "Search should succeed"

        data = response.json()
        assert "results" in data, "Response must include 'results' array"
        assert len(data["results"]) > 0, "Should return at least one result"

        # Check first result has all expected fields
        result = data["results"][0]

        # Existing fields (backward compatibility)
        assert "id" in result, "Result must include 'id' field"
        assert "title" in result, "Result must include 'title' field"
        assert "definition" in result, "Result must include 'definition' field"
        assert "source" in result, "Result must include 'source' field"
        assert "external_id" in result, "Result must include 'external_id' field"

        # New field (Phase 4 enhancement)
        assert "similarity_score" in result, "Result must include 'similarity_score' field (Phase 4)"
        assert isinstance(result["similarity_score"], (int, float)), "Similarity score must be numeric"
        assert 0.0 <= result["similarity_score"] <= 1.0, "Similarity score must be between 0 and 1"

    def test_error_handling_consistency(self, client, test_db_with_data):
        """
        TC-R004: Verify error handling remains consistent.

        Validates that error responses maintain the same structure and don't expose
        sensitive information.
        """
        # Test 404 for non-existent entity
        response = client.get("/api/reference/ref-db/entity/invalid-source/invalid-id")
        assert response.status_code == 404, "Should return 404 for non-existent entity"

        # Verify error response structure (should be consistent)
        error_data = response.json()
        assert "detail" in error_data or "message" in error_data, "Error should have detail/message"

        # Verify no stack traces or internal paths exposed
        error_str = str(error_data).lower()
        assert "/workspace" not in error_str, "Should not expose internal paths"
        assert "traceback" not in error_str, "Should not expose stack traces"

    def test_performance_no_regression(self, client, test_db_with_data):
        """
        TC-R005: Verify no performance regressions in existing endpoints.

        Validates that existing endpoints maintain their performance characteristics
        after Phase 4 changes.
        """
        # Test entity lookup performance
        start = time.time()
        response = client.get("/api/reference/ref-db/entity/schema.org/Person")
        entity_lookup_time = (time.time() - start) * 1000  # Convert to ms

        assert response.status_code == 200, "Entity lookup should succeed"
        assert entity_lookup_time < 100, f"Entity lookup should complete in <100ms (actual: {entity_lookup_time:.2f}ms)"

        # Test search performance
        start = time.time()
        response = client.post(
            "/api/reference/ref-db/search",
            json={"query": "person", "limit": 10}
        )
        search_time = (time.time() - start) * 1000  # Convert to ms

        assert response.status_code == 200, "Search should succeed"
        assert search_time < 200, f"Search should complete in <200ms (actual: {search_time:.2f}ms)"


@pytest.fixture(scope="class")
def test_db_with_data(tmp_path_factory):
    """
    Create a test database with sample data for regression testing.

    This fixture ensures we have known data to test backward compatibility.
    Uses class scope to share the database across all tests in the class.
    """
    # Import here to avoid circular dependencies
    from reference_db.manager import ReferenceManager
    from reference_db.config import ReferenceConfig
    import json
    import os

    # Create temporary database using tmp_path_factory for class-scoped fixtures
    tmpdir = tmp_path_factory.mktemp("regression_tests")
    db_path = str(tmpdir / "test_regression.db")

    # Create a minimal config for testing
    config = ReferenceConfig(enable_embeddings=True)
    manager = ReferenceManager(config=config, db_path=db_path)

    # Load schema.org sample data
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "fixtures",
        "schema_org_sample.jsonld"
    )

    if os.path.exists(fixture_path):
        with open(fixture_path, "r") as f:
            data = json.load(f)
            # Import the data (would use actual import logic here)
            # For now, create some basic test data

    # Check if nodes already exist before adding them
    person_node = manager.get_reference_node_by_source("schema.org", "Person")
    if not person_node:
        manager.add_reference_node(
            title="Person",
            definition="A person (alive, dead, undead, or fictional).",
            source="schema.org",
            external_id="Person",
            attributes={"@type": "Class"}
        )

    name_node = manager.get_reference_node_by_source("schema.org", "name")
    if not name_node:
        manager.add_reference_node(
            title="name",
            definition="The name of the item.",
            source="schema.org",
            external_id="name",
            attributes={"@type": "Property"}
        )

    # Close the manager to release the session
    manager.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="class")
def client(test_db_with_data):
    """
    Create test client with test database.
    Uses class scope to share the client across all tests in the class.
    """
    from fastapi.testclient import TestClient
    from api.reference import router
    from unittest.mock import patch
    import os

    # Patch the ReferenceManager's _get_default_db_path method to return test db path
    # This ensures all ReferenceManager instances in the API use the test database
    from reference_db.manager import ReferenceManager

    original_method = ReferenceManager._get_default_db_path

    def mock_get_default_db_path(self):
        return test_db_with_data

    # Apply the patch
    ReferenceManager._get_default_db_path = mock_get_default_db_path

    try:
        # Create app with the patched reference manager
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)

        yield TestClient(app)
    finally:
        # Restore original method
        ReferenceManager._get_default_db_path = original_method
