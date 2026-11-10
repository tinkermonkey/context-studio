"""
Integration tests (#1397): any decided proposal on DR relationship types exports
its applied creates, updates and deletes, with the values applied: the DR
attributes (strength, evidence) kept on the DR reference, and the cardinality
from the type's structure fields (#1482), for DR to write into its spec
(`cs-dr-spec-changes/1`).

Built on the pinned DR spec snapshot (0.8.4), as test_dr_reflection_plan.py is.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from adapters.interchange.dr_relationships import dr_cardinality
from adapters.interchange.dr_spec import iter_relationship_schemas
from adapters.interchange.dr_spec_changes import spec_changes_for
from domain.ontology.value_objects import SourceRevision
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import (
    InUseResolution,
    OperationStatus,
    ProposalSource,
    ResolutionStrategy,
)
from scripts.dr_ontology_loader import DR_SOURCE, DR_TAXONOMY_IDENTIFIER
from tests.integration.pipelines._harness.dr_spec import pinned_dr_spec_dir
from tests.integration.scripts import test_dr_reflection_plan as plan_tests
from tests.integration.scripts.test_dr_reflection_plan import (
    DELIVERS,
    SPEC_ATTRIBUTES,
    class_by_dr_id,
    prop_by_dr_id,
    put_delivers_in_use,
)

# The pinned-spec database fixtures, shared with the reflection-plan tests.
spec_db = plan_tests.spec_db
parts = plan_tests.parts

NEW = "api.response.references.api.operation"
RENAMED = "api.operation.uses.api.response"
EVIDENCE = ["The operation's spec lists the response under its responses."]


def dr_ref(relationship_id, **metadata):
    return {"source": DR_SOURCE, "identifier": relationship_id, "metadata": metadata or None}


def propose(repo, proposals, *drafts):
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    return proposals.propose(taxonomy.id, "Spec changes", list(drafts), ProposalSource.MCP)


def apply_all(proposals, proposal, **kwargs):
    return proposals.apply(proposal.id, [o.id for o in proposal.operations], **kwargs)


def create_new(repo):
    return OperationDraft(
        seq=1,
        op="create",
        kind="property",
        fields={
            "identifier": "response_references_operation",
            "title": "api.response references api.operation",
            "canonical_predicate": "references",
            "description": "The response names the operation it answers.",
            "domain_class_id": class_by_dr_id(repo, "api.response").id,
            "range_class_id": class_by_dr_id(repo, "api.operation").id,
            "external_references": [dr_ref(NEW, strength="medium", evidence=EVIDENCE)],
        },
    )


def test_a_create_exports_every_value_it_applied(parts):
    _, repo, proposals = parts
    assert prop_by_dr_id(repo, NEW) is None
    proposal = apply_all(proposals, propose(repo, proposals, create_new(repo)))
    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason

    recorded = proposals.decisions_of(proposal.id)
    document = spec_changes_for(proposal, repo, recorded)

    assert document["format"] == "cs-dr-spec-changes/1"
    assert document["proposal_id"] == proposal.id
    assert document["skipped"] == []
    assert document["changes"] == [
        {
            "seq": 1,
            "op_id": proposal.operations[0].id,
            "op": "create",
            "relationship_id": NEW,
            "identifier": "response_references_operation",
            "predicate": "references",
            "source_spec_node_id": "api.response",
            "destination_spec_node_id": "api.operation",
            "set": {
                "description": "The response names the operation it answers.",
                "cardinality": "many-to-many",
                "strength": "medium",
                "evidence": EVIDENCE,
            },
            "decided_at": recorded[proposal.operations[0].id].decided_at.isoformat(),
            "decided_by": "user",
        }
    ]


def test_an_update_exports_only_what_it_changed(parts):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    proposal = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1,
            op="update",
            kind="property",
            target_id=delivers.id,
            fields={
                "description": "The operation returns the response.",
                # Resent whole: only the evidence is new.
                "external_references": [dr_ref(DELIVERS, **SPEC_ATTRIBUTES, evidence=EVIDENCE)],
            },
        ),
    )
    proposal = apply_all(proposals, proposal)

    (change,) = spec_changes_for(proposal, repo)["changes"]

    assert change["op"] == "update"
    assert change["relationship_id"] == DELIVERS
    assert "previous_relationship_id" not in change
    assert change["identifier"] == delivers.identifier
    assert change["set"] == {
        "description": "The operation returns the response.",
        "evidence": EVIDENCE,
    }


def test_an_update_that_drops_the_evidence_exports_it_empty(parts):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    with_evidence = [dr_ref(DELIVERS, **SPEC_ATTRIBUTES, evidence=EVIDENCE)]
    first = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1,
            op="update",
            kind="property",
            target_id=delivers.id,
            fields={"external_references": with_evidence},
        ),
    )
    apply_all(proposals, first)
    second = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1,
            op="update",
            kind="property",
            target_id=delivers.id,
            fields={"external_references": [dr_ref(DELIVERS)], "max_per_target": 1},
        ),
    )

    (change,) = spec_changes_for(apply_all(proposals, second), repo)["changes"]

    assert change["set"] == {"cardinality": "one-to-many", "strength": None, "evidence": []}


def test_an_edited_rename_exports_the_new_triple_and_keeps_the_attributes(parts):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    proposal = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1, op="update", kind="property", target_id=delivers.id, fields={"title": "x"}
        ),
    )
    op = proposal.operations[0]
    edit = {
        "canonical_predicate": "uses",
        "max_per_target": 1,
        "external_references": [dr_ref(DELIVERS, strength="high")],
    }

    proposal = proposals.apply(proposal.id, [op.id], edits={op.id: edit})
    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason

    (change,) = spec_changes_for(proposal, repo)["changes"]
    assert change["relationship_id"] == RENAMED
    assert change["previous_relationship_id"] == DELIVERS
    assert change["predicate"] == "uses"
    assert change["identifier"] == "operation_uses_response"
    # The edit's attributes were applied; the generated default description is not exported.
    assert change["set"] == {"cardinality": "one-to-many", "strength": "high"}
    renamed = prop_by_dr_id(repo, RENAMED)
    assert dict(renamed.external_references[0].metadata) == {"strength": "high"}
    assert (renamed.max_per_source, renamed.max_per_target) == (None, 1)


ONE_TO_ONE = "api.securityscheme.composes.api.oauthflows"  # the pinned spec's one-to-one
SELF_TYPE = "api.schema.references.api.schema"  # same domain and range


def update(target, **fields):
    return OperationDraft(seq=1, op="update", kind="property", target_id=target.id, fields=fields)


def test_the_imported_cardinality_maps_back_to_the_spec_unchanged(parts):
    """#1482 done-when: an import and export round trip keeps every cardinality."""
    _, repo, _ = parts

    for record in iter_relationship_schemas(pinned_dr_spec_dir()):
        prop = prop_by_dr_id(repo, record.full_identifier)
        assert dr_cardinality(prop) == record.cardinality, record.full_identifier
        dr_metadata = dict(prop.external_references[0].metadata or {})
        assert "cardinality" not in dr_metadata


def test_a_create_exports_the_cardinality_of_its_structure_fields(parts):
    _, repo, proposals = parts
    create = create_new(repo)
    create.fields["max_per_source"] = 1
    proposal = apply_all(proposals, propose(repo, proposals, create))
    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason

    (change,) = spec_changes_for(proposal, repo)["changes"]

    assert change["set"]["cardinality"] == "many-to-one"
    assert (prop_by_dr_id(repo, NEW).max_per_source, prop_by_dr_id(repo, NEW).max_per_target) == (
        1,
        None,
    )


def test_an_update_exports_the_cardinality_only_when_the_numbers_changed(parts):
    _, repo, proposals = parts
    one_to_one = prop_by_dr_id(repo, ONE_TO_ONE)
    same = apply_all(
        proposals,
        propose(repo, proposals, update(one_to_one, description="Flows.", max_per_source=1)),
    )
    (change,) = spec_changes_for(same, repo)["changes"]
    assert change["set"] == {"description": "Flows."}

    changed = apply_all(
        proposals, propose(repo, proposals, update(one_to_one, max_per_target=None))
    )
    (change,) = spec_changes_for(changed, repo)["changes"]
    assert change["set"] == {"cardinality": "many-to-one"}


def test_hierarchy_and_symmetric_are_left_alone_and_not_exported(parts):
    _, repo, proposals = parts
    self_type = prop_by_dr_id(repo, SELF_TYPE)
    proposal = apply_all(
        proposals, propose(repo, proposals, update(self_type, hierarchy=True, symmetric=True))
    )
    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason

    (change,) = spec_changes_for(proposal, repo)["changes"]
    assert change["set"] == {}


@pytest.mark.parametrize(
    "structure",
    [{"min_per_source": 2}, {"min_per_source": 1}, {"max_per_target": 3}],
)
def test_structure_dr_cannot_express_is_refused_on_a_dr_type(parts, structure):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)

    proposal = apply_all(proposals, propose(repo, proposals, update(delivers, **structure)))

    op = proposal.operations[0]
    assert op.status is OperationStatus.FAILED
    assert "DR's spec can't express" in op.reason
    assert "many-to-many, many-to-one, one-to-many or one-to-one" in op.reason
    assert dr_cardinality(prop_by_dr_id(repo, DELIVERS)) == "many-to-many"


def test_a_create_or_edit_dr_cannot_express_is_refused(parts):
    _, repo, proposals = parts
    create = create_new(repo)
    create.fields["min_per_source"] = 2
    created = apply_all(proposals, propose(repo, proposals, create))
    assert created.operations[0].status is OperationStatus.FAILED
    assert "DR's spec can't express min_per_source 2" in created.operations[0].reason

    delivers = prop_by_dr_id(repo, DELIVERS)
    proposal = propose(repo, proposals, update(delivers, title="x"))
    op = proposal.operations[0]
    edited = proposals.apply(proposal.id, [op.id], edits={op.id: {"max_per_source": 2}})
    assert edited.operations[0].status is OperationStatus.FAILED
    assert "DR's spec can't express" in edited.operations[0].reason


def test_a_resolved_delete_names_the_replacement(parts):
    ontology, repo, proposals = parts
    delivers, _ = put_delivers_in_use(ontology, repo)
    uses = OperationDraft(
        seq=1,
        op="create",
        kind="property",
        fields={
            "identifier": "operation_uses_response",
            "title": "api.operation uses api.response",
            "canonical_predicate": "uses",
            "domain_class_id": delivers.domain_class_id,
            "range_class_id": delivers.range_class_id,
            "external_references": [dr_ref(RENAMED)],
        },
    )
    apply_all(proposals, propose(repo, proposals, uses))
    replacement = prop_by_dr_id(repo, RENAMED)
    proposal = propose(
        repo,
        proposals,
        OperationDraft(seq=1, op="delete", kind="property", target_id=delivers.id),
    )
    op = proposal.operations[0]

    proposal = proposals.apply(
        proposal.id,
        [op.id],
        resolutions={
            op.id: InUseResolution(
                strategy=ResolutionStrategy.MOVE, replacement_property_id=replacement.id
            )
        },
    )
    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason

    (change,) = spec_changes_for(proposal, repo)["changes"]
    assert change == {
        "seq": 1,
        "op_id": op.id,
        "op": "delete",
        "relationship_id": DELIVERS,
        "identifier": delivers.identifier,
        "predicate": "delivers",
        "source_spec_node_id": "api.operation",
        "destination_spec_node_id": "api.response",
        "set": {},
        "replacement_relationship_id": RENAMED,
        "decided_at": None,  # no decisions passed
        "decided_by": None,
    }


def uses_create(delivers, seq=1):
    """A create of api.operation uses api.response, the pair delivers links."""
    return OperationDraft(
        seq=seq,
        op="create",
        kind="property",
        ref="uses",
        fields={
            "identifier": "operation_uses_response",
            "title": "api.operation uses api.response",
            "canonical_predicate": "uses",
            "domain_class_id": delivers.domain_class_id,
            "range_class_id": delivers.range_class_id,
            "external_references": [dr_ref(RENAMED)],
        },
    )


def test_a_delete_exports_the_replacement_it_names_by_ref(parts):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    proposal = propose(
        repo,
        proposals,
        uses_create(delivers),
        OperationDraft(
            seq=2, op="delete", kind="property", target_id=delivers.id, replacement="$uses"
        ),
    )
    proposal = apply_all(proposals, proposal)
    assert all(o.status is OperationStatus.APPLIED for o in proposal.operations), [
        o.reason for o in proposal.operations
    ]

    changes = spec_changes_for(proposal, repo)["changes"]

    assert [c["op"] for c in changes] == ["create", "delete"]
    assert changes[1]["relationship_id"] == DELIVERS
    assert changes[1]["replacement_relationship_id"] == RENAMED


def test_a_named_replacement_whose_create_was_rejected_names_none(parts):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    proposal = propose(
        repo,
        proposals,
        uses_create(delivers),
        OperationDraft(
            seq=2, op="delete", kind="property", target_id=delivers.id, replacement="$uses"
        ),
    )
    create, delete = proposal.operations
    proposals.reject(proposal.id, [create.id], "no")
    proposal = proposals.apply(proposal.id, [delete.id])
    assert proposal.operations[1].status is OperationStatus.APPLIED, proposal.operations[1].reason

    (change,) = spec_changes_for(proposal, repo)["changes"]

    assert change["op"] == "delete"
    assert "replacement_relationship_id" not in change


def test_undecided_and_non_type_operations_are_skipped(parts):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    proposal = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1, op="update", kind="property", target_id=delivers.id, fields={"title": "x"}
        ),
        OperationDraft(
            seq=2, op="update", kind="taxonomy", target_id=taxonomy.id, fields={"color": "#123456"}
        ),
    )
    proposals.reject(proposal.id, [proposal.operations[0].id], "no")
    proposal = proposals.apply(proposal.id, [proposal.operations[1].id])

    document = spec_changes_for(proposal, repo)

    assert document["changes"] == []
    assert [(s["seq"], s["why"]) for s in document["skipped"]] == [
        (1, "rejected"),
        (2, "a taxonomy operation, which DR's spec doesn't hold"),
    ]


def test_a_reverted_proposal_is_refused(parts):
    _, repo, proposals = parts
    proposal = apply_all(proposals, propose(repo, proposals, create_new(repo)))
    proposals.revert(proposal.id)

    with pytest.raises(ValueError, match="reverted"):
        spec_changes_for(proposals._get(proposal.id), repo)


def test_a_dr_id_disagreeing_with_the_classes_is_refused(parts):
    _, repo, proposals = parts
    proposal = apply_all(proposals, propose(repo, proposals, create_new(repo)))
    # A create recorded with a DR id its classes don't give (as no rule would let through now).
    proposal.operations[0].fields["external_references"] = [dr_ref(RENAMED)]

    with pytest.raises(ValueError, match="DR relationship id is api.operation.uses"):
        spec_changes_for(proposal, repo)


def test_a_create_naming_a_class_the_proposal_created_resolves_its_ref(parts):
    _, repo, proposals = parts
    operation_class = class_by_dr_id(repo, "api.operation")
    widget = OperationDraft(
        seq=1,
        op="create",
        kind="class",
        ref="widget",
        fields={
            "concept_scheme_id": operation_class.concept_scheme_id,
            "title": "Widget",
            "identifier": "api_widget",
            "external_references": [{"source": DR_SOURCE, "identifier": "api.widget"}],
        },
    )
    uses = OperationDraft(
        seq=2,
        op="create",
        kind="property",
        fields={
            "identifier": "widget_uses_operation",
            "title": "api.widget uses api.operation",
            "canonical_predicate": "uses",
            "domain_class_id": "$widget",
            "range_class_id": operation_class.id,
            "external_references": [dr_ref("api.widget.uses.api.operation")],
        },
    )
    proposal = apply_all(proposals, propose(repo, proposals, widget, uses))
    assert all(o.status is OperationStatus.APPLIED for o in proposal.operations), [
        o.reason for o in proposal.operations
    ]

    document = spec_changes_for(proposal, repo)

    (change,) = document["changes"]
    assert change["relationship_id"] == "api.widget.uses.api.operation"
    assert change["source_spec_node_id"] == "api.widget"
    assert document["skipped"] == []
    assert [(c["seq"], c["spec_node_id"]) for c in document["node_changes"]] == [(1, "api.widget")]


def test_a_type_on_dr_spec_classes_without_a_dr_reference_is_refused(parts):
    _, repo, proposals = parts
    create = create_new(repo)
    create.fields["external_references"] = []
    proposal = apply_all(proposals, propose(repo, proposals, create))
    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason

    with pytest.raises(ValueError, match="seq 1: it created a relationship type on DR spec"):
        spec_changes_for(proposal, repo)


def test_an_update_stripping_the_dr_reference_is_refused(parts):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    proposal = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1,
            op="update",
            kind="property",
            target_id=delivers.id,
            fields={"external_references": []},
        ),
    )
    proposal = apply_all(proposals, proposal)
    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason

    with pytest.raises(ValueError, match=f"removed the DR reference of {DELIVERS}"):
        spec_changes_for(proposal, repo)


def test_a_reversal_drops_the_evidence_as_dr_does(parts):
    _, repo, proposals = parts
    delivers = prop_by_dr_id(repo, DELIVERS)
    with_evidence = [dr_ref(DELIVERS, **SPEC_ATTRIBUTES, evidence=EVIDENCE)]
    first = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1,
            op="update",
            kind="property",
            target_id=delivers.id,
            fields={"external_references": with_evidence},
        ),
    )
    apply_all(proposals, first)
    second = propose(
        repo,
        proposals,
        OperationDraft(
            seq=1, op="update", kind="property", target_id=delivers.id, fields={"title": "x"}
        ),
    )
    op = second.operations[0]
    edit = {
        "canonical_predicate": "references",
        "domain_class_id": delivers.range_class_id,
        "range_class_id": delivers.domain_class_id,
    }

    second = proposals.apply(second.id, [op.id], edits={op.id: edit})
    assert second.operations[0].status is OperationStatus.APPLIED, second.operations[0].reason

    ref = next(r for r in prop_by_dr_id(repo, NEW).external_references if r.source == DR_SOURCE)
    assert dict(ref.metadata) == SPEC_ATTRIBUTES
    (change,) = spec_changes_for(second, repo)["changes"]
    assert change["previous_relationship_id"] == DELIVERS
    assert change["relationship_id"] == NEW
    assert change["set"] == {"evidence": []}


def other_dr_types(repo, count):
    """Relationship types of the pinned spec's api layer other than delivers (sorted by DR id)."""
    found = sorted(
        (ref.identifier, prop)
        for prop in repo.list_property_definitions(limit=None)
        for ref in prop.external_references
        if ref.source == DR_SOURCE
        and ref.identifier.startswith("api.")
        and ref.identifier != DELIVERS
    )
    return [prop for _, prop in found[:count]]


def delete_naming(seq, target, replacement):
    return OperationDraft(
        seq=seq, op="delete", kind="property", target_id=target.id, replacement=replacement.id
    )


def test_a_replacement_the_proposal_also_deletes_is_followed_to_the_end(parts):
    _, repo, proposals = parts
    a = prop_by_dr_id(repo, DELIVERS)
    b, c = other_dr_types(repo, 2)
    c_id = next(r.identifier for r in c.external_references if r.source == DR_SOURCE)
    proposal = propose(repo, proposals, delete_naming(1, a, b), delete_naming(2, b, c))
    proposal = apply_all(proposals, proposal)
    assert all(o.status is OperationStatus.APPLIED for o in proposal.operations), [
        o.reason for o in proposal.operations
    ]

    changes = spec_changes_for(proposal, repo)["changes"]

    # A ends at C (through B, which this proposal deletes too), not at nothing.
    assert [ch["replacement_relationship_id"] for ch in changes] == [c_id, c_id]
    assert all("note" not in ch for ch in changes)


def test_a_replacement_chain_that_cycles_names_none_and_says_so(parts):
    _, repo, proposals = parts
    a = prop_by_dr_id(repo, DELIVERS)
    (b,) = other_dr_types(repo, 1)
    proposal = propose(repo, proposals, delete_naming(1, a, b), delete_naming(2, b, a))
    proposal = apply_all(proposals, proposal)
    assert all(o.status is OperationStatus.APPLIED for o in proposal.operations), [
        o.reason for o in proposal.operations
    ]

    changes = spec_changes_for(proposal, repo)["changes"]

    assert [ch["op"] for ch in changes] == ["delete", "delete"]
    for change in changes:
        assert "replacement_relationship_id" not in change
        assert "comes back round" in change["note"]


def test_the_header_carries_the_drafted_revision_and_the_landing(parts):
    _, repo, proposals = parts
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    drafted = SourceRevision(repo="documentation_robotics", commit="bbb222", spec_version="0.8.4")
    proposal = proposals.propose(
        taxonomy.id, "Spec changes", [create_new(repo)], ProposalSource.MCP, source_revision=drafted
    )
    proposal = apply_all(proposals, proposal)

    unlanded = spec_changes_for(proposal, repo)
    landing = SourceRevision(repo="documentation_robotics", commit="ccc333", spec_version="0.8.5")
    landed = spec_changes_for(proposals.mark_landed(proposal.id, landing), repo)

    assert unlanded["source_revision"] == {
        "repo": "documentation_robotics",
        "commit": "bbb222",
        "spec_version": "0.8.4",
    }
    assert unlanded["landed"] is None
    assert landed["source_revision"] == unlanded["source_revision"]
    assert {k: landed["landed"][k] for k in ("repo", "commit", "spec_version")} == {
        "repo": "documentation_robotics",
        "commit": "ccc333",
        "spec_version": "0.8.5",
    }
    assert landed["landed"]["landed_at"]
