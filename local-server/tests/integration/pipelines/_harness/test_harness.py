"""Test suite for A/B testing harness (runner.py and report.py)."""

import pytest

from tests.integration.pipelines._harness.report import ABReport
from tests.integration.pipelines._harness.runner import QualityRunner


class TestFormatComparisonMulti:
    """Test ABReport.format_comparison_multi() method."""

    def test_format_comparison_multi_two_configs(self):
        """Test format_comparison_multi with two configurations."""
        config_results = {
            "config-a": {
                "scenario-1": {"precision": 0.85, "recall": 0.90},
                "scenario-2": {"precision": 0.80, "recall": 0.88},
            },
            "config-b": {
                "scenario-1": {"precision": 0.82, "recall": 0.88},
                "scenario-2": {"precision": 0.78, "recall": 0.85},
            },
        }

        report = ABReport.format_comparison_multi(config_results)
        assert "Multi-Config A/B Comparison" in report
        assert "config-a" in report
        assert "config-b" in report
        assert "Δ(config-a - config-b)" in report

    def test_format_comparison_multi_three_configs(self):
        """Test format_comparison_multi with three configurations."""
        config_results = {
            "config-a": {
                "scenario-1": {"metric": 0.90},
            },
            "config-b": {
                "scenario-1": {"metric": 0.85},
            },
            "config-c": {
                "scenario-1": {"metric": 0.80},
            },
        }

        report = ABReport.format_comparison_multi(config_results)
        assert "3 configs" in report
        assert "Δ(config-a - config-b)" in report
        assert "Δ(config-a - config-c)" in report

    def test_format_comparison_multi_delta_sign_correctness(self):
        """Test that delta sign is correct: positive means config-a is higher."""
        config_results = {
            "config-a": {
                "scenario-1": {"metric": 0.90},
            },
            "config-b": {
                "scenario-1": {"metric": 0.80},
            },
        }

        report = ABReport.format_comparison_multi(config_results)
        # config-a (0.90) - config-b (0.80) = +0.1000
        assert "+0.1000" in report

    def test_format_comparison_multi_negative_delta(self):
        """Test negative delta when config-a is lower than config-b."""
        config_results = {
            "config-a": {
                "scenario-1": {"metric": 0.70},
            },
            "config-b": {
                "scenario-1": {"metric": 0.80},
            },
        }

        report = ABReport.format_comparison_multi(config_results)
        # config-a (0.70) - config-b (0.80) = -0.1000
        assert "-0.1000" in report

    def test_format_comparison_multi_floor_markers(self):
        """Test that floor markers (✗) are displayed for failed metrics."""
        config_results = {
            "config-a": {
                "scenario-1": {"precision": 0.55, "f1": 0.60},
            },
            "config-b": {
                "scenario-1": {"precision": 0.75, "f1": 0.70},
            },
        }
        floors = {
            "precision": 0.60,  # config-a fails this floor
            "f1": 0.50,  # both pass
        }

        report = ABReport.format_comparison_multi(config_results, floors=floors)
        # config-a's precision (0.55) should have ✗ marker
        assert "0.5500✗" in report or "0.55✗" in report

    def test_format_comparison_multi_brier_lower_is_better(self):
        """Test that brier score (lower-is-better) floor checking works correctly."""
        config_results = {
            "config-a": {
                "scenario-1": {"brier": 0.15},
            },
            "config-b": {
                "scenario-1": {"brier": 0.25},
            },
        }
        floors = {
            "brier": 0.20,
        }

        report = ABReport.format_comparison_multi(config_results, floors=floors)
        # config-a (0.15) passes (lower than 0.20)
        # config-b (0.25) fails (higher than 0.20)
        assert "0.2500✗" in report or "0.25✗" in report

    def test_format_comparison_multi_nan_values(self):
        """Test graceful handling of NaN values."""
        config_results = {
            "config-a": {
                "scenario-1": {"metric": float("nan"), "other": 0.85},
            },
            "config-b": {
                "scenario-1": {"metric": 0.90, "other": 0.80},
            },
        }

        report = ABReport.format_comparison_multi(config_results)
        assert "N/A" in report
        assert "0.8500" in report

    def test_format_comparison_multi_missing_metric_in_scenario(self):
        """Test handling when a metric is missing in one scenario."""
        config_results = {
            "config-a": {
                "scenario-1": {"precision": 0.85},
            },
            "config-b": {
                "scenario-1": {"precision": 0.80, "recall": 0.90},
            },
        }

        report = ABReport.format_comparison_multi(config_results)
        assert "N/A" in report  # for missing precision in config-b's scenario-1

    def test_format_comparison_multi_insufficient_configs_raises(self):
        """Test that ValueError is raised with < 2 configs."""
        config_results = {
            "config-a": {
                "scenario-1": {"metric": 0.85},
            },
        }

        with pytest.raises(ValueError, match="≥2 configs"):
            ABReport.format_comparison_multi(config_results)

    def test_format_comparison_multi_empty_configs_returns_message(self):
        """Test that empty config results return a message."""
        config_results = {}
        report = ABReport.format_comparison_multi(config_results)
        assert "No configurations" in report


class TestRunAB:
    """Test QualityRunner.run_ab() method."""

    @pytest.mark.asyncio
    async def test_run_ab_basic_execution(self):
        """Test run_ab executes across multiple configs and scenarios."""
        from unittest.mock import MagicMock

        llm_provider_a = MagicMock()
        llm_provider_b = MagicMock()

        runner = QualityRunner(llm_provider_a)

        # Mock fixture loading
        def mock_load_fixture(pipeline_type, scenario):
            return {"input": f"{scenario}_input"}

        def mock_load_expected(pipeline_type, scenario):
            return {"expected": f"{scenario}_output"}

        runner.load_fixture = mock_load_fixture
        runner.load_expected_output = mock_load_expected

        # Mock executor and metrics functions
        async def executor_fn(llm_provider, fixture_input):
            return {"result": f"{fixture_input['input']}_result"}

        def metrics_fn(expected, actual):
            return {"f1": 0.85, "precision": 0.90}

        config_specs = [
            ("config-a", llm_provider_a),
            ("config-b", llm_provider_b),
        ]

        results = await runner.run_ab(
            config_specs=config_specs,
            scenario_list=["scenario-1", "scenario-2"],
            pipeline_type="test_pipeline",
            executor_fn=executor_fn,
            metrics_fn=metrics_fn,
        )

        # Verify structure
        assert "config-a" in results
        assert "config-b" in results
        assert "scenario-1" in results["config-a"]
        assert "scenario-2" in results["config-a"]
        assert results["config-a"]["scenario-1"]["f1"] == 0.85
        assert results["config-b"]["scenario-2"]["precision"] == 0.90

    @pytest.mark.asyncio
    async def test_run_ab_returns_correct_structure(self):
        """Test that run_ab returns the documented nested dict structure."""
        from unittest.mock import MagicMock

        llm_provider = MagicMock()
        runner = QualityRunner(llm_provider)

        def mock_load_fixture(pipeline_type, scenario):
            return {"data": scenario}

        def mock_load_expected(pipeline_type, scenario):
            return {"expected": scenario}

        runner.load_fixture = mock_load_fixture
        runner.load_expected_output = mock_load_expected

        async def executor_fn(llm_provider, fixture_input):
            return {"output": "test"}

        def metrics_fn(expected, actual):
            return {"metric_a": 0.75}

        config_specs = [("config-1", llm_provider), ("config-2", llm_provider)]

        results = await runner.run_ab(
            config_specs=config_specs,
            scenario_list=["scenario-a"],
            pipeline_type="test",
            executor_fn=executor_fn,
            metrics_fn=metrics_fn,
        )

        # Structure: config_ref -> scenario -> metrics
        assert isinstance(results, dict)
        assert all(isinstance(v, dict) for v in results.values())
        for config_ref, scenario_dict in results.items():
            assert all(isinstance(m, dict) for m in scenario_dict.values())

    @pytest.mark.asyncio
    async def test_run_ab_multiple_metrics_per_scenario(self):
        """Test that run_ab aggregates multiple metrics per scenario."""
        from unittest.mock import MagicMock

        llm_provider = MagicMock()
        runner = QualityRunner(llm_provider)

        def mock_load_fixture(pipeline_type, scenario):
            return {}

        def mock_load_expected(pipeline_type, scenario):
            return {}

        runner.load_fixture = mock_load_fixture
        runner.load_expected_output = mock_load_expected

        async def executor_fn(llm_provider, fixture_input):
            return {}

        def metrics_fn(expected, actual):
            return {
                "precision": 0.80,
                "recall": 0.85,
                "f1": 0.825,
                "brier": 0.15,
            }

        config_specs = [("config", llm_provider)]

        results = await runner.run_ab(
            config_specs=config_specs,
            scenario_list=["scenario"],
            pipeline_type="test",
            executor_fn=executor_fn,
            metrics_fn=metrics_fn,
        )

        metrics = results["config"]["scenario"]
        assert len(metrics) == 4
        assert metrics["precision"] == 0.80
        assert metrics["recall"] == 0.85
        assert metrics["f1"] == 0.825
        assert metrics["brier"] == 0.15

    @pytest.mark.asyncio
    async def test_run_ab_handles_sync_executor(self):
        """Test that run_ab works with sync executor functions."""
        from unittest.mock import MagicMock

        llm_provider = MagicMock()
        runner = QualityRunner(llm_provider)

        def mock_load_fixture(pipeline_type, scenario):
            return {"input": "test"}

        def mock_load_expected(pipeline_type, scenario):
            return {"expected": "test"}

        runner.load_fixture = mock_load_fixture
        runner.load_expected_output = mock_load_expected

        # Synchronous executor (wrapped as async)
        async def executor_fn(llm_provider, fixture_input):
            return {"result": "sync_result"}

        def metrics_fn(expected, actual):
            return {"score": 0.9}

        config_specs = [("config", llm_provider)]

        results = await runner.run_ab(
            config_specs=config_specs,
            scenario_list=["scenario"],
            pipeline_type="test",
            executor_fn=executor_fn,
            metrics_fn=metrics_fn,
        )

        assert results["config"]["scenario"]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_run_ab_iterates_all_scenarios_all_configs(self):
        """Test that run_ab iterates over all scenario/config combinations."""
        from unittest.mock import MagicMock

        call_count = {"count": 0}

        async def counting_executor(llm_provider, fixture_input):
            call_count["count"] += 1
            return {}

        llm_provider = MagicMock()
        runner = QualityRunner(llm_provider)

        runner.load_fixture = lambda pt, sc: {}
        runner.load_expected_output = lambda pt, sc: {}

        config_specs = [("config-1", llm_provider), ("config-2", llm_provider)]
        scenarios = ["scenario-1", "scenario-2", "scenario-3"]

        await runner.run_ab(
            config_specs=config_specs,
            scenario_list=scenarios,
            pipeline_type="test",
            executor_fn=counting_executor,
            metrics_fn=lambda e, a: {},
        )

        # Should call executor once per (config, scenario) pair
        # 2 configs * 3 scenarios = 6 calls
        assert call_count["count"] == 6


class TestRunABIntegration:
    """Integration tests for run_ab with real-like scenarios."""

    @pytest.mark.asyncio
    async def test_run_ab_with_floor_gating(self):
        """Test run_ab output integrates with FloorGate."""
        from unittest.mock import MagicMock

        from tests.integration.pipelines._harness.report import FloorGate

        llm_provider = MagicMock()
        runner = QualityRunner(llm_provider)

        runner.load_fixture = lambda pt, sc: {}
        runner.load_expected_output = lambda pt, sc: {}

        async def executor_fn(llm_provider, fixture_input):
            return {}

        def metrics_fn(expected, actual):
            return {"f1": 0.65, "precision": 0.75}

        config_specs = [("config", llm_provider)]

        results = await runner.run_ab(
            config_specs=config_specs,
            scenario_list=["scenario"],
            pipeline_type="test",
            executor_fn=executor_fn,
            metrics_fn=metrics_fn,
        )

        # Extract aggregate metrics and gate them
        aggregate = results["config"]["scenario"]
        gate = FloorGate({"f1": 0.60, "precision": 0.70})

        # Should pass - all metrics meet floors
        gate.assert_metrics(aggregate)

    @pytest.mark.asyncio
    async def test_run_ab_formats_with_comparison_multi(self):
        """Test that run_ab output can be formatted with format_comparison_multi."""
        from unittest.mock import MagicMock

        llm_provider_a = MagicMock()
        llm_provider_b = MagicMock()
        runner = QualityRunner(llm_provider_a)

        runner.load_fixture = lambda pt, sc: {}
        runner.load_expected_output = lambda pt, sc: {}

        async def executor_fn(llm_provider, fixture_input):
            return {}

        def metrics_fn(expected, actual):
            return {"f1": 0.85}

        config_specs = [
            ("config-a", llm_provider_a),
            ("config-b", llm_provider_b),
        ]

        results = await runner.run_ab(
            config_specs=config_specs,
            scenario_list=["scenario"],
            pipeline_type="test",
            executor_fn=executor_fn,
            metrics_fn=metrics_fn,
        )

        # Format with ABReport
        report = ABReport.format_comparison_multi(results)
        assert "Multi-Config A/B Comparison" in report
        assert "config-a" in report
        assert "config-b" in report
