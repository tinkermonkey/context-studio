#!/usr/bin/env python
"""
Closed-loop quality optimizer for the open extraction pipelines (Phase 6).

Runs an open_v1 pipeline over the quality fixtures, reads the metrics, and
autonomously sweeps its configuration knobs (coordinate ascent) to maximize the
primary metric — re-running deterministically each iteration and keeping only
changes that do not regress below the frozen baseline. Every evaluation is
appended to the _metrics JSONL telemetry for provenance, and a baseline-vs-best
scoreboard is printed.

Because open_v1 rule-mode synthesis uses NO LLM, this entire loop runs OFFLINE
and deterministically at zero cost — the autonomous config-knob optimization the
closed-loop design calls for.

Autonomy + guardrails (per the "fully autonomous" decision):
  - Config-knob sweep (this script): free, deterministic, always-on.
  - Regression gate: a candidate is accepted only if its primary metric is >=
    the frozen baseline; the loop never moves to a worse config.
  - Provenance: every evaluation is emitted to _metrics/<pipeline>.jsonl with an
    incrementing config_version.
  - Live extension (documented, not run here): rewriting prompts/orchestrator
    logic and refreshing LLM cassettes for the llm/hybrid synthesis modes is the
    cost-capped half of the loop; gate it on a token budget before enabling.

Usage (from local-server/, venv active):
    python scripts/quality_loop.py --pipeline schema
    python scripts/quality_loop.py --pipeline individual --passes 2
"""

import argparse
import asyncio
import os
import random
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from uuid import uuid4

from adapters.clustering.sklearn_clusterer import SklearnClusterer
from adapters.embedding.caching_embedding_service import CachingEmbeddingService
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    get_open_v1_config as get_individual_open_config,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionState
from domain.pipelines.schema_extraction.configurations.open_v1 import (
    get_open_v1_config as get_schema_open_config,
)
from domain.pipelines.schema_extraction.open_orchestrator import (
    OpenSchemaExtractionOrchestrator,
)
from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionState
from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture
from tests.integration.pipelines._harness.dataset_split import (
    INDIVIDUAL_EXTRACTION_DEV_SCENARIOS,
)
from tests.integration.pipelines._harness.metrics import (
    precision_recall_f1,
    soft_precision_recall_f1,
)
from tests.integration.pipelines._harness.report import MetricsEmitter, read_scoreboard
from tests.integration.pipelines.test_quality_individual_extraction import extract_triple_key
from tests.integration.pipelines.test_quality_schema_extraction import (
    QUALITY_SCENARIOS as SCHEMA_SCENARIOS,
)
from tests.integration.pipelines.test_quality_schema_extraction import (
    compute_quality_metrics as schema_metrics,
)

_METRICS_DIR = (
    Path(__file__).parent.parent / "tests" / "integration" / "fixtures" / "pipelines" / "_metrics"
)

# Search spaces (the closed-loop optimization knobs).
_SCHEMA_SPACE: dict[str, list] = {
    "tf_idf_threshold": [0.0, 0.05, 0.1],
    "cluster_distance_threshold": [0.15, 0.2, 0.25, 0.3, 0.35],
    "top_n": [6, 8, 10, 12],
}
# Note: tf_idf_threshold is intentionally absent — relations are dependency-
# structural and not TF-IDF filtered, so it has no effect on the individual flow.
#
# Every knob here is a real, consumed field of IndividualOpenV1Config (see
# domain/pipelines/individual_extraction/configurations/open_v1.py) — nothing
# below is a placeholder for an unbuilt feature (karpathy_loop_design.md §4.1).
# ground_to_schema / require_schema_match / similarity_threshold / kinds_to_search
# only change orchestrator output when a SchemaVectorIndex is wired in; the
# fixture-based quality harness runs with schema_index=None (no ontology data
# in the fixtures to index), so sweeping them is currently a documented no-op
# rather than a fabricated knob — the moment a real index is wired into this
# harness, the sweep starts exercising it for free.
#
# 2*3*4*2*2*3 = 288 combinations — well under the ~10^3 threshold where
# successive-halving would be worth the added complexity over plain
# coordinate ascent (see coordinate_ascent's restart docstring).
_INDIVIDUAL_SPACE: dict[str, list] = {
    "predicate_form": ["surface", "lemma"],
    "relation_confidence": [0.3, 0.5, 0.7],
    "similarity_threshold": [0.35, 0.45, 0.55, 0.65],
    "ground_to_schema": [False, True],
    "require_schema_match": [False, True],
    "kinds_to_search": [
        ["class"],
        ["class", "property_definition"],
        ["class", "property_definition", "relationship"],
    ],
}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


async def evaluate_schema(orchestrator_ports, config) -> dict[str, float]:
    """Run open schema extraction over all scenarios; return mean metrics."""
    nlp, embedding, clusterer = orchestrator_ports
    orch = OpenSchemaExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=nlp,
        embedding_service=embedding,
        clusterer=clusterer,
        config=config,
    )
    keys = ["class_jaccard", "property_jaccard", "connection_overlap", "brier"]
    acc: dict[str, list[float]] = {k: [] for k in keys}
    for scenario in SCHEMA_SCENARIOS:
        fixture = dict(load_fixture("schema_extraction", scenario))
        if "text" in fixture and "documents" not in fixture:
            fixture["documents"] = [fixture.pop("text")]
        state = SchemaExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=fixture,
        )
        result_state = await orch.execute(state)
        actual = {"status": result_state.current_status.value, "result": result_state.result or {}}
        metrics = schema_metrics(load_expected_output("schema_extraction", scenario), actual)
        for k in keys:
            acc[k].append(metrics[k])
    return {k: _mean(v) for k, v in acc.items()}


def _make_embed_fn(embedding):
    """Cache label -> embedding vector lookups for the soft-metric's tier-3 comparisons."""
    cache: dict[str, list[float]] = {}

    def embed(label: str) -> list[float]:
        if label not in cache:
            cache[label] = embedding.embed(label)
        return cache[label]

    return embed


async def evaluate_individual(orchestrator_ports, config, embed_fn) -> dict[str, float]:
    """
    Run open individual extraction over the DEV split; return mean dev metrics.

    Per karpathy_loop_design.md §4.1, Loop A's objective is mean soft-F1 on dev,
    gated on strict-F1(dev) never regressing below the incumbent — so this
    computes both: `strict_f1` (exact-tuple match, the production floor metric)
    and `soft_f1` (tiered partial credit — see _harness/metrics.py). Only the
    fixed dev scenarios (_harness/dataset_split.py) are evaluated; holdout is
    reserved for Loop B/C's acceptance gate and must never influence knob
    selection, so it is intentionally never computed here.
    """
    nlp, embedding, _ = orchestrator_ports
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=nlp,
        embedding_service=embedding,
        schema_index=None,
        config=config,
    )
    strict_scores: list[float] = []
    soft_scores: list[float] = []
    for scenario in INDIVIDUAL_EXTRACTION_DEV_SCENARIOS:
        fixture = dict(load_fixture("individual_extraction", scenario))
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture,
        )
        result_state = await orch.execute(state)
        expected = load_expected_output("individual_extraction", scenario)
        expected_keys = [
            extract_triple_key(t) for t in expected.get("result", {}).get("triples", [])
        ]
        actual_keys = [
            extract_triple_key(t) for t in (result_state.result or {}).get("triples", [])
        ]
        strict_scores.append(precision_recall_f1(expected_keys, actual_keys).f1)
        soft_scores.append(soft_precision_recall_f1(expected_keys, actual_keys, embed_fn).f1)
    return {"soft_f1": _mean(soft_scores), "strict_f1": _mean(strict_scores)}


async def coordinate_ascent(
    evaluate,
    base_config,
    space,
    primary,
    emitter,
    pipeline_tag,
    passes,
    floor_key: str | None = None,
    restarts: int = 1,
    rng: random.Random | None = None,
):
    """
    Per-knob optimization under a regression gate, with random restarts.

    For each knob, tries each value (holding the current best for other
    knobs), keeping a value only if it strictly improves the `primary` metric
    *and* does not push `floor_key` below the incumbent baseline. `floor_key`
    defaults to `primary` itself, reproducing the original single-metric
    regression gate (schema pipeline; individual passes floor_key="strict_f1"
    against primary="soft_f1" per karpathy_loop_design.md §4.1 — maximize soft-
    F1(dev), never trade away strict-F1(dev)).

    `restarts` controls how many independent ascent passes are run: restart 0
    always starts at `base_config` with the knobs in declared order (the
    original, deterministic greedy behavior). Restarts 1..N-1 shuffle the knob
    order and jitter the starting point (a random value per knob) before
    ascending — a plain single-start greedy pass demonstrably plateaus at
    baseline (documentation/karpathy_loop_design.md §4.1). Every restart can
    only ever *raise* the global best; a restart that wanders somewhere worse
    is simply discarded; it cannot regress the winner from an earlier restart
    or push the floor metric below the incumbent baseline.

    Escalating to successive halving (allocating fewer evals to weaker
    starting points early) is future work, only worth the added complexity if
    the search space grows past ~10^3 combinations — it does not today.
    """
    floor_key = floor_key or primary
    rng = rng or random.Random(0)

    baseline_metrics = await evaluate(dict(base_config))
    baseline_primary = baseline_metrics[primary]
    baseline_floor = baseline_metrics[floor_key]
    best_config = dict(base_config)
    best_metrics = dict(baseline_metrics)
    best_primary = baseline_primary
    evals = 0
    emitter.emit(
        pipeline_type=pipeline_tag,
        fixture_id="aggregate",
        model="open_v1",
        config_ref="baseline",
        config_version=evals,
        metrics=baseline_metrics,
        mode="offline",
        source="closed_loop",
    )
    print(
        f"baseline {primary} = {baseline_primary:.3f}  "
        f"({floor_key} floor = {baseline_floor:.3f})  ({_fmt(baseline_metrics)})"
    )

    for restart in range(max(1, restarts)):
        if restart == 0:
            # Deterministic greedy pass from the incumbent, knobs in declared order.
            current_config = dict(base_config)
            current_primary = baseline_primary
            knob_order = list(space.keys())
        else:
            knob_order = list(space.keys())
            rng.shuffle(knob_order)
            jittered = {knob: rng.choice(values) for knob, values in space.items()}
            jittered_metrics = await evaluate(jittered)
            evals += 1
            emitter.emit(
                pipeline_type=pipeline_tag,
                fixture_id="aggregate",
                model="open_v1",
                config_ref=f"restart_{restart}_start",
                config_version=evals,
                metrics=jittered_metrics,
                mode="offline",
                source="closed_loop",
            )
            # A jittered start only becomes this restart's ascent origin if it
            # doesn't already violate the floor gate; otherwise fall back to
            # the incumbent so the restart still explores a shuffled knob
            # order without starting from a disqualified point. The global-
            # best ratchet is gated identically — a floor-violating jittered
            # start must never become (or contaminate) best_metrics/best_config,
            # even if its primary metric looks better in isolation.
            print(
                f"restart {restart}: jittered start {_fmt(jittered_metrics)} "
                f"(order={knob_order})"
            )
            if jittered_metrics[floor_key] + 1e-9 >= baseline_floor:
                current_config = jittered
                current_primary = jittered_metrics[primary]
                if jittered_metrics[primary] > best_primary + 1e-9:
                    best_primary = jittered_metrics[primary]
                    best_metrics = jittered_metrics
                    best_config = dict(current_config)
            else:
                current_config = dict(base_config)
                current_primary = baseline_primary

        for _pass in range(passes):
            for knob in knob_order:
                for value in space[knob]:
                    if current_config.get(knob) == value:
                        continue
                    trial = {**current_config, knob: value}
                    metrics = await evaluate(trial)
                    evals += 1
                    emitter.emit(
                        pipeline_type=pipeline_tag,
                        fixture_id="aggregate",
                        model="open_v1",
                        config_ref="candidate",
                        config_version=evals,
                        metrics=metrics,
                        mode="offline",
                        source="closed_loop",
                    )
                    meets_floor = metrics[floor_key] + 1e-9 >= baseline_floor
                    improved_locally = metrics[primary] > current_primary + 1e-9
                    accept = meets_floor and improved_locally
                    marker = "✓ accept" if accept else "  reject"
                    print(
                        f"  [restart {restart}] {marker}  {knob}={value!s:<14} "
                        f"{primary}={metrics[primary]:.3f} (local best {current_primary:.3f}, "
                        f"global best {best_primary:.3f})"
                    )
                    if accept:
                        current_config = trial
                        current_primary = metrics[primary]
                        if metrics[primary] > best_primary + 1e-9:
                            best_primary = metrics[primary]
                            best_metrics = metrics
                            best_config = dict(current_config)

    # Regression gate: the loop must not have moved below baseline on either
    # the metric it optimized or the metric it was told never to trade away.
    assert best_primary >= baseline_primary - 1e-9, "regression gate violated (primary)"
    assert best_metrics[floor_key] >= baseline_floor - 1e-9, "regression gate violated (floor)"
    emitter.emit(
        pipeline_type=pipeline_tag,
        fixture_id="aggregate",
        model="open_v1",
        config_ref="tuned",
        config_version=evals + 1,
        metrics=best_metrics,
        mode="offline",
        source="closed_loop",
    )
    return best_config, baseline_metrics, best_metrics, baseline_primary, best_primary, evals


def _fmt(metrics: dict[str, float]) -> str:
    return ", ".join(f"{k}={v:.3f}" for k, v in metrics.items())


async def _amain(args) -> int:
    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        print("ERROR: spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        return 1
    # Memoize .embed(label) across the whole coordinate-ascent sweep: each
    # candidate config re-runs the same open_v1 pipeline with only the knobs
    # changed, so grounding embeds the same labels every eval. Wrapping the
    # single shared embedding service collapses those repeats to one forward
    # pass per distinct label; embed_batch (reindex_all) passes through.
    embedding_service = CachingEmbeddingService(SentenceTransformerEmbedding())
    ports = (nlp, embedding_service, SklearnClusterer())
    emitter = MetricsEmitter(_METRICS_DIR)

    if args.pipeline == "schema":
        evaluate = lambda cfg: evaluate_schema(ports, cfg)  # noqa: E731
        base = get_schema_open_config()
        space, primary, tag = _SCHEMA_SPACE, "class_jaccard", "quality_loop_schema_extraction"
        floor_key = primary
        restarts = 1
    else:
        embed_fn = _make_embed_fn(embedding_service)
        evaluate = lambda cfg: evaluate_individual(ports, cfg, embed_fn)  # noqa: E731
        base = get_individual_open_config()
        space, primary, tag = _INDIVIDUAL_SPACE, "soft_f1", "quality_loop_individual_extraction"
        # Never trade the floor metric away (karpathy_loop_design.md §4.1): the
        # objective is soft-F1(dev), but a candidate is only ever accepted if
        # strict-F1(dev) hasn't regressed below the incumbent.
        floor_key = "strict_f1"
        restarts = args.restarts

    print(
        f"\n══ closed-loop optimization: {args.pipeline} "
        f"(primary={primary}, floor={floor_key}, restarts={restarts}) ══"
    )
    best_config, base_m, best_m, base_p, best_p, evals = await coordinate_ascent(
        evaluate,
        base,
        space,
        primary,
        emitter,
        tag,
        args.passes,
        floor_key=floor_key,
        restarts=restarts,
        rng=random.Random(args.seed),
    )

    print("\n══ scoreboard ══")
    print(f"  evaluations:      {evals}")
    print(f"  baseline {primary}: {base_p:.3f}  ({_fmt(base_m)})")
    print(f"  best     {primary}: {best_p:.3f}  ({_fmt(best_m)})")
    print(f"  improvement:      {best_p - base_p:+.3f}")
    tuned_knobs = {k: best_config[k] for k in space if best_config[k] != base[k]}
    print(f"  winning knobs:    {tuned_knobs or '(baseline already optimal)'}")
    print(f"  telemetry:        {_METRICS_DIR / (tag + '.jsonl')}")

    leaderboard = read_scoreboard(_METRICS_DIR / f"{tag}.jsonl")
    print(f"  scoreboard refs:  {sorted(leaderboard)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Closed-loop quality optimizer")
    parser.add_argument("--pipeline", choices=["schema", "individual"], default="schema")
    parser.add_argument("--passes", type=int, default=2, help="coordinate-ascent passes")
    parser.add_argument(
        "--restarts",
        type=int,
        default=3,
        help="random restarts for the individual pipeline's coordinate ascent (ignored for schema)",
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="RNG seed for restart shuffling/jitter (determinism)"
    )
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
