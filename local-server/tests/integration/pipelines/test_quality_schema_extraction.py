"""
Quality test suite for schema_extraction pipeline.

Verifies schema extraction quality using a curated fixture corpus with
hand-labeled expected classes, properties, and relationships.

Measures:
- Class label set Jaccard similarity
- Property Jaccard similarity
- Connection set overlap (subject_class, predicate, object_class)
- Brier score on confidence calibration

Metric floors:
- class_jaccard ≥ 0.60
- property_jaccard ≥ 0.50
- connection_overlap ≥ 0.40
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
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
    register_schema_extraction,
)
from domain.pipelines.schema_extraction.apply_service import SchemaExtractionApplyService
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
    jaccard_similarity,
)
from tests.integration.pipelines._harness.report import FloorGate, MetricsEmitter

_logger = logging.getLogger(__name__)

# Quality fixture scenarios for schema extraction
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

# Metric floors for schema extraction quality
METRIC_FLOORS = {
    "class_jaccard": 0.60,
    "property_jaccard": 0.50,
    "connection_overlap": 0.40,
    "brier": 0.25,
}


def extract_class_labels(classes: list[dict]) -> list[str]:
    """Extract class label strings from class dict list."""
    return [c.get("label", "") for c in classes if c.get("label")]


def extract_property_labels(properties: list[dict]) -> list[str]:
    """Extract property label strings from property dict list."""
    return [p.get("label", "") for p in properties if p.get("label")]


def extract_connection_tuples(relationships: list[dict]) -> list[tuple]:
    """
    Extract (subject_class, predicate, object_class) tuples from relationships.

    Handles both formats:
    - Expected (fixture): subject_class, predicate, object_class
    - Actual (orchestrator): subject_ref, predicate, object_ref

    Returns list of tuples for comparison.
    """
    tuples = []
    for rel in relationships:
        # Try fixture format first
        subject = rel.get("subject_class") or rel.get("subject_ref", "")
        predicate = rel.get("predicate", "")
        obj = rel.get("object_class") or rel.get("object_ref", "")

        if subject and predicate and obj:
            tuples.append((subject, predicate, obj))

    return tuples


def extract_confidence(item: dict, default: float = 0.5) -> float:
    """Extract confidence value from item dict, default to 0.5 if missing."""
    return item.get("confidence", default)


def compute_quality_metrics(
    expected_output: dict,
    actual_output: dict,
) -> dict:
    """
    Compute quality metrics for schema extraction.

    Returns dict with keys: class_jaccard, property_jaccard, connection_overlap, brier.
    """
    expected_result = expected_output.get("result", {})
    actual_result = actual_output.get("result", {})

    # Handle expected output format (from fixtures)
    expected_classes = expected_result.get("extracted_classes", [])
    expected_properties = expected_result.get("extracted_properties", [])
    expected_relationships = expected_result.get("extracted_relationships", [])

    # Handle actual output format (from orchestrator)
    # Orchestrator produces "candidates" (classes and properties) and "connections"
    actual_candidates = actual_result.get("candidates", [])
    actual_connections = actual_result.get("connections", [])

    # Split candidates into classes and properties
    actual_classes = [c for c in actual_candidates if c.get("kind") == "class"]
    actual_properties = [c for c in actual_candidates if c.get("kind") == "property_definition"]

    # Convert connections to relationship format for comparison
    actual_relationships = actual_connections

    # Class Jaccard: set overlap of class labels
    expected_class_labels = extract_class_labels(expected_classes)
    actual_class_labels = extract_class_labels(actual_classes)
    class_jaccard = jaccard_similarity(expected_class_labels, actual_class_labels)

    # Property Jaccard: set overlap of property labels
    expected_property_labels = extract_property_labels(expected_properties)
    actual_property_labels = extract_property_labels(actual_properties)
    property_jaccard = jaccard_similarity(expected_property_labels, actual_property_labels)

    # Connection set overlap: F1 on (subject, predicate, object) tuples
    expected_connections = set(extract_connection_tuples(expected_relationships))
    actual_connections = set(extract_connection_tuples(actual_relationships))

    if actual_connections:
        overlap = len(expected_connections & actual_connections) / len(
            expected_connections | actual_connections
        )
    else:
        overlap = 1.0 if not expected_connections else 0.0
    connection_overlap = round(overlap, 4)

    # Brier score on confidence calibration
    # For expected classes: predicted confidence should be ~1.0
    # For unexpected classes: predicted confidence should be ~0.0
    expected_class_set = set(expected_class_labels)
    brier_probs = []
    brier_labels = []

    for class_dict in actual_classes:
        label = class_dict.get("label", "")
        confidence = extract_confidence(class_dict)
        is_expected = 1 if label in expected_class_set else 0
        brier_probs.append(confidence)
        brier_labels.append(is_expected)

    brier = brier_score(brier_probs, brier_labels) if brier_probs else 0.0

    return {
        "class_jaccard": class_jaccard,
        "property_jaccard": property_jaccard,
        "connection_overlap": connection_overlap,
        "brier": brier,
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

    # Create placeholder classes
    for class_name in ["Entity", "Concept", "Relationship"]:
        cls = Class(
            id=str(uuid4()),
            identifier=class_name.lower(),
            concept_scheme_id=scheme.id,
            taxonomy_id=tax.id,
            title=class_name,
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
def registered_schema_extraction(session_factory):
    """Register schema extraction pipeline with registries."""
    config_registry = PipelineConfigurationRegistry()
    impl_registry = PipelineImplementationRegistry()

    # Load configuration if available
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


class TestQualitySchemaExtraction:
    """Quality test suite for schema_extraction pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", QUALITY_SCENARIOS)
    async def test_quality_scenario_with_metrics(
        self,
        scenario: str,
        extraction_service,
        registered_schema_extraction,
        metrics_emitter,
        cassette_dir,
    ):
        """
        Test schema extraction quality on a specific scenario.

        - Load fixture (input + expected output)
        - Run pipeline via orchestrator
        - Compute class Jaccard, property Jaccard, connection overlap, and Brier
        - Assert metrics meet floors
        - Emit JSONL row with metrics
        """
        config_registry, impl_registry = registered_schema_extraction
        register_schema_extraction(impl_registry, config_registry)

        cassette_dir.mkdir(parents=True, exist_ok=True)
        cassette_path = cassette_dir / f"schema_extraction_{scenario}.json"

        # Determine whether to use cassette (recording mode) or real LLM
        use_cassette = cassette_path.exists()
        llm_provider: CassetteLLMProvider | RecordingLLMProvider
        if use_cassette:
            llm_provider = CassetteLLMProvider(cassette_path)
        else:
            # Create recording provider for new cassettes
            fake_provider = FakeLLMProvider()
            llm_provider = RecordingLLMProvider(fake_provider, cassette_path)

        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=llm_provider,
            ontology_repo=None,
        )

        # Load fixture
        fixture_input = load_fixture("schema_extraction", scenario)
        expected_output = load_expected_output("schema_extraction", scenario)

        # Convert input format: wrap text in documents array if needed
        pipeline_input = fixture_input.copy()
        if "text" in pipeline_input and "documents" not in pipeline_input:
            pipeline_input["documents"] = [pipeline_input.pop("text")]

        # Run pipeline
        state = SchemaExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=pipeline_input,
        )
        result_state = await orchestrator.execute(state)

        # Build actual output dict
        actual_output = {
            "status": result_state.current_status.value,
            "result": result_state.result or {},
        }

        # Compute quality metrics
        metrics = compute_quality_metrics(expected_output, actual_output)

        # Log metrics for debugging
        _logger.info(f"Schema extraction metrics for {scenario}: {metrics}")

        # Emit JSONL row
        metrics_emitter.emit(
            pipeline_type="schema_extraction",
            scenario=scenario,
            model="test-model",
            config_ref="default",
            config_version=1,
            metrics=metrics,
            mode="cassette" if use_cassette else "recording",
        )

        # Assert metrics against floors
        gate = FloorGate(METRIC_FLOORS)
        gate.assert_metrics(metrics, pipeline_type=f"schema_extraction/{scenario}")

        # If recording, flush cassette
        if not use_cassette and isinstance(llm_provider, RecordingLLMProvider):
            llm_provider.flush()

    @pytest.mark.asyncio
    async def test_schema_extraction_apply_roundtrip(
        self,
        ontology_repo,
        registered_schema_extraction,
    ):
        """
        Test apply round-trip: run -> apply -> snapshot -> revert -> re-apply -> assert idempotent.

        Verifies that applying a schema extraction result is idempotent and
        produces consistent schema state across multiple cycles.
        """
        config_registry, impl_registry = registered_schema_extraction
        register_schema_extraction(impl_registry, config_registry)

        llm_provider = FakeLLMProvider()
        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=llm_provider,
            ontology_repo=None,
        )

        apply_service = SchemaExtractionApplyService(ontology_repo)

        # Use a simple fixture for round-trip testing
        fixture_input = load_fixture("schema_extraction", "async_patterns")

        # Convert input format: wrap text in documents array if needed
        pipeline_input = fixture_input.copy()
        if "text" in pipeline_input and "documents" not in pipeline_input:
            pipeline_input["documents"] = [pipeline_input.pop("text")]

        # Get concept scheme for apply service
        schemes = ontology_repo.list_concept_schemes()
        concept_scheme_id = schemes[0].id if schemes else str(uuid4())

        taxonomies = ontology_repo.list_taxonomies()
        taxonomy_id = taxonomies[0].id if taxonomies else str(uuid4())

        # First execution: run -> apply -> snapshot
        run_id = str(uuid4())
        state1 = SchemaExtractionState(
            run_id=run_id,
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=pipeline_input,
        )
        result_state1 = await orchestrator.execute(state1)

        # Create a mock PipelineRun for apply service
        mock_run = PipelineRun(
            id=run_id,
            batch_run_id="test-batch",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            output_summary=result_state1.result or {},
        )

        # Apply results to ontology
        apply_result1 = apply_service.apply(mock_run, concept_scheme_id, taxonomy_id)

        # Snapshot ontology state after first apply
        classes_after_apply1 = [
            (cls.id, cls.title, cls.identifier)
            for cls in ontology_repo.list_classes()
        ]
        properties_after_apply1 = [
            (prop.id, prop.label, prop.identifier)
            for prop in ontology_repo.list_property_definitions()
        ]
        relationships_after_apply1 = [
            (rel.id, rel.source_id, rel.property_id, rel.target_id)
            for rel in ontology_repo.list_relationships()
        ]

        # Revert: delete created classes and properties
        if apply_result1.created_class_ids:
            for cls_id in apply_result1.created_class_ids:
                ontology_repo.delete_class(cls_id)
        if apply_result1.created_property_definition_ids:
            for prop_id in apply_result1.created_property_definition_ids:
                ontology_repo.delete_property_definition(prop_id)
        if apply_result1.created_relationship_ids:
            for rel_id in apply_result1.created_relationship_ids:
                ontology_repo.delete_relationship(rel_id)

        # Second execution: re-apply with same run output
        apply_service.apply(mock_run, concept_scheme_id, taxonomy_id)

        # Snapshot ontology state after second apply
        classes_after_apply2 = [
            (cls.id, cls.title, cls.identifier)
            for cls in ontology_repo.list_classes()
        ]
        properties_after_apply2 = [
            (prop.id, prop.label, prop.identifier)
            for prop in ontology_repo.list_property_definitions()
        ]
        relationships_after_apply2 = [
            (rel.id, rel.source_id, rel.property_id, rel.target_id)
            for rel in ontology_repo.list_relationships()
        ]

        # Assert idempotence: same entities created (excluding IDs)
        count1_class = len(classes_after_apply1)
        count2_class = len(classes_after_apply2)
        assert count1_class == count2_class, (
            f"Class count mismatch: {count1_class} != {count2_class}"
        )

        count1_prop = len(properties_after_apply1)
        count2_prop = len(properties_after_apply2)
        assert count1_prop == count2_prop, (
            f"Property count mismatch: {count1_prop} != {count2_prop}"
        )

        count1_rel = len(relationships_after_apply1)
        count2_rel = len(relationships_after_apply2)
        assert count1_rel == count2_rel, (
            f"Relationship count mismatch: {count1_rel} != {count2_rel}"
        )
