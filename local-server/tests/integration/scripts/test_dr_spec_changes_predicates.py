"""
Integration tests (#1481): predicate creates and updates in the dr_spec
catalog export as `predicate_changes` in `cs-dr-spec-changes/1`, in the shape
DR's landing (documentation_robotics PR 1035) agreed; DR's enums are checked
as they apply.

Built on the pinned DR spec snapshot (0.8.4), whose import loads its catalog.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from adapters.interchange.dr_spec_changes import spec_changes_for
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposals import OperationStatus, ProposalSource
from scripts.dr_ontology_loader import DR_SOURCE, DR_TAXONOMY_IDENTIFIER
from tests.integration.scripts import test_dr_reflection_plan as plan_tests
from tests.integration.scripts.test_dr_reflection_plan import class_by_dr_id

spec_db = plan_tests.spec_db
parts = plan_tests.parts

SEMANTICS = {
    "directionality": "unidirectional",
    "transitivity": False,
    "symmetry": False,
    "reflexivity": False,
}


def dr_ref(identifier, **metadata):
    return [{"source": DR_SOURCE, "identifier": identifier, "metadata": metadata}]


@pytest.fixture()
def dr(parts):
    ontology, repo, proposals = parts
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    return ontology, repo, proposals, taxonomy


def propose(proposals, taxonomy, *drafts):
    return proposals.propose(taxonomy.id, "Predicates", list(drafts), ProposalSource.MCP)


def apply_all(proposals, proposal):
    applied = proposals.apply(proposal.id, [o.id for o in proposal.operations])
    return applied


def test_a_create_and_a_type_using_it_export_together(dr):
    _, repo, proposals, taxonomy = dr
    create = OperationDraft(
        seq=1,
        op="create",
        kind="predicate",
        ref="guards",
        fields={
            "identifier": "guards",
            "description": "Protects another element",
            "external_references": dr_ref(
                "guards", inverse="guarded-by", category="security", semantics=SEMANTICS
            ),
        },
    )
    source = class_by_dr_id(repo, "api.operation")
    target = class_by_dr_id(repo, "api.response")
    uses = OperationDraft(
        seq=2,
        op="create",
        kind="property",
        fields={
            "identifier": "operation_guards_response",
            "title": "api.operation guards api.response",
            "canonical_predicate": "guards",
            "domain_class_id": source.id,
            "range_class_id": target.id,
            "external_references": [
                {"source": DR_SOURCE, "identifier": "api.operation.guards.api.response"}
            ],
        },
    )
    proposal = apply_all(proposals, propose(proposals, taxonomy, create, uses))
    assert [o.status for o in proposal.operations] == [OperationStatus.APPLIED] * 2, [
        o.reason for o in proposal.operations
    ]
    recorded = proposals.decisions_of(proposal.id)

    document = spec_changes_for(proposal, repo, recorded)

    (change,) = document["predicate_changes"]
    assert {k: change[k] for k in ("seq", "op", "predicate", "set")} == {
        "seq": 1,
        "op": "create",
        "predicate": "guards",
        "set": {
            "description": "Protects another element",
            "inverse": "guarded-by",
            "category": "security",
            "archimate_alignment": None,
            "semantics": SEMANTICS,
        },
    }
    assert change["decided_by"] == "user"
    assert document["changes"][0]["predicate"] == "guards"


def test_an_update_sends_only_the_changed_keys_and_flags(dr):
    _, repo, proposals, taxonomy = dr
    serves = repo.get_predicate_by_identifier(taxonomy.id, "serves")
    current = {r.source: dict(r.metadata or {}) for r in serves.external_references}[DR_SOURCE]
    semantics = {**(current.get("semantics") or SEMANTICS)}
    semantics["transitivity"] = not semantics.get("transitivity", False)
    update = OperationDraft(
        seq=1,
        op="update",
        kind="predicate",
        target_id=serves.id,
        fields={
            "external_references": dr_ref(
                "serves", **{**current, "category": "dependency", "semantics": semantics}
            ),
        },
    )

    proposal = apply_all(proposals, propose(proposals, taxonomy, update))

    (change,) = spec_changes_for(proposal, repo)["predicate_changes"]
    expected = {"semantics": {"transitivity": semantics["transitivity"]}}
    if current.get("category") != "dependency":
        expected["category"] = "dependency"
    assert (change["op"], change["predicate"], change["set"]) == ("update", "serves", expected)


def test_a_category_dr_does_not_have_is_refused_as_it_applies(dr):
    _, repo, proposals, taxonomy = dr
    create = OperationDraft(
        seq=1,
        op="create",
        kind="predicate",
        fields={
            "identifier": "guards",
            "description": "Protects",
            "external_references": dr_ref(
                "guards", inverse="guarded-by", category="kitchen", semantics=SEMANTICS
            ),
        },
    )

    (applied,) = apply_all(proposals, propose(proposals, taxonomy, create)).operations

    assert applied.status is OperationStatus.FAILED
    assert "category 'kitchen' isn't one of" in applied.reason


def test_a_dr_predicate_create_without_a_dr_reference_is_refused_at_export(dr):
    _, repo, proposals, taxonomy = dr
    create = OperationDraft(seq=1, op="create", kind="predicate", fields={"identifier": "guards"})
    proposal = apply_all(proposals, propose(proposals, taxonomy, create))

    with pytest.raises(ValueError, match="without a DR reference"):
        spec_changes_for(proposal, repo)


def _serves(repo, taxonomy):
    serves = repo.get_predicate_by_identifier(taxonomy.id, "serves")
    metadata = {r.source: dict(r.metadata or {}) for r in serves.external_references}[DR_SOURCE]
    return serves, metadata


def test_a_dr_predicates_description_cant_be_cleared(dr):
    _, repo, proposals, taxonomy = dr
    serves, _ = _serves(repo, taxonomy)
    update = OperationDraft(
        seq=1, op="update", kind="predicate", target_id=serves.id, fields={"description": None}
    )

    (applied,) = apply_all(proposals, propose(proposals, taxonomy, update)).operations

    assert applied.status is OperationStatus.FAILED
    assert "needs a description" in applied.reason


def test_an_update_keeps_the_whole_dr_entry(dr):
    """Context Studio keeps DR's whole entry; the export sends only what changed."""
    _, repo, proposals, taxonomy = dr
    serves, _ = _serves(repo, taxonomy)
    partial = OperationDraft(
        seq=1,
        op="update",
        kind="predicate",
        target_id=serves.id,
        fields={"external_references": dr_ref("serves", semantics={"symmetry": True})},
    )

    (applied,) = apply_all(proposals, propose(proposals, taxonomy, partial)).operations

    assert applied.status is OperationStatus.FAILED
    assert "a DR predicate needs inverse, category" in applied.reason


def test_an_unused_predicate_deleted_with_no_replacement_retires_into_null(dr):
    _, repo, proposals, taxonomy = dr
    unused = OperationDraft(
        seq=1,
        op="create",
        kind="predicate",
        fields={
            "identifier": "guards",
            "description": "Protects",
            "external_references": dr_ref(
                "guards", inverse="guarded-by", category="security", semantics=SEMANTICS
            ),
        },
    )
    created = apply_all(proposals, propose(proposals, taxonomy, unused))
    guards = created.operations[0].result_entity_id
    delete = OperationDraft(seq=1, op="delete", kind="predicate", target_id=guards)

    proposal = apply_all(proposals, propose(proposals, taxonomy, delete))

    (record,) = [
        r for r in spec_changes_for(proposal, repo)["records"] if r["action"] == "retire-predicate"
    ]
    assert (record["from"], record["to"]) == ("guards", None)


def test_a_retirement_into_a_create_that_was_rejected_fails(dr):
    _, repo, proposals, taxonomy = dr
    serves, _ = _serves(repo, taxonomy)
    unused = (
        apply_all(
            proposals,
            propose(
                proposals,
                taxonomy,
                OperationDraft(
                    seq=1,
                    op="create",
                    kind="predicate",
                    fields={
                        "identifier": "spare",
                        "description": "Unused",
                        "external_references": dr_ref(
                            "spare", inverse="spared-by", category="structural", semantics=SEMANTICS
                        ),
                    },
                ),
            ),
        )
        .operations[0]
        .result_entity_id
    )
    create = OperationDraft(
        seq=1,
        op="create",
        kind="predicate",
        ref="next",
        fields={
            "identifier": "guards",
            "description": "Protects",
            "external_references": dr_ref(
                "guards", inverse="guarded-by", category="security", semantics=SEMANTICS
            ),
        },
    )
    retire = OperationDraft(
        seq=2, op="delete", kind="predicate", target_id=unused, replacement="$next"
    )
    proposal = propose(proposals, taxonomy, create, retire)
    proposal = proposals.reject(proposal.id, [proposal.operations[0].id], "not yet")

    (applied,) = [
        o
        for o in proposals.apply(proposal.id, [proposal.operations[1].id]).operations
        if o.seq == 2
    ]

    assert applied.status is OperationStatus.FAILED
    assert applied.reason.startswith("unresolved_ref")
    assert repo.get_predicate(unused) is not None


def test_a_predicate_retired_earlier_in_the_proposal_cant_be_used(dr):
    _, repo, proposals, taxonomy = dr
    spare = (
        apply_all(
            proposals,
            propose(
                proposals,
                taxonomy,
                OperationDraft(
                    seq=1,
                    op="create",
                    kind="predicate",
                    fields={
                        "identifier": "spare",
                        "description": "Unused",
                        "external_references": dr_ref(
                            "spare", inverse="spared-by", category="structural", semantics=SEMANTICS
                        ),
                    },
                ),
            ),
        )
        .operations[0]
        .result_entity_id
    )
    source = class_by_dr_id(repo, "api.operation")
    retire = OperationDraft(seq=1, op="delete", kind="predicate", target_id=spare)
    use = OperationDraft(
        seq=2,
        op="create",
        kind="property",
        fields={
            "identifier": "operation_spare_operation",
            "title": "api.operation spare api.operation",
            "canonical_predicate": "spare",
            "domain_class_id": source.id,
            "range_class_id": source.id,
        },
    )

    with pytest.raises(ProposalValidationError) as excinfo:
        propose(proposals, taxonomy, retire, use)
    assert "deleted earlier in this proposal" in excinfo.value.errors[0].message


def test_reverting_a_retirement_restores_the_predicate_and_its_types(parts):
    """Revert over SQLite: the moved type gets its predicate back (non-DR taxonomy)."""
    ontology, repo, proposals = parts
    house = ontology.create_taxonomy(title="House", identifier="house")
    scheme = ontology.create_scheme(taxonomy_id=house.id, title="Kinds")
    room = ontology.create_class(scheme.id, "Room", identifier="room")
    near = ontology.create_property_definition(
        "room_near_room",
        "near",
        canonical_predicate="near",
        domain_class_id=room.id,
        range_class_id=room.id,
        create_missing_predicate=True,
    )
    old = near.predicate_id
    ontology.create_predicate(house.id, "beside")
    proposal = proposals.propose(
        house.id,
        "Rename near",
        [OperationDraft(seq=1, op="delete", kind="predicate", target_id=old, replacement="beside")],
        ProposalSource.MCP,
    )
    proposal = proposals.apply(proposal.id, [proposal.operations[0].id])
    assert proposal.operations[0].status is OperationStatus.APPLIED, proposal.operations[0].reason
    assert repo.get_property_definition(near.id).canonical_predicate == "beside"

    proposals.revert(proposal.id)

    assert repo.get_predicate(old).identifier == "near"
    assert repo.get_property_definition(near.id).predicate_id == old
