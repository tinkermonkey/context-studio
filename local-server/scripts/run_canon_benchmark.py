#!/usr/bin/env python3
"""
Run the canon-software-architecture benchmark and emit a report compatible with
the existing TekGen/WebNLG benchmark output format.

This script materializes the canon's gold-standard ontology slice into a
temporary SQLite database (via the demo-dataset loader), reads it back through
the ontology repository, and computes the canon-specific schema metrics
(per-node-type F1, hierarchy correctness, multi-sense disambiguation, reference
grounding, identifier slug validity, color presence, embedding presence).

The emitted JSON slots into the existing `compare_benchmarks.py` /
`diff_benchmarks.py` pipeline so the iteration loop can compare a candidate
configuration against the canon baseline alongside TekGen and WebNLG.

Default mode ("gold-load") uses the demo dataset loader to populate the DB.
This establishes the *schema integrity* baseline — every metric should be 1.0
when the canon is loaded directly. Future modes that drive the real pipeline
against the canon source_text will produce realistic gap scores.

Usage:
    python scripts/run_canon_benchmark.py \\
      --canon-dir datafiles/canon/software_architecture \\
      --out reports/canon-software-architecture.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

# Ensure local-server is in sys.path so domain/ + adapters/ + benchmark/ resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.demo.canon_loader import CanonDemoDatasetLoader
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from benchmark.canon_metrics import aggregate_canon_metrics
from domain.ontology.ports import OntologyRepository
from utils.logger import get_logger

_logger = get_logger(__name__)


# ---------------------------------------------------------------------------- #
# Canon loading                                                                #
# ---------------------------------------------------------------------------- #


def _load_canon_directory(canon_dir: Path) -> tuple[dict, dict[str, dict]]:
    canon_path = canon_dir / "canon.json"
    if not canon_path.is_file():
        raise FileNotFoundError(f"canon.json not found in {canon_dir}")
    canon = json.loads(canon_path.read_text(encoding="utf-8"))

    papers: dict[str, dict] = {}
    for path in sorted(canon_dir.glob("paper_*.json")):
        paper = json.loads(path.read_text(encoding="utf-8"))
        name = paper.get("name") or path.stem.replace("paper_", "")
        papers[name] = paper
    return canon, papers


def _expected_identifiers_by_type(canon: dict) -> dict[str, list[str]]:
    return {
        "taxonomy": [t["identifier"] for t in canon.get("taxonomies", [])],
        "concept_scheme": [s["identifier"] for s in canon.get("concept_schemes", [])],
        "class": [c["identifier"] for c in canon.get("class_hierarchy", [])],
        "property_definition": [p["identifier"] for p in canon.get("property_definitions", [])],
        "individual": [],  # canon doesn't enumerate individuals at the master level
    }


# ---------------------------------------------------------------------------- #
# Pipeline materialisation                                                     #
# ---------------------------------------------------------------------------- #


def _materialise_canon(canon_root: Path, db_path: Path) -> str:
    """
    Materialize the canon's gold-standard slice into the given database path.

    Args:
        canon_root: Parent directory containing the `software_architecture`
            canon corpus directory.
        db_path: Path where the SQLite database file should be created. The
            caller (a TemporaryDirectory context manager) owns lifecycle.

    Returns:
        The synthetic source_run_id stamped on every persisted entity.
    """
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    repo = SQLiteOntologyRepository(session_factory)
    loader = CanonDemoDatasetLoader(canon_root=canon_root, ontology_repo=cast(OntologyRepository, repo))

    run_id = str(uuid4())
    result = loader.load(name="software-architecture", run_id=run_id)
    _logger.info(
        "Loaded canon into %s: taxonomies=%d schemes=%d classes=%d props=%d",
        db_path,
        result.taxonomies,
        result.concept_schemes,
        result.classes,
        result.property_definitions,
    )
    return run_id


# ---------------------------------------------------------------------------- #
# Repo readback                                                                #
# ---------------------------------------------------------------------------- #


def _read_produced_state(db_path: Path) -> dict[str, Any]:
    """Read everything the canon benchmark needs from the produced repo."""
    engine = create_engine(f"sqlite:///{db_path}")
    session_factory = sessionmaker(bind=engine)
    repo = SQLiteOntologyRepository(session_factory)

    taxonomies = repo.list_taxonomies(limit=None)
    concept_schemes = repo.list_concept_schemes(limit=None)
    classes = repo.list_classes(limit=None)
    individuals = repo.list_individuals(limit=None)
    property_defs = repo.list_property_definitions(limit=None)

    produced_by_type = {
        "taxonomy": [t.identifier for t in taxonomies if t.identifier],
        "concept_scheme": [s.identifier for s in concept_schemes if s.identifier],
        "class": [c.identifier for c in classes if c.identifier],
        "property_definition": [p.identifier for p in property_defs if p.identifier],
        "individual": [str(i.id) for i in individuals],
    }

    by_ident = {c.identifier: c for c in classes if c.identifier}
    produced_class_parents: dict[str, str | None] = {}
    parent_id_to_identifier = {c.id: c.identifier for c in classes}
    for ident, cls in by_ident.items():
        parent_id = getattr(cls, "parent_class_id", None)
        produced_class_parents[ident] = (
            parent_id_to_identifier.get(parent_id) if parent_id else None
        )

    produced_lexical_senses_by_term: dict[str, int] = {}
    for prop in property_defs:
        if prop.identifier:
            senses = getattr(prop, "lexical_senses", None) or []
            distinct = {(getattr(s, "label", "") or "") for s in senses}
            produced_lexical_senses_by_term[prop.identifier] = len(distinct)

    produced_classes_dicts: list[dict[str, Any]] = []
    for c in classes:
        produced_classes_dicts.append(
            {
                "identifier": c.identifier,
                "external_references": list(getattr(c, "external_references", []) or []),
                "embedding": getattr(c, "embedding", None),
            }
        )

    produced_identifiers = (
        produced_by_type["taxonomy"]
        + produced_by_type["concept_scheme"]
        + produced_by_type["class"]
        + produced_by_type["property_definition"]
    )

    produced_colors_by_type = {
        "taxonomy": [getattr(t, "color", None) for t in taxonomies],
        "concept_scheme": [getattr(s, "color", None) for s in concept_schemes],
        "class": [getattr(c, "color", None) for c in classes],
    }

    return {
        "produced_by_type": produced_by_type,
        "produced_class_parents": produced_class_parents,
        "produced_lexical_senses_by_term": produced_lexical_senses_by_term,
        "produced_classes": produced_classes_dicts,
        "produced_identifiers": produced_identifiers,
        "produced_colors_by_type": produced_colors_by_type,
    }


# ---------------------------------------------------------------------------- #
# Report shaping                                                               #
# ---------------------------------------------------------------------------- #


def _shape_result_record(canon_block: dict[str, Any], dataset_name: str) -> dict[str, Any]:
    """
    Map the canon metric block into a record shape compatible with the
    Text2KGBench benchmark output, plus a `canon` sub-block holding the rich
    schema metrics.
    """
    per_type = canon_block["per_node_type_f1"]
    # Average F1 across node types as the headline "f1" value so the existing
    # diff_benchmarks summary surfaces it next to TekGen/WebNLG F1.
    f1 = canon_block["avg_node_type_f1"]
    precision_avg = sum(m["precision"] for m in per_type.values()) / max(1, len(per_type))
    recall_avg = sum(m["recall"] for m in per_type.values()) / max(1, len(per_type))
    conformance = canon_block["identifier_slug_validity"]["rate"]

    return {
        "dataset": dataset_name,
        "ontology": "software_architecture",
        "precision": precision_avg,
        "recall": recall_avg,
        "f1": f1,
        "conformance": conformance,
        "hallucination_rate": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_config": "canon-gold-load",
        "model": "demo-loader",
        "cost_usd": 0.0,
        "extraction_run_ids": [],
        "total_duration_ms": 0,
        "samples_processed": (
            canon_block["per_node_type_f1"]["class"]["true_positives"]
            + canon_block["per_node_type_f1"]["class"]["false_negatives"]
        ),
        "total_error_count": 0,
        "errors": [],
        "canon": canon_block,
    }


# ---------------------------------------------------------------------------- #
# CLI                                                                          #
# ---------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--canon-dir",
        type=Path,
        default=Path("datafiles/canon/software_architecture"),
        help="Canon corpus directory (default: datafiles/canon/software_architecture)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON path (e.g. reports/canon-software-architecture.json)",
    )
    parser.add_argument(
        "--mode",
        choices=("gold-load",),
        default="gold-load",
        help=(
            "Benchmark mode. 'gold-load' (default) materialises the canon's "
            "gold slice via the demo loader to establish a schema-integrity "
            "baseline. Future modes will drive the real pipeline against the "
            "canon source_text."
        ),
    )
    args = parser.parse_args()

    canon_dir: Path = args.canon_dir.resolve()
    out_path: Path = args.out

    if not canon_dir.is_dir():
        _logger.error("Canon directory not found: %s", canon_dir)
        return 1

    canon, _papers = _load_canon_directory(canon_dir)

    start = time.time()
    with tempfile.TemporaryDirectory(prefix="canon_bench_") as tmpdir:
        db_path = Path(tmpdir) / "canon.db"
        run_id = _materialise_canon(canon_dir.parent, db_path)
        produced = _read_produced_state(db_path)
        # TemporaryDirectory cleans up automatically on context exit. If
        # cleanup fails, Python's TemporaryDirectory logs a warning rather
        # than raising — that's the right behaviour for an ephemeral scratch.

    expected_by_type = _expected_identifiers_by_type(canon)

    canon_block = aggregate_canon_metrics(
        produced_by_type=produced["produced_by_type"],
        expected_by_type=expected_by_type,
        produced_class_parents=produced["produced_class_parents"],
        produced_lexical_senses_by_term=produced["produced_lexical_senses_by_term"],
        produced_classes=produced["produced_classes"],
        produced_identifiers=produced["produced_identifiers"],
        produced_colors_by_type=produced["produced_colors_by_type"],
        canon=canon,
    )

    result_record = _shape_result_record(canon_block, dataset_name="canon-software-architecture")
    duration_ms = int((time.time() - start) * 1000)
    result_record["total_duration_ms"] = duration_ms

    report = {
        "run_id": run_id,
        "dataset": "canon-software-architecture",
        "pipeline_config": "canon-gold-load",
        "model": "demo-loader",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_duration_ms": duration_ms,
        "total_cost_usd": 0.0,
        "ontologies_count": 1,
        "samples_processed": result_record["samples_processed"],
        "results": [result_record],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _logger.info("Wrote canon benchmark report to %s", out_path)

    # Print a compact summary to stdout for human visibility.
    print()
    print(f"=== Canon benchmark: {args.mode} ===")
    print(f"  Avg per-node-type F1     : {canon_block['avg_node_type_f1']:.4f}")
    print(
        f"  Hierarchy correctness    : "
        f"{canon_block['hierarchy_correctness']['ratio']:.4f} "
        f"({canon_block['hierarchy_correctness']['edges_correct']}/"
        f"{canon_block['hierarchy_correctness']['edges_expected']})"
    )
    print(
        f"  Multi-sense ratio        : "
        f"{canon_block['multi_sense_disambiguation']['ratio']:.4f} "
        f"({canon_block['multi_sense_disambiguation']['terms_correct']}/"
        f"{canon_block['multi_sense_disambiguation']['terms_evaluated']})"
    )
    print(
        f"  Reference grounding rate : "
        f"{canon_block['reference_grounding_rate']['rate']:.4f} "
        f"({canon_block['reference_grounding_rate']['classes_grounded']}/"
        f"{canon_block['reference_grounding_rate']['classes_total']})"
    )
    print(f"  Identifier slug validity : " f"{canon_block['identifier_slug_validity']['rate']:.4f}")
    print(
        f"  Color presence (class)   : "
        f"{canon_block['color_presence_rate'].get('class', {}).get('rate', 0.0):.4f}"
    )
    print(f"  Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
