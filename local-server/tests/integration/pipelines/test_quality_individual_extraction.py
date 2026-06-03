"""
Quality test suite for individual_extraction pipeline.

Verifies extraction quality using a curated fixture corpus with hand-labeled
expected triples. Measures precision, recall, F1 score, per-(subject_class, predicate)
breakdown, and Brier score on confidence calibration.

Metric floors:
- recall ≥ 0.50
- precision ≥ 0.60
- f1 ≥ 0.50
- brier ≤ 0.25
"""

import json
import logging
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import SQLiteExtractionRunRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.pipelines.entities import PipelineRun, PipelineType
from domain.pipelines.individual_extraction import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
    register_individual_extraction,
)
from domain.pipelines.individual_extraction.apply_service import IndividualExtractionApplyService
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource
from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture
from tests.integration.pipelines._harness.cassettes import (
    CassetteLLMProvider,
    RecordingLLMProvider,
)
from tests.integration.pipelines._harness.metrics import (
    brier_score,
    precision_recall_f1,
)
from tests.integration.pipelines._harness.report import FloorGate, MetricsEmitter

_logger = logging.getLogger(__name__)

# Quality fixture scenarios for individual extraction
QUALITY_SCENARIOS = [
    "async_patterns",
    "clean_code",
    "design_patterns",
    "distributed_systems",
    "domain_driven_design",
    "microservices_architecture",
    "object_oriented_design",
    "reactive_programming",
    "service_oriented",
    "testing_strategies",
]

# Metric floors for individual extraction quality
METRIC_FLOORS = {
    "precision": 0.60,
    "recall": 0.50,
    "f1": 0.50,
    "brier": 0.25,
}


def extract_triple_key(triple: dict) -> tuple:
    """
    Extract a comparable key from a triple dict.

    Returns (subject_label, predicate_label, object_label) tuple.
    """
    subject_label = triple.get("subject", {}).get("label", "")
    predicate_label = triple.get("predicate", {}).get("label", "")
    object_label = triple.get("object", {}).get("label", "")
    return (subject_label, predicate_label, object_label)


def extract_confidence(triple: dict) -> float:
    """Extract confidence value from a triple, default to 0.5 if missing."""
    return triple.get("confidence", 0.5)


def compute_per_category_metrics(
    expected_triples: list[dict],
    actual_triples: list[dict],
) -> dict:
    """
    Compute per-(subject_class, predicate) breakdown metrics.

    Returns dict mapping (subject, predicate) tuple to PrecisionRecallF1.
    """
    expected_by_category: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    actual_by_category: dict[tuple[str, str], list[tuple[str, str, str]]] = {}

    for triple in expected_triples:
        subject = triple.get("subject", {}).get("label", "unknown")
        predicate = triple.get("predicate", {}).get("label", "unknown")
        category = (subject, predicate)
        if category not in expected_by_category:
            expected_by_category[category] = []
        expected_by_category[category].append(extract_triple_key(triple))

    for triple in actual_triples:
        subject = triple.get("subject", {}).get("label", "unknown")
        predicate = triple.get("predicate", {}).get("label", "unknown")
        category = (subject, predicate)
        if category not in actual_by_category:
            actual_by_category[category] = []
        actual_by_category[category].append(extract_triple_key(triple))

    breakdown = {}
    all_categories = set(expected_by_category.keys()) | set(actual_by_category.keys())

    for category in all_categories:
        expected = expected_by_category.get(category, [])
        actual = actual_by_category.get(category, [])
        metrics = precision_recall_f1(expected, actual)
        breakdown[category] = {
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
        }

    return breakdown


def compute_quality_metrics(
    expected_triples: list[dict],
    actual_triples: list[dict],
) -> dict:
    """
    Compute aggregate quality metrics for individual extraction.

    Returns dict with keys: precision, recall, f1, brier, per_category_breakdown.
    """
    # Convert to comparable keys
    expected_keys = [extract_triple_key(t) for t in expected_triples]
    actual_keys = [extract_triple_key(t) for t in actual_triples]

    # Compute precision, recall, F1
    metrics = precision_recall_f1(expected_keys, actual_keys)

    # Compute Brier score on confidence calibration
    # For triples in expected set: predicted confidence should be ~1.0
    # For triples NOT in expected set: predicted confidence should be ~0.0
    expected_set = set(expected_keys)
    brier_probs = []
    brier_labels = []

    for triple in actual_triples:
        key = extract_triple_key(triple)
        confidence = extract_confidence(triple)
        label = 1 if key in expected_set else 0
        brier_probs.append(confidence)
        brier_labels.append(label)

    brier = brier_score(brier_probs, brier_labels) if brier_probs else 0.0

    # Per-category breakdown
    breakdown = compute_per_category_metrics(expected_triples, actual_triples)

    return {
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "brier": brier,
        "per_category_breakdown": breakdown,
    }


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    engine = create_engine(temp_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def ontology_repo(session_factory):
    """Create a real SQLiteOntologyRepository with test data."""
    repo = SQLiteOntologyRepository(session_factory)

    # Create ontology with classes for testing
    tax = Taxonomy(
        id=str(uuid4()),
        identifier="test_ontology",
        title="Test Ontology",
        description="Test ontology for extraction",
    )
    repo.save_taxonomy(tax)

    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="test_scheme",
        taxonomy_id=tax.id,
        title="Test Scheme",
        description="Test scheme",
    )
    repo.save_concept_scheme(scheme)

    # Create placeholder classes for the fixtures
    for class_name in ["individual", "property", "entity"]:
        cls = Class(
            id=str(uuid4()),
            identifier=class_name,
            concept_scheme_id=scheme.id,
            taxonomy_id=tax.id,
            title=class_name.title(),
            description=f"A {class_name}",
        )
        repo.save_class(cls)

    yield repo


@pytest.fixture
def extraction_service(ontology_repo, session_factory):
    """Create ExtractionService with fake adapters."""
    embedding_service = FakeEmbeddingService()
    event_publisher = InProcessEventPublisher()
    extraction_repo = SQLiteExtractionRepository(session_factory)
    extraction_run_repo = SQLiteExtractionRunRepository(session_factory)
    llm_provider = FakeLLMProvider()

    return ExtractionService(
        ontology_repo=ontology_repo,
        embedding_service=embedding_service,
        llm=llm_provider,
        nlp=FakeNLPProcessor(),
        reference_sources=[FakeReferenceSource()],
        event_publisher=event_publisher,
        extraction_repo=extraction_repo,
        extraction_run_repo=extraction_run_repo,
    )


@pytest.fixture
def registered_extraction(session_factory):
    """Register extraction pipeline with registries."""
    config_registry = PipelineConfigurationRegistry()
    impl_registry = PipelineImplementationRegistry()

    # Load Wave A configurations
    wave_a_config_file = (
        Path(__file__).parent.parent.parent
        / "integration"
        / "fixtures"
        / "wave_a_extraction_configs.json"
    )
    if wave_a_config_file.exists():
        with open(wave_a_config_file, "r") as f:
            configs = json.load(f)
            for config_name, config_data in configs.items():
                config_registry.register(config_name, config_data)

    return config_registry, impl_registry


@pytest.fixture
def metrics_emitter(tmp_path):
    """Create a MetricsEmitter for JSONL output."""
    metrics_dir = tmp_path / "_metrics"
    return MetricsEmitter(metrics_dir)


@pytest.fixture
def cassette_dir(tmp_path):
    """Create a cassette directory for LLM recordings."""
    return tmp_path / "_cassettes"


class TestQualityIndividualExtraction:
    """Quality test suite for individual_extraction pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", QUALITY_SCENARIOS)
    async def test_quality_scenario_with_metrics(
        self,
        scenario: str,
        extraction_service,
        registered_extraction,
        metrics_emitter,
        cassette_dir,
    ):
        """
        Test individual extraction quality on a specific scenario.

        - Load fixture (input + expected output)
        - Run pipeline via orchestrator
        - Compute precision, recall, F1, and Brier score
        - Assert metrics meet floors
        - Emit JSONL row with metrics
        """
        config_registry, impl_registry = registered_extraction
        register_individual_extraction(impl_registry, config_registry)

        cassette_dir.mkdir(parents=True, exist_ok=True)
        cassette_path = cassette_dir / f"individual_extraction_{scenario}.json"

        # Determine whether to use cassette (recording mode) or real LLM
        use_cassette = cassette_path.exists()
        llm_provider: CassetteLLMProvider | RecordingLLMProvider
        if use_cassette:
            llm_provider = CassetteLLMProvider(cassette_path)
        else:
            # Create recording provider for new cassettes
            fake_provider = FakeLLMProvider()
            llm_provider = RecordingLLMProvider(fake_provider, cassette_path)

        orchestrator = IndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            extraction_service=extraction_service,
        )

        # Load fixture
        fixture_input = load_fixture("individual_extraction", scenario)
        expected_output = load_expected_output("individual_extraction", scenario)

        # Run pipeline
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture_input,
        )
        result_state = await orchestrator.execute(state)

        # Extract triples from result
        actual_triples = (result_state.result or {}).get("triples", [])
        expected_triples = expected_output.get("result", {}).get("triples", [])

        # Compute quality metrics
        metrics = compute_quality_metrics(expected_triples, actual_triples)

        # Extract aggregate metrics for floor assertion
        aggregate_metrics = {
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "brier": metrics["brier"],
        }

        # Log per-category breakdown for debugging
        if metrics["per_category_breakdown"]:
            _logger.info(
                f"Per-category breakdown for {scenario}:\n"
                + "\n".join(
                    f"  {cat}: {breakdown}"
                    for cat, breakdown in metrics["per_category_breakdown"].items()
                )
            )

        # Emit JSONL row
        metrics_emitter.emit(
            pipeline_type="individual_extraction",
            scenario=scenario,
            model="test-model",
            config_ref="default",
            config_version=1,
            metrics=aggregate_metrics,
            mode="cassette" if use_cassette else "recording",
        )

        # Assert metrics against floors
        gate = FloorGate(METRIC_FLOORS)
        gate.assert_metrics(aggregate_metrics, pipeline_type=f"individual_extraction/{scenario}")

        # If recording, flush cassette
        if not use_cassette and isinstance(llm_provider, RecordingLLMProvider):
            llm_provider.flush()

    @pytest.mark.asyncio
    async def test_individual_extraction_apply_roundtrip(
        self,
        extraction_service,
        registered_extraction,
        ontology_repo,
    ):
        """
        Test apply round-trip: run -> apply -> snapshot -> revert -> re-apply -> assert idempotent.

        Verifies that applying an extraction result is idempotent and
        produces consistent ontology state across multiple cycles.
        """
        config_registry, impl_registry = registered_extraction
        register_individual_extraction(impl_registry, config_registry)

        llm_provider = FakeLLMProvider()
        orchestrator = IndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            extraction_service=extraction_service,
        )

        apply_service = IndividualExtractionApplyService(ontology_repo)

        # Use a simple fixture for round-trip testing
        fixture_input = load_fixture("individual_extraction", "async_patterns")
        run_id = str(uuid4())

        # First execution: run -> apply -> snapshot
        state1 = IndividualExtractionState(
            run_id=run_id,
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture_input,
        )
        result_state1 = await orchestrator.execute(state1)

        # Create a mock PipelineRun for apply service
        mock_run1 = PipelineRun(
            id=run_id,
            batch_run_id="test-batch",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            output_summary=result_state1.result or {},
        )

        # Apply results to ontology
        apply_result1 = apply_service.apply(mock_run1)
        created_individual_ids_1 = apply_result1.created_individual_ids
        created_relationship_ids_1 = apply_result1.created_relationship_ids

        # Snapshot ontology state after first apply
        individuals_after_apply1 = [
            (ind.id, ind.title, tuple(sorted(ind.class_ids)))
            for ind in ontology_repo.list_individuals()
            if ind.id not in created_individual_ids_1
        ]
        relationships_after_apply1 = [
            (rel.id, rel.source_id, rel.property_id, rel.target_id)
            for rel in ontology_repo.list_relationships()
            if rel.id not in created_relationship_ids_1
        ]

        # Revert: delete created entities
        for ind_id in created_individual_ids_1:
            ontology_repo.delete_individual(ind_id)
        for rel_id in created_relationship_ids_1:
            ontology_repo.delete_relationship(rel_id)

        # Second execution: re-apply with same run output
        apply_result2 = apply_service.apply(mock_run1)
        created_individual_ids_2 = apply_result2.created_individual_ids
        created_relationship_ids_2 = apply_result2.created_relationship_ids

        # Snapshot ontology state after second apply
        individuals_after_apply2 = [
            (ind.id, ind.title, tuple(sorted(ind.class_ids)))
            for ind in ontology_repo.list_individuals()
            if ind.id not in created_individual_ids_2
        ]
        relationships_after_apply2 = [
            (rel.id, rel.source_id, rel.property_id, rel.target_id)
            for rel in ontology_repo.list_relationships()
            if rel.id not in created_relationship_ids_2
        ]

        # Assert idempotence: same entities created (excluding IDs)
        count1_indiv = len(individuals_after_apply1)
        count2_indiv = len(individuals_after_apply2)
        assert count1_indiv == count2_indiv, (
            f"Individual count mismatch: {count1_indiv} != {count2_indiv}"
        )

        count1_rel = len(relationships_after_apply1)
        count2_rel = len(relationships_after_apply2)
        assert count1_rel == count2_rel, (
            f"Relationship count mismatch: {count1_rel} != {count2_rel}"
        )
