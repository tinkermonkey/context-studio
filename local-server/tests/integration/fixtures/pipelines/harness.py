"""Shared test harness for pipeline integration tests.

Provides `run_pipeline_against_fixture`: a helper that:
1. Loads input and expected output fixtures
2. Runs a pipeline against the input
3. Compares actual output to expected output
4. Reports diffs in a structured way
"""

from typing import Any

from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture


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
    diff = {
        "matches": True,
        "missing_keys": [],
        "extra_keys": [],
        "mismatched_values": [],
    }

    # Check for missing keys in actual
    for key in expected:
        if key not in actual:
            diff["missing_keys"].append(key)
            diff["matches"] = False

    # Check for extra keys in actual
    for key in actual:
        if key not in expected:
            diff["extra_keys"].append(key)

    # Check for mismatched values in keys that exist in both
    for key in expected:
        if key in actual:
            if actual[key] != expected[key]:
                diff["mismatched_values"].append(
                    {
                        "key": key,
                        "expected": expected[key],
                        "actual": actual[key],
                    }
                )
                diff["matches"] = False

    return diff


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
    from domain.pipelines.entities import PipelineType
    from domain.pipelines.orchestration.noop import NoOpPipelineState
    from uuid import uuid4

    # Load fixture
    fixture_input = load_fixture(pipeline_type, scenario)
    expected_output = load_expected_output(pipeline_type, scenario)

    # Create state based on pipeline type
    if pipeline_type == "no_op":
        state = NoOpPipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.NO_OP,
            input_data=fixture_input,
        )
    else:
        # For other pipeline types, use appropriate state class
        # This will be extended per-pipeline-type
        from domain.pipelines.orchestration.base import PipelineState

        state = PipelineState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType(pipeline_type),
            input_data=fixture_input,
        )

    # Execute pipeline
    result_state = await orchestrator.execute(state)

    # Extract actual output from result state
    actual_output = {
        "status": str(result_state.current_status),
        "result": result_state.result,
    }

    if hasattr(result_state, "metadata") and result_state.metadata:
        actual_output["metadata"] = result_state.metadata

    return actual_output, expected_output
