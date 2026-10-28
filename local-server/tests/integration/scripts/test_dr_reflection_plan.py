"""
Integration tests (#1366): a DR reflection plan (`dr-reflection-plan/1`) becomes
a change proposal on dr_spec; applying it renames, reverses, retargets and
deletes relationship types (in-use ones keep their relationships); reverting
it restores them exactly; the decisions export in DR's shape; and the DR spec
re-imports cleanly after DR applies the same change.

Built on the pinned DR spec snapshot (0.8.4) on real SQLite with foreign keys
enforced and change events recorded. The plan fixture is DR's api-layer plan,
unedited (documentation_robotics commit 9b4dc9d6).
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import copy
import dataclasses
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
)
from domain.versioning.revert_service import RevertService
from scripts.dr_ontology_loader import DR_SOURCE, import_dr_ontology
from scripts.dr_reflection_plan import PlanError, decisions_for, import_reflection_plan, read_plan
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import pinned_dr_spec_dir
from tests.utils.change_recording import wire_change_recorder

PLAN_FILE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "dr_reflection_plan" / "api_full.json"
)
DELIVERS = "api.operation.delivers.api.response"
IN_USE = 3


@pytest.fixture(scope="module")
def spec_db():
    """A database with the pinned DR spec imported, built once and copied per test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "spec.db"
        engine = create_local_db_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        repo = SQLiteOntologyRepository(session_factory=sessionmaker(bind=engine))
        service = OntologyService(repo, FakeEmbeddingService(), InProcessEventPublisher())
        import_dr_ontology(service, repo, pinned_dr_spec_dir())
        engine.dispose()
        yield path


@pytest.fixture()
def parts(spec_db, tmp_path):
    db = tmp_path / "local.db"
    db.write_bytes(spec_db.read_bytes())
    engine = create_local_db_engine(f"sqlite:///{db}")
    session_factory = sessionmaker(bind=engine)
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    change_repo = SQLiteChangeRepository(session_factory=session_factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
    proposals = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        repo,
        RevertService(change_repo=change_repo, ontology_repo=repo),
    )
    yield ontology, repo, proposals
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


def put_delivers_in_use(ontology, repo):
    """IN_USE relationships typed by api.operation delivers api.response."""
    delivers = prop_by_dr_id(repo, DELIVERS)
    operation = class_by_dr_id(repo, "api.operation")
    response = class_by_dr_id(repo, "api.response")
    rel_ids = []
    for n in range(IN_USE):
        source = ontology.create_individual(operation.id, f"GET /things/{n}")
        target = ontology.create_individual(response.id, f"200 for {n}")
        rel_ids.append(ontology.create_relationship(source.id, target.id, delivers.id).id)
    return delivers, rel_ids


def snap(entity):
    return {
        k: v
        for k, v in dataclasses.asdict(entity).items()
        if k not in {"last_modified", "version", "embedding"}
    }


def plan_with(*operations):
    plan = read_plan(PLAN_FILE)
    plan["operations"] = list(operations)
    return plan


def plan_for(*seqs):
    """The fixture plan cut down to these seqs."""
    plan = read_plan(PLAN_FILE)
    plan["operations"] = [o for o in plan["operations"] if o["seq"] in seqs]
    assert len(plan["operations"]) == len(seqs)
    return plan


def operation(seq, op, target_id, **fields):
    return {
        "seq": seq,
        "op": op,
        "kind": "property",
        "target_id": target_id,
        "ref": None,
        "fields": fields,
        "base": {},
        "rationale": f"seq {seq}",
        "evidence": [{"quote": "q", "claim_id": f"rel:{seq}"}],
        "probability": 0.5,
        "scope": None,
        "status": "pending",
        "dr": {},
    }


def rename(seq, old_id, new_id):
    """An update moving a relationship type from one DR id to another."""
    old, new = old_id.split("."), new_id.split(".")
    fields = {"title": f"{new[0]}.{new[1]} {new[2]} {new[3]}.{new[4]}"}
    if new[2] != old[2]:
        fields["predicate"] = new[2]
    if new[:2] != old[:2]:
        fields["source_spec_node_id"] = f"{new[0]}.{new[1]}"
    if new[3:] != old[3:]:
        fields["destination_spec_node_id"] = f"{new[3]}.{new[4]}"
    return operation(seq, "update", old_id, **fields)


def apply_all(proposals, proposal):
    return proposals.apply(proposal.id, [o.id for o in proposal.operations])


def spec_after(tmp_path, renames):
    """A copy of the pinned spec in which DR has applied these {old id: new id} renames."""
    spec = tmp_path / "spec"
    shutil.copytree(pinned_dr_spec_dir(), spec)
    pending = dict(renames)
    for path in (spec / "schemas" / "relationships").glob("*/*.relationship.schema.json"):
        data = json.loads(path.read_text())
        props = data["properties"]
        full = ".".join(
            [
                props["source_spec_node_id"]["const"],
                props["predicate"]["const"],
                props["destination_spec_node_id"]["const"],
            ]
        )
        if full not in pending:
            continue
        new = pending.pop(full).split(".")
        props["source_spec_node_id"]["const"] = f"{new[0]}.{new[1]}"
        props["source_layer"]["const"] = new[0]
        props["predicate"]["const"] = new[2]
        props["destination_spec_node_id"]["const"] = f"{new[3]}.{new[4]}"
        props["destination_layer"]["const"] = new[3]
        path.write_text(json.dumps(data))
    assert not pending, pending
    return spec


# ------------------------------------------------------------- import, apply


def test_fixture_operations_map_onto_property_definitions(parts):
    _, repo, proposals = parts
    plan = plan_for(1, 13, 14, 28)
    proposal = import_reflection_plan(plan, proposals, repo)

    assert proposal.taxonomy_id == repo.get_by_identifier("dr_spec").id
    assert proposal.source is ProposalSource.PIPELINE
    assert proposal.title == plan["title"] and proposal.rationale == plan["rationale"]
    ops = {o.seq: o for o in proposal.operations}
    assert sorted(ops) == [1, 13, 14, 28]
    assert all(
        o.kind is OperationKind.PROPERTY and o.scope is ChangeScope.BREAKING for o in ops.values()
    )
    assert all(o.status is OperationStatus.PENDING for o in ops.values())

    delete = ops[1]
    assert delete.op is OperationType.DELETE
    assert delete.target_id == prop_by_dr_id(repo, "api.mediatype.aggregates.api.encoding").id
    assert delete.base["title"] == "api.mediatype aggregates api.encoding"  # CS's own snapshot

    renamed = ops[14]
    delivers = prop_by_dr_id(repo, DELIVERS)
    assert renamed.target_id == delivers.id
    assert renamed.fields == {
        "title": "api.operation aggregates api.response",
        "description": "Defines relationship: api.operation aggregates api.response",
        "canonical_predicate": "aggregates",
        "identifier": "operation_aggregates_response",
        "external_references": [
            {
                "source": DR_SOURCE,
                "identifier": "api.operation.aggregates.api.response",
                "uri": None,
                "metadata": None,
            }
        ],
    }
    assert renamed.base["identifier"] == delivers.identifier
    source_plan = next(o for o in plan["operations"] if o["seq"] == 14)
    assert renamed.rationale == source_plan["rationale"]
    assert renamed.evidence == source_plan["evidence"]
    assert renamed.probability == source_plan["probability"]

    retarget = ops[28]  # api.mediatype -> api.encoding as the source
    assert retarget.fields["domain_class_id"] == class_by_dr_id(repo, "api.encoding").id
    assert "range_class_id" not in retarget.fields
    assert retarget.fields["identifier"] == "encoding_associated_with_header"


def test_the_whole_fixture_imports_and_applies(parts):
    _, repo, proposals = parts
    plan = read_plan(PLAN_FILE)
    proposal = import_reflection_plan(plan, proposals, repo)
    assert [o.seq for o in proposal.operations] == [o["seq"] for o in plan["operations"]]
    assert Counter(o.op.value for o in proposal.operations) == {"delete": 43, "update": 20}

    applied = apply_all(proposals, proposal)

    assert {o.seq: o.reason for o in applied.operations if o.reason} == {}
    assert applied.status is ProposalStatus.DONE
    for item in plan["operations"]:
        if item["op"] == "delete":
            assert prop_by_dr_id(repo, item["target_id"]) is None, item["seq"]
        else:
            old = item["target_id"].split(".")
            fields = item["fields"]
            new_id = ".".join(
                [
                    fields.get("source_spec_node_id", f"{old[0]}.{old[1]}"),
                    fields.get("predicate", old[2]),
                    fields.get("destination_spec_node_id", f"{old[3]}.{old[4]}"),
                ]
            )
            moved = prop_by_dr_id(repo, new_id)
            assert moved is not None and prop_by_dr_id(repo, item["target_id"]) is None
            assert moved.title == fields["title"] and moved.description == fields["description"]


def test_apply_then_revert_restores_every_property_and_relationship(parts):
    ontology, repo, proposals = parts
    delivers, rel_ids = put_delivers_in_use(ontology, repo)
    plan = plan_for(1, 13, 14, 28)
    plan["operations"].append(
        rename(70, "api.ratelimit.serves.api.pathitem", "api.pathitem.serves.api.ratelimit")
    )
    targets = {o["target_id"] for o in plan["operations"]}
    before = {t: snap(prop_by_dr_id(repo, t)) for t in targets}
    rels_before = {r: snap(repo.get_relationship(r)) for r in rel_ids}

    proposal = import_reflection_plan(plan, proposals, repo)
    applied = apply_all(proposals, proposal)
    ops = {o.seq: o for o in applied.operations}

    assert all(o.status is OperationStatus.APPLIED for o in ops.values()), [
        (o.seq, o.reason) for o in ops.values()
    ]
    assert repo.get_property_definition(ops[1].target_id) is None
    renamed = repo.get_property_definition(delivers.id)
    assert renamed.identifier == "operation_aggregates_response"
    assert renamed.canonical_predicate == "aggregates"
    assert [r.identifier for r in renamed.external_references] == [
        "api.operation.aggregates.api.response"
    ]
    assert all(repo.get_relationship(r).property_definition_id == delivers.id for r in rel_ids)
    reversed_prop = repo.get_property_definition(ops[70].target_id)
    assert reversed_prop.domain_class_id == class_by_dr_id(repo, "api.pathitem").id
    assert reversed_prop.range_class_id == class_by_dr_id(repo, "api.ratelimit").id
    assert reversed_prop.identifier == "pathitem_serves_ratelimit"
    assert prop_by_dr_id(repo, "api.pathitem.serves.api.ratelimit").id == reversed_prop.id

    proposals.revert(proposal.id)

    assert {t: snap(prop_by_dr_id(repo, t)) for t in targets} == before
    assert {r: snap(repo.get_relationship(r)) for r in rel_ids} == rels_before


def test_deleting_an_in_use_relationship_type_fails_and_changes_nothing(parts):
    ontology, repo, proposals = parts
    delivers, rel_ids = put_delivers_in_use(ontology, repo)
    proposal = import_reflection_plan(plan_with(operation(5, "delete", DELIVERS)), proposals, repo)

    result = proposals.apply(proposal.id, [proposal.operations[0].id])

    op = result.operations[0]
    assert op.status is OperationStatus.FAILED
    assert (
        op.reason
        == f"error: PropertyDefinition '{delivers.id}' is in use by {IN_USE} relationship(s)"
    )
    assert repo.get_property_definition(delivers.id) is not None
    assert all(repo.get_relationship(r) is not None for r in rel_ids)


def test_create_maps_onto_a_new_property_definition(parts):
    _, repo, proposals = parts
    create = operation(
        9,
        "create",
        None,
        relationship_id="api.tag.governs.api.ratelimit",
        predicate="governs",
        source_spec_node_id="api.tag",
        destination_spec_node_id="api.ratelimit",
        title="api.tag governs api.ratelimit",
    )
    create["ref"] = "c9"
    proposal = import_reflection_plan(plan_with(copy.deepcopy(create)), proposals, repo)
    assert proposal.operations[0].ref == "c9"
    applied = proposals.apply(proposal.id, [proposal.operations[0].id])

    op = applied.operations[0]
    assert op.status is OperationStatus.APPLIED, op.reason
    made = repo.get_property_definition(op.result_entity_id)
    assert made.identifier == "tag_governs_ratelimit"
    assert made.title == "api.tag governs api.ratelimit"
    assert made.canonical_predicate == "governs"
    assert made.domain_class_id == class_by_dr_id(repo, "api.tag").id
    assert made.range_class_id == class_by_dr_id(repo, "api.ratelimit").id
    assert prop_by_dr_id(repo, "api.tag.governs.api.ratelimit").id == made.id


# --------------------------------------------------------- refused at import


def test_unresolvable_operations_are_listed_and_nothing_is_proposed(parts):
    _, repo, proposals = parts
    plan = plan_with(
        operation(1, "delete", "api.nothing.serves.api.nowhere"),
        operation(2, "update", DELIVERS, source_spec_node_id="api.unknown"),
        operation(3, "update", DELIVERS, cardinality="many"),
    )
    with pytest.raises(PlanError) as caught:
        import_reflection_plan(plan, proposals, repo)
    problems = caught.value.problems
    assert len(problems) == 3
    assert problems[0].startswith("seq 1 (delete api.nothing.serves.api.nowhere): no property")
    assert "no class for spec node api.unknown" in problems[1]
    assert "unknown fields ['cardinality']" in problems[2]
    assert proposals._proposals.count_proposals() == 0


def test_two_operations_on_one_relationship_type_are_refused_naming_both(parts):
    _, repo, proposals = parts
    target = "api.mediatype.aggregates.api.encoding"
    plan = plan_with(operation(32, "delete", target), operation(52, "delete", target))
    with pytest.raises(PlanError) as caught:
        import_reflection_plan(plan, proposals, repo)
    assert caught.value.problems == [f"seqs 32 and 52 both target {target}"]


def test_renames_onto_an_existing_or_shared_triple_are_refused_by_seq(parts):
    _, repo, proposals = parts
    existing = "api.components.aggregates.api.response"
    assert prop_by_dr_id(repo, existing) is not None
    plan = plan_with(
        rename(55, "api.components.composes.api.response", existing),
        rename(6, "api.components.composes.api.parameter", "api.components.uses.api.parameter"),
        rename(60, "api.components.composes.api.header", "api.components.uses.api.parameter"),
    )
    with pytest.raises(PlanError) as caught:
        import_reflection_plan(plan, proposals, repo)
    assert caught.value.problems == [
        f"seq 55 (update api.components.composes.api.response): {existing} already exists",
        "seqs 6 and 60 both produce api.components.uses.api.parameter",
    ]


@pytest.mark.parametrize("plan", [[], "plan", {"format": "dr-reflection-plan/1", "operations": 5}])
def test_a_malformed_plan_is_a_plan_error(parts, plan):
    _, repo, proposals = parts
    with pytest.raises(PlanError):
        import_reflection_plan(plan, proposals, repo)


def test_a_malformed_operation_is_listed(parts):
    _, repo, proposals = parts
    with pytest.raises(PlanError) as caught:
        import_reflection_plan(plan_with("delete everything", None), proposals, repo)
    assert caught.value.problems == [
        "operation 1: not an object",
        "operation 2: not an object",
    ]


# ----------------------------------------------------------- revert, export


def test_revert_refused_when_an_old_identifier_was_taken_meanwhile(parts):
    ontology, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(13, 14), proposals, repo)
    applied = apply_all(proposals, proposal)
    assert applied.status is ProposalStatus.DONE
    param = next(o for o in applied.operations if o.seq == 13)
    old_identifier = param.base["identifier"]
    assert old_identifier == "parameter_references_schema"
    ontology.create_property_definition(identifier=old_identifier, title="someone else")
    after_apply = {
        o.target_id: snap(repo.get_property_definition(o.target_id)) for o in applied.operations
    }

    with pytest.raises(ValueError, match="parameter_references_schema"):
        proposals.revert(proposal.id)

    assert {
        o.target_id: snap(repo.get_property_definition(o.target_id)) for o in applied.operations
    } == after_apply
    assert proposals.get(proposal.id).status is ProposalStatus.DONE


def test_decisions_export_in_drs_shape(parts):
    ontology, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(1, 9, 13, 14, 28), proposals, repo)
    ops = {o.seq: o for o in proposal.operations}
    ontology.update_property_definition(ops[28].target_id, description="Edited meanwhile")
    proposals.apply(proposal.id, [ops[1].id, ops[14].id, ops[28].id])
    proposals.reject(proposal.id, [ops[13].id], note="Keep references")

    decisions = decisions_for(proposals.get(proposal.id))

    by_seq = {d["seq"]: d for d in decisions}
    assert [d["seq"] for d in decisions] == [1, 9, 13, 14, 28]
    assert all(
        set(d) == {"seq", "op_id", "status", "reason", "result_entity_id"} for d in decisions
    )
    assert by_seq[1] == {
        "seq": 1,
        "op_id": ops[1].id,
        "status": "applied",
        "reason": None,
        "result_entity_id": ops[1].target_id,
    }
    assert by_seq[13]["status"] == "rejected" and by_seq[13]["reason"] == "Keep references"
    assert by_seq[14]["status"] == "applied"
    assert by_seq[28]["status"] == "failed"
    assert by_seq[28]["reason"].startswith("target_changed:")
    assert by_seq[9]["status"] == "pending"
    json.dumps(decisions)  # serializable as written

    proposals.revert(proposal.id)
    with pytest.raises(ValueError, match="reverted"):
        decisions_for(proposals.get(proposal.id))


# ------------------------------------------------- DR applies, CS re-imports


def reimport_after(parts, tmp_path, old_id, new_id):
    """Propose and apply the rename, then re-import the spec DR produced from it."""
    ontology, repo, proposals = parts
    proposal = import_reflection_plan(plan_with(rename(1, old_id, new_id)), proposals, repo)
    applied = apply_all(proposals, proposal)
    assert applied.operations[0].status is OperationStatus.APPLIED, applied.operations[0].reason
    renamed = repo.get_property_definition(applied.operations[0].target_id)
    before = {p.id: p.identifier for p in repo.list_property_definitions(limit=None)}

    summary = import_dr_ontology(ontology, repo, spec_after(tmp_path, {old_id: new_id}))

    after = {p.id: p.identifier for p in repo.list_property_definitions(limit=None)}
    assert set(after) == set(before)  # nothing created, nothing lost
    assert len(set(after.values())) == len(after)
    assert summary.stale == []
    assert summary.property_definitions_created == 0
    assert after[renamed.id] == renamed.identifier  # the proposal chose what the loader computes
    return before, after


def test_reimport_after_a_rename_updates_in_place(parts, tmp_path):
    before, after = reimport_after(
        parts, tmp_path, DELIVERS, "api.operation.aggregates.api.response"
    )
    assert before == after


def test_reimport_after_a_rename_into_a_collision_group(parts, tmp_path):
    _, repo, _ = parts
    twin = prop_by_dr_id(repo, "data-store.view.realizes.api.response")
    assert twin.identifier == "view_realizes_response"

    before, after = reimport_after(
        parts, tmp_path, "ux.view.serves.business.businessrole", "ux.view.realizes.api.response"
    )

    # Both now share a stripped form, so the loader hashes both, the twin in place.
    assert after[twin.id] != "view_realizes_response"
    assert after[twin.id].startswith("view_realizes_response_")
    changed = {i for i in after if after[i] != before[i]}
    assert changed == {twin.id}


def test_reimport_after_a_rename_out_of_a_collision_group(parts, tmp_path):
    _, repo, _ = parts
    old = "ux.view.serves.application.applicationservice"
    twin = prop_by_dr_id(repo, "data-store.view.serves.application.applicationservice")
    assert twin is not None and twin.identifier != "view_serves_applicationservice"

    before, after = reimport_after(
        parts, tmp_path, old, "ux.view.uses.application.applicationservice"
    )

    assert after[prop_by_dr_id(repo, "ux.view.uses.application.applicationservice").id] == (
        "view_uses_applicationservice"
    )
    assert after[twin.id] == "view_serves_applicationservice"  # left alone, so un-hashed
