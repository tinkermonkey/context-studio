"""Shared test harness for pipeline integration tests.

Provides `run_pipeline_against_fixture`: a helper that:
1. Loads input and expected output fixtures
2. Runs a pipeline against the input
3. Compares actual output to expected output
4. Reports diffs in a structured way
"""

from dataclasses import dataclass, field
from typing import Any

from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture


@dataclass
class OutputDiff:
    """Structured comparison result between actual and expected outputs."""

    matches: bool = True
    missing_keys: list[str] = field(default_factory=list)
    extra_keys: list[str] = field(default_factory=list)
    mismatched_values: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for backward compatibility."""
        return {
            "matches": self.matches,
            "missing_keys": self.missing_keys,
            "extra_keys": self.extra_keys,
            "mismatched_values": self.mismatched_values,
        }


def compare_output(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """
    Compare actual output to expected output.

    Returns a diff dict with structure:
    {
        "matches": bool,
        "missing_keys": list of expected keys not in actual,
        "extra_keys": list of actual keys not in expected,
        "mismatched_values": list of dicts with key, expected, actual,
    }
    """
    diff = OutputDiff()

    # Check for missing keys in actual
    for key in expected:
        if key not in actual:
            diff.missing_keys.append(key)
            diff.matches = False

    # Check for extra keys in actual
    for key in actual:
        if key not in expected:
            diff.extra_keys.append(key)
            diff.matches = False

    # Check for mismatched values in keys that exist in both
    for key in expected:
        if key in actual:
            if actual[key] != expected[key]:
                diff.mismatched_values.append(
                    {
                        "key": key,
                        "expected": expected[key],
                        "actual": actual[key],
                    }
                )
                diff.matches = False

    return diff.to_dict()


async def run_pipeline_against_fixture(
    orchestrator: Any,
    pipeline_type: str,
    scenario: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Run a pipeline against a fixture and return actual and expected outputs.

    Args:
        orchestrator: PipelineOrchestrator instance to run
        pipeline_type: Pipeline type dir name (e.g., 'individual_extraction', 'no_op')
        scenario: Scenario name without suffix (e.g., 'basic')

    Returns:
        Tuple of (actual_output, expected_output) dicts

    Raises:
        FileNotFoundError: If fixture or expected output file not found
    """
    from uuid import uuid4

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from adapters.persistence.sqlite.models import Base
    from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
    from domain.pipelines.entities import PipelineType
    from domain.pipelines.orchestration.base import PipelineState
    from domain.pipelines.orchestration.noop import NoOpPipelineState
    from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
    from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionState
    from domain.pipelines.schema_node_connection_refinement.orchestrator import (
        ConnectionRefinementState,
    )
    from domain.pipelines.schema_node_definition_refinement.orchestrator import (
        DefinitionRefinementState,
    )
    from domain.pipelines.schema_node_grounding.orchestrator import SchemaGroundingState

    # Load fixture
    fixture_input = load_fixture(pipeline_type, scenario)
    expected_output = load_expected_output(pipeline_type, scenario)

    # Create state based on pipeline type
    state: PipelineState
    if pipeline_type == "no_op":
        state = NoOpPipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.NO_OP,
            input_data=fixture_input,
        )
    elif pipeline_type == "schema_extraction":
        state = SchemaExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=fixture_input,
        )
    elif pipeline_type == "schema_node_connection_refinement":
        from domain.ontology.entities import Class, ConceptScheme, Taxonomy

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        repo = SQLiteOntologyRepository(session_factory)

        # Setup fixture data if _setup section exists
        if "_setup" in fixture_input:
            setup = fixture_input["_setup"]
            if "create_class" in setup:
                class_spec = setup["create_class"]
                # Create taxonomy and scheme if needed
                tax = Taxonomy(
                    id="fixture-tax-1",
                    identifier="fixture_taxonomy",
                    title="Fixture Taxonomy",
                )
                repo.save_taxonomy(tax)
                scheme = ConceptScheme(
                    id="fixture-scheme-1",
                    identifier="fixture_scheme",
                    taxonomy_id=tax.id,
                    title="Fixture Scheme",
                )
                repo.save_concept_scheme(scheme)
                # Create the class
                cls = Class(
                    id=class_spec.get("id", "test-scope-456"),
                    identifier=class_spec.get("identifier", "test_class"),
                    concept_scheme_id=scheme.id,
                    taxonomy_id=tax.id,
                    title=class_spec.get("title", "Test Class"),
                    description=class_spec.get("description", ""),
                )
                repo.save_class(cls)

        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)
        if hasattr(orchestrator, '_traversal') and orchestrator._traversal is None:
            orchestrator._traversal = traversal
        state = ConnectionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data=fixture_input,
        )
    elif pipeline_type == "schema_node_definition_refinement":
        from domain.ontology.entities import Class, ConceptScheme, Taxonomy

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        repo = SQLiteOntologyRepository(session_factory)

        # Setup fixture data if _setup section exists
        if "_setup" in fixture_input:
            setup = fixture_input["_setup"]
            if "create_class" in setup:
                class_spec = setup["create_class"]
                # Create taxonomy and scheme if needed
                tax = Taxonomy(
                    id="fixture-tax-1",
                    identifier="fixture_taxonomy",
                    title="Fixture Taxonomy",
                )
                repo.save_taxonomy(tax)
                scheme = ConceptScheme(
                    id="fixture-scheme-1",
                    identifier="fixture_scheme",
                    taxonomy_id=tax.id,
                    title="Fixture Scheme",
                )
                repo.save_concept_scheme(scheme)
                # Create the class
                cls = Class(
                    id=class_spec.get("id", "test-node-456"),
                    identifier=class_spec.get("identifier", "test_class"),
                    concept_scheme_id=scheme.id,
                    taxonomy_id=tax.id,
                    title=class_spec.get("title", "Test Class"),
                    description=class_spec.get("description", ""),
                )
                repo.save_class(cls)

        traversal = SchemaNeighborhoodTraversal(ontology_repo=repo)
        if hasattr(orchestrator, '_traversal') and orchestrator._traversal is None:
            orchestrator._traversal = traversal
        state = DefinitionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data=fixture_input,
        )
    elif pipeline_type == "schema_node_grounding":
        state = SchemaGroundingState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            input_data=fixture_input,
        )
    else:
        # For other pipeline types, use appropriate state class
        # This will be extended per-pipeline-type
        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType(pipeline_type),
            input_data=fixture_input,
        )

    # Execute pipeline
    result_state = await orchestrator.execute(state)

    # Extract actual output from result state
    # Convert status enum to string value (e.g., "completed" not "PipelineRunStatus.COMPLETED")
    status_str = (
        result_state.current_status.value
        if hasattr(result_state.current_status, "value")
        else str(result_state.current_status)
    )
    actual_output = {
        "status": status_str,
        "result": result_state.result,
    }

    if hasattr(result_state, "metadata") and result_state.metadata:
        actual_output["metadata"] = result_state.metadata

    return actual_output, expected_output
