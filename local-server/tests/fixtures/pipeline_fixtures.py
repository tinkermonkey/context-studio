"""
Utilities for loading pipeline test fixtures.

Fixtures are data-only JSON files that provide:
- Input data for pipeline execution
- Expected output structure and key values

This enables reproducible, deterministic testing of pipeline implementations.

Supports both flat fixture layout ({scenario}_input.json) and
per-scenario directory layout ({scenario}/input.json).
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

    Supports both layouts:
    1. Per-scenario directory: {pipeline_type}/{scenario}/input.json
    2. Flat (legacy): {pipeline_type}/{scenario}_input.json

    Args:
        pipeline_type: Pipeline type directory name (e.g., 'individual_extraction', 'no_op')
        scenario: Scenario name without suffix (e.g., 'basic', 'error_case')

    Returns:
        Parsed JSON fixture as dict

    Raises:
        FileNotFoundError: If the fixture file does not exist
        json.JSONDecodeError: If the fixture is malformed JSON
    """
    fixtures_dir = _get_fixtures_dir()

    # Try per-scenario directory layout first
    per_scenario_path = fixtures_dir / pipeline_type / scenario / "input.json"
    if per_scenario_path.exists():
        with open(per_scenario_path, "r") as f:
            return json.load(f)

    # Fall back to flat layout
    flat_path = fixtures_dir / pipeline_type / f"{scenario}_input.json"
    if flat_path.exists():
        with open(flat_path, "r") as f:
            return json.load(f)

    raise FileNotFoundError(
        f"Fixture not found for {pipeline_type}/{scenario}. "
        f"Tried: {per_scenario_path} and {flat_path}"
    )


def load_expected_output(pipeline_type: str, scenario: str) -> dict[str, Any]:
    """
    Load the expected output fixture for a pipeline.

    Supports both layouts:
    1. Per-scenario directory: {pipeline_type}/{scenario}/expected.json
    2. Flat (legacy): {pipeline_type}/{scenario}_output.json

    Args:
        pipeline_type: Pipeline type directory name (e.g., 'individual_extraction', 'no_op')
        scenario: Scenario name without suffix (e.g., 'basic', 'error_case')

    Returns:
        Parsed JSON fixture as dict

    Raises:
        FileNotFoundError: If the fixture file does not exist
        json.JSONDecodeError: If the fixture is malformed JSON
    """
    fixtures_dir = _get_fixtures_dir()

    # Try per-scenario directory layout first
    per_scenario_path = fixtures_dir / pipeline_type / scenario / "expected.json"
    if per_scenario_path.exists():
        with open(per_scenario_path, "r") as f:
            return json.load(f)

    # Fall back to flat layout
    flat_path = fixtures_dir / pipeline_type / f"{scenario}_output.json"
    if flat_path.exists():
        with open(flat_path, "r") as f:
            return json.load(f)

    raise FileNotFoundError(
        f"Expected output fixture not found for {pipeline_type}/{scenario}. "
        f"Tried: {per_scenario_path} and {flat_path}"
    )


def load_distractors(pipeline_type: str, scenario: str) -> dict[str, Any] | None:
    """
    Load distractor fixtures for a scenario (optional).

    Distractors are plausible-but-wrong candidates used to evaluate
    ranking and filtering quality. Not all pipelines use distractors.

    Args:
        pipeline_type: Pipeline type directory name
        scenario: Scenario name

    Returns:
        Parsed JSON dict if distractors exist, None otherwise
    """
    fixtures_dir = _get_fixtures_dir()
    distractor_path = fixtures_dir / pipeline_type / scenario / "distractors.json"

    if distractor_path.exists():
        with open(distractor_path, "r") as f:
            return json.load(f)

    return None
