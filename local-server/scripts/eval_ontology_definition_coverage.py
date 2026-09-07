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
from math import sqrt

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Ensure local-server config takes precedence
local_server = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, local_server)

from adapters.embedding.sentence_transformer import (  # noqa: E402
    SentenceTransformerEmbedding,
)
from scripts.eval_ontology import build_eval_ontology  # noqa: E402


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors without numpy."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = sqrt(sum(a * a for a in vec1))
    norm_b = sqrt(sum(b * b for b in vec2))
    denominator = norm_a * norm_b + 1e-10
    return float(dot_product / denominator)


def check_definition_coverage() -> dict[str, int | float]:
    """
    Check class-definition coverage in the evaluation ontology.

    Validates both:
    1. Basic coverage: percentage of classes with non-empty definitions
    2. Distinctiveness: pairwise embedding similarity of definitions,
       ensuring they are sufficiently diverse for the NLP-grounded typing
       variant to use them for disambiguation.

    Returns:
        Dict with coverage metrics:
        - total_classes: Total number of classes
        - classes_with_definition: Classes that have non-empty definitions
        - coverage_percent: Percentage of classes with definitions
        - avg_definition_length: Average definition text length (chars)
        - avg_embedding_similarity: Mean pairwise cosine similarity of definition embeddings
        - embedding_distinctiveness: Fraction of definition pairs with low similarity (<0.7)
    """
    try:
        embedding = SentenceTransformerEmbedding()
        ontology_repo, schema_index = build_eval_ontology(embedding)
    except Exception as e:
        print(f"\nERROR initializing ontology ({type(e).__name__}): {e}")
        print("This typically occurs when embedding models are not cached in offline mode.")
        print("Try running with internet access to download the embedding model, or")
        print("configure HuggingFace cache with locally-downloaded models.")
        return {
            "total_classes": 0,
            "classes_with_definition": 0,
            "coverage_percent": 0.0,
            "avg_definition_length": 0.0,
            "avg_embedding_similarity": 0.0,
            "embedding_distinctiveness": 0.0,
        }

    # Scan all classes for definitions
    total_classes = 0
    classes_with_defs = 0
    definition_lengths = []
    definition_embeddings: list[list[float]] = []
    definition_texts: list[str] = []
    classes_by_length = defaultdict(list)

    def get_class_title(cls):
        return cls.title if hasattr(cls, "title") else "unknown"

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
                definition_texts.append(definition)

                # Categorize by length
                class_title = get_class_title(cls)
                if def_len < 50:
                    classes_by_length["<50 chars"].append(class_title)
                elif def_len < 100:
                    classes_by_length["50-100 chars"].append(class_title)
                elif def_len < 200:
                    classes_by_length["100-200 chars"].append(class_title)
                else:
                    classes_by_length[">200 chars"].append(class_title)

    # Compute embeddings for all definitions (for distinctiveness check)
    embedding_available = False
    try:
        if definition_texts:
            definition_embeddings = embedding.embed_batch(definition_texts)
            embedding_available = True
    except Exception as e:
        print(
            f"\nNote: Embedding computation unavailable ({type(e).__name__}), "
            "skipping distinctiveness check"
        )
        embedding_available = False

    avg_def_length = (
        sum(definition_lengths) / len(definition_lengths) if definition_lengths else 0.0
    )

    # Compute embedding distinctiveness: measure full pairwise similarity
    embedding_similarities: list[float] = []
    avg_embedding_similarity = 0.0
    embedding_distinctiveness = 0.0
    if embedding_available and len(definition_embeddings) > 1:
        for i in range(len(definition_embeddings)):
            for j in range(i + 1, len(definition_embeddings)):
                sim = _cosine_similarity(definition_embeddings[i], definition_embeddings[j])
                embedding_similarities.append(sim)

        avg_embedding_similarity = (
            sum(embedding_similarities) / len(embedding_similarities)
            if embedding_similarities
            else 0.0
        )

        # Distinctiveness: fraction of pairs with low similarity (good for disambiguation)
        low_similarity_threshold = 0.7
        embedding_distinctiveness = (
            sum(1 for sim in embedding_similarities if sim < low_similarity_threshold)
            / len(embedding_similarities)
            if embedding_similarities
            else 0.0
        )

    results = {
        "total_classes": total_classes,
        "classes_with_definition": classes_with_defs,
        "coverage_percent": (classes_with_defs / total_classes * 100) if total_classes > 0 else 0.0,
        "avg_definition_length": avg_def_length,
        "avg_embedding_similarity": avg_embedding_similarity,
        "embedding_distinctiveness": embedding_distinctiveness,
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

    # Embedding distinctiveness metrics
    if embedding_available:
        print("\n=== Embedding Distinctiveness ===\n")
        print(
            "Average pairwise definition embedding similarity: "
            f"{results['avg_embedding_similarity']:.3f}"
        )
        print(
            "Fraction of definition pairs with low similarity (<0.7): "
            f"{results['embedding_distinctiveness']:.1%}"
        )
    else:
        print("\n=== Embedding Distinctiveness ===")
        print("(Skipped - embedding model unavailable in offline mode)")

    # Assessment
    print("\n=== Assessment ===")
    coverage_ok = results["coverage_percent"] >= 60.0
    distinctiveness_ok = (
        embedding_available and results["embedding_distinctiveness"] >= 0.5
    )  # At least 50% of pairs should be distinct

    if embedding_available:
        if coverage_ok and distinctiveness_ok:
            print("✓ PASS: Sufficient class definition coverage and distinctiveness")
            print("  Grounded_v1 can reliably use definition matching for typing disambiguation.")
        elif coverage_ok and not distinctiveness_ok:
            print("⚠ WARNING: Adequate coverage but low definition distinctiveness")
            print(
                "  Many definitions are too similar; definition-preferred "
                "matching may be ineffective."
            )
        elif not coverage_ok and distinctiveness_ok:
            print("⚠ WARNING: Adequate distinctiveness but insufficient coverage")
            print("  Too many classes lack definitions for reliable " "definition-based matching.")
        else:
            print("✗ FAIL: Insufficient coverage and low distinctiveness")
            print("  Definitions are not suitable for disambiguation.")
    else:
        # Embedding not available; assess based on coverage alone
        if coverage_ok:
            print("✓ PASS: Sufficient class definition coverage")
            print(
                "  (Embedding distinctiveness check skipped - model unavailable " "in offline mode)"
            )
            print(
                "  Grounded_v1 can use definitions for typing, but "
                "distinctiveness cannot be verified."
            )
        else:
            print("✗ FAIL: Insufficient class definition coverage")
            print(
                "  (Embedding distinctiveness check skipped - model unavailable " "in offline mode)"
            )

    if results["coverage_percent"] >= 80.0:
        print("\n✓ BONUS: High definition coverage (≥80%)")
    elif results["coverage_percent"] >= 60.0:
        print("\n⚠ Coverage is moderate (60-80%)")
    else:
        print("\n✗ Coverage is low (<60%)")

    return results


if __name__ == "__main__":
    try:
        results = check_definition_coverage()
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
