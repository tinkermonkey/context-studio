"""scripts/bench_triage.py (#1522): triage the judged claims and score them, over SQLite."""

import pytest

from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.versioning.claims import Claim, ClaimFilter, ClaimService, ClaimVerdict, NoteSource
from scripts.bench_triage import BENCH_RUN_ID, render, run_bench
from tests.fakes.fake_decision_model import FakeDecisionModel

T = "tax-1"


class Models:
    def __init__(self, model):
        self.model = model

    def get(self, name=None):
        return self.model


@pytest.fixture()
def world(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    repo.save_taxonomy(Taxonomy(id=T, identifier="house", title="House"))
    repo.save_concept_scheme(ConceptScheme(id="s1", taxonomy_id=T, title="Rooms"))
    repo.save_class(Class(id="c1", taxonomy_id=T, concept_scheme_id="s1", title="Room"))
    claims = ClaimService(SQLiteClaimRepository(session_factory), repo)
    stored = claims.submit(
        T,
        [
            Claim(
                taxonomy_id=T,
                key=f"room#{n}",
                text=f"Room claim {n}",
                note_ref="room",
                note_source=NoteSource.REVIEWER,
                subject_id="c1",
            )
            for n in (1, 2, 3)
        ],
    )
    for claim, validity in zip(stored[:2], ("real_defect", "works_as_designed")):
        claims.set_verdict(
            claim.id,
            ClaimVerdict(validity=validity, adjudicated_by="user", category="other", severity=1),
        )
    yield repo, claims
    engine.dispose()


def test_the_judged_claims_are_triaged_and_scored(world):
    repo, claims = world
    model = FakeDecisionModel(
        "clef", choices={"validity": "real_defect", "category": "other"}, scores={"severity": 1}
    )

    bench = run_bench(repo, claims, T, Models(model))
    score, judged = bench.score, bench.scored

    assert len(model.calls) == 2  # only the claims with a verdict
    assert [c.key for c in judged] == ["room#1", "room#2"]
    assert {c.triage.run_id for c in judged} == {BENCH_RUN_ID}
    assert (bench.judged, score.n, bench.errors) == (2, 2, [])
    assert score.validity_accuracy == pytest.approx(0.5)
    assert score.misses == ("room#2",)
    assert score.severity_mae == 0
    untriaged = claims.list_claims(ClaimFilter(taxonomy_id=T, triaged=False))
    assert [c.key for c in untriaged] == ["room#3"]

    table = render(bench, "clef")
    assert "Benchmark: 2 adjudicated claims, 2 scored" in table
    assert "| clef | 2 | 50% |" in table
    assert "MISS room#2" in table and "ok   room#1" in table


def test_score_only_uses_the_saved_triage(world):
    repo, claims = world
    run_bench(repo, claims, T, Models(FakeDecisionModel("clef")))

    bench = run_bench(repo, claims, T)

    assert bench.score.n == 2


def test_a_claim_that_fails_is_reported_not_scored_on_old_answers(world, monkeypatch):
    repo, claims = world
    run_bench(repo, claims, T, Models(FakeDecisionModel("clef")))
    flash = FakeDecisionModel("clef-flash")
    real = flash.decide

    def flaky(state, questions):
        if "Room claim 2" in state:
            raise RuntimeError("timed out")
        return real(state, questions)

    monkeypatch.setattr(flash, "decide", flaky)

    bench = run_bench(repo, claims, T, Models(flash))

    assert bench.judged == 2
    assert [c.key for c in bench.scored] == ["room#1"]
    assert {c.triage.model for c in bench.scored} == {"clef-flash"}
    assert bench.errors == ["room#2: timed out"]
