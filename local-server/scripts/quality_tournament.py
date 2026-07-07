#!/usr/bin/env python
"""
Loop B — variant tournament runner for individual extraction (karpathy_loop_design.md §4.2).

Reintroduces the legacy POC's parallel-variant harness on the new stack: a
named **variant registry** maps a variant name to (an evaluation seam over its
orchestrator, its base config, its knob space). For every registered variant,
this script:

  1. Runs Phase 3's Loop A (coordinate ascent, `scripts/quality_loop.py`) to
     tune the variant's knobs on the dev split, maximizing soft-F1 without
     regressing strict-F1 (§4.1).
  2. Re-evaluates the tuned variant across the full corpus (dev + holdout) and
     writes a Phase 1 error report (JSON + markdown digest) under
     `experiments/reports/`.
  3. Aggregates dev/holdout means for strict-F1, soft-F1, and the Phase 1
     diagnostics (candidate_recall, predicate_recall, label_accuracy).

Once every variant has been tuned and scored, the variants are ranked by mean
dev soft-F1 (the hill-climbing signal; holdout is advisory only — see §3.3/§6
and NEEDS_HUMAN_REVIEW.md, since 2 of the 5 holdout scenarios have unreviewed,
agent-drafted ground truth) into a scoreboard: a telemetry JSONL row per variant (same
`_metrics/<pipeline_type>.jsonl` schema `quality_loop.py` uses, with the new
diagnostic keys) plus a markdown digest under `experiments/reports/`.

Loop A/B never make live LLM calls (§4.1/§5) — every variant here must be
fully replayable from recorded cassettes or, like `open_v1`, use no LLM at
all. See `build_registry()` for which variants are registered today and why.

Usage (from local-server/, venv active):
    python scripts/quality_tournament.py --pipeline individual
"""

import argparse
import asyncio
import os
import random
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    get_open_v1_config,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionState
from scripts.quality_loop import (
    _INDIVIDUAL_SPACE,
    _METRICS_DIR,
    _make_embed_fn,
    coordinate_ascent,
)
from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture
from tests.integration.pipelines._harness.dataset_split import (
    INDIVIDUAL_EXTRACTION_DEV_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    split_for,
)
from tests.integration.pipelines._harness.error_report import (
    ScenarioReport,
    build_missed_triples,
    generate_run_id,
    write_report,
)
from tests.integration.pipelines._harness.metrics import (
    candidate_recall,
    label_accuracy,
    precision_recall_f1,
    predicate_recall,
    soft_precision_recall_f1,
)
from tests.integration.pipelines._harness.report import MetricsEmitter
from tests.integration.pipelines.test_quality_individual_extraction import (
    compute_quality_metrics,
    extract_triple_key,
)

# local-server/experiments/reports/ — see local-server/experiments/README.md
_EXPERIMENTS_REPORTS_DIR = Path(__file__).parent.parent / "experiments" / "reports"

# Scoreboard telemetry: same _metrics/ directory quality_loop.py writes to,
# under its own pipeline_type file (tests/integration/fixtures/pipelines/_metrics/
# quality_tournament_individual_extraction.jsonl).
_TOURNAMENT_PIPELINE_TAG = "quality_tournament_individual_extraction"

RunScenario = Callable[[dict[str, Any], str], Awaitable[list[dict]]]


@dataclass(frozen=True)
class Variant:
    """
    One registered algorithm variant under Loop B evaluation (karpathy_loop_design.md §4.2).

    `run_scenario(config, scenario) -> raw triple dicts` is the single seam a
    variant must implement to participate: both Loop A's coordinate-ascent
    objective and this script's full-corpus error-report generation are built
    on it, so adding a variant never requires touching the tournament loop
    itself.

    `knob_space` must cover every key of `base_config` that Loop A is allowed
    to tune — `coordinate_ascent`'s random-restart jitter replaces the config
    wholesale from `knob_space` (see `scripts/quality_loop.py`), so a knob
    present in `base_config` but absent from `knob_space` would silently drop
    out of jittered restarts. A variant with no tunable knobs (e.g. a pure
    LLM-prompt variant with nothing for Loop A to sweep) should pass an empty
    `knob_space` and `restarts=0` when running the tournament, or add a single
    no-op knob.
    """

    name: str
    base_config: dict[str, Any]
    knob_space: dict[str, list]
    run_scenario: RunScenario


_REGISTRY: dict[str, Variant] = {}


def register_variant(variant: Variant) -> None:
    """
    Register a variant so `quality_tournament.py` evaluates it.

    Future Loop C experiment branches (karpathy_loop_design.md §4.3) that get
    accepted call this to add themselves to the tournament — the registry
    takes no dependency on unbuilt variants; only implementations that exist
    in code today are registered by `build_registry()` below.
    """
    _REGISTRY[variant.name] = variant


def registered_variants() -> dict[str, Variant]:
    """Return a snapshot of the current variant registry."""
    return dict(_REGISTRY)


def _make_open_v1_variant(nlp, embedding) -> Variant:
    """Build the `open_v1` variant: the rule-mode spaCy dependency-triple pipeline."""

    async def run_scenario(config: dict[str, Any], scenario: str) -> list[dict]:
        orch = OpenIndividualExtractionOrchestrator(
            llm_provider=None,
            nlp_processor=nlp,
            embedding_service=embedding,
            schema_index=None,
            config=config,
        )
        fixture = dict(load_fixture("individual_extraction", scenario))
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture,
        )
        result_state = await orch.execute(state)
        return (result_state.result or {}).get("triples", [])

    return Variant(
        name="open_v1",
        base_config=get_open_v1_config(),
        knob_space=dict(_INDIVIDUAL_SPACE),
        run_scenario=run_scenario,
    )


def build_registry(nlp, embedding) -> dict[str, Variant]:
    """
    Seed today's variant registry (karpathy_loop_design.md §4.2).

    Only variants that both exist in code *and* can be evaluated entirely
    offline (Loop A/B never make live LLM calls — §4.1/§5) are registered:

    - 'open_v1': the rule-mode spaCy dependency-triple pipeline. Makes no LLM
      calls at all, so it always qualifies.

    'default' (the LLM pipeline, `IndividualExtractionOrchestrator`) is
    deliberately NOT registered yet. Phase 2 fixed the live-mode output
    contract bug — it now produces structurally valid, non-zero triples
    against the real Anthropic API (see
    `test_quality_individual_extraction.py::test_live_quality_scenario`) —
    but no cassettes have been recorded for individual_extraction under
    `tests/integration/fixtures/cassettes/individual_extraction/`, so there is nothing
    for this offline tournament to replay. Once cassettes exist (record them
    via `pytest --refresh-cassettes -k test_quality_scenario_with_metrics`
    against the individual_extraction quality suite, with an LLM provider
    configured), add a `Variant` here whose `run_scenario` replays through
    `CassetteLLMProvider` (see `_harness/cassettes.py` and the cassette-mode
    branch of `test_quality_scenario_with_metrics`) and register it — no
    change to the tournament loop itself is required.
    """
    register_variant(_make_open_v1_variant(nlp, embedding))
    return registered_variants()


def _make_dev_evaluator(variant: Variant, embed_fn) -> Callable[[dict], Awaitable[dict]]:
    """Build a Loop A `evaluate(config) -> {"soft_f1", "strict_f1"}` closure over dev scenarios."""

    async def evaluate(config: dict[str, Any]) -> dict[str, float]:
        strict_scores: list[float] = []
        soft_scores: list[float] = []
        for scenario in INDIVIDUAL_EXTRACTION_DEV_SCENARIOS:
            expected_raw = load_expected_output("individual_extraction", scenario).get(
                "result", {}
            ).get("triples", [])
            actual_raw = await variant.run_scenario(config, scenario)
            expected_keys = [extract_triple_key(t) for t in expected_raw]
            actual_keys = [extract_triple_key(t) for t in actual_raw]
            strict_scores.append(precision_recall_f1(expected_keys, actual_keys).f1)
            soft_scores.append(soft_precision_recall_f1(expected_keys, actual_keys, embed_fn).f1)
        return {
            "soft_f1": sum(soft_scores) / len(soft_scores) if soft_scores else 0.0,
            "strict_f1": sum(strict_scores) / len(strict_scores) if strict_scores else 0.0,
        }

    return evaluate


async def _build_scenario_reports(
    variant: Variant, config: dict[str, Any], embed_fn
) -> list[ScenarioReport]:
    """Evaluate `variant` under `config` across the full corpus (dev + holdout), per scenario."""
    reports: list[ScenarioReport] = []
    for scenario in INDIVIDUAL_EXTRACTION_SCENARIOS:
        fixture_input = load_fixture("individual_extraction", scenario)
        expected_output = load_expected_output("individual_extraction", scenario)
        expected_triples_raw = expected_output.get("result", {}).get("triples", [])
        actual_triples_raw = await variant.run_scenario(config, scenario)

        expected_keys = [extract_triple_key(t) for t in expected_triples_raw]
        actual_keys = [extract_triple_key(t) for t in actual_triples_raw]

        strict = compute_quality_metrics(expected_triples_raw, actual_triples_raw)
        soft = soft_precision_recall_f1(expected_keys, actual_keys, embed_fn)

        reports.append(
            ScenarioReport(
                scenario=scenario,
                split=split_for(scenario),
                strict={
                    "precision": strict["precision"],
                    "recall": strict["recall"],
                    "f1": strict["f1"],
                },
                soft={"precision": soft.precision, "recall": soft.recall, "f1": soft.f1},
                candidate_recall=candidate_recall(expected_keys, actual_keys, embed_fn),
                predicate_recall=predicate_recall(expected_keys, actual_keys, embed_fn),
                label_accuracy=label_accuracy(expected_keys, actual_keys, embed_fn),
                missed_triples=build_missed_triples(
                    fixture_input.get("text", ""), expected_keys, actual_keys, embed_fn
                ),
            )
        )
    return reports


def _aggregate(reports: list[ScenarioReport], split: str) -> dict[str, float]:
    """Mean strict/soft F1 + Phase 1 diagnostics (§3.1) over one split's scenario reports."""
    subset = [r for r in reports if r.split == split]

    def _mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    return {
        "strict_precision": _mean([r.strict["precision"] for r in subset]),
        "strict_recall": _mean([r.strict["recall"] for r in subset]),
        "strict_f1": _mean([r.strict["f1"] for r in subset]),
        "soft_precision": _mean([r.soft["precision"] for r in subset]),
        "soft_recall": _mean([r.soft["recall"] for r in subset]),
        "soft_f1": _mean([r.soft["f1"] for r in subset]),
        "candidate_recall": _mean([r.candidate_recall for r in subset]),
        "predicate_recall": _mean([r.predicate_recall for r in subset]),
        "label_accuracy_strict": _mean([r.label_accuracy["strict"] for r in subset]),
        "label_accuracy_soft": _mean([r.label_accuracy["soft"] for r in subset]),
    }


async def _run_variant(
    variant: Variant,
    embed_fn,
    passes: int,
    restarts: int,
    seed: int,
) -> dict[str, Any]:
    """Tune one variant with Loop A, then score the tuned config across the full corpus."""
    print(f"\n== Loop A: tuning '{variant.name}' on dev ({restarts} restarts x {passes} passes) ==")
    evaluate = _make_dev_evaluator(variant, embed_fn)
    loop_a_emitter = MetricsEmitter(_METRICS_DIR)
    best_config, _base_metrics, _best_metrics, base_primary, best_primary, evals = (
        await coordinate_ascent(
            evaluate,
            variant.base_config,
            variant.knob_space,
            "soft_f1",
            loop_a_emitter,
            f"quality_tournament_loopA_{variant.name}",
            passes,
            floor_key="strict_f1",
            restarts=restarts,
            rng=random.Random(seed),
        )
    )
    print(
        f"   baseline soft_f1={base_primary:.3f}  tuned soft_f1={best_primary:.3f}  "
        f"({evals} evaluations)"
    )

    print(f"== full-corpus evaluation: '{variant.name}' (tuned config) ==")
    scenario_reports = await _build_scenario_reports(variant, best_config, embed_fn)
    run_id = f"tournament_{variant.name}_{generate_run_id()}"
    json_path, markdown_path = write_report(run_id, scenario_reports, _EXPERIMENTS_REPORTS_DIR)
    print(f"   error report: {json_path}")

    tuned_knobs = {
        knob: best_config[knob]
        for knob in variant.knob_space
        if best_config.get(knob) != variant.base_config.get(knob)
    }

    return {
        "variant": variant.name,
        "tuned_config": best_config,
        "tuned_knobs": tuned_knobs,
        "dev": _aggregate(scenario_reports, "dev"),
        "holdout": _aggregate(scenario_reports, "holdout"),
        "error_report_json": str(json_path),
        "error_report_md": str(markdown_path),
    }


def _render_scoreboard_digest(run_id: str, results: list[dict[str, Any]]) -> str:
    """Markdown scoreboard: variants ranked by dev soft-F1, diagnostics alongside (§4.2)."""
    lines = [f"# Individual extraction variant tournament — {run_id}", ""]
    lines.append(
        "Ranked by mean dev soft-F1 (the Loop A/B hill-climbing signal, §3.1). "
        "Strict-F1 is the production floor metric. Holdout is advisory only — "
        "per §3.3/§6 it never selects the winner, because 2 of the 5 holdout "
        "scenarios (arxiv_llm_research_lab, arxiv_researcher_profile) have "
        "unreviewed, agent-drafted ground truth (see NEEDS_HUMAN_REVIEW.md)."
    )
    lines.append("")
    lines.append(
        "| rank | variant | dev strict-F1 | dev soft-F1 | candidate_recall | "
        "predicate_recall | label_acc (strict/soft) | holdout strict-F1 | holdout soft-F1 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for rank, result in enumerate(results, start=1):
        dev, holdout = result["dev"], result["holdout"]
        lines.append(
            f"| {rank} | {result['variant']} | {dev['strict_f1']:.3f} | {dev['soft_f1']:.3f} | "
            f"{dev['candidate_recall']:.3f} | {dev['predicate_recall']:.3f} | "
            f"{dev['label_accuracy_strict']:.3f}/{dev['label_accuracy_soft']:.3f} | "
            f"{holdout['strict_f1']:.3f} | {holdout['soft_f1']:.3f} |"
        )
    lines.append("")

    lines.append("## Winning knobs per variant")
    lines.append("")
    for result in results:
        lines.append(f"- **{result['variant']}**: {result['tuned_knobs'] or '(baseline already optimal)'}")
    lines.append("")

    lines.append("## Per-variant error reports")
    lines.append("")
    for result in results:
        lines.append(f"- **{result['variant']}**: {result['error_report_json']}")
    lines.append("")

    return "\n".join(lines)


async def _amain(args) -> int:
    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        print("ERROR: spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        return 1
    embedding = SentenceTransformerEmbedding()
    try:
        embedding.embed_batch(["probe"])
    except Exception as exc:
        print(f"ERROR: embedding model not available (offline cache miss): {exc}")
        return 1
    embed_fn = _make_embed_fn(embedding)

    registry = build_registry(nlp, embedding)
    if not registry:
        print("ERROR: no variants registered")
        return 1

    print(f"\n══ Loop B variant tournament: {args.pipeline} ══")
    print(f"registered variants: {sorted(registry)}")

    results = [
        await _run_variant(registry[name], embed_fn, args.passes, args.restarts, args.seed)
        for name in sorted(registry)
    ]
    results.sort(key=lambda r: r["dev"]["soft_f1"], reverse=True)

    scoreboard_emitter = MetricsEmitter(_METRICS_DIR)
    for result in results:
        scoreboard_emitter.emit(
            pipeline_type=_TOURNAMENT_PIPELINE_TAG,
            fixture_id="dev",
            model=result["variant"],
            config_ref=result["variant"],
            config_version=1,
            metrics=result["dev"],
            mode="offline",
            source="quality_tournament",
        )
        scoreboard_emitter.emit(
            pipeline_type=_TOURNAMENT_PIPELINE_TAG,
            fixture_id="holdout",
            model=result["variant"],
            config_ref=result["variant"],
            config_version=1,
            metrics=result["holdout"],
            mode="offline",
            source="quality_tournament",
        )

    run_id = f"tournament_{generate_run_id()}"
    digest = _render_scoreboard_digest(run_id, results)
    digest_path = _EXPERIMENTS_REPORTS_DIR / f"{run_id}.md"
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(digest)

    print("\n══ scoreboard (ranked by dev soft-F1) ══")
    print(digest)
    print(f"telemetry: {_METRICS_DIR / (_TOURNAMENT_PIPELINE_TAG + '.jsonl')}")
    print(f"digest:    {digest_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Loop B variant tournament runner (karpathy_loop_design.md §4.2)"
    )
    parser.add_argument("--pipeline", choices=["individual"], default="individual")
    parser.add_argument(
        "--passes", type=int, default=2, help="Loop A coordinate-ascent passes per variant"
    )
    parser.add_argument(
        "--restarts", type=int, default=3, help="Loop A random restarts per variant"
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="RNG seed for Loop A restart shuffling/jitter"
    )
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
