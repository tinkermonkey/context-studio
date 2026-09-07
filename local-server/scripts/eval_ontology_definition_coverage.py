#!/usr/bin/env python
"""
Check class-definition coverage for the evaluation ontology.

Verifies that classes in the evaluation ontology have definitions distinctive
enough for embedding similarity to separate specific instances. This check
ensures the grounded_v1 variant can reliably use definition matching for
typing disambiguation.

Usage (from local-server/, venv active):
    python scripts/eval_ontology_definition_coverage.py
"""

import os
import sys
from collections import defaultdict

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.eval_ontology import build_eval_ontology
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding


def check_definition_coverage() -> dict[str, int | float]:
    """
    Check class-definition coverage in the evaluation ontology.

    Returns:
        Dict with coverage metrics:
        - total_classes: Total number of classes
        - classes_with_definition: Classes that have non-empty definitions
        - coverage_percent: Percentage of classes with definitions
        - avg_definition_length: Average definition text length (chars)
    """
    embedding = SentenceTransformerEmbedding()
    ontology_repo, schema_index = build_eval_ontology(embedding)

    # Scan all classes for definitions
    total_classes = 0
    classes_with_defs = 0
    definition_lengths = []
    classes_by_length = defaultdict(list)

    concept_schemes = ontology_repo.list_concept_schemes(limit=None)
    for scheme in concept_schemes:
        classes = ontology_repo.list_classes(concept_scheme_id=scheme.id, limit=None)
        for cls in classes:
            total_classes += 1
            definition = getattr(cls, "description", None) or getattr(cls, "definition", None)
            if definition and definition.strip():
                classes_with_defs += 1
                def_len = len(definition)
                definition_lengths.append(def_len)

                # Categorize by length
                if def_len < 50:
                    classes_by_length["<50 chars"].append(cls.title if hasattr(cls, 'title') else "unknown")
                elif def_len < 100:
                    classes_by_length["50-100 chars"].append(cls.title if hasattr(cls, 'title') else "unknown")
                elif def_len < 200:
                    classes_by_length["100-200 chars"].append(cls.title if hasattr(cls, 'title') else "unknown")
                else:
                    classes_by_length[">200 chars"].append(cls.title if hasattr(cls, 'title') else "unknown")

    avg_def_length = sum(definition_lengths) / len(definition_lengths) if definition_lengths else 0.0

    results = {
        "total_classes": total_classes,
        "classes_with_definition": classes_with_defs,
        "coverage_percent": (classes_with_defs / total_classes * 100) if total_classes > 0 else 0.0,
        "avg_definition_length": avg_def_length,
    }

    print("\n=== Class Definition Coverage Report ===\n")
    print(f"Total classes: {results['total_classes']}")
    print(f"Classes with definitions: {results['classes_with_definition']}")
    print(f"Coverage: {results['coverage_percent']:.1f}%")
    print(f"Average definition length: {results['avg_definition_length']:.0f} characters")

    if classes_by_length:
        print("\nDefinition length distribution:")
        for length_range in sorted(classes_by_length.keys()):
            count = len(classes_by_length[length_range])
            print(f"  {length_range}: {count} classes")
            # Show a few examples
            examples = classes_by_length[length_range][:3]
            for ex in examples:
                print(f"    - {ex}")

    # Assessment
    print("\n=== Assessment ===")
    if results["coverage_percent"] >= 80.0:
        print("✓ PASS: Sufficient class definition coverage (≥80%)")
        print("  Grounded_v1 can reliably use definition matching for typing.")
    elif results["coverage_percent"] >= 60.0:
        print("⚠ WARNING: Moderate class definition coverage (60-80%)")
        print("  Definition-preferred matching may have limited effectiveness.")
    else:
        print("✗ FAIL: Insufficient class definition coverage (<60%)")
        print("  Definition-preferred matching not recommended.")

    return results


if __name__ == "__main__":
    try:
        results = check_definition_coverage()
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
