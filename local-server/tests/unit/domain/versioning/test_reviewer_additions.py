"""
Unit tests (#1610): a reviewer adds an element the extraction missed to its
proposal, from the proposal's source text; it is applied at once and its
decision is flagged as added.
"""

import pytest

from domain.extraction.sources import Source
from domain.ontology.value_objects import SourceRevision
from domain.pipelines.source_proposals import SUPERSEDED_REASON
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
    ChangeProposalStateError,
    ProposalValidationError,
)
from domain.versioning.gold import DecisionKind
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationDraft
from domain.versioning.proposals import (
    OperationStatus,
    ProposalSource,
    ProposalStatus,
)
from tests.fakes.fake_entity_source_repository import FakeEntitySourceRepository
from tests.fakes.fake_source_repository import FakeSourceRepository
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

TEXT = "The Study faces the hall. A Pantry sits off the Den, by the Study."


@pytest.fixture()
def entity_sources():
    return FakeEntitySourceRepository()


@pytest.fixture()
def source_repo():
    return FakeSourceRepository()


@pytest.fixture()
def source(source_repo, ontology, graph):
    [dataset] = ontology.list_datasets(graph["taxonomy"])
    return source_repo.save(
        Source(
            taxonomy_id=graph["taxonomy"],
            dataset_id=dataset.id,
            kind="text",
            title="Floor plan notes",
            text=TEXT,
            chars=len(TEXT),
            pages=1,
            page_starts=[0],
        )
    )


@pytest.fixture()
def service(proposals, ontology, repo, reverter, entity_sources, source_repo):
    return ProposalService(
        proposals,
        ontology,
        repo,
        reverter,
        entity_sources=entity_sources,
        source_repo=source_repo,
    )


def passage_of(quote, source, occurrence=0):
    start = TEXT.index(quote)
    for _ in range(occurrence):
        start = TEXT.index(quote, start + 1)
    return {"source_id": source.id, "start": start, "end": start + len(quote), "quote": quote}


def extracted(service, graph, source, source_id=None, seq=3):
    """An individual extraction's proposal on the source: the Study, at seq 3."""
    return service.propose(
        graph["taxonomy"],
        "Extracted",
        [
            OperationDraft(
                seq=seq,
                op=T.CREATE,
                kind=K.INDIVIDUAL,
                fields={"class_ids": [graph["room"]], "title": "Study"},
                evidence=[{**passage_of("Study", source), "page": 1}],
            )
        ],
        ProposalSource.PIPELINE,
        client_metadata={
            "source_id": source_id or source.id,
            "pipeline": "individual_extraction",
        },
    )


def add_pantry(service, proposal, graph, source, **extra):
    return service.add_individual(
        proposal.id, "Pantry", [graph["room"]], passage_of("Pantry", source), **extra
    )


class TestAddIndividual:
    def test_it_is_added_with_the_next_seq_and_applied(
        self, service, graph, source, repo, proposals, entity_sources
    ):
        proposal = extracted(service, graph, source)

        added = add_pantry(service, proposal, graph, source, review_ms=5200)

        [study, pantry] = added.operations
        assert pantry.seq == study.seq + 1 == 4
        assert pantry.added_by_reviewer and not study.added_by_reviewer
        assert (pantry.op, pantry.kind) == (T.CREATE, K.INDIVIDUAL)
        assert pantry.fields == {"title": "Pantry", "class_ids": [graph["room"]]}
        assert pantry.evidence == [{**passage_of("Pantry", source), "page": 1}]
        assert pantry.status is OperationStatus.APPLIED
        individual = repo.get_individual(pantry.result_entity_id)
        assert individual.title == "Pantry" and individual.dataset_id == source.dataset_id
        [decision] = proposals.decisions
        assert decision.decision is DecisionKind.APPLIED
        assert decision.added and decision.review_ms == 5200
        assert decision.operation_id == pantry.id
        [provenance] = entity_sources.list_for_entity(pantry.result_entity_id)
        assert (provenance.source_id, provenance.op_seq) == (source.id, 4)
        assert (provenance.start, provenance.end) == (TEXT.index("Pantry"), TEXT.index(" sits"))

    def test_a_proposed_operations_decision_is_not_added(self, service, graph, source, proposals):
        proposal = extracted(service, graph, source)

        service.apply(proposal.id, [proposal.operations[0].id])

        assert proposals.decisions[0].added is False

    def test_a_done_proposal_takes_it_and_settles_again(self, service, graph, source):
        proposal = extracted(service, graph, source)
        done = service.apply(proposal.id, [proposal.operations[0].id])
        assert done.status is ProposalStatus.DONE

        added = add_pantry(service, proposal, graph, source)

        assert added.operations[-1].status is OperationStatus.APPLIED
        assert added.status is ProposalStatus.DONE

    def test_a_title_already_in_the_dataset_adds_nothing(self, service, graph, source, proposals):
        proposal = extracted(service, graph, source)
        service.apply(proposal.id, [proposal.operations[0].id])

        # "Den" is already a Room in the dataset
        with pytest.raises(ProposalValidationError) as raised:
            service.add_individual(proposal.id, "Den", [graph["room"]], passage_of("Den", source))

        assert [e.code for e in raised.value.errors] == ["duplicate_title"]
        stored = proposals.get(proposal.id)
        assert len(stored.operations) == 1 and stored.status is ProposalStatus.DONE

    def test_the_same_title_in_another_class_is_added(self, service, graph, source):
        proposal = extracted(service, graph, source)

        added = service.add_individual(
            proposal.id, "Den", [graph["place"]], passage_of("Den", source)
        )

        assert added.operations[-1].status is OperationStatus.APPLIED

    def test_an_unforeseen_apply_failure_stays_failed_and_reopens_a_done_proposal(
        self, service, graph, source, proposals, ontology, monkeypatch
    ):
        proposal = extracted(service, graph, source)
        service.apply(proposal.id, [proposal.operations[0].id])

        def refuse(*args, **kwargs):
            raise ValueError("the store is unavailable")

        monkeypatch.setattr(ontology, "create_individual", refuse)
        added = add_pantry(service, proposal, graph, source)

        failed = added.operations[-1]
        assert failed.status is OperationStatus.FAILED and failed.added_by_reviewer
        assert added.status is ProposalStatus.OPEN
        assert [d.added for d in proposals.decisions] == [False]

    def test_the_passage_page_comes_from_the_source(
        self, service, graph, source_repo, ontology, proposals
    ):
        [dataset] = ontology.list_datasets(graph["taxonomy"])
        page_two = TEXT.index("A Pantry")
        two_pages = source_repo.save(
            Source(
                taxonomy_id=graph["taxonomy"],
                dataset_id=dataset.id,
                kind="pdf",
                title="Two pages",
                text=TEXT,
                chars=len(TEXT),
                pages=2,
                page_starts=[0, page_two],
            )
        )
        proposal = extracted(service, graph, two_pages)

        added = add_pantry(service, proposal, graph, two_pages)

        assert added.operations[-1].evidence[0]["page"] == 2

    def test_a_revert_undoes_the_addition_and_its_provenance(
        self, service, graph, source, reverter, proposals, entity_sources
    ):
        """The individual itself is undone with the run (see the integration test)."""
        proposal = extracted(service, graph, source)
        added = add_pantry(service, proposal, graph, source).operations[-1]
        assert entity_sources.list_for_entity(added.result_entity_id)

        service.revert(proposal.id)

        assert reverter.reverted == [proposal.id]
        assert entity_sources.list_for_entity(added.result_entity_id) == []
        [decision] = proposals.decisions
        assert decision.added and decision.superseded_at is not None

    def test_seq_follows_the_highest_even_after_an_addition(self, service, graph, source):
        proposal = extracted(service, graph, source, seq=7)
        add_pantry(service, proposal, graph, source)

        again = service.add_individual(
            proposal.id, "Second study", [graph["room"]], passage_of("Study", source, 1)
        )

        assert [o.seq for o in again.operations] == [7, 8, 9]

    @pytest.mark.parametrize(
        ("class_ids", "code"),
        [
            (["nope"], "endpoint_not_found"),
            ([], "invalid"),
            (["$room"], "unknown_ref"),
        ],
    )
    def test_a_bad_class_adds_nothing(self, service, graph, source, proposals, class_ids, code):
        proposal = extracted(service, graph, source)

        with pytest.raises(ProposalValidationError) as raised:
            service.add_individual(proposal.id, "Pantry", class_ids, passage_of("Pantry", source))

        assert [e.code for e in raised.value.errors] in ([code], ["missing_field"])
        assert len(proposals.get(proposal.id).operations) == 1
        assert proposals.decisions == []

    def test_a_class_of_another_taxonomy_adds_nothing(self, service, graph, source, ontology):
        garden = ontology.create_taxonomy(title="Garden")
        scheme = ontology.create_scheme(taxonomy_id=garden.id, title="Plants")
        tree = ontology.create_class(scheme.id, "Tree")
        proposal = extracted(service, graph, source)

        with pytest.raises(ProposalValidationError, match="not a class of the taxonomy"):
            service.add_individual(proposal.id, "Pantry", [tree.id], passage_of("Pantry", source))

    def test_a_derived_class_adds_nothing(self, service, graph, source, ontology):
        derived = ontology.create_class(graph["vocab"], "Computed", derived=True)
        proposal = extracted(service, graph, source)

        with pytest.raises(ProposalValidationError, match="derived"):
            service.add_individual(
                proposal.id, "Pantry", [derived.id], passage_of("Pantry", source)
            )

    @pytest.mark.parametrize(
        ("change", "code"),
        [
            ({"quote": "Pantri"}, "quote_mismatch"),
            ({"start": 0}, "quote_mismatch"),
            ({"end": 10_000}, "quote_mismatch"),
            ({"source_id": "another-source"}, "invalid_passage"),
            ({"quote": ""}, "invalid_passage"),
            ({"start": -1}, "invalid_passage"),
            ({"end": None}, "invalid_passage"),
        ],
    )
    def test_a_bad_passage_adds_nothing(self, service, graph, source, proposals, change, code):
        proposal = extracted(service, graph, source)

        with pytest.raises(ProposalValidationError) as raised:
            service.add_individual(
                proposal.id, "Pantry", [graph["room"]], {**passage_of("Pantry", source), **change}
            )

        assert [e.code for e in raised.value.errors] == [code]
        assert len(proposals.get(proposal.id).operations) == 1

    def test_a_blank_title_adds_nothing(self, service, graph, source):
        proposal = extracted(service, graph, source)

        with pytest.raises(ProposalValidationError, match="needs a title"):
            service.add_individual(proposal.id, "  ", [graph["room"]], passage_of("Pantry", source))

    @pytest.mark.parametrize("review_ms", [-1, 2**31])
    def test_a_bad_review_time_adds_nothing(self, service, graph, source, proposals, review_ms):
        proposal = extracted(service, graph, source)

        with pytest.raises(ValueError, match="review_ms"):
            add_pantry(service, proposal, graph, source, review_ms=review_ms)

        assert len(proposals.get(proposal.id).operations) == 1

    def test_without_a_source_reader_only_the_shape_is_checked(
        self, proposals, ontology, repo, reverter, graph, source
    ):
        service = ProposalService(proposals, ontology, repo, reverter)
        proposal = extracted(service, graph, source)

        added = service.add_individual(
            proposal.id, "Pantry", [graph["room"]], {**passage_of("Pantry", source), "start": 0}
        )

        assert added.operations[-1].status is OperationStatus.APPLIED
        assert added.operations[-1].evidence[0]["page"] is None


class TestRefused:
    def test_an_unknown_proposal(self, service, graph, source):
        with pytest.raises(ChangeProposalNotFoundError):
            service.add_individual("nope", "Pantry", [graph["room"]], passage_of("Pantry", source))

    def test_a_reverted_proposal(self, service, graph, source, proposals):
        proposal = extracted(service, graph, source)
        service.apply(proposal.id, [proposal.operations[0].id])
        service.revert(proposal.id)

        with pytest.raises(ChangeProposalStateError, match="reverted"):
            add_pantry(service, proposal, graph, source)
        assert len(proposals.get(proposal.id).operations) == 1

    def test_a_landed_proposal(self, service, graph, source, proposals):
        proposal = extracted(service, graph, source)
        service.apply(proposal.id, [proposal.operations[0].id])
        service.mark_landed(proposal.id, SourceRevision(commit="abc123"))

        with pytest.raises(ChangeProposalStateError, match="landed"):
            add_pantry(service, proposal, graph, source)
        assert len(proposals.get(proposal.id).operations) == 1

    def test_a_proposal_a_newer_extraction_superseded(self, service, graph, source, proposals):
        proposal = extracted(service, graph, source)
        service.reject(
            proposal.id,
            [proposal.operations[0].id],
            note=SUPERSEDED_REASON.format("newer-proposal"),
            decided_by=None,
        )

        with pytest.raises(ChangeProposalStateError, match="superseded"):
            add_pantry(service, proposal, graph, source)
        assert len(proposals.get(proposal.id).operations) == 1

    def test_a_proposal_not_extracted_from_a_source(self, service, graph, source):
        proposal = service.propose(
            graph["taxonomy"],
            "By hand",
            [
                OperationDraft(
                    seq=1,
                    op=T.CREATE,
                    kind=K.INDIVIDUAL,
                    fields={"class_ids": [graph["room"]], "title": "Study"},
                )
            ],
            ProposalSource.USER,
        )

        with pytest.raises(ChangeProposalStateError, match="not an extraction"):
            add_pantry(service, proposal, graph, source)

    def test_a_proposal_without_a_dataset(self, service, graph, source):
        """A schema extraction: classes only, so no dataset to add an individual to."""
        proposal = service.propose(
            graph["taxonomy"],
            "Schema",
            [
                OperationDraft(
                    seq=1,
                    op=T.CREATE,
                    kind=K.CLASS,
                    fields={"concept_scheme_id": graph["vocab"], "title": "Larder"},
                )
            ],
            ProposalSource.PIPELINE,
            client_metadata={"source_id": source.id, "pipeline": "schema_extraction"},
        )

        with pytest.raises(ChangeProposalStateError, match="not an extraction"):
            add_pantry(service, proposal, graph, source)
