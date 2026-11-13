"""
Quality test suite for schema_extraction pipeline.

Verifies schema extraction quality using a curated fixture corpus with
hand-labeled expected classes, properties, and relationships.

Measures:
- Class label set Jaccard similarity
- Property Jaccard similarity
- Connection set overlap (subject_class, predicate, object_class)
- Brier score on confidence calibration

Labels are compared after normalize_label (case, spacing and punctuation
ignored), so "Event Loop" matches the fixture's "EventLoop".

Metric floors (enforced only for GATED_SCENARIOS):
- class_jaccard ≥ 0.60
- property_jaccard ≥ 0.50
- connection_overlap ≥ 0.40
- brier ≤ 0.25

Every scenario currently in the corpus is in DIAGNOSTIC_SCENARIOS: its metrics
are computed and emitted on every run but do not gate, and the test asserts
only that the pipeline completes and proposes classes. See that constant.

Structure metrics (#1570), emitted only for scenarios whose gold opts in (see
compute_structure_metrics): parent_accuracy, attribute_recall,
forbidden_class_count and sense_duplicate_count. A scenario whose input.json
lists `existing_classes` runs against a taxonomy seeded with them.
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
from adapters.llm.provider_router import LLMProviderRouter
from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import (
    SQLiteExtractionRunRepository,
)
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from config import get_settings
from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.ontology.services import OntologyService
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
from domain.pipelines.schema_extraction.apply_service import (
    SchemaExtractionApplyService,
    taxonomy_classes,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource
from tests.fixtures.pipeline_fixtures import (
    load_distractors,
    load_expected_output,
    load_fixture,
)
from tests.integration.pipelines._harness.cassettes import (
    RecordingLLMProvider,
)
from tests.integration.pipelines._harness.metrics import (
    brier_score,
    forbidden_label_hits,
    jaccard_similarity,
    parent_accuracy,
    precision_recall_f1,
    sense_base,
    sense_duplicate_count,
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

# These ten scenarios are the placeholder software-architecture corpus (generic
# concept prose graded against 6-7 hand-picked PascalCase labels). The same
# corpus was moved out of individual extraction's scored split for the same
# reason (see RELABELED_ARXIV_SCENARIOS and the placeholder note in
# tests/integration/pipelines/_harness/dataset_split.py): the pipeline extracts
# 15-21 valid classes per text, so Jaccard against a 6-7 label GT measures the
# GT's size more than extraction quality. With normalized labels the pipeline
# recalls 57-100% of the expected classes (2026-10-24 recording), but Jaccard
# sits at 0.2-0.4. They are kept as an always-reported diagnostic group: metrics
# are emitted every run (split="diagnostic") but never gate. A scenario moves to
# GATED_SCENARIOS once it has SME-authored ground truth sized to the text.
#
# Home-appliance documents (#1570): a heat pump maintenance page, a hand shower
# installation sheet (a three-page source) and a water heater care page. Their
# gold also says where each class belongs among the seeded `existing_classes`,
# which measurements are attributes, and which labels must not be classes (see
# compute_structure_metrics). Kept out of QUALITY_SCENARIOS, which the open_v1
# baseline and scripts/quality_loop.py also iterate. Diagnostic until the
# placement and sense-collapsing work lands and their gold is reviewed; with no
# cassette recorded yet, cassette mode skips them (quality_llm_provider_factory).
APPLIANCE_SCENARIOS = [
    "home_hand_shower_installation",
    "home_heat_pump_maintenance",
    "home_water_heater_care",
]
ALL_SCENARIOS = QUALITY_SCENARIOS + APPLIANCE_SCENARIOS

DIAGNOSTIC_SCENARIOS: frozenset[str] = frozenset(ALL_SCENARIOS)
GATED_SCENARIOS: frozenset[str] = frozenset(ALL_SCENARIOS) - DIAGNOSTIC_SCENARIOS

# Metric floors for schema extraction quality
METRIC_FLOORS = {
    "class_jaccard": 0.60,
    "property_jaccard": 0.50,
    "connection_overlap": 0.40,
    "brier": 0.25,
}


def normalize_label(label: str) -> str:
    """
    Comparison key for a class/property label: lower-cased, with spacing and
    punctuation removed, so "EventLoop", "Event Loop" and "event_loop" match.
    """
    return "".join(ch for ch in (label or "").lower() if ch.isalnum())


def extract_class_labels(classes: list[dict]) -> list[str]:
    """Extract normalized class labels from a class dict list."""
    return [normalize_label(c["label"]) for c in classes if c.get("label")]


def extract_property_labels(properties: list[dict]) -> list[str]:
    """Extract normalized property labels from a property dict list."""
    return [normalize_label(p["label"]) for p in properties if p.get("label")]


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
            tuples.append(
                (normalize_label(subject), normalize_label(predicate), normalize_label(obj))
            )

    return tuples


def _assert_quality(scenario: str, actual_output: dict, metrics: dict) -> None:
    """
    Gate a scenario's result.

    Gated scenarios must meet METRIC_FLOORS. Diagnostic scenarios are reported
    but not gated; they must still complete and propose at least one class, so a
    broken pipeline (crash, parse failure, empty output) still fails the build.
    """
    if scenario in GATED_SCENARIOS:
        FloorGate(METRIC_FLOORS).assert_metrics(
            metrics, pipeline_type=f"schema_extraction/{scenario}"
        )
        return
    result = actual_output.get("result") or {}
    classes = [c for c in result.get("candidates", []) if c.get("kind") == "class"]
    assert (
        actual_output.get("status") == "completed"
    ), f"schema_extraction/{scenario} did not complete: {actual_output.get('status')}"
    assert classes, f"schema_extraction/{scenario} proposed no classes"
    _logger.info(f"Diagnostic (non-gating) schema extraction metrics for {scenario}: {metrics}")


def extract_confidence(item: dict, default: float = 0.5) -> float:
    """Extract confidence value from item dict, default to 0.5 if missing."""
    return item.get("confidence", default)


# Where a class candidate may carry its placement and its attributes. The
# pipeline does not emit either yet (#1570 adds them); these name the shapes the
# structure metrics read, so the placement work only has to match one of them.
_PARENT_KEYS = ("proposed_parent", "parent", "parent_label")
_NESTED_ATTRIBUTE_KEYS = ("proposed_attributes", "attributes")
_ATTRIBUTE_KINDS = ("attribute", "attribute_definition")


def _candidate_parent(candidate: dict) -> str | None:
    """The label of the class a class candidate was placed under, or None."""
    for key in _PARENT_KEYS:
        value = candidate.get(key)
        if isinstance(value, dict):
            value = value.get("label")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _attribute_labels(candidates: list[dict]) -> list[str]:
    """
    Normalized labels of every attribute the run proposed: attribute candidates,
    and attributes listed on a class candidate.
    """
    labels = [c.get("label") for c in candidates if c.get("kind") in _ATTRIBUTE_KINDS]
    for candidate in candidates:
        if candidate.get("kind") != "class":
            continue
        for key in _NESTED_ATTRIBUTE_KEYS:
            for item in candidate.get(key) or []:
                labels.append(item.get("label") if isinstance(item, dict) else item)
    return [normalize_label(label) for label in labels if isinstance(label, str) and label]


def _expected_parent_labels(parent: str | list[str]) -> set[str]:
    """A gold class's accepted parents: one label or a list of them, normalized."""
    parents = [parent] if isinstance(parent, str) else parent
    return {normalize_label(p) for p in parents}


def compute_structure_metrics(
    expected_result: dict, actual_classes: list[dict], actual_candidates: list[dict]
) -> dict:
    """
    Schema structure metrics (#1570), for gold that opts in. `actual_classes`
    are the run's class candidates to score; `actual_candidates` all of its
    candidates, where attribute candidates are found.

    Gold opts in with a `forbidden_class_labels` list, or with `parent` or
    `attributes` on an expected class. Then:

    - parent_accuracy: of the expected classes with a `parent` that were
      extracted, the share placed under it (or under one of a list of parents)
    - attribute_recall: share of the expected classes' `attributes` the run
      proposed as attributes, by label (whatever class it attached them to)
    - forbidden_class_count: classes whose label, without a sense qualifier,
      is on the forbidden list (measurements, warranty and safety junk)
    - sense_duplicate_count: classes repeating a term another class names,
      such as "Cooling System (Functional Category)" beside "Cooling System"

    Returns {} for gold that does not opt in, so other scenarios' rows are unchanged.
    """
    expected_classes = expected_result.get("extracted_classes", [])
    forbidden = expected_result.get("forbidden_class_labels")
    with_parent = [c for c in expected_classes if c.get("parent")]
    expected_attributes = [
        normalize_label(attribute)
        for c in expected_classes
        for attribute in c.get("attributes") or []
    ]
    if forbidden is None and not with_parent and not expected_attributes:
        return {}

    metrics: dict = {}
    if with_parent:
        actual_parents: dict[str, str | None] = {}
        for candidate in actual_classes:
            parent = _candidate_parent(candidate)
            actual_parents.setdefault(
                normalize_label(candidate.get("label", "")),
                normalize_label(parent) if parent else None,
            )
        metrics["parent_accuracy"] = parent_accuracy(
            {
                normalize_label(c["label"]): _expected_parent_labels(c["parent"])
                for c in with_parent
            },
            actual_parents,
        )
    if expected_attributes:
        actual_attributes = _attribute_labels(actual_candidates)
        metrics["attribute_recall"] = precision_recall_f1(
            expected_attributes, actual_attributes
        ).recall
    labels = [c.get("label", "") for c in actual_classes if c.get("label")]
    hits = forbidden_label_hits(
        [normalize_label(label) for label in forbidden or []],
        [normalize_label(sense_base(label)) for label in labels],
    )
    if hits:
        _logger.info(f"Forbidden classes proposed: {hits}")
    metrics["forbidden_class_count"] = len(hits)
    metrics["sense_duplicate_count"] = sense_duplicate_count(labels)
    return metrics


def compute_quality_metrics(
    expected_output: dict,
    actual_output: dict,
    distractors: dict | None = None,
    existing_class_labels: list[str] | None = None,
) -> dict:
    """
    Compute quality metrics for schema extraction.

    Args:
        expected_output: Expected output from fixture
        actual_output: Actual output from pipeline
        distractors: Optional distractor dict with off-topic classes/properties
        existing_class_labels: Classes already in the run's taxonomy; class
            candidates that echo one are left out of every class score

    Returns dict with keys: class_jaccard, property_jaccard, connection_overlap,
    brier, and the compute_structure_metrics keys when the gold opts in.
    """
    distractors = distractors or {}
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
    existing_keys = {normalize_label(label) for label in existing_class_labels or []}
    actual_classes = [
        c
        for c in actual_candidates
        if c.get("kind") == "class" and normalize_label(c.get("label", "")) not in existing_keys
    ]
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
    # For non-expected classes (including distractors): predicted confidence should be ~0.0
    expected_class_set = set(expected_class_labels)
    distractor_class_labels = {
        normalize_label(c["label"]) for c in distractors.get("classes", []) if c.get("label")
    }
    actual_class_labels_set = set(actual_class_labels)
    brier_probs = []
    brier_labels = []

    for class_dict in actual_classes:
        label = normalize_label(class_dict.get("label", ""))
        confidence = extract_confidence(class_dict)
        is_expected = 1 if label in expected_class_set else 0
        brier_probs.append(confidence)
        brier_labels.append(is_expected)

    # Reward not extracting distractor classes
    for label in distractor_class_labels:
        if label not in actual_class_labels_set:
            brier_probs.append(0.0)
            brier_labels.append(0)

    brier = brier_score(brier_probs, brier_labels) if brier_probs else 0.0

    return {
        "class_jaccard": class_jaccard,
        "property_jaccard": property_jaccard,
        "connection_overlap": connection_overlap,
        "brier": brier,
        **compute_structure_metrics(expected_result, actual_classes, actual_candidates),
    }


def _pipeline_input(fixture_input: dict) -> dict:
    """
    The run input for a fixture: its text as the one document, and without
    `existing_classes` (those are seeded into the taxonomy, not passed in).
    """
    pipeline_input = {k: v for k, v in fixture_input.items() if k != "existing_classes"}
    if "text" in pipeline_input and "documents" not in pipeline_input:
        pipeline_input["documents"] = [pipeline_input.pop("text")]
    return pipeline_input


def _seed_existing_classes(taxonomy_id: str, labels: list[str]) -> SQLiteOntologyRepository:
    """An in-memory ontology whose taxonomy `taxonomy_id` holds a class per label."""
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    repo = SQLiteOntologyRepository(create_session_factory(engine))
    repo.save_taxonomy(
        Taxonomy(
            id=taxonomy_id,
            identifier="house",
            title="House",
            description="Existing classes for a schema extraction quality scenario",
        )
    )
    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="house_scheme",
        taxonomy_id=taxonomy_id,
        title="House Scheme",
        description="Existing classes for a schema extraction quality scenario",
    )
    repo.save_concept_scheme(scheme)
    for label in labels:
        repo.save_class(
            Class(
                id=str(uuid4()),
                identifier=normalize_label(label),
                concept_scheme_id=scheme.id,
                taxonomy_id=taxonomy_id,
                title=label,
                description=f"A {label.lower()}",
            )
        )
    return repo


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
        id="test-ontology-123",
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
def metrics_emitter():
    """Create a MetricsEmitter for JSONL output."""
    metrics_dir = Path(__file__).parent.parent / "fixtures" / "pipelines" / "_metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    return MetricsEmitter(metrics_dir)


@pytest.fixture
def cassette_dir():
    """Create a cassette directory for LLM recordings."""
    return Path(__file__).parent.parent / "fixtures" / "cassettes" / "schema_extraction"


class TestQualitySchemaExtraction:
    """Quality test suite for schema_extraction pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", ALL_SCENARIOS)
    async def test_quality_scenario_with_metrics(
        self,
        scenario: str,
        extraction_service,
        registered_schema_extraction,
        metrics_emitter,
        cassette_dir,
        quality_llm_provider_factory,
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

        # Use quality_llm_provider_factory to get appropriate provider
        quality_provider = quality_llm_provider_factory(
            scenario, cassette_dir, "schema_extraction_"
        )

        # If it's a recording provider, we need to flush it after execution
        is_recording = isinstance(quality_provider, RecordingLLMProvider)

        # Load fixture
        fixture_input = load_fixture("schema_extraction", scenario)
        expected_output = load_expected_output("schema_extraction", scenario)
        distractors = load_distractors("schema_extraction", scenario) or {}
        existing_classes = fixture_input.get("existing_classes") or []
        pipeline_input = _pipeline_input(fixture_input)

        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=quality_provider,
            ontology_repo=(
                _seed_existing_classes(fixture_input["ontology_id"], existing_classes)
                if existing_classes
                else None
            ),
        )

        # Run pipeline
        state = SchemaExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=pipeline_input,
        )
        result_state = await orchestrator.execute(state)

        # Flush recording provider if needed
        if is_recording:
            quality_provider.flush()

        # Build actual output dict
        actual_output = {
            "status": result_state.current_status.value,
            "result": result_state.result or {},
        }

        # Compute quality metrics
        metrics = compute_quality_metrics(
            expected_output, actual_output, distractors, existing_classes
        )

        # Log metrics for debugging
        _logger.info(f"Schema extraction metrics for {scenario}: {metrics}")

        # Emit JSONL row
        metrics_emitter.emit(
            pipeline_type="schema_extraction",
            fixture_id=scenario,
            model="test-model",
            config_ref="default",
            config_version=1,
            metrics=metrics,
            mode="cassette" if scenario in GATED_SCENARIOS else "cassette-diagnostic",
        )

        _assert_quality(scenario, actual_output, metrics)

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

        apply_service = SchemaExtractionApplyService(
            OntologyService(
                repository=ontology_repo,
                embedding_service=FakeEmbeddingService(),
                event_publisher=FakeEventPublisher(),
            ),
            ontology_repo,
        )

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
        apply_result1 = apply_service.apply(mock_run, taxonomy_id, concept_scheme_id)

        # Snapshot ontology state after first apply
        classes_after_apply1 = [
            (cls.id, cls.title, cls.identifier) for cls in ontology_repo.list_classes()
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
        apply_service.apply(mock_run, taxonomy_id, concept_scheme_id)

        # Snapshot ontology state after second apply
        classes_after_apply2 = [
            (cls.id, cls.title, cls.identifier) for cls in ontology_repo.list_classes()
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
        assert (
            count1_class == count2_class
        ), f"Class count mismatch: {count1_class} != {count2_class}"

        count1_prop = len(properties_after_apply1)
        count2_prop = len(properties_after_apply2)
        assert (
            count1_prop == count2_prop
        ), f"Property count mismatch: {count1_prop} != {count2_prop}"

        count1_rel = len(relationships_after_apply1)
        count2_rel = len(relationships_after_apply2)
        assert (
            count1_rel == count2_rel
        ), f"Relationship count mismatch: {count1_rel} != {count2_rel}"

    @pytest.mark.real_llm
    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", ALL_SCENARIOS)
    async def test_live_quality_scenario(
        self,
        scenario: str,
        ontology_repo,
        registered_schema_extraction,
        metrics_emitter,
        cassette_dir,
    ):
        """
        Live test for schema extraction quality with real LLM provider.

        - Load fixture (input + expected output)
        - Run pipeline with real LLM provider from config
        - Record cassette for future deterministic testing
        - Compute class Jaccard, property Jaccard, and connection overlap
        - Assert metrics meet floors
        - Emit JSONL row with metrics

        This test is decorated with @pytest.mark.real_llm and only runs when
        explicitly enabled (pytest -m real_llm). Requires LLM provider configuration.
        """
        settings = get_settings()
        llm_config = settings.llm

        if (
            not llm_config.openai_api_key
            and not llm_config.anthropic_api_key
            and not llm_config.openrouter_api_key
        ):
            pytest.skip(
                "No LLM provider configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, "
                "or OPENROUTER_API_KEY environment variable."
            )

        config_registry, impl_registry = registered_schema_extraction
        register_schema_extraction(impl_registry, config_registry)

        cassette_dir.mkdir(parents=True, exist_ok=True)
        cassette_path = cassette_dir / f"schema_extraction_{scenario}.json"

        try:
            llm_provider = LLMProviderRouter(
                openai_api_key=llm_config.openai_api_key,
                anthropic_api_key=llm_config.anthropic_api_key,
                openrouter_api_key=llm_config.openrouter_api_key,
            )
        except ValueError as e:
            pytest.skip(f"LLM provider initialization failed: {e}")

        # Load fixture
        fixture_input = load_fixture("schema_extraction", scenario)
        expected_output = load_expected_output("schema_extraction", scenario)
        distractors = load_distractors("schema_extraction", scenario) or {}
        existing_classes = fixture_input.get("existing_classes") or []
        pipeline_input = _pipeline_input(fixture_input)

        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=llm_provider,
            ontology_repo=(
                _seed_existing_classes(fixture_input["ontology_id"], existing_classes)
                if existing_classes
                else ontology_repo
            ),
        )

        # Run pipeline with real LLM
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

        # Record cassette for future use (optional - can be stored in VCS)
        if not cassette_path.exists():
            cassette_data = {
                "scenario": scenario,
                "input": pipeline_input,
                "expected": expected_output,
                "actual": actual_output,
            }
            cassette_path.write_text(json.dumps(cassette_data, indent=2))

        # Compute quality metrics
        metrics = compute_quality_metrics(
            expected_output, actual_output, distractors, existing_classes
        )

        # Log metrics for debugging
        _logger.info(f"Schema extraction metrics for {scenario}: {metrics}")

        # Emit JSONL row
        metrics_emitter.emit(
            pipeline_type="schema_extraction",
            fixture_id=scenario,
            model="live",
            config_ref="default",
            config_version=1,
            metrics=metrics,
            mode="live" if scenario in GATED_SCENARIOS else "live-diagnostic",
        )

        _assert_quality(scenario, actual_output, metrics)


class TestQualityHarness:
    """The scoring rules themselves: label normalization and diagnostic gating."""

    def test_normalize_label_ignores_case_spacing_and_punctuation(self):
        assert normalize_label("EventLoop") == normalize_label("Event Loop")
        assert normalize_label("event_loop") == normalize_label("Event-Loop") == "eventloop"
        assert normalize_label("Factory") != normalize_label("Factory Pattern")

    def test_metrics_match_across_label_formats(self):
        expected = {
            "result": {
                "extracted_classes": [{"label": "EventLoop"}, {"label": "Coroutine"}],
                "extracted_properties": [{"label": "awaits"}],
                "extracted_relationships": [
                    {"subject_class": "EventLoop", "predicate": "runs", "object_class": "Coroutine"}
                ],
            }
        }
        actual = {
            "result": {
                "candidates": [
                    {"kind": "class", "label": "Event Loop", "confidence": 0.9},
                    {"kind": "class", "label": "coroutine", "confidence": 0.9},
                    {"kind": "property_definition", "label": "Awaits", "confidence": 0.8},
                ],
                "connections": [
                    {"subject_ref": "Event Loop", "predicate": "Runs", "object_ref": "Coroutine"}
                ],
            }
        }
        metrics = compute_quality_metrics(expected, actual)
        assert metrics["class_jaccard"] == 1.0
        assert metrics["property_jaccard"] == 1.0
        assert metrics["connection_overlap"] == 1.0

    def test_diagnostic_scenarios_report_without_gating(self):
        scenario = next(iter(DIAGNOSTIC_SCENARIOS))
        output = {
            "status": "completed",
            "result": {"candidates": [{"kind": "class", "label": "X", "confidence": 0.5}]},
        }
        low = {
            "class_jaccard": 0.0,
            "property_jaccard": 0.0,
            "connection_overlap": 0.0,
            "brier": 1.0,
        }
        _assert_quality(scenario, output, low)  # does not raise

    def test_diagnostic_scenarios_still_fail_on_empty_or_failed_runs(self):
        scenario = next(iter(DIAGNOSTIC_SCENARIOS))
        low = {
            "class_jaccard": 0.0,
            "property_jaccard": 0.0,
            "connection_overlap": 0.0,
            "brier": 1.0,
        }
        with pytest.raises(AssertionError, match="proposed no classes"):
            _assert_quality(scenario, {"status": "completed", "result": {"candidates": []}}, low)
        with pytest.raises(AssertionError, match="did not complete"):
            _assert_quality(scenario, {"status": "failed", "result": {}}, low)

    def test_appliance_scenarios_are_diagnostic_and_have_fixtures(self):
        for scenario in APPLIANCE_SCENARIOS:
            assert scenario in DIAGNOSTIC_SCENARIOS and scenario not in GATED_SCENARIOS
            fixture_input = load_fixture("schema_extraction", scenario)
            expected = load_expected_output("schema_extraction", scenario)["result"]
            assert fixture_input["existing_classes"] and fixture_input["ontology_id"]
            assert expected["forbidden_class_labels"]
            # No expected class is also forbidden, and none repeats a term
            labels = [c["label"] for c in expected["extracted_classes"]]
            forbidden = {normalize_label(label) for label in expected["forbidden_class_labels"]}
            assert not {normalize_label(label) for label in labels} & forbidden, scenario
            assert sense_duplicate_count(labels) == 0, scenario
            # Every expected parent is a seeded class or another expected class
            known = {normalize_label(label) for label in labels + fixture_input["existing_classes"]}
            for c in expected["extracted_classes"]:
                if c.get("parent"):
                    assert _expected_parent_labels(c["parent"]) <= known, (scenario, c)

    def test_structure_metrics_only_for_gold_that_opts_in(self):
        expected = {"result": {"extracted_classes": [{"label": "EventLoop"}]}}
        actual = {"result": {"candidates": [{"kind": "class", "label": "Event Loop"}]}}
        assert set(compute_quality_metrics(expected, actual)) == {
            "class_jaccard",
            "property_jaccard",
            "connection_overlap",
            "brier",
        }

    def test_structure_metrics(self):
        expected = {
            "result": {
                "extracted_classes": [
                    {"label": "Heat Pump", "parent": "Appliance", "attributes": ["Voltage"]},
                    {"label": "Air Filter", "parent": ["Supply", "Part"]},
                    {"label": "Thermostat", "attributes": ["Setpoint"]},
                ],
                "forbidden_class_labels": ["Voltage", "Indoor Humidity"],
            }
        }
        actual = {
            "result": {
                "candidates": [
                    {"kind": "class", "label": "Appliance"},
                    {"kind": "class", "label": "Heat Pump", "proposed_parent": "Appliance"},
                    {"kind": "class", "label": "Heat Pump (Device)"},
                    {"kind": "class", "label": "Air Filter", "parent": None},
                    {"kind": "class", "label": "Indoor Humidity (Measurement)"},
                    {"kind": "class", "label": "Thermostat", "attributes": [{"label": "Setpoint"}]},
                    {"kind": "attribute", "label": "voltage"},
                ],
            }
        }
        metrics = compute_quality_metrics(expected, actual, existing_class_labels=["Appliance"])
        assert metrics["parent_accuracy"] == 0.5  # Heat Pump placed, Air Filter top-level
        assert metrics["attribute_recall"] == 1.0  # a kind=attribute and a nested one
        assert metrics["forbidden_class_count"] == 1  # Indoor Humidity, qualifier ignored
        assert metrics["sense_duplicate_count"] == 1  # Heat Pump (Device)
        # The echoed existing class "Appliance" is not counted as an extra class
        assert metrics["class_jaccard"] == round(3 / 5, 4)

    def test_existing_classes_are_seeded_into_the_run_taxonomy(self):
        repo = _seed_existing_classes("house-ontology", ["Appliance", "Supply"])
        assert {c.title for c in taxonomy_classes(repo, "house-ontology")} == {
            "Appliance",
            "Supply",
        }

    def test_pipeline_input_leaves_out_existing_classes(self):
        pipeline_input = _pipeline_input(
            {"text": "Some text.", "ontology_id": "t", "existing_classes": ["Appliance"]}
        )
        assert pipeline_input == {"documents": ["Some text."], "ontology_id": "t"}
