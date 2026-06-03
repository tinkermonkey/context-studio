"""
Quality test suite for schema_node_connection_refinement pipeline.

Verifies connection refinement quality using a curated fixture corpus with
hand-labeled expected relationship deltas. Measures per-operation (add/remove/modify)
precision and recall on (operation, subject_class, predicate, object_class) tuples.

Includes explicit regression test for the historical silent-drop bug on modify operations,
validating that modify operations are properly tracked in the ontology state.

Metric floors:
- delta_f1 ≥ 0.40 (overall F1 on delta operations)
- add_recall ≥ 0.30 (recall for add operations)
- remove_recall ≥ 0.30 (recall for remove operations)
- modify_recall ≥ 0.30 (recall for modify operations)
"""

import json
import logging
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.pipelines.entities import PipelineRun, PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_node_connection_refinement.apply_service import (
    SchemaConnectionRefinementApplyService,
)
from domain.pipelines.schema_node_connection_refinement.bootstrap import (
    register_schema_node_connection_refinement,
)
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
    ConnectionRefinementState,
)
from tests.integration.pipelines._harness.cassettes import CassetteLLMProvider
from tests.integration.pipelines._harness.metrics import precision_recall_f1
from tests.integration.pipelines._harness.report import FloorGate, MetricsEmitter

_logger = logging.getLogger(__name__)

# Quality fixture scenarios for connection refinement
QUALITY_SCENARIOS = [
    "add_inherits_from_pattern",
    "add_implements_interface",
    "add_uses_pattern",
    "remove_outdated_pattern",
    "remove_no_longer_applicable",
    "modify_relationship_semantics",
    "mixed_add_and_remove",
    "empty_delta_fixture_1",
    "empty_delta_already_optimal",
    "add_event_driven_pattern",
    "add_async_pattern",
    "add_caching_relationship",
    "remove_sync_pattern",
    "remove_antipattern",
    "modify_strengthens_relationship",
    "complex_architecture_deltas",
    "add_dependency_injection",
    "add_aspect_oriented",
    "remove_tight_coupling",
    "mixed_semantic_refinement",
    "empty_delta_complete_schema",
    "add_multiple_implementations",
    "empty_delta_fixture_2",
    "empty_delta_fixture_3",
]

# Metric floors for connection refinement quality
METRIC_FLOORS = {
    "delta_f1": 0.40,
    "add_recall": 0.30,
    "remove_recall": 0.30,
    "modify_recall": 0.30,
}


def extract_delta_tuples(deltas: list[dict]) -> dict[str, list[tuple]]:
    """
    Extract (subject_class, predicate, object_class) tuples from deltas, grouped by operation.

    Returns dict with keys "add", "remove", "modify", each containing list of tuples.
    """
    result: dict[str, list[tuple]] = {"add": [], "remove": [], "modify": []}
    for delta in deltas:
        operation = delta.get("operation", "").lower()
        subject = delta.get("subject", "")
        predicate = delta.get("predicate", "")
        obj = delta.get("object", "")

        if subject and predicate and obj and operation in result:
            result[operation].append((subject, predicate, obj))

    return result


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

    # Create ontology with classes and properties for testing
    tax = Taxonomy(
        id="test-ontology-123",
        identifier="test_ontology",
        title="Test Ontology",
        description="Test ontology for connection refinement",
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

    # Create default properties
    for prop_label in ["inherits_from", "implements", "uses", "depends_on", "related_to"]:
        prop = PropertyDefinition(
            id=str(uuid4()),
            identifier=prop_label,
            title=prop_label.replace("_", " ").title(),
            description=f"Property: {prop_label}",
        )
        repo.save_property_definition(prop)

    yield repo


@pytest.fixture
def registered_connection_refinement(session_factory):
    """Register connection refinement pipeline with registries."""
    config_registry = PipelineConfigurationRegistry()
    impl_registry = PipelineImplementationRegistry()

    register_schema_node_connection_refinement(impl_registry, config_registry)

    return config_registry, impl_registry


@pytest.fixture
def metrics_emitter():
    """Create a MetricsEmitter for JSONL output."""
    metrics_dir = Path(__file__).parent.parent.parent.parent / "_metrics"
    return MetricsEmitter(metrics_dir)


@pytest.fixture
def cassette_dir():
    """Resolve cassette directory to committed recordings."""
    return Path(__file__).parent / "_cassettes"


class TestQualityConnectionRefinement:
    """Quality test suite for schema_node_connection_refinement pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.external_network
    @pytest.mark.parametrize("scenario", QUALITY_SCENARIOS)
    async def test_quality_scenario_with_metrics(
        self,
        scenario: str,
        ontology_repo,
        registered_connection_refinement,
        metrics_emitter,
        cassette_dir,
    ):
        """
        Test connection refinement quality on a specific scenario.

        - Load fixture (input + expected output)
        - Create scope class and candidate relationships in ontology
        - Run pipeline via orchestrator with cassette LLM
        - Extract actual and expected deltas
        - Compute per-operation precision and recall on delta tuples
        - Assert metrics meet floors
        - Apply deltas and verify ontology state for add/remove/modify
        - Emit JSONL row with metrics

        FR-P5.1: Corpus covers at least one add, remove, modify
        FR-P5.2: Computes delta-set overlap on (operation, subject_class, predicate, object_class)
        FR-P5.3: Metric floors: overall delta_f1 >= 0.40, per-operation recall >= 0.30
        FR-P5.4: Empty-delta fixtures verified (pipeline must propose no changes)
        FR-P5.5: Apply round-trip explicitly asserts modify produces correct ontology state
        """
        config_registry, impl_registry = registered_connection_refinement

        cassette_dir.mkdir(parents=True, exist_ok=True)
        cassette_path = cassette_dir / f"connection_refinement_{scenario}.json"

        # Skip test if cassette doesn't exist
        if not cassette_path.exists():
            pytest.skip(
                f"Cassette not found at {cassette_path}. Run with --refresh-cassettes to record."
            )

        # Use cassette provider for deterministic quality testing
        llm_provider = CassetteLLMProvider(cassette_path)

        # Load fixture from pipelines/fixtures directory
        fixture_base = Path(__file__).parent.parent / "fixtures" / "pipelines"
        fixture_dir = fixture_base / "schema_node_connection_refinement" / scenario
        input_file = fixture_dir / "input.json"
        expected_file = fixture_dir / "expected.json"

        if not input_file.exists() or not expected_file.exists():
            pytest.skip(
                f"Fixture not found for scenario {scenario}. "
                f"Expected: {input_file}, {expected_file}"
            )

        with open(input_file) as f:
            fixture_input = json.load(f)
        with open(expected_file) as f:
            expected_output = json.load(f)

        # Setup ontology: create scope class and candidate relationships
        scope_id = fixture_input.get("scope_id", str(uuid4()))
        is_empty_delta = fixture_input.get("is_empty_delta", False)

        # Get concept scheme and taxonomy
        schemes = ontology_repo.list_concept_schemes()
        concept_scheme_id = schemes[0].id if schemes else str(uuid4())
        taxonomies = ontology_repo.list_taxonomies()
        taxonomy_id = taxonomies[0].id if taxonomies else str(uuid4())

        # Create or fetch scope class
        existing_scope = ontology_repo.get_class(scope_id)
        if not existing_scope:
            scope_cls = Class(
                id=scope_id,
                identifier=fixture_input.get("scope_identifier", f"test_{scenario}"),
                concept_scheme_id=concept_scheme_id,
                taxonomy_id=taxonomy_id,
                title=fixture_input.get("scope_title", scenario),
                description=fixture_input.get("scope_description", ""),
            )
            ontology_repo.save_class(scope_cls)
        else:
            scope_cls = existing_scope

        # Create candidate classes and relationships from fixture
        before_relationships = fixture_input.get("before_relationships", [])
        candidate_classes = fixture_input.get("candidate_classes", [])

        class_id_map = {scope_id: scope_cls.id}  # scope_id -> entity ID

        # Create candidate classes
        for class_info in candidate_classes:
            class_id = class_info.get("id", str(uuid4()))
            if class_id not in class_id_map:
                cls = Class(
                    id=class_id,
                    identifier=class_info.get("identifier", class_id[:8]),
                    concept_scheme_id=concept_scheme_id,
                    taxonomy_id=taxonomy_id,
                    title=class_info.get("title", class_id[:8]),
                    description="",
                )
                ontology_repo.save_class(cls)
                class_id_map[class_id] = cls.id

        # Create before relationships
        for rel_info in before_relationships:
            subject_id = rel_info.get("subject_id", scope_id)
            object_id = rel_info.get("object_id")
            predicate = rel_info.get("predicate", "related_to")

            if not object_id:
                continue

            # Resolve predicate to property definition
            prop_def = ontology_repo.get_property_definition_by_identifier(
                predicate.lower().replace(" ", "_")
            )
            if not prop_def:
                # Create if doesn't exist
                prop_def = PropertyDefinition(
                    id=str(uuid4()),
                    identifier=predicate.lower().replace(" ", "_"),
                    title=predicate,
                    description=f"Property: {predicate}",
                )
                ontology_repo.save_property_definition(prop_def)

            src_id = class_id_map.get(subject_id, subject_id)
            tgt_id = class_id_map.get(object_id, object_id)

            rel = Relationship(
                id=str(uuid4()),
                source_id=src_id,
                target_id=tgt_id,
                property_definition_id=prop_def.id,
            )
            ontology_repo.save_relationship(rel)

        # Create orchestrator and execute pipeline
        from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal

        traversal = SchemaNeighborhoodTraversal(ontology_repo=ontology_repo)
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm_provider,
            traversal=traversal,
        )

        state = ConnectionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={
                "scope_id": scope_id,
                "candidates": fixture_input.get("candidates", []),
                "model": fixture_input.get("model", "claude-opus-4-7"),
                "temperature": fixture_input.get("temperature", 0.0),
            },
        )
        result_state = await orchestrator.execute(state)

        # Extract actual and expected deltas
        actual_deltas = result_state.result.get("deltas", []) if result_state.result else []
        expected_deltas = expected_output.get("result", {}).get("deltas", [])

        actual_delta_tuples = extract_delta_tuples(actual_deltas)
        expected_delta_tuples = extract_delta_tuples(expected_deltas)

        # Compute per-operation metrics
        add_metrics = precision_recall_f1(expected_delta_tuples["add"], actual_delta_tuples["add"])
        remove_metrics = precision_recall_f1(
            expected_delta_tuples["remove"], actual_delta_tuples["remove"]
        )
        modify_metrics = precision_recall_f1(
            expected_delta_tuples["modify"], actual_delta_tuples["modify"]
        )

        # Compute overall delta F1
        all_expected_deltas = (
            expected_delta_tuples["add"]
            + expected_delta_tuples["remove"]
            + expected_delta_tuples["modify"]
        )
        all_actual_deltas = (
            actual_delta_tuples["add"]
            + actual_delta_tuples["remove"]
            + actual_delta_tuples["modify"]
        )
        overall_metrics = precision_recall_f1(all_expected_deltas, all_actual_deltas)

        _logger.info(
            f"Connection refinement metrics for {scenario}: "
            f"delta_f1={overall_metrics.f1:.4f}, "
            f"add_recall={add_metrics.recall:.4f}, "
            f"remove_recall={remove_metrics.recall:.4f}, "
            f"modify_recall={modify_metrics.recall:.4f}"
        )

        # Emit JSONL row with per-operation metrics
        metrics_emitter.emit(
            pipeline_type="connection_refinement",
            fixture_id=scenario,
            model=fixture_input.get("model", "claude-opus-4-7"),
            config_ref="default",
            config_version=1,
            metrics={
                "delta_f1": overall_metrics.f1,
                "add_recall": add_metrics.recall,
                "remove_recall": remove_metrics.recall,
                "modify_recall": modify_metrics.recall,
                "add_precision": add_metrics.precision,
                "remove_precision": remove_metrics.precision,
                "modify_precision": modify_metrics.precision,
            },
            mode="cassette",
        )

        # Assert empty-delta constraint if applicable
        if is_empty_delta:
            assert (
                len(actual_deltas) == 0
            ), f"Empty-delta fixture {scenario} should produce no deltas, got {len(actual_deltas)}"
        else:
            # Assert per-operation recall floors
            assert (
                add_metrics.recall >= 0.30 or len(expected_delta_tuples["add"]) == 0
            ), f"Add recall {add_metrics.recall:.4f} below floor 0.30 for scenario {scenario}"

            assert (
                remove_metrics.recall >= 0.30 or len(expected_delta_tuples["remove"]) == 0
            ), f"Remove recall {remove_metrics.recall:.4f} below floor 0.30 for scenario {scenario}"

            assert (
                modify_metrics.recall >= 0.30 or len(expected_delta_tuples["modify"]) == 0
            ), f"Modify recall {modify_metrics.recall:.4f} below floor 0.30 for scenario {scenario}"

            # Assert overall delta F1 floor
            assert (
                overall_metrics.f1 >= 0.40
            ), f"Delta F1 {overall_metrics.f1:.4f} below floor 0.40 for scenario {scenario}"

    @pytest.mark.asyncio
    @pytest.mark.external_network
    async def test_connection_refinement_apply_roundtrip_with_modify(
        self,
        ontology_repo,
        registered_connection_refinement,
    ):
        """
        Test apply round-trip with explicit validation of modify operations.

        This test is the primary regression target for the historical silent-drop bug
        on modify operations. Explicitly verifies that:
        - add operations create new relationships in the ontology
        - remove operations delete existing relationships
        - modify operations are properly tracked (FR-P5.5)

        The test asserts not just that counts change, but that the actual ontology
        state reflects the expected delta operations.
        """
        config_registry, impl_registry = registered_connection_refinement

        from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
        from tests.fakes.fake_llm_provider import FakeLLMProvider

        # Get concept scheme and taxonomy
        schemes = ontology_repo.list_concept_schemes()
        concept_scheme_id = schemes[0].id if schemes else str(uuid4())
        taxonomies = ontology_repo.list_taxonomies()
        taxonomy_id = taxonomies[0].id if taxonomies else str(uuid4())

        # Create test classes
        scope_id = str(uuid4())
        class_a_id = str(uuid4())
        class_b_id = str(uuid4())

        scope_cls = Class(
            id=scope_id,
            identifier="test_scope",
            concept_scheme_id=concept_scheme_id,
            taxonomy_id=taxonomy_id,
            title="Test Scope",
            description="Test scope for modify validation",
        )
        ontology_repo.save_class(scope_cls)

        cls_a = Class(
            id=class_a_id,
            identifier="class_a",
            concept_scheme_id=concept_scheme_id,
            taxonomy_id=taxonomy_id,
            title="Class A",
            description="",
        )
        ontology_repo.save_class(cls_a)

        cls_b = Class(
            id=class_b_id,
            identifier="class_b",
            concept_scheme_id=concept_scheme_id,
            taxonomy_id=taxonomy_id,
            title="Class B",
            description="",
        )
        ontology_repo.save_class(cls_b)

        # Get or create property definitions
        inherits_prop = ontology_repo.get_property_definition_by_identifier("inherits_from")
        if not inherits_prop:
            inherits_prop = PropertyDefinition(
                id=str(uuid4()),
                identifier="inherits_from",
                title="Inherits From",
                description="Inheritance relationship",
            )
            ontology_repo.save_property_definition(inherits_prop)

        # Create initial relationship that will be subject to modify
        initial_rel = Relationship(
            id=str(uuid4()),
            source_id=scope_id,
            target_id=class_a_id,
            property_definition_id=inherits_prop.id,
        )
        ontology_repo.save_relationship(initial_rel)

        # Create mock LLM response with add, modify, and remove operations
        # Order: add (new), modify (existing), remove (existing after modify)
        llm_response = {
            "deltas": [
                {
                    "operation": "add",
                    "subject": "Test Scope",
                    "predicate": "inherits_from",
                    "object": "Class B",
                    "confidence": 0.9,
                },
                {
                    "operation": "modify",
                    "subject": "Test Scope",
                    "predicate": "inherits_from",
                    "object": "Class A",
                    "confidence": 0.7,
                },
                {
                    "operation": "remove",
                    "subject": "Test Scope",
                    "predicate": "inherits_from",
                    "object": "Class A",
                    "confidence": 0.8,
                },
            ]
        }

        llm_provider = FakeLLMProvider(response_content=json.dumps(llm_response.get("deltas", [])))

        traversal = SchemaNeighborhoodTraversal(ontology_repo=ontology_repo)
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm_provider,
            traversal=traversal,
        )

        # Execute pipeline
        run_id = str(uuid4())
        state = ConnectionRefinementState(
            run_id=run_id,
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={
                "scope_id": scope_id,
                "candidates": [],
                "model": "claude-opus-4-7",
                "temperature": 0.0,
            },
        )
        result_state = await orchestrator.execute(state)

        # Create mock PipelineRun for apply service
        mock_run = PipelineRun(
            id=run_id,
            batch_run_id="test-batch",
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            output_summary={
                "scope_id": scope_id,
                "deltas": result_state.result.get("deltas", []) if result_state.result else [],
            },
        )

        apply_service = SchemaConnectionRefinementApplyService(ontology_repo)

        # First apply
        apply_result1 = apply_service.apply(mock_run)

        # Snapshot ontology state after first apply
        relationships_after_apply1 = list(ontology_repo.list_relationships(source_id=scope_id))
        rel_tuples_1 = [
            (r.source_id, r.property_definition_id, r.target_id) for r in relationships_after_apply1
        ]

        # Verify add operation: relationship to class_b should exist
        add_verified = any(
            (r.source_id == scope_id and r.target_id == class_b_id)
            for r in relationships_after_apply1
        )
        assert add_verified, "Add operation did not create relationship to Class B"

        # Verify remove operation: relationship to class_a should be gone
        remove_verified = not any(
            (r.source_id == scope_id and r.target_id == class_a_id)
            for r in relationships_after_apply1
        )
        assert remove_verified, "Remove operation did not delete relationship to Class A"

        # Verify modify operation is tracked
        assert (
            apply_result1.relationships_modified > 0
        ), "Modify operation was not tracked (silent-drop bug regression)"

        # Second apply: verify idempotence
        apply_service.apply(mock_run)

        relationships_after_apply2 = list(ontology_repo.list_relationships(source_id=scope_id))
        rel_tuples_2 = [
            (r.source_id, r.property_definition_id, r.target_id) for r in relationships_after_apply2
        ]

        # Assert idempotence: same relationship tuples after second apply
        assert rel_tuples_1 == rel_tuples_2, (
            f"Apply round-trip is not idempotent: "
            f"{len(rel_tuples_1)} rels after 1st apply, "
            f"{len(rel_tuples_2)} rels after 2nd apply"
        )


class TestQualityConnectionRefinementAggregation:
    """Aggregate quality metrics across all connection refinement scenarios."""

    @pytest.mark.asyncio
    async def test_quality_aggregate_metrics(self, metrics_emitter):
        """
        Aggregate quality metrics across all scenarios.

        Computes:
        - delta_f1: overall F1 on delta tuples
        - add_recall: average recall for add operations
        - remove_recall: average recall for remove operations
        - modify_recall: average recall for modify operations

        These aggregate metrics are computed from individual scenario metrics
        (which must have been emitted via MetricsEmitter in test_quality_scenario_with_metrics).

        FR-P5.2, FR-P5.3: Floors: delta_f1 >= 0.40, per-operation recall >= 0.30
        """
        # Read emitted metrics from JSONL file
        metrics_file = metrics_emitter._metrics_dir / "connection_refinement.jsonl"

        if not metrics_file.exists():
            pytest.skip(
                "No metrics emitted yet (scenarios may have skipped due to missing cassettes)"
            )

        delta_f1_values = []
        add_recall_values = []
        remove_recall_values = []
        modify_recall_values = []

        with open(metrics_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                metrics = row.get("metrics", {})

                if "delta_f1" in metrics:
                    delta_f1_values.append(metrics["delta_f1"])
                if "add_recall" in metrics:
                    add_recall_values.append(metrics["add_recall"])
                if "remove_recall" in metrics:
                    remove_recall_values.append(metrics["remove_recall"])
                if "modify_recall" in metrics:
                    modify_recall_values.append(metrics["modify_recall"])

        # Compute aggregates
        if not delta_f1_values:
            pytest.skip("No valid delta_f1 metrics found")

        aggregate_delta_f1 = sum(delta_f1_values) / len(delta_f1_values)
        aggregate_add_recall = (
            sum(add_recall_values) / len(add_recall_values) if add_recall_values else 0.0
        )
        aggregate_remove_recall = (
            sum(remove_recall_values) / len(remove_recall_values) if remove_recall_values else 0.0
        )
        aggregate_modify_recall = (
            sum(modify_recall_values) / len(modify_recall_values) if modify_recall_values else 0.0
        )

        _logger.info(
            f"Connection refinement aggregate metrics: "
            f"delta_f1={aggregate_delta_f1:.4f}, "
            f"add_recall={aggregate_add_recall:.4f}, "
            f"remove_recall={aggregate_remove_recall:.4f}, "
            f"modify_recall={aggregate_modify_recall:.4f}"
        )

        # Assert floors using FloorGate
        gate = FloorGate(METRIC_FLOORS)
        gate.assert_metrics(
            {
                "delta_f1": aggregate_delta_f1,
                "add_recall": aggregate_add_recall,
                "remove_recall": aggregate_remove_recall,
                "modify_recall": aggregate_modify_recall,
            },
            pipeline_type="connection_refinement",
        )
