"""
Unit tests (#1553, part of #1552): source evidence on operations, near-match
alternatives on individual creates ("use existing" at apply), and the
provenance rows applied operations record and revert removes.
"""

from datetime import datetime, timezone

import pytest

from domain.versioning.approval_policy import ApprovalPolicy, AutoApplyRule, auto_apply_ids
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    ChangeScope,
    OperationStatus,
    ProposalSource,
    ProposedOperation,
)
from domain.versioning.provenance import EntitySource, entity_sources, evidence_problem
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

SOURCE = "src-manual"


def passage(start=10, end=24, page=5, quote="French door fridge", source_id=SOURCE):
    return {"source_id": source_id, "page": page, "start": start, "end": end, "quote": quote}


def near(entity_id, similarity=0.93):
    return {"kind": "existing", "entity_id": entity_id, "similarity": similarity}


@pytest.fixture()
def sources():
    return FakeEntitySourceRepository()


@pytest.fixture()
def service(proposals, ontology, repo, reverter, sources):
    return ProposalService(proposals, ontology, repo, reverter, entity_sources=sources)


@pytest.fixture()
def hall(ontology, graph):
    return ontology.create_individual(graph["room"], "Hall").id


def propose(service, graph, *drafts):
    return service.propose(graph["taxonomy"], "Extracted", list(drafts), ProposalSource.PIPELINE)


def create_den_like(graph, evidence=(), alternatives=(), ref="fridge", seq=1):
    return OperationDraft(
        seq=seq,
        op=T.CREATE,
        kind=K.INDIVIDUAL,
        ref=ref,
        fields={"class_ids": [graph["room"]], "title": "Study"},
        evidence=list(evidence),
        alternatives=list(alternatives),
    )


def link(graph, source, target, seq, evidence=()):
    return OperationDraft(
        seq=seq,
        op=T.CREATE,
        kind=K.RELATIONSHIP,
        fields={"source_id": source, "target_id": target, "property_definition_id": graph["near"]},
        evidence=list(evidence),
    )


# ---------------------------------------------------------------- evidence


class TestEvidenceProblem:
    @pytest.mark.parametrize(
        "item",
        [
            {"quote": "q", "url": "u", "entity_id": "e"},
            passage(),
            passage(page=None),
            {"source_id": SOURCE, "start": 0, "end": 0},
            {**passage(), "label": "chunk 3"},
        ],
    )
    def test_valid_items(self, item):
        assert evidence_problem(item) is None

    @pytest.mark.parametrize(
        ("item", "message"),
        [
            ("a quote", "must be an object"),
            ({"quote": 3}, "must be text"),
            ({"start": 1, "end": 2}, 'needs a "source_id"'),
            (passage(start=-1), "non-negative integer"),
            (passage(start=True), "non-negative integer"),
            (passage(end=1.5), "non-negative integer"),
            (passage(page="5"), "non-negative integer"),
            (passage(start=9, end=3), "before its start"),
            ({"source_id": SOURCE, "start": 1}, "needs end"),
            (passage(source_id="  "), "must not be empty"),
            (passage(source_id=7), "must be text"),
            (passage(quote=None), "must be text"),
        ],
    )
    def test_invalid_items(self, item, message):
        assert message in evidence_problem(item)

    def test_propose_refuses_a_malformed_passage(self, service, graph):
        with pytest.raises(ProposalValidationError, match="before its start"):
            propose(service, graph, create_den_like(graph, [passage(start=30, end=4)]))

    def test_a_proposed_passage_is_kept_as_given(self, service, graph):
        proposal = propose(service, graph, create_den_like(graph, [passage(), {"quote": "q"}]))

        assert proposal.operations[0].evidence == [passage(), {"quote": "q"}]

    def test_entity_sources_reads_only_passages(self):
        now = datetime.now(timezone.utc)
        rows = entity_sources([{"quote": "q"}, passage()], "ind-1", "individual", "p-1", 3, now)

        assert [(r.entity_id, r.source_id, r.page, r.start, r.end, r.quote) for r in rows] == [
            ("ind-1", SOURCE, 5, 10, 24, "French door fridge")
        ]
        assert (rows[0].proposal_id, rows[0].op_seq, rows[0].entity_kind) == (
            "p-1",
            3,
            "individual",
        )

    def test_an_entity_source_needs_ordered_offsets_and_a_zone(self):
        with pytest.raises(ValueError, match="before start"):
            EntitySource("e", "individual", SOURCE, "p", 1, 5, 2, datetime.now(timezone.utc))
        with pytest.raises(ValueError, match="timezone"):
            EntitySource("e", "individual", SOURCE, "p", 1, 1, 2, datetime.now())


# ---------------------------------------------------------------- alternatives


class TestProposeAlternatives:
    def test_an_individual_create_keeps_its_near_matches(self, service, graph):
        proposal = propose(
            service, graph, create_den_like(graph, alternatives=[near(graph["den"])])
        )

        assert proposal.operations[0].alternatives == [near(graph["den"])]

    def test_similarity_may_be_left_out(self, service, graph):
        alternative = {"kind": "existing", "entity_id": graph["den"]}
        proposal = propose(service, graph, create_den_like(graph, alternatives=[alternative]))

        assert proposal.operations[0].alternatives == [near(graph["den"], None)]

    @pytest.mark.parametrize(
        ("alternative", "message"),
        [
            ({"kind": "new", "entity_id": "x"}, 'must be "existing"'),
            ({"kind": "existing"}, "needs an entity_id"),
            ({"kind": "existing", "entity_id": "x", "similarity": 1.2}, "0 to 1"),
            ({"kind": "existing", "entity_id": "x", "similarity": True}, "0 to 1"),
            ({"kind": "existing", "entity_id": "x", "title": "Den"}, "each alternative must be"),
        ],
    )
    def test_malformed_alternatives_are_refused(self, service, graph, alternative, message):
        with pytest.raises(ProposalValidationError, match=message):
            propose(service, graph, create_den_like(graph, alternatives=[alternative]))

    def test_an_entity_is_named_once(self, service, graph):
        with pytest.raises(ProposalValidationError, match="listed twice"):
            propose(
                service,
                graph,
                create_den_like(graph, alternatives=[near(graph["den"]), near(graph["den"], 0.5)]),
            )

    def test_only_an_individual_create_carries_them(self, service, graph):
        with pytest.raises(ProposalValidationError, match="Only an individual create"):
            propose(
                service,
                graph,
                OperationDraft(
                    1,
                    T.UPDATE,
                    K.INDIVIDUAL,
                    graph["den"],
                    fields={"title": "Study"},
                    alternatives=[near(graph["den"])],
                ),
            )

    def test_a_near_match_must_be_an_existing_individual(self, service, graph):
        with pytest.raises(ProposalValidationError, match="alternative_not_found"):
            propose(service, graph, create_den_like(graph, alternatives=[near(graph["room"])]))

    def test_a_near_match_must_be_in_the_proposals_taxonomy(self, service, graph, ontology):
        other = ontology.create_taxonomy(title="Garden")
        scheme = ontology.create_scheme(other.id, title="Plants")
        tree = ontology.create_individual(ontology.create_class(scheme.id, "Tree").id, "Oak")

        with pytest.raises(ProposalValidationError, match="not in the proposal's taxonomy"):
            propose(service, graph, create_den_like(graph, alternatives=[near(tree.id)]))

    def test_a_near_match_must_be_in_the_proposals_dataset(self, service, graph, ontology):
        annex = ontology.create_dataset(graph["taxonomy"], "annex", "Annex")
        annex_den = ontology.create_individual(graph["room"], "Den", dataset_id=annex.id)
        [default] = [d for d in ontology.list_datasets(graph["taxonomy"]) if d.id != annex.id]

        with pytest.raises(ProposalValidationError, match="dataset_mismatch"):
            service.propose(
                graph["taxonomy"],
                "Extracted",
                [create_den_like(graph, alternatives=[near(annex_den.id)])],
                ProposalSource.PIPELINE,
                dataset_id=default.identifier,
            )

    def test_a_create_with_near_matches_never_auto_applies(self, graph):
        policy = ApprovalPolicy(graph["taxonomy"], (AutoApplyRule(op=T.CREATE),))
        additive = {"scope": ChangeScope.ADDITIVE}
        plain = ProposedOperation(
            1, T.CREATE, K.INDIVIDUAL, ref="a", fields={"title": "A"}, **additive
        )
        matched = ProposedOperation(
            2,
            T.CREATE,
            K.INDIVIDUAL,
            ref="b",
            fields={"title": "B"},
            alternatives=[near("x")],
            **additive,
        )
        follows = ProposedOperation(
            3, T.CREATE, K.RELATIONSHIP, fields={"source_id": "$a", "target_id": "$b"}, **additive
        )

        chosen = auto_apply_ids(
            policy,
            [plain, matched, follows],
            lambda op: [],
            lambda op: True,
            id_fields=frozenset({"source_id", "target_id"}),
            source=ProposalSource.PIPELINE,
        )

        assert chosen == [plain.id]


# ---------------------------------------------------------------- apply


class TestUseExisting:
    def _proposal(self, service, graph, hall):
        return propose(
            service,
            graph,
            create_den_like(graph, [passage()], [near(graph["den"])]),
            link(graph, "$fridge", hall, 2, [passage(40, 60, 6, "next to the hall")]),
        )

    def test_choosing_a_near_match_creates_nothing_and_repoints_relationships(
        self, service, graph, repo, ontology, hall
    ):
        proposal = self._proposal(service, graph, hall)
        create, relate = proposal.operations
        before = ontology.count_individuals(class_id=graph["room"])

        applied = service.apply(
            proposal.id,
            [create.id, relate.id],
            chosen_alternatives={create.id: {"kind": "existing", "entity_id": graph["den"]}},
        )

        create, relate = applied.operations
        assert ontology.count_individuals(class_id=graph["room"]) == before
        assert (create.status, create.result_entity_id, create.matched) == (
            OperationStatus.APPLIED,
            graph["den"],
            True,
        )
        assert relate.status is OperationStatus.APPLIED
        relationship = repo.get_relationship(relate.result_entity_id)
        assert (relationship.source_id, relationship.target_id) == (graph["den"], hall)

    def test_the_choice_is_recorded_in_gold_with_its_similarity(
        self, service, graph, proposals, hall
    ):
        proposal = self._proposal(service, graph, hall)
        create = proposal.operations[0]

        service.apply(
            proposal.id,
            [create.id],
            chosen_alternatives={create.id: {"kind": "existing", "entity_id": graph["den"]}},
        )

        [decision] = proposals.decisions
        assert decision.chosen_alternative == near(graph["den"])
        assert decision.result_entity_id == graph["den"]
        assert decision.applied_fields == {}
        assert decision.proposed["alternatives"] == [near(graph["den"])]

    def test_a_relationship_applied_later_points_at_the_match(self, service, graph, repo, hall):
        proposal = self._proposal(service, graph, hall)
        create, relate = proposal.operations
        service.apply(
            proposal.id,
            [create.id],
            chosen_alternatives={create.id: {"kind": "existing", "entity_id": graph["den"]}},
        )

        applied = service.apply(proposal.id, [relate.id])

        relationship = repo.get_relationship(applied.operations[1].result_entity_id)
        assert relationship.source_id == graph["den"]

    def test_accepting_without_a_choice_creates_the_individual(self, service, graph, repo, hall):
        proposal = self._proposal(service, graph, hall)
        create, relate = proposal.operations

        applied = service.apply(proposal.id, [create.id, relate.id])

        create, relate = applied.operations
        assert create.result_entity_id != graph["den"] and not create.matched
        assert repo.get_individual(create.result_entity_id).title == "Study"
        assert repo.get_relationship(relate.result_entity_id).source_id == create.result_entity_id

    def test_a_choice_not_among_the_near_matches_is_refused(self, service, graph, hall):
        proposal = self._proposal(service, graph, hall)
        create = proposal.operations[0]

        with pytest.raises(ValueError, match="no near match"):
            service.apply(
                proposal.id,
                [create.id],
                chosen_alternatives={create.id: {"kind": "existing", "entity_id": "other"}},
            )

    def test_a_match_deleted_since_fails_the_operation(self, service, graph, ontology, hall):
        proposal = self._proposal(service, graph, hall)
        create = proposal.operations[0]
        ontology.delete_individual(graph["den"])

        applied = service.apply(
            proposal.id,
            [create.id],
            chosen_alternatives={create.id: {"kind": "existing", "entity_id": graph["den"]}},
        )

        assert applied.operations[0].status is OperationStatus.FAILED
        assert applied.operations[0].reason.startswith("target_missing")


class TestProvenance:
    def test_applied_operations_record_their_passages(self, service, graph, sources):
        proposal = propose(
            service,
            graph,
            create_den_like(graph, [passage(), passage(100, 120, 54, "Accessories")]),
            link(graph, "$fridge", graph["den"], 2, [passage(40, 60, 6, "next to the den")]),
        )
        create, relate = proposal.operations

        applied = service.apply(proposal.id, [create.id, relate.id])

        created, related = (o.result_entity_id for o in applied.operations)
        rows = service.sources_of(created)
        assert [(r.page, r.start, r.end, r.quote, r.op_seq) for r in rows] == [
            (5, 10, 24, "French door fridge", 1),
            (54, 100, 120, "Accessories", 1),
        ]
        assert {(r.entity_kind, r.proposal_id, r.source_id) for r in rows} == {
            ("individual", proposal.id, SOURCE)
        }
        [edge] = service.sources_of(related)
        assert (edge.entity_kind, edge.quote, edge.op_seq) == ("relationship", "next to the den", 2)

    def test_a_match_adds_the_passage_to_the_existing_individual(self, service, graph):
        proposal = propose(
            service, graph, create_den_like(graph, [passage()], [near(graph["den"])])
        )
        create = proposal.operations[0]

        service.apply(
            proposal.id,
            [create.id],
            chosen_alternatives={create.id: {"kind": "existing", "entity_id": graph["den"]}},
        )

        [row] = service.sources_of(graph["den"])
        assert (row.entity_id, row.quote, row.proposal_id) == (
            graph["den"],
            "French door fridge",
            proposal.id,
        )

    def test_nothing_is_recorded_without_passages_or_for_a_failure(self, service, graph, sources):
        proposal = propose(
            service,
            graph,
            create_den_like(graph, [{"quote": "no source"}]),
            OperationDraft(2, T.DELETE, K.INDIVIDUAL, graph["den"], evidence=[passage()]),
        )

        service.apply(proposal.id, [o.id for o in proposal.operations])

        assert sources.rows == []

    def test_revert_removes_the_rows_the_proposal_wrote(self, service, graph, sources):
        earlier = propose(service, graph, create_den_like(graph, [passage()]))
        service.apply(earlier.id, [earlier.operations[0].id])
        proposal = propose(
            service, graph, create_den_like(graph, [passage()], [near(graph["den"])])
        )
        create = proposal.operations[0]
        service.apply(
            proposal.id,
            [create.id],
            chosen_alternatives={create.id: {"kind": "existing", "entity_id": graph["den"]}},
        )

        service.revert(proposal.id)

        assert service.sources_of(graph["den"]) == []
        assert [r.proposal_id for r in sources.rows] == [earlier.id]

    def test_without_a_repository_nothing_is_recorded(
        self, proposals, ontology, repo, reverter, graph
    ):
        service = ProposalService(proposals, ontology, repo, reverter)
        proposal = propose(service, graph, create_den_like(graph, [passage()]))

        applied = service.apply(proposal.id, [proposal.operations[0].id])

        assert applied.operations[0].status is OperationStatus.APPLIED
        assert service.sources_of(applied.operations[0].result_entity_id) == []

    def test_alternative_titles_name_each_near_match(self, service, graph):
        proposal = propose(
            service, graph, create_den_like(graph, alternatives=[near(graph["den"])])
        )

        assert service.alternative_titles(proposal) == {graph["den"]: "Den"}
