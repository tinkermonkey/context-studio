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

import pytest
from fastapi import status


def create_taxonomy_with_changes(e2e_client):
    """
    Helper to create a taxonomy and return its ID.
    Used to reduce boilerplate in versioning tests.
    """
    import uuid

    unique_id = str(uuid.uuid4())[:8]
    response = e2e_client.post(
        "/api/taxonomies", json={"title": f"Test Taxonomy {unique_id}"}
    )
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


def create_and_submit_changeset(e2e_client, event_ids, changeset_name="Test Changeset"):
    """
    Helper to create a changeset, stage it, and submit it as a proposal.
    Returns the proposal_id.
    """
    # Create changeset
    response = e2e_client.post(
        "/api/v1/versioning/changesets",
        json={
            "name": changeset_name,
            "description": f"Test changeset: {changeset_name}",
            "event_ids": event_ids,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    changeset_id = response.json()["id"]

    # Stage it
    response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
    assert response.status_code == status.HTTP_200_OK

    # Submit as proposal
    response = e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
    assert response.status_code == status.HTTP_200_OK
    return response.json()["id"]


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
        response = e2e_client.post(
            "/api/taxonomies", json={"title": "Change History Taxonomy"}
        )
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
class TestEntityVersions:
    """Tests for entity version chain listing."""

    def test_list_entity_versions(self, e2e_client):
        """
        List all versions of an entity after creation.

        Asserts:
        - Status code 200 (OK)
        - Response is array of EntityVersionResponse objects
        """
        # Create an entity
        taxonomy_id = create_taxonomy_with_changes(e2e_client)

        # List versions
        response = e2e_client.get(f"/api/v1/versioning/versions/{taxonomy_id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert isinstance(body, list)
        # Verify each version (if any) has required fields
        for version in body:
            assert "version" in version
            assert "entity_id" in version
            assert "snapshot" in version

    def test_get_specific_version(self, e2e_client):
        """
        Get a specific version of an entity.

        Asserts:
        - Response status is 200 (OK) after version snapshot is created via merge workflow
        - Response includes version, entity_id, and snapshot
        """
        # Create an entity
        taxonomy_id = create_taxonomy_with_changes(e2e_client)

        # Get change events for the entity
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)

        # Create, stage, and submit changeset as proposal
        proposal_id = create_and_submit_changeset(
            e2e_client, event_ids, "Version Test Changeset"
        )

        # Approve the proposal
        approve_response = e2e_client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/approve"
        )
        assert approve_response.status_code == status.HTTP_200_OK

        # Merge the proposal (this creates version snapshots)
        merge_response = e2e_client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/merge"
        )
        assert merge_response.status_code == status.HTTP_200_OK

        # Get version 1 (now exists due to merge creating a snapshot)
        response = e2e_client.get(f"/api/v1/versioning/versions/{taxonomy_id}/1")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["version"] == 1
        assert body["entity_id"] == taxonomy_id
        assert "snapshot" in body

    def test_version_history_tracks_mutations(self, e2e_client):
        """
        Verify version history tracks mutations.

        Asserts:
        - Status code 200 (OK)
        - Can retrieve version list after multiple updates
        """
        # Create and update
        taxonomy_id = create_taxonomy_with_changes(e2e_client)

        # Update multiple times
        update1_response = e2e_client.put(
            f"/api/taxonomies/{taxonomy_id}", json={"title": "Update 1"}
        )
        assert update1_response.status_code == status.HTTP_200_OK

        update2_response = e2e_client.put(
            f"/api/taxonomies/{taxonomy_id}", json={"title": "Update 2"}
        )
        assert update2_response.status_code == status.HTTP_200_OK

        # Get versions
        response = e2e_client.get(f"/api/v1/versioning/versions/{taxonomy_id}")
        assert response.status_code == status.HTTP_200_OK
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
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)

        # Create changeset
        response = e2e_client.post(
            "/api/v1/versioning/changesets",
            json={
                "name": "Test Changeset",
                "description": "A test changeset",
                "event_ids": event_ids,
            },
        )
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
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)

        response = e2e_client.post(
            "/api/v1/versioning/changesets",
            json={
                "name": "Stage Test Changeset",
                "description": "Test staging",
                "event_ids": event_ids,
            },
        )
        changeset_id = response.json()["id"]

        # Stage it
        response = e2e_client.post(
            f"/api/v1/versioning/changesets/{changeset_id}/stage"
        )
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
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)

        # Create
        response = e2e_client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Lifecycle Changeset", "event_ids": event_ids},
        )
        changeset_id = response.json()["id"]
        # State is lowercase
        assert response.json()["state"] == "working"

        # Stage
        response = e2e_client.post(
            f"/api/v1/versioning/changesets/{changeset_id}/stage"
        )
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
        # Create changeset and get event IDs
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)

        # Create changeset
        response = e2e_client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Proposal Changeset", "event_ids": event_ids},
        )
        changeset_id = response.json()["id"]

        # Stage it
        e2e_client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        # Submit proposal
        response = e2e_client.post(
            f"/api/v1/versioning/changesets/{changeset_id}/submit"
        )
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
        # Create changeset and submit as proposal
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)
        proposal_id = create_and_submit_changeset(
            e2e_client, event_ids, "Approve Changeset"
        )

        # Approve
        response = e2e_client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/approve"
        )
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
        # Create changeset and submit as proposal
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)
        proposal_id = create_and_submit_changeset(
            e2e_client, event_ids, "Merge Changeset"
        )

        # Approve
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
        # Create changeset and submit as proposal
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)

        # Create changeset
        response = e2e_client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Full Workflow Changeset", "event_ids": event_ids},
        )
        changeset_id = response.json()["id"]

        # Stage
        response = e2e_client.post(
            f"/api/v1/versioning/changesets/{changeset_id}/stage"
        )
        # State is lowercase
        assert response.json()["state"] == "staged"

        # Submit
        response = e2e_client.post(
            f"/api/v1/versioning/changesets/{changeset_id}/submit"
        )
        proposal_id = response.json()["id"]
        # State is lowercase
        assert response.json()["state"] == "open"

        # Approve
        response = e2e_client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/approve"
        )
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
        # Create changeset and submit as proposal
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)
        proposal_id = create_and_submit_changeset(
            e2e_client, event_ids, "Reject Changeset"
        )

        # Reject
        response = e2e_client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/reject",
            json={"reason": "Not ready for merge"},
        )
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
        # Create changeset and submit as proposal
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)
        proposal_id = create_and_submit_changeset(
            e2e_client, event_ids, "Conflict Changeset"
        )

        # Detect conflicts
        response = e2e_client.get(
            f"/api/v1/versioning/proposals/{proposal_id}/conflicts"
        )
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
        - 422 means there are no conflicts to resolve (valid expected scenario)
        """
        # Create changeset and submit as proposal
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)
        proposal_id = create_and_submit_changeset(
            e2e_client, event_ids, "Auto Resolve Changeset"
        )

        # Auto-resolve with last_write_wins strategy (lowercase with underscores)
        # 422 is expected if there are no conflicts to resolve (proposal is conflict-free)
        # 200 is expected if there are conflicts that were resolved
        response = e2e_client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/auto-resolve",
            json={"strategy": "last_write_wins"},
        )
        # In a clean proposal without conflicts, 422 Unprocessable Entity is returned
        # because there is nothing to auto-resolve. This is the expected behavior.
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]
        if response.status_code == status.HTTP_200_OK:
            body = response.json()
            assert "conflicts" in body

    def test_conflict_report_structure(self, e2e_client):
        """
        Verify conflict report has correct structure.

        Asserts:
        - Conflict report includes all required fields
        """
        # Create changeset and submit as proposal
        taxonomy_id = create_taxonomy_with_changes(e2e_client)
        event_ids = get_change_event_ids(e2e_client, taxonomy_id)
        proposal_id = create_and_submit_changeset(
            e2e_client, event_ids, "Conflict Report Changeset"
        )

        # Get conflict report
        response = e2e_client.get(
            f"/api/v1/versioning/proposals/{proposal_id}/conflicts"
        )
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
