"""
Unit tests (#1613): what checking a benchmark gold file needs of proposals.
A proposer's client_metadata is checked (its source and origin), and a
reviewer's annotations for gold (tier, also-defensible classes) are recorded
on decisions.
"""

import pytest

from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposals import OperationDraft
from domain.versioning.proposals import OperationStatus, ProposalSource
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
from tests.unit.domain.versioning.test_reviewer_additions import (  # noqa: F401 - fixtures
    entity_sources,
    extracted,
    passage_of,
    service,
    source,
    source_repo,
)

ORIGIN = {
    "pipeline_type": "individual_extraction",
    "implementation_id": "gold_check",
    "configuration_ref": "gold",
    "configuration_version": 1,
    "digest": "0123456789ab",
}


def study(graph, seq=1):
    return OperationDraft(
        seq=seq,
        op=T.CREATE,
        kind=K.INDIVIDUAL,
        ref=f"study{seq}",
        fields={"class_ids": [graph["room"]], "title": f"Study {seq}"},
    )


def propose(service, graph, client_metadata, *drafts):
    return service.propose(
        graph["taxonomy"],
        "Gold check",
        list(drafts) or [study(graph)],
        ProposalSource.PIPELINE,
        client_metadata=client_metadata,
    )


class TestClientMetadata:
    def test_a_source_of_the_taxonomy_and_an_origin_are_kept(self, service, graph, source):
        metadata = {"source_id": source.id, "origin": ORIGIN, "gold_check": {"document": "d"}}

        proposal = propose(service, graph, metadata)

        assert proposal.client_metadata == metadata
        assert proposal.extracted_from_source
        assert proposal.origin.implementation_id == "gold_check"

    def test_an_unknown_source_is_refused(self, service, graph, proposals):
        with pytest.raises(ProposalValidationError) as raised:
            propose(service, graph, {"source_id": "nope"})

        assert [e.code for e in raised.value.errors] == ["source_not_found"]

    def test_a_source_of_another_taxonomy_is_refused(self, service, graph, source, ontology):
        other = ontology.create_taxonomy(title="Garden")

        with pytest.raises(ProposalValidationError, match="not a source of the taxonomy"):
            service.propose(
                other.id,
                "Elsewhere",
                [
                    OperationDraft(
                        seq=1,
                        op=T.CREATE,
                        kind=K.SCHEME,
                        fields={"taxonomy_id": other.id, "title": "S"},
                    )
                ],
                ProposalSource.PIPELINE,
                client_metadata={"source_id": source.id},
            )

    @pytest.mark.parametrize(
        "origin",
        ["gold_check", {}, {**ORIGIN, "configuration_version": "1"}, {"pipeline_type": "x"}],
    )
    def test_a_malformed_origin_is_refused(self, service, graph, origin):
        with pytest.raises(ProposalValidationError, match="origin needs"):
            propose(service, graph, {"origin": origin})

    def test_what_the_service_records_wins_and_is_not_checked_as_given(
        self, service, graph, proposals
    ):
        run = service.recording({"origin": ORIGIN})

        proposal = propose(run, graph, {"origin": "the proposer's own"})

        assert proposals.get(proposal.id).client_metadata == {"origin": ORIGIN}


class TestAnnotations:
    def test_apply_records_them_on_each_decision(self, service, graph, proposals):
        proposal = propose(service, graph, None, study(graph, 1), study(graph, 2))
        first, second = proposal.operations

        service.apply(
            proposal.id,
            [first.id, second.id],
            annotations={
                first.id: {"tier": "core", "also_defensible": [graph["kitchen"], graph["kitchen"]]},
                second.id: {},
            },
        )

        notes = {d.seq: d.annotations for d in proposals.decisions}
        assert notes == {1: {"tier": "core", "also_defensible": [graph["kitchen"]]}, 2: None}

    def test_reject_records_them(self, service, graph, proposals):
        proposal = propose(service, graph, None)
        op = proposal.operations[0]

        service.reject(proposal.id, [op.id], annotations={op.id: {"tier": "supporting"}})

        assert proposals.decisions[0].annotations == {"tier": "supporting"}

    def test_an_added_element_records_its_tier(self, service, graph, source, proposals):
        proposal = extracted(service, graph, source)

        service.add_individual(
            proposal.id,
            "Pantry",
            [graph["room"]],
            passage_of("Pantry", source),
            annotation={"tier": "core"},
        )

        [decision] = proposals.decisions
        assert decision.added and decision.annotations == {"tier": "core"}

    @pytest.mark.parametrize(
        ("annotation", "message"),
        [
            ({"tier": "central"}, "tier must be one of"),
            ({"rank": 1}, "takes only tier and also_defensible"),
            ({"also_defensible": "room"}, "must be a list"),
            ({"also_defensible": ["nope"]}, "not classes of the taxonomy"),
            ("core", "must be an object"),
        ],
    )
    def test_an_invalid_one_changes_nothing(self, service, graph, proposals, annotation, message):
        proposal = propose(service, graph, None)
        op = proposal.operations[0]

        for action in ("apply", "reject"):
            with pytest.raises(ValueError, match=message):
                getattr(service, action)(proposal.id, [op.id], annotations={op.id: annotation})

        assert proposals.get(proposal.id).operations[0].status is OperationStatus.PENDING
        assert proposals.decisions == []

    def test_a_class_of_another_taxonomy_is_not_defensible(
        self, service, graph, proposals, ontology
    ):
        other = ontology.create_taxonomy(title="Garden")
        tree = ontology.create_class(ontology.create_scheme(other.id, "Plants").id, "Tree")
        proposal = propose(service, graph, None)
        op = proposal.operations[0]

        with pytest.raises(ValueError, match="not classes of the taxonomy"):
            service.apply(proposal.id, [op.id], annotations={op.id: {"also_defensible": [tree.id]}})

    def test_one_for_an_operation_not_in_the_call_changes_nothing(self, service, graph, proposals):
        proposal = propose(service, graph, None, study(graph, 1), study(graph, 2))
        first, second = proposal.operations

        with pytest.raises(ValueError, match="Annotations for operations not being applied"):
            service.apply(proposal.id, [first.id], annotations={second.id: {"tier": "core"}})
        assert proposals.decisions == []

    def test_an_invalid_one_adds_nothing(self, service, graph, source, proposals):
        proposal = extracted(service, graph, source)

        with pytest.raises(ValueError, match="tier must be one of"):
            service.add_individual(
                proposal.id,
                "Pantry",
                [graph["room"]],
                passage_of("Pantry", source),
                annotation={"tier": "major"},
            )
        assert len(proposals.get(proposal.id).operations) == 1
