#!/usr/bin/env python
"""
Check that the tournament has what it replays: the triple corpus's cassettes
for the `default` variants, and the benchmark cassettes of the target its
benchmark pass would run.

The target is chosen as in `scripts/quality_tournament.py` and
`scripts/benchmark_replay.py`: `--implementation` and `--configuration`, each
defaulting through the pipeline registry.

Two modes:
1. Lightweight (default): the cassette files exist and are valid JSON
2. Full (--full): additionally builds the variant registry (loads the models)

A cassette that exists but no longer answers the pipeline's prompts is not
caught here: the tournament itself reports that (STALE CASSETTES, exit 3).

Usage (from local-server/, venv active):
    python scripts/validate_tournament_setup.py
    python scripts/validate_tournament_setup.py --implementation find_then_type
    python scripts/validate_tournament_setup.py --full
"""

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Ensure local-server config takes precedence
local_server = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, local_server)

from scripts import benchmark_replay  # noqa: E402
from scripts.quality_tournament import (  # noqa: E402
    _DEFAULT_REPLAY_SCENARIOS,
    _default_cassette_path,
    build_registry,
    triple_corpus_target,
)
from tests.integration.pipelines._harness.benchmark import benchmark_documents  # noqa: E402

# The variants the tournament registers when their recordings are present
EXPECTED_VARIANTS = ("open_v1", "default", "default+grounding")


def check_cassettes(label: str, paths: dict[str, Path]) -> bool:
    """Every named cassette file exists and holds valid JSON."""
    print(f"\n=== {label} ===\n")
    problems = 0
    for name, path in paths.items():
        if not path.exists():
            print(f"  ✗ {name} (missing: {path})")
            problems += 1
            continue
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            print(f"  ✗ {name} (invalid JSON: {exc})")
            problems += 1
            continue
        print(f"  ✓ {name}")
    if problems:
        print(f"\n✗ {problems} of {len(paths)} cassettes missing or invalid")
        return False
    print(f"\n✓ All {len(paths)} cassettes present and valid")
    return True


def validate_triple_corpus_cassettes() -> bool:
    """The cassettes the `default` and `default+grounding` variants replay."""
    target = triple_corpus_target()
    return check_cassettes(
        f"Triple corpus: {target.implementation} with {target.configuration} ({target.model})",
        {scenario: _default_cassette_path(scenario) for scenario in _DEFAULT_REPLAY_SCENARIOS},
    )


def validate_benchmark_cassettes(target: benchmark_replay.BenchmarkTarget) -> bool:
    """The cassettes the benchmark pass replays for the chosen target."""
    return check_cassettes(
        f"Benchmark: {target.implementation} with {target.configuration} ({target.model}), "
        f"{benchmark_replay.cassette_dir(target).name}/",
        {d: benchmark_replay.cassette_path(d, target) for d in benchmark_documents()},
    )


def validate_variants() -> bool:
    """Load the models and check that every expected tournament variant registers."""
    print("\n=== Variant registration ===\n")

    from adapters.embedding.caching_embedding_service import CachingEmbeddingService
    from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        print("✗ spaCy model not loaded (required for variant registration)")
        print("  Run: python -m spacy download en_core_web_sm")
        return False

    try:
        embedding = CachingEmbeddingService(SentenceTransformerEmbedding())
        registry = build_registry(nlp, embedding)
    except Exception as exc:
        print(f"✗ Failed to build registry: {exc}")
        return False

    for name in EXPECTED_VARIANTS:
        variant = registry.get(name)
        if variant is None:
            print(f"  ✗ {name} not registered")
            continue
        print(
            f"  ✓ {name:<20} implementation {variant.implementation}, configuration "
            f"{variant.configuration}, model {variant.model}"
        )

    missing = [name for name in EXPECTED_VARIANTS if name not in registry]
    if missing:
        print(f"\n✗ {len(missing)} variant(s) not registered: {missing}")
        return False
    print(f"\n✓ All {len(EXPECTED_VARIANTS)} variants registered")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that the tournament's recordings are in place"
    )
    parser.add_argument(
        "--implementation",
        help="The implementation the benchmark pass would run (the registry's default)",
    )
    parser.add_argument(
        "--configuration",
        help="The implementation's configuration (the one its recordings were made with)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Also build the variant registry, which loads the models (slower)",
    )
    args = parser.parse_args()

    try:
        target = benchmark_replay.resolve_target(args.implementation, args.configuration)
    except benchmark_replay.UnknownTargetError as exc:
        print(f"ERROR: {exc}")
        return 1

    results = {
        "Triple-corpus cassettes": validate_triple_corpus_cassettes(),
        "Benchmark cassettes": validate_benchmark_cassettes(target),
    }
    if args.full:
        results["Variants"] = validate_variants()

    print("\n=== Summary ===\n")
    for check_name, passed in results.items():
        print(f"{'✓ PASS' if passed else '✗ FAIL'}: {check_name}")

    if not all(results.values()):
        print("\n✗ The tournament cannot measure this target as it stands")
        return 1
    print("\n✓ Recordings are in place. Run the tournament with:")
    print(f"  python scripts/quality_tournament.py --pipeline individual {target.flags}")
    if not args.full:
        print("Pass --full to also check that the variants register and the models load.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
