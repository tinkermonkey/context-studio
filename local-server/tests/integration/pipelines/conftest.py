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
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.llm.provider_router import LLMProviderRouter
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.operations.models import OperationsBase
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from adapters.web.pipelines_routes import router
from config import get_settings
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineType
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.bootstrap import register_schema_extraction
from scripts.dr_ontology_loader import import_dr_ontology
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.integration.pipelines._harness.cassettes import (
    CassetteLLMProvider,
    RecordingLLMProvider,
)
from tests.integration.pipelines._harness.dataset_split import OntologyContext

# Candidate locations for the sibling `documentation_robotics/spec` checkout
# (an external, versioned dependency — see
# documentation/karpathy_loop_dr_ontology_design.md §4). Not every environment
# has it; the DR_SPEC ontology_factory branch skips when neither is found.
_DR_SPEC_DIR_CANDIDATES = [
    Path(__file__).resolve().parents[5] / "documentation_robotics" / "spec",
    Path("/reference/documentation_robotics/spec"),
]


def _find_dr_spec_dir() -> Path | None:
    return next((p for p in _DR_SPEC_DIR_CANDIDATES if p.is_dir()), None)


def _build_placeholder_ontology():
    """The throwaway 3-class (individual/property/entity) ontology, in-memory."""
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)

    tax = Taxonomy(
        id=str(uuid4()),
        identifier="placeholder",
        title="Placeholder Ontology",
        description="Throwaway 3-class ontology for individual-extraction quality tests",
    )
    repo.save_taxonomy(tax)
    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="placeholder_scheme",
        taxonomy_id=tax.id,
        title="Placeholder Scheme",
        description="Placeholder concept scheme",
    )
    repo.save_concept_scheme(scheme)
    for class_name in ("individual", "property", "entity"):
        repo.save_class(
            Class(
                id=str(uuid4()),
                identifier=class_name,
                concept_scheme_id=scheme.id,
                taxonomy_id=tax.id,
                title=class_name.title(),
                description=f"A {class_name}",
            )
        )

    index = SqliteSchemaVectorIndex(session_factory, FakeEmbeddingService())
    index.reindex_all()
    return repo, index


def _build_dr_spec_ontology():
    """
    The imported DR spec ontology (~1,750 rows), in-memory.

    Reuses the Phase 1 DR-spec transform (scripts.dr_ontology_loader) rather
    than duplicating any translation logic. Skips if the sibling DR spec
    checkout isn't available in this environment.
    """
    spec_dir = _find_dr_spec_dir()
    if spec_dir is None:
        pytest.skip(
            "documentation_robotics/spec checkout not found (checked "
            f"{[str(p) for p in _DR_SPEC_DIR_CANDIDATES]}); skipping DR_SPEC ontology tests"
        )

    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    embedding_service = FakeEmbeddingService()
    # schema_index=None here for the same reason as import_dr_ontology.py's
    # CLI entrypoint: suppress per-entity embedding sync during import, then
    # reindex once in a single batch below.
    ontology_service = OntologyService(
        repository=repo,
        embedding_service=embedding_service,
        event_publisher=InProcessEventPublisher(),
        schema_index=None,
    )
    import_dr_ontology(ontology_service, repo, spec_dir)

    index = SqliteSchemaVectorIndex(session_factory, embedding_service)
    index.reindex_all()
    return repo, index


_ONTOLOGY_BUILDERS = {
    OntologyContext.PLACEHOLDER: _build_placeholder_ontology,
    OntologyContext.DR_SPEC: _build_dr_spec_ontology,
}


@pytest.fixture(scope="session")
def ontology_factory():
    """
    Session-scoped factory returning a cached (repo, schema_index) pair for a
    given OntologyContext.

    Each context is built at most once per test session — scenario tests that
    request the same context repeatedly (e.g. all 18 PLACEHOLDER scenarios)
    reuse the same in-memory ontology instead of rebuilding it per test.
    """
    cache: dict[OntologyContext, tuple] = {}

    def _get(context: OntologyContext):
        if context not in cache:
            cache[context] = _ONTOLOGY_BUILDERS[context]()
        return cache[context]

    return _get


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
    register_schema_extraction(registry, None)  # config_registry param will be None here
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
        if cassette_path.exists() and not request.config.getoption("--refresh-cassettes"):
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


@pytest.fixture
def quality_llm_provider_factory(request):
    """Factory to create LLM providers for quality test scenarios.

    Handles cassette mode with intelligent logic:
    - If --refresh-cassettes is set: use RecordingLLMProvider (even if cassette exists)
    - Else if cassette exists: use CassetteLLMProvider
    - Else: skip test

    Parameters:
        scenario: scenario name (used in cassette filename)
        cassette_dir: directory containing cassettes
        cassette_prefix: prefix for cassette filename (e.g., "individual_extraction_")
    """

    def _make_provider(scenario: str, cassette_dir: Path, cassette_prefix: str):
        cassette_path = cassette_dir / f"{cassette_prefix}{scenario}.json"
        refresh_cassettes = request.config.getoption("--refresh-cassettes")

        # Check --refresh-cassettes first so we can re-record existing cassettes
        if refresh_cassettes:
            settings = get_settings()
            llm_config = settings.llm
            if (
                not llm_config.openai_api_key
                and not llm_config.anthropic_api_key
                and not llm_config.openrouter_api_key
            ):
                pytest.skip(
                    f"Cassette not found at {cassette_path} and no real LLM provider configured. "
                    "To record cassettes, set OPENAI_API_KEY, ANTHROPIC_API_KEY, or "
                    "OPENROUTER_API_KEY."
                )

            try:
                real_llm_provider = LLMProviderRouter(
                    openai_api_key=llm_config.openai_api_key,
                    anthropic_api_key=llm_config.anthropic_api_key,
                    openrouter_api_key=llm_config.openrouter_api_key,
                )
            except ValueError as e:
                pytest.skip(f"Failed to initialize LLM provider: {e}")

            return RecordingLLMProvider(real_llm_provider, cassette_path)

        # Cassette mode: require cassette to exist and contain recorded responses
        if not cassette_path.exists():
            pytest.skip(
                f"Cassette not found at {cassette_path}. " "Run with --refresh-cassettes to record."
            )

        try:
            import json as _json

            with open(cassette_path, "r") as _f:
                _data = _json.load(_f)
            if not _data:
                pytest.skip(
                    f"Cassette at {cassette_path} is empty. "
                    "Run with --refresh-cassettes to record."
                )
        except (ValueError, OSError):
            pytest.skip(
                f"Cassette at {cassette_path} is unreadable. "
                "Run with --refresh-cassettes to record."
            )

        return CassetteLLMProvider(cassette_path)

    return _make_provider
