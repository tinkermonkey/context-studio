"""A reviewer's edit of an operation proposed with anchored edits (#1630)."""

from domain.versioning.proposals import OperationStatus
from tests.unit.domain.versioning.test_proposal_edits import (  # noqa: F401 - fixtures
    K,
    T,
    draft,
    graph,
    ontology,
    propose,
    repo,
    service,
)


def test_a_reviewer_edit_replaces_the_edits(service, graph, ontology):
    ontology.update_property_definition(graph["near"], description="Close by. Within reach.")
    edits = {"edits": [{"replace": "Within reach.", "with": "Nearby."}]}
    proposal = propose(
        service,
        graph,
        draft(1, T.UPDATE, K.PROPERTY, graph["near"], title="close to", description=edits),
    )
    operation = proposal.operations[0]
    assert operation.text_edits

    applied = service.apply(proposal.id, [operation.id], edits={operation.id: {"title": "next to"}})
    assert applied.operations[0].status is OperationStatus.APPLIED, applied.operations[0].reason
    assert ontology.get_property_definition(graph["near"]).title == "next to"
