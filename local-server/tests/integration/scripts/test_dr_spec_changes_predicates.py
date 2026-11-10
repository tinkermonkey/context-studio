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
