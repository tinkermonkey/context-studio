"""
Integration tests for the Version Control & Collaboration API routes.

Tests verify the change history and sync routes with:
- Real SQLite database (local.db)
- ChangeRepository backed by actual persistence
- VersioningService with sync adapter
- HTTP routes via TestClient
- End-to-end request/response validation

These tests exercise the complete stack: routes → domain service → adapters → database.
"""

import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base
from adapters.sync.noop_sync import NoOpSyncTarget
from adapters.web.versioning_routes import router
from domain.versioning.services import VersioningService
from domain.versioning.value_objects import ChangeOperation
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

    def test_sync_with_no_unprocessed_changes(self, client):
        """Test that push returns 0 when no unprocessed changes exist."""
        response = client.post("/api/v1/versioning/sync/push")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pushed"] == 0
