"""
End-to-end quality test suite for cross-pipeline chain execution.

Tests the complete chain of all 5 pipelines in sequence:
1. schema_extraction
2. schema_extraction.apply
3. individual_extraction
4. individual_extraction.apply
5. schema_node_grounding
6. schema_node_grounding.apply
7. schema_node_definition_refinement
8. schema_node_definition_refinement.apply
9. schema_node_connection_refinement
10. schema_node_connection_refinement.apply

All stages share one temp SQLite database. Final ontology state is verified
against a hand-curated expected ontology with metrics:
- Exact match on class/property/relationship sets
- Cosine similarity ≥ 0.75 on refined descriptions
- Top-3 match on external references
"""

import json
import logging
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.pipelines.entities import PipelineRun, PipelineRunStatus, PipelineType
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
)
from domain.pipelines.individual_extraction import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
    register_individual_extraction,
)
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from domain.pipelines.schema_node_grounding import (
    register_schema_node_grounding,
)
from domain.pipelines.schema_node_grounding.orchestrator import (
    SchemaGroundingOrchestrator,
    SchemaGroundingState,
)
from domain.pipelines.schema_node_grounding.apply_service import (
    SchemaGroundingApplyService,
)
from domain.pipelines.schema_node_definition_refinement import (
    DefinitionRefinementOrchestrator,
    DefinitionRefinementState,
    register_schema_node_definition_refinement,
)
from domain.pipelines.schema_node_definition_refinement.apply_service import (
    SchemaDefinitionRefinementApplyService,
)
from domain.pipelines.schema_node_connection_refinement import (
    ConnectionRefinementOrchestrator,
    ConnectionRefinementState,
    register_schema_node_connection_refinement,
)
from domain.pipelines.schema_node_connection_refinement.apply_service import (
    SchemaConnectionRefinementApplyService,
)
from tests.fixtures.pipeline_fixtures import load_fixture, load_expected_output
from tests.integration.pipelines._harness.cassettes import (
    CassetteLLMProvider,
)
from tests.integration.pipelines._harness.metrics import (
    cosine_similarity,
    jaccard_similarity,
    mean_reciprocal_rank,
)
from tests.integration.pipelines._harness.report import FloorGate, MetricsEmitter

_logger = logging.getLogger(__name__)

# Quality scenarios for E2E chain testing
QUALITY_SCENARIOS = [
    "technical_concepts",
]

# Metric floors for E2E chain quality
METRIC_FLOORS = {
    "class_set_match": 1.0,
    "property_set_match": 1.0,
    "relationship_set_match": 1.0,
    "mean_description_cosine": 0.75,
    "pct_references_top3": 0.80,
}


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database shared across all pipeline stages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "e2e_chain.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url, db_path


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    db_url, _ = temp_db
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def ontology_repo(session_factory):
    """Create a real SQLiteOntologyRepository with initial taxonomy."""
    repo = SQLiteOntologyRepository(session_factory)

    # Create the base taxonomy and scheme
    tax = Taxonomy(
        id="e2e-taxonomy",
        identifier="e2e_taxonomy",
        title="E2E Chain Test Ontology",
        description="Ontology for E2E chain quality testing",
    )
    repo.save_taxonomy(tax)

    scheme = ConceptScheme(
        id="e2e-scheme",
        identifier="e2e_scheme",
        taxonomy_id=tax.id,
        title="E2E Test Scheme",
        description="Test scheme",
    )
    repo.save_concept_scheme(scheme)

    yield repo


@pytest.fixture
def registered_pipelines(session_factory):
    """Register all 5 pipelines with their configurations and implementations."""
    config_registry = PipelineConfigurationRegistry()
    impl_registry = PipelineImplementationRegistry()

    # Register all pipeline implementations
    register_schema_extraction(impl_registry, config_registry)
    register_individual_extraction(impl_registry, config_registry)
    register_schema_node_grounding(impl_registry, config_registry)
    register_schema_node_definition_refinement(impl_registry, config_registry)
    register_schema_node_connection_refinement(impl_registry, config_registry)

    return config_registry, impl_registry


@pytest.fixture
def metrics_emitter(tmp_path):
    """Create a MetricsEmitter for JSONL output."""
    metrics_dir = tmp_path / "_metrics"
    return MetricsEmitter(metrics_dir)


@pytest.fixture
def cassette_dir():
    """Cassette directory for LLM recordings (repo-relative)."""
    cassette_path = Path(__file__).parent.parent.parent / "_e2e_chain"
    return cassette_path


class TestQualityE2EChain:
    """E2E chain quality test suite."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", QUALITY_SCENARIOS)
    async def test_e2e_chain_executes_all_stages(
        self,
        scenario: str,
        ontology_repo,
        registered_pipelines,
        metrics_emitter,
        cassette_dir,
    ):
        """
        Test complete pipeline chain execution.

        1. Load fixture input (3-5 documents)
        2. Execute schema_extraction → apply
        3. Execute individual_extraction → apply
        4. Execute schema_node_grounding → apply
        5. Execute schema_node_definition_refinement → apply
        6. Execute schema_node_connection_refinement → apply
        7. Assert final ontology matches expected_final_ontology.json
        8. Compute quality metrics and verify floors
        9. Emit JSONL row with metrics

        Runs in cassette mode (zero network calls); cassettes must exist or test
        will be skipped. To record cassettes, run with @pytest.mark.real_llm.
        """
        config_registry, impl_registry = registered_pipelines
        cassette_dir.mkdir(parents=True, exist_ok=True)

        # Load fixture
        try:
            fixture_input = load_fixture("e2e_chain", scenario)
            expected_final = load_expected_output("e2e_chain", scenario)
        except FileNotFoundError:
            pytest.skip(f"Fixture not found for e2e_chain/{scenario}")

        # Check if all required cassettes exist before proceeding
        cassette_paths = [
            cassette_dir / f"e2e_chain_{scenario}_schema_extraction.json",
            cassette_dir / f"e2e_chain_{scenario}_individual_extraction.json",
            cassette_dir / f"e2e_chain_{scenario}_schema_node_grounding.json",
            cassette_dir / f"e2e_chain_{scenario}_definition_refinement.json",
            cassette_dir / f"e2e_chain_{scenario}_connection_refinement.json",
        ]

        missing_cassettes = [p for p in cassette_paths if not p.exists()]
        if missing_cassettes:
            pytest.skip(
                f"Cassettes not found for {scenario}. Missing: "
                f"{[p.name for p in missing_cassettes]}. "
                f"Run with @pytest.mark.real_llm to record cassettes."
            )

        # Extract taxonomy and scheme IDs
        taxonomies = ontology_repo.list_taxonomies()
        schemes = ontology_repo.list_concept_schemes()
        taxonomy_id = taxonomies[0].id if taxonomies else str(uuid4())
        concept_scheme_id = schemes[0].id if schemes else str(uuid4())

        documents = fixture_input.get("documents", [])

        # ===== STAGE 1: Schema Extraction =====
        llm_provider = CassetteLLMProvider(cassette_paths[0])
        schema_ext_orchestrator = SchemaExtractionOrchestrator(
            llm_provider=llm_provider,
            ontology_repo=ontology_repo,
        )

        schema_ext_state = SchemaExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data={"documents": documents},
        )
        schema_ext_result = await schema_ext_orchestrator.execute(schema_ext_state)

        assert schema_ext_result.current_status == PipelineRunStatus.COMPLETED
        schema_ext_run = PipelineRun(
            id=schema_ext_state.run_id,
            batch_run_id="e2e-batch",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
            output_summary=schema_ext_result.result or {},
        )

        # ===== STAGE 2: Apply Schema Extraction =====
        schema_ext_apply = SchemaExtractionApplyService(ontology_repo)
        schema_ext_apply.apply(schema_ext_run, concept_scheme_id, taxonomy_id)

        # ===== STAGE 3: Individual Extraction =====
        llm_provider = CassetteLLMProvider(cassette_paths[1])
        indiv_ext_orchestrator = IndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            ontology_repo=ontology_repo,
        )

        indiv_ext_state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data={
                "documents": documents,
                "target_classes": [
                    c.get("label", "")
                    for c in (schema_ext_result.result or {}).get("candidates", [])
                    if c.get("kind") == "class"
                ],
            },
        )
        indiv_ext_result = await indiv_ext_orchestrator.execute(indiv_ext_state)

        assert indiv_ext_result.current_status == PipelineRunStatus.COMPLETED
        indiv_ext_run = PipelineRun(
            id=indiv_ext_state.run_id,
            batch_run_id="e2e-batch",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
            output_summary=indiv_ext_result.result or {},
        )

        # ===== STAGE 4: Apply Individual Extraction =====
        indiv_ext_apply = IndividualExtractionApplyService(ontology_repo)
        indiv_ext_apply.apply(indiv_ext_run, concept_scheme_id, taxonomy_id)

        # ===== STAGE 5: Schema Node Grounding =====
        llm_provider = CassetteLLMProvider(cassette_paths[2])
        grounding_orchestrator = SchemaGroundingOrchestrator(
            llm_provider=llm_provider,
            ontology_repo=ontology_repo,
        )

        # Get class IDs from ontology for grounding
        classes = ontology_repo.list_classes()
        class_ids = [c.id for c in classes]

        grounding_state = SchemaGroundingState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            input_data={
                "class_ids": class_ids,
                "target_sources": ["wikidata", "conceptnet", "dbpedia"],
                "top_n": 5,
            },
        )
        grounding_result = await grounding_orchestrator.execute(grounding_state)

        assert grounding_result.current_status == PipelineRunStatus.COMPLETED
        grounding_run = PipelineRun(
            id=grounding_state.run_id,
            batch_run_id="e2e-batch",
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
            output_summary=grounding_result.result or {},
        )

        # ===== STAGE 6: Apply Schema Node Grounding =====
        grounding_apply = SchemaGroundingApplyService(ontology_repo)
        grounding_apply.apply(grounding_run)

        # ===== STAGE 7: Definition Refinement =====
        embedding_service = SentenceTransformerEmbedding(
            model_name="all-MiniLM-L12-v2"
        )
        llm_provider = CassetteLLMProvider(cassette_paths[3])
        def_refine_orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=llm_provider,
            embedding_service=embedding_service,
            ontology_repo=ontology_repo,
        )

        # Get class IDs from ontology for refinement
        classes = ontology_repo.list_classes()
        class_ids = [c.id for c in classes]

        def_refine_state = DefinitionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={"class_ids": class_ids},
        )
        def_refine_result = await def_refine_orchestrator.execute(def_refine_state)

        assert def_refine_result.current_status == PipelineRunStatus.COMPLETED
        def_refine_run = PipelineRun(
            id=def_refine_state.run_id,
            batch_run_id="e2e-batch",
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
            output_summary=def_refine_result.result or {},
        )

        # ===== STAGE 8: Apply Definition Refinement =====
        def_refine_apply = SchemaDefinitionRefinementApplyService(ontology_repo)
        def_refine_apply.apply(def_refine_run)

        # ===== STAGE 9: Connection Refinement =====
        llm_provider = CassetteLLMProvider(cassette_paths[4])
        conn_refine_orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=llm_provider,
            embedding_service=embedding_service,
            ontology_repo=ontology_repo,
        )

        # Get relationship IDs from ontology for refinement
        relationships = ontology_repo.list_relationships()
        relationship_ids = [r.id for r in relationships]

        conn_refine_state = ConnectionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={"relationship_ids": relationship_ids},
        )
        conn_refine_result = await conn_refine_orchestrator.execute(conn_refine_state)

        assert conn_refine_result.current_status == PipelineRunStatus.COMPLETED
        conn_refine_run = PipelineRun(
            id=conn_refine_state.run_id,
            batch_run_id="e2e-batch",
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
            output_summary=conn_refine_result.result or {},
        )

        # ===== STAGE 10: Apply Connection Refinement =====
        conn_refine_apply = SchemaConnectionRefinementApplyService(ontology_repo)
        conn_refine_apply.apply(conn_refine_run)

        # ===== Compute Quality Metrics =====
        final_classes = ontology_repo.list_classes()
        final_properties = ontology_repo.list_property_definitions()
        final_relationships = ontology_repo.list_relationships()

        expected_final_result = expected_final.get("result", {})
        expected_classes = expected_final_result.get("classes", [])
        expected_properties = expected_final_result.get("properties", [])
        expected_relationships = expected_final_result.get("relationships", [])
        expected_references = expected_final_result.get("external_references", {})

        # Extract labels for matching
        final_class_labels = {c.title for c in final_classes}
        expected_class_labels = {c.get("label", "") for c in expected_classes}

        final_property_labels = {p.label for p in final_properties}
        expected_property_labels = {p.get("label", "") for p in expected_properties}

        # Build id→label mappings for relationship matching
        id_to_class_label = {c.id: c.title for c in final_classes}
        id_to_property_label = {p.id: p.label for p in final_properties}

        # Match relationships by labels instead of IDs
        final_relationship_tuples = set()
        for r in final_relationships:
            source_label = id_to_class_label.get(r.source_id, "")
            property_label = id_to_property_label.get(r.property_definition_id, "")
            target_label = id_to_class_label.get(r.target_id, "")
            if source_label and property_label and target_label:
                final_relationship_tuples.add((source_label, property_label, target_label))

        expected_relationship_tuples = {
            (r.get("subject_label", ""), r.get("predicate", ""), r.get("object_label", ""))
            for r in expected_relationships
        }

        # Compute set match metrics
        class_set_match = 1.0 if final_class_labels == expected_class_labels else 0.0
        property_set_match = (
            1.0 if final_property_labels == expected_property_labels else 0.0
        )
        relationship_set_match = (
            1.0 if final_relationship_tuples == expected_relationship_tuples else 0.0
        )

        # Compute description cosine similarities
        description_cosines = []
        for final_class in final_classes:
            if final_class.description:
                # Find expected class with same label
                for expected_class in expected_classes:
                    if (
                        expected_class.get("label") == final_class.title
                        and expected_class.get("description")
                    ):
                        # Compute embedding cosine
                        final_embedding = embedding_service.embed(
                            final_class.description
                        )
                        expected_embedding = embedding_service.embed(
                            expected_class["description"]
                        )
                        if final_embedding and expected_embedding:
                            cosine = cosine_similarity(final_embedding, expected_embedding)
                            description_cosines.append(cosine)
                        break

        mean_description_cosine = (
            sum(description_cosines) / len(description_cosines)
            if description_cosines
            else 0.0
        )

        # Compute external reference top-3 match
        ref_top3_matches = []
        for class_label, expected_refs in expected_references.items():
            # Match classes by label, not by fixture ID
            final_class = next(
                (c for c in final_classes if c.title == class_label), None
            )
            if final_class and expected_refs:
                final_refs = [
                    ref.get("uri", "") for ref in (final_class.external_references or [])
                ]
                mrr = mean_reciprocal_rank(expected_refs[:3], final_refs)
                ref_top3_matches.append(mrr)

        pct_references_top3 = (
            sum(ref_top3_matches) / len(ref_top3_matches)
            if ref_top3_matches
            else 0.0
        )

        metrics = {
            "class_set_match": class_set_match,
            "property_set_match": property_set_match,
            "relationship_set_match": relationship_set_match,
            "mean_description_cosine": mean_description_cosine,
            "pct_references_top3": pct_references_top3,
        }

        _logger.info(f"E2E chain metrics for {scenario}: {metrics}")

        # Emit JSONL row
        metrics_emitter.emit(
            pipeline_type="_e2e_chain",
            scenario=scenario,
            model="test-model",
            config_ref="default",
            config_version=1,
            metrics=metrics,
            mode="cassette",
        )

        # Assert metrics against floors
        gate = FloorGate(METRIC_FLOORS)
        gate.assert_metrics(metrics, pipeline_type=f"e2e_chain/{scenario}")
