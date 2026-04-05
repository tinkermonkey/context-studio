"""
Integration tests for the Version Control & Collaboration API routes.

Tests verify the full changeset, proposal, and sync workflow with:
- Real SQLite database (local.db)
- ChangeRepository backed by actual persistence
- VersioningService with sync adapter
- HTTP routes via TestClient
- End-to-end request/response validation

These tests exercise the complete stack: routes → domain service → adapters → database.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from domain.versioning.services import VersioningService
from domain.versioning.value_objects import ChangeOperation
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.sync.noop_sync import NoOpSyncTarget
from adapters.web.versioning_routes import router
from tests.fakes.fake_event_publisher import FakeEventPublisher


@pytest.fixture
def temp_local_db():
    """Create a temporary local SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "local.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def local_session_factory(temp_local_db):
    """Create a session factory for the temporary local database."""
    engine = create_engine(temp_local_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def change_repository(local_session_factory):
    """Create a real SQLiteChangeRepository with actual persistence."""
    return SQLiteChangeRepository(session_factory=local_session_factory)


@pytest.fixture
def sync_target():
    """Create a no-op sync target for testing."""
    return NoOpSyncTarget()


@pytest.fixture
def event_publisher():
    """Create a FakeEventPublisher for testing."""
    return FakeEventPublisher()


@pytest.fixture
def versioning_service(change_repository, sync_target, event_publisher):
    """Create VersioningService with no-op sync adapter."""
    return VersioningService(
        change_repo=change_repository,
        sync_target=sync_target,
        event_publisher=event_publisher,
    )


@pytest.fixture
def client(versioning_service):
    """Create a TestClient with real versioning service."""
    app = FastAPI()
    app.include_router(router)
    app.state.versioning_service = versioning_service

    return TestClient(app)


class TestVersioningRoutes:
    """Integration tests for versioning routes."""

    # ==================== Change History Tests ====================

    def test_get_change_history_all_returns_200(self, client, change_repository):
        """GET /api/v1/versioning/changes returns 200 with empty list."""
        response = client.get("/api/v1/versioning/changes")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["events"] == []
        assert data["total"] == 0

    def test_get_change_history_all_with_changes(self, client, change_repository):
        """GET /api/v1/versioning/changes returns recorded changes."""
        # Record a change
        change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Test"},
        )

        response = client.get("/api/v1/versioning/changes")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["events"]) == 1
        assert data["total"] == 1
        assert data["events"][0]["entity_id"] == "entity-1"

    def test_get_change_history_by_entity(self, client, change_repository):
        """GET /api/v1/versioning/changes/{entity_id} filters by entity."""
        # Record changes for two entities
        change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Test1"},
        )
        change_repository.record_change(
            entity_id="entity-2",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Test2"},
        )

        response = client.get("/api/v1/versioning/changes/entity-1")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["entity_id"] == "entity-1"

    def test_list_versions_returns_200(self, client, change_repository):
        """GET /api/v1/versioning/versions/{entity_id} returns version list."""
        # Record a change which should create a version
        change_repository.record_change(
            entity_id="entity-1",
            entity_type="Class",
            operation=ChangeOperation.CREATE,
            new_state={"name": "Test"},
        )

        response = client.get("/api/v1/versioning/versions/entity-1")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_get_entity_version_returns_200(self, client, change_repository):
        """GET /api/v1/versioning/versions/{entity_id}/{version} returns specific version."""
        response = client.get("/api/v1/versioning/versions/entity-1/1")
        # Should return 404 if version doesn't exist
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    # ==================== Changeset Tests ====================

    def test_create_changeset_returns_201(self, client):
        """POST /api/v1/versioning/changesets returns 201."""
        response = client.post(
            "/api/v1/versioning/changesets",
            json={
                "name": "Test Changeset",
                "description": "A test changeset",
                "event_ids": [],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test Changeset"
        assert data["state"] == "working"
        assert "id" in data
        assert "created_at" in data

    def test_create_changeset_with_invalid_name_returns_422(self, client):
        """POST /api/v1/versioning/changesets with empty name returns 422."""
        response = client.post(
            "/api/v1/versioning/changesets",
            json={
                "name": "",
                "description": "A test changeset",
                "event_ids": [],
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_changeset_returns_404_not_found(self, client):
        """GET /api/v1/versioning/changesets/{id} returns 404 for nonexistent changeset."""
        response = client.get("/api/v1/versioning/changesets/nonexistent-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_changeset_returns_200(self, client):
        """GET /api/v1/versioning/changesets/{id} returns the changeset."""
        # Create a changeset first
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test Changeset"},
        )
        changeset_id = create_response.json()["id"]

        # Get it back
        response = client.get(f"/api/v1/versioning/changesets/{changeset_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == changeset_id
        assert data["name"] == "Test Changeset"

    def test_stage_changeset_returns_200(self, client):
        """POST /api/v1/versioning/changesets/{id}/stage transitions to STAGED."""
        # Create a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test Changeset"},
        )
        changeset_id = create_response.json()["id"]

        # Stage it
        response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["state"] == "staged"

    def test_submit_proposal_returns_200(self, client):
        """POST /api/v1/versioning/changesets/{id}/submit creates a proposal."""
        # Create and stage a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test Changeset"},
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        # Submit it
        response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["state"] == "open"
        assert "id" in data

    # ==================== Proposal Workflow Tests ====================

    def test_approve_proposal_returns_200(self, client):
        """POST /api/v1/versioning/proposals/{id}/approve transitions to approved."""
        # Create, stage, and submit a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test Changeset"},
        )
        changeset_id = create_response.json()["id"]
        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        # Approve it
        response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["state"] == "approved"

    def test_reject_proposal_returns_200(self, client):
        """POST /api/v1/versioning/proposals/{id}/reject transitions to rejected."""
        # Create, stage, and submit a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test Changeset"},
        )
        changeset_id = create_response.json()["id"]
        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        # Reject it
        response = client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/reject",
            json={"reason": "Does not meet requirements"},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["state"] == "rejected"
        assert data["reviewer_notes"] == "Does not meet requirements"

    def test_detect_conflicts_returns_200(self, client):
        """GET /api/v1/versioning/proposals/{id}/conflicts detects conflicts."""
        # Create, stage, and submit a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test Changeset"},
        )
        changeset_id = create_response.json()["id"]
        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        # Detect conflicts (should be empty for new changeset)
        response = client.get(f"/api/v1/versioning/proposals/{proposal_id}/conflicts")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["proposal_id"] == proposal_id
        assert data["conflicts"] == []
        assert data["has_conflicts"] is False

    def test_resolve_conflicts_returns_200(self, client):
        """POST /api/v1/versioning/proposals/{id}/resolve handles resolutions."""
        # Create, stage, and submit a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test Changeset"},
        )
        changeset_id = create_response.json()["id"]
        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        # Resolve conflicts (empty resolutions for new changeset)
        response = client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/resolve",
            json={"resolutions": {}},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["proposal_id"] == proposal_id

    def test_merge_proposal_returns_200(self, client):
        """POST /api/v1/versioning/proposals/{id}/merge merges approved proposal."""
        # Create, stage, submit, and approve a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test Changeset"},
        )
        changeset_id = create_response.json()["id"]
        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]
        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Merge it
        response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["proposal_id"] == proposal_id
        assert "merged_at" in data
        assert data["events_applied"] >= 0

    # ==================== Sync Tests ====================

    def test_get_sync_status_returns_200(self, client):
        """GET /api/v1/versioning/sync/status returns sync status."""
        response = client.get("/api/v1/versioning/sync/status")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "unprocessed_count" in data
        assert "is_configured" in data
        assert data["is_configured"] is False  # No-op target

    def test_push_changes_returns_200(self, client):
        """POST /api/v1/versioning/sync/push returns sync result."""
        response = client.post("/api/v1/versioning/sync/push")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "pushed" in data
        assert "pulled" in data
        assert "errors" in data

    def test_pull_changes_returns_200(self, client):
        """POST /api/v1/versioning/sync/pull returns sync result."""
        response = client.post("/api/v1/versioning/sync/pull")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "pushed" in data
        assert "pulled" in data
        assert "errors" in data

    # ==================== Workflow Integration Tests ====================

    def test_full_changeset_workflow(self, client):
        """Test complete changeset workflow: create → stage → submit → approve → merge."""
        # 1. Create changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Complete Workflow"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        changeset = create_response.json()
        changeset_id = changeset["id"]
        assert changeset["state"] == "working"

        # 2. Stage changeset
        stage_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        assert stage_response.status_code == status.HTTP_200_OK
        assert stage_response.json()["state"] == "staged"

        # 3. Submit proposal
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        assert submit_response.status_code == status.HTTP_200_OK
        proposal = submit_response.json()
        proposal_id = proposal["id"]
        assert proposal["state"] == "open"

        # 4. Approve proposal
        approve_response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")
        assert approve_response.status_code == status.HTTP_200_OK
        assert approve_response.json()["state"] == "approved"

        # 5. Merge proposal
        merge_response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert merge_response.status_code == status.HTTP_200_OK
        merge_result = merge_response.json()
        assert merge_result["proposal_id"] == proposal_id
        assert "merged_at" in merge_result

    def test_changeset_rejection_workflow(self, client):
        """Test changeset rejection: create → stage → submit → reject → back to working."""
        # 1. Create and stage changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Rejection Workflow"},
        )
        changeset_id = create_response.json()["id"]
        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        # 2. Submit proposal
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        # 3. Reject proposal
        reject_response = client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/reject",
            json={"reason": "Needs revision"},
        )
        assert reject_response.status_code == status.HTTP_200_OK
        assert reject_response.json()["state"] == "rejected"

        # 4. Changeset should be back in working state
        get_response = client.get(f"/api/v1/versioning/changesets/{changeset_id}")
        assert get_response.json()["state"] == "working"

    def test_sync_with_no_unprocessed_changes(self, client):
        """Test that push returns 0 when no unprocessed changes exist."""
        response = client.post("/api/v1/versioning/sync/push")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pushed"] == 0

    # ==================== 409 Conflict Error Tests ====================

    def test_stage_changeset_returns_409_when_already_staged(self, client):
        """Test stage_changeset returns 409 when changeset is already staged."""
        # Create and stage a changeset
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test", "description": "Test changeset"},
        )
        changeset_id = create_response.json()["id"]

        # Stage it once
        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")

        # Try to stage again - should return 409
        response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_submit_proposal_returns_409_when_not_staged(self, client):
        """Test submit_proposal returns 409 when changeset is not staged."""
        # Create a changeset but don't stage it
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test", "description": "Test changeset"},
        )
        changeset_id = create_response.json()["id"]

        # Try to submit without staging - should return 409
        response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_approve_proposal_returns_409_when_not_proposed(self, client):
        """Test approve_proposal returns 409 when proposal is not in open state."""
        # Create, stage, and submit a proposal
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test", "description": "Test changeset"},
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        # Approve it
        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Try to approve again - should return 409
        response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_reject_proposal_returns_409_when_not_proposed(self, client):
        """Test reject_proposal returns 409 when proposal is not in open state."""
        # Create, stage, and submit a proposal
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test", "description": "Test changeset"},
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        # Approve it
        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Try to reject an approved proposal - should return 409
        response = client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/reject",
            json={"reason": "Not needed anymore"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_merge_proposal_returns_409_when_not_approved(self, client):
        """Test merge_proposal returns 409 when changeset is not in APPROVED state."""
        # Create, stage, and submit a proposal (but don't approve)
        create_response = client.post(
            "/api/v1/versioning/changesets",
            json={"name": "Test", "description": "Test changeset"},
        )
        changeset_id = create_response.json()["id"]

        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        submit_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = submit_response.json()["id"]

        # Try to merge without approving - should return 409
        response = client.post(f"/api/v1/versioning/proposals/{proposal_id}/merge")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_resolve_conflicts_returns_409_when_conflicts_remain(
        self, client, change_repository
    ):
        """Test resolve_conflicts returns 409 when conflicts are not fully resolved."""
        # Create and record conflicting events
        event_id_1 = change_repository.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "old_name"},
            new_state={"name": "new_name_1"},
        )
        event_id_2 = change_repository.record_change(
            entity_id="entity1",
            entity_type="class",
            operation=ChangeOperation.UPDATE,
            previous_state={"name": "different_name"},
            new_state={"name": "new_name_2"},
        )

        # Create changeset with these conflicting events
        changeset_response = client.post(
            "/api/v1/versioning/changesets",
            json={
                "name": "Conflicting",
                "description": "Has conflicts",
                "event_ids": [event_id_1, event_id_2],
            },
        )
        changeset_id = changeset_response.json()["id"]

        # Stage, submit, approve
        client.post(f"/api/v1/versioning/changesets/{changeset_id}/stage")
        proposal_response = client.post(f"/api/v1/versioning/changesets/{changeset_id}/submit")
        proposal_id = proposal_response.json()["id"]
        client.post(f"/api/v1/versioning/proposals/{proposal_id}/approve")

        # Try to resolve without actually resolving conflicts - should return 409
        # (empty resolutions dict leaves conflicts unresolved)
        response = client.post(
            f"/api/v1/versioning/proposals/{proposal_id}/resolve",
            json={"resolutions": {}},
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "conflict" in response.json()["detail"].lower()
