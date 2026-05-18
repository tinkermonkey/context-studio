"""
Integration test for entity version creation on merge.

This test verifies that when a changeset is merged, entity versions are created
and can be queried via the API endpoints.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from fastapi import status

from domain.versioning.value_objects import ChangeOperation


class TestMergeVersionsIntegration:
    """Integration tests for entity version creation on merge."""

    def test_merge_creates_entity_version_from_single_create_event(self, client, change_repository):
        """Test that merging a changeset with a CREATE event creates an entity version."""
        # Record a CREATE change event
        event_id = change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity 1", "description": "A test entity"},
        )

        # Create, stage, submit, and approve a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Create Entity", "event_ids": [event_id]},
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Merge the proposal
        merge_response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert merge_response.status_code == status.HTTP_200_OK
        merge_data = merge_response.json()
        assert merge_data["events_applied"] == 1

        # Query the entity version via the API
        versions_response = client.get("/api/v1/versioning/versions/entity-1")
        assert versions_response.status_code == status.HTTP_200_OK
        versions = versions_response.json()
        assert len(versions) == 1

        version = versions[0]
        assert version["entity_id"] == "entity-1"
        assert version["version"] == 1
        assert version["state"] == "active"
        assert version["snapshot"]["name"] == "Entity 1"
        assert version["snapshot"]["description"] == "A test entity"

    def test_merge_creates_multiple_entity_versions(self, client, change_repository):
        """Test that merging a changeset with updates to multiple entities creates multiple
        versions."""
        # Record changes to two different entities
        event_id_1 = change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity 1"},
        )
        event_id_2 = change_repository.record_change(
            entity_id="entity-2",
            entity_type="Taxonomy",
            operation=ChangeOperation.CREATE,
            new_state={"label": "Entity 2"},
        )

        # Create changeset with both events
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={
                "name": "Create Multiple Entities",
                "event_ids": [event_id_1, event_id_2],
            },
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Merge the proposal
        merge_response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert merge_response.status_code == status.HTTP_200_OK

        # Query versions for entity-1
        versions_1_response = client.get("/api/v1/versioning/versions/entity-1")
        assert versions_1_response.status_code == status.HTTP_200_OK
        versions_1 = versions_1_response.json()
        assert len(versions_1) == 1
        assert versions_1[0]["entity_id"] == "entity-1"
        assert versions_1[0]["snapshot"]["name"] == "Entity 1"

        # Query versions for entity-2
        versions_2_response = client.get("/api/v1/versioning/versions/entity-2")
        assert versions_2_response.status_code == status.HTTP_200_OK
        versions_2 = versions_2_response.json()
        assert len(versions_2) == 1
        assert versions_2[0]["entity_id"] == "entity-2"
        assert versions_2[0]["snapshot"]["label"] == "Entity 2"

    def test_merge_with_conflicts_creates_entity_version_with_resolutions(
        self, client, change_repository
    ):
        """Test that merging with resolved conflicts creates entity versions with resolved
        values."""
        # Record conflicting changes
        event_id_1 = change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "old"},
            new_state={"name": "new1"},
        )
        event_id_2 = change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "external"},
            new_state={"name": "new2"},
        )

        # Create changeset with conflicting events
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={
                "name": "Resolve Conflicts",
                "event_ids": [event_id_1, event_id_2],
            },
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Auto-resolve conflicts with LAST_WRITE_WINS strategy
        auto_resolve_response = client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/auto-resolve",
            json={"strategy": "last_write_wins"},
        )
        assert auto_resolve_response.status_code == status.HTTP_200_OK
        auto_resolve_data = auto_resolve_response.json()
        assert auto_resolve_data["has_conflicts"] is True
        # All conflicts should be resolved
        assert all(c["is_resolved"] for c in auto_resolve_data["conflicts"])

        # Merge the proposal
        merge_response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert merge_response.status_code == status.HTTP_200_OK
        merge_data = merge_response.json()
        assert merge_data["conflicts_resolved"] == 1
        assert merge_data["events_applied"] == 2

        # Query the entity version
        versions_response = client.get("/api/v1/versioning/versions/entity-1")
        assert versions_response.status_code == status.HTTP_200_OK
        versions = versions_response.json()
        assert len(versions) == 1

        # Verify the snapshot contains the resolved value
        version = versions[0]
        assert version["snapshot"]["name"] == "new2"  # incoming_value wins

    def test_query_specific_entity_version_by_version_number(self, client, change_repository):
        """Test querying a specific version by version number."""
        # Record a CREATE change
        event_id = change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity 1"},
        )

        # Create and merge changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Create Entity", "event_ids": [event_id]},
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")
        client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")

        # Query specific version
        version_response = client.get("/api/v1/versioning/versions/entity-1/1")
        assert version_response.status_code == status.HTTP_200_OK
        version = version_response.json()

        assert version["entity_id"] == "entity-1"
        assert version["version"] == 1
        assert version["state"] == "active"
        assert version["snapshot"]["name"] == "Entity 1"

    def test_merge_delete_operation_creates_archived_version(self, client, change_repository):
        """Test that deleting an entity creates an ARCHIVED version."""
        # Record a CREATE, then a DELETE
        event_id_1 = change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Entity 1"},
        )
        event_id_2 = change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.DELETE,
            previous_state={"name": "Entity 1"},
            new_state={},
        )

        # Create changeset with delete
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={
                "name": "Delete Entity",
                "event_ids": [event_id_1, event_id_2],
            },
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Merge the proposal
        merge_response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert merge_response.status_code == status.HTTP_200_OK
        merge_data = merge_response.json()
        assert merge_data["events_applied"] == 2

        # Query the versions
        versions_response = client.get("/api/v1/versioning/versions/entity-1")
        assert versions_response.status_code == status.HTTP_200_OK
        versions = versions_response.json()

        # When CREATE and DELETE are in the same changeset, they create a single version
        # with ARCHIVED state (since the final operation is a DELETE)
        assert len(versions) == 1
        assert versions[0]["version"] == 1
        assert versions[0]["state"] == "archived"
        assert versions[0]["snapshot"]["name"] == "Entity 1"
