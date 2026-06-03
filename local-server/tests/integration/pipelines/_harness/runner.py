"""Quality runner for fixture-based pipeline evaluation.

Orchestrates fixture loading, pipeline execution, and metric collection
across single or multiple (A/B) configurations.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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

    def load_distractors(self, pipeline_type: str, scenario: str) -> dict[str, Any] | None:
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

    async def run_ab(
        self,
        config_specs: list[tuple[str, Any]],
        scenario_list: list[str],
        pipeline_type: str,
        executor_fn: Callable,
        metrics_fn: Callable,
        cassette_dir: Path | str | None = None,
        validate_cassettes: bool = True,
    ) -> dict[str, dict[str, dict[str, float]]]:
        """
        Run A/B comparison across ≥2 configurations and fixture corpus.

        Each configuration is tested against the same fixture scenarios in a single
        invocation, allowing side-by-side comparison and aggregated metric reporting.

        Args:
            config_specs: List of (config_ref, llm_provider) tuples.
                         Each config_ref identifies the configuration;
                         llm_provider is the LLMProvider instance for that config.
            scenario_list: List of scenario names to run against each config.
            pipeline_type: Pipeline type identifier (e.g., "schema_extraction").
            executor_fn: Async callable(llm_provider, fixture_input) -> output_dict.
                        Should handle any pipeline-specific orchestration.
            metrics_fn: Callable(expected, actual) -> metrics_dict.
                       Computes metrics from expected output and actual result.
            cassette_dir: Base cassette directory (optional). If provided with
                         validate_cassettes=True, checks that cassettes exist
                         before running.
            validate_cassettes: If True and cassette_dir is set, checks all
                               required cassettes exist upfront, failing fast.

        Returns:
            Dict mapping config_ref → scenario → metrics:
            {
                "config-a": {
                    "scenario-1": {"metric_a": 0.85, "metric_b": 0.72},
                    "scenario-2": {"metric_a": 0.90, "metric_b": 0.68},
                },
                "config-b": {
                    "scenario-1": {"metric_a": 0.82, "metric_b": 0.75},
                    "scenario-2": {"metric_a": 0.88, "metric_b": 0.70},
                },
            }

        Raises:
            FileNotFoundError: If validate_cassettes=True and required cassettes
                              do not exist.
            AssertionError: If metric computation fails.
        """
        if validate_cassettes and cassette_dir:
            self._validate_cassettes_exist(
                config_specs, scenario_list, pipeline_type, Path(cassette_dir)
            )

        results: dict[str, dict[str, dict[str, float]]] = {}

        for config_ref, llm_provider in config_specs:
            results[config_ref] = {}

            for scenario in scenario_list:
                fixture_input = self.load_fixture(pipeline_type, scenario)
                expected_output = self.load_expected_output(pipeline_type, scenario)

                actual_output = await executor_fn(llm_provider, fixture_input)

                metrics = metrics_fn(expected_output, actual_output)
                results[config_ref][scenario] = metrics

        return results

    def _validate_cassettes_exist(
        self,
        config_specs: list[tuple[str, Any]],
        scenario_list: list[str],
        pipeline_type: str,
        cassette_dir: Path,
    ) -> None:
        """
        Check that all required cassettes exist before running A/B tests.

        Fails fast with a clear error message listing missing cassettes.

        Args:
            config_specs: List of (config_ref, llm_provider) tuples.
            scenario_list: List of scenario names.
            pipeline_type: Pipeline type identifier.
            cassette_dir: Base cassette directory.

        Raises:
            FileNotFoundError: If any required cassette is missing.
        """
        missing = []

        for config_ref, _ in config_specs:
            for scenario in scenario_list:
                cassette_path = (
                    cassette_dir / f"{pipeline_type}_{scenario}_{config_ref}.json"
                )
                if not cassette_path.exists():
                    missing.append(str(cassette_path))

        if missing:
            raise FileNotFoundError(
                "Missing cassettes for A/B run:\n"
                + "\n".join(f"  - {p}" for p in missing)
                + "\nRun with --refresh-cassettes to record all missing cassettes."
            )
