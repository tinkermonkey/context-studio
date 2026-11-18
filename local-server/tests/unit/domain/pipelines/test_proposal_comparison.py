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
    SampleUncheckedError,
    Verdict,
    pair_operations,
    sample_ids,
)
from domain.versioning.exceptions import ChangeProposalStateError
from domain.versioning.gold import DecisionKind
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    CopyOutcome,
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
        assert sample_ids(pairs, b.id, a.id, 5) != five or len(pairs) < 2


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
            ("a_class", "a", {}, "needs both"),
            ("keep", "a", {"reason_code": RejectionReason.OTHER}, "only for not_element"),
            ("keep", "a", {"match_entity_id": "nope"}, "not a near match"),
            ("not_element", "a", {"match_entity_id": "nope"}, "only for an element"),
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


class TestAcceptTheRest:
    def setup_pairs(self, service, graph, extra_a=(), extra_b=()):
        drafts = [create(n, f"Room {n}", graph["room"]) for n in range(1, 7)]
        return two(service, graph, drafts + list(extra_a), drafts + list(extra_b))

    def test_refused_while_a_sample_pair_is_open(self, service, graph, comparisons):
        a, b = self.setup_pairs(service, graph)

        with pytest.raises(SampleUncheckedError, match="2 of the 2 sample pairs"):
            comparisons.accept_rest(a.id, b.id, sample_size=2)

    def test_lands_the_rest_skips_what_a_person_must_see_and_records_the_sample(
        self, service, graph, comparisons, proposals
    ):
        match = {"kind": "existing", "entity_id": graph["den"], "similarity": 0.9}
        a, b = self.setup_pairs(
            service,
            graph,
            extra_a=[
                create(7, "Nook", graph["room"], alternatives=[match]),
                create(8, "Attic", graph["room"], evidence=False),
            ],
            extra_b=[create(7, "Nook", graph["room"]), create(8, "Attic", graph["room"])],
        )
        comparison = comparisons.compare(a.id, b.id, sample_size=2)
        sample = [p for p in comparison.pairs if p.pair_id in comparison.sample]
        assert len(sample) == 2
        decide(comparisons, a, b, "keep", sample[0].a, sample[0].b)
        decide(
            comparisons,
            a,
            b,
            "not_element",
            sample[1].a,
            sample[1].b,
            reason_code=RejectionReason.TOO_GENERIC,
        )

        result = comparisons.accept_rest(a.id, b.id, sample_size=2)

        by_title = {p.a.fields["title"]: p.pair_id for p in comparison.pairs}
        sampled = {p.pair_id for p in sample}
        expected = {
            by_title[title]: why
            for title, why in (("Nook", "near_match"), ("Attic", "no_passage"))
            if by_title[title] not in sampled
        }
        assert dict(result.skipped) == expected
        assert result.landed == 8 - len(sampled) - len(expected)
        assert result.failed == []
        assert (result.sample.size, result.sample.checked, result.sample.changed) == (2, 2, 1)
        bulk = [d.comparison for d in proposals.decisions if (d.comparison or {}).get("bulk")]
        assert len(bulk) == 2 * result.landed
        assert all(
            c["bulk"] == {"sample_size": 2, "sample_changed": 1} and not c["sample"] for c in bulk
        )
        assert comparisons.compare(a.id, b.id, sample_size=2).counts()["open"] == len(expected)

        again = comparisons.accept_rest(a.id, b.id, sample_size=2)

        assert (again.landed, again.failed, again.skipped) == (0, [], result.skipped)
        assert len(proposals.decisions) == 4 + 2 * result.landed

    def test_skips_a_near_match_and_a_copy_without_a_passage(self, service, graph, comparisons):
        match = {"kind": "existing", "entity_id": graph["den"], "similarity": 0.9}
        a, b = two(
            service,
            graph,
            [
                create(1, "Nook", graph["room"], alternatives=[match]),
                create(2, "Attic", graph["room"]),
                create(3, "Loft", graph["room"]),
            ],
            [
                create(1, "Nook", graph["room"]),
                create(2, "Attic", graph["room"], evidence=False),
                create(3, "Loft", graph["room"]),
            ],
        )

        result = comparisons.accept_rest(a.id, b.id, sample_size=0)

        assert sorted(why for _, why in result.skipped) == ["near_match", "no_passage"]
        assert result.landed == 1
        assert by_seq(service.get(a.id))[3].status is OperationStatus.APPLIED
        assert by_seq(service.get(b.id))[3].reason_code is RejectionReason.DUPLICATE


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
