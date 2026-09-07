#!/usr/bin/env python
"""
Validate that the A/B tournament infrastructure for grounded_v1 is ready.

This script verifies:
1. All tournament variants (including grounded_v1) are registered
2. Synthetic cassettes for grounded_v1 are present for all required scenarios
3. The tournament can instantiate without errors

Usage (from local-server/, venv active):
    python scripts/validate_tournament_setup.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [p for p in sys.path if '/app' not in p]

from scripts.quality_tournament import (
    _grounded_cassettes_present,
    _GROUNDED_REPLAY_SCENARIOS,
    _GROUNDED_CASSETTE_DIR,
    build_registry,
    registered_variants,
)
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.embedding.caching_embedding_service import CachingEmbeddingService


def validate_cassettes() -> bool:
    """Validate that all grounded_v1 cassettes are present."""
    print("\n=== Cassette Validation ===\n")

    if not _GROUNDED_CASSETTE_DIR.exists():
        print(f"✗ Cassette directory missing: {_GROUNDED_CASSETTE_DIR}")
        return False

    print(f"Cassette directory: {_GROUNDED_CASSETTE_DIR}")
    print(f"Required scenarios: {len(_GROUNDED_REPLAY_SCENARIOS)}")

    missing = []
    for scenario in _GROUNDED_REPLAY_SCENARIOS:
        cassette_file = _GROUNDED_CASSETTE_DIR / f"individual_grounded_typing_{scenario}.json"
        if cassette_file.exists():
            print(f"  ✓ {scenario}")
        else:
            print(f"  ✗ {scenario} (missing)")
            missing.append(scenario)

    if missing:
        print(f"\nMissing {len(missing)} cassettes")
        return False

    print(f"\n✓ All {len(_GROUNDED_REPLAY_SCENARIOS)} cassettes present")
    return True


def validate_variants() -> bool:
    """Validate that all tournament variants are registered."""
    print("\n=== Variant Registration ===\n")

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


def validate_grounded_specific() -> bool:
    """Validate grounded_v1 specific capabilities."""
    print("\n=== grounded_v1 Specific Validation ===\n")

    cassettes_present = _grounded_cassettes_present()
    print(f"Cassettes present for grounded_v1: {cassettes_present}")

    if cassettes_present:
        print("✓ grounded_v1 can be registered and evaluated offline")
    else:
        print("✗ grounded_v1 cannot be registered (missing cassettes)")
        return False

    return True


def main() -> int:
    print("=" * 70)
    print("A/B TOURNAMENT SETUP VALIDATION")
    print("=" * 70)

    results = {
        "Cassettes": validate_cassettes(),
        "Variants": validate_variants(),
        "Grounded-specific": validate_grounded_specific(),
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
        print("\nYou can now run the tournament with:")
        print("  python scripts/quality_tournament.py --pipeline individual")
        print("\nThe tournament will evaluate all 4 variants:")
        print("  - open_v1: Rule-based spaCy triple extraction")
        print("  - default: LLM-based extraction (phase-1 model via OpenRouter)")
        print("  - default+grounding: LLM + soft-match dedup")
        print("  - grounded_v1: NLP-grounded typing with LLM confirmation")
        print("\nVariants will be ranked by dev soft-F1, with promotion decisions")
        print("based on meeting strict-F1 floor and soft-F1 improvement criteria.")
        return 0
    else:
        print("\n" + "=" * 70)
        print("✗ FAILURE: Some validation checks failed")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
