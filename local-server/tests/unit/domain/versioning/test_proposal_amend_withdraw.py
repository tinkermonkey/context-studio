"""
Unit tests for #1624: a proposer amends its open proposal in place, withdraws
it (what it applied rolled back), and supersedes it with a new one.
"""

import pytest

from domain.versioning.exceptions import ChangeProposalStateError, ProposalValidationError
from domain.versioning.proposal_service import REMOVED_REASON, WITHDRAWN_REASON
from domain.versioning.proposals import (
    OperationStatus,
    ProposalLinkKind,
    ProposalSource,
    ProposalStatus,
)
from tests.unit.domain.versioning.test_proposal_service import (  # noqa: F401 - fixtures
    K,
    T,
    by_seq,
    draft,
    graph,
    ontology,
    proposals,
    propose,
    publisher,
    repo,
    reverter,
    service,
)


def nine_rewordings(graph):
    """Operation drafts of the kind #1624 describes: wording changes, pending review."""
    return [
        draft(1, T.UPDATE, K.CLASS, graph["room"], description="A room in the house"),
        draft(2, T.UPDATE, K.CLASS, graph["kitchen"], description="Where food is made"),
        draft(3, T.UPDATE, K.CLASS, graph["place"], description="Somewhere"),
    ]


class TestAmend:
    def test_one_sentence_change_is_one_call_and_one_proposal(self, service, proposals, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))
        before = by_seq(proposal)[2]

        amended = service.amend(
            proposal.id,
            replace=[draft(2, T.UPDATE, K.CLASS, graph["kitchen"], description="Where we cook")],
        )

        assert len(proposals._proposals) == 1
        changed = by_seq(amended)[2]
        assert changed.id == before.id
        assert changed.fields == {"description": "Where we cook"}
        assert changed.status is OperationStatus.PENDING
        assert changed.amended_at is not None
        (earlier,) = changed.amendments
        assert earlier["fields"] == {"description": "Where food is made"}
        assert earlier["base"] == before.base
        # The others are untouched
        assert by_seq(amended)[1].amended_at is None
        assert service.get(proposal.id).operations[1].amendments == changed.amendments

    def test_add_and_remove(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))

        amended = service.amend(
            proposal.id,
            add=[draft(4, T.UPDATE, K.CLASS, graph["kitchen"], title="Galley")],
            remove=[3],
        )

        ops = by_seq(service.get(amended.id))
        assert ops[4].status is OperationStatus.PENDING and ops[4].amended_at is not None
        assert ops[4].amendments == []
        assert (ops[3].status, ops[3].reason) == (OperationStatus.WITHDRAWN, REMOVED_REASON)
        assert amended.status is ProposalStatus.OPEN

    def test_removing_every_pending_operation_closes_the_proposal(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph)[:1])

        amended = service.amend(proposal.id, remove=[1])

        assert amended.status is ProposalStatus.WITHDRAWN
        assert service.get(proposal.id).status is ProposalStatus.WITHDRAWN

    def test_a_decided_operation_never_changes(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))
        service.apply(proposal.id, [by_seq(proposal)[1].id])

        with pytest.raises(ProposalValidationError) as raised:
            service.amend(
                proposal.id,
                replace=[draft(1, T.UPDATE, K.CLASS, graph["room"], description="Changed")],
                remove=[1],
            )

        assert {(e.seq, e.code) for e in raised.value.errors} >= {(1, "decided")}

    def test_unknown_and_taken_seqs_are_refused(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))

        with pytest.raises(ProposalValidationError) as raised:
            service.amend(
                proposal.id,
                replace=[draft(9, T.UPDATE, K.CLASS, graph["room"], description="x")],
                add=[draft(2, T.UPDATE, K.CLASS, graph["vocab"], title="x")],
            )

        codes = {(e.seq, e.code) for e in raised.value.errors}
        assert (9, "unknown_seq") in codes and (2, "invalid") in codes

    def test_a_replacement_is_validated_as_on_propose(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))

        with pytest.raises(ProposalValidationError) as raised:
            service.amend(
                proposal.id,
                replace=[draft(1, T.UPDATE, K.CLASS, "no-such-class", description="x")],
            )

        assert [(e.seq, e.code) for e in raised.value.errors] == [(1, "target_not_found")]

    def test_a_replacement_conflicting_with_a_kept_operation_is_refused(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))

        with pytest.raises(ProposalValidationError) as raised:
            service.amend(
                proposal.id,
                replace=[draft(3, T.UPDATE, K.CLASS, graph["room"], description="Twice")],
            )

        assert [(e.seq, e.code) for e in raised.value.errors] == [(3, "conflicting_op")]

    def test_dropping_a_ref_still_in_use_is_refused(self, service, graph):
        proposal = propose(
            service,
            graph,
            draft(1, T.CREATE, K.CLASS, ref="hall", concept_scheme_id=graph["vocab"], title="Hall"),
            draft(
                2,
                T.CREATE,
                K.CLASS,
                ref="foyer",
                concept_scheme_id=graph["vocab"],
                parent_class_id="$hall",
                title="Foyer",
            ),
        )

        with pytest.raises(ProposalValidationError) as raised:
            service.amend(proposal.id, remove=[1])

        assert [(e.seq, e.code) for e in raised.value.errors] == [(1, "ref_in_use")]

    def test_a_dry_run_changes_nothing(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))

        preview = service.amend(
            proposal.id,
            replace=[draft(1, T.UPDATE, K.CLASS, graph["room"], description="Preview")],
            dry_run=True,
        )

        assert by_seq(preview)[1].fields == {"description": "Preview"}
        assert by_seq(service.get(proposal.id))[1].fields == {"description": "A room in the house"}

    def test_only_an_open_proposal_is_amended(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph)[:1])
        service.reject(proposal.id, [o.id for o in proposal.operations])

        with pytest.raises(ChangeProposalStateError, match="only an open"):
            service.amend(proposal.id, remove=[1])

    def test_an_empty_amendment_is_refused(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))

        with pytest.raises(ProposalValidationError, match="at least one"):
            service.amend(proposal.id)


class TestWithdraw:
    def test_withdrawing_rolls_back_what_it_applied_and_withdraws_the_rest(
        self, service, reverter, graph
    ):
        proposal = propose(service, graph, *nine_rewordings(graph))
        service.apply(proposal.id, [by_seq(proposal)[1].id])

        withdrawn = service.withdraw(proposal.id)

        assert withdrawn.status is ProposalStatus.WITHDRAWN
        assert reverter.reverted == [proposal.id]  # the rollback of what it applied
        ops = by_seq(withdrawn)
        assert ops[1].status is OperationStatus.APPLIED  # its outcome, now rolled back
        assert {ops[2].status, ops[3].status} == {OperationStatus.WITHDRAWN}
        assert ops[2].reason == WITHDRAWN_REASON

    def test_superseded_by_links_the_two(self, service, graph):
        old = propose(service, graph, *nine_rewordings(graph))
        new = propose(service, graph, *nine_rewordings(graph)[:1])

        service.withdraw(old.id, superseded_by=new.id, note="one more sentence")

        (link,) = service.links_of(old.id)
        assert (link.source_proposal_id, link.kind, link.target_proposal_id) == (
            new.id,
            ProposalLinkKind.SUPERSEDES,
            old.id,
        )
        assert link.note == "one more sentence"
        assert service.links_of(new.id) == [link]

    def test_only_an_open_proposal_is_withdrawn(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph)[:1])
        service.withdraw(proposal.id)

        with pytest.raises(ChangeProposalStateError, match="only an open"):
            service.withdraw(proposal.id)

    def test_a_proposal_cant_supersede_itself(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph)[:1])

        with pytest.raises(ChangeProposalStateError, match="itself"):
            service.withdraw(proposal.id, superseded_by=proposal.id)


class TestSupersedeOnPropose:
    def test_propose_withdraws_and_links_what_it_supersedes(self, service, graph):
        old = propose(service, graph, *nine_rewordings(graph))

        new = service.propose(
            graph["taxonomy"],
            "Rewordings, take two",
            nine_rewordings(graph),
            ProposalSource.MCP,
            supersedes=[old.id],
        )

        assert service.get(old.id).status is ProposalStatus.WITHDRAWN
        (link,) = service.links_of(new.id)
        assert (link.source_proposal_id, link.target_proposal_id) == (new.id, old.id)

    def test_only_open_proposals_of_the_same_taxonomy_are_superseded(
        self, service, ontology, graph
    ):
        closed = propose(service, graph, *nine_rewordings(graph)[:1])
        service.reject(closed.id, [o.id for o in closed.operations])

        with pytest.raises(ProposalValidationError) as raised:
            service.propose(
                graph["taxonomy"],
                "Take two",
                nine_rewordings(graph),
                ProposalSource.MCP,
                supersedes=[closed.id, "nope"],
            )

        codes = sorted(e.code for e in raised.value.errors)
        assert codes == ["invalid", "proposal_not_found"]
