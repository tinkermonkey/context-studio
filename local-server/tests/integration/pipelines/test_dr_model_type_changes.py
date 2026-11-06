"""
Schema changes to the relationship types Context Studio's own DR model uses
(#1417): a reverse swaps the ends of every relationship of the type in place
(ids, provenance and creation time kept) and a rename keeps them, in one
transaction with the type's change; an in-use retarget waits for a
resolution; reverting the proposal restores types and relationships, and
reverting the run that made a relationship still removes it; and the export
carries the change records in the action shape of DR's `applied-*.json`.

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
from types import SimpleNamespace

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
from domain.interchange.services import get_current_batch_run_id, set_batch_run_context
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    InUseResolution,
    OperationStatus,
    ProposalSource,
    ProposalStatus,
    ResolutionStrategy,
)
from domain.versioning.revert_service import RevertService
from scripts.dr_model_loader import import_dr_model
from scripts.dr_ontology_loader import DR_SOURCE, import_dr_ontology
from scripts.import_dr_model import DEFAULT_VIEWER_DIR, build_import_service
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import MODEL_DR_SPEC_VERSION, dr_spec_dir
from tests.utils.change_recording import wire_change_recorder
from tests.utils.parent_rows import create_batch_run_row

# Used by the model: 29 relationships, and 36.
REVERSED = "data-model.objectschema.maps-to.api.response"
RENAMED = "api.operation.aggregates.api.requestbody"
AFTER_REVERSE = "api.response.maps-to.data-model.objectschema"
AFTER_RENAME = "api.operation.uses.api.requestbody"
# Used by 6 relationships; its pair reversed is another type's.
RETARGETED = "application.applicationevent.triggers.application.applicationprocess"
REVERSED_TWIN = "application.applicationprocess.triggers.application.applicationevent"
AFTER_RETARGET = "application.applicationevent.triggers.application.applicationfunction"
MOVE = ResolutionStrategy.MOVE


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
    revert = RevertService(
        change_repo=change_repo,
        ontology_repo=repo,
        transaction_scope=SqliteTransactionScope(factory),
    )
    proposals = ProposalService(
        SQLiteChangeProposalRepository(factory),
        ontology,
        repo,
        revert,
        apply_rules=[DrRelationshipRules(repo)],
        transaction_scope=SqliteTransactionScope(factory),
        event_publisher=publisher,
    )
    yield SimpleNamespace(
        repo=repo, proposals=proposals, ontology=ontology, revert=revert, factory=factory
    )
    engine.dispose()


def prop_by_dr_id(repo, relationship_id):
    for prop in repo.list_property_definitions(limit=None):
        if any(
            r.source == DR_SOURCE and r.identifier == relationship_id
            for r in prop.external_references
        ):
            return prop
    return None


def class_by_dr_id(repo, spec_node_id):
    for cls in repo.list_classes(limit=None):
        if any(
            r.source == DR_SOURCE and r.identifier == spec_node_id for r in cls.external_references
        ):
            return cls
    raise AssertionError(spec_node_id)


def edges(repo, prop):
    """Each relationship of the type: id, ends, attributes, provenance and creation time."""
    return {
        (
            r.id,
            r.source_id,
            r.target_id,
            json.dumps(r.attributes, sort_keys=True),
            r.source_run_id,
            r.created_at,
        )
        for r in repo.list_relationships(property_id=prop.id, limit=None)
    }


def swapped(found):
    return {(i, t, s, a, run, at) for i, s, t, a, run, at in found}


def snap(entity):
    return {
        k: v for k, v in dataclasses.asdict(entity).items() if k not in {"last_modified", "version"}
    }


def propose_edits(parts, title, *props):
    """A proposal of title updates of the types, to apply with edits."""
    taxonomy = parts.repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    return parts.proposals.propose(
        taxonomy.id,
        title,
        [
            OperationDraft(
                seq=seq, op="update", kind="property", target_id=prop.id, fields={"title": "x"}
            )
            for seq, prop in enumerate(props, start=1)
        ],
        ProposalSource.MCP,
    )


def reverse_and_rename(parts):
    """One proposal: reverse REVERSED (seq 1) and rename RENAMED's predicate (seq 2), as edits."""
    repo = parts.repo
    reversed_type, renamed_type = prop_by_dr_id(repo, REVERSED), prop_by_dr_id(repo, RENAMED)
    proposal = propose_edits(parts, "Reverse and rename", reversed_type, renamed_type)
    first, second = proposal.operations
    edits = {
        first.id: {
            "domain_class_id": reversed_type.range_class_id,
            "range_class_id": reversed_type.domain_class_id,
        },
        second.id: {"canonical_predicate": "uses"},
    }
    return parts.proposals.apply(proposal.id, [first.id, second.id], edits=edits)


def test_the_model_uses_both_types(parts):
    repo = parts.repo
    assert len(edges(repo, prop_by_dr_id(repo, REVERSED))) == 29
    assert len(edges(repo, prop_by_dr_id(repo, RENAMED))) == 36


def test_a_reverse_swaps_in_place_and_a_rename_keeps_the_models_relationships(parts):
    repo = parts.repo
    reversed_type, renamed_type = prop_by_dr_id(repo, REVERSED), prop_by_dr_id(repo, RENAMED)
    reversed_before, renamed_before = edges(repo, reversed_type), edges(repo, renamed_type)

    proposal = reverse_and_rename(parts)

    assert [o.status for o in proposal.operations] == [OperationStatus.APPLIED] * 2, [
        o.reason for o in proposal.operations
    ]
    assert prop_by_dr_id(repo, AFTER_REVERSE).id == reversed_type.id
    assert prop_by_dr_id(repo, AFTER_RENAME).id == renamed_type.id
    # Same ids, attributes, provenance and creation time; ends swapped.
    assert edges(repo, reversed_type) == swapped(reversed_before)
    assert edges(repo, renamed_type) == renamed_before


def test_a_reverse_swaps_a_pair_running_both_ways(parts):
    """On SQLite's (source, target, type) unique constraint: each keeps its id."""
    repo = parts.repo
    reversed_type = prop_by_dr_id(repo, REVERSED)
    one = repo.list_relationships(property_id=reversed_type.id, limit=1)[0]
    mirror = parts.ontology.create_relationship(one.target_id, one.source_id, reversed_type.id)
    before = edges(repo, reversed_type)

    proposal = reverse_and_rename(parts)

    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason
    assert edges(repo, reversed_type) == swapped(before)
    assert repo.get_relationship(mirror.id).source_id == one.source_id

    parts.proposals.revert(proposal.id)

    assert edges(repo, reversed_type) == before


def test_reverting_restores_the_types_and_their_relationships(parts):
    repo = parts.repo
    types = {i: prop_by_dr_id(repo, i) for i in (REVERSED, RENAMED)}
    before = {i: snap(t) for i, t in types.items()}
    relationships = {
        r.id: snap(r)
        for t in types.values()
        for r in repo.list_relationships(property_id=t.id, limit=None)
    }
    proposal = reverse_and_rename(parts)

    parts.proposals.revert(proposal.id)

    assert parts.proposals.get(proposal.id).status is ProposalStatus.REVERTED
    assert {i: snap(repo.get_property_definition(t.id)) for i, t in types.items()} == before
    after = {
        r.id: snap(r)
        for t in types.values()
        for r in repo.list_relationships(property_id=t.id, limit=None)
    }
    assert after == relationships


def test_reverting_the_run_that_made_a_relationship_removes_it_after_a_reverse(parts):
    repo = parts.repo
    reversed_type = prop_by_dr_id(repo, REVERSED)
    schema = parts.ontology.create_individual(
        class_by_dr_id(repo, "data-model.objectschema").id, "Extracted schema"
    )
    response = parts.ontology.create_individual(
        class_by_dr_id(repo, "api.response").id, "Extracted response"
    )
    previous = get_current_batch_run_id()
    run_id = create_batch_run_row(parts.factory)
    set_batch_run_context(run_id)
    try:
        made = parts.ontology.create_relationship(
            schema.id, response.id, reversed_type.id, source_run_id=run_id
        )
    finally:
        set_batch_run_context(previous)
    reverse_and_rename(parts)
    assert repo.get_relationship(made.id).source_id == response.id

    parts.revert.revert(run_id)

    assert repo.get_relationship(made.id) is None


def test_the_export_carries_the_records_as_drs_change_actions(parts):
    repo, proposals = parts.repo, parts.proposals
    proposal = reverse_and_rename(parts)
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


def test_an_in_use_retarget_waits_for_a_resolution(parts):
    repo = parts.repo
    retargeted = prop_by_dr_id(repo, RETARGETED)
    before = edges(repo, retargeted)
    proposal = propose_edits(parts, "Retarget", retargeted)
    (op,) = proposal.operations
    edit = {"range_class_id": class_by_dr_id(repo, "application.applicationfunction").id}

    (failed,) = parts.proposals.apply(proposal.id, [op.id], edits={op.id: edit}).operations

    assert failed.status is OperationStatus.FAILED
    assert "a retarget needs a resolution" in failed.reason
    assert edges(repo, retargeted) == before
    assert prop_by_dr_id(repo, RETARGETED).id == retargeted.id


def test_a_retarget_that_moved_its_relationships_exports_like_a_moved_delete(parts):
    """The old triple's relationships went to the reversed type: DR moves them there too."""
    repo = parts.repo
    retargeted, replacement = prop_by_dr_id(repo, RETARGETED), prop_by_dr_id(repo, REVERSED_TWIN)
    moved = edges(repo, retargeted)
    proposal = propose_edits(parts, "Retarget", retargeted)
    (op,) = proposal.operations
    edit = {"range_class_id": class_by_dr_id(repo, "application.applicationfunction").id}
    resolution = InUseResolution(strategy=MOVE, replacement_property_id=replacement.id)

    applied = parts.proposals.apply(
        proposal.id, [op.id], edits={op.id: edit}, resolutions={op.id: resolution}
    )

    (op,) = applied.operations
    assert op.status is OperationStatus.APPLIED, op.reason
    assert edges(repo, retargeted) == set()
    assert {(t, s) for _, s, t, *_ in moved} <= {(s, t) for _, s, t, *_ in edges(repo, replacement)}
    records = spec_changes_for(applied, repo, parts.proposals.decisions_of(applied.id))["records"]
    assert [(r["action"], r["kind"], r["from"], r["to"], r["swap"]) for r in records] == [
        ("delete", "cs:retarget", RETARGETED, REVERSED_TWIN, True),
        ("create", "cs:retarget", AFTER_RETARGET, AFTER_RETARGET, False),
    ]
