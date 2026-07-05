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
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from uuid import uuid4

from adapters.clustering.sklearn_clusterer import SklearnClusterer
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
from tests.integration.pipelines._harness.report import MetricsEmitter, read_scoreboard
from tests.integration.pipelines.test_quality_individual_extraction import (
    QUALITY_SCENARIOS as INDIVIDUAL_SCENARIOS,
)
from tests.integration.pipelines.test_quality_individual_extraction import (
    compute_quality_metrics as individual_metrics,
)
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
_SCHEMA_SPACE = {
    "tf_idf_threshold": [0.0, 0.05, 0.1],
    "cluster_distance_threshold": [0.15, 0.2, 0.25, 0.3, 0.35],
    "top_n": [6, 8, 10, 12],
}
# Note: tf_idf_threshold is intentionally absent — relations are dependency-
# structural and not TF-IDF filtered, so it has no effect on the individual flow.
_INDIVIDUAL_SPACE = {
    "predicate_form": ["surface", "lemma"],
    "relation_confidence": [0.3, 0.5, 0.7],
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


async def evaluate_individual(orchestrator_ports, config) -> dict[str, float]:
    """Run open individual extraction over all scenarios; return mean metrics."""
    nlp, embedding, _ = orchestrator_ports
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=nlp,
        embedding_service=embedding,
        schema_index=None,
        config=config,
    )
    keys = ["precision", "recall", "f1", "brier"]
    acc: dict[str, list[float]] = {k: [] for k in keys}
    for scenario in INDIVIDUAL_SCENARIOS:
        fixture = dict(load_fixture("individual_extraction", scenario))
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture,
        )
        result_state = await orch.execute(state)
        expected = load_expected_output("individual_extraction", scenario)
        metrics = individual_metrics(
            expected.get("result", {}).get("triples", []),
            (result_state.result or {}).get("triples", []),
        )
        for k in keys:
            acc[k].append(metrics[k])
    return {k: _mean(v) for k, v in acc.items()}


async def coordinate_ascent(evaluate, base_config, space, primary, emitter, pipeline_tag, passes):
    """
    Greedy per-knob optimization under a regression gate.

    Starts at the baseline config and, for each knob, tries each value (holding
    the current best for other knobs), keeping a value only if it strictly
    improves the primary metric. Never moves to a worse-than-baseline config.
    """
    config = dict(base_config)
    baseline_metrics = await evaluate(config)
    baseline_primary = baseline_metrics[primary]
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
    print(f"baseline {primary} = {baseline_primary:.3f}  ({_fmt(baseline_metrics)})")

    for _pass in range(passes):
        for knob, values in space.items():
            for value in values:
                if config.get(knob) == value:
                    continue
                trial = {**config, knob: value}
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
                improved = metrics[primary] > best_primary + 1e-9
                marker = "✓ accept" if improved else "  reject"
                print(
                    f"  {marker}  {knob}={value!s:<14} {primary}={metrics[primary]:.3f}"
                    f" (best {best_primary:.3f})"
                )
                if improved:
                    config = trial
                    best_primary = metrics[primary]
                    best_metrics = metrics

    # Regression gate: the loop must not have moved below baseline.
    assert best_primary >= baseline_primary - 1e-9, "regression gate violated"
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
    return config, baseline_metrics, best_metrics, baseline_primary, best_primary, evals


def _fmt(metrics: dict[str, float]) -> str:
    return ", ".join(f"{k}={v:.3f}" for k, v in metrics.items())


async def _amain(args) -> int:
    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        print("ERROR: spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        return 1
    ports = (nlp, SentenceTransformerEmbedding(), SklearnClusterer())
    emitter = MetricsEmitter(_METRICS_DIR)

    if args.pipeline == "schema":
        evaluate = lambda cfg: evaluate_schema(ports, cfg)  # noqa: E731
        base = get_schema_open_config()
        space, primary, tag = _SCHEMA_SPACE, "class_jaccard", "quality_loop_schema_extraction"
    else:
        evaluate = lambda cfg: evaluate_individual(ports, cfg)  # noqa: E731
        base = get_individual_open_config()
        space, primary, tag = _INDIVIDUAL_SPACE, "f1", "quality_loop_individual_extraction"

    print(f"\n══ closed-loop optimization: {args.pipeline} (primary={primary}) ══")
    best_config, base_m, best_m, base_p, best_p, evals = await coordinate_ascent(
        evaluate, base, space, primary, emitter, tag, args.passes
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
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
