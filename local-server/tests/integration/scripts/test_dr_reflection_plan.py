"""
Integration tests (#1366): a DR reflection plan (`dr-reflection-plan/1`) becomes
a change proposal on dr_spec; applying it renames, reverses, retargets and
deletes relationship types (in-use ones keep their relationships); reverting
it restores them exactly; and the decisions export in DR's shape.

Built on the pinned DR spec snapshot (0.8.4) on real SQLite with foreign keys
enforced and change events recorded. The plan fixture is six operations of
DR's api-layer plan (commit 495ab6b0 of documentation_robotics).
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import copy
import dataclasses
import json
import tempfile
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
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
)
from domain.versioning.revert_service import RevertService
from scripts.dr_ontology_loader import DR_SOURCE, import_dr_ontology
from scripts.dr_reflection_plan import PlanError, decisions_for, import_reflection_plan, read_plan
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.dr_spec import pinned_dr_spec_dir
from tests.utils.change_recording import wire_change_recorder

PLAN_FILE = Path(__file__).resolve().parents[1] / "fixtures" / "dr_reflection_plan" / "api.json"
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


def test_fixture_imports_as_a_proposal_with_mapped_operations(parts):
    _, repo, proposals = parts
    plan = read_plan(PLAN_FILE)
    proposal = import_reflection_plan(plan, proposals, repo)

    assert proposal.taxonomy_id == repo.get_by_identifier("dr_spec").id
    assert proposal.source is ProposalSource.PIPELINE
    assert proposal.title == plan["title"] and proposal.rationale == plan["rationale"]
    ops = {o.seq: o for o in proposal.operations}
    assert sorted(ops) == [o["seq"] for o in plan["operations"]] == [1, 13, 14, 28, 56, 63]
    assert all(
        o.kind is OperationKind.PROPERTY and o.scope is ChangeScope.BREAKING for o in ops.values()
    )
    assert all(o.status is OperationStatus.PENDING for o in ops.values())

    delete = ops[1]
    assert delete.op is OperationType.DELETE
    assert delete.target_id == prop_by_dr_id(repo, "api.mediatype.aggregates.api.encoding").id
    assert delete.base["title"] == "api.mediatype aggregates api.encoding"  # CS's own snapshot

    rename = ops[14]
    delivers = prop_by_dr_id(repo, DELIVERS)
    assert rename.target_id == delivers.id
    assert rename.fields == {
        "title": "api.operation aggregates api.response",
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
    assert rename.base["identifier"] == delivers.identifier
    source_plan = next(o for o in plan["operations"] if o["seq"] == 14)
    assert rename.rationale == source_plan["rationale"]
    assert rename.evidence == source_plan["evidence"]
    assert rename.probability == source_plan["probability"]

    retarget = ops[28]  # api.mediatype -> api.encoding as the source
    assert retarget.fields["domain_class_id"] == class_by_dr_id(repo, "api.encoding").id
    assert "range_class_id" not in retarget.fields
    assert retarget.fields["identifier"] == "encoding_associated_with_header"


def test_apply_then_revert_restores_every_property_and_relationship(parts):
    ontology, repo, proposals = parts
    delivers, rel_ids = put_delivers_in_use(ontology, repo)
    reverse = operation(
        70,
        "update",
        "api.ratelimit.serves.api.pathitem",
        source_spec_node_id="api.pathitem",
        destination_spec_node_id="api.ratelimit",
        title="api.pathitem serves api.ratelimit",
    )
    plan = read_plan(PLAN_FILE)
    plan["operations"].append(reverse)
    targets = {o["target_id"] for o in plan["operations"]}
    before = {t: snap(prop_by_dr_id(repo, t)) for t in targets}
    rels_before = {r: snap(repo.get_relationship(r)) for r in rel_ids}

    proposal = import_reflection_plan(plan, proposals, repo)
    applied = proposals.apply(proposal.id, [o.id for o in proposal.operations])
    ops = {o.seq: o for o in applied.operations}

    for seq in (1, 13, 14, 28, 70):
        assert ops[seq].status is OperationStatus.APPLIED, (seq, ops[seq].reason)
    # 56 and 63 rename onto a schema that already exists; the title is taken.
    for seq in (56, 63):
        assert ops[seq].status is OperationStatus.FAILED
        assert ops[seq].reason.startswith("error: PropertyDefinition with title")

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


def test_two_deletes_of_one_relationship_type_are_refused(parts):
    _, repo, proposals = parts
    target = "api.mediatype.aggregates.api.encoding"
    plan = plan_with(operation(32, "delete", target), operation(52, "delete", target))
    with pytest.raises(ProposalValidationError) as caught:
        import_reflection_plan(plan, proposals, repo)
    assert [(e.seq, e.code) for e in caught.value.errors] == [(52, "conflicting_op")]


def test_decisions_export_in_drs_shape(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(read_plan(PLAN_FILE), proposals, repo)
    ops = {o.seq: o for o in proposal.operations}
    proposals.apply(proposal.id, [ops[1].id, ops[14].id, ops[56].id])
    proposals.reject(proposal.id, [ops[13].id], note="Keep references")

    decisions = decisions_for(proposals.get(proposal.id))

    by_seq = {d["seq"]: d for d in decisions}
    assert [d["seq"] for d in decisions] == [1, 13, 14, 28, 56, 63]
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
    assert by_seq[56]["status"] == "failed" and by_seq[56]["reason"].startswith("error:")
    assert by_seq[28]["status"] == by_seq[63]["status"] == "pending"
    json.dumps(decisions)  # serializable as written

    proposals.revert(proposal.id)
    with pytest.raises(ValueError, match="reverted"):
        decisions_for(proposals.get(proposal.id))


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
