"""
Utilities for loading pipeline test fixtures.

Fixtures are data-only JSON files that provide:
- Input data for pipeline execution
- Expected output structure and key values

This enables reproducible, deterministic testing of pipeline implementations.
"""

import json
from pathlib import Path
from typing import Any


def _get_fixtures_dir() -> Path:
    """Get the pipelines fixtures directory."""
    return Path(__file__).parent.parent / "integration" / "fixtures" / "pipelines"


def load_fixture(pipeline_type: str, scenario: str) -> dict[str, Any]:
    """
    Load an input fixture for a pipeline.

    Args:
        pipeline_type: Pipeline type directory name (e.g., 'individual_extraction', 'no_op')
        scenario: Scenario name without suffix (e.g., 'basic', 'error_case')

    Returns:
        Parsed JSON fixture as dict

    Raises:
        FileNotFoundError: If the fixture file does not exist
        json.JSONDecodeError: If the fixture is malformed JSON
    """
    fixture_path = _get_fixtures_dir() / pipeline_type / f"{scenario}_input.json"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path, "r") as f:
        return json.load(f)


def load_expected_output(pipeline_type: str, scenario: str) -> dict[str, Any]:
    """
    Load the expected output fixture for a pipeline.

    Args:
        pipeline_type: Pipeline type directory name (e.g., 'individual_extraction', 'no_op')
        scenario: Scenario name without suffix (e.g., 'basic', 'error_case')

    Returns:
        Parsed JSON fixture as dict

    Raises:
        FileNotFoundError: If the fixture file does not exist
        json.JSONDecodeError: If the fixture is malformed JSON
    """
    fixture_path = _get_fixtures_dir() / pipeline_type / f"{scenario}_output.json"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Expected output fixture not found: {fixture_path}")

    with open(fixture_path, "r") as f:
        return json.load(f)
