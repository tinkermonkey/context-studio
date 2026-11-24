"""
Unit tests (#1615): two pipelines' proposals for the same source, paired and
decided once for both.
"""

import threading

import pytest

from domain.pipelines.proposal_comparison import (
    ComparisonGroup,
    InvalidPairDecisionError,
    PairDecision,
    PairState,
    ProposalComparisonService,
    ProposalsNotComparableError,
    SampleTooSmallError,
    SampleUncheckedError,
    Verdict,
    pair_operations,
    sample_ids,
)
from domain.pipelines.source_proposals import SUPERSEDED_REASON
from domain.versioning.exceptions import ChangeProposalStateError
from domain.versioning.gold import DecisionKind
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import (
    CopyOutcome,
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


@pytest.fixture()
def service(proposals, ontology, repo, reverter):
    return ProposalService(
        proposals, ontology, repo, reverter, entity_sources=FakeEntitySourceRepository()
    )


@pytest.fixture()
def comparisons(service, repo):
    return ProposalComparisonService(service, repo)


def passage(start=0):
    return {"source_id": SOURCE, "page": 1, "start": start, "end": start + 5, "quote": "words"}


def create(seq, title, class_id, ref=None, evidence=True, alternatives=()):
    return OperationDraft(
        seq=seq,
        op=T.CREATE,
        kind=K.INDIVIDUAL,
        ref=ref,
        fields={"title": title, "class_ids": [class_id]},
        evidence=[passage(seq)] if evidence else [],
        alternatives=list(alternatives),
    )


def near(seq, source_ref, target_id, graph):
    return OperationDraft(
        seq=seq,
        op=T.CREATE,
        kind=K.RELATIONSHIP,
        fields={
            "source_id": f"${source_ref}",
            "target_id": target_id,
            "property_definition_id": graph["near"],
        },
    )


def extraction(service, graph, *drafts, source=SOURCE, implementation="single_call"):
    return service.propose(
        graph["taxonomy"],
        f"Extracted by {implementation}",
        list(drafts),
        ProposalSource.PIPELINE,
        client_metadata={
            "source_id": source,
            "pipeline": "individual_extraction",
            "origin": {
                "pipeline_type": "individual_extraction",
                "implementation_id": implementation,
                "configuration_ref": "c",
                "configuration_version": 1,
                "digest": "0123456789ab",
            },
        },
    )


def two(service, graph, drafts_a, drafts_b):
    a = extraction(service, graph, *drafts_a, implementation="single_call")
    b = extraction(service, graph, *drafts_b, implementation="find_then_type")
    return a, b


def by_seq(proposal):
    return {o.seq: o for o in proposal.operations}


def groups(pairs):
    return [
        (p.group, p.a.fields["title"] if p.a else None, p.b.fields["title"] if p.b else None)
        for p in pairs
    ]


# ---------------------------------------------------------------- pairing


class TestPairing:
    def test_titles_with_the_same_key_pair_and_agree_on_the_class(self, service, graph):
        a, b = two(
            service,
            graph,
            [create(1, "Screws", graph["room"]), create(2, "Hall", graph["room"])],
            [create(1, "screw", graph["room"]), create(2, "Hall", graph["kitchen"])],
        )

        assert groups(pair_operations(a, b)) == [
            (ComparisonGroup.SAME_CLASS, "Screws", "screw"),
            (ComparisonGroup.CLASS_DIFFERS, "Hall", "Hall"),
        ]

    def test_one_key_many_copies_pairs_same_class_first_then_by_seq(self, service, graph):
        a, b = two(
            service,
            graph,
            [
                create(1, "Study", graph["room"]),
                create(2, "Study", graph["kitchen"]),
                create(3, "Studies", graph["place"]),
            ],
            [create(1, "Study", graph["kitchen"]), create(2, "study", graph["room"])],
        )

        pairs = pair_operations(a, b)

        assert [(p.group, p.a.seq if p.a else None, p.b.seq if p.b else None) for p in pairs] == [
            (ComparisonGroup.SAME_CLASS, 1, 2),
            (ComparisonGroup.SAME_CLASS, 2, 1),
            (ComparisonGroup.ONLY_A, 3, None),
        ]

    def test_what_only_one_proposes(self, service, graph):
        a, b = two(
            service,
            graph,
            [create(1, "Pantry", graph["room"])],
            [create(1, "Larder", graph["room"])],
        )

        assert groups(pair_operations(a, b)) == [
            (ComparisonGroup.ONLY_A, "Pantry", None),
            (ComparisonGroup.ONLY_B, None, "Larder"),
        ]

    def test_only_individual_creates_the_pipeline_proposed_are_compared(
        self, service, graph, ontology
    ):
        a, b = two(
            service,
            graph,
            [
                create(1, "Study", graph["room"], ref="study"),
                near(2, "study", graph["den"], graph),
                OperationDraft(
                    seq=3,
                    op=T.UPDATE,
                    kind=K.INDIVIDUAL,
                    target_id=graph["den"],
                    fields={"description": "Cosy"},
                ),
            ],
            [create(1, "Study", graph["room"])],
        )
        a.operations[0].added_by_reviewer = True  # as if a reviewer had added it

        assert groups(pair_operations(a, b)) == [(ComparisonGroup.ONLY_B, None, "Study")]

    def test_pairs_and_their_order_are_the_same_every_time(self, service, graph):
        drafts_a = [create(n, f"Room {n}", graph["room"]) for n in range(1, 8)]
        drafts_b = [create(n, f"Room {8 - n}", graph["room"]) for n in range(1, 8)]
        a, b = two(service, graph, drafts_a, drafts_b)

        first = [p.pair_id for p in pair_operations(a, b)]

        assert first == [p.pair_id for p in pair_operations(a, b)]
        assert [p.a.seq for p in pair_operations(a, b)] == list(range(1, 8))

    def test_the_sample_is_stable_and_grows_by_its_prefix(self, service, graph):
        drafts = [create(n, f"Room {n}", graph["room"]) for n in range(1, 21)]
        a, b = two(service, graph, drafts, drafts)
        pairs = pair_operations(a, b)

        five = sample_ids(pairs, a.id, b.id, 5)

        assert five == sample_ids(pairs, a.id, b.id, 5)
        assert sample_ids(pairs, a.id, b.id, 8)[:5] == five
        assert len(set(five)) == 5
        assert sample_ids(pairs, a.id, b.id, 50) and len(sample_ids(pairs, a.id, b.id, 50)) == 20
        # Comparing B with A draws the same sample
        assert sample_ids(pairs, b.id, a.id, 5) == five


# ---------------------------------------------------------------- comparable


class TestComparable:
    def test_a_proposal_with_itself(self, service, graph, comparisons):
        a = extraction(service, graph, create(1, "Study", graph["room"]))

        with pytest.raises(ProposalsNotComparableError, match="another one"):
            comparisons.compare(a.id, a.id)

    def test_one_not_extracted_from_a_source(self, service, graph, comparisons):
        a = extraction(service, graph, create(1, "Study", graph["room"]))
        b = service.propose(
            graph["taxonomy"], "By hand", [create(1, "Study", graph["room"])], ProposalSource.USER
        )

        with pytest.raises(ProposalsNotComparableError, match="not an individual extraction"):
            comparisons.compare(a.id, b.id)

    def test_another_source(self, service, graph, comparisons):
        a = extraction(service, graph, create(1, "Study", graph["room"]))
        b = extraction(service, graph, create(1, "Study", graph["room"]), source="src-other")

        with pytest.raises(ProposalsNotComparableError, match="different sources"):
            comparisons.compare(a.id, b.id)

    def test_another_dataset(self, service, graph, comparisons, ontology):
        a = extraction(service, graph, create(1, "Study", graph["room"]))
        annex = ontology.create_dataset(graph["taxonomy"], "annex", "Annex")
        b = service.propose(
            graph["taxonomy"],
            "Annex",
            [create(1, "Study", graph["room"])],
            ProposalSource.PIPELINE,
            client_metadata={"source_id": SOURCE, "pipeline": "individual_extraction"},
            dataset_id=annex.id,
        )

        with pytest.raises(ProposalsNotComparableError, match="different datasets"):
            comparisons.compare(a.id, b.id)

    def test_another_taxonomy(self, service, graph, comparisons, ontology):
        garden = ontology.create_taxonomy(title="Garden")
        tree = ontology.create_class(ontology.create_scheme(garden.id, "Plants").id, "Tree")
        a = extraction(service, graph, create(1, "Study", graph["room"]))
        b = service.propose(
            garden.id,
            "Garden",
            [create(1, "Oak", tree.id)],
            ProposalSource.PIPELINE,
            client_metadata={"source_id": SOURCE, "pipeline": "individual_extraction"},
        )

        with pytest.raises(ProposalsNotComparableError, match="different taxonomies"):
            comparisons.compare(a.id, b.id)


# ---------------------------------------------------------------- verdicts


def decide(comparisons, a, b, verdict, a_op=None, b_op=None, **extra):
    return comparisons.decide(
        a.id,
        b.id,
        PairDecision(
            Verdict(verdict),
            a_operation_id=a_op.id if a_op else None,
            b_operation_id=b_op.id if b_op else None,
            **extra,
        ),
    )


def decisions_by_op(proposals):
    return {d.operation_id: d for d in proposals.decisions}


class TestVerdicts:
    def test_keep_lands_a_and_closes_b_as_its_duplicate(
        self, service, graph, comparisons, proposals, repo
    ):
        a, b = two(
            service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
        )
        op_a, op_b = a.operations[0], b.operations[0]

        result = decide(comparisons, a, b, "keep", op_a, op_b, review_ms=4000)

        assert result.outcome is CopyOutcome.LANDED
        landed, closed = by_seq(service.get(a.id))[1], by_seq(service.get(b.id))[1]
        assert landed.status is OperationStatus.APPLIED
        assert repo.get_individual(landed.result_entity_id).title == "Study"
        assert closed.status is OperationStatus.REJECTED
        assert closed.reason_code is RejectionReason.DUPLICATE
        assert closed.result_entity_id == landed.result_entity_id
        records = decisions_by_op(proposals)
        assert records[op_a.id].review_ms == 4000 and records[op_b.id].review_ms is None
        assert records[op_b.id].result_entity_id == landed.result_entity_id
        sampled = result.pair.pair_id in result.comparison.sample
        assert records[op_a.id].comparison == {
            "with_proposal_id": b.id,
            "with_operation_id": op_b.id,
            "verdict": "kept",
            "sample": sampled,
            "bulk": None,
        }
        assert records[op_b.id].comparison["verdict"] == "kept"
        assert records[op_b.id].comparison["with_operation_id"] == op_a.id
        assert result.pair.state is PairState.DECIDED

    def test_a_class_lands_a_with_its_class(self, service, graph, comparisons, proposals, repo):
        a, b = two(
            service,
            graph,
            [create(1, "Hall", graph["room"])],
            [create(1, "Hall", graph["kitchen"])],
        )
        op_a, op_b = a.operations[0], b.operations[0]

        decide(comparisons, a, b, "a_class", op_a, op_b)

        landed = by_seq(service.get(a.id))[1]
        assert repo.get_individual(landed.result_entity_id).class_ids == [graph["room"]]
        records = decisions_by_op(proposals)
        assert records[op_a.id].comparison["verdict"] == "kept"
        assert records[op_b.id].comparison["verdict"] == "class_changed"
        assert records[op_b.id].decision is DecisionKind.REJECTED

    def test_b_class_lands_b_with_its_class(self, service, graph, comparisons, proposals, repo):
        a, b = two(
            service,
            graph,
            [create(1, "Hall", graph["room"])],
            [create(1, "Hall", graph["kitchen"])],
        )
        op_a, op_b = a.operations[0], b.operations[0]

        decide(comparisons, a, b, "b_class", op_a, op_b, review_ms=900)

        landed, closed = by_seq(service.get(b.id))[1], by_seq(service.get(a.id))[1]
        assert repo.get_individual(landed.result_entity_id).class_ids == [graph["kitchen"]]
        assert closed.result_entity_id == landed.result_entity_id
        records = decisions_by_op(proposals)
        assert records[op_b.id].comparison["verdict"] == "kept"
        assert records[op_b.id].review_ms == 900
        assert records[op_a.id].comparison["verdict"] == "class_changed"
        assert records[op_a.id].review_ms is None

    def test_not_element_rejects_both_with_the_reason(self, service, graph, comparisons, proposals):
        a, b = two(
            service,
            graph,
            [create(1, "Hall", graph["room"])],
            [create(1, "Hall", graph["kitchen"])],
        )
        op_a, op_b = a.operations[0], b.operations[0]

        result = decide(
            comparisons,
            a,
            b,
            "not_element",
            op_a,
            op_b,
            reason_code=RejectionReason.MENTIONED_ONLY,
            review_ms=300,
        )

        assert result.outcome is CopyOutcome.REJECTED
        for proposal_id in (a.id, b.id):
            op = service.get(proposal_id).operations[0]
            assert (op.status, op.reason_code) == (
                OperationStatus.REJECTED,
                RejectionReason.MENTIONED_ONLY,
            )
            assert op.result_entity_id is None
        records = decisions_by_op(proposals)
        assert records[op_a.id].review_ms == 300 and records[op_b.id].review_ms is None
        assert {r.comparison["verdict"] for r in records.values()} == {"not_element"}

    def test_only_in_a_keep_names_no_other_copy(self, service, graph, comparisons, proposals):
        a, b = two(
            service,
            graph,
            [create(1, "Pantry", graph["room"])],
            [create(1, "Larder", graph["room"])],
        )

        decide(comparisons, a, b, "keep", a.operations[0])

        record = decisions_by_op(proposals)[a.operations[0].id].comparison
        assert record == {
            "with_proposal_id": b.id,
            "with_operation_id": None,
            "verdict": "kept",
            "sample": False,
            "bulk": None,
        }
        assert service.get(b.id).operations[0].status is OperationStatus.PENDING

    def test_only_in_b_keep_lands_b(self, service, graph, comparisons):
        a, b = two(
            service,
            graph,
            [create(1, "Pantry", graph["room"])],
            [create(1, "Larder", graph["room"])],
        )

        result = decide(comparisons, a, b, "keep", b_op=b.operations[0])

        assert result.outcome is CopyOutcome.LANDED
        assert service.get(b.id).operations[0].status is OperationStatus.APPLIED

    def test_a_failed_landing_leaves_the_copy_pending(self, service, graph, comparisons):
        # "Den" is already a Room in the dataset
        a, b = two(
            service, graph, [create(1, "Den", graph["room"])], [create(1, "Den", graph["room"])]
        )

        result = decide(comparisons, a, b, "keep", a.operations[0], b.operations[0])

        assert result.outcome is CopyOutcome.FAILED and "already exists" in result.failure_reason
        assert service.get(a.id).operations[0].status is OperationStatus.FAILED
        assert service.get(b.id).operations[0].status is OperationStatus.PENDING
        assert result.pair.state is PairState.FAILED

    def test_an_already_applied_landing_copy_is_reused(self, service, graph, comparisons):
        a, b = two(
            service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
        )
        applied = service.apply(a.id, [a.operations[0].id]).operations[0]

        result = decide(comparisons, a, b, "keep", a.operations[0], b.operations[0])

        assert result.outcome is CopyOutcome.LANDED
        closed = service.get(b.id).operations[0]
        assert closed.result_entity_id == applied.result_entity_id

    def test_a_decided_copy_refuses_and_changes_nothing(self, service, graph, comparisons):
        a, b = two(
            service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
        )
        service.reject(b.id, [b.operations[0].id], note="no")

        with pytest.raises(ChangeProposalStateError, match="already rejected"):
            decide(comparisons, a, b, "keep", a.operations[0], b.operations[0])

        assert service.get(a.id).operations[0].status is OperationStatus.PENDING

    def test_a_reverted_proposal_refuses(self, service, graph, comparisons):
        a, b = two(
            service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
        )
        service.revert(b.id)

        with pytest.raises(ChangeProposalStateError):
            decide(comparisons, a, b, "keep", a.operations[0])

    def test_a_near_match_lands_as_the_existing_individual(self, service, graph, comparisons):
        match = {"kind": "existing", "entity_id": graph["den"], "similarity": 0.9}
        a, b = two(
            service,
            graph,
            [create(1, "The den", graph["room"], alternatives=[match])],
            [create(1, "The den", graph["room"])],
        )

        result = decide(
            comparisons,
            a,
            b,
            "keep",
            a.operations[0],
            b.operations[0],
            match_entity_id=graph["den"],
        )

        assert result.outcome is CopyOutcome.LANDED
        assert service.get(a.id).operations[0].result_entity_id == graph["den"]
        assert service.get(b.id).operations[0].result_entity_id == graph["den"]

    @pytest.mark.parametrize(
        ("verdict", "sides", "extra", "message"),
        [
            ("keep", "ab", {}, "different classes"),
            ("a_class", "a", {}, "Name both copies"),
            ("keep", "b", {}, "Name both copies"),
            ("a_class", "ab", {"reason_code": RejectionReason.OTHER}, "only for not_element"),
            ("b_class", "ab", {"match_entity_id": "nope"}, "not a near match"),
            ("not_element", "ab", {"match_entity_id": "nope"}, "only for an element"),
            ("keep", "", {}, "Name the A or the B"),
        ],
    )
    def test_a_malformed_decision_changes_nothing(
        self, service, graph, comparisons, proposals, verdict, sides, extra, message
    ):
        a, b = two(
            service,
            graph,
            [create(1, "Hall", graph["room"])],
            [create(1, "Hall", graph["kitchen"])],
        )

        with pytest.raises(InvalidPairDecisionError, match=message):
            decide(
                comparisons,
                a,
                b,
                verdict,
                a.operations[0] if "a" in sides else None,
                b.operations[0] if "b" in sides else None,
                **extra,
            )
        assert proposals.decisions == []

    def test_operations_that_are_not_a_pair(self, service, graph, comparisons):
        a, b = two(
            service,
            graph,
            [create(1, "Pantry", graph["room"], ref="x"), near(2, "x", graph["den"], graph)],
            [create(1, "Larder", graph["room"])],
        )

        with pytest.raises(InvalidPairDecisionError, match="not one pair"):
            decide(comparisons, a, b, "keep", a.operations[0], b.operations[0])
        with pytest.raises(InvalidPairDecisionError, match="not an individual create"):
            decide(comparisons, a, b, "keep", a.operations[1])


# ---------------------------------------------------------------- $ref follows


class TestRefFollowsTheDuplicate:
    def test_a_relationship_to_the_closed_copy_points_at_the_landed_one(
        self, service, graph, comparisons, repo
    ):
        a, b = two(
            service,
            graph,
            [create(1, "Study", graph["room"])],
            [create(1, "Study", graph["room"], ref="study"), near(2, "study", graph["den"], graph)],
        )
        decide(comparisons, a, b, "keep", a.operations[0], b.operations[0])

        relationship = by_seq(service.apply(b.id, [by_seq(b)[2].id]))[2]

        assert relationship.status is OperationStatus.APPLIED
        landed = service.get(a.id).operations[0].result_entity_id
        assert repo.get_relationship(relationship.result_entity_id).source_id == landed

    def test_not_an_element_still_fails_it(self, service, graph, comparisons):
        a, b = two(
            service,
            graph,
            [create(1, "Study", graph["room"])],
            [create(1, "Study", graph["room"], ref="study"), near(2, "study", graph["den"], graph)],
        )
        decide(comparisons, a, b, "not_element", a.operations[0], b.operations[0])

        relationship = by_seq(service.apply(b.id, [by_seq(b)[2].id]))[2]

        assert relationship.status is OperationStatus.FAILED
        assert relationship.reason.startswith("unresolved_ref:")

    def test_a_duplicate_rejected_by_hand_still_fails_it(self, service, graph):
        b = extraction(
            service,
            graph,
            create(1, "Study", graph["room"], ref="study"),
            near(2, "study", graph["den"], graph),
        )
        service.reject(b.id, [by_seq(b)[1].id], reason_code=RejectionReason.DUPLICATE)

        relationship = by_seq(service.apply(b.id, [by_seq(b)[2].id]))[2]

        assert relationship.reason.startswith("unresolved_ref:")


# ---------------------------------------------------------------- accept the rest


def rooms(graph, count, start=1):
    return [create(n, f"Room {n}", graph["room"]) for n in range(start, start + count)]


def decide_sample(comparisons, a, b, sample_size=10, not_element=0):
    """Decide every pair in the sample: keep, the first not_element ones rejected."""
    comparison = comparisons.compare(a.id, b.id, sample_size)
    sample = [p for p in comparison.pairs if p.pair_id in comparison.sample]
    for n, pair in enumerate(sample):
        if n < not_element:
            decide(
                comparisons,
                a,
                b,
                "not_element",
                pair.a,
                pair.b,
                reason_code=RejectionReason.TOO_GENERIC,
            )
        else:
            decide(comparisons, a, b, "keep", pair.a, pair.b)
    return comparison, sample


class TestAcceptTheRest:
    def test_refused_while_a_sample_pair_is_open(self, service, graph, comparisons):
        a, b = two(service, graph, rooms(graph, 12), rooms(graph, 12))

        with pytest.raises(SampleUncheckedError, match="10 of the 10 sample pairs"):
            comparisons.accept_rest(a.id, b.id)

    @pytest.mark.parametrize(("agreements", "too_small"), [(12, 9), (4, 3), (12, 0)])
    def test_a_sample_below_the_minimum_is_refused(
        self, service, graph, comparisons, agreements, too_small
    ):
        a, b = two(service, graph, rooms(graph, agreements), rooms(graph, agreements))

        with pytest.raises(SampleTooSmallError, match="Check at least"):
            comparisons.accept_rest(a.id, b.id, sample_size=too_small)

    def test_fewer_agreements_than_the_minimum_are_all_the_sample(
        self, service, graph, comparisons
    ):
        a, b = two(service, graph, rooms(graph, 3), rooms(graph, 3))
        decide_sample(comparisons, a, b, sample_size=3)

        result = comparisons.accept_rest(a.id, b.id, sample_size=3)

        assert (result.landed, result.skipped) == (0, [])
        assert (result.sample.size, result.sample.checked) == (3, 3)

    def test_lands_the_rest_skips_what_a_person_must_see_and_records_the_check(
        self, service, graph, comparisons, proposals
    ):
        match = {"kind": "existing", "entity_id": graph["den"], "similarity": 0.9}
        extra_a = [
            create(13, "Nook", graph["room"], alternatives=[match]),
            create(14, "Attic", graph["room"], evidence=False),
        ]
        extra_b = [create(13, "Nook", graph["room"]), create(14, "Attic", graph["room"])]
        a, b = two(service, graph, rooms(graph, 12) + extra_a, rooms(graph, 12) + extra_b)
        comparison, sample = decide_sample(comparisons, a, b, not_element=1)

        result = comparisons.accept_rest(a.id, b.id)

        by_title = {p.a.fields["title"]: p.pair_id for p in comparison.pairs}
        sampled = {p.pair_id for p in sample}
        expected = {
            by_title[title]: why
            for title, why in (("Nook", "near_match"), ("Attic", "no_passage"))
            if by_title[title] not in sampled
        }
        assert dict(result.skipped) == expected
        assert result.landed == 14 - len(sampled) - len(expected)
        assert result.failed == []
        assert (result.sample.size, result.sample.checked, result.sample.changed) == (10, 10, 1)
        bulk = [d.comparison for d in proposals.decisions if (d.comparison or {}).get("bulk")]
        assert len(bulk) == 2 * result.landed
        assert all(
            c["bulk"] == {"sample_size": 10, "sample_changed": 1} and not c["sample"] for c in bulk
        )
        assert comparisons.compare(a.id, b.id).counts()["open"] == len(expected)

        again = comparisons.accept_rest(a.id, b.id)

        assert (again.landed, again.failed, again.skipped) == (0, [], result.skipped)
        assert len(proposals.decisions) == 20 + 2 * result.landed

    def test_bulk_counts_the_pairs_checked_not_the_sample_size_asked(
        self, service, graph, comparisons, proposals
    ):
        a, b = two(service, graph, rooms(graph, 14), rooms(graph, 14))
        decide_sample(comparisons, a, b)
        # Two more agreements decided outside a sample: not checked as a sample
        rest = [
            p
            for p in comparisons.compare(a.id, b.id, 12).pairs
            if p.pair_id in comparisons.compare(a.id, b.id, 12).sample and p.state is PairState.OPEN
        ]
        for pair in rest:
            decide(comparisons, a, b, "keep", pair.a, pair.b)

        result = comparisons.accept_rest(a.id, b.id, sample_size=12)

        assert result.landed == 2
        bulk = {
            str(d.comparison["bulk"])
            for d in proposals.decisions
            if (d.comparison or {}).get("bulk")
        }
        assert bulk == {str({"sample_size": 10, "sample_changed": 0})}

    def test_skips_a_near_match_and_a_copy_without_a_passage(self, service, graph, comparisons):
        match = {"kind": "existing", "entity_id": graph["den"], "similarity": 0.9}
        specials_a = [
            create(13, "Nook", graph["room"], alternatives=[match]),
            create(14, "Attic", graph["room"]),
        ]
        specials_b = [
            create(13, "Nook", graph["room"]),
            create(14, "Attic", graph["room"], evidence=False),
        ]
        a, b = two(service, graph, rooms(graph, 12) + specials_a, rooms(graph, 12) + specials_b)
        comparison, sample = decide_sample(comparisons, a, b)

        result = comparisons.accept_rest(a.id, b.id)

        unsampled = {p.a.fields["title"] for p in comparison.pairs} - {
            p.a.fields["title"] for p in sample
        }
        whys = {"Nook": "near_match", "Attic": "no_passage"}
        titles = {p.pair_id: p.a.fields["title"] for p in comparison.pairs}
        assert {titles[p]: w for p, w in result.skipped} == {
            t: w for t, w in whys.items() if t in unsampled
        }
        assert result.landed == len(unsampled - set(whys))


# ---------------------------------------------------------------- concurrency


def test_two_reviewers_deciding_one_pair_from_both_sides_do_not_deadlock(
    service, graph, comparisons
):
    a, b = two(
        service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
    )
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def run(first, second, first_op, second_op):
        barrier.wait()
        try:
            comparisons.decide(
                first.id,
                second.id,
                PairDecision(Verdict.KEEP, a_operation_id=first_op, b_operation_id=second_op),
            )
            outcomes.append("landed")
        except ChangeProposalStateError:
            outcomes.append("conflict")

    threads = [
        threading.Thread(target=run, args=(a, b, a.operations[0].id, b.operations[0].id)),
        threading.Thread(target=run, args=(b, a, b.operations[0].id, a.operations[0].id)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(t.is_alive() for t in threads)
    assert sorted(outcomes) == ["conflict", "landed"]


# ---------------------------------------------------------------- review follow-ups


class TestBothCopiesOfAPair:
    def test_one_side_of_an_open_pair_is_refused(self, service, graph, comparisons, proposals):
        a, b = two(
            service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
        )

        for side in ({"a_op": a.operations[0]}, {"b_op": b.operations[0]}):
            with pytest.raises(InvalidPairDecisionError, match="Name both copies"):
                decide(comparisons, a, b, "keep", **side)

        assert proposals.decisions == []

    def test_one_side_when_the_other_is_decided_names_it(
        self, service, graph, comparisons, proposals
    ):
        a, b = two(
            service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
        )
        service.reject(b.id, [b.operations[0].id], note="decided on the Review page")

        result = decide(comparisons, a, b, "keep", a.operations[0])

        assert result.outcome is CopyOutcome.LANDED
        record = decisions_by_op(proposals)[a.operations[0].id].comparison
        assert record["with_operation_id"] == b.operations[0].id

    def test_a_class_on_a_pair_of_one_needs_both(self, service, graph, comparisons):
        a, b = two(
            service,
            graph,
            [create(1, "Pantry", graph["room"])],
            [create(1, "Larder", graph["room"])],
        )

        with pytest.raises(InvalidPairDecisionError, match="needs both"):
            decide(comparisons, a, b, "a_class", a.operations[0])


class TestRevertingTheLandedCopy:
    def test_reopens_the_other_proposals_copy(self, service, graph, comparisons, proposals):
        a, b = two(
            service,
            graph,
            [create(1, "Study", graph["room"])],
            [create(1, "Study", graph["room"], ref="study"), near(2, "study", graph["den"], graph)],
        )
        decide(comparisons, a, b, "keep", a.operations[0], b.operations[0])
        assert service.get(b.id).status.value == "open"  # its relationship awaits
        service.reject(b.id, [by_seq(b)[2].id])  # B done
        assert service.get(b.id).status.value == "done"

        service.revert(a.id)

        reopened = by_seq(service.get(b.id))[1]
        assert reopened.status is OperationStatus.PENDING
        assert (reopened.result_entity_id, reopened.reason_code, reopened.reason) == (
            None,
            None,
            None,
        )
        assert service.get(b.id).status.value == "open"
        superseded = decisions_by_op(proposals)[b.operations[0].id]
        assert superseded.superseded_at is not None and superseded.superseded_by == "user"

    def test_the_reopened_copy_decided_again_resolves_its_relationship(
        self, service, graph, comparisons, repo
    ):
        a, b = two(
            service,
            graph,
            [create(1, "Study", graph["room"])],
            [create(1, "Study", graph["room"], ref="study"), near(2, "study", graph["den"], graph)],
        )
        decide(comparisons, a, b, "keep", a.operations[0], b.operations[0])
        landed = service.get(a.id).operations[0].result_entity_id
        service.revert(a.id)
        repo.delete_individual(landed)  # the stub revert undoes nothing itself

        applied = service.apply(b.id, [b.operations[0].id, by_seq(b)[2].id])

        study, relationship = by_seq(applied)[1], by_seq(applied)[2]
        assert relationship.status is OperationStatus.APPLIED
        assert repo.get_relationship(relationship.result_entity_id).source_id == (
            study.result_entity_id
        )

    def test_a_duplicate_whose_individual_is_gone_fails_unresolved(
        self, service, graph, comparisons, repo
    ):
        a, b = two(
            service,
            graph,
            [create(1, "Study", graph["room"])],
            [create(1, "Study", graph["room"], ref="study"), near(2, "study", graph["den"], graph)],
        )
        decide(comparisons, a, b, "keep", a.operations[0], b.operations[0])
        repo.delete_individual(service.get(a.id).operations[0].result_entity_id)

        relationship = by_seq(service.apply(b.id, [by_seq(b)[2].id]))[2]

        assert relationship.reason.startswith("unresolved_ref:")


class TestVerdictsFromWhatLanded:
    def test_a_reused_edited_landing_records_its_class_change(
        self, service, graph, comparisons, proposals
    ):
        a, b = two(
            service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
        )
        op_a, op_b = a.operations[0], b.operations[0]
        service.apply(a.id, [op_a.id], edits={op_a.id: {"class_ids": [graph["kitchen"]]}})

        decide(comparisons, a, b, "keep", op_a, op_b)

        records = decisions_by_op(proposals)
        assert records[op_a.id].decision is DecisionKind.APPLIED_WITH_EDITS
        assert records[op_a.id].comparison["verdict"] == "class_changed"
        assert records[op_a.id].comparison["with_operation_id"] == op_b.id
        assert records[op_b.id].comparison["verdict"] == "class_changed"

    def test_a_near_match_of_another_class_is_a_class_change(
        self, service, graph, comparisons, proposals, ontology
    ):
        pantry = ontology.create_individual(graph["kitchen"], "Pantry")
        match = {"kind": "existing", "entity_id": pantry.id, "similarity": 0.9}
        a, b = two(
            service,
            graph,
            [create(1, "The pantry", graph["room"], alternatives=[match])],
            [create(1, "The pantry", graph["room"])],
        )

        result = decide(
            comparisons, a, b, "keep", a.operations[0], b.operations[0], match_entity_id=pantry.id
        )

        verdicts = {d.comparison["verdict"] for d in proposals.decisions}
        assert verdicts == {"class_changed"}
        assert result.comparison.changed(result.pair)


def test_the_relationship_preview_follows_a_closed_copy(service, graph, comparisons):
    """A Place is no Room: B's near relationship to its closed copy won't fit, and says so."""
    a, b = two(
        service,
        graph,
        [create(1, "Study", graph["place"])],
        [create(1, "Study", graph["room"], ref="study"), near(2, "study", graph["den"], graph)],
    )
    relationship_id = by_seq(b)[2].id
    assert relationship_id not in service.domain_range_mismatches(service.get(b.id))

    decide(comparisons, a, b, "a_class", a.operations[0], b.operations[0])

    assert relationship_id in service.domain_range_mismatches(service.get(b.id))
    applied = by_seq(service.apply(b.id, [relationship_id]))[2]
    assert applied.reason.startswith("domain_range_mismatch:")


def test_a_superseded_proposal_is_not_comparable(service, graph, comparisons):
    a, b = two(
        service, graph, [create(1, "Study", graph["room"])], [create(1, "Study", graph["room"])]
    )
    service.reject(
        a.id, [a.operations[0].id], note=SUPERSEDED_REASON.format("newer"), decided_by=None
    )

    with pytest.raises(ProposalsNotComparableError, match="compare the newer one"):
        comparisons.compare(a.id, b.id)
