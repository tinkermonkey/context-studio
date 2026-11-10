"""
Integration tests for SQLiteClaimRepository (#1518) on real SQLite with foreign
keys enforced; the in-memory fake must behave the same.
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base, ClaimRecord
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import Taxonomy
from domain.versioning.claims import Claim, ClaimFilter, ClaimTriage, ClaimVerdict, Validity
from tests.fakes.fake_claim_repository import FakeClaimRepository

TAXONOMY = "tax-1"
WHEN = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def ontology_repo(session_factory):
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    repo.save_taxonomy(Taxonomy(id=TAXONOMY, identifier="dr", title="DR"))
    return repo


@pytest.fixture(params=["sqlite", "fake"])
def repo(request, session_factory, ontology_repo):
    if request.param == "sqlite":
        return SQLiteClaimRepository(session_factory)
    return FakeClaimRepository()


def claim(key, text="Attribute x should be required", note_ref="note-1", **kwargs):
    return Claim(
        taxonomy_id=TAXONOMY,
        key=key,
        text=text,
        note_ref=note_ref,
        note_source="maintainer",
        **kwargs,
    )


def triage(validity=Validity.REAL_DEFECT):
    return ClaimTriage(
        validity=validity,
        model="clef",
        validity_probabilities={validity.value: 0.8},
        category="attribute_typing",
        severity=2,
        fix_scope=1,
        addressed_by_proposal=0.1,
        cost_usd=0.001,
        latency_ms=120.0,
        triaged_at=WHEN,
    )


def verdict():
    return ClaimVerdict(
        validity=Validity.WORKS_AS_DESIGNED,
        adjudicated_by="user",
        rationale="The layer intends it",
        severity=0,
        fix_scope=0,
        adjudicated_at=WHEN,
    )


def test_upsert_stores_and_returns_claims_in_order(repo):
    stored = repo.upsert(
        [
            claim("note-1#2", affected_ids=["c1", "c2"], unresolved_refs=["x.y"]),
            claim("note-1#1", subject_id="c1", note_text="Full note", proposed_change="Require x"),
        ]
    )

    assert [c.key for c in stored] == ["note-1#2", "note-1#1"]
    assert repo.get(stored[0].id) == stored[0]
    assert stored[0].affected_ids == ["c1", "c2"]
    assert stored[0].unresolved_refs == ["x.y"]
    assert stored[1].note_text == "Full note"
    assert stored[1].created_at.tzinfo is not None


def test_resubmitting_a_key_replaces_it_and_keeps_answers_for_the_same_text(repo):
    first = repo.upsert([claim("note-1#1")])[0]
    repo.save_triage(first.id, triage())
    repo.set_verdict(first.id, verdict())

    same = repo.upsert([claim("note-1#1", category_hint="attribute_typing")])[0]
    assert same.id == first.id
    assert same.created_at == first.created_at
    assert same.category_hint == "attribute_typing"
    assert same.triage == triage()
    assert same.verdict == verdict()

    reworded = repo.upsert([claim("note-1#1", text="Attribute x is optional by mistake")])[0]
    assert reworded.id == first.id
    assert (reworded.triage, reworded.verdict) == (None, None)


def test_triage_and_verdict_round_trip(repo):
    stored = repo.upsert([claim("note-1#1")])[0]

    repo.save_triage(stored.id, triage())
    repo.set_verdict(stored.id, verdict())
    got = repo.get(stored.id)
    assert got.triage == triage()
    assert got.verdict == verdict()

    repo.set_verdict(stored.id, None)
    assert repo.get(stored.id).verdict is None


def test_filters(repo):
    a, b, c = repo.upsert(
        [
            claim("n1#1", subject_id="c1"),
            claim("n1#2", subject_id="c2"),
            claim("n2#1", note_ref="n2", subject_id="c1"),
        ]
    )
    repo.save_triage(a.id, triage(Validity.REAL_DEFECT))
    repo.save_triage(b.id, triage(Validity.OUT_OF_SCOPE))
    repo.set_verdict(b.id, verdict())

    def keys(**kwargs):
        return [x.key for x in repo.list_claims(ClaimFilter(taxonomy_id=TAXONOMY, **kwargs))]

    assert keys() == ["n1#1", "n1#2", "n2#1"]
    assert keys(subject_id="c1") == ["n1#1", "n2#1"]
    assert keys(note_ref="n2") == ["n2#1"]
    assert keys(triaged=True) == ["n1#1", "n1#2"]
    assert keys(triaged=False) == ["n2#1"]
    assert keys(has_verdict=True) == ["n1#2"]
    assert keys(has_verdict=False) == ["n1#1", "n2#1"]
    assert keys(validity=Validity.OUT_OF_SCOPE) == ["n1#2"]
    assert keys(keys=("n2#1", "n1#1")) == ["n1#1", "n2#1"]
    assert repo.count_claims(ClaimFilter(taxonomy_id=TAXONOMY, triaged=True)) == 2
    assert repo.count_claims(ClaimFilter(taxonomy_id="other")) == 0
    page = repo.list_claims(ClaimFilter(taxonomy_id=TAXONOMY), limit=1, offset=1)
    assert [x.key for x in page] == ["n1#2"]


def test_delete_for_note(repo):
    repo.upsert(
        [claim("n1#1", note_ref="n1"), claim("n1#2", note_ref="n1"), claim("n2#1", note_ref="n2")]
    )

    assert repo.delete_for_note(TAXONOMY, "n1") == 2
    assert repo.delete_for_note("other", "n2") == 0
    assert [c.key for c in repo.list_claims(ClaimFilter(taxonomy_id=TAXONOMY))] == ["n2#1"]


def test_claims_go_with_their_taxonomy(session_factory, ontology_repo):
    repo = SQLiteClaimRepository(session_factory)
    repo.upsert([claim("note-1#1")])

    ontology_repo.delete_taxonomy(TAXONOMY)

    with session_factory() as session:
        assert session.query(ClaimRecord).count() == 0


def test_untriaged_claims_store_sql_null(session_factory, ontology_repo):
    """Not JSON 'null': the untriaged and has-verdict filters depend on it."""
    SQLiteClaimRepository(session_factory).upsert([claim("note-1#1")])

    with session_factory() as session:
        row = session.query(ClaimRecord).one()
        assert session.execute(
            ClaimRecord.__table__.select().where(ClaimRecord.triage.is_(None))
        ).first()
        assert row.verdict is None
