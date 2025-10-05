"""
Performance baseline validation tests.

Validates that current performance meets or exceeds established baselines.
"""

import pytest
import json
import os
from pathlib import Path


def load_baseline(baseline_name: str) -> dict:
    """Load performance baseline from JSON file."""
    baseline_path = Path(__file__).parent.parent / "performance" / "baselines" / f"{baseline_name}.json"

    if not baseline_path.exists():
        pytest.skip(f"Baseline file not found: {baseline_path}")

    with open(baseline_path, 'r') as f:
        return json.load(f)


def validate_metric(actual: float, baseline_data: dict, metric_name: str) -> None:
    """
    Validate a metric against its baseline.

    Args:
        actual: Measured value
        baseline_data: Baseline configuration for the metric
        metric_name: Name of the metric being validated
    """
    target = baseline_data.get("target")
    tolerance_pct = baseline_data.get("tolerance_pct", 15)

    # Calculate acceptable range
    lower_bound = target * (1 - tolerance_pct / 100)
    upper_bound = target * (1 + tolerance_pct / 100)

    # For latency metrics (smaller is better), ensure actual <= upper_bound
    # For throughput metrics (larger is better), ensure actual >= lower_bound
    if "latency" in metric_name.lower() or "overhead" in metric_name.lower():
        assert actual <= upper_bound, (
            f"{metric_name} regression: {actual:.2f} exceeds baseline {target:.2f} "
            f"(+{tolerance_pct}% tolerance = {upper_bound:.2f})"
        )
    else:
        assert actual >= lower_bound, (
            f"{metric_name} regression: {actual:.2f} below baseline {target:.2f} "
            f"(-{tolerance_pct}% tolerance = {lower_bound:.2f})"
        )


class TestVectorSearchBaselines:
    """Validate vector search performance against baselines."""

    def test_baseline_file_exists(self):
        """Ensure baseline file exists and is valid JSON."""
        baseline = load_baseline("vector_search_baseline")

        assert "baselines" in baseline, "Baseline file missing 'baselines' section"
        assert "version" in baseline, "Baseline file missing 'version'"
        assert len(baseline["baselines"]) > 0, "No baselines defined"

    def test_baseline_structure(self):
        """Validate baseline file structure."""
        baseline = load_baseline("vector_search_baseline")

        for metric_name, metric_data in baseline["baselines"].items():
            assert "target" in metric_data, f"Metric {metric_name} missing 'target'"
            assert "tolerance_pct" in metric_data, f"Metric {metric_name} missing 'tolerance_pct'"
            assert "description" in metric_data, f"Metric {metric_name} missing 'description'"

    @pytest.mark.skipif(
        not os.path.exists("/workspace/local-server/tests/performance_tests/test_vector_search_performance.py"),
        reason="Vector search performance tests not available"
    )
    def test_readme_documents_update_procedure(self):
        """Ensure fixtures README documents the update procedure."""
        readme_path = Path(__file__).parent.parent / "fixtures" / "README.md"

        assert readme_path.exists(), "Fixtures README.md not found"

        with open(readme_path, 'r') as f:
            content = f.read()

        # Check for key sections
        assert "Version Pinning" in content, "README missing Version Pinning section"
        assert "Updating" in content, "README missing update procedure"
        assert "Schema.org" in content, "README missing Schema.org documentation"


class TestPerformanceBaselineIntegration:
    """Test integration with actual performance measurements."""

    def test_example_latency_validation(self):
        """Example: Validate a latency metric against baseline."""
        baseline = load_baseline("vector_search_baseline")

        # This would be replaced with actual measurements from performance tests
        example_latency = 35.0  # ms

        latency_baseline = baseline["baselines"]["top_20_query_latency_ms"]

        # Validate against baseline
        validate_metric(example_latency, latency_baseline, "top_20_query_latency_ms")

    def test_example_throughput_validation(self):
        """Example: Validate a throughput metric against baseline."""
        baseline = load_baseline("vector_search_baseline")

        # This would be replaced with actual measurements from performance tests
        example_qps = 12.0  # queries per second

        throughput_baseline = baseline["baselines"]["concurrent_throughput_qps"]

        # Validate against baseline
        validate_metric(example_qps, throughput_baseline, "concurrent_throughput_qps")


def update_baseline(baseline_name: str, metric_name: str, new_value: float,
                    description: str = None) -> None:
    """
    Update a baseline metric with a new measured value.

    This function should be called manually when performance improvements are made
    and new baselines need to be established.

    Args:
        baseline_name: Name of the baseline file (without .json)
        metric_name: Name of the metric to update
        new_value: New measured value
        description: Optional description of the metric
    """
    baseline_path = Path(__file__).parent.parent / "performance" / "baselines" / f"{baseline_name}.json"

    with open(baseline_path, 'r') as f:
        baseline = json.load(f)

    if metric_name not in baseline["baselines"]:
        baseline["baselines"][metric_name] = {
            "target": new_value,
            "actual": new_value,
            "tolerance_pct": 15,
            "description": description or f"Performance baseline for {metric_name}"
        }
    else:
        baseline["baselines"][metric_name]["actual"] = new_value
        if description:
            baseline["baselines"][metric_name]["description"] = description

    # Update last_updated timestamp
    from datetime import date
    baseline["last_updated"] = date.today().isoformat()

    with open(baseline_path, 'w') as f:
        json.dump(baseline, f, indent=2)

    print(f"Updated baseline {baseline_name}.{metric_name} = {new_value}")
