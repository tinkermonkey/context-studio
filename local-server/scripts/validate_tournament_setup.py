#!/usr/bin/env python
"""
Validate that the A/B tournament infrastructure for grounded_v1 is ready.

This script has two modes:
1. Lightweight (default): Verifies cassette files exist and are valid JSON
2. Full (--full): Additionally validates variants are registered and models work

Usage (from local-server/, venv active):
    python scripts/validate_tournament_setup.py           # lightweight file check
    python scripts/validate_tournament_setup.py --full    # full integration check
"""

import argparse
import json
import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Ensure local-server config takes precedence
local_server = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, local_server)

from scripts.quality_tournament import (
    _GROUNDED_CASSETTE_DIR,
    _GROUNDED_REPLAY_SCENARIOS,
    _grounded_cassettes_present,
    build_registry,
)


def validate_cassettes_lightweight() -> bool:
    """Lightweight: Verify cassette files exist and contain valid JSON."""
    print("\n=== Cassette File Validation (Lightweight) ===\n")

    if not _GROUNDED_CASSETTE_DIR.exists():
        print(f"✗ Cassette directory missing: {_GROUNDED_CASSETTE_DIR}")
        return False

    print(f"Cassette directory: {_GROUNDED_CASSETTE_DIR}")
    print(f"Required scenarios: {len(_GROUNDED_REPLAY_SCENARIOS)}")

    missing = []
    invalid_json = []
    for scenario in _GROUNDED_REPLAY_SCENARIOS:
        cassette_file = _GROUNDED_CASSETTE_DIR / f"individual_grounded_typing_{scenario}.json"
        if not cassette_file.exists():
            print(f"  ✗ {scenario} (missing)")
            missing.append(scenario)
        else:
            try:
                with open(cassette_file) as f:
                    json.load(f)
                print(f"  ✓ {scenario}")
            except json.JSONDecodeError as e:
                print(f"  ✗ {scenario} (invalid JSON: {e})")
                invalid_json.append(scenario)

    if missing:
        print(f"\nMissing {len(missing)} cassettes")
        return False

    if invalid_json:
        print(f"\nInvalid JSON in {len(invalid_json)} cassettes")
        return False

    print(f"\n✓ All {len(_GROUNDED_REPLAY_SCENARIOS)} cassettes present and valid")
    return True


def validate_cassettes_full() -> bool:
    """Full validation: cassettes exist, valid JSON, and replay can register."""
    if not validate_cassettes_lightweight():
        return False

    # Also verify _grounded_cassettes_present() agrees
    if not _grounded_cassettes_present():
        print("\n✗ Cassettes present but _grounded_cassettes_present() returned False")
        return False

    return True


def validate_variants_full() -> bool:
    """Full validation: Load models and verify all tournament variants are registered."""
    print("\n=== Variant Registration (Full) ===\n")

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

    print(f"Total variants: {len(registry)}")

    expected_variants = {"open_v1", "default", "default+grounding", "grounded_v1"}
    actual_variants = set(registry.keys())

    for variant_name in sorted(expected_variants):
        if variant_name in actual_variants:
            variant = registry[variant_name]
            knob_count = sum(len(v) for v in variant.knob_space.values())
            print(f"  ✓ {variant_name:<20} ({knob_count} knob options)")
        else:
            print(f"  ✗ {variant_name} not registered")

    missing = expected_variants - actual_variants
    if missing:
        print(f"\n✗ {len(missing)} variant(s) not registered: {missing}")
        return False

    print(f"\n✓ All {len(expected_variants)} variants registered")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate A/B tournament infrastructure for grounded_v1"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Run full validation including model loading (slower). Default is lightweight file check.",
    )
    args = parser.parse_args()

    print("=" * 70)
    if args.full:
        print("A/B TOURNAMENT SETUP VALIDATION (FULL)")
    else:
        print("A/B TOURNAMENT SETUP VALIDATION (LIGHTWEIGHT)")
    print("=" * 70)

    if args.full:
        results = {
            "Cassettes": validate_cassettes_full(),
            "Variants": validate_variants_full(),
        }
    else:
        results = {
            "Cassettes": validate_cassettes_lightweight(),
        }

    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70 + "\n")

    all_passed = all(results.values())
    for check_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check_name}")

    if all_passed:
        print("\n" + "=" * 70)
        print("✓ SUCCESS: Tournament infrastructure is ready")
        print("=" * 70)
        if args.full:
            print("\nYou can now run the tournament with:")
            print("  python scripts/quality_tournament.py --pipeline individual")
            print("\nThe tournament will evaluate all 4 variants:")
            print("  - open_v1: Rule-based spaCy triple extraction")
            print("  - default: LLM-based extraction (phase-1 model via OpenRouter)")
            print("  - default+grounding: LLM + soft-match dedup")
            print("  - grounded_v1: NLP-grounded typing with LLM confirmation")
            print("\nVariants will be ranked by dev soft-F1, with promotion decisions")
            print("based on meeting strict-F1 floor and soft-F1 improvement criteria.")
        else:
            print("\nCassettes are in place for grounded_v1 variant.")
            print("Run with --full flag to validate variants and models can load:")
            print("  python scripts/validate_tournament_setup.py --full")
        return 0
    else:
        print("\n" + "=" * 70)
        print("✗ FAILURE: Some validation checks failed")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
