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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from domain.extraction.open_extraction import build_relation_candidates
from domain.extraction.ports import NounChunkSpan, OpenExtractionResult, OpenToken
from domain.ontology.ports import SchemaMatch
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.configurations.open_v1 import get_open_v1_config
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionState
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

# Honest rule-mode baseline (well below the production floors). Rule mode
# scores ~0 recall on every SME-authored DR-spec scenario (Waves 2 and 3) —
# its snake_case/fused-phrase exact-tuple matching doesn't line up with
# hand-labeled prose ground truth — so this floor is a function of how much
# of the corpus is SME-authored, not just of the rule-mode implementation.
#
# The scored split is now SME-native ONLY (af6edd6b moved the relabeled-arxiv
# scenarios to a non-gating diagnostic tier; the ungrounded placeholders were
# dropped earlier), and rule mode scores exactly 0 on every one of them BY
# CONSTRUCTION. The residual ~0.049 that justified the old 0.045 floor came
# entirely from the non-SME scenarios that are no longer in QUALITY_SCENARIOS,
# so the floor measured corpus composition, not the implementation.
#
# Exact-tuple recall is therefore pinned at 0.0 and carries no signal. The
# regression guard that DOES carry signal is
# RULE_MODE_MIN_TRIPLES_PER_SCENARIO below: open_v1 must still emit a
# non-empty triple set for every scenario. A genuine open_v1 quality
# measurement lives in
# test_open_v1_soft_metrics_and_error_report, which uses the soft/strict
# harness metrics rather than exact-tuple match.
RULE_MODE_MEAN_RECALL_FLOOR = 0.0

# Minimum triples rule mode must still produce per scenario. Rule mode
# currently emits 20-32 per scenario; 5 catches a pipeline that has silently
# stopped extracting without being brittle to spaCy/model drift.
RULE_MODE_MIN_TRIPLES_PER_SCENARIO = 5

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
    # Any scored scenario proves the contract — this assertion is about the
    # shape open_v1 emits, not about a particular corpus entry. Driven off
    # QUALITY_SCENARIOS so retiring a scenario can never orphan this test
    # again (it previously hardcoded `distributed_systems`, whose
    # individual_extraction fixture was pruned in 3a6fadf7).
    result = await _run(open_orchestrator, QUALITY_SCENARIOS[0])
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

    # The load-bearing guard: exact-tuple recall is pinned at 0 on the
    # SME-native split by construction, so it cannot detect a regression.
    # Assert instead that rule mode still assembles a real triple set.
    starved = [(s, n) for s, _, n in rows if n < RULE_MODE_MIN_TRIPLES_PER_SCENARIO]
    assert not starved, (
        f"open_v1 rule mode produced fewer than "
        f"{RULE_MODE_MIN_TRIPLES_PER_SCENARIO} triples for: {starved}"
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
                    fixture_input.get("text", ""), expected_keys, actual_keys, embed_fn
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


class _FakeTaxonomy:
    def __init__(self, taxonomy_id: str):
        self.id = taxonomy_id


class _FakeOntologyRepo:
    """Resolves the DR spec identifier to a taxonomy; anything else to None."""

    def __init__(self, taxonomy_id: str = "dr-spec-tax-id"):
        self._taxonomy = _FakeTaxonomy(taxonomy_id)

    def get_by_identifier(self, identifier):
        return self._taxonomy if identifier == "dr_spec" else None


class _StubSchemaIndex:
    """Returns a fixed class match for every query (or nothing when empty=True)."""

    def __init__(self, empty: bool = False):
        self._empty = empty

    def index_entity(self, entity_id, title, description):  # pragma: no cover - unused
        pass

    def search(self, query_embedding, kinds, top_k=20, threshold=0.0, taxonomy_id=None):
        if self._empty:
            return []
        return [
            SchemaMatch(
                entity_id="c1",
                kind="class",
                label="ConsensusAlgorithm",
                score=0.9,
                matched_field="title",
                external_id="application.consensus-algorithm",
            )
        ]


def _triple(subj, pred, obj):
    return {
        "subject": {"label": subj, "kind": "individual"},
        "predicate": {"label": pred, "kind": "property"},
        "object": {"label": obj, "kind": "individual"},
        "confidence": 0.7,
    }


def test_grounding_emits_is_a_triples():
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=_StubEmbedding(),
        schema_index=_StubSchemaIndex(),
        config={**get_open_v1_config(), "ground_to_schema": True, "require_schema_match": False},
        ontology_repo=_FakeOntologyRepo(),
    )
    triples = [_triple("consensus_algorithm", "ensures", "state_agreement")]
    grounded = orch._ground_to_schema(triples, "dr_spec")
    type_triples = [t for t in grounded if t["predicate"]["label"] == "is_a"]
    assert type_triples, "expected is_a triples for matched individuals"
    assert all(t["object"]["kind"] == "class" for t in type_triples)
    # Object is the matched class's external schema identifier, not its title.
    assert all(t["object"]["label"] == "application.consensus-algorithm" for t in type_triples)
    # The original relation triple is retained.
    assert any(t["predicate"]["label"] == "ensures" for t in grounded)


def test_grounding_skipped_when_ontology_unresolved():
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=_StubEmbedding(),
        schema_index=_StubSchemaIndex(),
        config={**get_open_v1_config(), "ground_to_schema": True, "require_schema_match": False},
        ontology_repo=_FakeOntologyRepo(),
    )
    triples = [_triple("consensus_algorithm", "ensures", "state_agreement")]
    # An unresolved ontology_id (e.g. a placeholder scenario's stale id) must
    # leave the triples untouched — no grounding across an unrelated ontology.
    assert orch._ground_to_schema(triples, "test-ontology-123") == triples


def test_require_schema_match_filters_unmatched():
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=_StubEmbedding(),
        schema_index=_StubSchemaIndex(empty=True),  # nothing matches
        config={**get_open_v1_config(), "ground_to_schema": False, "require_schema_match": True},
        ontology_repo=_FakeOntologyRepo(),
    )
    triples = [_triple("foo", "bars", "baz")]
    assert orch._ground_to_schema(triples, "dr_spec") == []


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

    def search(self, query_embedding, kinds, top_k=20, threshold=0.0, taxonomy_id=None):
        if query_embedding and query_embedding[0] == 1.0:
            return [
                SchemaMatch(
                    entity_id="c1",
                    kind="class",
                    label="ConsensusAlgorithm",
                    score=0.9,
                    matched_field="title",
                    external_id="application.consensus-algorithm",
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
        ontology_repo=_FakeOntologyRepo(),
    )
    triples = [
        _triple("consensus_algorithm", "ensures", "state_agreement"),  # subject matches → kept
        _triple("foo", "bars", "baz"),  # neither matches → dropped
    ]
    kept = orch._ground_to_schema(triples, "dr_spec")
    subjects = {t["subject"]["label"] for t in kept}
    assert "consensus_algorithm" in subjects
    assert "foo" not in subjects


# ---------------------------------------------------------------------------
# Predicate grounding (property_definition kind) — stubbed, model-free
# ---------------------------------------------------------------------------


class _StubPredicateIndex:
    """
    Grounds specific predicate phrases to bare canonical verbs.

    Keyed on the phrase the orchestrator queries with (label with underscores
    replaced by spaces). A None value simulates a property-definition match that
    exposes no bare predicate (e.g. a non-canonical title), which must NOT rewrite.
    """

    def __init__(self, mapping: dict[str, str | None]):
        self._mapping = mapping
        self.seen_kinds: list = []

    def index_entity(self, *a):  # pragma: no cover - unused
        pass

    def search(self, query_embedding, kinds, top_k=20, threshold=0.0, taxonomy_id=None):
        self.seen_kinds.append(list(kinds))
        phrase = getattr(query_embedding, "phrase", None)
        if phrase is None or phrase not in self._mapping:
            return []
        return [
            SchemaMatch(
                entity_id="p1",
                kind="property_definition",
                label=f"src {self._mapping[phrase] or 'x'} dst",
                score=0.9,
                matched_field="title",
                external_id="a.b.c",
                predicate=self._mapping[phrase],
            )
        ]


class _PhraseEmbedding:
    """Returns a list carrying the queried phrase so the stub index can key on it."""

    def embed(self, text: str):
        vec = [1.0, 0.0, 0.0]

        class _V(list):
            phrase = text

        return _V(vec)

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]

    def similarity(self, a, b):  # pragma: no cover - unused
        raise NotImplementedError


def _predicate_orch(index):
    return OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=_PhraseEmbedding(),
        schema_index=index,
        config={**get_open_v1_config(), "ground_predicates": True},
        ontology_repo=_FakeOntologyRepo(),
    )


def test_predicate_grounding_rewrites_matched_predicate():
    orch = _predicate_orch(_StubPredicateIndex({"navigate to": "navigates-to"}))
    triples = [_triple("technician_route", "navigate_to", "job_detail_route")]
    grounded = orch._ground_predicates(triples, "dr_spec")
    assert grounded[0]["predicate"]["label"] == "navigates-to"
    # Only property_definition is searched — never individual kinds.
    assert orch._schema_index.seen_kinds == [["property_definition"]]


def test_predicate_grounding_leaves_unmatched_predicate_unchanged():
    orch = _predicate_orch(_StubPredicateIndex({"navigate to": "navigates-to"}))
    triples = [_triple("a", "sprint", "b")]  # no mapping for "sprint"
    assert orch._ground_predicates(triples, "dr_spec") == triples


def test_predicate_grounding_ignores_match_without_bare_predicate():
    # A property-definition match whose title is non-canonical exposes predicate=None.
    orch = _predicate_orch(_StubPredicateIndex({"navigate to": None}))
    triples = [_triple("a", "navigate_to", "b")]
    assert orch._ground_predicates(triples, "dr_spec") == triples


def test_predicate_grounding_dedups_collapsed_predicates():
    # Two distinct surface predicates collapse onto one canonical verb between the
    # same subject/object → the rewritten duplicate must be dropped.
    orch = _predicate_orch(
        _StubPredicateIndex({"navigate to": "navigates-to", "go to": "navigates-to"})
    )
    triples = [
        _triple("a", "navigate_to", "b"),
        _triple("a", "go_to", "b"),
    ]
    grounded = orch._ground_predicates(triples, "dr_spec")
    assert len(grounded) == 1
    assert grounded[0]["predicate"]["label"] == "navigates-to"


def test_predicate_grounding_skipped_when_ontology_unresolved():
    orch = _predicate_orch(_StubPredicateIndex({"navigate to": "navigates-to"}))
    triples = [_triple("technician_route", "navigate_to", "job_detail_route")]
    # Unresolved taxonomy → no rewriting.
    assert orch._ground_predicates(triples, "test-ontology-123") == triples


# ---------------------------------------------------------------------------
# Coverage completion (unconsumed noun chunks + wider capture) — stubbed
# ---------------------------------------------------------------------------


def _ctok(index, text, pos, dep, head_index, *, lemma=None, is_stop=False, is_alpha=True):
    return OpenToken(
        index=index,
        text=text,
        lemma=(lemma or text).lower(),
        pos=pos,
        tag="X",
        dep=dep,
        head_index=head_index,
        start=index,
        end=index + len(text),
        sentence_index=0,
        is_stop=is_stop,
        is_alpha=is_alpha,
    )


def _cchunk(text, start_token, end_token, root_index):
    return NounChunkSpan(
        text=text,
        start_token=start_token,
        end_token=end_token,
        root_index=root_index,
        start=0,
        end=len(text),
        sentence_index=0,
    )


def _coverage_doc():
    """'The technician navigates routes and jobs.' — 'jobs' left unconsumed."""
    tokens = [
        _ctok(0, "The", "DET", "det", 1, lemma="the", is_stop=True),
        _ctok(1, "technician", "NOUN", "nsubj", 2, lemma="technician"),
        _ctok(2, "navigates", "VERB", "ROOT", 2, lemma="navigate"),
        _ctok(3, "routes", "NOUN", "dobj", 2, lemma="route"),
        _ctok(4, "and", "CCONJ", "cc", 3, lemma="and", is_stop=True),
        _ctok(5, "jobs", "NOUN", "conj", 3, lemma="job"),
        _ctok(6, ".", "PUNCT", "punct", 2, lemma=".", is_alpha=False),
    ]
    chunks = [
        _cchunk("The technician", 0, 2, 1),
        _cchunk("routes", 3, 4, 3),
        _cchunk("jobs", 5, 6, 5),
    ]
    return OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )


def _coverage_orch(schema_index, ontology_repo=None):
    return OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=_StubEmbedding(),
        schema_index=schema_index,
        config={**get_open_v1_config(), "coverage_completion": True},
        ontology_repo=ontology_repo if ontology_repo is not None else _FakeOntologyRepo(),
    )


def _object_labels(triples):
    return {t["object"]["label"] for t in triples}


def test_coverage_completion_surfaces_candidate_with_relation():
    doc = _coverage_doc()
    relations = build_relation_candidates(doc)
    base = _coverage_orch(_StubSchemaIndex())._build_triples(doc, relations)
    # Baseline never surfaces 'job'.
    assert "job" not in _object_labels(base)

    orch = _coverage_orch(_StubSchemaIndex())
    merged = orch._complete_coverage(base, doc, relations, "dr_spec")

    # 'job' is now surfaced AND paired under a real predicate — not dangling.
    surfaced = [t for t in merged if t["object"]["label"] == "job"]
    assert surfaced, "coverage completion must surface the unconsumed 'jobs' chunk"
    assert surfaced[0]["predicate"]["label"] == "navigates"
    assert surfaced[0]["subject"]["label"] == "technician"


def test_coverage_completion_dedups_existing_triple():
    doc = _coverage_doc()
    relations = build_relation_candidates(doc)
    orch = _coverage_orch(_StubSchemaIndex())
    # The surfaced triple is already present → it must not be duplicated.
    base = orch._build_triples(doc, relations) + [
        _triple("technician", "navigates", "job")
    ]
    merged = orch._complete_coverage(base, doc, relations, "dr_spec")
    job_triples = [
        t
        for t in merged
        if t["object"]["label"] == "job" and t["predicate"]["label"] == "navigates"
    ]
    assert len(job_triples) == 1


def test_coverage_completion_skipped_without_index():
    doc = _coverage_doc()
    relations = build_relation_candidates(doc)
    orch = _coverage_orch(schema_index=None)
    base = orch._build_triples(doc, relations)
    assert orch._complete_coverage(base, doc, relations, "dr_spec") == base


def test_coverage_completion_skipped_when_ontology_unresolved():
    doc = _coverage_doc()
    relations = build_relation_candidates(doc)
    orch = _coverage_orch(_StubSchemaIndex())
    base = orch._build_triples(doc, relations)
    # Unresolved taxonomy → nothing surfaced.
    assert orch._complete_coverage(base, doc, relations, "test-ontology-123") == base


def test_coverage_completion_skipped_when_no_grounding():
    doc = _coverage_doc()
    relations = build_relation_candidates(doc)
    # Empty index → unconsumed chunks never ground → no bare candidate emitted.
    orch = _coverage_orch(_StubSchemaIndex(empty=True))
    base = orch._build_triples(doc, relations)
    assert orch._complete_coverage(base, doc, relations, "dr_spec") == base


class _StubNLP:
    """Returns a fixed OpenExtractionResult from process_open for any text."""

    def __init__(self, result):
        self._result = result

    def process(self, text):
        raise NotImplementedError

    def extract_entities(self, text):
        raise NotImplementedError

    def process_open(self, text):
        return self._result

    def is_ready(self):
        return True


async def _run_coverage(enabled: bool):
    doc = _coverage_doc()
    orch = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=_StubNLP(doc),
        embedding_service=_StubEmbedding(),
        schema_index=_StubSchemaIndex(),
        config={**get_open_v1_config(), "coverage_completion": enabled},
        ontology_repo=_FakeOntologyRepo(),  # type: ignore[arg-type]
    )
    state = IndividualExtractionState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data={"text": "The technician navigates routes and jobs.", "ontology_id": "dr_spec"},
    )
    result_state = await orch.execute(state)
    return (result_state.result or {}).get("triples", [])


@pytest.mark.asyncio
async def test_coverage_completion_knob_gates_execute():
    off = await _run_coverage(enabled=False)
    on = await _run_coverage(enabled=True)
    assert "job" not in _object_labels(off)
    assert "job" in _object_labels(on)
