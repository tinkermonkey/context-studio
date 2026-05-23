"""
Unit tests for diff_benchmarks script.

Tests metric delta computation, cost direction logic, and JSON diff generation.
"""

import sys
from io import StringIO

from scripts.diff_benchmarks import compute_delta, print_json_diff, print_metric_diff


class TestComputeDelta:
    """Tests for compute_delta function."""

    def test_positive_delta(self):
        """Positive delta should return upward arrow."""
        delta, direction = compute_delta(0.8, 0.7)
        assert abs(delta - 0.1) < 1e-9
        assert direction == "↑"

    def test_negative_delta(self):
        """Negative delta should return downward arrow."""
        delta, direction = compute_delta(0.6, 0.7)
        assert abs(delta - (-0.1)) < 1e-9
        assert direction == "↓"

    def test_zero_delta(self):
        """Zero delta should return rightward arrow."""
        delta, direction = compute_delta(0.7, 0.7)
        assert delta == 0.0
        assert direction == "→"

    def test_both_zero(self):
        """When both are zero, delta is zero and direction is rightward."""
        delta, direction = compute_delta(0.0, 0.0)
        assert delta == 0.0
        assert direction == "→"

    def test_from_zero_positive(self):
        """From zero to positive should be upward."""
        delta, direction = compute_delta(5.0, 0.0)
        assert delta == 5.0
        assert direction == "↑"

    def test_from_zero_negative(self):
        """From zero to negative should be downward."""
        delta, direction = compute_delta(-5.0, 0.0)
        assert delta == -5.0
        assert direction == "↓"


class TestPrintMetricDiff:
    """Tests for print_metric_diff function."""

    def test_metric_diff_quality(self):
        """Quality metric (higher is better) shows correct direction."""
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            print_metric_diff("Avg F1", 0.7000, 0.7500, is_cost=False)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        assert "↑" in output
        assert "+0.0500" in output

    def test_metric_diff_cost_increase(self):
        """Cost metric going UP should show UP arrow (cost is bad when it increases)."""
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            print_metric_diff("Total Cost", 5.00, 8.00, is_cost=True)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        # Cost increased from 5 to 8, so delta is +3.00 and direction is ↑ (bad)
        assert "↑" in output
        assert "+3.00" in output

    def test_metric_diff_cost_decrease(self):
        """Cost metric going DOWN should show DOWN arrow (cost decrease is good)."""
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            print_metric_diff("Total Cost", 8.00, 5.00, is_cost=True)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        # Cost decreased from 8 to 5, so delta is -3.00 and direction is ↓ (good)
        assert "↓" in output
        assert "-3.00" in output


class TestPrintJsonDiff:
    """Tests for print_json_diff function."""

    def test_json_diff_without_baseline(self):
        """JSON diff without baseline should have has_baseline=False."""
        current = {
            "timestamp": "2026-05-08T00:00:00Z",
            "datasets": ["tekgen"],
            "aggregate_stats": {
                "by_dataset": {
                    "tekgen": {
                        "avg_f1": 0.7500,
                        "avg_precision": 0.8000,
                        "avg_recall": 0.7000,
                        "total_cost_usd": 25.50,
                    }
                }
            },
        }

        diff = print_json_diff(current, None)

        assert diff["has_baseline"] is False
        assert diff["baseline_timestamp"] is None
        assert "tekgen" in diff["datasets"]
        assert diff["datasets"]["tekgen"]["baseline"] is None
        assert diff["datasets"]["tekgen"]["delta"] is None

    def test_json_diff_with_baseline(self):
        """JSON diff with baseline should compute deltas."""
        current = {
            "timestamp": "2026-05-08T00:00:00Z",
            "datasets": ["tekgen"],
            "aggregate_stats": {
                "by_dataset": {
                    "tekgen": {
                        "avg_f1": 0.7500,
                        "avg_precision": 0.8000,
                        "avg_recall": 0.7000,
                        "total_cost_usd": 25.50,
                    }
                }
            },
        }

        baseline = {
            "timestamp": "2026-05-01T00:00:00Z",
            "datasets": ["tekgen"],
            "aggregate_stats": {
                "by_dataset": {
                    "tekgen": {
                        "avg_f1": 0.7000,
                        "avg_precision": 0.7500,
                        "avg_recall": 0.6500,
                        "total_cost_usd": 20.00,
                    }
                }
            },
        }

        diff = print_json_diff(current, baseline)

        assert diff["has_baseline"] is True
        assert diff["baseline_timestamp"] == baseline["timestamp"]
        assert "tekgen" in diff["datasets"]

        tekgen_diff = diff["datasets"]["tekgen"]
        assert abs(tekgen_diff["delta"]["f1"] - 0.0500) < 1e-9  # 0.75 - 0.70
        assert abs(tekgen_diff["delta"]["precision"] - 0.0500) < 1e-9  # 0.80 - 0.75
        assert abs(tekgen_diff["delta"]["recall"] - 0.0500) < 1e-9  # 0.70 - 0.65
        assert abs(tekgen_diff["delta"]["cost_usd"] - 5.50) < 1e-9  # 25.50 - 20.00
