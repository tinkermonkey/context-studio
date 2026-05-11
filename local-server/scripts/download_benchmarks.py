#!/usr/bin/env python3
"""
Download Text2KGBench datasets from HuggingFace.

This script downloads Text2KGBench datasets from HuggingFace and caches them locally
for benchmarking purposes. Supports multiple dataset tracks.

Supported datasets:
- text2kg-bench/wikidata-tekgen (10 ontologies)
- text2kg-bench/dbpedia-webnlg (19 ontologies)

Usage:
    python scripts/download_benchmarks.py --dataset text2kg-bench/wikidata-tekgen
    python scripts/download_benchmarks.py --dataset text2kg-bench/dbpedia-webnlg
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Ensure local-server is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import load_dataset  # type: ignore[import-untyped]
from utils.logger import get_logger

_logger = get_logger(__name__)


def download_benchmark_dataset(dataset_name: str, split: str = "test", output_dir: str | None = None) -> Path:
    """
    Download a benchmark dataset from HuggingFace.

    Args:
        dataset_name: HuggingFace dataset identifier (e.g., 'text2kg-bench/text2kgbench')
        split: Dataset split to download (e.g., 'test', 'train', 'validation')
        output_dir: Output directory for dataset files. Defaults to datafiles/benchmarks/{dataset_name}/

    Returns:
        Path to the downloaded dataset directory

    Raises:
        ValueError: If dataset cannot be downloaded
        OSError: If output directory cannot be created
    """
    if output_dir is None:
        # Default to datafiles/benchmarks/{org/project}/
        parts = dataset_name.split("/")
        if len(parts) == 2:
            org, project = parts
            output_dir = f"datafiles/benchmarks/{org}/{project}"
        else:
            raise ValueError(f"Invalid dataset name format: {dataset_name}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    _logger.info(f"Downloading {dataset_name} ({split} split) to {output_path}")

    try:
        # Load the dataset from HuggingFace (without trust_remote_code for safety)
        dataset = load_dataset(
            dataset_name,
            split=split,
        )
        _logger.info(f"Downloaded {len(dataset)} samples")

        # Save to local JSONL file for easier access
        output_file = output_path / f"{split}.jsonl"
        _logger.info(f"Saving to {output_file}")

        # Save as JSONL
        with open(output_file, "w") as f:
            for item in dataset:
                f.write(json.dumps(item) + "\n")

        _logger.info(f"Successfully saved {len(dataset)} samples to {output_file}")
        return output_path

    except Exception as e:
        _logger.error(f"Failed to download dataset {dataset_name}: {e}")
        _logger.error("Dataset may not be available yet. Check:")
        _logger.error(f"  - https://huggingface.co/datasets/{dataset_name}")
        _logger.error("  - Correct dataset name and accessibility")
        raise


def main():
    """Command-line interface for downloading benchmark datasets."""
    parser = argparse.ArgumentParser(
        description="Download benchmark datasets from HuggingFace"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="text2kg-bench/wikidata-tekgen",
        help="HuggingFace dataset identifier (default: text2kg-bench/wikidata-tekgen)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Dataset split to download (default: test)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for dataset files (optional)",
    )

    args = parser.parse_args()

    try:
        output_path = download_benchmark_dataset(
            args.dataset,
            split=args.split,
            output_dir=args.output_dir,
        )
        _logger.info(f"Dataset downloaded to: {output_path}")
        return 0
    except Exception as e:
        _logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
