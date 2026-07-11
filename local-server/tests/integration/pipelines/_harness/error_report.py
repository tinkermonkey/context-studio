"""Per-triple failure-stage classification and error-report artifacts (§3.2).

Every GT triple the strict metric misses is classified into one failure
stage, checked in this order (first match wins):

    candidate_missing    - neither the subject nor the object label appears
                            anywhere among the actual output's subject/object
                            labels (lemma/stem-normalized) — the pipeline never
                            surfaced the entity at all.
    relation_not_derived - both entities were surfaced somewhere, but no
                            actual triple ever pairs them together, under any
                            predicate.
    label_mismatch       - some actual triple pairs matching entities, but its
                            subject/object labels are not exactly the GT
                            labels (a lemma/stem or chunk-boundary variant).
    predicate_mismatch   - an actual triple has the exact GT subject and
                            object labels; only the predicate differs.

This is the "look at your errors" step of the Karpathy loop, precomputed: the
report is the primary input to experimenter agents (§4.3). Depends only on
`metrics.py` — no other infrastructure — so it runs against any pipeline's
triple output.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from tests.integration.pipelines._harness.metrics import EmbedFn, Triple, label_match_tier

CANDIDATE_MISSING = "candidate_missing"
RELATION_NOT_DERIVED = "relation_not_derived"
LABEL_MISMATCH = "label_mismatch"
PREDICATE_MISMATCH = "predicate_mismatch"

_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


@dataclass
class MissedTriple:
    """One GT triple the strict metric missed, with its failure classification."""

    expected: Triple
    stage: str
    nearest_actual: Optional[Triple]
    source_sentence: str


@dataclass
class ScenarioReport:
    """Metrics + missed-triple diagnostics for one scenario."""

    scenario: str
    split: str
    strict: dict
    soft: dict
    candidate_recall: float
    predicate_recall: float
    label_accuracy: dict
    missed_triples: list[MissedTriple] = field(default_factory=list)


def classify_stage(
    expected: Triple, actual_triples: list[Triple], embed_fn: Optional[EmbedFn] = None
) -> tuple[str, Optional[Triple]]:
    """
    Classify why a single missed GT triple was missed.

    Uses the same tiered label-match rule as `candidate_recall`/
    `predicate_recall` (`label_match_tier`, which includes the >= 0.85
    embedding-cosine tier, not just lemma/stem equality) so a label those
    aggregate diagnostics count as "present" is never classified
    `candidate_missing`/`relation_not_derived` here — keeping the per-triple
    stage counts (which drive Loop C's target selection) in agreement with
    the coverage metrics they're supposed to explain.

    Returns (stage, nearest_actual) where `nearest_actual` is the actual
    triple that best illustrates the classification (None for
    `candidate_missing`, where nothing in the output is close).
    """
    exp_subj, exp_pred, exp_obj = expected

    def present(label: str) -> bool:
        return any(
            label_match_tier(label, candidate, embed_fn) > 0
            for triple in actual_triples
            for candidate in (triple[0], triple[2])
        )

    if not present(exp_subj) or not present(exp_obj):
        return CANDIDATE_MISSING, None

    paired = [
        t
        for t in actual_triples
        if label_match_tier(t[0], exp_subj, embed_fn) > 0
        and label_match_tier(t[2], exp_obj, embed_fn) > 0
    ]
    if not paired:
        return RELATION_NOT_DERIVED, None

    exact_pair = [t for t in paired if t[0] == exp_subj and t[2] == exp_obj]
    if not exact_pair:
        return LABEL_MISMATCH, paired[0]

    return PREDICATE_MISMATCH, exact_pair[0]


def find_source_sentence(text: str, expected: Triple) -> str:
    """
    Find the sentence in the source text most likely to contain a GT triple.

    Splits on sentence-ending punctuation (a stdlib-only heuristic — this is a
    diagnostic aid for experimenter agents, not an NLP-grade sentence
    segmenter) and returns the first sentence mentioning the subject or object
    surface text, case-insensitively. Falls back to "" if no sentence matches
    (e.g. the label was itself synthesized/normalized rather than quoted).
    """
    if not text:
        return ""
    subject_label, _predicate, object_label = expected
    needles = [n.lower() for n in (subject_label, object_label) if n]
    if not needles:
        return ""
    for sentence in _SENTENCE_SPLIT_PATTERN.split(text.strip()):
        lowered = sentence.lower()
        if any(needle in lowered for needle in needles):
            return sentence.strip()
    return ""


def build_missed_triples(
    source_text: str,
    expected_triples: list[Triple],
    actual_triples: list[Triple],
    embed_fn: Optional[EmbedFn] = None,
) -> list[MissedTriple]:
    """Build the missed-triple report entries for one scenario (strict misses only)."""
    actual_set = set(actual_triples)
    missed = []
    for expected in expected_triples:
        if expected in actual_set:
            continue
        stage, nearest = classify_stage(expected, actual_triples, embed_fn)
        missed.append(
            MissedTriple(
                expected=expected,
                stage=stage,
                nearest_actual=nearest,
                source_sentence=find_source_sentence(source_text, expected),
            )
        )
    return missed


def generate_run_id() -> str:
    """A sortable, collision-resistant run id: UTC timestamp + short random suffix."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:8]}"


def _failure_stage_counts(reports: list[ScenarioReport]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for report in reports:
        for missed in report.missed_triples:
            counts[missed.stage] = counts.get(missed.stage, 0) + 1
    return counts


def _render_markdown_digest(run_id: str, reports: list[ScenarioReport]) -> str:
    """Short markdown digest: top failure classes, 5 worst scenarios, examples."""
    lines = [f"# Individual extraction error report — {run_id}", ""]

    stage_counts = _failure_stage_counts(reports)
    lines.append("## Top failure classes")
    lines.append("")
    if stage_counts:
        for stage, count in sorted(stage_counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"- **{stage}**: {count}")
    else:
        lines.append("- (no missed GT triples — strict metric found every triple)")
    lines.append("")

    lines.append("## 5 worst scenarios (by strict F1)")
    lines.append("")
    worst = sorted(reports, key=lambda r: (r.strict.get("f1", 0.0), r.scenario))[:5]
    lines.append("| scenario | split | strict F1 | soft F1 | candidate_recall | predicate_recall |")
    lines.append("|---|---|---|---|---|---|")
    for r in worst:
        lines.append(
            f"| {r.scenario} | {r.split} | {r.strict.get('f1', 0.0):.3f} | "
            f"{r.soft.get('f1', 0.0):.3f} | {r.candidate_recall:.3f} | {r.predicate_recall:.3f} |"
        )
    lines.append("")

    lines.append("## Examples")
    lines.append("")
    examples = [(report.scenario, missed) for report in worst for missed in report.missed_triples][
        :5
    ]
    if not examples:
        lines.append("(no missed triples to show)")
    for scenario, missed in examples:
        lines.append(f"- **{scenario}** [{missed.stage}]")
        lines.append(f"  - expected: `{missed.expected}`")
        lines.append(f"  - nearest actual: `{missed.nearest_actual}`")
        if missed.source_sentence:
            lines.append(f'  - source: "{missed.source_sentence}"')
    lines.append("")

    return "\n".join(lines)


def write_report(
    run_id: str, reports: list[ScenarioReport], reports_dir: Path | str
) -> tuple[Path, Path]:
    """
    Write the JSON error report and its markdown digest for one evaluation run.

    Args:
        run_id: Identifier for this run (see `generate_run_id`).
        reports: Per-scenario metrics + missed-triple diagnostics.
        reports_dir: Directory to write into (created if missing), typically
            `local-server/experiments/reports/`.

    Returns:
        (json_path, markdown_path)
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    dev_reports = [r for r in reports if r.split == "dev"]
    holdout_reports = [r for r in reports if r.split == "holdout"]

    def _mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenarios": {r.scenario: asdict(r) for r in reports},
        "dev_mean": {
            "strict_f1": _mean([r.strict.get("f1", 0.0) for r in dev_reports]),
            "soft_f1": _mean([r.soft.get("f1", 0.0) for r in dev_reports]),
        },
        "holdout_mean": {
            "strict_f1": _mean([r.strict.get("f1", 0.0) for r in holdout_reports]),
            "soft_f1": _mean([r.soft.get("f1", 0.0) for r in holdout_reports]),
        },
        "failure_stage_counts": _failure_stage_counts(reports),
    }

    json_path = reports_dir / f"{run_id}.json"
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    markdown_path = reports_dir / f"{run_id}.md"
    with open(markdown_path, "w") as f:
        f.write(_render_markdown_digest(run_id, reports))

    return json_path, markdown_path
