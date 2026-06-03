"""
Shared fixtures for pipeline integration tests.

Provides common infrastructure for testing the pipeline framework:
- No-op pipeline registration
- Mock LLM provider with canned responses
- Database and repository fixtures
- Event publisher for change event tracking
- Quality testing fixtures (cassettes, refresh mode)
"""

import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.operations.models import OperationsBase
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.web.pipelines_routes import router
from domain.pipelines.entities import PipelineType
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.bootstrap import register_schema_extraction
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.integration.pipelines._harness.cassettes import (
    CassetteLLMProvider,
    RecordingLLMProvider,
)


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
def batch_repo(local_session_factory):
    """Create a real BatchRepository with actual persistence."""
    return BatchRepository(session_factory=local_session_factory)


@pytest.fixture
def event_publisher():
    """Create an in-process event publisher for testing."""
    return InProcessEventPublisher()


@pytest.fixture
def impl_registry():
    """Create initialized implementation registry with no-op and schema extraction pipelines."""
    registry = PipelineImplementationRegistry()
    registry.register_impl(
        PipelineType.NO_OP,
        "default",
        NoOpPipelineOrchestrator,
    )
    # Register schema extraction
    register_schema_extraction(
        registry, None
    )  # config_registry param will be None here
    return registry


@pytest.fixture
def config_registry(impl_registry):
    """Create initialized configuration registry."""
    registry = PipelineConfigurationRegistry()

    # Register a configuration for the no-op pipeline
    registry.register(
        PipelineType.NO_OP,
        "default",
        "noop-default",
        {"model": "test-model", "temperature": 0.0},
    )

    # Register schema extraction configurations
    register_schema_extraction(None, registry)  # impl_registry param will be None here

    return registry


@pytest.fixture
def llm_provider():
    """Create a mock LLM provider with canned responses."""
    return FakeLLMProvider(response_content="test response")


@pytest.fixture
def client(pipeline_run_repo, batch_repo, impl_registry, config_registry, llm_provider):
    """Create a TestClient with pipeline routes and registries."""
    app = FastAPI()
    app.include_router(router)

    # Store in app.state for route handlers
    app.state.pipeline_run_repo = pipeline_run_repo
    app.state.batch_repo = batch_repo
    app.state.implementation_registry = impl_registry
    app.state.config_registry = config_registry
    app.state.llm_router = llm_provider

    return TestClient(app)


def pytest_addoption(parser):
    """Register custom pytest command-line options for quality testing."""
    parser.addoption(
        "--refresh-cassettes",
        action="store_true",
        default=False,
        help="Re-record all cassettes against live providers",
    )


@pytest.fixture
def cassette_path(request):
    """Compute cassette path based on test module and function."""
    test_file = Path(request.node.fspath)
    test_module = request.node.name

    cassette_dir = test_file.parent / "_cassettes" / test_file.stem
    cassette_dir.mkdir(parents=True, exist_ok=True)

    return cassette_dir / f"{test_module}.json"


@pytest.fixture
def llm_provider_mode(request):
    """Determine execution mode: 'cassette' (default) or 'live'."""
    if request.node.get_closest_marker("real_llm"):
        return "live"
    return "cassette"


@pytest.fixture
def quality_llm_provider(request, llm_provider_mode, cassette_path, llm_provider):
    """Provide appropriate LLM provider based on execution mode.

    Returns:
    - CassetteLLMProvider if cassette mode and cassette exists
    - RecordingLLMProvider if refresh-cassettes is requested
    - Real llm_provider if live mode
    """
    if llm_provider_mode == "cassette":
        if cassette_path.exists() and not request.config.getoption(
            "--refresh-cassettes"
        ):
            yield CassetteLLMProvider(cassette_path)
        elif request.config.getoption("--refresh-cassettes"):
            provider = RecordingLLMProvider(llm_provider, cassette_path)
            yield provider
            provider.flush()
        else:
            raise FileNotFoundError(
                f"Cassette not found at {cassette_path}. "
                f"Run with --refresh-cassettes to record, or mark test with @pytest.mark.real_llm"
            )
    else:
        # Live mode
        yield llm_provider
