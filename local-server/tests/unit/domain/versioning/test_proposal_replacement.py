# The in-use fixtures are imported for pytest, so test arguments shadow them.
# ruff: noqa: F811
"""
Unit tests for a relationship-type delete's named replacement (#1398): it is
validated and resolved when proposed, its pair of classes is compared with the
deleted type's, and the in-use resolver offers it first when it fits.
"""

import pytest

from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.in_use import PairMatch, compare_pair
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import OperationKind, OperationType, ProposalSource
from tests.unit.domain.versioning.test_proposal_in_use import (  # noqa: F401 - fixtures
    add_fitting_type,
    edge_attributes,
    graph,
    ontology,
    publisher,
    repo,
    scope,
    service,
    the_op,
)

T, K = OperationType, OperationKind


def delete(graph, replacement, seq=1, target="triggers_function"):
    return OperationDraft(seq, T.DELETE, K.PROPERTY, graph[target], replacement=replacement)


def propose(service, graph, *drafts):
    return service.propose(graph["taxonomy"], "Business layer", list(drafts), ProposalSource.MCP)


def errors_of(service, graph, *drafts):
    with pytest.raises(ProposalValidationError) as caught:
        propose(service, graph, *drafts)
    return [(e.seq, e.code, e.message) for e in caught.value.errors]


class TestComparePair:
    def test_same_reversed_or_different(self):
        assert compare_pair(("a", "b"), ("a", "b")) is PairMatch.SAME
        assert compare_pair(("a", "b"), ("b", "a")) is PairMatch.REVERSED
        assert compare_pair(("a", "b"), ("a", "c")) is PairMatch.DIFFERENT
        assert compare_pair(("a", "a"), ("a", "a")) is PairMatch.SAME
        assert compare_pair(("a", None), (None, "a")) is PairMatch.REVERSED
        assert compare_pair((None, None), ("a", None)) is PairMatch.DIFFERENT


class TestPropose:
    def test_resolves_an_identifier_to_the_types_id(self, service, graph):
        proposal = propose(service, graph, delete(graph, "businessevent_triggers_businessprocess"))
        assert the_op(proposal).proposed_replacement_id == graph["triggers_process"]

    def test_keeps_an_id_or_a_ref_to_an_earlier_property_create(self, service, graph):
        by_id = propose(service, graph, delete(graph, graph["triggers_process"]))
        assert the_op(by_id).proposed_replacement_id == graph["triggers_process"]
        create = OperationDraft(
            1,
            T.CREATE,
            K.PROPERTY,
            ref="serves",
            fields={"identifier": "serves", "title": "serves"},
        )
        by_ref = propose(service, graph, create, delete(graph, "$serves", seq=2))
        assert the_op(by_ref, 2).proposed_replacement_id == "$serves"

    def test_refuses_what_cant_be_a_replacement(self, service, graph, ontology):
        on_update = OperationDraft(
            1,
            T.UPDATE,
            K.PROPERTY,
            graph["triggers_function"],
            fields={"title": "x"},
            replacement=graph["triggers_process"],
        )
        on_individual = OperationDraft(
            1, T.DELETE, K.INDIVIDUAL, graph["changed"], replacement=graph["triggers_process"]
        )
        class_create = OperationDraft(
            1,
            T.CREATE,
            K.CLASS,
            ref="cls",
            fields={
                "concept_scheme_id": ontology.get_class(graph["event"]).concept_scheme_id,
                "title": "C",
            },
        )
        cases = [
            ([on_update], "invalid", "Only a property"),
            ([on_individual], "invalid", "Only a property"),
            ([delete(graph, "no_such_type")], "replacement_not_found", "no_such_type"),
            ([delete(graph, graph["triggers_function"])], "invalid", "can't replace itself"),
            ([delete(graph, "$later")], "unknown_ref", "no create earlier"),
            ([class_create, delete(graph, "$cls", seq=2)], "replacement_not_found", "a class"),
            ([delete(graph, 5)], "invalid", "must be a relationship type"),
        ]
        for drafts, code, text in cases:
            (error,) = [e for e in errors_of(service, graph, *drafts)]
            assert error[1] == code and text in error[2], (drafts, error)

    def test_a_replacement_the_proposal_also_deletes_is_kept_as_a_chain(self, service, graph):
        """DR plans chain them (Gate B: seq 6's replacement is the type row 17 deletes)."""
        proposal = propose(
            service,
            graph,
            delete(graph, graph["triggers_process"]),
            OperationDraft(2, T.DELETE, K.PROPERTY, graph["triggers_process"]),
        )
        assert the_op(proposal).proposed_replacement_id == graph["triggers_process"]
        check = service.replacement_checks(proposal)[the_op(proposal).id]
        assert check.pair is PairMatch.DIFFERENT
        # The in-use resolver never offers a type the proposal deletes.
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]
        assert graph["triggers_process"] not in {r.property_id for r in blockers.replacements}


class TestAfterTheProposal:
    """The replacement is judged as the proposal leaves it (review 1 on #1398)."""

    def test_an_update_of_the_replacement_in_the_proposal_overlays_its_pair(
        self, service, graph, ontology
    ):
        """DR navigation seq 20/21: seq 20 retargets the type seq 21 names as replacement."""
        twin = add_fitting_type(ontology, graph)  # BusinessEvent -> BusinessFunction, as deleted
        retarget = OperationDraft(
            20,
            T.UPDATE,
            K.PROPERTY,
            twin,
            fields={
                "identifier": "businessfunction_navigates_to_businessprocess",
                "domain_class_id": graph["function"],
                "range_class_id": graph["process"],
            },
        )
        proposal = propose(service, graph, retarget, delete(graph, twin, seq=21))

        check = service.replacement_checks(proposal)[the_op(proposal, 21).id]
        assert check.pair is PairMatch.DIFFERENT  # the same pair until seq 20 applies
        assert (check.domain.title, check.range.title) == ("BusinessFunction", "BusinessProcess")
        assert check.identifier == "businessfunction_navigates_to_businessprocess"
        assert check.property_id == twin

        # A reversal by the update (DR technology seq 8/9) reads as reversed.
        reverse = OperationDraft(
            8,
            T.UPDATE,
            K.PROPERTY,
            twin,
            fields={"domain_class_id": graph["function"], "range_class_id": graph["event"]},
        )
        reversed_ = propose(service, graph, reverse, delete(graph, twin, seq=9))
        assert service.replacement_checks(reversed_)[the_op(reversed_, 9).id].pair is (
            PairMatch.REVERSED
        )

        # Rejected, the update no longer counts.
        rejected = service.reject(proposal.id, [the_op(proposal, 20).id])
        assert service.replacement_checks(rejected)[the_op(rejected, 21).id].pair is (
            PairMatch.SAME
        )

    def test_a_chain_of_deletes_is_followed_to_the_type_it_ends_at(self, service, graph, ontology):
        """Gate B business seq 6 -> seq 17: the replacement is deleted too, with its own."""
        serves = add_fitting_type(ontology, graph)
        proposal = propose(
            service,
            graph,
            delete(graph, graph["triggers_process"], seq=6),
            delete(graph, serves, seq=17, target="triggers_process"),
        )

        check = service.replacement_checks(proposal)[the_op(proposal, 6).id]
        assert check.replacement_deleted and not check.cycle
        assert [(link.identifier, link.deleted_by_seq) for link in check.chain] == [
            ("businessevent_triggers_businessprocess", 17),
            ("businessevent_serves_businessfunction", None),
        ]
        assert check.pair is PairMatch.DIFFERENT
        assert not service.replacement_checks(proposal)[the_op(proposal, 17).id].chain

        # Applied, the deleted replacement is read from its delete's base.
        applied = service.apply(proposal.id, [the_op(proposal, 17).id])
        after = service.replacement_checks(applied)[the_op(applied, 6).id]
        assert (after.pair, after.property_id, after.replacement_deleted) == (
            PairMatch.DIFFERENT,
            None,
            True,
        )
        assert after.range.title == "BusinessProcess"

    def test_deletes_naming_each_other_are_a_cycle(self, service, graph):
        """DR api 15 <-> 19: both types are deleted, so neither replaces the other."""
        proposal = propose(
            service,
            graph,
            delete(graph, graph["triggers_process"], seq=15),
            delete(graph, graph["triggers_function"], seq=19, target="triggers_process"),
        )

        checks = service.replacement_checks(proposal)
        first, second = checks[the_op(proposal, 15).id], checks[the_op(proposal, 19).id]
        assert first.cycle and second.cycle
        assert [link.deleted_by_seq for link in first.chain] == [19]
        assert [link.deleted_by_seq for link in second.chain] == [15]

        # A rejected delete breaks the cycle: its type stays.
        kept = service.reject(proposal.id, [the_op(proposal, 19).id])
        assert not service.replacement_checks(kept)[the_op(kept, 15).id].chain


class TestChecks:
    def test_compares_the_replacements_pair_with_the_deleted_types(self, service, graph, ontology):
        reversed_type = ontology.create_property_definition(
            "businessfunction_triggered_by_businessevent",
            "triggered by",
            domain_class_id=graph["function"],
            range_class_id=graph["event"],
        )
        cases = {
            add_fitting_type(ontology, graph): PairMatch.SAME,
            reversed_type.id: PairMatch.REVERSED,
            graph["triggers_process"]: PairMatch.DIFFERENT,
        }
        for replacement, pair in cases.items():
            proposal = propose(service, graph, delete(graph, replacement))
            check = service.replacement_checks(proposal)[the_op(proposal).id]
            assert check.pair is pair
            assert check.property_id == replacement
            assert (check.deleted_domain.title, check.deleted_range.title) == (
                "BusinessEvent",
                "BusinessFunction",
            )

        different = service.replacement_checks(proposal)[the_op(proposal).id]
        assert (different.domain.title, different.range.title) == (
            "BusinessEvent",
            "BusinessProcess",
        )
        assert different.identifier == "businessevent_triggers_businessprocess"

    def test_a_ref_reads_its_create_until_applied_and_is_missing_once_rejected(
        self, service, graph
    ):
        create = OperationDraft(
            1,
            T.CREATE,
            K.PROPERTY,
            ref="serves",
            fields={
                "identifier": "businessfunction_serves_businessevent",
                "title": "serves",
                "domain_class_id": graph["function"],
                "range_class_id": graph["event"],
            },
        )
        proposal = propose(service, graph, create, delete(graph, "$serves", seq=2))
        delete_id = the_op(proposal, 2).id

        pending = service.replacement_checks(proposal)[delete_id]
        assert (pending.pair, pending.property_id) == (PairMatch.REVERSED, None)
        assert pending.identifier == "businessfunction_serves_businessevent"

        applied = service.apply(proposal.id, [the_op(proposal).id])
        made = service.replacement_checks(applied)[delete_id]
        assert made.property_id == the_op(applied).result_entity_id
        assert made.pair is PairMatch.REVERSED

        other = propose(service, graph, create, delete(graph, "$serves", seq=2))
        rejected = service.reject(other.id, [the_op(other).id])
        gone = service.replacement_checks(rejected)[the_op(rejected, 2).id]
        assert (gone.pair, gone.domain, gone.range) == (PairMatch.MISSING, None, None)

    def test_a_replacement_deleted_since_is_missing(self, service, graph, ontology):
        proposal = propose(service, graph, delete(graph, graph["triggers_process"]))
        ontology.delete_property_definition(graph["triggers_process"])
        check = service.replacement_checks(proposal)[the_op(proposal).id]
        assert check.pair is PairMatch.MISSING

    def test_no_check_without_a_replacement(self, service, graph):
        proposal = propose(service, graph, delete(graph, None))
        assert service.replacement_checks(proposal) == {}


class TestInUseResolver:
    def test_offers_the_named_replacement_first_when_it_fits(self, service, graph, ontology):
        serves = add_fitting_type(ontology, graph)  # sorts after "businessevent_relates_to"
        relates = ontology.create_property_definition(
            "businessevent_relates_to",
            "relates to",
            domain_class_id=graph["event"],
            external_references=edge_attributes("weight"),
        ).id
        unnamed = propose(service, graph, delete(graph, None))
        listed = service.in_use_blockers(unnamed)[the_op(unnamed).id].replacements
        assert [r.property_id for r in listed] == [relates, serves]

        named = propose(service, graph, delete(graph, serves))
        listed = service.in_use_blockers(named)[the_op(named).id].replacements
        assert [r.property_id for r in listed] == [serves, relates]

    def test_a_named_replacement_that_doesnt_fit_isnt_offered(self, service, graph):
        proposal = propose(service, graph, delete(graph, graph["triggers_process"]))
        blockers = service.in_use_blockers(proposal)[the_op(proposal).id]
        assert blockers.replacements == ()
