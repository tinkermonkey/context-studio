#!/usr/bin/env python3
"""
Diff benchmarks between current and baseline runs.

Compares metrics across datasets and shows deltas to help guide iteration decisions.
Provides both machine-readable (JSON) and human-readable (Markdown/text) diffs.

Usage:
    python scripts/diff_benchmarks.py \\
      --current reports/comparison.json \\
      --baseline reports/baseline-comparison.json
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import get_logger

_logger = get_logger(__name__)


def load_comparison(file_path: str) -> Optional[dict[str, Any]]:
    """
    Load a comparison JSON file.

    Args:
        file_path: Path to comparison JSON file

    Returns:
        Comparison results dictionary, or None if file does not exist

    Raises:
        json.JSONDecodeError: If file contains invalid JSON
        PermissionError: If file cannot be read due to permission issues
    """
    comparison_file = Path(file_path)
    if not comparison_file.exists():
        return None

    with open(comparison_file) as f:
        return json.load(f)


def compute_delta(current: float, baseline: float) -> tuple[float, str]:
    """
    Compute metric delta and direction.

    Args:
        current: Current metric value
        baseline: Baseline metric value

    Returns:
        Tuple of (delta, direction_str)
    """
    if baseline == 0 and current == 0:
        return 0.0, "→"
    elif baseline == 0:
        return current, "↑" if current > 0 else "↓"
    else:
        delta = current - baseline
        if delta > 0:
            return delta, "↑"
        elif delta < 0:
            return delta, "↓"
        else:
            return 0.0, "→"


def print_metric_diff(
    metric_name: str,
    baseline: float,
    current: float,
    is_cost: bool = False,
) -> None:
    """
    Print a single metric diff line.

    Args:
        metric_name: Human-readable metric name
        baseline: Baseline value
        current: Current value
        is_cost: Whether this is a cost metric (lower is better)
    """
    delta, direction = compute_delta(current, baseline)

    if is_cost:
        print(f"  {metric_name:20s} ${baseline:7.2f} → ${current:7.2f} ({direction} ${delta:+7.2f})")
    else:
        print(f"  {metric_name:20s} {baseline:7.4f} → {current:7.4f} ({direction} {delta:+7.4f})")


def print_summary_diff(
    current: dict[str, Any],
    baseline: Optional[dict[str, Any]],
) -> None:
    """
    Print a human-readable summary diff.

    Args:
        current: Current comparison results
        baseline: Baseline comparison results (or None if no baseline)
    """
    print("\n" + "=" * 80)
    print("BENCHMARK DIFF SUMMARY")
    print("=" * 80)

    if baseline is None:
        print("\nℹ️  No baseline found. This is the first run or baseline not available.")
        print("   Current results will be used as reference for future iterations.\n")
        print("Current Results:")
        print("-" * 80)
    else:
        print("\nComparing against baseline...")
        print("-" * 80)

    # Get datasets from current
    datasets = current.get("datasets", [])
    if not datasets:
        print("No datasets found in current comparison")
        return

    aggregate_current = current.get("aggregate_stats", {}).get("by_dataset", {})
    aggregate_baseline = baseline.get("aggregate_stats", {}).get("by_dataset", {}) if baseline else {}

    for dataset in datasets:
        print(f"\n📊 Dataset: {dataset}")
        print("-" * 40)

        current_stats = aggregate_current.get(dataset, {})
        baseline_stats = aggregate_baseline.get(dataset, {})

        if not baseline_stats:
            # No baseline - just show current
            print(f"  Avg Precision:     {current_stats.get('avg_precision', 0.0):.4f}")
            print(f"  Avg Recall:        {current_stats.get('avg_recall', 0.0):.4f}")
            print(f"  Avg F1:            {current_stats.get('avg_f1', 0.0):.4f}")
            print(f"  Avg Conformance:   {current_stats.get('avg_conformance', 0.0):.4f}")
            print(f"  Total Cost:        ${current_stats.get('total_cost_usd', 0.0):.2f}")
        else:
            # Compare with baseline
            print_metric_diff(
                "Avg Precision",
                baseline_stats.get("avg_precision", 0.0),
                current_stats.get("avg_precision", 0.0),
            )
            print_metric_diff(
                "Avg Recall",
                baseline_stats.get("avg_recall", 0.0),
                current_stats.get("avg_recall", 0.0),
            )
            print_metric_diff(
                "Avg F1",
                baseline_stats.get("avg_f1", 0.0),
                current_stats.get("avg_f1", 0.0),
            )
            print_metric_diff(
                "Avg Conformance",
                baseline_stats.get("avg_conformance", 0.0),
                current_stats.get("avg_conformance", 0.0),
            )
            print_metric_diff(
                "Total Cost",
                baseline_stats.get("total_cost_usd", 0.0),
                current_stats.get("total_cost_usd", 0.0),
                is_cost=True,
            )

    print("\n" + "=" * 80)
    print("DECISION GUIDANCE")
    print("=" * 80)

    # Compute overall metrics
    all_current_f1 = []
    for dataset in datasets:
        stats = aggregate_current.get(dataset, {})
        if stats.get("avg_f1") is not None:
            all_current_f1.append(stats["avg_f1"])

    all_baseline_f1 = []
    if baseline:
        for dataset in datasets:
            stats = aggregate_baseline.get(dataset, {})
            if stats.get("avg_f1") is not None:
                all_baseline_f1.append(stats["avg_f1"])

    if all_current_f1:
        current_avg_f1 = sum(all_current_f1) / len(all_current_f1)
        print(f"\n📈 Current average F1 across datasets: {current_avg_f1:.4f}")

        if all_baseline_f1:
            baseline_avg_f1 = sum(all_baseline_f1) / len(all_baseline_f1)
            f1_delta = current_avg_f1 - baseline_avg_f1

            if f1_delta > 0.05:
                print(f"✅ F1 improved by {f1_delta:+.4f} — likely ready to promote")
            elif f1_delta > 0:
                print(f"⚠️  F1 improved by {f1_delta:+.4f} — marginal improvement, check for regressions")
            elif f1_delta > -0.05:
                print(f"⚠️  F1 declined by {abs(f1_delta):.4f} — investigate regression")
            else:
                print(f"❌ F1 declined significantly ({f1_delta:.4f}) — do not promote")
        else:
            print("   (No baseline for comparison)")

    print("\n" + "=" * 80 + "\n")


def print_json_diff(
    current: dict[str, Any],
    baseline: Optional[dict[str, Any]],
    output_path: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate and optionally save JSON diff output.

    Args:
        current: Current comparison results
        baseline: Baseline comparison results
        output_path: Optional path to save JSON diff

    Returns:
        Dictionary with current, baseline, and delta metrics by dataset
    """
    diff: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "current_timestamp": current.get("timestamp"),
        "baseline_timestamp": baseline.get("timestamp") if baseline else None,
        "has_baseline": baseline is not None,
        "datasets": {},
    }

    datasets = current.get("datasets", [])
    aggregate_current = current.get("aggregate_stats", {}).get("by_dataset", {})
    aggregate_baseline = baseline.get("aggregate_stats", {}).get("by_dataset", {}) if baseline else {}

    for dataset in datasets:
        current_stats = aggregate_current.get(dataset, {})
        baseline_stats = aggregate_baseline.get(dataset, {})

        current_f1 = current_stats.get("avg_f1", 0.0)
        baseline_f1 = baseline_stats.get("avg_f1", 0.0) if baseline_stats else None

        diff["datasets"][dataset] = {
            "current": {
                "avg_f1": current_f1,
                "avg_precision": current_stats.get("avg_precision", 0.0),
                "avg_recall": current_stats.get("avg_recall", 0.0),
                "total_cost_usd": current_stats.get("total_cost_usd", 0.0),
            },
            "baseline": (
                {
                    "avg_f1": baseline_f1,
                    "avg_precision": baseline_stats.get("avg_precision", 0.0),
                    "avg_recall": baseline_stats.get("avg_recall", 0.0),
                    "total_cost_usd": baseline_stats.get("total_cost_usd", 0.0),
                }
                if baseline_stats
                else None
            ),
            "delta": (
                {
                    "f1": current_f1 - baseline_f1,
                    "precision": current_stats.get("avg_precision", 0.0)
                    - baseline_stats.get("avg_precision", 0.0),
                    "recall": current_stats.get("avg_recall", 0.0)
                    - baseline_stats.get("avg_recall", 0.0),
                    "cost_usd": current_stats.get("total_cost_usd", 0.0)
                    - baseline_stats.get("total_cost_usd", 0.0),
                }
                if baseline_stats
                else None
            ),
        }

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(diff, f, indent=2)
        _logger.info(f"Saved JSON diff to {output_file}")

    return diff


def main():
    """Command-line interface for benchmark diffing."""
    parser = argparse.ArgumentParser(
        description="Diff current benchmark results against baseline"
    )
    parser.add_argument(
        "--current",
        type=str,
        required=True,
        help="Path to current comparison JSON file",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default="reports/baseline-comparison.json",
        help="Path to baseline comparison JSON file (optional)",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional path to save JSON diff output",
    )

    args = parser.parse_args()

    try:
        # Load current results
        current = load_comparison(args.current)
        if not current:
            _logger.error(f"Current comparison file not found: {args.current}")
            return 1
    except json.JSONDecodeError as e:
        _logger.error(f"Invalid JSON in current comparison file: {e}", exc_info=True)
        return 1
    except PermissionError as e:
        _logger.error(f"Permission denied reading current comparison file: {e}", exc_info=True)
        return 1

    try:
        # Load baseline if it exists
        baseline = load_comparison(args.baseline)
        if not baseline:
            _logger.info(f"No baseline found at {args.baseline} — running in baseline-establishment mode")
    except json.JSONDecodeError as e:
        _logger.error(f"Invalid JSON in baseline comparison file: {e}", exc_info=True)
        return 1
    except PermissionError as e:
        _logger.error(f"Permission denied reading baseline comparison file: {e}", exc_info=True)
        return 1

    # Print human-readable summary
    print_summary_diff(current, baseline)

    # Generate and optionally save JSON diff
    print_json_diff(current, baseline, args.json_out)

    # Print agent-readable decision hints
    print("\n📋 AGENT-READABLE METADATA\n")
    datasets = current.get("datasets", [])
    aggregate_current = current.get("aggregate_stats", {}).get("by_dataset", {})
    aggregate_baseline = baseline.get("aggregate_stats", {}).get("by_dataset", {}) if baseline else {}

    all_improvements = []
    all_regressions = []

    for dataset in datasets:
        current_stats = aggregate_current.get(dataset, {})
        baseline_stats = aggregate_baseline.get(dataset, {})
        current_f1 = current_stats.get("avg_f1", 0.0)

        if baseline_stats:
            baseline_f1 = baseline_stats.get("avg_f1", 0.0)
            f1_delta = current_f1 - baseline_f1

            if f1_delta > 0.01:
                all_improvements.append((dataset, f1_delta, current_f1))
            elif f1_delta < -0.01:
                all_regressions.append((dataset, abs(f1_delta), baseline_f1))

    if all_improvements:
        print("✅ IMPROVEMENTS:")
        for dataset, delta, current_f1 in all_improvements:
            print(f"   {dataset}: F1 +{delta:.4f} (now {current_f1:.4f})")

    if all_regressions:
        print("\n❌ REGRESSIONS:")
        for dataset, delta, baseline_f1 in all_regressions:
            print(f"   {dataset}: F1 -{delta:.4f} (was {baseline_f1:.4f})")

    if not all_improvements and not all_regressions:
        print("→ No significant changes from baseline")

    return 0


if __name__ == "__main__":
    sys.exit(main())
