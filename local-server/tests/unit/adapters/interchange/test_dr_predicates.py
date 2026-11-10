"""
Unit tests (#1481): a DR predicate's metadata is checked against the enums of
DR's predicate-catalog.schema.json as its proposal applies.
"""

import pytest

from adapters.interchange.dr_predicates import DrPredicateRules, dr_predicate_problems
from domain.versioning.proposals import OperationKind, OperationType, ProposedOperation

SEMANTICS = {
    "directionality": "unidirectional",
    "transitivity": False,
    "symmetry": False,
    "reflexivity": False,
}
COMPLETE = {
    "inverse": "guarded-by",
    "category": "security",
    "archimate_alignment": None,
    "semantics": SEMANTICS,
}


def operation(op, fields, target_id=None):
    return ProposedOperation(
        seq=1, op=op, kind=OperationKind.PREDICATE, target_id=target_id, fields=fields
    )


def dr_refs(metadata):
    return [{"source": "documentation_robotics", "identifier": "guards", "metadata": metadata}]


def test_a_complete_create_passes():
    assert dr_predicate_problems(COMPLETE, creating=True) == []


@pytest.mark.parametrize(
    "metadata, problem",
    [
        ({**COMPLETE, "category": "kitchen"}, "category 'kitchen' isn't one of"),
        ({**COMPLETE, "archimate_alignment": "Uses"}, "archimate_alignment 'Uses' isn't one of"),
        (
            {**COMPLETE, "semantics": {**SEMANTICS, "directionality": "both"}},
            "directionality 'both' isn't one of",
        ),
        ({**COMPLETE, "semantics": {**SEMANTICS, "symmetry": "no"}}, "symmetry must be true"),
        ({k: v for k, v in COMPLETE.items() if k != "inverse"}, "needs inverse"),
        ({**COMPLETE, "semantics": {"transitivity": True}}, "semantics needs directionality"),
        ({**COMPLETE, "colour": "red"}, "unknown DR predicate fields ['colour']"),
    ],
)
def test_a_create_breaking_drs_catalog_schema_is_refused(metadata, problem):
    assert any(problem in p for p in dr_predicate_problems(metadata, creating=True))


def test_without_creating_only_the_given_fields_are_checked():
    assert dr_predicate_problems({"semantics": {"transitivity": True}}, creating=False) == []
    assert dr_predicate_problems({"category": "ux"}, creating=False) == []


def test_the_rules_govern_predicate_writes_with_a_dr_reference_only():
    rules = DrPredicateRules(repo=None)
    with_dr = {"identifier": "guards", "external_references": dr_refs(COMPLETE)}

    assert rules.governs(operation(OperationType.CREATE, with_dr), with_dr)
    assert not rules.governs(operation(OperationType.CREATE, {"identifier": "x"}), {})
    property_op = ProposedOperation(
        seq=1, op=OperationType.CREATE, kind=OperationKind.PROPERTY, fields=with_dr
    )
    assert not rules.governs(property_op, with_dr)


def test_a_create_needs_a_description():
    rules = DrPredicateRules(repo=None)
    fields = {"identifier": "guards", "external_references": dr_refs(COMPLETE)}

    with pytest.raises(ValueError, match="needs a description"):
        rules.check(operation(OperationType.CREATE, fields), fields)
    rules.check(
        operation(OperationType.CREATE, {**fields, "description": "G"}),
        fields | {"description": "G"},
    )
