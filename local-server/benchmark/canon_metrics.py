"""
Canon-specific benchmark metrics.

Pure functions that score a *produced* ontology slice against the
software-architecture canon's gold-standard expectations. No I/O, no
HuggingFace, no LLM — these are scored over data already in memory.

Used by `scripts/run_canon_benchmark.py` to compute the canon section of the
benchmark experiment report. Imported in tests for direct unit verification.

The canon bundle structure is whatever `tests/utils/canon_assertions.load_canon`
returns:
  - canon: master dict from canon.json
  - papers: dict[name -> paper dict]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-f]{6}$")


# ---------------------------------------------------------------------------- #
# Result containers                                                            #
# ---------------------------------------------------------------------------- #


@dataclass(frozen=True)
class F1Metrics:
    """Precision / recall / F1 over a single node type."""

    node_type: str
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_type": self.node_type,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


# ---------------------------------------------------------------------------- #
# Per-node-type F1                                                             #
# ---------------------------------------------------------------------------- #


def _score_set(produced: set[str], expected: set[str], node_type: str) -> F1Metrics:
    tp = len(produced & expected)
    fp = len(produced - expected)
    fn = len(expected - produced)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        (2 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )
    return F1Metrics(
        node_type=node_type,
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
    )


def compute_per_node_type_f1(
    produced_by_type: Mapping[str, Iterable[str]],
    expected_by_type: Mapping[str, Iterable[str]],
    node_types: Iterable[str] = (
        "taxonomy",
        "concept_scheme",
        "class",
        "individual",
        "property_definition",
    ),
) -> dict[str, F1Metrics]:
    """
    Compute per-node-type precision/recall/F1 over identifier sets.

    Args:
        produced_by_type: mapping of node_type → iterable of produced identifiers
        expected_by_type: mapping of node_type → iterable of expected identifiers
        node_types: which node types to score (always returned, even if empty)

    Returns:
        Mapping of node_type → F1Metrics
    """
    out: dict[str, F1Metrics] = {}
    for nt in node_types:
        produced = set(produced_by_type.get(nt, []) or [])
        expected = set(expected_by_type.get(nt, []) or [])
        out[nt] = _score_set(produced, expected, nt)
    return out


# ---------------------------------------------------------------------------- #
# Hierarchy correctness                                                        #
# ---------------------------------------------------------------------------- #


def compute_hierarchy_correctness(
    produced_class_parents: Mapping[str, str | None],
    canon: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Fraction of expected parent_class_identifier edges produced correctly.

    Args:
        produced_class_parents: mapping of produced class identifier → parent identifier
            (None for root classes)
        canon: the canon master dict (from canon.json)

    Returns:
        {"edges_expected", "edges_correct", "ratio"}
    """
    expected_edges: set[tuple[str, str | None]] = set()
    for cls in canon.get("class_hierarchy", []):
        expected_edges.add((cls["identifier"], cls.get("parent_class_identifier")))

    correct = 0
    for ident, expected_parent in expected_edges:
        actual_parent = produced_class_parents.get(ident, "<missing>")
        if actual_parent == expected_parent:
            correct += 1

    total = len(expected_edges)
    return {
        "edges_expected": total,
        "edges_correct": correct,
        "ratio": (correct / total) if total else 0.0,
    }


# ---------------------------------------------------------------------------- #
# Multi-sense disambiguation                                                   #
# ---------------------------------------------------------------------------- #


def compute_multi_sense_disambiguation_score(
    produced_lexical_senses_by_term: Mapping[str, int],
    canon: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Score the produced lexical-sense counts against canon's expected counts.

    For each multi-sense term in `canon.cross_paper_resolutions`, a term is
    "correctly disambiguated" if its produced lexical-sense count equals the
    canon's `expected_sense_count`. Over-splitting (1 → 3) and under-splitting
    (3 → 1) are both penalised — single-sense terms must produce exactly one
    sense, multi-sense terms must produce exactly the expected number.

    Args:
        produced_lexical_senses_by_term: mapping of term identifier → count of
            distinct lexical_senses produced
        canon: the canon master dict

    Returns:
        {"terms_evaluated", "terms_correct", "ratio", "per_term": {term: bool}}
    """
    resolutions = canon.get("cross_paper_resolutions", {}) or {}
    per_term: dict[str, bool] = {}
    for term, info in resolutions.items():
        expected = int(info.get("expected_sense_count", 0))
        actual = int(produced_lexical_senses_by_term.get(term, 0))
        per_term[term] = actual == expected

    total = len(per_term)
    correct = sum(1 for v in per_term.values() if v)
    return {
        "terms_evaluated": total,
        "terms_correct": correct,
        "ratio": (correct / total) if total else 0.0,
        "per_term": per_term,
    }


# ---------------------------------------------------------------------------- #
# Reference grounding rate                                                     #
# ---------------------------------------------------------------------------- #


def compute_reference_grounding_rate(
    produced_classes: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """
    Fraction of produced classes with at least one external_reference.

    Args:
        produced_classes: iterable of class dicts each with an `external_references` key

    Returns:
        {"classes_total", "classes_grounded", "rate"}
    """
    classes = list(produced_classes)
    grounded = sum(1 for c in classes if (c.get("external_references") or []))
    total = len(classes)
    return {
        "classes_total": total,
        "classes_grounded": grounded,
        "rate": (grounded / total) if total else 0.0,
    }


# ---------------------------------------------------------------------------- #
# Identifier slug validity                                                     #
# ---------------------------------------------------------------------------- #


def compute_identifier_slug_validity(
    produced_identifiers: Iterable[str | None],
) -> dict[str, Any]:
    """
    Fraction of identifiers conforming to the slug pattern. Post-migration
    f319bb8dc961 mandates 100% on taxonomy/concept_scheme/class/property_definition.

    Args:
        produced_identifiers: iterable of identifier strings (may include None)

    Returns:
        {"identifiers_total", "identifiers_valid", "rate", "invalid_examples": [...]}
    """
    identifiers = list(produced_identifiers)
    valid_count = 0
    invalid_examples: list[str | None] = []
    for ident in identifiers:
        if ident is not None and _SLUG_PATTERN.match(str(ident)):
            valid_count += 1
        elif len(invalid_examples) < 10:
            invalid_examples.append(ident)
    total = len(identifiers)
    return {
        "identifiers_total": total,
        "identifiers_valid": valid_count,
        "rate": (valid_count / total) if total else 0.0,
        "invalid_examples": invalid_examples,
    }


# ---------------------------------------------------------------------------- #
# Color presence                                                               #
# ---------------------------------------------------------------------------- #


def compute_color_presence_rate(
    produced_colors_by_type: Mapping[str, Iterable[str | None]],
) -> dict[str, dict[str, Any]]:
    """
    Per node-type populated rate for the `color` field (valid hex only).

    Args:
        produced_colors_by_type: mapping of node_type → iterable of color values
            (None for missing/unset)

    Returns:
        Mapping of node_type → {"total", "with_color", "rate"}
    """
    out: dict[str, dict[str, Any]] = {}
    for node_type, values in produced_colors_by_type.items():
        values_list = list(values)
        with_color = sum(
            1 for v in values_list if v and _HEX_COLOR_PATTERN.match(str(v))
        )
        total = len(values_list)
        out[node_type] = {
            "total": total,
            "with_color": with_color,
            "rate": (with_color / total) if total else 0.0,
        }
    return out


# ---------------------------------------------------------------------------- #
# Embedding presence                                                           #
# ---------------------------------------------------------------------------- #


def compute_embedding_presence_rate(
    produced_classes: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """
    Fraction of produced classes with a non-empty `embedding`.

    Args:
        produced_classes: iterable of class dicts each with an `embedding` key
            (None or empty list when absent)

    Returns:
        {"classes_total", "classes_with_embedding", "rate"}
    """
    classes = list(produced_classes)
    with_embedding = sum(
        1 for c in classes if c.get("embedding") not in (None, [], b"", "")
    )
    total = len(classes)
    return {
        "classes_total": total,
        "classes_with_embedding": with_embedding,
        "rate": (with_embedding / total) if total else 0.0,
    }


# ---------------------------------------------------------------------------- #
# Aggregate                                                                    #
# ---------------------------------------------------------------------------- #


def aggregate_canon_metrics(
    produced_by_type: Mapping[str, Iterable[str]],
    expected_by_type: Mapping[str, Iterable[str]],
    produced_class_parents: Mapping[str, str | None],
    produced_lexical_senses_by_term: Mapping[str, int],
    produced_classes: Iterable[Mapping[str, Any]],
    produced_identifiers: Iterable[str | None],
    produced_colors_by_type: Mapping[str, Iterable[str | None]],
    canon: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Bundle every canon metric into a single block suitable for benchmark reports.

    Returns:
        Nested dict with the canon-specific metric block.
    """
    per_type = compute_per_node_type_f1(produced_by_type, expected_by_type)
    avg_f1 = sum(m.f1 for m in per_type.values()) / len(per_type) if per_type else 0.0

    classes_list = list(produced_classes)

    return {
        "per_node_type_f1": {k: v.to_dict() for k, v in per_type.items()},
        "avg_node_type_f1": avg_f1,
        "hierarchy_correctness": compute_hierarchy_correctness(
            produced_class_parents, canon
        ),
        "multi_sense_disambiguation": compute_multi_sense_disambiguation_score(
            produced_lexical_senses_by_term, canon
        ),
        "reference_grounding_rate": compute_reference_grounding_rate(classes_list),
        "identifier_slug_validity": compute_identifier_slug_validity(
            produced_identifiers
        ),
        "color_presence_rate": compute_color_presence_rate(produced_colors_by_type),
        "embedding_presence_rate": compute_embedding_presence_rate(classes_list),
    }
