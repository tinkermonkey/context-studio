"""
Schema changes to the relationship types Context Studio's own DR model uses
(#1417): a reverse swaps the ends of every relationship of the type and a
rename keeps them, in one transaction with the type's change; reverting the
proposal restores types and relationships; and the export carries the change
records in the action shape of DR's `applied-*.json`.

Built like test_dr_model_import.py: the model's spec snapshot
(`MODEL_DR_SPEC_VERSION`, with its predicate catalog as dist/base.json), then
`documentation-robotics/model/`, on file-backed SQLite with foreign keys
enforced, and the services wired as app.py wires them (DR rules, transaction
scope, change recording).
"""

import dataclasses
import json
import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.interchange.dr_relationships import DR_TAXONOMY_IDENTIFIER, DrRelationshipRules
from adapters.interchange.dr_spec_changes import spec_changes_for
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import OperationStatus, ProposalSource, ProposalStatus
from domain.versioning.revert_service import RevertService
from scripts.dr_model_loader import import_dr_model
from scripts.dr_ontology_loader import DR_SOURCE, import_dr_ontology
from scripts.import_dr_model import DEFAULT_VIEWER_DIR, build_import_service
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import MODEL_DR_SPEC_VERSION, dr_spec_dir
from tests.utils.change_recording import wire_change_recorder

# Used by the model: 29 relationships, and 36.
REVERSED = "data-model.objectschema.maps-to.api.response"
RENAMED = "api.operation.aggregates.api.requestbody"
AFTER_REVERSE = "api.response.maps-to.data-model.objectschema"
AFTER_RENAME = "api.operation.uses.api.requestbody"


@pytest.fixture(scope="module")
def model_db():
    """The model's spec and the model itself, imported once and copied per test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec = Path(tmpdir) / "spec"
        shutil.copytree(dr_spec_dir(MODEL_DR_SPEC_VERSION), spec)
        catalog = json.loads((spec / "schemas" / "base" / "predicates.json").read_text())
        (spec / "dist" / "base.json").write_text(json.dumps({"predicates": catalog["predicates"]}))
        path = Path(tmpdir) / "model.db"
        engine = create_local_db_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        service = build_import_service(session_factory, FakeEmbeddingService())
        repo = SQLiteOntologyRepository(session_factory)
        import_dr_ontology(service, repo, spec)
        import_dr_model(service, repo, DEFAULT_VIEWER_DIR)
        engine.dispose()
        yield path


@pytest.fixture()
def parts(model_db, tmp_path):
    db = tmp_path / "local.db"
    db.write_bytes(model_db.read_bytes())
    engine = create_local_db_engine(f"sqlite:///{db}")
    factory = SharedSessionFactory(sessionmaker(bind=engine))
    repo = SQLiteOntologyRepository(session_factory=factory)
    change_repo = SQLiteChangeRepository(session_factory=factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
    proposals = ProposalService(
        SQLiteChangeProposalRepository(factory),
        ontology,
        repo,
        RevertService(
            change_repo=change_repo,
            ontology_repo=repo,
            transaction_scope=SqliteTransactionScope(factory),
        ),
        apply_rules=[DrRelationshipRules(repo)],
        transaction_scope=SqliteTransactionScope(factory),
        event_publisher=publisher,
    )
    yield repo, proposals
    engine.dispose()


def prop_by_dr_id(repo, relationship_id):
    for prop in repo.list_property_definitions(limit=None):
        if any(
            r.source == DR_SOURCE and r.identifier == relationship_id
            for r in prop.external_references
        ):
            return prop
    return None


def edges(repo, prop):
    return {
        (r.source_id, r.target_id, json.dumps(r.attributes, sort_keys=True))
        for r in repo.list_relationships(property_id=prop.id, limit=None)
    }


def snap(entity):
    return {
        k: v for k, v in dataclasses.asdict(entity).items() if k not in {"last_modified", "version"}
    }


def reverse_and_rename(repo, proposals):
    """One proposal: reverse REVERSED (seq 1) and rename RENAMED's predicate (seq 2), as edits."""
    reversed_type, renamed_type = prop_by_dr_id(repo, REVERSED), prop_by_dr_id(repo, RENAMED)
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    proposal = proposals.propose(
        taxonomy.id,
        "Reverse and rename",
        [
            OperationDraft(
                seq=seq, op="update", kind="property", target_id=prop.id, fields={"title": "x"}
            )
            for seq, prop in ((1, reversed_type), (2, renamed_type))
        ],
        ProposalSource.MCP,
    )
    first, second = proposal.operations
    edits = {
        first.id: {
            "domain_class_id": reversed_type.range_class_id,
            "range_class_id": reversed_type.domain_class_id,
        },
        second.id: {"canonical_predicate": "uses"},
    }
    return proposals.apply(proposal.id, [first.id, second.id], edits=edits)


def test_the_model_uses_both_types(parts):
    repo, _ = parts
    assert len(edges(repo, prop_by_dr_id(repo, REVERSED))) == 29
    assert len(edges(repo, prop_by_dr_id(repo, RENAMED))) == 36


def test_a_reverse_swaps_and_a_rename_keeps_the_models_relationships(parts):
    repo, proposals = parts
    reversed_type, renamed_type = prop_by_dr_id(repo, REVERSED), prop_by_dr_id(repo, RENAMED)
    reversed_before, renamed_before = edges(repo, reversed_type), edges(repo, renamed_type)
    renamed_ids = {r.id for r in repo.list_relationships(property_id=renamed_type.id, limit=None)}

    proposal = reverse_and_rename(repo, proposals)

    assert [o.status for o in proposal.operations] == [OperationStatus.APPLIED] * 2, [
        o.reason for o in proposal.operations
    ]
    assert prop_by_dr_id(repo, AFTER_REVERSE).id == reversed_type.id
    assert prop_by_dr_id(repo, AFTER_RENAME).id == renamed_type.id
    assert edges(repo, reversed_type) == {(t, s, a) for s, t, a in reversed_before}
    assert edges(repo, renamed_type) == renamed_before
    assert {
        r.id for r in repo.list_relationships(property_id=renamed_type.id, limit=None)
    } == renamed_ids


def test_reverting_restores_the_types_and_their_relationships(parts):
    repo, proposals = parts
    types = {i: prop_by_dr_id(repo, i) for i in (REVERSED, RENAMED)}
    before = {i: snap(t) for i, t in types.items()}
    relationships = {
        r.id: snap(r)
        for t in types.values()
        for r in repo.list_relationships(property_id=t.id, limit=None)
    }
    proposal = reverse_and_rename(repo, proposals)

    proposals.revert(proposal.id)

    assert proposals.get(proposal.id).status is ProposalStatus.REVERTED
    assert {i: snap(repo.get_property_definition(t.id)) for i, t in types.items()} == before
    after = {
        r.id: snap(r)
        for t in types.values()
        for r in repo.list_relationships(property_id=t.id, limit=None)
    }
    assert after == relationships


def test_the_export_carries_the_records_as_drs_change_actions(parts):
    repo, proposals = parts
    proposal = reverse_and_rename(repo, proposals)
    decisions = proposals.decisions_of(proposal.id)

    document = spec_changes_for(proposal, repo, decisions)

    first, second = proposal.operations
    assert [
        {k: r[k] for k in ("action", "kind", "from", "to", "swap", "operation_id")}
        for r in document["records"]
    ] == [
        {
            "action": "rename",
            "kind": "cs:reverse",
            "from": REVERSED,
            "to": AFTER_REVERSE,
            "swap": True,
            "operation_id": first.id,
        },
        {
            "action": "rename",
            "kind": "cs:rename",
            "from": RENAMED,
            "to": AFTER_RENAME,
            "swap": False,
            "operation_id": second.id,
        },
    ]
    assert all(r["proposal_id"] == proposal.id and r["p"] == 1.0 for r in document["records"])
    assert document["records"][0]["applied_at"] == decisions[first.id].decided_at.isoformat()
    assert [(c["previous_relationship_id"], c["relationship_id"]) for c in document["changes"]] == [
        (REVERSED, AFTER_REVERSE),
        (RENAMED, AFTER_RENAME),
    ]
