"""Quality runner for fixture-based pipeline evaluation.

Orchestrates fixture loading, pipeline execution, and metric collection
across single or multiple (A/B) configurations.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.fixtures.pipeline_fixtures import (
    load_distractors,
    load_expected_output,
    load_fixture,
)


@dataclass
class QualityResult:
    """Result of a single fixture execution."""

    scenario: str
    actual_output: Any
    expected_output: Any
    duration_ms: float


class QualityRunner:
    """Executes quality tests against fixtures with a specified LLM provider."""

    def __init__(
        self,
        llm_provider: Any,
        fixture_dir: Path | str | None = None,
    ) -> None:
        """
        Initialize the quality runner.

        Args:
            llm_provider: LLMProvider instance (cassette, recording, or real)
            fixture_dir: Base directory for fixtures (optional, defaults to standard location)
        """
        self._llm_provider = llm_provider
        self._fixture_dir = fixture_dir

    def load_fixture(self, pipeline_type: str, scenario: str) -> dict[str, Any]:
        """
        Load an input fixture for a pipeline.

        Args:
            pipeline_type: Pipeline type directory name (e.g., 'individual_extraction')
            scenario: Scenario name (e.g., 'basic', 'fielding_rest')

        Returns:
            Parsed JSON fixture as dict
        """
        return load_fixture(pipeline_type, scenario)

    def load_expected_output(self, pipeline_type: str, scenario: str) -> dict[str, Any]:
        """
        Load the expected output fixture for a pipeline.

        Args:
            pipeline_type: Pipeline type directory name
            scenario: Scenario name

        Returns:
            Parsed JSON fixture as dict
        """
        return load_expected_output(pipeline_type, scenario)

    def load_distractors(
        self, pipeline_type: str, scenario: str
    ) -> dict[str, Any] | None:
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
        return load_distractors(pipeline_type, scenario)

    def get_llm_provider(self) -> Any:
        """Get the current LLM provider."""
        return self._llm_provider
