"""
Unit tests (#1609): what reviewers record on decisions. An individual create
accepted with an edited class and/or title, a rejection reason code beside the
note, and the time the reviewer spent on each operation.
"""

import pytest

from domain.versioning.gold import DecisionKind
from domain.versioning.proposal_service import (
    MAX_REVIEW_MS,
    REVERTED_REASON,
    ProposalService,
)
from domain.versioning.proposals import (
    OperationDraft,
    OperationStatus,
    ProposalSource,
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


def create_study(graph, seq=1, **extra):
    return OperationDraft(
        seq=seq,
        op=T.CREATE,
        kind=K.INDIVIDUAL,
        ref="study",
        fields={"class_ids": [graph["room"]], "title": "Study"},
        evidence=[PASSAGE],
        **extra,
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


# ------------------------------------------------- edited individual creates


class TestEditedIndividualCreate:
    def test_a_class_edit_creates_it_with_the_new_class(self, service, graph, repo, proposals):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]

        applied = ops_of(
            service.apply(proposal.id, [op.id], edits={op.id: {"class_ids": [graph["kitchen"]]}})
        )[1]

        assert applied.status is OperationStatus.APPLIED
        individual = repo.get_individual(applied.result_entity_id)
        assert individual.class_ids == [graph["kitchen"]] and individual.title == "Study"
        assert applied.fields == {"class_ids": [graph["room"]], "title": "Study"}
        assert applied.applied_fields == {"class_ids": [graph["kitchen"]], "title": "Study"}
        [decision] = proposals.decisions
        assert decision.decision is DecisionKind.APPLIED_WITH_EDITS
        assert decision.proposed["fields"]["class_ids"] == [graph["room"]]
        assert decision.applied_fields["class_ids"] == [graph["kitchen"]]
        assert decision.result_entity_id == applied.result_entity_id

    def test_a_title_edit(self, service, graph, repo, proposals):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]

        applied = ops_of(service.apply(proposal.id, [op.id], edits={op.id: {"title": "Library"}}))[
            1
        ]

        individual = repo.get_individual(applied.result_entity_id)
        assert individual.title == "Library" and individual.class_ids == [graph["room"]]
        [decision] = proposals.decisions
        assert decision.decision is DecisionKind.APPLIED_WITH_EDITS
        assert decision.proposed["fields"]["title"] == "Study"
        assert decision.applied_fields == {"class_ids": [graph["room"]], "title": "Library"}

    def test_its_passages_are_recorded_as_for_an_unedited_create(self, service, graph, sources):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]

        applied = ops_of(service.apply(proposal.id, [op.id], edits={op.id: {"title": "Library"}}))[
            1
        ]

        [source] = sources.list_for_entity(applied.result_entity_id)
        assert (source.source_id, source.start, source.end) == (SOURCE, 0, 5)
        assert (source.proposal_id, source.op_seq) == (proposal.id, 1)

    @pytest.mark.parametrize(
        ("edit", "message"),
        [
            ({"description": "A room for reading"}, "sets only title and class_ids"),
            ({"title": "Library", "data_properties": {}}, "sets only title and class_ids"),
            ({"title": "  "}, "non-empty text"),
            ({"title": 3}, "non-empty text"),
            ({"class_ids": []}, "non-empty list"),
            ({"class_ids": "room"}, "non-empty list"),
            ({"class_ids": ["$other"]}, r"\$ref"),
            ({}, "at least one field"),
        ],
    )
    def test_a_misplaced_edit_applies_nothing(self, service, graph, proposals, edit, message):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)

        with pytest.raises(ValueError, match=message):
            service.apply(proposal.id, [ops[1].id, ops[2].id], edits={ops[1].id: edit})

        stored = ops_of(proposals.get(proposal.id))
        assert all(o.status is OperationStatus.PENDING for o in stored.values())
        assert proposals.decisions == []

    def test_an_unknown_class_fails_only_that_operation(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]

        failed = service.apply(proposal.id, [op.id], edits={op.id: {"class_ids": ["nope"]}})

        [outcome] = failed.operations
        assert outcome.status is OperationStatus.FAILED
        assert outcome.reason.startswith("invalid_edit:")
        assert outcome.applied_fields is None
        assert proposals.decisions == []
        # applied again without the edit, it applies as proposed
        applied = service.apply(proposal.id, [op.id]).operations[0]
        assert applied.status is OperationStatus.APPLIED and applied.applied_fields is None
        assert [d.decision for d in proposals.decisions] == [DecisionKind.APPLIED]

    def test_a_class_of_another_taxonomy_fails_invalid_edit(self, service, graph, ontology):
        elsewhere = ontology.create_taxonomy(title="Garden")
        scheme = ontology.create_scheme(taxonomy_id=elsewhere.id, title="Plants")
        tree = ontology.create_class(scheme.id, "Tree")
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]

        [outcome] = service.apply(
            proposal.id, [op.id], edits={op.id: {"class_ids": [tree.id]}}
        ).operations

        assert outcome.status is OperationStatus.FAILED
        assert outcome.reason.startswith("invalid_edit:")
        assert "taxonomy" in outcome.reason

    def test_an_edit_with_an_existing_alternative_is_refused(self, service, graph, proposals):
        near = {"kind": "existing", "entity_id": graph["den"], "similarity": 0.9}
        proposal = propose(service, graph, create_study(graph, alternatives=[near]))
        op = proposal.operations[0]

        with pytest.raises(ValueError, match="takes no edit"):
            service.apply(
                proposal.id,
                [op.id],
                edits={op.id: {"title": "Library"}},
                chosen_alternatives={op.id: {"kind": "existing", "entity_id": graph["den"]}},
            )
        assert proposals.get(proposal.id).operations[0].status is OperationStatus.PENDING

    def test_a_relationship_by_ref_to_it_still_applies(self, service, graph, repo):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)

        applied = ops_of(
            service.apply(
                proposal.id,
                [ops[1].id, ops[2].id],
                edits={ops[1].id: {"class_ids": [graph["kitchen"]]}},
            )
        )

        assert applied[2].status is OperationStatus.APPLIED
        edge = repo.get_relationship(applied[2].result_entity_id)
        assert edge.source_id == applied[1].result_entity_id

    def test_a_relationship_by_ref_keeps_its_domain_and_range_check(self, service, graph):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)

        applied = ops_of(
            service.apply(
                proposal.id,
                [ops[1].id, ops[2].id],
                # A Place is not a Room: "near" no longer fits the edited individual
                edits={ops[1].id: {"class_ids": [graph["place"]]}},
            )
        )

        assert applied[1].status is OperationStatus.APPLIED
        assert applied[2].status is OperationStatus.FAILED
        assert applied[2].reason.startswith("domain_range_mismatch:")

    def _study_on_floor(self, service, graph, ontology):
        """A Room individual proposed with a value of Room's "floor" attribute."""
        ontology.create_attribute_definition(graph["room"], "floor", "Floor", "integer")
        draft = create_study(graph)
        draft.fields["data_properties"] = {"floor": 2}
        return propose(service, graph, draft)

    def test_an_edited_class_lacking_a_proposed_attribute_fails_invalid_edit(
        self, service, graph, ontology, repo, proposals
    ):
        proposal = self._study_on_floor(service, graph, ontology)
        op = proposal.operations[0]
        before = len(repo.list_individuals(limit=None))

        [outcome] = service.apply(
            proposal.id, [op.id], edits={op.id: {"class_ids": [graph["place"]]}}
        ).operations

        assert outcome.status is OperationStatus.FAILED
        assert outcome.reason.startswith("invalid_edit:") and "floor" in outcome.reason
        assert outcome.result_entity_id is None and outcome.applied_fields is None
        assert len(repo.list_individuals(limit=None)) == before
        assert proposals.decisions == []

    def test_an_edited_class_with_the_proposed_attribute_stores_its_value(
        self, service, graph, ontology, repo
    ):
        proposal = self._study_on_floor(service, graph, ontology)
        ontology.create_attribute_definition(graph["place"], "floor", "Floor", "integer")
        op = proposal.operations[0]

        [outcome] = service.apply(
            proposal.id, [op.id], edits={op.id: {"class_ids": [graph["place"]]}}
        ).operations

        assert outcome.status is OperationStatus.APPLIED
        individual = repo.get_individual(outcome.result_entity_id)
        assert individual.class_ids == [graph["place"]]
        assert {v.property_identifier: v.value for v in individual.data_properties} == {"floor": 2}
        assert outcome.applied_fields["data_properties"] == {"floor": 2}


# ------------------------------------------------------- reason code


class TestRejectionReasonCode:
    def test_it_is_stored_on_the_operation_and_its_decision(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)

        rejected = service.reject(
            proposal.id,
            [ops[1].id, ops[2].id],
            note="only an example",
            reason_code=RejectionReason.MENTIONED_ONLY,
        )

        assert all(o.reason_code is RejectionReason.MENTIONED_ONLY for o in rejected.operations)
        assert all(o.reason == "only an example" for o in rejected.operations)
        assert [d.reason_code for d in proposals.decisions] == [RejectionReason.MENTIONED_ONLY] * 2
        assert all(d.reason == "only an example" for d in proposals.decisions)

    def test_a_code_given_as_text_is_read_as_the_enum(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph))

        service.reject(proposal.id, [proposal.operations[0].id], reason_code="too_generic")

        assert proposals.decisions[0].reason_code is RejectionReason.TOO_GENERIC

    def test_an_unknown_code_is_refused(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph))

        with pytest.raises(ValueError):
            service.reject(proposal.id, [proposal.operations[0].id], reason_code="boring")
        assert proposals.decisions == []

    def test_without_one_none_is_recorded(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph))

        rejected = service.reject(proposal.id, [proposal.operations[0].id], note="no")

        assert rejected.operations[0].reason_code is None
        assert proposals.decisions[0].reason_code is None

    def test_an_applied_decision_has_none(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph))

        service.apply(proposal.id, [proposal.operations[0].id])

        assert proposals.decisions[0].reason_code is None

    def test_a_revert_rejects_what_is_undecided_without_a_code(self, service, graph):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)
        service.apply(proposal.id, [ops[1].id])

        service.revert(proposal.id)

        closed = ops_of(service.get(proposal.id))[2]
        assert closed.status is OperationStatus.REJECTED and closed.reason == REVERTED_REASON
        assert closed.reason_code is None


# ------------------------------------------------------- review time


class TestReviewTime:
    def test_apply_records_it_on_each_decision(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)

        service.apply(proposal.id, [ops[1].id, ops[2].id], review_ms={ops[1].id: 4200})

        times = {d.seq: d.review_ms for d in proposals.decisions}
        assert times == {1: 4200, 2: None}

    def test_the_largest_one_is_kept(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]

        service.reject(proposal.id, [op.id], review_ms={op.id: MAX_REVIEW_MS})

        assert proposals.decisions[0].review_ms == MAX_REVIEW_MS

    def test_reject_records_it_on_each_decision(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)

        service.reject(
            proposal.id,
            [ops[1].id, ops[2].id],
            reason_code=RejectionReason.NOT_IN_TEXT,
            review_ms={ops[1].id: 0, ops[2].id: 1500},
        )

        assert {d.seq: d.review_ms for d in proposals.decisions} == {1: 0, 2: 1500}

    def test_it_is_not_kept_on_the_operation(self, service, graph, proposals):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]

        applied = service.apply(proposal.id, [op.id], review_ms={op.id: 900})

        assert not hasattr(applied.operations[0], "review_ms")
        assert proposals.decisions[0].review_ms == 900

    @pytest.mark.parametrize("action", ["apply", "reject"])
    def test_one_for_an_operation_not_in_the_call_changes_nothing(
        self, service, graph, proposals, action
    ):
        proposal = propose(service, graph, create_study(graph), near_den(graph))
        ops = ops_of(proposal)

        with pytest.raises(ValueError, match="review_ms for operations not being"):
            getattr(service, action)(proposal.id, [ops[1].id], review_ms={ops[2].id: 10})

        stored = ops_of(proposals.get(proposal.id))
        assert all(o.status is OperationStatus.PENDING for o in stored.values())
        assert proposals.decisions == []

    @pytest.mark.parametrize("value", [-1, 1.5, True, "10", MAX_REVIEW_MS + 1, 10**20])
    @pytest.mark.parametrize("action", ["apply", "reject"])
    def test_a_negative_or_non_integer_one_changes_nothing(
        self, service, graph, proposals, action, value
    ):
        proposal = propose(service, graph, create_study(graph))
        op = proposal.operations[0]

        with pytest.raises(ValueError, match="non-negative integer"):
            getattr(service, action)(proposal.id, [op.id], review_ms={op.id: value})

        assert proposals.get(proposal.id).operations[0].status is OperationStatus.PENDING
        assert proposals.decisions == []
