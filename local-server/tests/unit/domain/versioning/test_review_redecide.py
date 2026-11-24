"""
Unit tests: changing a decision while a review is open. Decided individual and
relationship creates reopen (with the applied relationships that use them) so
they can be decided again, and a relationship create accepts with an edited
type or ends.
"""

import pytest

from domain.versioning.exceptions import ChangeProposalStateError
from domain.versioning.gold import DecisionFilter, DecisionKind
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import (
    OperationDraft,
    OperationStatus,
    ProposalSource,
    ProposalStatus,
    RejectionReason,
)
from tests.fakes.fake_entity_source_repository import FakeEntitySourceRepository
from tests.unit.domain.versioning.test_proposal_service import (  # noqa: F401 - fixtures
    K,
    T,
    graph,
    ontology,
    proposals,
    publisher,
    repo,
    reverter,
)

SOURCE = "src-notes"
PASSAGE = {"source_id": SOURCE, "page": 1, "start": 0, "end": 5, "quote": "Study"}


@pytest.fixture()
def sources():
    return FakeEntitySourceRepository()


@pytest.fixture()
def service(proposals, ontology, repo, reverter, sources):
    return ProposalService(proposals, ontology, repo, reverter, entity_sources=sources)


def create_study(graph, seq=1):
    return OperationDraft(
        seq=seq,
        op=T.CREATE,
        kind=K.INDIVIDUAL,
        ref="study",
        fields={"class_ids": [graph["room"]], "title": "Study"},
        evidence=[PASSAGE],
    )


def near_den(graph, seq=2):
    return OperationDraft(
        seq=seq,
        op=T.CREATE,
        kind=K.RELATIONSHIP,
        fields={
            "source_id": "$study",
            "target_id": graph["den"],
            "property_definition_id": graph["near"],
        },
    )


def propose(service, graph, *drafts):
    return service.propose(graph["taxonomy"], "Extracted", list(drafts), ProposalSource.PIPELINE)


def ops_of(proposal):
    return {o.seq: o for o in proposal.operations}


def standing(proposals, proposal_id):
    return proposals.list_decisions(DecisionFilter(proposal_id=proposal_id))


class TestReopen:
    def test_a_rejected_operation_reopens_and_its_decision_is_superseded(
        self, service, graph, proposals, reverter
    ):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]
        service.reject(proposal.id, [op.id], "no", reason_code=RejectionReason.TOO_GENERIC)

        reopened = ops_of(service.reopen(proposal.id, [op.id]))[1]

        assert reopened.status is OperationStatus.PENDING
        assert reopened.reason is None and reopened.reason_code is None
        assert standing(proposals, proposal.id) == []
        # A rejection changed nothing, so nothing is undone.
        assert reverter.entities == []

    def test_an_applied_create_is_undone_and_can_take_another_class(
        self, service, graph, proposals, reverter, sources
    ):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]
        created = ops_of(service.apply(proposal.id, [op.id]))[1].result_entity_id
        assert sources.list_for_entity(created)

        reopened = ops_of(service.reopen(proposal.id, [op.id]))[1]

        assert reverter.entities == [[created]]
        assert reopened.status is OperationStatus.PENDING
        assert reopened.result_entity_id is None and reopened.applied_fields is None
        assert sources.rows == []
        [old] = proposals.list_decisions(
            DecisionFilter(proposal_id=proposal.id, include_superseded=True)
        )
        assert old.superseded_at is not None and old.superseded_by == "user"

        # Decided again: the latest decision is the one that stands.
        again = ops_of(
            service.apply(proposal.id, [op.id], edits={op.id: {"class_ids": [graph["kitchen"]]}})
        )[1]
        assert again.status is OperationStatus.APPLIED
        [latest] = standing(proposals, proposal.id)
        assert latest.decision is DecisionKind.APPLIED_WITH_EDITS
        assert latest.applied_fields["class_ids"] == [graph["kitchen"]]

    def test_an_accepted_create_can_be_rejected_instead(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]
        service.apply(proposal.id, [op.id])

        service.reopen(proposal.id, [op.id])
        rejected = ops_of(
            service.reject(proposal.id, [op.id], "not here", reason_code=RejectionReason.OTHER)
        )[1]

        assert rejected.status is OperationStatus.REJECTED
        [latest] = standing(proposals, proposal.id)
        assert latest.decision is DecisionKind.REJECTED

    def test_applied_relationships_that_use_it_reopen_with_it(self, service, graph, reverter):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)
        applied = ops_of(service.apply(proposal.id, [ops[1].id, ops[2].id]))
        individual, relationship = applied[1].result_entity_id, applied[2].result_entity_id

        reopened = ops_of(service.reopen(proposal.id, [ops[1].id]))

        assert reopened[1].status is OperationStatus.PENDING
        assert reopened[2].status is OperationStatus.PENDING
        assert sorted(reverter.entities[0]) == sorted([individual, relationship])

    def test_a_relationship_reopens_alone(self, service, graph, reverter):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)
        applied = ops_of(service.apply(proposal.id, [ops[1].id, ops[2].id]))

        reopened = ops_of(service.reopen(proposal.id, [ops[2].id]))

        assert reopened[1].status is OperationStatus.APPLIED
        assert reopened[2].status is OperationStatus.PENDING
        assert reverter.entities == [[applied[2].result_entity_id]]

    def test_a_done_proposal_is_open_again(self, service, graph):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]
        assert service.apply(proposal.id, [op.id]).status is ProposalStatus.DONE

        assert service.reopen(proposal.id, [op.id]).status is ProposalStatus.OPEN

    def test_an_undecided_operation_is_a_state_error(self, service, graph):
        proposal = propose(service, graph, create_study(graph))

        with pytest.raises(ChangeProposalStateError, match="not decided"):
            service.reopen(proposal.id, [proposal.operations[0].id])

    def test_a_reverted_proposal_is_a_state_error(self, service, graph):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]
        service.apply(proposal.id, [op.id])
        service.revert(proposal.id)

        with pytest.raises(ChangeProposalStateError, match="reverted"):
            service.reopen(proposal.id, [op.id])

    def test_an_unknown_operation_is_a_value_error(self, service, graph):
        proposal = propose(service, graph, create_study(graph))

        with pytest.raises(ValueError, match="no operations"):
            service.reopen(proposal.id, ["nope"])

    def test_only_individual_and_relationship_creates_reopen(self, service, graph):
        proposal = propose(
            service,
            graph,
            OperationDraft(
                seq=1,
                op=T.UPDATE,
                kind=K.CLASS,
                target_id=graph["room"],
                fields={"description": "Any room"},
            ),
        )
        op = proposal.operations[0]
        service.apply(proposal.id, [op.id])

        with pytest.raises(ValueError, match="only an individual or relationship create"):
            service.reopen(proposal.id, [op.id])


class TestEditedRelationshipCreate:
    def test_another_end_applies_and_is_recorded(self, service, graph, repo, proposals, ontology):
        study = ontology.create_individual(graph["room"], "Study")
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        op = ops_of(proposal)[2]
        # Its proposed source is a $ref to a create left undecided; the edit names another.
        applied = ops_of(
            service.apply(proposal.id, [op.id], edits={op.id: {"source_id": study.id}})
        )[2]

        assert applied.status is OperationStatus.APPLIED, applied.reason
        relationship = repo.get_relationship(applied.result_entity_id)
        assert relationship.source_id == study.id and relationship.target_id == graph["den"]
        assert applied.applied_fields["source_id"] == study.id
        [decision] = proposals.decisions
        assert decision.decision is DecisionKind.APPLIED_WITH_EDITS
        assert decision.proposed["fields"]["source_id"] == "$study"

    def test_another_type_applies(self, service, graph, repo, ontology):
        study = ontology.create_individual(graph["room"], "Study")
        beside = ontology.create_property_definition(
            "beside", "beside", domain_class_id=graph["room"], range_class_id=graph["room"]
        )
        proposal = propose(
            service,
            graph,
            OperationDraft(
                seq=1,
                op=T.CREATE,
                kind=K.RELATIONSHIP,
                fields={
                    "source_id": study.id,
                    "target_id": graph["den"],
                    "property_definition_id": graph["near"],
                },
            ),
        )
        op = proposal.operations[0]

        applied = ops_of(
            service.apply(
                proposal.id, [op.id], edits={op.id: {"property_definition_id": beside.id}}
            )
        )[1]

        assert applied.status is OperationStatus.APPLIED, applied.reason
        assert repo.get_relationship(applied.result_entity_id).property_definition_id == beside.id

    def test_an_end_outside_the_types_domain_fails_that_operation(self, service, graph, ontology):
        elsewhere = ontology.create_individual(graph["place"], "Garden")
        study = ontology.create_individual(graph["room"], "Study")
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        op = ops_of(proposal)[2]

        applied = ops_of(
            service.apply(
                proposal.id,
                [op.id],
                edits={op.id: {"source_id": study.id, "target_id": elsewhere.id}},
            )
        )[2]

        assert applied.status is OperationStatus.FAILED
        assert applied.reason.startswith("domain_range_mismatch")

    def test_a_missing_end_is_an_invalid_edit(self, service, graph):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        op = ops_of(proposal)[2]

        applied = ops_of(
            service.apply(proposal.id, [op.id], edits={op.id: {"source_id": "no-such"}})
        )[2]

        assert applied.status is OperationStatus.FAILED
        assert applied.reason.startswith("invalid_edit")

    def test_an_edit_of_another_field_is_a_value_error(self, service, graph):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        op = ops_of(proposal)[2]

        with pytest.raises(ValueError, match="sets only property_definition_id"):
            service.apply(proposal.id, [op.id], edits={op.id: {"title": "x"}})

    def test_an_edit_naming_a_ref_is_a_value_error(self, service, graph):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        op = ops_of(proposal)[2]

        with pytest.raises(ValueError, match=r"\$ref"):
            service.apply(proposal.id, [op.id], edits={op.id: {"target_id": "$study"}})
