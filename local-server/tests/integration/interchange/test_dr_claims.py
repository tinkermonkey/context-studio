"""
DR's claims and bench gold imported into the dr_spec taxonomy (#1521), against
the pinned DR spec snapshot and the committed DR triage fixtures.
"""

from pathlib import Path

import pytest

from adapters.interchange.dr_claims import DR_BENCH_GOLD, import_dr_claims, read_jsonl
from adapters.interchange.dr_relationships import (
    DR_TAXONOMY_IDENTIFIER,
    dr_property_definitions,
    dr_spec_classes,
)
from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.versioning.claims import ClaimFilter, ClaimService, ClaimVerdict, Validity
from scripts.dr_ontology_loader import import_dr_ontology
from scripts.import_dr_model import build_import_service
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import MODEL_DR_SPEC_VERSION, dr_spec_dir

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dr_triage"
CLAIMS = read_jsonl(FIXTURES / "claims.jsonl.xz")
GOLD = read_jsonl(FIXTURES / "bench-gold.jsonl")


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    """The pinned DR spec in a file SQLite workspace, with DR's claims imported once."""
    engine = create_local_db_engine(
        f"sqlite:///{tmp_path_factory.mktemp('dr_claims') / 'local.db'}"
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    import_dr_ontology(
        build_import_service(session_factory, FakeEmbeddingService()),
        repo,
        dr_spec_dir(MODEL_DR_SPEC_VERSION),
    )
    service = ClaimService(SQLiteClaimRepository(session_factory), repo)
    result = import_dr_claims(service, repo, CLAIMS, GOLD)
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    yield repo, service, taxonomy.id, result
    engine.dispose()


def by_key(service, taxonomy_id, key):
    return service.list_claims(ClaimFilter(taxonomy_id=taxonomy_id, keys=(key,)))[0]


def test_every_claim_and_gold_row_is_stored(workspace):
    _, service, taxonomy_id, result = workspace

    assert result.claims == len(CLAIMS) == 1462
    assert service.count_claims(ClaimFilter(taxonomy_id=taxonomy_id)) == 1462
    assert result.verdicts == len(GOLD) == 10
    assert result.gold_without_claim == []
    # Most DR ids map to an entity of the pinned spec; the report lists the rest
    assert result.unresolved_references < result.references * 0.15
    assert len(result.unresolved) > 0


def test_dr_ids_map_to_classes_attributes_and_property_definitions(workspace):
    repo, service, taxonomy_id, _ = workspace
    classes = dr_spec_classes(repo)

    node_claim = by_key(service, taxonomy_id, "node:api.callback#2")
    assert node_claim.subject_id == classes["api.callback"]
    assert node_claim.note_ref == "node:api.callback"
    assert node_claim.note_source.value == "maintainer"
    assert node_claim.category_hint == "definition_conflict"
    callback, expression = node_claim.affected_ids
    assert callback == classes["api.callback"]
    attribute = repo.get_attribute_definition(expression)
    assert attribute.class_id == classes["api.callback"]
    assert attribute.identifier == "expression"

    relationship_claim = by_key(service, taxonomy_id, "rel:api.callback#1")
    uses = dr_property_definitions(repo)["api.callback.uses.api.server"]
    assert relationship_claim.affected_ids == [uses.id]


def test_gold_becomes_verdicts(workspace):
    _, service, taxonomy_id, _ = workspace

    claim = by_key(service, taxonomy_id, "node:security.accesscondition#1")

    assert claim.verdict.validity is Validity.REAL_DEFECT
    assert claim.verdict.adjudicated_by == DR_BENCH_GOLD
    assert (claim.verdict.severity, claim.verdict.fix_scope) == (2, 2)
    assert claim.verdict.rationale.startswith("Charter:")


def test_importing_again_replaces_rather_than_adds(workspace):
    repo, service, taxonomy_id, first = workspace
    before = by_key(service, taxonomy_id, "node:security.accesscondition#1")

    again = import_dr_claims(service, repo, CLAIMS)

    assert again.claims == first.claims
    assert service.count_claims(ClaimFilter(taxonomy_id=taxonomy_id)) == 1462
    after = by_key(service, taxonomy_id, "node:security.accesscondition#1")
    assert after.id == before.id
    assert after.verdict == before.verdict


def test_without_the_dr_spec_the_import_is_refused(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)

    with pytest.raises(ValueError, match="import the DR spec first"):
        import_dr_claims(ClaimService(SQLiteClaimRepository(session_factory), repo), repo, CLAIMS)
    engine.dispose()


def row(key, text, subject="api.callback", affected=("api.callback",)):
    return {
        "id": key,
        "note_id": key.split("#")[0],
        "layer": subject.split(".")[0],
        "subject": subject,
        "kind": "node",
        "text": text,
        "category_hint": "other",
        "affected_ids": list(affected),
        "proposed_change": "",
    }


def gold(key):
    return {"claim_id": key, "validity": "judgment_call", "category": "other", "severity": 1}


def test_a_subject_the_spec_lacks_is_kept_as_unresolved(workspace):
    repo, service, taxonomy_id, _ = workspace

    result = import_dr_claims(
        service,
        repo,
        [row("test:api.nosuch#1", "No such type", "api.nosuch", ["api.nosuch", "api.callback"])],
        [gold("test:missing#1")],
    )

    claim = by_key(service, taxonomy_id, "test:api.nosuch#1")
    assert claim.subject_id is None
    assert claim.unresolved_refs == ["api.nosuch"]
    assert claim.affected_ids == [dr_spec_classes(repo)["api.callback"]]
    assert result.unresolved_subjects == ["api.nosuch"]
    assert (result.references, result.unresolved_references) == (2, 1)
    assert result.gold_without_claim == ["test:missing#1"]


def test_gold_skips_a_claim_whose_text_changed_or_a_persons_verdict(workspace):
    repo, service, taxonomy_id, _ = workspace
    import_dr_claims(service, repo, [row("test:a#1", "First split"), row("test:b#1", "Kept")])
    judged = by_key(service, taxonomy_id, "test:b#1")
    service.set_verdict(judged.id, ClaimVerdict(validity="real_defect", adjudicated_by="user"))

    result = import_dr_claims(
        service,
        repo,
        [row("test:a#1", "Re-split: another sentence"), row("test:b#1", "Kept")],
        [gold("test:a#1"), gold("test:b#1")],
    )

    assert result.verdicts == 0
    assert result.gold_on_changed_claims == ["test:a#1"]
    assert result.gold_under_person_verdicts == ["test:b#1"]
    assert by_key(service, taxonomy_id, "test:a#1").verdict is None
    assert by_key(service, taxonomy_id, "test:b#1").verdict.adjudicated_by == "user"
