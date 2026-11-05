"""
E2E tests for the Version Control & Collaboration bounded context.

This module tests the Versioning bounded context through the HTTP API
with a fully initialized application using real databases and real adapters.

Tests verify:
- Change history retrieval after ontology mutations
- Sync status
"""

import pytest
from fastapi import status


def create_taxonomy_with_changes(e2e_client):
    """
    Helper to create a taxonomy and return its ID.
    Used to reduce boilerplate in versioning tests.
    """
    import uuid

    unique_id = str(uuid.uuid4())[:8]
    response = e2e_client.post("/api/taxonomies", json={"title": f"Test Taxonomy {unique_id}"})
    assert (
        response.status_code == status.HTTP_201_CREATED
    ), f"Failed to create taxonomy: {response.text}"
    return response.json()["id"]


def get_change_event_ids(e2e_client, entity_id):
    """
    Helper to retrieve change event IDs for an entity.
    """
    response = e2e_client.get(f"/api/v1/versioning/changes/{entity_id}")
    assert response.status_code == status.HTTP_200_OK
    events = response.json()["events"]
    return [e["id"] for e in events]


@pytest.mark.e2e
class TestChangeHistory:
    """Tests for change history retrieval after ontology mutations."""

    def test_get_change_history_all(self, e2e_client):
        """
        Get all change history events.

        Asserts:
        - Status code 200 (OK)
        - Response includes events array and total count
        """
        # Create an entity to generate a change event
        response = e2e_client.post("/api/taxonomies", json={"title": "Change History Taxonomy"})
        assert response.status_code == status.HTTP_201_CREATED

        # Get all change history
        response = e2e_client.get("/api/v1/versioning/changes")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "events" in body
        assert "total" in body
        assert isinstance(body["events"], list)
        assert body["total"] >= 1

    def test_get_change_history_by_entity(self, e2e_client):
        """
        Get change history for a specific entity.

        Asserts:
        - Status code 200 (OK)
        - Events are filtered to the entity
        """
        # Create a taxonomy
        response = e2e_client.post(
            "/api/taxonomies", json={"title": "Entity Change History Taxonomy"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        taxonomy_id = response.json()["id"]

        # Get change history for this entity
        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "events" in body
        assert "total" in body
        assert body["total"] >= 1
        assert all(e.get("entity_id") == taxonomy_id for e in body["events"])

    def test_change_event_on_mutation(self, e2e_client):
        """
        Verify change events are recorded for mutations.

        Asserts:
        - Create event is recorded for taxonomy
        - Update event is recorded for taxonomy
        """
        # Create taxonomy
        create_response = e2e_client.post(
            "/api/taxonomies", json={"title": "Mutation Test Taxonomy"}
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        taxonomy_id = create_response.json()["id"]

        # Check creation event
        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        events = response.json()["events"]
        create_events = [e for e in events if e.get("operation") == "create"]
        assert len(create_events) > 0

        # Update taxonomy
        update_response = e2e_client.put(
            f"/api/taxonomies/{taxonomy_id}", json={"title": "Updated Title"}
        )
        assert update_response.status_code == status.HTTP_200_OK

        # Check update event
        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        events = response.json()["events"]
        update_events = [e for e in events if e.get("operation") == "update"]
        assert len(update_events) > 0


@pytest.mark.e2e
class TestSyncOperations:
    """Tests for sync status and operations."""

    def test_get_sync_status(self, e2e_client):
        """
        Get current synchronization status.

        Asserts:
        - Status code 200 (OK)
        - Response includes sync status information
        """
        # Create some activity to ensure sync status reflects something
        create_taxonomy_with_changes(e2e_client)

        response = e2e_client.get("/api/v1/versioning/sync/status")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # Field is unprocessed_count, not pending_changes
        assert "unprocessed_count" in body
        assert "is_configured" in body
        assert "last_pushed_at" in body
        assert "last_pulled_at" in body
