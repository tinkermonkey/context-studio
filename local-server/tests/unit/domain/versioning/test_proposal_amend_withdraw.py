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
    """Nine operation drafts of the kind #1624 describes: wording changes, pending review."""
    return [
        draft(1, T.UPDATE, K.CLASS, graph["room"], description="A room in the house"),
        draft(2, T.UPDATE, K.CLASS, graph["kitchen"], description="Where food is made"),
        draft(3, T.UPDATE, K.CLASS, graph["place"], description="Somewhere"),
        draft(4, T.UPDATE, K.CLASS, graph["room"], title="Room"),
        draft(5, T.UPDATE, K.CLASS, graph["kitchen"], title="Kitchen"),
        draft(6, T.UPDATE, K.CLASS, graph["place"], title="Place"),
        draft(7, T.UPDATE, K.SCHEME, graph["vocab"], description="The house's words"),
        draft(8, T.UPDATE, K.SCHEME, graph["other"], description="The house's records"),
        draft(9, T.UPDATE, K.TAXONOMY, graph["taxonomy"], description="Our home"),
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
            add=[
                draft(
                    10,
                    T.CREATE,
                    K.CLASS,
                    ref="hall",
                    concept_scheme_id=graph["vocab"],
                    title="Hall",
                )
            ],
            remove=[3],
        )

        ops = by_seq(service.get(amended.id))
        assert ops[10].status is OperationStatus.PENDING and ops[10].amended_at is not None
        assert ops[10].amendments == []
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
                replace=[draft(99, T.UPDATE, K.CLASS, graph["room"], description="x")],
                add=[draft(2, T.UPDATE, K.CLASS, graph["vocab"], title="x")],
            )

        codes = {(e.seq, e.code) for e in raised.value.errors}
        assert (99, "unknown_seq") in codes and (2, "invalid") in codes

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

    def test_a_replacement_conflicting_with_a_kept_operation_at_a_higher_seq_is_refused(
        self, service, graph
    ):
        """Review of #1728: seq 1 now changes what seq 2 already changes."""
        proposal = propose(service, graph, *nine_rewordings(graph))

        with pytest.raises(ProposalValidationError) as raised:
            service.amend(
                proposal.id,
                replace=[draft(1, T.UPDATE, K.CLASS, graph["kitchen"], description="Twice")],
            )

        assert [(e.seq, e.code) for e in raised.value.errors] == [(1, "conflicting_op")]

    def test_a_replacement_touching_what_a_kept_delete_removes_is_refused(self, service, graph):
        proposal = propose(
            service,
            graph,
            draft(1, T.UPDATE, K.CLASS, graph["room"], description="A room"),
            draft(2, T.DELETE, K.CLASS, graph["place"]),
        )

        with pytest.raises(ProposalValidationError) as raised:
            service.amend(
                proposal.id,
                replace=[draft(1, T.UPDATE, K.CLASS, graph["place"], description="Gone soon")],
            )

        assert [(e.seq, e.code) for e in raised.value.errors] == [(1, "conflicting_op")]

    def test_a_failed_operation_is_replaced_but_never_removed(self, service, proposals, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))
        failed = by_seq(proposal)[1]
        failed.status = OperationStatus.FAILED
        proposals.save_operations(proposal.id, [failed])

        with pytest.raises(ProposalValidationError) as raised:
            service.amend(proposal.id, remove=[1])
        amended = service.amend(
            proposal.id,
            replace=[draft(1, T.UPDATE, K.CLASS, graph["room"], description="Again")],
        )

        assert [(e.seq, e.code) for e in raised.value.errors] == [(1, "decided")]
        assert by_seq(amended)[1].status is OperationStatus.PENDING

    def test_the_replaced_version_keeps_every_proposer_set_field(self, service, graph):
        """Review of #1728: op, kind, target, ref, notes, replacement and alternatives too."""
        proposal = propose(service, graph, *nine_rewordings(graph))

        amended = service.amend(
            proposal.id,
            replace=[draft(3, T.UPDATE, K.CLASS, graph["place"], description="A spot")],
        )

        (earlier,) = by_seq(amended)[3].amendments
        assert {k: earlier[k] for k in ("op", "kind", "target_id", "ref", "fields")} == {
            "op": "update",
            "kind": "class",
            "target_id": graph["place"],
            "ref": None,
            "fields": {"description": "Somewhere"},
        }
        assert {"notes", "replacement", "alternatives", "scope", "amended_at"} <= set(earlier)

    def test_a_first_data_operation_resolves_the_proposals_dataset(self, service, graph):
        """Review of #1728: as propose does, a schema-only proposal takes its dataset."""
        proposal = propose(service, graph, *nine_rewordings(graph))
        assert proposal.dataset_id is None

        service.amend(
            proposal.id,
            add=[draft(10, T.CREATE, K.INDIVIDUAL, title="Pantry", class_ids=[graph["room"]])],
        )

        assert service.get(proposal.id).dataset_id is not None

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


class TestAWithdrawnProposalTakesNoDecisions:
    """Review of #1728: nothing is applied, rejected, reopened or added after a withdraw."""

    def test_apply_and_reject_are_refused(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))
        service.withdraw(proposal.id)
        first = by_seq(proposal)[1].id

        with pytest.raises(ChangeProposalStateError, match="withdrawn"):
            service.apply(proposal.id, [first])
        with pytest.raises(ChangeProposalStateError, match="withdrawn"):
            service.reject(proposal.id, [first])
        with pytest.raises(ChangeProposalStateError, match="withdrawn"):
            service.reopen(proposal.id, [first])
        with pytest.raises(ChangeProposalStateError, match="withdrawn"):
            service.revert(proposal.id)

    def test_a_removed_operation_is_never_applied(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))
        service.amend(proposal.id, remove=[2])

        with pytest.raises(ChangeProposalStateError, match="withdrawn"):
            service.apply(proposal.id, [by_seq(proposal)[2].id])


class TestApplyWhatWasRead:
    """Review of #1728: an operation amended since the reviewer read it is refused."""

    def test_an_amendment_since_the_read_is_refused(self, service, graph):
        proposal = propose(service, graph, *nine_rewordings(graph))
        seen = by_seq(proposal)[1]
        service.amend(
            proposal.id,
            replace=[draft(1, T.UPDATE, K.CLASS, graph["room"], description="Changed")],
        )

        with pytest.raises(ChangeProposalStateError, match="amended"):
            service.apply(proposal.id, [seen.id], amended_at={seen.id: seen.amended_at})

        current = by_seq(service.get(proposal.id))[1]
        applied = service.apply(
            proposal.id, [current.id], amended_at={current.id: current.amended_at}
        )
        assert by_seq(applied)[1].status is OperationStatus.APPLIED


class TestWithdrawSupersededBy:
    def test_the_replacement_must_be_on_the_same_taxonomy_and_standing(
        self, service, ontology, graph
    ):
        old = propose(service, graph, *nine_rewordings(graph))
        other = ontology.create_taxonomy(title="Garden")
        elsewhere = service.propose(
            other.id,
            "Garden",
            [draft(1, T.UPDATE, K.TAXONOMY, other.id, description="Green")],
            ProposalSource.USER,
        )
        gone = propose(service, graph, *nine_rewordings(graph)[:1])
        service.withdraw(gone.id)

        with pytest.raises(ChangeProposalStateError, match="another taxonomy"):
            service.withdraw(old.id, superseded_by=elsewhere.id)
        with pytest.raises(ChangeProposalStateError, match="withdrawn"):
            service.withdraw(old.id, superseded_by=gone.id)
        assert service.get(old.id).status is ProposalStatus.OPEN


class TestSupersedeOnPropose:
    def test_a_failed_withdraw_stores_nothing(self, proposals, ontology, repo, graph):
        """Review of #1728: withdraw first; if it fails, no new proposal exists."""
        from domain.versioning.exceptions import RevertConflictError
        from domain.versioning.proposal_service import ProposalService
        from tests.unit.domain.versioning.test_proposal_service import StubRevertService

        service = ProposalService(
            proposals, ontology, repo, StubRevertService(error=RevertConflictError("no", []))
        )
        old = propose(service, graph, *nine_rewordings(graph))

        with pytest.raises(RevertConflictError):
            service.propose(
                graph["taxonomy"],
                "Take two",
                nine_rewordings(graph),
                ProposalSource.MCP,
                supersedes=[old.id],
            )

        assert [p.id for p in proposals._proposals.values()] == [old.id]
        assert service.get(old.id).status is ProposalStatus.OPEN

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
