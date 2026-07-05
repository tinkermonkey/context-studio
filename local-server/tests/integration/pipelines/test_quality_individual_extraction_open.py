"""
Quality measurement for the open_v1 individual extraction implementation (rule mode).

Runs the OPEN spaCy dependency-triple pipeline end-to-end through the SAME
quality-metric path as the default implementation, fully deterministically and
OFFLINE (no LLM, no network). Asserts a valid triple contract and an honest
rule-mode baseline, and prints the metric table.

Rule mode is a free, deterministic baseline that does NOT meet the production
floors (precision>=0.60, recall>=0.50, f1>=0.50) — exact-tuple match against
hand-labeled triples (snake_case individuals + canonical predicate forms +
fused object phrases) needs llm disambiguation (cassettes) and closed-loop
tuning. This test pins the baseline and proves the open pipeline assembles the
correct contract; the floor itself is driven by Phase 6.

Also emits the Karpathy-loop measurement-layer artifacts (§3 of
documentation/karpathy_loop_design.md): strict + soft P/R/F1 and coverage
diagnostics per scenario, split by the fixed dev/holdout assignment, plus a
machine-readable error report (JSON + markdown digest) under
`local-server/experiments/reports/`.
"""

import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.configurations.open_v1 import get_open_v1_config
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionState
from domain.ontology.ports import SchemaMatch
from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture
from tests.integration.pipelines._harness.dataset_split import split_for
from tests.integration.pipelines._harness.error_report import (
    ScenarioReport,
    build_missed_triples,
    generate_run_id,
    write_report,
)
from tests.integration.pipelines._harness.metrics import (
    candidate_recall,
    label_accuracy,
    predicate_recall,
    soft_precision_recall_f1,
)
from tests.integration.pipelines.test_quality_individual_extraction import (
    QUALITY_SCENARIOS,
    compute_quality_metrics,
    extract_triple_key,
)

# Honest rule-mode baseline (well below the production floors).
RULE_MODE_MEAN_RECALL_FLOOR = 0.05

# local-server/experiments/reports/ — see local-server/experiments/README.md
_EXPERIMENTS_REPORTS_DIR = Path(__file__).resolve().parents[3] / "experiments" / "reports"


@pytest.fixture(scope="module")
def open_orchestrator():
    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        pytest.skip("spaCy model not installed")
    embedding = SentenceTransformerEmbedding()
    try:
        embedding.embed_batch(["probe"])
    except Exception:
        pytest.skip("embedding model not available (offline cache miss)")
    return OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=nlp,
        embedding_service=embedding,
        schema_index=None,
        config=get_open_v1_config(),  # rule mode, no grounding
    )


@pytest.fixture(scope="module")
def embed_fn(open_orchestrator):
    """
    Cached label -> embedding vector function for the soft-metric tiers.

    Wraps the same SentenceTransformerEmbedding used for schema grounding.
    Memoized per label string: the diagnostics compare many (subject, object)
    pairs across a scenario's triples, and most labels repeat across those
    comparisons, so caching avoids re-encoding the same short string dozens
    of times per scenario.
    """
    embedding = SentenceTransformerEmbedding()

    @lru_cache(maxsize=None)
    def _cached(label: str) -> tuple:
        return tuple(embedding.embed(label))

    return lambda label: list(_cached(label))


async def _run(orchestrator, scenario):
    fixture = load_fixture("individual_extraction", scenario)
    state = IndividualExtractionState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data=dict(fixture),
    )
    result_state = await orchestrator.execute(state)
    return result_state.result or {}


@pytest.mark.nlp
@pytest.mark.asyncio
async def test_open_v1_produces_valid_triples(open_orchestrator):
    """open_v1 returns the individual-extraction triple contract."""
    result = await _run(open_orchestrator, "distributed_systems")
    assert "triples" in result and "metadata" in result
    assert isinstance(result["triples"], list)
    for triple in result["triples"]:
        assert triple["subject"]["label"] and triple["subject"]["kind"] == "individual"
        assert triple["predicate"]["label"] and triple["predicate"]["kind"] == "property"
        assert triple["object"]["label"] and triple["object"]["kind"] == "individual"
        assert 0.0 <= triple["confidence"] <= 1.0


@pytest.mark.nlp
@pytest.mark.asyncio
async def test_open_v1_rule_mode_baseline(open_orchestrator):
    """Measure open_v1 rule-mode across all scenarios; pin the honest baseline."""
    rows = []
    for scenario in QUALITY_SCENARIOS:
        result = await _run(open_orchestrator, scenario)
        expected_output = load_expected_output("individual_extraction", scenario)
        expected_triples = expected_output.get("result", {}).get("triples", [])
        actual_triples = result.get("triples", [])
        metrics = compute_quality_metrics(expected_triples, actual_triples)
        rows.append((scenario, metrics, len(actual_triples)))

    mean_recall = sum(m["recall"] for _, m, _ in rows) / len(rows)
    mean_precision = sum(m["precision"] for _, m, _ in rows) / len(rows)
    mean_f1 = sum(m["f1"] for _, m, _ in rows) / len(rows)

    print("\n── open_v1 rule-mode individual extraction (offline, deterministic) ──")
    print(f"{'scenario':<28} prec    recall   f1     brier  #triples")
    for scenario, m, n in rows:
        print(
            f"{scenario:<28} {m['precision']:>5.2f}  {m['recall']:>5.2f}  "
            f"{m['f1']:>5.2f}  {m['brier']:>5.2f}  {n:>5}"
        )
    print(
        f"{'MEAN':<28} {mean_precision:>5.2f}  {mean_recall:>5.2f}  {mean_f1:>5.2f}"
        "   (prod floors: P>=.60 R>=.50 f1>=.50)"
    )

    assert mean_recall >= RULE_MODE_MEAN_RECALL_FLOOR, (
        f"open_v1 rule-mode mean recall {mean_recall:.3f} fell below baseline "
        f"{RULE_MODE_MEAN_RECALL_FLOOR}"
    )


@pytest.mark.nlp
@pytest.mark.asyncio
async def test_open_v1_soft_metrics_and_error_report(open_orchestrator, embed_fn):
    """
    Measure open_v1 rule-mode with the full Karpathy-loop measurement layer (§3).

    For every scenario in the fixed dev/holdout split: strict + soft P/R/F1
    side by side, plus candidate_recall/predicate_recall/label_accuracy
    diagnostics. Every GT triple the strict metric misses is classified into a
    failure stage. Writes the JSON error report + markdown digest to
    local-server/experiments/reports/<run_id>.{json,md} — the primary input to
    Loop C experimenter agents (§4.3).
    """
    scenario_reports: list[ScenarioReport] = []

    for scenario in QUALITY_SCENARIOS:
        result = await _run(open_orchestrator, scenario)
        fixture_input = load_fixture("individual_extraction", scenario)
        expected_output = load_expected_output("individual_extraction", scenario)
        expected_triples_raw = expected_output.get("result", {}).get("triples", [])
        actual_triples_raw = result.get("triples", [])

        expected_keys = [extract_triple_key(t) for t in expected_triples_raw]
        actual_keys = [extract_triple_key(t) for t in actual_triples_raw]

        strict = compute_quality_metrics(expected_triples_raw, actual_triples_raw)
        soft = soft_precision_recall_f1(expected_keys, actual_keys, embed_fn)

        scenario_reports.append(
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
                    fixture_input.get("text", ""), expected_keys, actual_keys
                ),
            )
        )

    dev_reports = [r for r in scenario_reports if r.split == "dev"]
    holdout_reports = [r for r in scenario_reports if r.split == "holdout"]

    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    print("\n── open_v1 rule-mode: strict vs soft, diagnostics (§3.1) ──")
    print(
        f"{'scenario':<28} {'split':<8} strict-F1  soft-F1  cand_rec  pred_rec  "
        "label_acc(strict/soft)"
    )
    for r in scenario_reports:
        print(
            f"{r.scenario:<28} {r.split:<8} {r.strict['f1']:>8.3f}  {r.soft['f1']:>6.3f}  "
            f"{r.candidate_recall:>8.3f}  {r.predicate_recall:>8.3f}  "
            f"{r.label_accuracy['strict']:.3f}/{r.label_accuracy['soft']:.3f}"
        )
    print(
        f"{'DEV MEAN':<28} {'':<8} "
        f"{_mean([r.strict['f1'] for r in dev_reports]):>8.3f}  "
        f"{_mean([r.soft['f1'] for r in dev_reports]):>6.3f}"
    )
    print(
        f"{'HOLDOUT MEAN':<28} {'':<8} "
        f"{_mean([r.strict['f1'] for r in holdout_reports]):>8.3f}  "
        f"{_mean([r.soft['f1'] for r in holdout_reports]):>6.3f}"
    )

    run_id = generate_run_id()
    json_path, markdown_path = write_report(run_id, scenario_reports, _EXPERIMENTS_REPORTS_DIR)
    print(f"\nerror report: {json_path}")
    print(f"digest:       {markdown_path}")

    assert json_path.exists()
    assert markdown_path.exists()
    # Soft-F1 is a hill-climbing signal, not a floor — but it must never score
    # below strict-F1, since every strict match is also a soft match (tier 1.0).
    for r in scenario_reports:
        assert r.soft["f1"] >= r.strict["f1"] - 1e-9, (
            f"{r.scenario}: soft F1 {r.soft['f1']} fell below strict F1 {r.strict['f1']}"
        )


# ---------------------------------------------------------------------------
# Schema grounding (SchemaVectorIndex integration) — stubbed, model-free
# ---------------------------------------------------------------------------


class _StubEmbedding:
    def embed(self, text: str):
        return [1.0, 0.0, 0.0]

    def embed_batch(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def similarity(self, a, b):
        raise NotImplementedError


class _StubSchemaIndex:
    """Returns a fixed class match for every query (or nothing when empty=True)."""

    def __init__(self, empty: bool = False):
        self._empty = empty

    def index_entity(self, entity_id, title, description):  # pragma: no cover - unused
        pass

    def search(self, query_embedding, kinds, top_k=20, threshold=0.0):
        if self._empty:
            return []
        return [
            SchemaMatch(
                entity_id="c1",
                kind="class",
                label="ConsensusAlgorithm",
                score=0.9,
                matched_field="title",
            )
        ]


def _triple(subj, pred, obj):
    return {
        "subject": {"label": subj, "kind": "individual"},
        "predicate": {"label": pred, "kind": "property"},
        "object": {"label": obj, "kind": "individual"},
        "confidence": 0.7,
    }


def test_grounding_emits_rdf_type_triples():
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=_StubEmbedding(),
        schema_index=_StubSchemaIndex(),
        config={**get_open_v1_config(), "ground_to_schema": True, "require_schema_match": False},
    )
    triples = [_triple("consensus_algorithm", "ensures", "state_agreement")]
    grounded = orch._ground_to_schema(triples)
    type_triples = [t for t in grounded if t["predicate"]["label"] == "rdf:type"]
    assert type_triples, "expected rdf:type triples for matched individuals"
    assert all(t["object"]["kind"] == "class" for t in type_triples)
    # The original relation triple is retained.
    assert any(t["predicate"]["label"] == "ensures" for t in grounded)


def test_require_schema_match_filters_unmatched():
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=_StubEmbedding(),
        schema_index=_StubSchemaIndex(empty=True),  # nothing matches
        config={**get_open_v1_config(), "ground_to_schema": False, "require_schema_match": True},
    )
    triples = [_triple("foo", "bars", "baz")]
    assert orch._ground_to_schema(triples) == []


class _SelectiveEmbedding:
    """Distinct vectors so a selective index can match some labels but not others."""

    def embed(self, text: str):
        return [1.0, 0.0, 0.0] if "consensus" in text else [0.0, 1.0, 0.0]

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]

    def similarity(self, a, b):
        raise NotImplementedError


class _SelectiveSchemaIndex:
    """Matches only the 'consensus' vector ([1,0,0])."""

    def index_entity(self, *a):
        pass

    def search(self, query_embedding, kinds, top_k=20, threshold=0.0):
        if query_embedding and query_embedding[0] == 1.0:
            return [
                SchemaMatch(
                    entity_id="c1",
                    kind="class",
                    label="ConsensusAlgorithm",
                    score=0.9,
                    matched_field="title",
                )
            ]
        return []


def test_require_schema_match_keeps_matched_drops_unmatched():
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=_SelectiveEmbedding(),
        schema_index=_SelectiveSchemaIndex(),
        config={**get_open_v1_config(), "ground_to_schema": False, "require_schema_match": True},
    )
    triples = [
        _triple("consensus_algorithm", "ensures", "state_agreement"),  # subject matches → kept
        _triple("foo", "bars", "baz"),  # neither matches → dropped
    ]
    kept = orch._ground_to_schema(triples)
    subjects = {t["subject"]["label"] for t in kept}
    assert "consensus_algorithm" in subjects
    assert "foo" not in subjects
