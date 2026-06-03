"""
Assertion helpers for the canon-driven pipeline test cycle.

These helpers compare pipeline output against the gold-standard ontology slice
in `datafiles/canon/software_architecture/`. The assertions are deliberately
threshold-based (precision/recall/F1) rather than strict-equality, because an
extractor's output is allowed to differ from gold in tolerable ways (extra
correct entities, label normalization). Hard equality would punish improvements.

All helpers raise AssertionError with structured detail messages on failure so
the pytest output explains the gap rather than just reporting a number.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# Slug pattern from domain/ontology/value_objects.py — enforced by the migration
# f319bb8dc961_add_color_column_and_require_identifier_.py.
_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-f]{6}$")


# ---------------------------------------------------------------------------- #
# Canon loading                                                                #
# ---------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CanonBundle:
    """Parsed canon directory contents: master slice + per-paper fixtures."""

    canon: dict[str, Any]
    papers: dict[str, dict[str, Any]]
    canon_dir: Path

    @property
    def class_identifiers(self) -> set[str]:
        return {c["identifier"] for c in self.canon["class_hierarchy"]}

    @property
    def scheme_identifiers(self) -> set[str]:
        return {s["identifier"] for s in self.canon["concept_schemes"]}

    @property
    def property_identifiers(self) -> set[str]:
        return {p["identifier"] for p in self.canon["property_definitions"]}


def load_canon(canon_dir: str | Path) -> CanonBundle:
    """
    Load the master canon.json plus all paper_*.json fixtures from a directory.

    Returns:
        CanonBundle with both the master slice and a name→paper lookup.

    Raises:
        FileNotFoundError: if canon.json or any paper fixture is missing.
    """
    root = Path(canon_dir)
    canon_path = root / "canon.json"
    if not canon_path.is_file():
        raise FileNotFoundError(f"canon.json not found in {root}")

    canon = json.loads(canon_path.read_text(encoding="utf-8"))

    papers: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("paper_*.json")):
        paper = json.loads(path.read_text(encoding="utf-8"))
        name = paper.get("name") or path.stem.replace("paper_", "")
        papers[name] = paper

    return CanonBundle(canon=canon, papers=papers, canon_dir=root)


# ---------------------------------------------------------------------------- #
# Triple-level assertions                                                      #
# ---------------------------------------------------------------------------- #


def _normalize(s: str) -> str:
    """Lowercase, strip underscores/whitespace for tolerant id comparison."""
    return re.sub(r"[\s_-]+", "", s.lower())


def _produced_triple_key(triple: dict[str, Any]) -> tuple[str, str, str]:
    subject = triple.get("subject", {}) or {}
    predicate = triple.get("predicate", {}) or {}
    obj = triple.get("object", {}) or {}

    subject_id = subject.get("id") or subject.get("label") or ""
    predicate_id = (
        predicate.get("property_definition_id") or predicate.get("label") or ""
    )
    object_id = obj.get("id") or obj.get("label") or obj.get("value") or ""

    return (
        _normalize(str(subject_id)),
        _normalize(str(predicate_id)),
        _normalize(str(object_id)),
    )


def _expected_triple_key(rel: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _normalize(str(rel.get("subject", ""))),
        _normalize(str(rel.get("predicate", ""))),
        _normalize(str(rel.get("object", ""))),
    )


@dataclass(frozen=True)
class TripleMetrics:
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    missing_expected: list[tuple[str, str, str]]
    extra_produced: list[tuple[str, str, str]]


def score_triples(
    produced: Iterable[dict[str, Any]],
    expected: Iterable[dict[str, Any]],
) -> TripleMetrics:
    """Compute precision/recall/F1 on a (subject, predicate, object) tuple match."""
    produced_keys = {_produced_triple_key(t) for t in produced}
    expected_keys = {_expected_triple_key(r) for r in expected}

    tp = len(produced_keys & expected_keys)
    fp = len(produced_keys - expected_keys)
    fn = len(expected_keys - produced_keys)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        (2 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )

    return TripleMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        missing_expected=sorted(expected_keys - produced_keys),
        extra_produced=sorted(produced_keys - expected_keys),
    )


def assert_triples_match(
    produced: Iterable[dict[str, Any]],
    expected: Iterable[dict[str, Any]],
    *,
    min_recall: float = 0.5,
    min_precision: float = 0.0,
    min_f1: float = 0.0,
    paper_name: str = "<unknown>",
) -> TripleMetrics:
    """
    Assert produced triples meet recall / precision / F1 thresholds vs gold.

    Recall is the primary signal — extractors that find the right things but
    also surface extras are still useful; extractors that miss the right things
    are broken.

    Returns the metrics so the caller can log them.
    """
    metrics = score_triples(produced, expected)
    failures = []
    if metrics.recall < min_recall:
        failures.append(f"recall={metrics.recall:.2f} < min {min_recall:.2f}")
    if metrics.precision < min_precision:
        failures.append(f"precision={metrics.precision:.2f} < min {min_precision:.2f}")
    if metrics.f1 < min_f1:
        failures.append(f"f1={metrics.f1:.2f} < min {min_f1:.2f}")
    if failures:
        msg_lines = [
            f"Triple-match assertion failed for paper {paper_name!r}: "
            + ", ".join(failures),
            (
                f"  tp={metrics.true_positives} fp={metrics.false_positives} "
                f"fn={metrics.false_negatives}"
            ),
        ]
        if metrics.missing_expected:
            msg_lines.append("  missing (recall gap):")
            for triple in metrics.missing_expected[:10]:
                msg_lines.append(f"    - {triple}")
            if len(metrics.missing_expected) > 10:
                msg_lines.append(
                    f"    ... and {len(metrics.missing_expected) - 10} more"
                )
        raise AssertionError("\n".join(msg_lines))
    return metrics


# ---------------------------------------------------------------------------- #
# Schema-level assertions                                                      #
# ---------------------------------------------------------------------------- #


def assert_identifier_slugs_populated(repo: Any) -> None:
    """
    Every taxonomy, concept_scheme, class, and property_definition must have
    a non-null identifier matching `^[a-z][a-z0-9_]{1,63}$`.

    Enforced by migration f319bb8dc961.
    """
    offenders: list[str] = []

    for tax in repo.list_taxonomies():
        identifier = getattr(tax, "identifier", None)
        if not identifier or not _SLUG_PATTERN.match(identifier):
            offenders.append(f"taxonomy {tax.id} identifier={identifier!r}")

    # Schemes / classes / property defs — repos vary; iterate defensively.
    for getter, label in (
        ("list_concept_schemes", "concept_scheme"),
        ("list_classes", "class"),
        ("list_property_definitions", "property_definition"),
    ):
        method = getattr(repo, getter, None)
        if method is None:
            continue
        try:
            entries = method()
        except TypeError:
            # Some repos require an arg (e.g. taxonomy_id) — skip silently.
            continue
        for entry in entries:
            identifier = getattr(entry, "identifier", None)
            if not identifier or not _SLUG_PATTERN.match(identifier):
                offenders.append(f"{label} {entry.id} identifier={identifier!r}")

    if offenders:
        msg = "\n".join(
            ["Identifier slugs missing or malformed:"] + [f"  - {o}" for o in offenders]
        )
        raise AssertionError(msg)


def assert_color_present(repo: Any, *, for_node_types: Iterable[str]) -> None:
    """
    Every taxonomy / concept_scheme / class entity persisted must have a `color`
    matching `#rrggbb`. Optional for individuals and property_definitions.
    """
    offenders: list[str] = []
    node_types = set(for_node_types)

    if "taxonomy" in node_types:
        for tax in repo.list_taxonomies():
            color = getattr(tax, "color", None)
            if color is None or not _HEX_COLOR_PATTERN.match(color):
                offenders.append(f"taxonomy {tax.id} color={color!r}")

    if "concept_scheme" in node_types and hasattr(repo, "list_concept_schemes"):
        for sch in repo.list_concept_schemes():
            color = getattr(sch, "color", None)
            if color is None or not _HEX_COLOR_PATTERN.match(color):
                offenders.append(f"concept_scheme {sch.id} color={color!r}")

    if "class" in node_types and hasattr(repo, "list_classes"):
        for cls in repo.list_classes():
            color = getattr(cls, "color", None)
            if color is None or not _HEX_COLOR_PATTERN.match(color):
                offenders.append(f"class {cls.id} color={color!r}")

    if offenders:
        msg = "\n".join(
            ["Color missing or malformed:"] + [f"  - {o}" for o in offenders]
        )
        raise AssertionError(msg)


def assert_class_hierarchy_matches(repo: Any, canon: CanonBundle) -> None:
    """
    For each expected parent→child edge in canon.class_hierarchy, assert the
    repository's stored classes form the same parent relationship via
    `parent_class_id`. Classes are looked up by `identifier`.
    """
    if not hasattr(repo, "list_classes"):
        raise AssertionError(
            "Repo does not expose list_classes; cannot verify hierarchy"
        )

    by_identifier: dict[str, Any] = {}
    for cls in repo.list_classes():
        ident = getattr(cls, "identifier", None)
        if ident:
            by_identifier[ident] = cls

    missing_classes: list[str] = []
    wrong_parents: list[str] = []

    for expected in canon.canon["class_hierarchy"]:
        ident = expected["identifier"]
        expected_parent = expected.get("parent_class_identifier")
        actual = by_identifier.get(ident)
        if actual is None:
            missing_classes.append(ident)
            continue

        actual_parent_id = getattr(actual, "parent_class_id", None)
        expected_parent_obj = (
            by_identifier.get(expected_parent) if expected_parent else None
        )
        expected_parent_id = (
            getattr(expected_parent_obj, "id", None) if expected_parent_obj else None
        )

        if expected_parent_id != actual_parent_id:
            wrong_parents.append(
                f"{ident}: expected parent identifier {expected_parent!r}, "
                f"actual parent_class_id {actual_parent_id!r}"
            )

    failures = []
    if missing_classes:
        failures.append(
            "missing classes: "
            + ", ".join(missing_classes[:10])
            + (
                f" (and {len(missing_classes)-10} more)"
                if len(missing_classes) > 10
                else ""
            )
        )
    if wrong_parents:
        failures.append("wrong parents:\n  - " + "\n  - ".join(wrong_parents[:10]))

    if failures:
        raise AssertionError("Class hierarchy mismatch:\n  " + "\n  ".join(failures))


def assert_lexical_senses_distinguish(
    repo: Any,
    term_identifier: str,
    *,
    expected_sense_count: int,
) -> None:
    """
    A property_definition with the given identifier must carry exactly the
    expected number of distinct `lexical_senses`. Used to verify multi-sense
    disambiguation (e.g., `service` has 3 senses, `clock` has 2).
    """
    if not hasattr(repo, "list_property_definitions"):
        raise AssertionError("Repo does not expose list_property_definitions")

    target = None
    for prop in repo.list_property_definitions():
        if getattr(prop, "identifier", None) == term_identifier:
            target = prop
            break

    if target is None:
        raise AssertionError(
            f"PropertyDefinition with identifier {term_identifier!r} not found in repo"
        )

    senses = getattr(target, "lexical_senses", None) or []
    distinct_labels = {getattr(s, "label", None) or "" for s in senses}
    if len(distinct_labels) != expected_sense_count:
        raise AssertionError(
            f"{term_identifier}: expected {expected_sense_count} distinct lexical senses, "
            f"got {len(distinct_labels)}: {sorted(distinct_labels)}"
        )


def assert_external_references_populated(
    repo: Any,
    *,
    min_coverage: float = 0.3,
) -> None:
    """
    At least `min_coverage` fraction of classes in the repository must carry
    at least one `external_reference`. This catches regressions in the Reference
    Enrich layer where DBpedia/Wikidata grounding silently fails.
    """
    if not hasattr(repo, "list_classes"):
        raise AssertionError("Repo does not expose list_classes")

    classes = list(repo.list_classes())
    if not classes:
        raise AssertionError("No classes in repo; cannot assert reference coverage")

    grounded = sum(1 for cls in classes if getattr(cls, "external_references", None))
    coverage = grounded / len(classes)
    if coverage < min_coverage:
        raise AssertionError(
            f"External reference coverage {coverage:.2f} < min {min_coverage:.2f} "
            f"({grounded}/{len(classes)} classes grounded)"
        )


def assert_source_run_id_lineage(
    repo: Any,
    *,
    run_id: str,
    min_count: int = 1,
) -> None:
    """
    At least `min_count` classes in the repository must record the given run_id
    as their `source_run_id`. Verifies extraction provenance is wired through
    the persistence layer.
    """
    if not hasattr(repo, "list_classes"):
        raise AssertionError("Repo does not expose list_classes")

    tagged = [
        cls
        for cls in repo.list_classes()
        if getattr(cls, "source_run_id", None) == run_id
    ]
    if len(tagged) < min_count:
        raise AssertionError(
            f"Expected ≥{min_count} classes tagged with source_run_id={run_id!r}, "
            f"found {len(tagged)}"
        )
