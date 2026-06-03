#!/usr/bin/env python
"""
Aggregates human evaluation ratings into metrics.

Reads JSONL ratings from multiple raters and computes:
- accept_rate: Percentage of candidates rated as 'accept'
- revise_rate: Percentage of candidates rated as 'revise'
- reject_rate: Percentage of candidates rated as 'reject'
- n: Total number of rated candidates

Metrics are computed per (config_ref, config_version) and written to _metrics/
with source: "human_eval" using the standard envelope.

Usage:
    python aggregate.py --ratings _ratings/human_eval.jsonl --pipeline definition_refinement
    python aggregate.py --ratings _ratings/human_eval.jsonl --output _metrics/human_eval.jsonl
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)


def load_ratings(ratings_file: Path) -> list[dict[str, Any]]:
    """
    Load JSONL ratings from a file.

    Args:
        ratings_file: Path to JSONL file

    Returns:
        List of rating dictionaries

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is malformed
    """
    if not ratings_file.exists():
        _logger.warning(f"Ratings file not found: {ratings_file}")
        return []

    ratings = []
    with open(ratings_file, "r") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                ratings.append(json.loads(line))
            except json.JSONDecodeError as e:
                _logger.error(f"Line {line_num}: {e}")
                raise

    return ratings


def fetch_run_metadata(
    ratings: list[dict[str, Any]],
    api_url: str,
    pipeline_type: str,
) -> dict[str, dict[str, Any]]:
    """
    Fetch run metadata from the API to get config_ref and config_version.

    Args:
        ratings: List of rating dictionaries
        api_url: Base URL of the API
        pipeline_type: Pipeline type to fetch metadata for

    Returns:
        Dict mapping run_id → {config_ref, config_version, ...}
    """
    try:
        import requests

        run_ids: set[str] = {
            str(r.get("run_id"))
            for r in ratings
            if r.get("run_id")
        }
        if not run_ids:
            return {}

        metadata: dict[str, dict[str, Any]] = {}
        for run_id in run_ids:
            try:
                url = f"{api_url}/api/pipelines/runs/{run_id}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                run = response.json()
                metadata[run_id] = {
                    "config_ref": run.get("configuration_ref"),
                    "config_version": run.get("configuration_version"),
                    "implementation_id": run.get("implementation_id"),
                }
            except Exception as e:
                _logger.warning(f"Failed to fetch metadata for {run_id}: {e}")

        return metadata

    except ImportError:
        _logger.warning("requests library not available; skipping API metadata fetch")
        return {}


def aggregate_ratings(
    ratings: list[dict[str, Any]],
    run_metadata: dict[str, dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
    """
    Aggregate ratings per (config_ref, config_version).

    Args:
        ratings: List of rating dictionaries
        run_metadata: Dict mapping run_id → {config_ref, config_version}

    Returns:
        Dict mapping (config_ref, config_version) → {
            accept_count, revise_count, reject_count, n,
            accept_rate, revise_rate, reject_rate
        }
    """
    # Group ratings by (config_ref, config_version)
    groups: dict[tuple[str, int], dict[str, int]] = defaultdict(
        lambda: {"accept": 0, "revise": 0, "reject": 0, "total": 0}
    )

    for rating in ratings:
        run_id = rating.get("run_id")
        rating_value = rating.get("rating")

        # Get config info from metadata
        metadata = run_metadata.get(str(run_id) if run_id else "", {})
        config_ref: str = metadata.get("config_ref", "unknown")
        config_version: int = metadata.get("config_version", 0)

        # If metadata is unavailable, try to infer from ratings themselves
        # (though this is less reliable)
        if config_ref == "unknown":
            # Try to extract from rating if it has config info
            config_ref = str(rating.get("config_ref", "unknown"))
            config_version = int(rating.get("config_version", 0))

        key = (config_ref, config_version)

        if rating_value in ("accept", "revise", "reject"):
            groups[key][rating_value] += 1
            groups[key]["total"] += 1

    # Compute rates
    result = {}
    for key, counts in groups.items():
        total = counts["total"]
        if total > 0:
            result[key] = {
                "accept_count": counts["accept"],
                "revise_count": counts["revise"],
                "reject_count": counts["reject"],
                "n": total,
                "accept_rate": round(counts["accept"] / total, 4),
                "revise_rate": round(counts["revise"] / total, 4),
                "reject_rate": round(counts["reject"] / total, 4),
            }

    return result


def emit_metrics_jsonl(
    output_file: Path,
    aggregated: dict[tuple[str, int], dict[str, Any]],
    pipeline_type: str,
    model: str = "human_eval",
    scenario: str = "human_evaluation",
) -> None:
    """
    Emit aggregated metrics as JSONL rows.

    Args:
        output_file: Path to output JSONL file
        aggregated: Dict of aggregated metrics
        pipeline_type: Pipeline type for metrics
        model: Model identifier (default: human_eval)
        scenario: Scenario identifier (default: human_evaluation)
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "a") as f:
        for (config_ref, config_version), metrics in aggregated.items():
            row = {
                "schema_version": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": None,
                "pipeline_type": pipeline_type,
                "scenario": scenario,
                "model": model,
                "config_ref": config_ref,
                "config_version": config_version,
                "mode": "human_eval",
                "source": "human_eval",
                "duration_ms": 0.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "metrics": {
                    "accept_rate": metrics["accept_rate"],
                    "revise_rate": metrics["revise_rate"],
                    "reject_rate": metrics["reject_rate"],
                },
            }
            f.write(json.dumps(row) + "\n")
            _logger.info(
                f"Emitted metrics for {config_ref} v{config_version}: "
                f"accept={metrics['accept_rate']}, revise={metrics['revise_rate']}, "
                f"reject={metrics['reject_rate']} (n={metrics['n']})"
            )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Aggregate human evaluation ratings into metrics"
    )
    parser.add_argument(
        "--ratings",
        type=Path,
        default=Path("_ratings/human_eval.jsonl"),
        help="Input JSONL file with ratings (default: _ratings/human_eval.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("_metrics/human_eval.jsonl"),
        help="Output JSONL file for metrics (default: _metrics/human_eval.jsonl)",
    )
    parser.add_argument(
        "--pipeline",
        default="schema_node_definition_refinement",
        help="Pipeline type for metrics (default: schema_node_definition_refinement)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the API for fetching run metadata (optional)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        # Load ratings
        _logger.info(f"Loading ratings from {args.ratings}")
        ratings = load_ratings(args.ratings)

        if not ratings:
            _logger.warning("No ratings found")
            return 0

        _logger.info(f"Loaded {len(ratings)} ratings")

        # Fetch run metadata
        _logger.info("Fetching run metadata from API...")
        run_metadata = fetch_run_metadata(ratings, args.api_url, args.pipeline)

        # Aggregate ratings
        _logger.info("Aggregating ratings...")
        aggregated = aggregate_ratings(ratings, run_metadata)

        if not aggregated:
            _logger.warning("No aggregated metrics found")
            return 0

        _logger.info(f"Aggregated into {len(aggregated)} metric rows")

        # Emit metrics
        _logger.info(f"Writing metrics to {args.output}")
        emit_metrics_jsonl(args.output, aggregated, args.pipeline)

        _logger.info("Done")
        return 0

    except FileNotFoundError as e:
        _logger.error(f"File not found: {e}")
        return 1
    except json.JSONDecodeError as e:
        _logger.error(f"JSON error: {e}")
        return 1
    except Exception as e:
        _logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
