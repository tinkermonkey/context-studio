"""
Practical Integration tests for Version Management API endpoints.

Tests the core version management functionality that is currently working,
focusing on direct API operations rather than full automatic integration.
"""

import sys
import os
from uuid import uuid4

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestVersionManagementPracticalAPI:
    """Test practical version management API functionality that's currently working."""

    def test_health_endpoint(self, client):
        """Test the version management health endpoint."""
        response = client.get("/api/versions/health")
        assert response.status_code == 200

        health = response.json()
        # Test all expected fields from VersionManagementHealthOut model
        expected_fields = [
            "status",
            "total_versions",
            "total_working_tree_entries",
            "total_staged_entities",
            "total_modified_entities",
            "issues",
            "database_status",
        ]

        for field in expected_fields:
            assert field in health, f"Missing field: {field}"

        assert health["status"] in ["healthy", "warning", "error"]
        assert isinstance(health["total_versions"], int)
        assert isinstance(health["issues"], list)

    def test_stats_endpoint_implemented(self, client):
        """Test that the stats endpoint is implemented and returns proper structure."""
        response = client.get("/api/versions/stats")
        assert response.status_code == 200  # Endpoint is implemented

        stats = response.json()
        # Test expected fields from VersionManagementStatsOut model
        expected_fields = [
            "versions_by_entity_type",
            "versions_by_state", 
            "working_tree_summary",
            "recent_activity",
            "performance_metrics",
        ]

        for field in expected_fields:
            assert field in stats, f"Missing field: {field}"

        assert isinstance(stats["versions_by_entity_type"], dict)
        assert isinstance(stats["versions_by_state"], dict)
        assert isinstance(stats["recent_activity"], list)
        assert isinstance(stats["performance_metrics"], dict)

    def test_working_tree_status(self, client):
        """Test working tree status endpoint."""
        response = client.get("/api/versions/working-tree/status")
        assert response.status_code == 200

        status = response.json()
        # Test all expected fields from WorkingTreeStatusOut model
        expected_fields = [
            "total_entities",
            "modified_entities",
            "staged_entities",
            "unstaged_entities",
            "entries",
        ]

        for field in expected_fields:
            assert field in status, f"Missing field: {field}"

        assert isinstance(status["total_entities"], int)
        assert isinstance(status["entries"], list)

    def test_working_tree_changes(self, client):
        """Test getting working tree changes."""
        response = client.get("/api/versions/working-tree/changes")
        assert response.status_code == 200

        changes = response.json()
        assert isinstance(changes, list)
        # Changes can be empty initially - that's fine

    def test_working_diffs_endpoint(self, client):
        """Test getting all working diffs."""
        response = client.get("/api/versions/diffs/working")
        assert response.status_code == 200

        diffs = response.json()
        assert isinstance(diffs, list)
        # Diffs can be empty initially - that's fine

    def test_commit_preview(self, client):
        """Test commit preview endpoint - returns list of diffs."""
        response = client.get("/api/versions/working-tree/preview")
        assert response.status_code == 200

        preview = response.json()
        # The endpoint returns List[EntityDiffOut], not a dict with entities/summary
        assert isinstance(preview, list)
        # Preview can be empty list when no staged changes exist

    def test_empty_version_operations(self, client):
        """Test version operations with non-existent entities return empty results."""
        fake_id = str(uuid4())

        # Test getting versions for non-existent entity - returns empty list
        response = client.get(
            f"/api/versions/entities/structure_node/{fake_id}/versions"
        )
        assert response.status_code == 200
        versions = response.json()
        assert isinstance(versions, list)
        assert len(versions) == 0

        # Test getting specific version for non-existent entity
        response = client.get(
            f"/api/versions/entities/structure_node/{fake_id}/versions/1"
        )
        assert response.status_code == 404

        # Test getting diff for non-existent entity
        response = client.get(f"/api/versions/entities/structure_node/{fake_id}/diff")
        assert response.status_code == 404

    def test_invalid_requests(self, client):
        """Test various invalid request formats."""
        # Test invalid entity type
        response = client.get("/api/versions/entities/invalid_type/123/versions")
        assert response.status_code == 422  # Validation error

        # Test invalid UUID format
        response = client.get(
            "/api/versions/entities/structure_node/invalid-uuid/versions"
        )
        assert response.status_code == 422  # Validation error

        # Test invalid version number
        response = client.get(
            f"/api/versions/entities/structure_node/{uuid4()}/versions/-1"
        )
        assert response.status_code in [404, 422]  # Not found or validation error

    def test_stage_operations_invalid_data(self, client):
        """Test staging operations with invalid data."""
        # Test staging with missing required fields
        response = client.post("/api/versions/working-tree/stage", json={})
        assert response.status_code == 422  # Validation error

        # Test staging with invalid entity type
        stage_data = {"entity_type": "invalid_type", "entity_id": str(uuid4())}
        response = client.post("/api/versions/working-tree/stage", json=stage_data)
        assert response.status_code == 422  # Validation error

    def test_commit_operations_invalid_data(self, client):
        """Test commit operations with invalid data."""
        # Test commit with missing required fields
        response = client.post("/api/versions/working-tree/commit", json={})
        assert response.status_code == 422  # Validation error

        # Test commit with empty message - this returns 400 (Bad Request) for no staged changes
        commit_data = {"message": "", "author_id": "test-user"}
        response = client.post("/api/versions/working-tree/commit", json=commit_data)
        # Should return 400 for no staged changes to commit
        assert response.status_code == 400

    def test_rollback_invalid_data(self, client):
        """Test rollback operations with invalid data."""
        fake_id = str(uuid4())

        # Test rollback with missing fields
        response = client.post(
            f"/api/versions/entities/structure_node/{fake_id}/rollback", json={}
        )
        assert response.status_code == 422  # Validation error

        # Test rollback with invalid version number
        rollback_data = {"target_version_number": -1, "author_id": "test-user"}
        response = client.post(
            f"/api/versions/entities/structure_node/{fake_id}/rollback",
            json=rollback_data,
        )
        assert response.status_code in [404, 422]  # Not found or validation error

    def test_diff_comparison_invalid_data(self, client):
        """Test diff comparison with invalid data."""
        # Test comparison with missing fields
        response = client.post("/api/versions/diffs/compare", json={})
        assert response.status_code == 422  # Validation error

        # Test comparison with invalid entity type
        compare_data = {
            "entity_type": "invalid_type",
            "entity_id": str(uuid4()),
            "before_version_number": 1,
            "after_version_number": 2,
        }
        response = client.post("/api/versions/diffs/compare", json=compare_data)
        assert response.status_code == 422  # Validation error

    def test_api_endpoint_existence(self, client):
        """Test that implemented API endpoints exist and return expected status codes."""
        endpoints_to_test = [
            ("/api/versions/health", "GET", 200),
            ("/api/versions/stats", "GET", 200), # Stats endpoint is now implemented
            ("/api/versions/working-tree/status", "GET", 200),
            ("/api/versions/working-tree/changes", "GET", 200),
            ("/api/versions/working-tree/preview", "GET", 200),
            ("/api/versions/diffs/working", "GET", 200),
        ]

        for endpoint, method, expected_status in endpoints_to_test:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            else:
                continue

            # Should not return 404 (endpoint exists)
            assert response.status_code != 404, f"Endpoint {endpoint} not found"

            # For GET endpoints, we expect them to work
            if method == "GET":
                assert (
                    response.status_code == expected_status
                ), f"Endpoint {endpoint} returned {response.status_code}, expected {expected_status}"

    def test_content_type_headers(self, client):
        """Test that API endpoints return correct content-type headers."""
        response = client.get("/api/versions/health")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    def test_cors_headers(self, client):
        """Test CORS headers if applicable."""
        response = client.get("/api/versions/health")
        # CORS headers may or may not be present depending on configuration
        # This is just checking that the request doesn't fail due to CORS issues
        assert response.status_code == 200

    def test_error_response_format(self, client):
        """Test that error responses have consistent format."""
        # Try to get a non-existent version
        fake_id = str(uuid4())
        response = client.get(
            f"/api/versions/entities/structure_node/{fake_id}/versions/1"
        )
        assert response.status_code == 404

        # Check that error response is valid JSON
        error_data = response.json()
        assert isinstance(error_data, dict)
        # FastAPI typically returns {"detail": "error message"} for HTTP exceptions
        assert "detail" in error_data

    def test_pagination_parameters(self, client):
        """Test pagination parameters where applicable."""
        fake_id = str(uuid4())

        # Test limit parameter - returns empty list for non-existent entity
        response = client.get(
            f"/api/versions/entities/structure_node/{fake_id}/versions?limit=10"
        )
        assert response.status_code == 200
        versions = response.json()
        assert isinstance(versions, list)
        assert len(versions) == 0

        # Test offset parameter
        response = client.get(
            f"/api/versions/entities/structure_node/{fake_id}/versions?offset=0"
        )
        assert response.status_code == 200
        versions = response.json()
        assert isinstance(versions, list)
        assert len(versions) == 0

        # Test invalid limit (negative) - should be handled gracefully
        response = client.get(
            f"/api/versions/entities/structure_node/{fake_id}/versions?limit=-1"
        )
        # Should handle invalid parameter gracefully, might return validation error or empty results
        assert response.status_code in [200, 422]
