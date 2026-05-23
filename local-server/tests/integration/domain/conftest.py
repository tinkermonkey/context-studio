"""
Shared test fixtures and utilities for domain integration tests.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.services import OntologyService

from .mocks import DummyEmbeddingService, DummyEventPublisher, MockLLMProvider

# Re-export mock classes for use in tests
__all__ = ["MockLLMProvider", "DummyEventPublisher", "DummyEmbeddingService"]


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        yield db_url


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory."""
    engine = create_engine(temp_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def ontology_service(session_factory):
    """Create an ontology service."""
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    embedding_svc = DummyEmbeddingService()
    event_pub = DummyEventPublisher()
    return OntologyService(
        repository=repo,
        embedding_service=embedding_svc,
        event_publisher=event_pub,
    )
