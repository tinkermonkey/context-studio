"""
Unit tests (#1487): a proposal's individual and relationship operations are in
one dataset. It is named (by id or identifier) or implied when the taxonomy has
only one; no operation reaches an individual of another dataset; creates go in.
"""

import pytest

from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposals import OperationStatus, ProposalSource
from tests.unit.domain.versioning.test_proposal_service import (  # noqa: F401 - fixtures
    K,
    T,
    draft,
    graph,
    ontology,
    proposals,
    publisher,
    repo,
    reverter,
    service,
)


@pytest.fixture()
def platforms(ontology, graph):
    """The House taxonomy's `default` (holding Den) plus a second dataset with its own Den."""
    [default] = ontology.list_datasets(graph["taxonomy"])
    other = ontology.create_dataset(graph["taxonomy"], "annex", "Annex")
    annex_den = ontology.create_individual(graph["room"], "Den", dataset_id=other.id)
    return {"default": default, "annex": other, "annex_den": annex_den.id}


def _propose(service, graph, *drafts, dataset=None, dry_run=False):
    return service.propose(
        graph["taxonomy"],
        "Data",
        list(drafts),
        ProposalSource.MCP,
        dataset_id=dataset,
        dry_run=dry_run,
    )


def test_a_single_dataset_is_implied(service, graph, ontology):
    [default] = ontology.list_datasets(graph["taxonomy"])

    proposal = _propose(
        service, graph, draft(1, T.CREATE, K.INDIVIDUAL, class_ids=[graph["room"]], title="Hall")
    )

    assert proposal.dataset_id == default.id


def test_several_datasets_need_one_named_and_the_error_lists_them(service, graph, platforms):
    with pytest.raises(ProposalValidationError, match="dataset_required.*annex, default"):
        _propose(
            service,
            graph,
            draft(1, T.CREATE, K.INDIVIDUAL, class_ids=[graph["room"]], title="Hall"),
        )


def test_a_dataset_can_be_named_by_identifier_and_creates_go_into_it(
    service, graph, platforms, repo
):
    proposal = _propose(
        service,
        graph,
        draft(1, T.CREATE, K.INDIVIDUAL, class_ids=[graph["room"]], title="Hall"),
        dataset="annex",
    )

    applied = service.apply(proposal.id, [proposal.operations[0].id])

    assert applied.dataset_id == platforms["annex"].id
    created = repo.get_individual(applied.operations[0].result_entity_id)
    assert created.dataset_id == platforms["annex"].id


def test_an_operation_cant_reach_another_datasets_individual(service, graph, platforms):
    with pytest.raises(ProposalValidationError, match="dataset_mismatch"):
        _propose(
            service,
            graph,
            draft(1, T.UPDATE, K.INDIVIDUAL, graph["den"], title="Study"),
            dataset="annex",
        )


def test_a_relationship_cant_link_individuals_across_datasets(service, graph, platforms):
    with pytest.raises(ProposalValidationError, match="dataset_mismatch"):
        _propose(
            service,
            graph,
            draft(
                1,
                T.CREATE,
                K.RELATIONSHIP,
                source_id=platforms["annex_den"],
                target_id=graph["den"],
                property_definition_id=graph["near"],
            ),
            dataset="annex",
        )


def test_schema_only_proposals_have_no_dataset(service, graph, platforms):
    proposal = _propose(
        service, graph, draft(1, T.CREATE, K.CLASS, concept_scheme_id=graph["vocab"], title="Hall")
    )

    assert proposal.dataset_id is None
    assert proposal.operations[0].status is OperationStatus.PENDING


def test_a_dry_run_on_a_taxonomy_without_datasets_creates_none(service, ontology):
    taxonomy = ontology.create_taxonomy(title="Fresh")
    scheme = ontology.create_scheme(taxonomy.id, title="S")
    cls = ontology.create_class(scheme.id, "C")

    proposal = service.propose(
        taxonomy.id,
        "Dry",
        [draft(1, T.CREATE, K.INDIVIDUAL, class_ids=[cls.id], title="I")],
        ProposalSource.MCP,
        dry_run=True,
    )

    assert proposal.dataset_id is None
    assert ontology.list_datasets(taxonomy.id) == []
