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
dev soft-F1 (the hill-climbing signal; holdout is advisory only — see §3.3/§6:
it is two scenarios, too few to be authoritative) into a scoreboard: a
telemetry JSONL row per variant (same
`_metrics/<pipeline_type>.jsonl` schema `quality_loop.py` uses, with the new
diagnostic keys) plus a markdown digest under `experiments/reports/`.

Loop A/B never make live LLM calls (§4.1/§5) — every variant here must be
fully replayable from recorded cassettes or, like `open_v1`, use no LLM at
all. See `build_registry()` for which variants are registered today and why.

The run ends with the benchmark pass (`scripts/benchmark_replay.py`): one
target, an implementation of the pipeline type with one of its configurations
(`--implementation`, `--configuration`, each defaulting through the pipeline
registry as in that script), over the long benchmark documents, scored on the
individuals it finds against hand-made gold extractions. Its dev and holdout
rows (`benchmark_dev`, `benchmark_holdout`) are what Loop C optimises. The
triple corpus above is Loop C's regression guard for the implementation and
configuration it was recorded with (`default` with
`extraction-openrouter-default`); for any other target the guard does not
apply, and the benchmark report says so (`guard.applies`) and lists the
corpus's measure under `other_guards` instead.

A variant whose cassettes no longer answer its prompts is reported as STALE at
the top of the digest. The run exits with `EXIT_STALE_CASSETTES` when the
stale recordings are the chosen target's: its benchmark cassettes, or a
variant that runs its implementation. It exits with
`EXIT_BENCHMARK_NOT_SCORED` when the target's benchmark has no score for
another reason (not recorded, a document missing, the extraction failed).
The pipelines swallow a missing
recording, so without that check a stale cassette set reads as a pipeline
scoring low.

Usage (from local-server/, venv active):
    python scripts/quality_tournament.py --pipeline individual
    python scripts/quality_tournament.py --implementation find_then_type
"""

import argparse
import asyncio
import json
import os
import random
import sys

# Ensure both the script's directory and current working directory are in sys.path
sys.path.insert(0, os.getcwd())
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from adapters.embedding.caching_embedding_service import CachingEmbeddingService
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.in_process import InProcessEventPublisher
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import (
    SQLiteExtractionRunRepository,
)
from adapters.persistence.sqlite.models import Base
from domain.extraction.services import ExtractionService
from domain.ontology.ports import EmbeddingService
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineExecutionError
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionState,
)
from domain.pipelines.selection import RUN_PARAMETERS
from scripts import benchmark_replay
from scripts.default_pipeline_ontology import (
    DefaultPipelineOntologyResolver,
    dr_spec_available,
)
from scripts.eval_ontology import build_eval_ontology
from scripts.quality_loop import (
    _INDIVIDUAL_SPACE,
    _METRICS_DIR,
    _make_embed_fn,
    coordinate_ascent,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource
from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture
from tests.integration.pipelines._harness.cassettes import (
    CassetteLLMProvider,
    CassetteStaleError,
)
from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_DEV_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    RECOGNITION_EPISODES,
    RELABELED_ARXIV_SCENARIOS,
    REPLAY_SCENARIOS,
    WAVE4_INFORMAL_SCENARIOS,
    ontology_context_for,
    split_for,
)
from tests.integration.pipelines._harness.episode_runner import (
    EpisodeSetupError,
    run_full_pipeline_episode,
)
from tests.integration.pipelines._harness.error_report import (
    ScenarioReport,
    build_missed_triples,
    generate_run_id,
    write_report,
)
from tests.integration.pipelines._harness.metrics import (
    RecognitionMetrics,
    candidate_recall,
    label_accuracy,
    precision_recall_f1,
    predicate_recall,
    recognition_metrics,
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

# Exit code when a variant's cassettes no longer answer its prompts: its scores
# are not a measurement, and nothing downstream should read them as one.
EXIT_STALE_CASSETTES = 3

# Exit code when the chosen target's benchmark was not scored for another
# reason (not recorded, a document missing, the extraction itself failed): the
# benchmark report's `status` says which.
EXIT_BENCHMARK_NOT_SCORED = 4

# Every cassette provider a variant replayed from. The pipelines catch a missing
# recording (the extraction service returns no triples, open_v1 skips its label
# canonicalization), so without counting each provider's misses a stale cassette
# set reads as a pipeline scoring low.
_REPLAY_PROVIDERS: dict[str, list[CassetteLLMProvider]] = {}


def _track(variant: str, provider: CassetteLLMProvider) -> CassetteLLMProvider:
    """Remember a variant's cassette provider so its misses can be counted."""
    _REPLAY_PROVIDERS.setdefault(variant, []).append(provider)
    return provider


def _cassette_use(variant: str) -> dict[str, int]:
    """LLM calls a variant replayed, and how many had no recorded response."""
    providers = _REPLAY_PROVIDERS.get(variant, [])
    return {
        "calls": sum(p.calls for p in providers),
        "misses": sum(p.misses for p in providers),
    }


# Cassette location for the `default` LLM pipeline. This is the SAME path
# convention the quality suite records to (see the `cassette_dir` fixture and
# the `quality_llm_provider_factory` cassette-mode branch in
# tests/integration/pipelines/test_quality_individual_extraction.py): one file
# per scenario named `individual_extraction_<scenario>.json` under
# tests/integration/fixtures/cassettes/individual_extraction/.
# Dedicated directory for the `default` LLM pipeline's cassettes, SEPARATE from
# the quality suite's own `cassettes/individual_extraction/` set: those are
# recorded against each fixture's pinned model (claude-opus-4-7), whereas the
# default variant replays cassettes recorded against the model of
# triple_corpus_target(). Sharing a path would collide (see
# scripts/record_default_cassettes.py).
_DEFAULT_CASSETTE_DIR = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "individual_extraction_default"
)
_DEFAULT_CASSETTE_PREFIX = "individual_extraction_"

# The implementation the `default` / `default+grounding` variants run, and the
# triple corpus's cassettes were recorded with.
TRIPLE_CORPUS_IMPLEMENTATION = "default"


def scenario_input(scenario: str) -> dict[str, Any]:
    """
    A corpus scenario's input without the run parameters its fixture pins
    (model, temperature, output-token limit): a run takes those from its
    configuration (PipelineSelection.run_input), and every orchestrator
    honours a model named in its input, so a pinned one would replace it.
    """
    fixture = load_fixture("individual_extraction", scenario)
    return {key: value for key, value in fixture.items() if key not in RUN_PARAMETERS}


def triple_corpus_target() -> benchmark_replay.BenchmarkTarget:
    """
    What the `default*` variants run: the two-pass implementation (its id is
    `default`, a name: the type's default implementation is find_then_type),
    named explicitly, with the configuration its recordings were made with
    (benchmark_replay.RECORDED_WITH).

    The corpus fixtures pin claude-opus-4-7; the recorder
    (scripts/record_default_cassettes.py) and the replay here both replace it
    with this target's model. The cassette key includes the model, so the two
    MUST use the same one or every replay misses: both read it from here.
    """
    return benchmark_replay.resolve_target(TRIPLE_CORPUS_IMPLEMENTATION)


# Cassette location for the `open_v1` LLM label-canonicalization call. One file
# per scenario named `individual_canon_<scenario>.json`, recorded by
# scripts/record_individual_canonicalization_cassettes.py against the same
# eval ontology this tournament grounds against. The canonicalization prompt is
# built only from scenario-fixed inputs (spaCy mentions + their vector-retrieved
# candidate titles), so one recording per scenario replays across the whole knob
# sweep. When a scenario has no cassette the provider is None and the
# canonicalization stage self-skips.
_CANON_CASSETTE_DIR = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "individual_canonicalization"
)
_CANON_CASSETTE_PREFIX = "individual_canon_"

# Recognition episode fixtures (issue #1142 Phase 1/2): one directory per
# episode under here, each holding ordered doc_NN.json fixtures, an
# expected_entities.json coreference gold file, and a cassettes/ subdirectory
# -- see tests/integration/pipelines/_harness/episode_runner.py.
_RECOGNITION_EPISODES_DIR = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "pipelines"
    / "individual_recognition"
)

# JSONL emission tag for recognition diagnostics -- MetricsEmitter writes to
# _metrics/<pipeline_type>.jsonl, so this determines the file name.
_RECOGNITION_PIPELINE_TAG = "individual_recognition"


def _canon_cassette_path(scenario: str) -> Path:
    """Return the recorded-cassette path for one `open_v1` canonicalization scenario."""
    return _CANON_CASSETTE_DIR / f"{_CANON_CASSETTE_PREFIX}{scenario}.json"


def _canon_cassette_provider(scenario: str) -> CassetteLLMProvider | None:
    """Cassette provider for a scenario's canonicalization call, or None if unrecorded."""
    path = _canon_cassette_path(scenario)
    return _track("open_v1", CassetteLLMProvider(path)) if path.exists() else None


# Every scenario the `default` variant is asked to replay across a full
# tournament run: the dev/holdout corpus plus the always-reported diagnostic
# groups (see `_run_variant` and `dataset_split.REPLAY_SCENARIOS`). The guard in
# `build_registry` only admits `default` once a cassette exists for every one of
# these, so an admitted variant can never crash mid-tournament on a missing
# recording.
_DEFAULT_REPLAY_SCENARIOS = list(REPLAY_SCENARIOS)

RunScenario = Callable[[dict[str, Any], str], Awaitable[list[dict]]]


def _default_cassette_path(scenario: str) -> Path:
    """Return the recorded-cassette path for one `default`-pipeline scenario."""
    return _DEFAULT_CASSETTE_DIR / f"{_DEFAULT_CASSETTE_PREFIX}{scenario}.json"


def _default_cassettes_present() -> bool:
    """
    Report whether the `default` LLM pipeline can be replayed fully offline.

    True only when a recorded cassette exists for every scenario the variant
    would replay (`_DEFAULT_REPLAY_SCENARIOS`). A cassette that exists but no
    longer answers the pipeline's prompts is caught later, per call (see
    `_REPLAY_PROVIDERS`).
    """
    return all(_default_cassette_path(scenario).exists() for scenario in _DEFAULT_REPLAY_SCENARIOS)


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
    # What the variant runs, for the telemetry rows and the digest: the
    # implementation and configuration it is built from and the model its LLM
    # calls ask for. A variant is these plus the knobs of base_config.
    implementation: str = ""
    configuration: str = ""
    model: str = ""


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


def _make_open_v1_variant(nlp, embedding, eval_repo=None, eval_index=None) -> Variant:
    """Build the `open_v1` variant: the rule-mode spaCy dependency-triple pipeline.

    `eval_repo`/`eval_index` wire the imported ontology (scripts/eval_ontology.py)
    into the grounding stage so the schema-grounding knobs move the metric;
    grounding self-skips per scenario when the ontology can't be resolved.
    """
    implementation = "open_v1"
    selection = benchmark_replay.pipeline_resolver().resolve(
        benchmark_replay.PIPELINE_TYPE, implementation
    )
    orchestrator = selection.implementation

    async def run_scenario(config: dict[str, Any], scenario: str) -> list[dict]:
        orch = orchestrator(
            llm_provider=_canon_cassette_provider(scenario),
            nlp_processor=nlp,
            embedding_service=embedding,
            schema_index=eval_index,
            config=config,
            ontology_repo=eval_repo,
        )
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=selection.run_input(scenario_input(scenario)),
        )
        result_state = await orch.execute(state)
        return (result_state.result or {}).get("triples", [])

    # Enable LLM label canonicalization in the variant baseline so Loop A tunes
    # it from ON; `_INDIVIDUAL_SPACE` still offers False so the floor gate can
    # switch it back off if it fails to help.
    return Variant(
        name="open_v1",
        base_config={**selection.config, "llm_canonicalization": True},
        knob_space=dict(_INDIVIDUAL_SPACE),
        run_scenario=run_scenario,
        implementation=implementation,
        configuration=selection.configuration_ref,
        model=str(selection.parameters.get("model") or ""),
    )


def _make_default_variant(
    resolver: DefaultPipelineOntologyResolver,
    *,
    grounding: bool,
) -> Variant:
    """
    Build a `default` LLM-pipeline variant that replays entirely from cassettes.

    `run_scenario` reconstructs the exact wiring the recorder captured against
    (`scripts/record_default_cassettes.py`): the orchestrator of
    `triple_corpus_target()` (the registry's `default` implementation, with the
    model of the configuration its cassettes were recorded with) over an
    `ExtractionService` with
    `FakeEmbeddingService` / `FakeNLPProcessor` / `FakeReferenceSource`, but with
    a `CassetteLLMProvider` in place of the live provider — so no live LLM call
    is ever made (§4.1/§5). Crucially it resolves each scenario's ontology
    through the SAME `DefaultPipelineOntologyResolver` the recorder used and
    overrides `ontology_id` to that taxonomy, so the extraction prompt (whose
    only ontology-derived value is `ontology.title`) hashes to the recorded
    cassette key.

    `grounding` selects the `similarity_threshold` operating point (0.5 vs
    0.85, which drives soft-match dedup); the `ground_to_schema` /
    `require_schema_match` knobs are inert on this path (`ExtractionService`
    does not consume them and no schema index is wired into it), so
    `default` and `default+grounding` share cassettes and differ only by that
    threshold.

    Every `base_config` key also appears in `knob_space` (as a single-value
    list) so `coordinate_ascent`'s wholesale, restart-time config replacement
    can never drop a fixed key (see `Variant.knob_space`).
    """
    target = triple_corpus_target()
    name = f"{target.implementation}+grounding" if grounding else target.implementation
    base_config: dict[str, Any] = {
        "ground_to_schema": grounding,
        "require_schema_match": grounding,
        "similarity_threshold": 0.5 if grounding else 0.85,
    }

    async def run_scenario(config: dict[str, Any], scenario: str) -> list[dict]:
        ontology_repo, taxonomy, _index = resolver.get(ontology_context_for(scenario))
        provider = _track(name, CassetteLLMProvider(_default_cassette_path(scenario)))
        engine = create_local_db_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = create_session_factory(engine)
        extraction_service = ExtractionService(
            ontology_repo=ontology_repo,
            embedding_service=FakeEmbeddingService(),
            llm=provider,
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=InProcessEventPublisher(),
            extraction_repo=SQLiteExtractionRepository(session_factory),
            extraction_run_repo=SQLiteExtractionRunRepository(session_factory),
            similarity_threshold=config.get("similarity_threshold", 0.85),
        )
        orch = target.orchestrator(
            llm_provider=provider,
            extraction_service=extraction_service,
            config=dict(target.config),
        )
        # Resolve to the SAME taxonomy the recorder used (its title is the only
        # ontology-derived value in the prompt hash), and run with the target's
        # model, not the fixture's pinned one: both must match
        # record_default_cassettes.py or the cassette key misses.
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=target.run_input({**scenario_input(scenario), "ontology_id": taxonomy.id}),
        )
        try:
            result_state = await orch.execute(state)
        except PipelineExecutionError:
            # A prompt with no recording fails the extraction. That is a stale
            # cassette, reported from the provider's miss count (`_stale_variants`),
            # not a crash; a failure with every prompt answered is the pipeline's own.
            if not provider.misses:
                raise
            return []
        return (result_state.result or {}).get("triples", [])

    return Variant(
        name=name,
        base_config=base_config,
        knob_space={key: [value] for key, value in base_config.items()},
        run_scenario=run_scenario,
        implementation=target.implementation,
        configuration=target.configuration,
        model=target.model,
    )


def build_registry(nlp, embedding, eval_repo=None, eval_index=None) -> dict[str, Variant]:
    """
    Seed today's variant registry (karpathy_loop_design.md §4.2).

    Only variants that both exist in code *and* can be evaluated entirely
    offline (Loop A/B never make live LLM calls — §4.1/§5) are registered:

    - 'open_v1': the rule-mode spaCy dependency-triple pipeline. Makes no LLM
      calls at all, so it always qualifies.

    - 'default' / 'default+grounding': the LLM pipeline
      (`IndividualExtractionOrchestrator`), admitted under a GUARD. The default
      pipeline can only be replayed offline once cassettes have been recorded
      for it AND the DR spec checkout is present (its replay set includes
      DR-context scenarios). When both hold, this registers a `default` and a
      `default+grounding` variant; both resolve each scenario's ontology through
      a shared `DefaultPipelineOntologyResolver` (the same conftest builders the
      recorder used, so prompt titles — and thus cassette keys — match) and
      replay strictly through `CassetteLLMProvider`, never a live provider. The
      two variants differ only by `similarity_threshold` (soft-match dedup); the
      `default+grounding` knobs are inert on the ExtractionService path, so the
      two tie in practice — the RAG grounding that lifts the LLM pipeline lives
      in the prompt (`ExtractionService._build_individual_extraction_prompt`),
      not in these knobs.

    `default`/`default+grounding` register whenever their cassettes exist. To
    re-record after a change to the two-pass prompts, or to anything that feeds
    them (the class catalog, the predicate vocabulary), use
    `scripts/record_default_cassettes.py --record`.

    No variant runs `find_then_type`: the triple corpus has no recordings of
    it, so it is measured by the benchmark pass alone (`--implementation`). The
    earlier `grounded_v1` variant (retrieval-based typing) is gone: its
    cassettes were removed when the prompts gained source spans (#1243), and its
    last scored result was a clear STAY, recorded in
    individual_extraction_refinement_learnings.md.
    """
    register_variant(_make_open_v1_variant(nlp, embedding, eval_repo, eval_index))

    if _default_cassettes_present() and dr_spec_available():
        # One resolver shared by both variants builds each scenario's ontology
        # via the same conftest builders the recorder used, so the replayed
        # prompt title matches the recorded one. DR-context scenarios need the
        # DR spec checkout, so both must be present to register the default
        # variants (their replay set includes DR scenarios).
        resolver = DefaultPipelineOntologyResolver()
        register_variant(_make_default_variant(resolver, grounding=False))
        register_variant(_make_default_variant(resolver, grounding=True))
    elif _default_cassettes_present():
        print(
            "note: 'default' LLM pipeline has recorded cassettes but the DR spec "
            "checkout is absent, so its DR-context replay scenarios cannot be "
            "rebuilt — not registering the 'default'/'default+grounding' variants."
        )
    else:
        print(
            "note: 'default' LLM pipeline not registered — no recorded cassettes "
            f"found under {_DEFAULT_CASSETTE_DIR} for all "
            f"{len(_DEFAULT_REPLAY_SCENARIOS)} replay scenarios, so there is "
            "nothing for this offline tournament to replay. Record them via "
            "`python scripts/record_default_cassettes.py --record` "
            "and the 'default'/'default+grounding' variants register automatically."
        )

    return registered_variants()


def _make_dev_evaluator(variant: Variant, embed_fn) -> Callable[[dict], Awaitable[dict]]:
    """Build a Loop A `evaluate(config) -> {"soft_f1", "strict_f1"}` closure over dev scenarios."""

    async def evaluate(config: dict[str, Any]) -> dict[str, float]:
        strict_scores: list[float] = []
        soft_scores: list[float] = []
        for scenario in INDIVIDUAL_EXTRACTION_DEV_SCENARIOS:
            expected_raw = (
                load_expected_output("individual_extraction", scenario)
                .get("result", {})
                .get("triples", [])
            )
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


async def _evaluate_scenario(
    variant: Variant, config: dict[str, Any], scenario: str, split: str, embed_fn
) -> ScenarioReport:
    """Evaluate `variant` under `config` on one scenario; `split` is recorded as-is."""
    fixture_input = load_fixture("individual_extraction", scenario)
    expected_output = load_expected_output("individual_extraction", scenario)
    expected_triples_raw = expected_output.get("result", {}).get("triples", [])
    actual_triples_raw = await variant.run_scenario(config, scenario)

    expected_keys = [extract_triple_key(t) for t in expected_triples_raw]
    actual_keys = [extract_triple_key(t) for t in actual_triples_raw]

    strict = compute_quality_metrics(expected_triples_raw, actual_triples_raw)
    soft = soft_precision_recall_f1(expected_keys, actual_keys, embed_fn)

    return ScenarioReport(
        scenario=scenario,
        split=split,
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


async def _build_scenario_reports(
    variant: Variant, config: dict[str, Any], embed_fn
) -> list[ScenarioReport]:
    """Evaluate `variant` under `config` across the full corpus (dev + holdout), per scenario."""
    return [
        await _evaluate_scenario(variant, config, scenario, split_for(scenario), embed_fn)
        for scenario in INDIVIDUAL_EXTRACTION_SCENARIOS
    ]


async def _build_bootstrap_reports(
    variant: Variant, config: dict[str, Any], embed_fn
) -> list[ScenarioReport]:
    """
    Evaluate `variant` under `config` on the Wave 1 DR bootstrap scenarios.

    A distinct, always-reported diagnostic group
    (karpathy_loop_dr_ontology_design.md §5): graded against the imported DR
    spec, deliberately excluded from `INDIVIDUAL_EXTRACTION_SCENARIOS` (see
    `dataset_split.py`), so `split_for()` would raise for these scenarios --
    the "bootstrap" split is recorded directly instead. Kept out of
    `_build_scenario_reports`'s report entirely, not just out of its dev/
    holdout aggregation, so this diagnostic pass can never contaminate the
    failure-stage counts that drive Loop C's target selection, let alone the
    accept gate.
    """
    return [
        await _evaluate_scenario(variant, config, scenario, "bootstrap", embed_fn)
        for scenario in DR_BOOTSTRAP_SCENARIOS
    ]


async def _build_wave4_reports(
    variant: Variant, config: dict[str, Any], embed_fn
) -> list[ScenarioReport]:
    """
    Evaluate `variant` under `config` on the Wave 4 informal/incidental-prose scenarios.

    Another distinct, always-reported diagnostic group
    (karpathy_loop_dr_ontology_design.md §8, #1109 Phase 8): graded against
    the imported DR spec, deliberately excluded from
    `INDIVIDUAL_EXTRACTION_SCENARIOS` (see `dataset_split.py`), so
    `split_for()` would raise for these scenarios -- the "wave4" split is
    recorded directly instead, the same mechanism `_build_bootstrap_reports`
    uses for Wave 1. Kept out of `_build_scenario_reports`'s report entirely
    so this diagnostic pass can never contaminate Loop C's target selection
    or the accept gate -- the Phase 8 acceptance criteria require Wave 4
    results never gate a Wave 0-3 accept/reject decision.
    """
    return [
        await _evaluate_scenario(variant, config, scenario, "wave4", embed_fn)
        for scenario in WAVE4_INFORMAL_SCENARIOS
    ]


async def _build_arxiv_reports(
    variant: Variant, config: dict[str, Any], embed_fn
) -> list[ScenarioReport]:
    """
    Evaluate `variant` under `config` on the DR-relabeled arxiv scenarios.

    A distinct, always-reported diagnostic group (see
    `RELABELED_ARXIV_SCENARIOS` in `dataset_split.py`): real external paper
    abstracts whose GT was retrofitted into idealized DR models, measuring a
    harder task than this pipeline's grounded-identification job. Moved out of
    `INDIVIDUAL_EXTRACTION_SCENARIOS` after a root-cause trace found the
    candidate_missing bucket concentrated entirely here (SME-native scenarios
    sit at ~1.0 candidate recall) while per-triple adjudication confirmed the GT
    is sound. Recorded under the "arxiv" split -- the same mechanism
    `_build_bootstrap_reports` / `_build_wave4_reports` use -- so it is reported
    for visibility but never contaminates Loop C's target selection or the
    accept gate.
    """
    return [
        await _evaluate_scenario(variant, config, scenario, "arxiv", embed_fn)
        for scenario in RELABELED_ARXIV_SCENARIOS
    ]


async def _build_recognition_reports(
    embedding: EmbeddingService,
) -> dict[str, RecognitionMetrics]:
    """
    Run every `RECOGNITION_EPISODES` entry through the full extraction+apply+
    recognition pipeline (Phase 1's `run_full_pipeline_episode`) and score it
    with `recognition_metrics()` (issue #1142 Phase 3).

    A distinct, always-reported diagnostic group, like bootstrap/wave4/arxiv --
    but unlike them, recognition has no `Variant.run_scenario` seam: each
    episode exercises the real pipeline directly via its own per-document
    cassettes (not a variant's config), so this runs once per tournament
    invocation rather than once per variant (see `_amain`). Degrades
    gracefully (returns `{}` or skips an episode) when the DR spec checkout or
    an episode's cassettes are missing, the same guard `build_registry` uses
    for the `default` variants via `dr_spec_available()`. Also skips (with a
    warning, never raising) an episode that fails with a recoverable,
    episode-scoped error -- a missing/malformed fixture or cassette
    (`FileNotFoundError`, `json.JSONDecodeError`), a stale cassette
    (`CassetteStaleError`), or an orchestrator/import failure surfaced as
    `EpisodeSetupError` -- or one whose `EpisodeRunResult.mentions` is empty
    after `extraction_misses` are accounted for -- `recognition_metrics([])`
    reports a perfect 1.0 score for an empty input, so scoring a total
    extraction failure would misrepresent it as a dedup success. Infrastructure
    failures (`MemoryError`, `OSError`, `sqlite3.DatabaseError`, etc.) and any
    other `RuntimeError` (e.g. `NotImplementedError`, `RecursionError`) are not
    caught here and propagate, since silently skipping them would let the
    tournament exit 0 with an incomplete, unflagged scoreboard.
    """
    from tests.integration.pipelines import conftest

    dr_ontology_dir = conftest._find_dr_spec_dir()
    if dr_ontology_dir is None:
        print(
            "note: recognition diagnostics skipped -- DR spec checkout not "
            "available, so recognition episodes cannot be graded."
        )
        return {}

    reports: dict[str, RecognitionMetrics] = {}
    for episode in RECOGNITION_EPISODES:
        cassette_dir = _RECOGNITION_EPISODES_DIR / episode / "cassettes"
        if not cassette_dir.exists():
            print(
                f"note: recognition episode '{episode}' skipped -- no cassettes "
                f"found at {cassette_dir}"
            )
            continue
        try:
            result = await run_full_pipeline_episode(
                episode, cassette_dir, dr_ontology_dir, embedding
            )
        except (
            FileNotFoundError,
            json.JSONDecodeError,
            CassetteStaleError,
            EpisodeSetupError,
        ) as exc:
            print(
                f"WARNING: recognition episode '{episode}' failed at runtime "
                f"({type(exc).__name__}: {exc}) -- skipped. Other episodes, variant "
                "results, and the scoreboard digest are unaffected."
            )
            continue
        if result.extraction_misses:
            print(
                f"WARNING: recognition episode '{episode}' had "
                f"{len(result.extraction_misses)} extraction miss(es) out of "
                f"{len(result.mentions) + len(result.extraction_misses)} ground-truth "
                "mention(s) -- misses are excluded from dedup scoring."
            )
        if not result.mentions:
            print(
                f"WARNING: recognition episode '{episode}' skipped -- extraction "
                "produced zero scoreable mentions (total extraction failure). "
                "recognition_metrics([]) reports a perfect 1.0 score for an empty "
                "input, which would misrepresent this episode as a dedup success."
            )
            continue
        reports[episode] = recognition_metrics(result.mentions)
    return reports


def _aggregate_recognition(reports: dict[str, RecognitionMetrics]) -> dict[str, float]:
    """
    Mean dedup precision/recall/F1 + node-count ratio across recognition episodes.

    This is the summary attached to every variant's result dict under the
    `"recognition"` key (for scoreboard-table parity) -- it is never read by
    the `results.sort(key=lambda r: r["dev"]["soft_f1"], ...)` ranking that
    drives accept/reject, so a recognition regression alone can never flip
    the tournament decision.
    """
    if not reports:
        return {
            "dedup_precision": 0.0,
            "dedup_recall": 0.0,
            "dedup_f1": 0.0,
            "node_count_ratio": 0.0,
        }
    values = list(reports.values())

    def _mean(attr: str) -> float:
        return round(sum(getattr(v, attr) for v in values) / len(values), 4)

    return {
        "dedup_precision": _mean("dedup_precision"),
        "dedup_recall": _mean("dedup_recall"),
        "dedup_f1": _mean("dedup_f1"),
        "node_count_ratio": _mean("node_count_ratio"),
    }


def _emit_recognition_metrics(
    recognition_reports: dict[str, RecognitionMetrics],
) -> None:
    """Emit each episode's RecognitionMetrics to _metrics/individual_recognition.jsonl."""
    emitter = MetricsEmitter(_METRICS_DIR)
    for episode, metrics in recognition_reports.items():
        emitter.emit(
            pipeline_type=_RECOGNITION_PIPELINE_TAG,
            fixture_id=episode,
            model="quality_tournament",
            config_ref="recognition_episode",
            config_version=1,
            metrics=asdict(metrics),
            mode="offline",
            source="quality_tournament",
        )


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
    (
        best_config,
        _base_metrics,
        _best_metrics,
        base_primary,
        best_primary,
        evals,
    ) = await coordinate_ascent(
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
    print(
        f"   baseline soft_f1={base_primary:.3f}  tuned soft_f1={best_primary:.3f}  "
        f"({evals} evaluations)"
    )

    print(f"== full-corpus evaluation: '{variant.name}' (tuned config) ==")
    scenario_reports = await _build_scenario_reports(variant, best_config, embed_fn)
    run_id = f"tournament_{variant.name}_{generate_run_id()}"
    json_path, markdown_path = write_report(run_id, scenario_reports, _EXPERIMENTS_REPORTS_DIR)
    print(f"   error report: {json_path}")

    print(
        f"== bootstrap diagnostics: '{variant.name}' (Wave 1, dr_spec ontology -- "
        "always reported, never gates accept/reject) =="
    )
    bootstrap_reports = await _build_bootstrap_reports(variant, best_config, embed_fn)
    for r in bootstrap_reports:
        print(f"   {r.scenario:<28} strict-F1={r.strict['f1']:.3f}  soft-F1={r.soft['f1']:.3f}")
    bootstrap_metrics = _aggregate(bootstrap_reports, "bootstrap")

    print(
        f"== wave4 diagnostics: '{variant.name}' (Wave 4, informal prose -- "
        "always reported, never gates accept/reject) =="
    )
    wave4_reports = await _build_wave4_reports(variant, best_config, embed_fn)
    for r in wave4_reports:
        print(f"   {r.scenario:<28} strict-F1={r.strict['f1']:.3f}  soft-F1={r.soft['f1']:.3f}")
    wave4_metrics = _aggregate(wave4_reports, "wave4")

    print(
        f"== arxiv diagnostics: '{variant.name}' (relabeled external abstracts -- "
        "always reported, never gates accept/reject) =="
    )
    arxiv_reports = await _build_arxiv_reports(variant, best_config, embed_fn)
    for r in arxiv_reports:
        print(f"   {r.scenario:<28} strict-F1={r.strict['f1']:.3f}  soft-F1={r.soft['f1']:.3f}")
    arxiv_metrics = _aggregate(arxiv_reports, "arxiv")

    tuned_knobs = {
        knob: best_config[knob]
        for knob in variant.knob_space
        if best_config.get(knob) != variant.base_config.get(knob)
    }

    return {
        "variant": variant.name,
        "implementation": variant.implementation,
        "configuration": variant.configuration,
        "model": variant.model,
        "tuned_config": best_config,
        "tuned_knobs": tuned_knobs,
        "dev": _aggregate(scenario_reports, "dev"),
        "holdout": _aggregate(scenario_reports, "holdout"),
        "bootstrap": bootstrap_metrics,
        "wave4": wave4_metrics,
        "arxiv": arxiv_metrics,
        "error_report_json": str(json_path),
        "error_report_md": str(markdown_path),
    }


def _render_scoreboard_digest(
    run_id: str,
    results: list[dict[str, Any]],
    recognition_reports: dict[str, RecognitionMetrics],
) -> str:
    """Markdown scoreboard: variants ranked by dev soft-F1, diagnostics alongside (§4.2)."""
    lines = [f"# Individual extraction variant tournament — {run_id}", ""]
    lines.append(
        "Ranked by mean dev soft-F1 (the Loop A/B hill-climbing signal, §3.1). "
        "Strict-F1 is the production floor metric. Holdout is advisory only — "
        "per §3.3/§6 it never selects the winner (a guard against holdout "
        "overfitting). The formerly-unreviewed arxiv holdout scenarios have "
        "since been retired from the scored split (see LEGACY_CORPUS_DISPOSITION.md)."
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

    ran = [r for r in results if r.get("implementation")]
    if ran:
        lines.append("## What each variant ran")
        lines.append("")
        for result in ran:
            lines.append(
                f"- **{result['variant']}**: implementation `{result['implementation']}`, "
                f"configuration `{result['configuration']}`, model `{result['model']}`"
            )
        lines.append("")

    lines.append("## Winning knobs per variant")
    lines.append("")
    for result in results:
        lines.append(
            f"- **{result['variant']}**: {result['tuned_knobs'] or '(baseline already optimal)'}"
        )
    lines.append("")

    lines.append("## Per-variant error reports")
    lines.append("")
    for result in results:
        lines.append(f"- **{result['variant']}**: {result['error_report_json']}")
    lines.append("")

    lines.append("## Wave 1 bootstrap diagnostics (always reported, never gates accept/reject)")
    lines.append("")
    lines.append(
        f"Sanity-check only over {len(DR_BOOTSTRAP_SCENARIOS)} scenario(s) graded against the "
        "imported DR spec ontology (karpathy_loop_dr_ontology_design.md §5) -- too thin to "
        "holdout-split or optimize against. Excluded from dev/holdout aggregation, from Loop C's "
        "target selection, and from the §6 accept gate; logged here and to the ledger purely for "
        "visibility."
    )
    lines.append("")
    lines.append("| variant | bootstrap strict-F1 | bootstrap soft-F1 |")
    lines.append("|---|---|---|")
    for result in results:
        bootstrap = result["bootstrap"]
        lines.append(
            f"| {result['variant']} | {bootstrap['strict_f1']:.3f} | {bootstrap['soft_f1']:.3f} |"
        )
    lines.append("")

    lines.append(
        "## Wave 4 informal-prose diagnostics (always reported, never gates accept/reject)"
    )
    lines.append("")
    lines.append(
        f"Generalization check only over {len(WAVE4_INFORMAL_SCENARIOS)} scenario(s) -- "
        "user-manual, sales-literature, marketing-copy, and support-article prose that "
        "mentions DR entities only incidentally (karpathy_loop_dr_ontology_design.md §8) -- "
        "too thin, and deliberately out of scope, to holdout-split or optimize against. "
        "Excluded from dev/holdout aggregation, from Loop C's target selection, and from the "
        "§6 accept gate; logged here and to the ledger purely for visibility."
    )
    lines.append("")
    lines.append("| variant | wave4 strict-F1 | wave4 soft-F1 |")
    lines.append("|---|---|---|")
    for result in results:
        wave4 = result["wave4"]
        lines.append(f"| {result['variant']} | {wave4['strict_f1']:.3f} | {wave4['soft_f1']:.3f} |")
    lines.append("")

    lines.append("## Relabeled-arxiv diagnostics (always reported, never gates accept/reject)")
    lines.append("")
    lines.append(
        f"Difficulty check only over {len(RELABELED_ARXIV_SCENARIOS)} scenario(s) -- real "
        "external paper abstracts whose GT was retrofitted into idealized DR models, so they "
        "measure a harder task (dense external prose -> full DR model) than this pipeline's "
        "grounded-identification job (see RELABELED_ARXIV_SCENARIOS in dataset_split.py). Moved "
        "out of the scored split after a root-cause trace found candidate_missing concentrated "
        "entirely here while SME-native scenarios sit at ~1.0 candidate recall. Excluded from "
        "dev/holdout aggregation, Loop C's target selection, and the §6 accept gate."
    )
    lines.append("")
    lines.append("| variant | arxiv strict-F1 | arxiv soft-F1 | arxiv candidate_recall |")
    lines.append("|---|---|---|---|")
    for result in results:
        arxiv = result["arxiv"]
        lines.append(
            f"| {result['variant']} | {arxiv['strict_f1']:.3f} | {arxiv['soft_f1']:.3f} | "
            f"{arxiv['candidate_recall']:.3f} |"
        )
    lines.append("")

    lines.append("## Recognition diagnostics (always reported, never gates accept/reject)")
    lines.append("")
    lines.append(
        f"Cross-document entity-recognition (dedup) quality over {len(RECOGNITION_EPISODES)} "
        "episode(s) (issue #1142), run once per tournament invocation through the full "
        "extraction+apply+recognition pipeline (`episode_runner.run_full_pipeline_episode`) -- "
        "independent of the open_v1/default variant sweep above, since recognition has no "
        "`Variant.run_scenario` seam. Scored by pairwise dedup precision/recall/F1 and "
        "node-count ratio (`_harness/metrics.py::recognition_metrics`); separate from, and never "
        "gating, the strict/soft-F1 dev/holdout accept/reject decision."
    )
    lines.append("")
    if recognition_reports:
        lines.append("| episode | dedup precision | dedup recall | dedup F1 | node_count_ratio |")
        lines.append("|---|---|---|---|---|")
        for episode, metrics in recognition_reports.items():
            lines.append(
                f"| {episode} | {metrics.dedup_precision:.3f} | {metrics.dedup_recall:.3f} | "
                f"{metrics.dedup_f1:.3f} | {metrics.node_count_ratio:.3f} |"
            )
    else:
        lines.append(
            "_Skipped -- DR spec checkout or episode cassettes not available in this environment._"
        )
    lines.append("")

    return "\n".join(lines)


def _stale_variants(results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Variants whose replay asked for a response its cassettes don't hold."""
    use = {r["variant"]: _cassette_use(r["variant"]) for r in results}
    return {variant: counts for variant, counts in use.items() if counts["misses"]}


def _stale_for_target(
    stale: dict[str, dict[str, int]],
    variants: dict[str, Variant],
    target: benchmark_replay.BenchmarkTarget,
) -> list[str]:
    """
    The stale variants that run the target, its implementation with its
    configuration: the ones that end the run. A variant of the same
    implementation with another configuration is not the target's.
    """
    return sorted(
        v
        for v in stale
        if (variants[v].implementation, variants[v].configuration)
        == (target.implementation, target.configuration)
    )


def _exit_code(gating: list[str], benchmark_status: str) -> int:
    """
    The run's exit code from what happened to the chosen target: stale
    recordings of its own first, then a benchmark with no score for any other
    reason. Zero only when the target's numbers can be read.
    """
    if gating or benchmark_status == "stale":
        return EXIT_STALE_CASSETTES
    if benchmark_status != "scored":
        return EXIT_BENCHMARK_NOT_SCORED
    return 0


def _render_stale_section(
    stale: dict[str, dict[str, int]],
    benchmark_results: list[benchmark_replay.DocumentResult] | None = None,
    target: benchmark_replay.BenchmarkTarget | None = None,
) -> str:
    """A warning for the top of the digest, empty when no recording is stale."""
    stale_documents = [r for r in benchmark_results or [] if r.status == "stale"]
    if not stale and not stale_documents:
        return ""
    lines = ["## STALE CASSETTES: the scores below are not a measurement", ""]
    for variant, use in sorted(stale.items()):
        lines.append(
            f"- `{variant}`: {use['misses']} of {use['calls']} LLM calls had no recorded response. "
            "Its prompts have changed since the cassettes were recorded; each missed call "
            "returned nothing."
        )
    if stale_documents and target is not None:
        misses = sum(r.misses for r in stale_documents)
        calls = sum(r.calls for r in stale_documents)
        lines.append(
            f"- benchmark, `{target.implementation}` with `{target.configuration}`: {misses} of "
            f"{calls} LLM calls had no recorded response ("
            f"{', '.join(r.document_id for r in stale_documents)}). Record again with "
            f"`python scripts/benchmark_replay.py --record --spend {target.flags}`."
        )
    if stale:
        lines += [
            "",
            "Re-record before reading any number for these variants (both call the live LLM): "
            "`python scripts/record_default_cassettes.py --record` for `default*`, "
            "`python scripts/record_individual_canonicalization_cassettes.py` for `open_v1`.",
        ]
    lines.append("")
    return "\n".join(lines)


def _triple_corpus_measure(
    results: list[dict[str, Any]], stale: dict[str, dict[str, int]]
) -> dict[str, Any]:
    """
    What the triple corpus measured: the dev scores of the variant that runs
    its implementation as it is (the variant named after it), with the
    implementation, configuration and model that variant ran. When the variant
    did not register or its cassettes are stale there is no number, and
    `status` says which.
    """
    recorded = triple_corpus_target()
    measure: dict[str, Any] = {
        "variant": recorded.implementation,
        "implementation": recorded.implementation,
        "configuration": recorded.configuration,
        "model": recorded.model,
    }
    row = next((r for r in results if r["variant"] == recorded.implementation), None)
    if row is None:
        return {**measure, "status": "not_registered"}
    if row["variant"] in stale:
        return {**measure, "status": "stale"}
    return {
        **measure,
        "status": "scored",
        "strict_f1": row["dev"]["strict_f1"],
        "soft_f1": row["dev"]["soft_f1"],
    }


def _guard_applies(target: benchmark_replay.BenchmarkTarget) -> bool:
    """The triple corpus guards the one implementation and configuration it was recorded with."""
    recorded = triple_corpus_target()
    return (target.implementation, target.configuration) == (
        recorded.implementation,
        recorded.configuration,
    )


def _guard(
    results: list[dict[str, Any]],
    stale: dict[str, dict[str, int]],
    target: benchmark_replay.BenchmarkTarget,
) -> dict[str, Any]:
    """
    The triple corpus's guard measure for the benchmark target.

    The guard applies only to the implementation and configuration the triple
    corpus has recordings of. For any other target, `applies` is false and says
    why: a reader must record that the guard was not applicable, never take the
    recorded target's row for it (the report's `other_guards` holds that row,
    under its own name).
    """
    if _guard_applies(target):
        return {"applies": True, **_triple_corpus_measure(results, stale)}
    recorded = triple_corpus_target()
    return {
        "applies": False,
        "reason": (
            f"the triple corpus has no recordings of {target.implementation} with "
            f"{target.configuration}: its variants run {recorded.implementation} with "
            f"{recorded.configuration}"
        ),
    }


def _other_guards(
    results: list[dict[str, Any]],
    stale: dict[str, dict[str, int]],
    target: benchmark_replay.BenchmarkTarget,
) -> list[dict[str, Any]]:
    """
    The triple corpus's measure when it is not the target's guard: it still
    says whether a change made for the target damaged the implementation the
    corpus was recorded with (a change to a part the implementations share).
    """
    return [] if _guard_applies(target) else [_triple_corpus_measure(results, stale)]


def _render_benchmark_section(
    results: list[benchmark_replay.DocumentResult],
    summary: dict[str, Any],
    report_path: Path,
    target: benchmark_replay.BenchmarkTarget,
    guard: dict[str, Any],
) -> str:
    """The benchmark target on the benchmark documents (extraction_benchmark fixtures)."""
    record = f"python scripts/benchmark_replay.py --record --spend {target.flags}"
    lines = [
        f"## Benchmark: `{target.implementation}` with `{target.configuration}` "
        f"({target.model}) on the benchmark documents",
        "",
        "Long real documents run as sources (chunked, merged, planned as proposal operations) "
        "and scored on the individuals found against hand-made gold extractions. "
        f"Dev: {', '.join(benchmark_replay.DEV_DOCUMENTS)}. "
        f"Holdout: {', '.join(benchmark_replay.HOLDOUT_DOCUMENTS)}. "
        f"Recordings: `{benchmark_replay.cassette_dir(target).name}/`.",
        "",
        "| document | status | recall | core recall | precision | type accuracy | typed F1 "
        "| relationship recall |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.score is None:
            lines.append(f"| {r.document_id} | {r.status} | | | | | | |")
            continue
        m = r.score.metrics
        lines.append(
            f"| {r.document_id} | scored | {m['recall']:.3f} | {m['recall_core']:.3f} | "
            f"{m['precision']:.3f} | {m['type_accuracy']:.3f} | {m['typed_f1']:.3f} | "
            f"{m['relationship_recall']:.3f} |"
        )
    lines.append("")
    if summary["status"] == "not_recorded":
        lines.append(f"_Not recorded: `{record}` records the cassettes (calls the live LLM)._")
    elif summary["status"] == "stale":
        lines.append(
            "_Stale: the pipeline's prompts changed since the cassettes were recorded. Record "
            f"again with `{record}`._"
        )
    elif summary["status"] == "failed":
        failed = "; ".join(f"{r.document_id}: {r.detail}" for r in results if r.status == "failed")
        lines.append(f"_Failed: the extraction itself failed with every prompt answered. {failed}_")
    elif summary["status"] == "partial":
        lines.append(
            "_Partial: not every benchmark document was scored (a document's `gold.json` is "
            "missing from the fixtures). A split has a mean only when all of its documents "
            "scored._"
        )
        if summary["failure_counts"]:
            lines.append(f"Failure counts over dev: {summary['failure_counts']}")
    else:
        dev, holdout = summary["dev"], summary["holdout"]
        lines.append(
            f"Dev typed F1 {dev['typed_f1']:.3f}, found F1 {dev['f1']:.3f}; "
            f"holdout typed F1 {holdout['typed_f1']:.3f}, found F1 {holdout['f1']:.3f}."
        )
        lines.append(f"Failure counts over dev: {summary['failure_counts']}")
        lines.append(f"Detail: `{report_path}`")
    lines.append("")
    if not guard["applies"]:
        lines.append(f"Triple-corpus guard: not applicable ({guard['reason']}).")
    elif guard["status"] == "scored":
        lines.append(
            f"Triple-corpus guard: the `{guard['variant']}` variant's dev strict-F1 "
            f"{guard['strict_f1']:.3f}, soft-F1 {guard['soft_f1']:.3f}."
        )
    else:
        lines.append(
            f"Triple-corpus guard: the `{guard['variant']}` variant has no score "
            f"({guard['status']})."
        )
    lines.append("")
    return "\n".join(lines)


def _write_benchmark_report(
    run_id: str,
    results: list[benchmark_replay.DocumentResult],
    summary: dict[str, Any],
    guard: dict[str, Any],
    other_guards: list[dict[str, Any]] | None = None,
) -> Path:
    """
    Write what Loop C reads: the benchmark summary (which says what was run),
    each document's score lists, the triple-corpus guard for that target, and
    the triple corpus's measure of another target when it is not this one's.
    """
    path = _EXPERIMENTS_REPORTS_DIR / f"{run_id}_benchmark.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **summary,
        "guard": guard,
        "other_guards": other_guards or [],
        "scores": {r.document_id: r.score.to_json() for r in results if r.score is not None},
    }
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    return path


def _emit_scoreboard_row(
    emitter: MetricsEmitter, fixture_id: str, ran: dict[str, Any], metrics: dict[str, float]
) -> None:
    """
    One scoreboard telemetry row, labeled with what was run: the model and the
    configuration, with the implementation and (for a triple-corpus row) the
    variant beside them.
    """
    labels = {"implementation": ran["implementation"]}
    if ran.get("variant"):
        labels["variant"] = ran["variant"]
    emitter.emit(
        pipeline_type=_TOURNAMENT_PIPELINE_TAG,
        fixture_id=fixture_id,
        model=ran["model"],
        config_ref=ran["configuration"],
        config_version=1,
        metrics=metrics,
        mode="offline",
        source="quality_tournament",
        labels=labels,
    )


async def _amain(args) -> int:
    try:
        target = benchmark_replay.resolve_target(args.implementation, args.configuration)
    except benchmark_replay.UnknownTargetError as exc:
        print(f"ERROR: {exc}")
        return 1
    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        print("ERROR: spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        return 1
    embedding: EmbeddingService = SentenceTransformerEmbedding()
    try:
        embedding.embed_batch(["probe"])
    except Exception as exc:
        print(f"ERROR: embedding model probe failed ({type(exc).__name__}): {exc}")
        print(
            "This could be a CUDA/GPU error, an out-of-memory failure, a missing dependency, "
            "or a dtype mismatch -- see the exception above for the actual cause."
        )
        return 1
    # Memoize .embed(label) across the whole sweep: every variant's Loop A
    # coordinate ascent re-runs the same open_v1 pipeline with only the config
    # knobs changed, so the candidate labels grounding embeds are identical
    # across evals. Wrapping the single shared embedding service means the
    # SentenceTransformer forward pass for each distinct label runs once, not
    # once per eval. embed_batch (reindex_all) passes through unchanged.
    embedding = CachingEmbeddingService(embedding)
    embed_fn = _make_embed_fn(embedding)

    eval_repo, eval_index = build_eval_ontology(embedding)

    registry = build_registry(nlp, embedding, eval_repo, eval_index)
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

    # Recognition (issue #1142 Phase 3): a fourth always-reported diagnostic
    # group, run once per tournament invocation (not per variant -- see
    # `_build_recognition_reports`). The same summary is attached to every
    # variant's result dict under "recognition" for scoreboard-table parity;
    # it is never read by the `sort(key=...)` call above, so a recognition
    # regression alone can never flip which variant ranks first.
    print(
        "\n== recognition diagnostics (issue #1142, always reported, never gates accept/reject) =="
    )
    recognition_reports = await _build_recognition_reports(embedding)
    for episode, metrics in recognition_reports.items():
        print(
            f"   {episode:<28} dedup-P={metrics.dedup_precision:.3f}  "
            f"dedup-R={metrics.dedup_recall:.3f}  dedup-F1={metrics.dedup_f1:.3f}  "
            f"node_count_ratio={metrics.node_count_ratio:.3f}"
        )
    recognition_summary = _aggregate_recognition(recognition_reports)
    for result in results:
        result["recognition"] = recognition_summary
    _emit_recognition_metrics(recognition_reports)

    # One row per variant and group. "dev" and "holdout" are the scored split;
    # "bootstrap", "wave4" and "arxiv" are diagnostic-only groups
    # (karpathy_loop_dr_ontology_design.md §5/§8, RELABELED_ARXIV_SCENARIOS),
    # each under its own fixture_id so nothing downstream reads one as an input
    # to the accept gate.
    scoreboard_emitter = MetricsEmitter(_METRICS_DIR)
    for result in results:
        for group in ("dev", "holdout", "bootstrap", "wave4", "arxiv"):
            _emit_scoreboard_row(scoreboard_emitter, group, result, result[group])

    run_id = f"tournament_{generate_run_id()}"

    print(
        f"\n== benchmark: implementation {target.implementation}, configuration "
        f"{target.configuration}, model {target.model} =="
    )
    benchmark_results = await benchmark_replay.replay_all(target=target)
    benchmark_replay.print_results(benchmark_results)
    benchmark_summary = benchmark_replay.summarize(benchmark_results, target)
    stale = _stale_variants(results)
    guard = _guard(results, stale, target)
    benchmark_path = _write_benchmark_report(
        run_id,
        benchmark_results,
        benchmark_summary,
        guard,
        _other_guards(results, stale, target),
    )
    if benchmark_summary["status"] == "scored":
        for split in ("dev", "holdout"):
            _emit_scoreboard_row(
                scoreboard_emitter,
                f"benchmark_{split}",
                target.describe(),
                benchmark_summary[split],
            )

    digest = (
        _render_stale_section(stale, benchmark_results, target)
        + _render_scoreboard_digest(run_id, results, recognition_reports)
        + "\n"
        + _render_benchmark_section(
            benchmark_results, benchmark_summary, benchmark_path, target, guard
        )
    )
    digest_path = _EXPERIMENTS_REPORTS_DIR / f"{run_id}.md"
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(digest)

    print("\n══ scoreboard (ranked by dev soft-F1) ══")
    print(digest)
    print(f"telemetry: {_METRICS_DIR / (_TOURNAMENT_PIPELINE_TAG + '.jsonl')}")
    print(f"digest:    {digest_path}")
    print(f"benchmark: {benchmark_path} ({benchmark_summary['status']})")
    if stale:
        print(f"\nWARNING: stale cassettes for {sorted(stale)}: not a measurement.")
    # The gate is the chosen target's recordings: its benchmark cassettes and
    # the variants that run its implementation. Any other stale variant is
    # flagged above and in the digest.
    gating = _stale_for_target(stale, registry, target)
    if gating:
        print(
            f"ERROR: the triple-corpus cassettes of {gating} are stale (they run "
            f"{target.implementation} with {target.configuration}). Re-record with "
            "scripts/record_default_cassettes.py --record."
        )
    if benchmark_summary["status"] == "stale":
        print(
            f"ERROR: the benchmark cassettes of {target.implementation} with "
            f"{target.configuration} are stale. Re-record with "
            f"scripts/benchmark_replay.py --record --spend {target.flags}."
        )
    exit_code = _exit_code(gating, benchmark_summary["status"])
    if exit_code == EXIT_BENCHMARK_NOT_SCORED:
        print(
            f"ERROR: the benchmark of {target.implementation} with {target.configuration} was "
            f"not scored ({benchmark_summary['status']}); see {benchmark_path}."
        )
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Loop B variant tournament runner (karpathy_loop_design.md §4.2)"
    )
    parser.add_argument(
        "--pipeline",
        choices=["individual"],
        default="individual",
        help="The pipeline type; individual extraction is the one with a tournament",
    )
    parser.add_argument(
        "--implementation",
        help="The implementation the benchmark pass runs (the registry's default)",
    )
    parser.add_argument(
        "--configuration",
        help=(
            "The implementation's configuration the benchmark pass runs with (the one its "
            "recordings were made with, else its default)"
        ),
    )
    parser.add_argument(
        "--passes",
        type=int,
        default=2,
        help="Loop A coordinate-ascent passes per variant",
    )
    parser.add_argument(
        "--restarts", type=int, default=3, help="Loop A random restarts per variant"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="RNG seed for Loop A restart shuffling/jitter",
    )
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
