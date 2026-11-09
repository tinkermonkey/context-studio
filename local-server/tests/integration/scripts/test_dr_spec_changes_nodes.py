"""
Integration tests (#1462): a decided proposal's applied class operations on the
DR spec export as node type changes in `cs-dr-spec-changes/1` (`node_changes`),
each keyed by its DR spec node id, with `rename-type` records for the moves and
replaced deletes a model migration can follow.

Built on the pinned DR spec snapshot (0.8.4), as test_dr_spec_changes.py is.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from adapters.interchange.dr_spec_changes import spec_changes_for
from domain.ontology.value_objects import ExternalReference
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import OperationStatus, ProposalSource
from scripts.dr_ontology_loader import DR_SOURCE, DR_TAXONOMY_IDENTIFIER
from tests.integration.scripts import test_dr_reflection_plan as plan_tests
from tests.integration.scripts.test_dr_reflection_plan import class_by_dr_id

spec_db = plan_tests.spec_db
parts = plan_tests.parts


def dr_ref(spec_node_id):
    return {"source": DR_SOURCE, "identifier": spec_node_id}


def propose(repo, proposals, *drafts):
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    return proposals.propose(taxonomy.id, "Node type changes", list(drafts), ProposalSource.MCP)


def apply_all(proposals, proposal):
    applied = proposals.apply(proposal.id, [o.id for o in proposal.operations])
    for operation in applied.operations:
        assert operation.status is OperationStatus.APPLIED, operation.reason
    return applied


def scheme_of(repo, layer):
    return repo.get_by_identifier(layer.replace("-", "_"))


def unused_class(parts, layer, type_name="spare"):
    """An imported DR node type of the layer that nothing uses, so a delete can apply."""
    ontology, repo, _ = parts
    cls = ontology.create_class(
        concept_scheme_id=scheme_of(repo, layer).id,
        title=type_name.title(),
        identifier=f"{layer}_{type_name}".replace("-", "_"),
    )
    cls.external_references = [
        ExternalReference(source=DR_SOURCE, identifier=f"{layer}.{type_name}")
    ]
    return repo.save_class(cls)


def create(repo, seq, layer, type_name, ref=None, **fields):
    return OperationDraft(
        seq=seq,
        op="create",
        kind="class",
        ref=ref,
        fields={
            "concept_scheme_id": scheme_of(repo, layer).id,
            "title": fields.pop("title", type_name.title()),
            "identifier": f"{layer}_{type_name}".replace("-", "_"),
            "external_references": [dr_ref(f"{layer}.{type_name}")],
            **fields,
        },
    )


def test_a_create_exports_its_node_id_layer_title_and_description(parts):
    _, repo, proposals = parts
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            create(repo, 1, "business", "businesscapability", description="What it can do."),
        ),
    )
    recorded = proposals.decisions_of(proposal.id)

    document = spec_changes_for(proposal, repo, recorded)

    operation = proposal.operations[0]
    assert document["changes"] == []
    assert document["skipped"] == []
    assert document["node_changes"] == [
        {
            "seq": 1,
            "op_id": operation.id,
            "op": "create",
            "spec_node_id": "business.businesscapability",
            "layer_id": "business",
            "identifier": "business_businesscapability",
            "set": {"title": "Businesscapability", "description": "What it can do."},
            "decided_at": recorded[operation.id].decided_at.isoformat(),
            "decided_by": "user",
        }
    ]
    assert document["records"] == []


def test_a_create_without_a_dr_reference_in_a_dr_layer_is_refused(parts):
    _, repo, proposals = parts
    draft = create(repo, 1, "business", "orphan")
    draft.fields.pop("external_references")
    proposal = apply_all(proposals, propose(repo, proposals, draft))

    with pytest.raises(ValueError, match="without a DR reference"):
        spec_changes_for(proposal, repo)


def test_a_create_whose_node_id_is_in_another_layer_is_refused(parts):
    _, repo, proposals = parts
    draft = create(repo, 1, "business", "misfiled")
    draft.fields["external_references"] = [dr_ref("api.misfiled")]
    proposal = apply_all(proposals, propose(repo, proposals, draft))

    with pytest.raises(ValueError, match="not 'business.<type>'"):
        spec_changes_for(proposal, repo)


def test_an_update_exports_only_the_title_and_description_it_changed(parts):
    _, repo, proposals = parts
    operation_class = class_by_dr_id(repo, "api.operation")
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1,
                op="update",
                kind="class",
                target_id=operation_class.id,
                fields={
                    "title": operation_class.title,  # unchanged
                    "description": "One HTTP method on one path.",
                },
            ),
        ),
    )

    (change,) = spec_changes_for(proposal, repo)["node_changes"]

    assert change["op"] == "update"
    assert change["spec_node_id"] == "api.operation"
    assert change["layer_id"] == "api"
    assert change["identifier"] == operation_class.identifier
    assert change["set"] == {"description": "One HTTP method on one path."}


def test_an_update_of_nothing_dr_holds_is_skipped(parts):
    _, repo, proposals = parts
    target = class_by_dr_id(repo, "api.operation")
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1, op="update", kind="class", target_id=target.id, fields={"color": "#aabbcc"}
            ),
        ),
    )

    document = spec_changes_for(proposal, repo)

    assert document["node_changes"] == []
    assert document["skipped"] == [
        {
            "seq": 1,
            "op_id": proposal.operations[0].id,
            "why": "it changes nothing DR's spec holds for a node type",
        }
    ]


def test_an_update_that_changes_the_dr_id_is_refused(parts):
    _, repo, proposals = parts
    target = class_by_dr_id(repo, "api.operation")
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1,
                op="update",
                kind="class",
                target_id=target.id,
                fields={"external_references": [dr_ref("api.endpoint")]},
            ),
        ),
    )

    with pytest.raises(ValueError, match="changed the class's DR id"):
        spec_changes_for(proposal, repo)


def test_a_move_to_another_scheme_moves_the_node_type_to_that_layer(parts):
    _, repo, proposals = parts
    target = class_by_dr_id(repo, "motivation.goal")
    type_name = next(
        r.identifier for r in target.external_references if r.source == DR_SOURCE
    ).split(".")[1]
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1,
                op="move",
                kind="class",
                target_id=target.id,
                fields={
                    "concept_scheme_id": scheme_of(repo, "business").id,
                    "parent_class_id": None,
                },
                probability=0.8,
            ),
        ),
    )
    recorded = proposals.decisions_of(proposal.id)

    document = spec_changes_for(proposal, repo, recorded)

    operation = proposal.operations[0]
    (change,) = document["node_changes"]
    assert change["op"] == "move"
    assert change["spec_node_id"] == f"business.{type_name}"
    assert change["previous_spec_node_id"] == f"motivation.{type_name}"
    assert change["layer_id"] == "business"
    assert change["set"] == {}
    assert document["records"] == [
        {
            "action": "rename-type",
            "kind": "cs:move",
            "from": f"motivation.{type_name}",
            "to": f"business.{type_name}",
            "swap": False,
            "p": 0.8,
            "proposal_id": proposal.id,
            "operation_id": operation.id,
            "applied_at": recorded[operation.id].decided_at.isoformat(),
        }
    ]


def test_a_parent_only_move_is_skipped(parts):
    _, repo, proposals = parts
    child = unused_class(parts, "business")
    parent = class_by_dr_id(repo, "business.businessactor")
    assert child.id != parent.id
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1,
                op="move",
                kind="class",
                target_id=child.id,
                fields={"parent_class_id": parent.id},
            ),
        ),
    )

    document = spec_changes_for(proposal, repo)

    assert document["node_changes"] == []
    assert document["skipped"][0]["why"] == (
        "a parent class move; DR's spec has no class hierarchy"
    )


def test_a_delete_names_its_replacement_and_records_a_type_rename(parts):
    _, repo, proposals = parts
    target = unused_class(parts, "business")
    node_id = next(r.identifier for r in target.external_references if r.source == DR_SOURCE)
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            create(repo, 1, "business", "businesscapability", ref="split"),
            OperationDraft(
                seq=2, op="delete", kind="class", target_id=target.id, replacement="$split"
            ),
        ),
    )
    recorded = proposals.decisions_of(proposal.id)

    document = spec_changes_for(proposal, repo, recorded)

    delete = proposal.operations[1]
    created, deleted = document["node_changes"]
    assert created["op"] == "create"
    assert deleted == {
        "seq": 2,
        "op_id": delete.id,
        "op": "delete",
        "spec_node_id": node_id,
        "layer_id": "business",
        "identifier": target.identifier,
        "set": {},
        "replacement_spec_node_id": "business.businesscapability",
        "decided_at": recorded[delete.id].decided_at.isoformat(),
        "decided_by": "user",
    }
    assert [(r["action"], r["kind"], r["from"], r["to"]) for r in document["records"]] == [
        ("rename-type", "cs:delete", node_id, "business.businesscapability")
    ]


def test_a_delete_without_a_replacement_has_no_record(parts):
    _, repo, proposals = parts
    target = unused_class(parts, "business")
    proposal = apply_all(
        proposals,
        propose(
            repo, proposals, OperationDraft(seq=1, op="delete", kind="class", target_id=target.id)
        ),
    )

    document = spec_changes_for(proposal, repo)

    (change,) = document["node_changes"]
    assert change["op"] == "delete"
    assert "replacement_spec_node_id" not in change
    assert document["records"] == []


def test_a_class_delete_can_name_a_replacement_by_identifier(parts):
    _, repo, proposals = parts
    target = unused_class(parts, "business")
    replacement = class_by_dr_id(repo, "business.businessactor")
    proposal = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1,
            op="delete",
            kind="class",
            target_id=target.id,
            replacement=replacement.identifier,
        ),
    )

    assert proposal.operations[0].proposed_replacement_id == replacement.id


@pytest.mark.parametrize(
    "replacement, why",
    [("$nothing", "names no create"), ("not_a_class", "not the id or identifier of a class")],
)
def test_a_class_delete_refuses_a_replacement_that_is_no_class(parts, replacement, why):
    _, repo, proposals = parts
    target = unused_class(parts, "business")
    with pytest.raises(ProposalValidationError, match=why):
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1, op="delete", kind="class", target_id=target.id, replacement=replacement
            ),
        )


def test_operations_on_other_kinds_are_skipped_as_neither_type(parts):
    _, repo, proposals = parts
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    proposal = apply_all(
        proposals,
        propose(
            repo,
            proposals,
            OperationDraft(
                seq=1,
                op="update",
                kind="taxonomy",
                target_id=taxonomy.id,
                fields={"color": "#112233"},
            ),
        ),
    )

    (skipped,) = spec_changes_for(proposal, repo)["skipped"]
    assert skipped["why"] == "a taxonomy operation, not a relationship or node type"


def test_a_class_delete_fails_while_relationship_types_still_use_it(parts):
    """DR refuses a node type delete that leaves relationship schemas naming it."""
    _, repo, proposals = parts
    goal = class_by_dr_id(repo, "motivation.goal")
    proposal = propose(
        repo, proposals, OperationDraft(seq=1, op="delete", kind="class", target_id=goal.id)
    )

    applied = proposals.apply(proposal.id, [proposal.operations[0].id])

    assert applied.operations[0].status is OperationStatus.FAILED
    assert repo.get_class(goal.id) is not None
    assert spec_changes_for(applied, repo)["node_changes"] == []
