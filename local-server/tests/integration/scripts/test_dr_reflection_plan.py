"""
Integration tests (#1366): a DR reflection plan (`dr-reflection-plan/1`) becomes
a change proposal on dr_spec; applying it renames, reverses, retargets and
deletes relationship types (in-use ones keep their relationships); reverting
it restores them exactly; the decisions export in DR's shape; and the DR spec
re-imports cleanly after DR applies the same change. A reviewer's edit of an
operation (#1383) applies the corrected triple, refused by the DR rules when the
classes, predicate or triple don't hold, and the export reports what was applied.

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
from adapters.interchange.dr_relationships import (
    DR_TAXONOMY_IDENTIFIER,
    DrRelationshipRules,
    dr_predicate_catalog,
)
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
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


def spec_with_catalog(spec):
    """
    Copy the pinned spec to `spec` with its predicate catalog as dist/base.json.

    The 0.8.4 snapshot predates dist/base.json; its catalog is the same set of
    entries, in schemas/base/predicates.json, so the dist file is built from it.
    """
    shutil.copytree(pinned_dr_spec_dir(), spec)
    catalog = json.loads((spec / "schemas" / "base" / "predicates.json").read_text())
    base = {"specVersion": "0.8.4", "predicates": catalog["predicates"]}
    (spec / "dist" / "base.json").write_text(json.dumps(base))
    return spec


@pytest.fixture(scope="module")
def spec_db():
    """A database with the pinned DR spec imported, built once and copied per test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "spec.db"
        engine = create_local_db_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        repo = SQLiteOntologyRepository(session_factory=sessionmaker(bind=engine))
        service = OntologyService(repo, FakeEmbeddingService(), InProcessEventPublisher())
        import_dr_ontology(service, repo, spec_with_catalog(Path(tmpdir) / "spec"))
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
        apply_rules=[DrRelationshipRules(repo)],  # as app.py wires it
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
    spec = spec_with_catalog(tmp_path / "spec")
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


# ----------------------------------------------------------- accept with edit (#1383)

MEDIATYPE_AGGREGATES = "api.mediatype.aggregates.api.encoding"  # seq 1, a delete


def edit_triple(repo, source=None, predicate=None, destination=None, **fields):
    """An edit in Context Studio fields, the way the review UI builds it from DR's triple."""
    if source is not None:
        fields["domain_class_id"] = class_by_dr_id(repo, source).id
    if destination is not None:
        fields["range_class_id"] = class_by_dr_id(repo, destination).id
    if predicate is not None:
        fields["canonical_predicate"] = predicate
    return fields


def test_an_edited_rename_applies_the_reviewers_triple(parts):
    _, repo, proposals = parts
    new_id = "api.operation.uses.api.response"
    assert prop_by_dr_id(repo, new_id) is None
    proposal = import_reflection_plan(plan_for(14), proposals, repo)  # delivers -> aggregates
    op = proposal.operations[0]
    delivers = repo.get_property_definition(op.target_id)

    applied = proposals.apply(
        proposal.id, [op.id], edits={op.id: edit_triple(repo, predicate="uses")}
    ).operations[0]

    assert applied.status is OperationStatus.APPLIED, applied.reason
    prop = repo.get_property_definition(delivers.id)
    assert prop_by_dr_id(repo, new_id).id == delivers.id
    assert prop.canonical_predicate == "uses" and prop.identifier == "operation_uses_response"
    assert prop.title == "api.operation uses api.response"  # the default title follows
    assert prop.domain_class_id == delivers.domain_class_id
    assert prop.range_class_id == delivers.range_class_id
    stored = proposals.get(proposal.id).operations[0]
    assert stored.applied_fields == {
        "canonical_predicate": "uses",
        "domain_class_id": delivers.domain_class_id,
        "range_class_id": delivers.range_class_id,
        "identifier": "operation_uses_response",
        "title": "api.operation uses api.response",
        "external_references": [
            {"source": DR_SOURCE, "identifier": new_id, "uri": None, "metadata": None}
        ],
    }
    assert stored.fields["canonical_predicate"] == "aggregates"  # the proposal is kept
    assert stored.scope is ChangeScope.BREAKING


def test_a_delete_replaced_by_a_triple_applies_as_an_update(parts):
    _, repo, proposals = parts
    new_id = "api.mediatype.aggregates.api.header"
    assert prop_by_dr_id(repo, new_id) is None
    proposal = import_reflection_plan(plan_for(1), proposals, repo)
    op = proposal.operations[0]
    target = prop_by_dr_id(repo, MEDIATYPE_AGGREGATES)

    edit = edit_triple(repo, destination="api.header", title="Media type headers")
    applied = proposals.apply(proposal.id, [op.id], edits={op.id: edit}).operations[0]

    assert applied.status is OperationStatus.APPLIED, applied.reason
    assert (applied.seq, applied.op) == (1, OperationType.DELETE)
    assert applied.result_entity_id == target.id
    prop = repo.get_property_definition(target.id)
    assert prop is not None and prop_by_dr_id(repo, MEDIATYPE_AGGREGATES) is None
    assert prop_by_dr_id(repo, new_id).id == target.id
    assert prop.title == "Media type headers"
    assert prop.range_class_id == class_by_dr_id(repo, "api.header").id
    assert prop.identifier == "mediatype_aggregates_header"


def test_an_edit_keeping_the_triple_carries_it_whole(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(1), proposals, repo)
    op = proposal.operations[0]
    target = prop_by_dr_id(repo, MEDIATYPE_AGGREGATES)

    applied = proposals.apply(
        proposal.id, [op.id], edits={op.id: {"description": "Kept, reworded"}}
    ).operations[0]

    assert applied.status is OperationStatus.APPLIED, applied.reason
    assert applied.applied_fields["identifier"] == target.identifier
    assert applied.scope is ChangeScope.EDITORIAL
    [decision] = decisions_for(proposals.get(proposal.id))
    assert decision["fields"] == {
        "predicate": "aggregates",
        "source_spec_node_id": "api.mediatype",
        "destination_spec_node_id": "api.encoding",
    }


@pytest.mark.parametrize(
    "edit, reason",
    [
        (
            {"source": "api.response", "predicate": "frobnicates"},
            "invalid_edit: predicate 'frobnicates' is not in the DR predicate catalog",
        ),
        (
            {"source": "api.components", "predicate": "aggregates"},
            "invalid_edit: api.components.aggregates.api.response already exists",
        ),
    ],
)
def test_an_edit_the_dr_spec_refuses_fails_only_that_operation(parts, edit, reason):
    _, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(13, 14), proposals, repo)
    ops = {o.seq: o for o in proposal.operations}
    before = snap(repo.get_property_definition(ops[14].target_id))

    result = proposals.apply(
        proposal.id, [ops[13].id, ops[14].id], edits={ops[14].id: edit_triple(repo, **edit)}
    )

    by_seq = {o.seq: o for o in result.operations}
    assert by_seq[14].status is OperationStatus.FAILED
    assert by_seq[14].reason == reason
    assert by_seq[14].applied_fields is None
    assert snap(repo.get_property_definition(ops[14].target_id)) == before
    assert by_seq[13].status is OperationStatus.APPLIED


def test_the_import_stores_the_predicate_catalog_on_the_taxonomy(parts):
    _, repo, _ = parts
    catalog = dr_predicate_catalog(repo)

    assert len(catalog) == 70
    assert catalog["owns"] == {
        "inverse": "owned-by",
        "category": "business",
        "description": "Element has responsibility or authority over another element",
    }
    used = {p.canonical_predicate for p in repo.list_property_definitions(limit=None)}
    assert "owns" not in used  # in the catalog, used by no relationship type


def test_a_reimport_keeps_one_catalog(parts, tmp_path):
    ontology, repo, _ = parts
    import_dr_ontology(ontology, repo, spec_with_catalog(tmp_path / "spec"))

    refs = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER).external_references
    assert [(r.source, r.identifier) for r in refs] == [(DR_SOURCE, "spec")]
    assert refs[0].metadata["spec_version"] == "0.8.4"
    assert len(dr_predicate_catalog(repo)) == 70


def test_an_edit_to_a_catalog_predicate_no_type_uses_applies(parts):
    _, repo, proposals = parts
    new_id = "api.operation.owns.api.response"
    proposal = import_reflection_plan(plan_for(14), proposals, repo)
    op = proposal.operations[0]

    applied = proposals.apply(
        proposal.id, [op.id], edits={op.id: edit_triple(repo, predicate="owns")}
    ).operations[0]

    assert applied.status is OperationStatus.APPLIED, applied.reason
    assert prop_by_dr_id(repo, new_id).canonical_predicate == "owns"
    [decision] = decisions_for(proposals.get(proposal.id))
    assert decision["fields"]["predicate"] == "owns"


def test_an_edit_without_a_stored_catalog_is_refused_clearly(parts):
    """An import from before the catalog was stored (or of a spec without one)."""
    _, repo, proposals = parts
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    taxonomy.external_references = []
    repo.save_taxonomy(taxonomy)
    proposal = import_reflection_plan(plan_for(14), proposals, repo)
    op = proposal.operations[0]

    result = proposals.apply(
        proposal.id, [op.id], edits={op.id: edit_triple(repo, predicate="uses")}
    ).operations[0]

    assert result.status is OperationStatus.FAILED
    assert result.reason == (
        "invalid_edit: the DR spec was imported without its predicate catalog; re-import "
        "the DR spec to load it"
    )
    assert prop_by_dr_id(repo, "api.operation.delivers.api.response") is not None


def house_proposal(ontology, proposals, *drafts):
    """A proposal on another taxonomy: property definitions are global."""
    house = ontology.create_taxonomy(title="House", identifier="house")
    return proposals.propose(house.id, "From the house", list(drafts), ProposalSource.USER)


def test_dr_rules_govern_a_dr_type_whatever_the_proposals_taxonomy(parts):
    ontology, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    proposal = house_proposal(
        ontology,
        proposals,
        OperationDraft(
            seq=1, op="update", kind="property", target_id=delivers.id, fields={"title": "delivers"}
        ),
    )
    op = proposal.operations[0]

    result = proposals.apply(
        proposal.id, [op.id], edits={op.id: {"canonical_predicate": "frobnicates"}}
    ).operations[0]

    assert result.status is OperationStatus.FAILED
    assert (
        result.reason == "invalid_edit: predicate 'frobnicates' is not in the DR predicate catalog"
    )
    assert repo.get_property_definition(delivers.id).canonical_predicate == "delivers"


def test_an_edit_pointing_a_non_dr_type_into_the_dr_spec_is_refused(parts):
    ontology, repo, proposals = parts
    near = ontology.create_property_definition("near", "near")
    proposal = house_proposal(
        ontology,
        proposals,
        OperationDraft(
            seq=1, op="update", kind="property", target_id=near.id, fields={"title": "near by"}
        ),
    )
    op = proposal.operations[0]

    result = proposals.apply(
        proposal.id, [op.id], edits={op.id: edit_triple(repo, source="api.operation")}
    ).operations[0]

    assert result.status is OperationStatus.FAILED
    assert result.reason == "invalid_edit: near has no DR relationship id"
    assert repo.get_property_definition(near.id).domain_class_id is None


def test_an_edit_onto_a_class_outside_the_dr_spec_fails(parts):
    ontology, repo, proposals = parts
    house = ontology.create_taxonomy(title="House")
    rooms = ontology.create_scheme(taxonomy_id=house.id, title="Rooms")
    kitchen = ontology.create_class(rooms.id, "Kitchen")
    proposal = import_reflection_plan(plan_for(14), proposals, repo)
    op = proposal.operations[0]

    result = proposals.apply(
        proposal.id, [op.id], edits={op.id: {"domain_class_id": kitchen.id}}
    ).operations[0]

    assert result.status is OperationStatus.FAILED
    assert result.reason == (
        f"invalid_edit: domain_class_id '{kitchen.id}' is not an imported DR spec class"
    )


def test_an_edit_onto_a_triple_another_operation_proposes_fails(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(1, 14), proposals, repo)  # 14 -> aggregates
    ops = {o.seq: o for o in proposal.operations}
    edit = edit_triple(repo, source="api.operation", destination="api.response")

    result = proposals.apply(proposal.id, [ops[1].id], edits={ops[1].id: edit})

    failed = next(o for o in result.operations if o.seq == 1)
    assert failed.status is OperationStatus.FAILED
    assert failed.reason == (
        "invalid_edit: seq 14 also produces api.operation.aggregates.api.response"
    )
    assert prop_by_dr_id(repo, MEDIATYPE_AGGREGATES) is not None


def test_two_edits_producing_one_triple_both_fail(parts):
    _, repo, proposals = parts
    new_id = "api.tag.governs.api.ratelimit"
    assert prop_by_dr_id(repo, new_id) is None
    proposal = import_reflection_plan(plan_for(1, 2), proposals, repo)
    ops = {o.seq: o for o in proposal.operations}
    edit = edit_triple(repo, source="api.tag", predicate="governs", destination="api.ratelimit")

    result = proposals.apply(
        proposal.id, [ops[1].id, ops[2].id], edits={ops[1].id: edit, ops[2].id: edit}
    )

    by_seq = {o.seq: o for o in result.operations}
    assert by_seq[1].reason == f"invalid_edit: seq 2 also produces {new_id}"
    assert by_seq[2].reason == f"invalid_edit: seq 1 also produces {new_id}"
    assert prop_by_dr_id(repo, new_id) is None


def test_revert_of_an_edited_apply_restores_exactly(parts):
    ontology, repo, proposals = parts
    delivers, rel_ids = put_delivers_in_use(ontology, repo)
    proposal = import_reflection_plan(plan_for(1, 14), proposals, repo)
    ops = {o.seq: o for o in proposal.operations}
    targets = [ops[1].target_id, ops[14].target_id]
    before = {t: snap(repo.get_property_definition(t)) for t in targets}
    rels_before = {r: snap(repo.get_relationship(r)) for r in rel_ids}
    edits = {
        ops[1].id: edit_triple(repo, destination="api.header"),
        ops[14].id: edit_triple(repo, predicate="uses"),
    }

    applied = proposals.apply(proposal.id, [ops[1].id, ops[14].id], edits=edits)
    assert all(o.status is OperationStatus.APPLIED for o in applied.operations), [
        o.reason for o in applied.operations
    ]
    assert repo.get_property_definition(delivers.id).canonical_predicate == "uses"

    proposals.revert(proposal.id)

    assert {t: snap(repo.get_property_definition(t)) for t in targets} == before
    assert {r: snap(repo.get_relationship(r)) for r in rel_ids} == rels_before
    assert proposals.get(proposal.id).status is ProposalStatus.REVERTED


def test_decisions_export_reports_what_was_applied(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(1, 2, 13, 14), proposals, repo)
    ops = {o.seq: o for o in proposal.operations}
    edits = {
        ops[1].id: edit_triple(repo, destination="api.header"),
        ops[14].id: edit_triple(repo, predicate="uses"),
    }
    proposals.apply(proposal.id, [ops[1].id, ops[2].id, ops[14].id], edits=edits)
    proposals.reject(proposal.id, [ops[13].id], note="Keep references")

    decisions = {d["seq"]: d for d in decisions_for(proposals.get(proposal.id))}

    assert decisions[1] == {
        "seq": 1,
        "op_id": ops[1].id,
        "status": "applied",
        "fields": {
            "predicate": "aggregates",
            "source_spec_node_id": "api.mediatype",
            "destination_spec_node_id": "api.header",
        },
        "reason": None,
        "result_entity_id": ops[1].target_id,
    }
    assert decisions[14]["fields"] == {
        "predicate": "uses",
        "source_spec_node_id": "api.operation",
        "destination_spec_node_id": "api.response",
    }
    assert "fields" not in decisions[2] and decisions[2]["status"] == "applied"
    assert "fields" not in decisions[13] and decisions[13]["status"] == "rejected"
    json.dumps(list(decisions.values()))


def test_a_failed_edit_exports_as_failed_without_fields(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(plan_for(14), proposals, repo)
    op = proposal.operations[0]
    proposals.apply(proposal.id, [op.id], edits={op.id: edit_triple(repo, predicate="nope")})

    [decision] = decisions_for(proposals.get(proposal.id))

    assert decision["status"] == "failed" and "fields" not in decision
    assert decision["reason"] == "invalid_edit: predicate 'nope' is not in the DR predicate catalog"


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


def test_a_spec_with_an_unknown_node_fails_before_any_identifier_moves(parts, tmp_path):
    """The rename puts the twin's identifier on the move; a bad record must stop that first."""
    ontology, repo, proposals = parts
    old, new = "ux.view.serves.business.businessrole", "ux.view.realizes.api.response"
    proposal = import_reflection_plan(plan_with(rename(1, old, new)), proposals, repo)
    assert apply_all(proposals, proposal).operations[0].status is OperationStatus.APPLIED
    spec = spec_after(tmp_path, {old: new})
    broken = sorted((spec / "schemas" / "relationships").glob("*/*.relationship.schema.json"))[-1]
    data = json.loads(broken.read_text())
    data["properties"]["source_spec_node_id"]["const"] = "testing.nosuchnode"
    broken.write_text(json.dumps(data))
    before = {p.id: p.identifier for p in repo.list_property_definitions(limit=None)}

    with pytest.raises(ValueError, match="testing.nosuchnode"):
        import_dr_ontology(ontology, repo, spec)

    assert {p.id: p.identifier for p in repo.list_property_definitions(limit=None)} == before
