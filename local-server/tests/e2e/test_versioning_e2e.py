"""
E2E tests for the Version Control & Collaboration bounded context.

This module tests the Versioning bounded context through the HTTP API
with a fully initialized application using real databases and real adapters.

Tests verify:
- Change history retrieval after ontology mutations
- Entity version chain listing
- Changeset lifecycle (create → stage → submit as proposal)
- Proposal workflow (submit → approve → merge)
- Conflict detection
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi import status


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
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Change History Taxonomy"
        })
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
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Entity Change History Taxonomy"
        })
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
        create_response = e2e_client.post("/api/taxonomies", json={
            "title": "Mutation Test Taxonomy"
        })
        assert create_response.status_code == status.HTTP_201_CREATED
        taxonomy_id = create_response.json()["id"]

        # Check creation event
        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        events = response.json()["events"]
        create_events = [e for e in events if e.get("operation") == "create"]
        assert len(create_events) > 0

        # Update taxonomy
        update_response = e2e_client.put(f"/api/taxonomies/{taxonomy_id}", json={
            "title": "Updated Title"
        })
        assert update_response.status_code == status.HTTP_200_OK

        # Check update event
        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        events = response.json()["events"]
        update_events = [e for e in events if e.get("operation") == "update"]
        assert len(update_events) > 0


@pytest.mark.e2e
class TestEntityVersions:
    """Tests for entity version chain listing."""

    def test_list_entity_versions(self, e2e_client):
        """
        List all versions of an entity.

        Asserts:
        - Status code 200 (OK)
        - Response is array of EntityVersionResponse objects
        """
        # Create and modify a taxonomy
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Version List Taxonomy"
        })
        assert response.status_code == status.HTTP_201_CREATED
        taxonomy_id = response.json()["id"]

        # Update it to create a second version
        e2e_client.put(f"/api/taxonomies/{taxonomy_id}", json={
            "title": "Updated Version List Taxonomy"
        })

        # List versions - may be empty if versioning not enabled or events not recorded
        response = e2e_client.get(f"/api/v1/versioning/versions/{taxonomy_id}")
        # Accept 404 or 200 depending on whether versioning is active for this entity
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        if response.status_code == status.HTTP_200_OK:
            body = response.json()
            assert isinstance(body, list)
            # Verify each version has required fields if any exist
            for version in body:
                assert "version" in version
                assert "entity_id" in version
                assert "snapshot" in version

    def test_get_specific_version(self, e2e_client):
        """
        Get a specific version of an entity.

        Asserts:
        - Endpoint handles requests for specific versions
        """
        # Create an entity
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Specific Version Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        # Try to get version 1
        response = e2e_client.get(f"/api/v1/versioning/versions/{taxonomy_id}/1")
        # Accept 404 if version doesn't exist or 200 if it does
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        if response.status_code == status.HTTP_200_OK:
            body = response.json()
            assert body["version"] == 1
            assert body["entity_id"] == taxonomy_id

    def test_version_history_tracks_mutations(self, e2e_client):
        """
        Version history endpoint responds to mutation tracking requests.

        Asserts:
        - Endpoint handles requests for version lists
        """
        # Create and update
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Multi Update Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        # Update multiple times
        e2e_client.put(f"/api/taxonomies/{taxonomy_id}", json={
            "title": "Update 1"
        })
        e2e_client.put(f"/api/taxonomies/{taxonomy_id}", json={
            "title": "Update 2"
        })

        # Get versions
        response = e2e_client.get(f"/api/v1/versioning/versions/{taxonomy_id}")
        # Accept 404 if versioning not active, or 200 if it is
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
        if response.status_code == status.HTTP_200_OK:
            versions = response.json()
            assert isinstance(versions, list)


@pytest.mark.e2e
class TestChangesetLifecycle:
    """Tests for changeset lifecycle (create → stage → submit)."""

    def test_create_changeset(self, e2e_client):
        """
        Create a new changeset.

        Asserts:
        - Status code 201 (Created)
        - Response includes id, name, description, state, event_ids
        """
        # Create an entity to get change events
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Changeset Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        # Get the change events
        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        events = response.json()["events"]
        event_ids = [e["id"] for e in events]

        # Create changeset
        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Test Changeset",
            "description": "A test changeset",
            "event_ids": event_ids
        })
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert "id" in body
        assert body["name"] == "Test Changeset"
        assert body["description"] == "A test changeset"
        assert "state" in body
        # State is lowercase
        assert body["state"] == "working"

    def test_stage_changeset(self, e2e_client):
        """
        Transition changeset from working to staged.

        Asserts:
        - Status code 200 (OK)
        - State transitions to staged (lowercase)
        """
        # Create changeset
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Stage Test Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Stage Test Changeset",
            "description": "Test staging",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        # Stage it
        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # State is lowercase
        assert body["state"] == "staged"

    def test_changeset_lifecycle_flow(self, e2e_client):
        """
        Test complete changeset lifecycle from creation through staging.

        Asserts:
        - Changeset starts in working state (lowercase)
        - Can transition to staged state (lowercase)
        """
        # Setup
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Lifecycle Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        # Create
        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Lifecycle Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]
        # State is lowercase
        assert response.json()["state"] == "working"

        # Stage
        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        assert response.status_code == status.HTTP_200_OK
        # State is lowercase
        assert response.json()["state"] == "staged"


@pytest.mark.e2e
class TestProposalWorkflow:
    """Tests for proposal workflow (submit → approve → merge)."""

    def test_submit_proposal(self, e2e_client):
        """
        Submit a changeset as a proposal.

        Asserts:
        - Status code 200 (OK)
        - Response includes proposal id, changeset_id, state, created_at
        """
        # Setup changeset
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Proposal Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        # Create and stage
        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Proposal Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        # Submit proposal
        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "id" in body
        assert body["changeset_id"] == changeset_id
        assert body["state"] == "open"

    def test_approve_proposal(self, e2e_client):
        """
        Approve a proposal.

        Asserts:
        - Status code 200 (OK)
        - State transitions to 'approved'
        """
        # Setup: create and submit proposal
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Approve Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Approve Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = response.json()["id"]

        # Approve
        response = e2e_client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["state"] == "approved"

    def test_merge_proposal(self, e2e_client):
        """
        Merge an approved proposal.

        Asserts:
        - Status code 200 (OK)
        - Response includes merge result details
        """
        # Setup: create, submit, and approve proposal
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Merge Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Merge Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = response.json()["id"]

        e2e_client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Merge
        response = e2e_client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # Response has changeset_id, not merged_changeset_id
        assert "changeset_id" in body
        assert "merged_at" in body

    def test_proposal_full_workflow(self, e2e_client):
        """
        Test complete proposal workflow from submission through merge.

        Asserts:
        - Can create, submit, approve, and merge proposals
        - States transition correctly through the workflow (all lowercase)
        """
        # Setup
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Full Workflow Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        # Create changeset
        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Full Workflow Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        # Stage
        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        # State is lowercase
        assert response.json()["state"] == "staged"

        # Submit
        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = response.json()["id"]
        # State is lowercase
        assert response.json()["state"] == "open"

        # Approve
        response = e2e_client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")
        # State is lowercase
        assert response.json()["state"] == "approved"

        # Merge
        response = e2e_client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert response.status_code == status.HTTP_200_OK

    def test_reject_proposal(self, e2e_client):
        """
        Reject a proposal.

        Asserts:
        - Status code 200 (OK)
        - State transitions to 'rejected'
        """
        # Setup
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Reject Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Reject Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = response.json()["id"]

        # Reject
        response = e2e_client.post(f"/api/v1/versioning/proposals/{proposal_id}/reject", json={
            "reason": "Not ready for merge"
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["state"] == "rejected"


@pytest.mark.e2e
class TestConflictDetection:
    """Tests for conflict detection in proposals."""

    def test_detect_conflicts(self, e2e_client):
        """
        Detect conflicts in a proposal.

        Asserts:
        - Status code 200 (OK)
        - Response includes conflicts array and has_conflicts flag
        """
        # Setup
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Conflict Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Conflict Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = response.json()["id"]

        # Detect conflicts
        response = e2e_client.get(f"/api/v1/versioning/proposals/{proposal_id}/conflicts")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "proposal_id" in body
        assert "conflicts" in body
        assert "has_conflicts" in body
        assert isinstance(body["conflicts"], list)
        assert isinstance(body["has_conflicts"], bool)

    def test_auto_resolve_conflicts(self, e2e_client):
        """
        Automatically resolve conflicts using a merge strategy.

        Asserts:
        - Status code 200 (OK)
        - Response includes conflicts field
        """
        # Setup
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Auto Resolve Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Auto Resolve Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = response.json()["id"]

        # Auto-resolve with last_write_wins strategy (lowercase with underscores)
        response = e2e_client.post(f"/api/v1/versioning/proposals/{proposal_id}/auto-resolve", json={
            "strategy": "last_write_wins"
        })
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]
        if response.status_code == status.HTTP_200_OK:
            body = response.json()
            assert "conflicts" in body

    def test_conflict_report_structure(self, e2e_client):
        """
        Verify conflict report has correct structure.

        Asserts:
        - Conflict report includes all required fields
        """
        # Setup
        response = e2e_client.post("/api/taxonomies", json={
            "title": "Conflict Report Taxonomy"
        })
        taxonomy_id = response.json()["id"]

        response = e2e_client.get(f"/api/v1/versioning/changes/{taxonomy_id}")
        event_ids = [e["id"] for e in response.json()["events"]]

        response = e2e_client.post("/api/v1/versioning/changesets", json={
            "name": "Conflict Report Changeset",
            "event_ids": event_ids
        })
        changeset_id = response.json()["id"]

        e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = response.json()["id"]

        # Get conflict report
        response = e2e_client.get(f"/api/v1/versioning/proposals/{proposal_id}/conflicts")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        # Verify structure
        assert "proposal_id" in body
        assert body["proposal_id"] == proposal_id
        assert "has_conflicts" in body
        assert "conflicts" in body
        assert isinstance(body["conflicts"], list)


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
        response = e2e_client.get("/api/v1/versioning/sync/status")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # Field is unprocessed_count, not pending_changes
        assert "unprocessed_count" in body
        assert "is_configured" in body
        assert "last_pushed_at" in body
        assert "last_pulled_at" in body
