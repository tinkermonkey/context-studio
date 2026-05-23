"""
Shared fixtures for pipeline integration tests.

Provides common infrastructure for testing the pipeline framework:
- No-op pipeline registration
- Mock LLM provider with canned responses
- Database and repository fixtures
- Event publisher for change event tracking
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.operations.models import OperationsBase
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.web.pipelines_routes import router
from domain.pipeline.ports import LLMResponse
from domain.pipelines.entities import PipelineType
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)


class CanLLMProvider:
    """Mock LLM provider with canned responses for deterministic testing."""

    def __init__(self, response_content: str = "test response"):
        """Initialize with a fixed response."""
        self.response_content = response_content
        self.call_count = 0
        self.last_call_args = None

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format=None,
        timeout=None,
        seed=None,
    ) -> LLMResponse:
        """Return canned response."""
        self.call_count += 1
        self.last_call_args = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
            "timeout": timeout,
            "seed": seed,
        }

        return LLMResponse(
            content=self.response_content,
            tokens_in=10,
            tokens_out=5,
            duration_ms=100,
            finish_reason="stop",
            model=model,
        )

    def is_model_available(self, model: str) -> bool:
        """Check if model is available."""
        return True

    def list_available_models(self) -> list[str]:
        """List available models."""
        return ["test-model"]


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
def temp_ops_db():
    """Create a temporary operations SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "operations.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        OperationsBase.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def local_session_factory(temp_local_db):
    """Create a session factory for the temporary local database."""
    engine = create_engine(temp_local_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def ops_session_factory(temp_ops_db):
    """Create a session factory for the temporary operations database."""
    engine = create_engine(temp_ops_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def pipeline_run_repo(local_session_factory):
    """Create a real PipelineRepository with actual persistence."""
    return PipelineRepository(session_factory=local_session_factory)


@pytest.fixture
def event_publisher():
    """Create an in-process event publisher for testing."""
    return InProcessEventPublisher()


@pytest.fixture
def impl_registry():
    """Create initialized implementation registry with no-op pipeline."""
    registry = PipelineImplementationRegistry()
    registry.register_impl(
        PipelineType.NO_OP,
        "default",
        NoOpPipelineOrchestrator,
    )
    return registry


@pytest.fixture
def config_registry():
    """Create initialized configuration registry."""
    registry = PipelineConfigurationRegistry()

    # Register a configuration for the no-op pipeline
    registry.register(
        PipelineType.NO_OP,
        "default",
        "noop-default",
        {"model": "test-model", "temperature": 0.0},
    )

    return registry


@pytest.fixture
def llm_provider():
    """Create a mock LLM provider with canned responses."""
    return CanLLMProvider()


@pytest.fixture
def client(pipeline_run_repo, impl_registry, config_registry):
    """Create a TestClient with pipeline routes and registries."""
    app = FastAPI()
    app.include_router(router)

    # Store in app.state for route handlers
    app.state.pipeline_run_repo = pipeline_run_repo
    app.state.implementation_registry = impl_registry
    app.state.config_registry = config_registry

    return TestClient(app)
