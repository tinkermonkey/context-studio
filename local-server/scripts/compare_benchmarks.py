#!/usr/bin/env python3
"""
Compare benchmark results across datasets.

This script takes two or more benchmark result JSON files and generates
a cross-dataset comparison report showing side-by-side metrics (F1, precision, recall).

Usage:
    python scripts/compare_benchmarks.py \\
      --results reports/tekgen.json reports/webnlg.json \\
      --out reports/comparison.json
"""

import os
import sys
import json
import argparse
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import get_logger

_logger = get_logger(__name__)


def load_results_file(file_path: str) -> dict[str, Any]:
    """
    Load a benchmark results JSON file.

    Args:
        file_path: Path to JSON results file

    Returns:
        Benchmark results dictionary

    Raises:
        FileNotFoundError: If file not found
        json.JSONDecodeError: If JSON is invalid
    """
    results_file = Path(file_path)
    if not results_file.exists():
        raise FileNotFoundError(f"Results file not found: {file_path}")

    with open(results_file) as f:
        results = json.load(f)

    return results


def build_comparison_matrix(
    results_by_dataset: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Build a comparison matrix across datasets.

    Compares metrics for each ontology across all datasets.

    Args:
        results_by_dataset: Dict mapping dataset name to results dict

    Returns:
        Comparison matrix with side-by-side metrics
    """
    # Collect all unique ontologies
    all_ontologies: set[str] = set()
    for results in results_by_dataset.values():
        for result in results.get("results", []):
            all_ontologies.add(result["ontology"])

    ontologies = sorted(list(all_ontologies))

    # Build comparison table
    comparison: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "datasets": list(results_by_dataset.keys()),
        "ontologies_count": len(ontologies),
        "ontology_comparisons": [],
    }

    for ontology in ontologies:
        ontology_data: dict[str, Any] = {
            "ontology": ontology,
            "datasets": {},
        }

        for dataset_name, results in results_by_dataset.items():
            matching_result = None
            for result in results.get("results", []):
                if result["ontology"] == ontology:
                    matching_result = result
                    break

            if matching_result:
                ontology_data["datasets"][dataset_name] = {
                    "precision": matching_result["precision"],
                    "recall": matching_result["recall"],
                    "f1": matching_result["f1"],
                    "conformance": matching_result["conformance"],
                    "samples_processed": matching_result["samples_processed"],
                    "cost_usd": matching_result["cost_usd"],
                }
            else:
                ontology_data["datasets"][dataset_name] = {
                    "precision": None,
                    "recall": None,
                    "f1": None,
                    "conformance": None,
                    "samples_processed": 0,
                    "cost_usd": 0.0,
                }

        comparison["ontology_comparisons"].append(ontology_data)

    # Compute aggregate statistics
    aggregate_stats: dict[str, Any] = {
        "by_dataset": {},
    }

    for dataset_name, results in results_by_dataset.items():
        dataset_results = results.get("results", [])
        if not dataset_results:
            continue

        precisions = [
            r["precision"] for r in dataset_results if r["precision"] is not None
        ]
        recalls = [r["recall"] for r in dataset_results if r["recall"] is not None]
        f1s = [r["f1"] for r in dataset_results if r["f1"] is not None]
        conformances = [
            r["conformance"] for r in dataset_results if r["conformance"] is not None
        ]

        aggregate_stats["by_dataset"][dataset_name] = {
            "avg_precision": sum(precisions) / len(precisions) if precisions else 0.0,
            "avg_recall": sum(recalls) / len(recalls) if recalls else 0.0,
            "avg_f1": sum(f1s) / len(f1s) if f1s else 0.0,
            "avg_conformance": (
                sum(conformances) / len(conformances) if conformances else 0.0
            ),
            "total_samples": results.get("samples_processed", 0),
            "total_cost_usd": results.get("total_cost_usd", 0.0),
            "ontologies_count": results.get("ontologies_count", 0),
        }

    comparison["aggregate_stats"] = aggregate_stats

    return comparison


def save_json_comparison(comparison: dict[str, Any], output_path: str) -> Path:
    """Save comparison results as JSON."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(comparison, f, indent=2)

    _logger.info(f"Saved JSON comparison to {output_file}")
    return output_file


def save_markdown_comparison(
    comparison: dict[str, Any],
    results_by_dataset: dict[str, dict[str, Any]],
    output_path: str,
) -> Path:
    """Save comparison results as Markdown."""
    output_file = Path(output_path).with_suffix(".md")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Cross-Dataset Benchmark Comparison",
        "",
        f"**Generated:** {timestamp}",
        "",
        "## Summary",
        "",
    ]

    # Add dataset info
    datasets_info = []
    for dataset_name, results in results_by_dataset.items():
        datasets_info.append(
            f"- **{dataset_name}**: {results.get('ontologies_count', 0)} ontologies, "
            f"{results.get('samples_processed', 0)} samples, "
            f"${results.get('total_cost_usd', 0.0):.2f}"
        )

    lines.extend(datasets_info)
    lines.append("")

    # Aggregate statistics
    lines.extend(
        [
            "## Aggregate Statistics",
            "",
        ]
    )

    for dataset_name, stats in (
        comparison.get("aggregate_stats", {}).get("by_dataset", {}).items()
    ):
        lines.extend(
            [
                f"### {dataset_name}",
                "",
                f"- **Average Precision:** {stats['avg_precision']:.3f}",
                f"- **Average Recall:** {stats['avg_recall']:.3f}",
                f"- **Average F1:** {stats['avg_f1']:.3f}",
                f"- **Average Conformance:** {stats['avg_conformance']:.3f}",
                "",
            ]
        )

    # Detailed ontology comparison
    lines.extend(
        [
            "## Ontology-by-Ontology Comparison",
            "",
        ]
    )

    datasets_list = comparison.get("datasets", [])
    if datasets_list:
        # Create header row with separate columns for each metric
        header = "| Ontology |"
        separator = "|----------|"

        for dataset in datasets_list:
            header += f" {dataset} P | {dataset} R | {dataset} F1 |"
            separator += "---|---|---|"

        lines.append(header)
        lines.append(separator)

        # Add rows for each ontology
        for ontology_data in comparison.get("ontology_comparisons", []):
            row = f"| {ontology_data['ontology']} |"

            for dataset in datasets_list:
                dataset_metrics = ontology_data["datasets"].get(dataset, {})
                if dataset_metrics.get("f1") is not None:
                    precision = dataset_metrics["precision"]
                    recall = dataset_metrics["recall"]
                    f1 = dataset_metrics["f1"]
                    row += f" {precision:.3f} | {recall:.3f} | {f1:.3f} |"
                else:
                    row += " N/A | N/A | N/A |"

            lines.append(row)

    lines.extend(
        [
            "",
            "## Metrics Explanation",
            "",
            "- **Precision:** Proportion of predicted triples that match ground truth",
            "- **Recall:** Proportion of ground truth triples that were predicted",
            "- **F1:** Harmonic mean of precision and recall",
            "- **Conformance:** Proportion of triples with valid format and confidence (0-1)",
            "",
            "---",
            f"*Cross-dataset comparison generated on {timestamp}*",
        ]
    )

    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    _logger.info(f"Saved Markdown comparison to {output_file}")
    return output_file


def main():
    """Command-line interface for benchmark comparison."""
    parser = argparse.ArgumentParser(
        description="Compare benchmark results across datasets"
    )
    parser.add_argument(
        "--results",
        type=str,
        nargs="+",
        required=True,
        help="Paths to JSON results files to compare",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output path for comparison report (default: reports/comparison-YYYY-MM-DD.json)",
    )

    args = parser.parse_args()

    # Default output path
    if args.out is None:
        today = datetime.now().strftime("%Y-%m-%d")
        args.out = f"reports/comparison-{today}.json"

    try:
        _logger.info(f"Loading {len(args.results)} results files")

        results_by_dataset = {}
        for result_file in args.results:
            _logger.info(f"Loading {result_file}")
            results = load_results_file(result_file)
            dataset_name = results.get("dataset", Path(result_file).stem)
            results_by_dataset[dataset_name] = results

        _logger.info(
            f"Building comparison matrix across {len(results_by_dataset)} datasets"
        )
        comparison = build_comparison_matrix(results_by_dataset)

        # Save reports
        json_path = save_json_comparison(comparison, args.out)
        md_path = save_markdown_comparison(comparison, results_by_dataset, args.out)

        _logger.info("Comparison complete!")
        _logger.info(f"JSON report: {json_path}")
        _logger.info(f"Markdown report: {md_path}")

        return 0

    except Exception as e:
        _logger.error(f"Comparison failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
