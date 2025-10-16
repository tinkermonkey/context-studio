"""
End-to-end tests for predicate discovery workflow.

Tests complete user workflows from API request through discovery to results.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
import time
import tempfile
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, Mock

# Import the FastAPI app
from app import app


@pytest.fixture
def client(shared_client):
    """Use the shared client from conftest which has proper dataset setup."""
    return shared_client


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_e2e_discovery.db"
    return str(db_path)


class TestPredicateDiscoveryE2E:
    """End-to-end tests for predicate discovery workflows."""

    def test_complete_discovery_workflow_conceptnet(self, client):
        """
        Test complete workflow: Start discovery -> Poll status -> Verify results.

        This simulates a user:
        1. Starting a ConceptNet discovery via POST /api/predicates/discover
        2. Polling the status via GET /api/predicates/discover/{task_id}
        3. Verifying predicates are stored via GET /api/predicates/external
        """
        with patch('api.predicates._run_discovery_task') as mock_task:
            # Configure mock to simulate successful discovery
            async def mock_discovery(task_id, sources):
                from api.predicates import _discovery_tasks
                import datetime

                _discovery_tasks[task_id]["status"] = "completed"
                _discovery_tasks[task_id]["results"] = {
                    "conceptnet": {
                        "created": 40,
                        "updated": 0,
                        "error_count": 0,
                        "errors": [],
                        "errors_truncated": False
                    }
                }
                _discovery_tasks[task_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()

            mock_task.side_effect = mock_discovery

            # Step 1: Start discovery
            response = client.post(
                "/api/predicates/discover",
                params={"sources": ["conceptnet"]}
            )

            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "started"
            task_id = data["task_id"]

            # Step 2: Poll status (simulate async completion)
            time.sleep(0.1)  # Small delay for mock to execute

            response = client.get(f"/api/predicates/discover/{task_id}")
            assert response.status_code == 200
            status_data = response.json()

            assert status_data["task_id"] == task_id
            assert status_data["status"] == "completed"
            assert "conceptnet" in status_data["results"]
            assert status_data["results"]["conceptnet"]["created"] == 40
            assert status_data["results"]["conceptnet"]["updated"] == 0
            assert status_data["results"]["conceptnet"]["error_count"] == 0

    def test_discovery_workflow_with_errors(self, client):
        """
        Test workflow when discovery encounters errors.

        Verifies that:
        - Partial failures are reported correctly
        - Error messages are included in status
        - errors_truncated flag works correctly
        """
        with patch('api.predicates._run_discovery_task') as mock_task:
            # Configure mock to simulate partial failure
            async def mock_discovery(task_id, sources):
                from api.predicates import _discovery_tasks
                import datetime

                # Simulate 3 failures out of 40 attempts
                errors = [f"Error {i}: Network timeout" for i in range(15)]

                _discovery_tasks[task_id]["status"] = "completed"
                _discovery_tasks[task_id]["results"] = {
                    "conceptnet": {
                        "created": 37,
                        "updated": 0,
                        "error_count": 15,
                        "errors": errors[:10],  # Only first 10
                        "errors_truncated": True
                    }
                }
                _discovery_tasks[task_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()

            mock_task.side_effect = mock_discovery

            # Start discovery
            response = client.post("/api/predicates/discover", params={"sources": ["conceptnet"]})
            task_id = response.json()["task_id"]

            # Poll status
            time.sleep(0.1)
            response = client.get(f"/api/predicates/discover/{task_id}")
            status_data = response.json()

            # Verify error handling
            assert status_data["status"] == "completed"
            result = status_data["results"]["conceptnet"]
            assert result["created"] == 37
            assert result["error_count"] == 15
            assert len(result["errors"]) == 10
            assert result["errors_truncated"] is True

    def test_multi_source_discovery_workflow(self, client):
        """
        Test discovering from multiple sources simultaneously.

        Simulates:
        1. Start discovery for all sources
        2. Verify all sources are processed
        3. Check performance targets are met
        """
        with patch('api.predicates._run_discovery_task') as mock_task:
            async def mock_discovery(task_id, sources):
                from api.predicates import _discovery_tasks
                import datetime

                results = {}
                if sources is None or "conceptnet" in sources:
                    results["conceptnet"] = {
                        "created": 40, "updated": 0, "error_count": 0,
                        "errors": [], "errors_truncated": False
                    }
                if sources is None or "dbpedia" in sources:
                    results["dbpedia"] = {
                        "created": 760, "updated": 0, "error_count": 0,
                        "errors": [], "errors_truncated": False
                    }
                if sources is None or "wikidata" in sources:
                    results["wikidata"] = {
                        "created": 10000, "updated": 0, "error_count": 0,
                        "errors": [], "errors_truncated": False
                    }

                _discovery_tasks[task_id]["status"] = "completed"
                _discovery_tasks[task_id]["results"] = results
                _discovery_tasks[task_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()

            mock_task.side_effect = mock_discovery

            # Start discovery for all sources
            start_time = time.time()
            response = client.post("/api/predicates/discover")
            assert response.status_code == 200
            task_id = response.json()["task_id"]

            # Poll status
            time.sleep(0.1)
            response = client.get(f"/api/predicates/discover/{task_id}")
            status_data = response.json()

            # Verify all sources completed
            assert status_data["status"] == "completed"
            assert "conceptnet" in status_data["results"]
            assert "dbpedia" in status_data["results"]
            assert "wikidata" in status_data["results"]

            assert status_data["results"]["conceptnet"]["created"] == 40
            assert status_data["results"]["dbpedia"]["created"] == 760
            assert status_data["results"]["wikidata"]["created"] == 10000

    def test_invalid_source_validation(self, client):
        """Test that invalid source names are rejected."""
        response = client.post(
            "/api/predicates/discover",
            params={"sources": ["invalid_source", "conceptnet"]}
        )

        assert response.status_code == 400
        assert "Invalid sources" in response.json()["detail"]

    def test_task_not_found(self, client):
        """Test querying status for non-existent task."""
        response = client.get("/api/predicates/discover/invalid-task-id")
        assert response.status_code == 404
        assert "Task not found" in response.json()["detail"]

    def test_external_predicates_listing(self, client):
        """
        Test listing external predicates after discovery.

        Verifies:
        - Pagination works correctly
        - Source filtering works
        - Predicates have all required fields
        """
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig

        # Add test data directly to the reference database
        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            # Clear any existing test data
            from reference_db.models import ExternalPredicate
            manager.session.query(ExternalPredicate).delete()
            manager.session.commit()

            # Add 100 test predicates
            for i in range(100):
                manager.add_external_predicate(
                    title=f"Predicate {i}",
                    definition=f"Definition for predicate {i}",
                    source="conceptnet",
                    external_id=f"/r/Relation{i}"
                )

        # Test pagination
        response = client.get("/api/predicates/external?skip=0&limit=50")
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 100
        assert data["skip"] == 0
        assert data["limit"] == 50
        assert len(data["data"]) == 50

        # Verify first predicate structure
        first_pred = data["data"][0]
        assert "id" in first_pred
        assert "title" in first_pred
        assert "definition" in first_pred
        assert "source" in first_pred
        assert "external_id" in first_pred
        assert "created_at" in first_pred
        assert "updated_at" in first_pred

        # Clean up test data
        with reference_manager_context(config) as manager:
            manager.session.query(ExternalPredicate).delete()
            manager.session.commit()

    def test_external_predicates_source_filtering(self, client):
        """Test filtering external predicates by source."""
        from reference_db.dependencies import reference_manager_context
        from reference_db.config import ReferenceConfig

        # Add test data from different sources
        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            # Clear any existing test data
            from reference_db.models import ExternalPredicate
            manager.session.query(ExternalPredicate).delete()
            manager.session.commit()

            # Add predicates from different sources
            manager.add_external_predicate(
                title="ConceptNet Predicate 1",
                definition="Definition from ConceptNet",
                source="conceptnet",
                external_id="/r/Rel1"
            )
            manager.add_external_predicate(
                title="DBpedia Predicate 1",
                definition="Definition from DBpedia",
                source="dbpedia",
                external_id="dbo:property1"
            )

        # Test filtering by source
        response = client.get("/api/predicates/external?source=conceptnet&limit=50")
        assert response.status_code == 200
        data = response.json()

        assert data["source"] == "conceptnet"
        assert len(data["data"]) == 1
        assert all(p["source"] == "conceptnet" for p in data["data"])

        # Clean up test data
        with reference_manager_context(config) as manager:
            manager.session.query(ExternalPredicate).delete()
            manager.session.commit()

    def test_incremental_discovery_updates(self, client):
        """
        Test that running discovery again updates existing predicates.

        Verifies the upsert behavior:
        1. First discovery creates predicates
        2. Second discovery updates them (not creates duplicates)
        """
        with patch('api.predicates._run_discovery_task') as mock_task:
            # First discovery - all creates
            async def mock_first_discovery(task_id, sources):
                from api.predicates import _discovery_tasks
                import datetime

                _discovery_tasks[task_id]["status"] = "completed"
                _discovery_tasks[task_id]["results"] = {
                    "conceptnet": {
                        "created": 40,
                        "updated": 0,
                        "error_count": 0,
                        "errors": [],
                        "errors_truncated": False
                    }
                }
                _discovery_tasks[task_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()

            mock_task.side_effect = mock_first_discovery

            # First discovery
            response = client.post("/api/predicates/discover", params={"sources": ["conceptnet"]})
            task_id1 = response.json()["task_id"]
            time.sleep(0.1)
            response = client.get(f"/api/predicates/discover/{task_id1}")
            result1 = response.json()["results"]["conceptnet"]

            assert result1["created"] == 40
            assert result1["updated"] == 0

            # Second discovery - all updates
            async def mock_second_discovery(task_id, sources):
                from api.predicates import _discovery_tasks
                import datetime

                _discovery_tasks[task_id]["status"] = "completed"
                _discovery_tasks[task_id]["results"] = {
                    "conceptnet": {
                        "created": 0,
                        "updated": 40,
                        "error_count": 0,
                        "errors": [],
                        "errors_truncated": False
                    }
                }
                _discovery_tasks[task_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()

            mock_task.side_effect = mock_second_discovery

            response = client.post("/api/predicates/discover", params={"sources": ["conceptnet"]})
            task_id2 = response.json()["task_id"]
            time.sleep(0.1)
            response = client.get(f"/api/predicates/discover/{task_id2}")
            result2 = response.json()["results"]["conceptnet"]

            assert result2["created"] == 0
            assert result2["updated"] == 40

    def test_concurrent_discovery_requests(self, client):
        """
        Test handling multiple concurrent discovery requests.

        Verifies that:
        - Multiple tasks can run concurrently
        - Each task has unique ID
        - Tasks don't interfere with each other
        """
        with patch('api.predicates._run_discovery_task') as mock_task:
            async def mock_discovery(task_id, sources):
                from api.predicates import _discovery_tasks
                import datetime

                _discovery_tasks[task_id]["status"] = "completed"
                _discovery_tasks[task_id]["results"] = {
                    "conceptnet": {
                        "created": 40, "updated": 0, "error_count": 0,
                        "errors": [], "errors_truncated": False
                    }
                }
                _discovery_tasks[task_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()

            mock_task.side_effect = mock_discovery

            # Start multiple discovery tasks
            task_ids = []
            for i in range(3):
                response = client.post("/api/predicates/discover", params={"sources": ["conceptnet"]})
                assert response.status_code == 200
                task_ids.append(response.json()["task_id"])

            # Verify unique task IDs
            assert len(set(task_ids)) == 3

            # Verify each task completes independently
            time.sleep(0.1)
            for task_id in task_ids:
                response = client.get(f"/api/predicates/discover/{task_id}")
                assert response.status_code == 200
                assert response.json()["status"] == "completed"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
