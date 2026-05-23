"""
Shared fixtures for integration tests.

Provides common infrastructure for all integration tests:
- Network blocking to prevent outgoing calls during CI
- Database fixtures
- Event publisher fixtures
- LLM mock fixtures
"""

import socket as socket_module
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base

_original_socket = socket_module.socket


def _blocking_socket(family=socket_module.AF_INET, *args, **kwargs):
    """Block outgoing network calls, but allow local sockets."""
    # Block network sockets (AF_INET, AF_INET6)
    if family in (socket_module.AF_INET, socket_module.AF_INET6):
        raise RuntimeError(
            "Network access is blocked during test runs. "
            "If this test requires external network access, "
            "mark it with @pytest.mark.external_network"
        )

    # Allow all other socket families
    return _original_socket(family, *args, **kwargs)


@pytest.fixture(autouse=True)
def block_network(request):
    """Block outgoing network calls by default.

    Tests can opt-out with @pytest.mark.external_network marker.
    """
    if "external_network" in request.keywords:
        yield
        return

    with patch.object(socket_module, "socket", side_effect=_blocking_socket):
        yield


@pytest.fixture
def db_session():
    """Create a temporary database session for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        try:
            yield session
        finally:
            session.close()
