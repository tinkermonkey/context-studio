#!/usr/bin/env python
"""
Interactive CLI for rating pipeline candidates from refinement pipelines.

Fetches runs from the API, presents candidates for human evaluation, and
appends JSONL rows without overwriting existing rater entries.

Usage:
    python rate.py --pipeline definition_refinement --api-url http://localhost:8000
    python rate.py --pipeline connection_refinement --output ratings.jsonl
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

_logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)


def fetch_pipeline_runs(
    api_url: str,
    pipeline_type: str,
    status: Optional[str] = "completed",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Fetch pipeline runs from the API.

    Args:
        api_url: Base URL of the API (e.g., http://localhost:8000)
        pipeline_type: Pipeline type to filter by
        status: Optional status filter (completed, failed, etc.)
        limit: Maximum number of runs to fetch

    Returns:
        List of pipeline run dictionaries

    Raises:
        requests.RequestException: If API call fails
    """
    url = f"{api_url}/api/pipelines/runs"
    params = {
        "pipeline_type": pipeline_type,
        "limit": limit,
    }
    if status:
        params["status"] = status

    _logger.info(f"Fetching runs from {url} with params {params}")
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data.get("items", [])


def fetch_run_candidates(
    api_url: str,
    run_id: str,
) -> list[dict[str, Any]]:
    """
    Fetch candidates for a specific run.

    Args:
        api_url: Base URL of the API
        run_id: Run ID to fetch candidates for

    Returns:
        List of candidate dictionaries

    Raises:
        requests.RequestException: If API call fails
    """
    url = f"{api_url}/api/pipelines/runs/{run_id}/candidates"
    _logger.info(f"Fetching candidates from {url}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.json()


def format_candidate(candidate: dict[str, Any], index: int = 0) -> str:
    """Format a candidate for display."""
    lines = [f"\n--- Candidate {index + 1} ---"]

    if "label" in candidate:
        lines.append(f"Label: {candidate['label']}")

    if "proposed_definition" in candidate:
        lines.append(f"Proposed: {candidate['proposed_definition']}")

    if "current_definition" in candidate:
        lines.append(f"Current: {candidate['current_definition']}")

    if "refined_definition" in candidate:
        lines.append(f"Refined: {candidate['refined_definition']}")

    if "confidence" in candidate:
        lines.append(f"Confidence: {candidate['confidence']:.2%}")

    if "provenance" in candidate:
        lines.append(f"Provenance: {json.dumps(candidate['provenance'])}")

    return "\n".join(lines)


def prompt_for_rating(
    candidate_id: str,
) -> tuple[str, Optional[str]] | tuple[None, None]:
    """
    Prompt user for rating.

    Args:
        candidate_id: ID of the candidate being rated

    Returns:
        Tuple of (rating, rationale) where rating is one of:
        - "accept": The candidate is good
        - "revise": The candidate needs changes
        - "reject": The candidate should not be applied
        Returns (None, None) if user skips

    Raises:
        KeyboardInterrupt: If user cancels
    """
    while True:
        print("\nRate this candidate:")
        print("  [a]ccept - approve this candidate")
        print("  [r]evise - needs changes")
        print("  [j]reject - reject this candidate")
        print("  [s]kip - skip this candidate")
        print("  [q]uit - exit rating")

        choice = input("\nYour choice: ").strip().lower()

        if choice in ("a", "accept"):
            rating = "accept"
            break
        elif choice in ("r", "revise"):
            rating = "revise"
            break
        elif choice in ("j", "reject"):
            rating = "reject"
            break
        elif choice in ("s", "skip"):
            return None, None
        elif choice in ("q", "quit"):
            raise KeyboardInterrupt("User quit")
        else:
            print("Invalid choice. Please try again.")

    rationale = input("Optional rationale (press Enter to skip): ").strip()
    return rating, rationale if rationale else None


def append_rating_jsonl(
    output_file: Path,
    run_id: str,
    candidate_id: str,
    rater: str,
    rating: str,
    rationale: Optional[str] = None,
) -> None:
    """
    Append a rating to a JSONL file.

    Multiple rater entries for the same candidate do not overwrite each other.
    Each rater's entry is appended as a new line.

    Args:
        output_file: Path to JSONL file
        run_id: Run ID
        candidate_id: Candidate ID
        rater: Rater identifier (username, email, etc.)
        rating: Rating value (accept, revise, reject)
        rationale: Optional explanation for the rating
    """
    row = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "rater": rater,
        "rating": rating,
    }
    if rationale:
        row["rationale"] = rationale

    with open(output_file, "a") as f:
        f.write(json.dumps(row) + "\n")

    _logger.info(f"Appended rating: {run_id}/{candidate_id} = {rating} by {rater}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Rate pipeline candidates for human evaluation")
    parser.add_argument(
        "--pipeline",
        required=True,
        choices=["definition_refinement", "connection_refinement"],
        help="Pipeline type to rate",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("_ratings/human_eval.jsonl"),
        help="Output JSONL file for ratings (default: _ratings/human_eval.jsonl)",
    )
    parser.add_argument(
        "--rater",
        required=True,
        help="Rater identifier (username, email, etc.)",
    )
    parser.add_argument(
        "--pipeline-type",
        type=str,
        help="Alternate name for pipeline type if different from --pipeline",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    parser.add_argument(
        "--skip-duplicate",
        action="store_true",
        help="Skip candidates that already have a rating from this rater",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    pipeline_type = args.pipeline_type or f"schema_node_{args.pipeline}"

    try:
        # Ensure output directory exists
        args.output.parent.mkdir(parents=True, exist_ok=True)

        # Load existing ratings if skip_duplicate is enabled
        existing_ratings = {}
        if args.skip_duplicate and args.output.exists():
            with open(args.output, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("rater") == args.rater:
                        key = (entry.get("run_id"), entry.get("candidate_id"))
                        existing_ratings[key] = entry.get("rating")

        # Fetch runs
        _logger.info(f"Fetching {pipeline_type} pipeline runs...")
        runs = fetch_pipeline_runs(
            args.api_url,
            pipeline_type,
            status="completed",
            limit=100,
        )

        if not runs:
            _logger.warning("No runs found")
            return 0

        _logger.info(f"Found {len(runs)} runs")

        # Rate each run's candidates
        total_rated = 0
        total_skipped = 0

        for run in runs:
            run_id = run["id"]
            _logger.info(f"\n=== Run {run_id} ===")

            try:
                candidates = fetch_run_candidates(args.api_url, run_id)
            except requests.RequestException as e:
                _logger.error(f"Failed to fetch candidates for {run_id}: {e}")
                continue

            if not candidates:
                _logger.info(f"No candidates found for {run_id}")
                continue

            _logger.info(f"Found {len(candidates)} candidates")

            for i, candidate in enumerate(candidates):
                candidate_id = candidate.get("id", f"candidate-{i}")

                # Check if already rated by this rater
                if args.skip_duplicate:
                    key = (run_id, candidate_id)
                    if key in existing_ratings:
                        _logger.info(f"Skipping {candidate_id} (already rated by {args.rater})")
                        total_skipped += 1
                        continue

                # Display candidate
                print(format_candidate(candidate, i))

                # Prompt for rating
                try:
                    rating, rationale = prompt_for_rating(candidate_id)
                    if rating is None:
                        _logger.info(f"Skipped {candidate_id}")
                        total_skipped += 1
                        continue

                    # Append to JSONL
                    append_rating_jsonl(
                        args.output,
                        run_id,
                        candidate_id,
                        args.rater,
                        rating,
                        rationale,
                    )
                    total_rated += 1

                except KeyboardInterrupt:
                    _logger.info("User quit")
                    break

        _logger.info("\n=== Summary ===")
        _logger.info(f"Rated: {total_rated}")
        _logger.info(f"Skipped: {total_skipped}")
        _logger.info(f"Output: {args.output}")

        return 0

    except requests.RequestException as e:
        _logger.error(f"API error: {e}")
        return 1
    except KeyboardInterrupt:
        _logger.info("Interrupted")
        return 1
    except Exception as e:
        _logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
