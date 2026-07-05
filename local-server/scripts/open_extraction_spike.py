#!/usr/bin/env python
"""
Open-extraction spike (read-only research tool, Phase 1).

Runs the open spaCy extraction over the schema-extraction quality fixtures and
prints, per scenario: how many concept/relation candidates the OPEN approach
surfaces, and a rough recall of the ground-truth class labels (the "superset"
check). This is for eyeballing the openness/recall of the pre-clustering stage,
not a pass/fail gate.

Usage (from local-server/, venv active):
    python scripts/open_extraction_spike.py                 # all scenarios
    python scripts/open_extraction_spike.py distributed_systems
    python scripts/open_extraction_spike.py --thresholds 0.0,0.05,0.1
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.clustering.sklearn_clusterer import SklearnClusterer
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from domain.extraction.open_extraction import (
    OpenExtractionParams,
    build_concept_candidates,
    build_relation_candidates,
    select_cluster_representatives,
    synthesize_label,
)

FIXTURES = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "pipelines"
    / "schema_extraction"
)

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")


def _label_parts(label: str) -> list[str]:
    """Split a CamelCase/underscore class label into lowercased word parts."""
    cleaned = label.replace("_", " ")
    parts = _CAMEL.findall(cleaned) or cleaned.split()
    return [p.lower() for p in parts if len(p) > 2]


def _word_pool(candidates) -> set[str]:
    """Union of candidate surface words (>2 chars) and lemmas, lowercased."""
    pool: set[str] = set()
    for c in candidates:
        pool.add(c.lemma.lower())
        for w in c.text.lower().split():
            if len(w) > 2:
                pool.add(w)
    return pool


def _covers(part: str, pool: set[str]) -> bool:
    """Fuzzy stem match so 'partition' covers 'partitioning' and vice versa."""
    for w in pool:
        if w == part:
            return True
        if len(part) >= 4 and len(w) >= 4 and (w.startswith(part) or part.startswith(w)):
            return True
    return False


def _recall(gt_labels: list[str], pool: set[str]) -> tuple[float, list[str]]:
    """Fraction of ground-truth labels whose word parts all appear in the pool."""
    if not gt_labels:
        return 1.0, []
    missed = []
    covered = 0
    for label in gt_labels:
        parts = _label_parts(label)
        if parts and all(_covers(p, pool) for p in parts):
            covered += 1
        else:
            missed.append(label)
    return covered / len(gt_labels), missed


def _text_of(inp: dict) -> str:
    """Extract input text, tolerating the 'text' and 'documents' fixture shapes."""
    if inp.get("text"):
        return inp["text"]
    parts = []
    for doc in inp.get("documents", []):
        if isinstance(doc, str):
            parts.append(doc)
        elif isinstance(doc, dict):
            parts.append(doc.get("text") or doc.get("content") or "")
    return "\n".join(p for p in parts if p)


def _jaccard(a: set[str], b: set[str]) -> float:
    """Set-overlap Jaccard index (matches the harness metric)."""
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def _gt_parts(gt_labels: list[str]) -> set[str]:
    """Union of all word parts across the ground-truth class labels."""
    parts: set[str] = set()
    for label in gt_labels:
        parts.update(_label_parts(label))
    return parts


def _scenarios(selected: str | None) -> list[str]:
    if selected:
        return [selected]
    return sorted(
        d.name for d in FIXTURES.iterdir() if d.is_dir() and (d / "input.json").exists()
    )


def run_synthesis(scenarios, nlp, tfidf, cluster_threshold, top_ns):
    """Full open schema pipeline: cluster → PascalCase labels → EXACT-match jaccard vs GT."""
    embedder = SentenceTransformerEmbedding()
    clusterer = SklearnClusterer()
    agg = {n: {"jaccard": [], "precision": [], "recall": []} for n in top_ns}

    for scenario in scenarios:
        inp = json.loads((FIXTURES / scenario / "input.json").read_text())
        expected = json.loads((FIXTURES / scenario / "expected.json").read_text())
        text = _text_of(inp)
        if not text:
            continue
        gt = {c["label"] for c in expected.get("result", {}).get("extracted_classes", [])}

        result = nlp.process_open(text)
        cands = build_concept_candidates(result, OpenExtractionParams(tf_idf_threshold=tfidf))
        if not cands:
            continue
        vectors = embedder.embed_batch([c.text for c in cands])
        assignments = clusterer.cluster(vectors, distance_threshold=cluster_threshold)
        reps = select_cluster_representatives(cands, assignments)  # sorted by priority,score

        print(f"━━ {scenario}  (GT {len(gt)}: {', '.join(sorted(gt))})")
        for n in top_ns:
            # PascalCase labels for the top-N representatives, de-duplicated in order.
            labels: list[str] = []
            for rep in reps:
                label = synthesize_label(rep)
                if label and label not in labels:
                    labels.append(label)
                if len(labels) >= n:
                    break
            actual = set(labels)
            inter = len(gt & actual)
            jac = inter / len(gt | actual) if (gt | actual) else 1.0
            precision = inter / len(actual) if actual else 0.0
            recall = inter / len(gt) if gt else 1.0
            agg[n]["jaccard"].append(jac)
            agg[n]["precision"].append(precision)
            agg[n]["recall"].append(recall)
            hit = ", ".join(sorted(gt & actual)) or "—"
            print(
                f"   top{n:<2}: jaccard {jac:.2f} | P {precision:.2f} R {recall:.2f}"
                f" | matched: {hit}"
            )
        print()

    print("══ means across scenarios (FLOOR class_jaccard>=0.60) ══")
    for n in top_ns:
        d = agg[n]
        k = len(d["jaccard"]) or 1
        print(
            f"   top{n}: jaccard {sum(d['jaccard'])/k:.3f} | "
            f"P {sum(d['precision'])/k:.2f} | R {sum(d['recall'])/k:.2f}"
        )


def run_clustering(scenarios, nlp, tfidf, cluster_thresholds):
    """Embed open concept candidates, cluster them, and report distillation."""
    embedder = SentenceTransformerEmbedding()
    clusterer = SklearnClusterer()
    agg = {dt: {"distill": [], "recall": [], "jaccard": []} for dt in cluster_thresholds}

    for scenario in scenarios:
        inp = json.loads((FIXTURES / scenario / "input.json").read_text())
        expected = json.loads((FIXTURES / scenario / "expected.json").read_text())
        text = _text_of(inp)
        if not text:
            continue
        gt = [c["label"] for c in expected.get("result", {}).get("extracted_classes", [])]
        gt_parts = _gt_parts(gt)

        result = nlp.process_open(text)
        cands = build_concept_candidates(result, OpenExtractionParams(tf_idf_threshold=tfidf))
        if not cands:
            continue
        vectors = embedder.embed_batch([c.text for c in cands])

        print(f"━━ {scenario}  ({len(cands)} candidates @tfidf>={tfidf} → cluster)")
        print(f"   ground-truth classes ({len(gt)}): {', '.join(gt)}")
        for dt in cluster_thresholds:
            assignments = clusterer.cluster(vectors, distance_threshold=dt, min_cluster_size=1)
            reps = select_cluster_representatives(cands, assignments)
            distill = len(reps) / len(cands)
            recall, _ = _recall(gt, _word_pool(reps))
            rep_parts = _word_pool(reps)
            jac = _jaccard(gt_parts, rep_parts)
            agg[dt]["distill"].append(distill)
            agg[dt]["recall"].append(recall)
            agg[dt]["jaccard"].append(jac)
            print(
                f"   dist>={dt:<4}: {len(reps):3d} reps ({distill:4.0%} of cands)"
                f" | recall {recall:5.1%} | word-jaccard {jac:.2f}"
                f" | sample: {', '.join(r.lemma for r in reps[:6])}"
            )
        print()

    print("══ means across scenarios ══")
    for dt in cluster_thresholds:
        d = agg[dt]
        n = len(d["distill"]) or 1
        print(
            f"   dist>={dt}: distill {sum(d['distill'])/n:4.0%} | "
            f"recall {sum(d['recall'])/n:5.1%} | word-jaccard {sum(d['jaccard'])/n:.2f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Open-extraction spike")
    parser.add_argument("scenario", nargs="?", help="single scenario (default: all)")
    parser.add_argument(
        "--thresholds",
        default="0.0,0.1",
        help="comma-separated tf_idf_thresholds to report recall at",
    )
    parser.add_argument(
        "--cluster",
        action="store_true",
        help="embed candidates, cluster them, and report distillation/recall",
    )
    parser.add_argument(
        "--cluster-thresholds",
        default="0.1,0.2,0.3,0.4",
        help="comma-separated cosine distance thresholds for clustering",
    )
    parser.add_argument(
        "--tfidf",
        type=float,
        default=0.0,
        help="tf_idf_threshold for the candidates fed into clustering",
    )
    parser.add_argument(
        "--synthesize",
        action="store_true",
        help="full pipeline: cluster → PascalCase labels → exact-match jaccard vs GT",
    )
    parser.add_argument(
        "--top-ns", default="6,8,10,12", help="comma-separated top-N values to sweep"
    )
    parser.add_argument(
        "--cluster-threshold", type=float, default=0.25, help="single cluster distance threshold"
    )
    args = parser.parse_args()
    thresholds = [float(t) for t in args.thresholds.split(",")]

    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        print("ERROR: spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        return 1

    scenarios = _scenarios(args.scenario)
    print(f"spaCy model: {nlp._model_name} | scenarios: {len(scenarios)}\n")

    if args.synthesize:
        top_ns = [int(n) for n in args.top_ns.split(",")]
        run_synthesis(scenarios, nlp, args.tfidf, args.cluster_threshold, top_ns)
        return 0

    if args.cluster:
        cluster_thresholds = [float(t) for t in args.cluster_thresholds.split(",")]
        run_clustering(scenarios, nlp, args.tfidf, cluster_thresholds)
        return 0

    agg = {t: [] for t in thresholds}
    for scenario in scenarios:
        inp = json.loads((FIXTURES / scenario / "input.json").read_text())
        expected = json.loads((FIXTURES / scenario / "expected.json").read_text())
        text = _text_of(inp)
        if not text:
            print(f"━━ {scenario}  (skipped: no input text)\n")
            continue
        gt = [c["label"] for c in expected.get("result", {}).get("extracted_classes", [])]

        result = nlp.process_open(text)
        relations = build_relation_candidates(result)

        print(f"━━ {scenario}  ({result.sentence_count} sentences, {len(result.tokens)} tokens)")
        print(f"   ground-truth classes ({len(gt)}): {', '.join(gt)}")
        for t in thresholds:
            cands = build_concept_candidates(result, OpenExtractionParams(tf_idf_threshold=t))
            distinct = len({c.lemma for c in cands})
            recall, missed = _recall(gt, _word_pool(cands))
            agg[t].append(recall)
            miss = f" | missed: {', '.join(missed)}" if missed else ""
            print(
                f"   @tfidf>={t:<4}: {len(cands):3d} candidates, {distinct:3d} distinct lemmas"
                f" | class recall {recall:5.1%}{miss}"
            )
        print(f"   relation candidates: {len(relations)}")
        for r in relations[:6]:
            print(f"      {r.subject!r} --{r.predicate}--> {r.object!r}")
        print()

    print("══ mean class recall across scenarios ══")
    for t in thresholds:
        vals = agg[t]
        mean = sum(vals) / len(vals) if vals else 0.0
        print(f"   @tfidf>={t}: {mean:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
