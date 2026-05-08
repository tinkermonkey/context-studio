#!/usr/bin/env python3
"""
Run benchmark harness for Text2KGBench datasets (TekGen, DBpedia-WebNLG, etc).

This script:
1. Loads a Text2KGBench dataset from HuggingFace
2. Runs extraction against all ontologies in the dataset via the extraction API
3. Computes precision, recall, F1, and conformance metrics for each ontology
4. Generates machine-readable (JSON) and human-readable (Markdown) reports
5. Optionally generates cross-dataset comparison reports

Supported datasets:
- text2kg-bench/wikidata-tekgen (10 ontologies)
- text2kg-bench/dbpedia-webnlg (19 ontologies)

## Quick Start

From a clean checkout:

    cd local-server
    python -m venv .venv
    source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows
    pip install -r requirements.txt

    # Start the extraction API server (in another terminal)
    python app.py

    # Download datasets (optional, harness will fetch from HuggingFace if not cached)
    python scripts/download_benchmarks.py --dataset text2kg-bench/wikidata-tekgen
    python scripts/download_benchmarks.py --dataset text2kg-bench/dbpedia-webnlg

    # Run the benchmark
    python scripts/run_benchmark.py \\
      --dataset text2kg-bench/wikidata-tekgen \\
      --pipeline configs/extraction-default.json \\
      --out reports/tekgen.json

    python scripts/run_benchmark.py \\
      --dataset text2kg-bench/dbpedia-webnlg \\
      --pipeline configs/extraction-default.json \\
      --out reports/webnlg.json

    # Generate cross-dataset comparison
    python scripts/compare_benchmarks.py \\
      --results reports/tekgen.json reports/webnlg.json \\
      --out reports/comparison.json

## Output

The benchmark generates two reports in local-server/reports/:
- `{dataset}-YYYY-MM-DD.json`: Machine-readable results for agent analysis
- `{dataset}-YYYY-MM-DD.md`: Human-readable summary with metrics table

Cross-dataset comparison generates:
- `comparison-YYYY-MM-DD.json`: Machine-readable comparison data
- `comparison-YYYY-MM-DD.md`: Human-readable comparison table

## Cost Management

- Single run stays within $50 USD ceiling
- Uses stratified sampling if full dataset would exceed budget
- Estimates costs based on model and token usage
- Samples roughly equally from each ontology

## Dependencies

- datasets: For loading HuggingFace datasets
- httpx: For API calls
- scikit-learn: For metric computation utilities
"""

import os
import sys
import json
import argparse
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
import time

# Ensure local-server is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from datasets import load_dataset
from utils.logger import get_logger

_logger = get_logger(__name__)


class BenchmarkResult:
    """
    Container for benchmark metrics for a single ontology.

    Note:
        extraction_run_ids: Should be populated with ExtractionRun IDs from the
        API response once the extraction endpoint returns these IDs. Currently
        not populated as the extraction API is still being implemented.
    """

    def __init__(self, ontology: str, dataset_name: str, pipeline_config: str):
        self.ontology = ontology
        self.dataset_name = dataset_name
        self.pipeline_config = pipeline_config
        self.precision = 0.0
        self.recall = 0.0
        self.f1 = 0.0
        self.conformance = 0.0
        self.extraction_run_ids: list[str] = []  # TODO: Populate from API response when implemented
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.model = ""
        self.cost_usd = 0.0
        self.total_duration_ms = 0
        self.samples_processed = 0
        self.errors: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            "dataset": self.dataset_name,
            "ontology": self.ontology,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "conformance": self.conformance,
            "timestamp": self.timestamp,
            "pipeline_config": self.pipeline_config,
            "model": self.model,
            "cost_usd": self.cost_usd,
            "extraction_run_ids": self.extraction_run_ids,
            "total_duration_ms": self.total_duration_ms,
            "samples_processed": self.samples_processed,
            "errors": self.errors[:5],  # Limit error reporting
        }


def load_dataset_from_jsonl(dataset_name: str, split: str = "test") -> list[dict] | None:
    """
    Attempt to load dataset from local JSONL file.

    Checks for datafiles/benchmarks/{org}/{project}/{split}.jsonl (created by download_benchmarks.py).

    Args:
        dataset_name: HuggingFace dataset identifier (e.g., 'text2kg-bench/text2kgbench')
        split: Dataset split (e.g., 'test', 'train')

    Returns:
        List of samples if local file exists, None otherwise
    """
    try:
        parts = dataset_name.split("/")
        if len(parts) != 2:
            return None

        org, project = parts
        local_path = Path("datafiles") / "benchmarks" / org / project / f"{split}.jsonl"

        if not local_path.exists():
            return None

        _logger.info(f"Loading dataset from local JSONL: {local_path}")
        samples = []
        with open(local_path, "r") as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))

        _logger.info(f"Loaded {len(samples)} samples from local JSONL")
        return samples

    except Exception as e:
        _logger.warning(f"Failed to load from local JSONL: {e}")
        return None


def load_extraction_config(config_path: str) -> dict[str, Any]:
    """
    Load extraction configuration from JSON file.

    Args:
        config_path: Path to extraction config JSON

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file not found
        json.JSONDecodeError: If config is invalid JSON
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file) as f:
        config = json.load(f)

    _logger.info(f"Loaded config from {config_path}: model={config.get('model')}")
    return config


def estimate_cost(
    num_samples: int,
    config: dict[str, Any],
    max_tokens: int = 4096,
) -> float:
    """
    Estimate cost for extraction run.

    Uses simple pricing model based on:
    - Input tokens (average ~150 tokens per sample)
    - Output tokens (up to max_tokens per sample)
    - Model pricing (extracted from config or defaults)

    Args:
        num_samples: Number of samples to extract
        config: Extraction configuration
        max_tokens: Maximum output tokens per sample

    Returns:
        Estimated cost in USD
    """
    model = config.get("model", "gpt-3.5-turbo")

    # Simple pricing model (as of May 2026)
    # These are estimates and should be updated with actual pricing
    pricing = {
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},  # per 1K tokens
        "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},  # per 1K tokens
        "claude-opus-4-7": {"input": 0.003, "output": 0.015},  # per 1K tokens
        "claude-sonnet": {"input": 0.003, "output": 0.015},  # per 1K tokens
    }

    if model not in pricing:
        _logger.warning(f"Unknown model {model}, using gpt-3.5-turbo pricing")
        model = "gpt-3.5-turbo"

    rates = pricing[model]

    # Average ~150 input tokens per sample (text + ontology context)
    avg_input_tokens = 150
    # Output varies but cap at max_tokens
    avg_output_tokens = min(max_tokens, 500)

    total_input_tokens = num_samples * avg_input_tokens
    total_output_tokens = num_samples * avg_output_tokens

    cost = (total_input_tokens / 1000 * rates["input"] +
            total_output_tokens / 1000 * rates["output"])

    return cost


def stratified_sample_dataset(
    dataset: list[dict] | Any,
    max_cost: float,
    config: dict[str, Any],
) -> list[dict]:
    """
    Sample dataset using stratified sampling to stay within cost budget.

    Aims to sample roughly equally from each ontology to ensure fair
    representation while respecting cost constraint.

    Args:
        dataset: HuggingFace dataset
        max_cost: Maximum cost in USD
        config: Extraction configuration

    Returns:
        List of sample dictionaries from dataset
    """
    # Estimate max samples we can afford
    estimated_cost_per_sample = estimate_cost(1, config) / 1
    max_samples = int(max_cost / estimated_cost_per_sample)

    if len(dataset) <= max_samples:
        _logger.info(f"Dataset ({len(dataset)} samples) fits within budget, using all")
        return [dict(item) for item in dataset]

    # Get ontologies and sample proportionally from each
    ontologies = set()
    for item in dataset:
        if "ontology" in item:
            ontologies.add(item["ontology"])
        elif "ontologies" in item and isinstance(item["ontologies"], list):
            ontologies.update(item["ontologies"])

    _logger.info(f"Found {len(ontologies)} ontologies in dataset")

    samples_per_ontology = max(1, max_samples // max(1, len(ontologies)))
    sampled = []
    ontology_counts = {ont: 0 for ont in ontologies}

    for item in dataset:
        # Determine which ontologies this sample covers
        item_ontologies = []
        if "ontology" in item:
            item_ontologies = [item["ontology"]]
        elif "ontologies" in item and isinstance(item["ontologies"], list):
            item_ontologies = item["ontologies"]

        # Add if we haven't reached quota for any of its ontologies
        if any(ontology_counts.get(ont, 0) < samples_per_ontology for ont in item_ontologies):
            sampled.append(dict(item))
            for ont in item_ontologies:
                ontology_counts[ont] = ontology_counts.get(ont, 0) + 1

        if len(sampled) >= max_samples:
            break

    _logger.info(
        f"Sampled {len(sampled)} from {len(dataset)} samples"
        f" (cost estimate: ${estimate_cost(len(sampled), config):.2f})"
    )
    return sampled


def extract_triples_http(
    text: str,
    ontology_id: str,
    config: dict[str, Any],
    base_url: str = "http://localhost:8000",
) -> tuple[list[dict], int, str]:
    """
    Call extraction API via HTTP.

    Calls POST /api/extraction/extract to extract RDF triples scoped to an ontology.

    Args:
        text: Text to extract from
        ontology_id: ID of ontology for scoped extraction
        config: Extraction configuration
        base_url: API base URL

    Returns:
        Tuple of (triples, duration_ms, model_used)

    Note:
        The API response currently is a placeholder. When the extraction is fully
        implemented, this should also track extraction_run_id from the response.
        ExtractionRun entities should be created server-side and their IDs included
        in the metadata or response body.
    """
    url = f"{base_url}/api/extraction/extract"
    payload = {
        "text": text,
        "ontology_id": ontology_id,
        "options": {
            "model": config.get("model", "gpt-3.5-turbo"),
            "temperature": config.get("temperature", 0.0),
            "max_tokens": config.get("max_tokens", 4096),
        },
    }

    start_time = time.time()
    try:
        response = httpx.post(url, json=payload, timeout=60.0)
        duration_ms = int((time.time() - start_time) * 1000)

        if response.status_code != 200:
            _logger.warning(
                f"Extraction API returned {response.status_code}: {response.text[:200]}"
            )
            return [], duration_ms, config.get("model", "unknown")

        data = response.json()
        triples = data.get("triples", [])
        metadata = data.get("metadata", {})
        model_used = metadata.get("model", config.get("model", "unknown"))

        return triples, duration_ms, model_used

    except httpx.ConnectError:
        _logger.warning("Could not connect to extraction API (running standalone mode)")
        return [], int((time.time() - start_time) * 1000), config.get("model", "unknown")
    except Exception as e:
        _logger.error(f"Error calling extraction API: {e}")
        return [], int((time.time() - start_time) * 1000), config.get("model", "unknown")


def compute_metrics(
    predicted_triples: list[dict],
    gold_triples: list[dict],
) -> tuple[float, float, float, float]:
    """
    Compute precision, recall, F1, and conformance metrics.

    Precision: proportion of predicted triples that match gold triples
    Recall: proportion of gold triples that are predicted
    F1: harmonic mean of precision and recall
    Conformance: proportion of triples with valid format and confidence

    Handles both simple triple format (s, p, o) and ontology-scoped format
    (subject nodes, predicate nodes, object nodes with IDs and labels).

    Args:
        predicted_triples: Triples returned by extraction
        gold_triples: Ground truth triples

    Returns:
        Tuple of (precision, recall, f1, conformance)
    """
    if not gold_triples:
        # No gold triples to match against
        if not predicted_triples:
            return 1.0, 1.0, 1.0, 1.0  # Both empty = perfect
        else:
            return 0.0, 0.0, 0.0, 0.0  # Predicted something when nothing expected

    if not predicted_triples:
        # No predictions but there are gold triples
        return 0.0, 0.0, 0.0, 0.0

    # Normalize triples for comparison (handle both formats)
    def triple_key(t):
        # Handle ontology-scoped format with nodes
        if isinstance(t.get("subject"), dict):
            s = str(t["subject"].get("label", t["subject"].get("id", ""))).lower().strip()
        else:
            s = str(t.get("subject", "")).lower().strip()

        if isinstance(t.get("predicate"), dict):
            p = str(t["predicate"].get("label", t["predicate"].get("id", ""))).lower().strip()
        else:
            p = str(t.get("predicate", "")).lower().strip()

        if isinstance(t.get("object"), dict):
            o = str(t["object"].get("label", t["object"].get("id", ""))).lower().strip()
        else:
            o = str(t.get("object", "")).lower().strip()

        return (s, p, o)

    pred_set = set(triple_key(t) for t in predicted_triples)
    gold_set = set(triple_key(t) for t in gold_triples)

    if not gold_set:
        # All gold triples normalized to empty strings (degenerate case)
        if not pred_set:
            return 1.0, 1.0, 1.0, 1.0
        else:
            return 0.0, 0.0, 0.0, 0.0

    # Compute metrics
    true_positives = len(pred_set & gold_set)
    false_positives = len(pred_set - gold_set)
    false_negatives = len(gold_set - pred_set)

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    # Conformance: check for required fields and valid confidence scores
    valid_count = 0
    for t in predicted_triples:
        has_subject = "subject" in t and t["subject"]
        has_predicate = "predicate" in t and t["predicate"]
        has_object = "object" in t and t["object"]
        confidence = t.get("confidence", 1.0)
        valid_confidence = isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0

        if has_subject and has_predicate and has_object and valid_confidence:
            valid_count += 1

    conformance = valid_count / len(predicted_triples) if predicted_triples else 0.0

    return precision, recall, f1, conformance


def run_benchmark(
    dataset_name: str,
    config_path: str,
    max_cost: float = 50.0,
    api_base_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    """
    Run the benchmark harness.

    Args:
        dataset_name: HuggingFace dataset identifier
        config_path: Path to extraction config JSON
        max_cost: Maximum cost ceiling in USD
        api_base_url: Base URL for extraction API

    Returns:
        Dictionary with benchmark results
    """
    _logger.info(f"Starting benchmark: {dataset_name}")

    # Load configuration
    config = load_extraction_config(config_path)

    # Load dataset — try local JSONL first, then fall back to HuggingFace
    _logger.info(f"Loading dataset {dataset_name}")
    samples = load_dataset_from_jsonl(dataset_name, split="test")

    if samples is None:
        # Fall back to loading from HuggingFace
        _logger.info("Local JSONL not found, loading from HuggingFace")
        try:
            dataset = load_dataset(dataset_name, split="test")
            samples = [dict(item) for item in dataset]
        except Exception as e:
            _logger.error(f"Failed to load dataset: {e}")
            _logger.error("Dataset may not be available yet or may be private.")
            _logger.error(f"Check: https://huggingface.co/datasets/{dataset_name}")
            _logger.info(f"To avoid repeated downloads, run: python scripts/download_benchmarks.py --dataset {dataset_name}")
            raise
    else:
        _logger.info(f"Loaded {len(samples)} samples from cache")

    # Apply stratified sampling if needed
    samples = stratified_sample_dataset(samples, max_cost, config)

    # Collect unique ontologies from samples
    ontologies_set: set[Any] = set()
    for sample in samples:
        if "ontology" in sample:
            ontologies_set.add(sample["ontology"])
        elif "ontologies" in sample and isinstance(sample["ontologies"], list):
            ontologies_set.update(sample["ontologies"])

    _logger.info(f"Found {len(ontologies_set)} unique ontologies")
    ontologies = sorted(list(ontologies_set))

    # Run extraction for each ontology
    results_by_ontology = {}
    total_start_time = time.time()

    for ontology in ontologies:
        _logger.info(f"Processing ontology: {ontology}")
        result = BenchmarkResult(ontology, dataset_name, Path(config_path).stem)
        result.model = config.get("model", "unknown")

        # Filter samples for this ontology
        ontology_samples = [
            s for s in samples
            if (s.get("ontology") == ontology or
                (isinstance(s.get("ontologies"), list) and ontology in s["ontologies"]))
        ]

        if not ontology_samples:
            _logger.warning(f"No samples found for ontology {ontology}")
            results_by_ontology[ontology] = result
            continue

        _logger.info(f"Processing {len(ontology_samples)} samples for {ontology}")

        precision_scores = []
        recall_scores = []
        f1_scores = []
        conformance_scores = []

        for sample_idx, sample in enumerate(ontology_samples):
            text = sample.get("text", "")
            gold_triples = sample.get("triples", [])

            if not text:
                continue

            try:
                # Extract triples via API
                pred_triples, duration_ms, model_used = extract_triples_http(
                    text,
                    ontology,
                    config,
                    api_base_url,
                )

                result.total_duration_ms += duration_ms
                if not result.model:
                    result.model = model_used

                # Compute metrics
                precision, recall, f1, conformance = compute_metrics(
                    pred_triples, gold_triples
                )
                precision_scores.append(precision)
                recall_scores.append(recall)
                f1_scores.append(f1)
                conformance_scores.append(conformance)
                result.samples_processed += 1

            except Exception as e:
                _logger.error(f"Error processing sample {sample_idx}: {e}")
                result.errors.append(f"Sample {sample_idx}: {str(e)[:100]}")

        # Aggregate metrics
        if precision_scores:
            result.precision = sum(precision_scores) / len(precision_scores)
            result.recall = sum(recall_scores) / len(recall_scores)
            result.f1 = sum(f1_scores) / len(f1_scores)
            result.conformance = sum(conformance_scores) / len(conformance_scores)

        # Estimate cost
        result.cost_usd = estimate_cost(result.samples_processed, config)

        _logger.info(
            f"{ontology}: P={result.precision:.3f} R={result.recall:.3f} "
            f"F1={result.f1:.3f} (cost: ${result.cost_usd:.2f})"
        )

        results_by_ontology[ontology] = result

    total_duration_ms = int((time.time() - total_start_time) * 1000)
    total_cost = sum(r.cost_usd for r in results_by_ontology.values())

    # Prepare output
    benchmark_output = {
        "run_id": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset_name,
        "pipeline_config": Path(config_path).stem,
        "model": config.get("model", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_duration_ms": total_duration_ms,
        "total_cost_usd": total_cost,
        "ontologies_count": len(results_by_ontology),
        "samples_processed": sum(r.samples_processed for r in results_by_ontology.values()),
        "results": [r.to_dict() for r in results_by_ontology.values()],
    }

    return benchmark_output


def save_json_report(results: dict[str, Any], output_path: str) -> Path:
    """Save benchmark results as JSON."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    _logger.info(f"Saved JSON report to {output_file}")
    return output_file


def save_markdown_report(results: dict[str, Any], output_path: str) -> Path:
    """Save benchmark results as human-readable Markdown."""
    output_file = Path(output_path).with_suffix(".md")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Text2KGBench Benchmark Results",
        "",
        f"**Dataset:** {results['dataset']}",
        f"**Pipeline:** {results['pipeline_config']}",
        f"**Model:** {results['model']}",
        f"**Timestamp:** {results['timestamp']}",
        "",
        "## Summary",
        "",
        f"- **Total Ontologies:** {results['ontologies_count']}",
        f"- **Samples Processed:** {results['samples_processed']}",
        f"- **Total Duration:** {results['total_duration_ms']}ms",
        f"- **Total Cost:** ${results['total_cost_usd']:.2f}",
        "",
        "## Results by Ontology",
        "",
        "| Ontology | Precision | Recall | F1 | Conformance | Samples | Cost |",
        "|----------|-----------|--------|-----|-------------|---------|------|",
    ]

    for result in results["results"]:
        lines.append(
            f"| {result['ontology']} | "
            f"{result['precision']:.3f} | "
            f"{result['recall']:.3f} | "
            f"{result['f1']:.3f} | "
            f"{result['conformance']:.3f} | "
            f"{result['samples_processed']} | "
            f"${result['cost_usd']:.2f} |"
        )

    lines.extend([
        "",
        "## Metrics Explanation",
        "",
        "- **Precision:** Proportion of predicted triples that match ground truth",
        "- **Recall:** Proportion of ground truth triples that were predicted",
        "- **F1:** Harmonic mean of precision and recall",
        "- **Conformance:** Proportion of triples with valid format and confidence (0-1)",
        "",
        "---",
        f"*Generated by Text2KGBench harness on {datetime.now(timezone.utc).isoformat()}*",
    ])

    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    _logger.info(f"Saved Markdown report to {output_file}")
    return output_file


def generate_comparison_from_current(
    current_results: dict[str, Any],
    comparison_file: str,
    output_path: str,
) -> None:
    """
    Generate a comparison report between current and previous results.

    Args:
        current_results: Current benchmark results
        comparison_file: Path to previous benchmark results JSON
        output_path: Base path for comparison output (will generate .json and .md)
    """
    try:
        # Import the comparison module
        comparison_script_path = Path(__file__).parent / "compare_benchmarks.py"
        spec = importlib.util.spec_from_file_location("compare_benchmarks", comparison_script_path)
        compare_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compare_module)

        # Save current results to temp file for comparison
        current_dataset = current_results.get("dataset", "current")
        # Sanitize dataset name for use in filename (remove slashes)
        safe_dataset_name = current_dataset.replace("/", "_")
        temp_current = Path(output_path).parent / f"_temp_{safe_dataset_name}.json"
        with open(temp_current, "w") as f:
            json.dump(current_results, f)

        # Load previous results
        previous_results = compare_module.load_results_file(comparison_file)

        # Build comparison
        results_by_dataset = {
            previous_results.get("dataset", Path(comparison_file).stem): previous_results,
            current_dataset: current_results,
        }
        comparison = compare_module.build_comparison_matrix(results_by_dataset)

        # Save comparison reports
        comparison_json = compare_module.save_json_comparison(comparison, output_path)
        comparison_md = compare_module.save_markdown_comparison(
            comparison, results_by_dataset, output_path
        )

        _logger.info(f"Cross-dataset comparison generated!")
        _logger.info(f"Comparison JSON: {comparison_json}")
        _logger.info(f"Comparison Markdown: {comparison_md}")

        # Clean up temp file
        if temp_current.exists():
            temp_current.unlink()

    except Exception as e:
        _logger.warning(f"Could not generate comparison report: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Command-line interface for benchmark harness."""
    parser = argparse.ArgumentParser(
        description="Run Text2KGBench benchmark harness"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="text2kg-bench/wikidata-tekgen",
        help="Dataset identifier (default: text2kg-bench/wikidata-tekgen)",
    )
    parser.add_argument(
        "--pipeline",
        type=str,
        default="configs/extraction-default.json",
        help="Path to extraction pipeline config (default: configs/extraction-default.json)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output path for JSON report (default: reports/{dataset_abbrev}-YYYY-MM-DD.json)",
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=50.0,
        help="Maximum cost ceiling in USD (default: 50.0)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="Extraction API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--comparison",
        type=str,
        default=None,
        help="Path to previous results JSON for cross-dataset comparison (optional)",
    )

    args = parser.parse_args()

    # Default output path
    if args.out is None:
        today = datetime.now().strftime("%Y-%m-%d")
        dataset_abbrev = args.dataset.split("/")[-1][:6]
        args.out = f"reports/{dataset_abbrev}-{today}.json"

    try:
        results = run_benchmark(
            dataset_name=args.dataset,
            config_path=args.pipeline,
            max_cost=args.max_cost,
            api_base_url=args.api_url,
        )

        # Save reports
        json_path = save_json_report(results, args.out)
        md_path = save_markdown_report(results, args.out)

        _logger.info("Benchmark complete!")
        _logger.info(f"JSON report: {json_path}")
        _logger.info(f"Markdown report: {md_path}")
        _logger.info(f"Total cost: ${results['total_cost_usd']:.2f}")

        # Generate comparison if requested
        if args.comparison:
            comparison_out = str(Path(args.out).parent / "comparison")
            generate_comparison_from_current(results, args.comparison, comparison_out)

        return 0

    except Exception as e:
        _logger.error(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
