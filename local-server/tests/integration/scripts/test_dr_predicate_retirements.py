"""
Integration tests (#1440, #1481): a DR reflection plan's `predicate_retirements`
become predicate deletes naming the replacement, after the plan's operations,
and `cs-dr-spec-changes/1` sends an applied one back as a `retire-predicate`
record (it applies once no DR relationship type uses the predicate), else lists
it as skipped with the types still using it.

Built on the pinned DR spec snapshot (0.8.4), whose only `enforces` type is
security.securityconstraints enforces security.securitypolicy.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from adapters.interchange.dr_reflection_plan import PlanError, import_reflection_plan
from adapters.interchange.dr_spec_changes import spec_changes_for
from tests.integration.scripts import test_dr_reflection_plan as plan_tests
from tests.integration.scripts.test_dr_reflection_plan import operation, plan_with

spec_db = plan_tests.spec_db
parts = plan_tests.parts

ENFORCES = "security.securityconstraints.enforces.security.securitypolicy"
RETIREMENT = {"from": "enforces", "to": "governs", "note": "enforcing a policy is governing"}


def retiring(*operations, retirements=(RETIREMENT,)):
    plan = plan_with(*operations)
    plan["predicate_retirements"] = list(retirements)
    return plan


def test_the_retirements_become_predicate_deletes_after_the_plan(parts):
    _, repo, proposals = parts

    proposal = import_reflection_plan(retiring(operation(1, "delete", ENFORCES)), proposals, repo)

    plan_op, retire = proposal.operations
    assert (retire.kind.value, retire.op.value, retire.seq) == ("predicate", "delete", 2)
    assert retire.base["identifier"] == "enforces"
    governs = repo.get_predicate(retire.proposed_replacement_id)
    assert governs.identifier == "governs"
    assert retire.rationale == "enforcing a policy is governing"
    assert proposals._get(proposal.id).client_metadata == {}


def test_a_plan_without_retirements_has_no_predicate_operations(parts):
    _, repo, proposals = parts

    proposal = import_reflection_plan(plan_with(operation(1, "delete", ENFORCES)), proposals, repo)

    assert [o.kind.value for o in proposal.operations] == ["property"]


def test_a_retirement_is_exported_once_no_type_uses_the_predicate(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(retiring(operation(1, "delete", ENFORCES)), proposals, repo)
    proposal = proposals.apply(proposal.id, [o.id for o in proposal.operations])
    recorded = proposals.decisions_of(proposal.id)

    document = spec_changes_for(proposal, repo, recorded)

    retire = proposal.operations[1]
    assert retire.status.value == "applied", retire.reason
    assert document["skipped"] == []
    assert document["records"][-1] == {
        "action": "retire-predicate",
        "kind": "cs:retire-predicate",
        "from": "enforces",
        "to": "governs",
        "p": 1.0,
        "proposal_id": proposal.id,
        "operation_id": retire.id,
        "applied_at": recorded[retire.id].decided_at.isoformat(),
        "note": "enforcing a policy is governing",
    }
    taxonomy = repo.get_by_identifier("dr_spec")
    assert repo.get_predicate_by_identifier(taxonomy.id, "enforces") is None


def test_a_retirement_is_skipped_while_a_type_still_uses_the_predicate(parts):
    _, repo, proposals = parts
    proposal = import_reflection_plan(retiring(operation(1, "delete", ENFORCES)), proposals, repo)
    plan_op, retire = proposal.operations
    proposal = proposals.reject(proposal.id, [plan_op.id], "keep enforces")
    proposal = proposals.apply(proposal.id, [retire.id])
    retire = proposal.operations[1]
    # DR's relationship ids embed the predicate: its types can't just move.
    assert retire.status.value == "failed"
    assert retire.reason.startswith(f"refused: relationship type ")

    document = spec_changes_for(proposal, repo)

    assert [r for r in document["records"] if r["action"] == "retire-predicate"] == []
    assert document["skipped"][-1] == {
        "seq": None,
        "op_id": None,
        "retire_predicate": "enforces",
        "why": "retiring enforces into governs: a relationship type still uses it",
        "relationship_ids": [ENFORCES],
    }


@pytest.mark.parametrize(
    "retirement, problem",
    [
        ({"from": "enforces", "to": "enforces"}, "retires enforces into itself"),
        ({"from": "nonesuch", "to": "governs"}, "nonesuch is not in the spec's predicate catalog"),
        ({"from": "enforces", "to": "nonesuch"}, "nonesuch is not in the spec's predicate catalog"),
        ({"from": "enforces"}, "not an object with from and to predicates"),
    ],
)
def test_a_retirement_that_does_not_hold_refuses_the_plan(parts, retirement, problem):
    _, repo, proposals = parts

    with pytest.raises(PlanError, match=problem):
        import_reflection_plan(
            retiring(operation(1, "delete", ENFORCES), retirements=[retirement]), proposals, repo
        )


def test_a_plan_kind_in_the_operation_kind_is_explained(parts):
    _, repo, proposals = parts
    item = operation(1, "delete", ENFORCES)
    item["kind"] = "principles"

    with pytest.raises(PlanError, match="must be 'property'.*plan kind"):
        import_reflection_plan(plan_with(item), proposals, repo)
