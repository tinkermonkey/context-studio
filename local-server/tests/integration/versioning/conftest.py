"""
Shared fixtures for versioning integration tests.

Provides common database, repository, and service fixtures used across
all versioning integration tests.
"""

import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base
from adapters.sync.noop_sync import NoOpSyncTarget
from adapters.web.versioning_routes import router
from domain.versioning.services import VersioningService
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
