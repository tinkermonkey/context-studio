"""Proposals whose updates give description or vision as anchored edits (#1630)."""

import pytest

from domain.ontology.services import OntologyService
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationDraft, OperationKind as K
from domain.versioning.proposals import OperationStatus
from domain.versioning.proposals import OperationType as T
from domain.versioning.proposals import ProposalSource
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

VISION = "- **Knowing who the house deals with:** contacts.\n- **Fixing things:** repairs.\n"
BUYING = "- **Buying where it's in stock:** stores.\n"
INSERT_BUYING = {"edits": [{"after": "contacts.\n", "insert": BUYING}]}


class StubRevertService:
    def revert_with_summary(self, run_id: str, on_reverted=None) -> RevertResult:
        return RevertResult(run_id=run_id, events_reverted=0)


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def service(ontology):
    return ProposalService(
        FakeChangeProposalRepository(), ontology, ontology._repository, StubRevertService()
    )


@pytest.fixture()
def taxonomy(ontology):
    return ontology.create_taxonomy(title="House", vision=VISION).id


def _propose(service, taxonomy, fields, op=T.UPDATE, kind=K.TAXONOMY, target=None):
    return service.propose(
        taxonomy,
        "Vision",
        [OperationDraft(1, op, kind, target or taxonomy, fields=fields)],
        ProposalSource.MCP,
    )


def _errors(raised):
    return [(e.code, e.message) for e in raised.value.errors]


def test_edits_resolve_to_the_text_they_make(service, taxonomy):
    operation = _propose(service, taxonomy, {"vision": INSERT_BUYING}).operations[0]
    assert operation.text_edits == {"vision": INSERT_BUYING["edits"]}
    assert operation.base == {"vision": VISION}
    assert operation.fields["vision"] == VISION.replace("contacts.\n", "contacts.\n" + BUYING)
    assert operation.scope.value == "editorial"


def test_a_missing_anchor_refuses_the_proposal(service, taxonomy):
    with pytest.raises(ProposalValidationError) as raised:
        _propose(service, taxonomy, {"vision": {"edits": [{"delete": "gardening"}]}})
    [(code, message)] = _errors(raised)
    assert code == "anchor_not_found"
    assert message.startswith("vision: edit 1: anchor 'gardening'")


def test_an_ambiguous_anchor_refuses_the_proposal(service, taxonomy):
    with pytest.raises(ProposalValidationError) as raised:
        _propose(service, taxonomy, {"vision": {"edits": [{"after": "- **", "insert": "x"}]}})
    assert _errors(raised)[0][0] == "anchor_not_unique"


def test_malformed_edits_are_invalid(service, taxonomy):
    with pytest.raises(ProposalValidationError) as raised:
        _propose(service, taxonomy, {"vision": {"edits": [{"after": "contacts."}]}})
    assert _errors(raised)[0][0] == "invalid"


def test_only_an_update_takes_edits(service, ontology, taxonomy):
    scheme = ontology.create_scheme(taxonomy_id=taxonomy, title="Vocabulary").id
    with pytest.raises(ProposalValidationError) as raised:
        service.propose(
            taxonomy,
            "New",
            [
                OperationDraft(
                    1,
                    T.CREATE,
                    K.CLASS,
                    fields={"concept_scheme_id": scheme, "title": "Room", "description": INSERT_BUYING},
                )
            ],
            ProposalSource.MCP,
        )
    assert _errors(raised)[0] == ("invalid", "Only an update can give a field as anchored edits")


def test_a_class_description_takes_edits(service, ontology, taxonomy):
    scheme = ontology.create_scheme(taxonomy_id=taxonomy, title="Vocabulary").id
    room = ontology.create_class(scheme, "Room", description="A room. Has walls.").id
    fields = {"description": {"edits": [{"replace": "Has walls.", "with": "Has walls and a door."}]}}
    operation = _propose(service, taxonomy, fields, kind=K.CLASS, target=room).operations[0]
    assert operation.fields["description"] == "A room. Has walls and a door."


def test_accepting_applies_the_edits_to_the_text_as_it_is_now(service, ontology, taxonomy):
    proposal = _propose(service, taxonomy, {"vision": INSERT_BUYING})
    operation = proposal.operations[0]
    # Someone else changes another part of the vision meanwhile.
    changed = VISION.replace("repairs.", "repairs and upkeep.")
    ontology.update_taxonomy(taxonomy, vision=changed)

    assert service.stale_operation_ids(proposal) == set()
    applied = service.apply(proposal.id, [operation.id]).operations[0]

    expected = changed.replace("contacts.\n", "contacts.\n" + BUYING)
    assert applied.status is OperationStatus.APPLIED
    assert ontology.get_taxonomy(taxonomy).vision == expected
    # The operation records the text it applied the edits to and what they made.
    stored = service.get(proposal.id).operations[0]
    assert stored.base == {"vision": changed}
    assert stored.fields == {"vision": expected}


def test_an_anchor_gone_since_makes_the_operation_stale(service, ontology, taxonomy):
    proposal = _propose(service, taxonomy, {"vision": INSERT_BUYING})
    operation = proposal.operations[0]
    ontology.update_taxonomy(taxonomy, vision=VISION.replace("contacts.", "people."))

    assert service.stale_operation_ids(proposal) == {operation.id}
    failed = service.apply(proposal.id, [operation.id]).operations[0]
    assert failed.status is OperationStatus.FAILED
    assert failed.reason.startswith("target_changed: vision changed since proposed; vision edit 1:")
    assert ontology.get_taxonomy(taxonomy).vision == VISION.replace("contacts.", "people.")


def test_forcing_past_a_gone_anchor_writes_the_proposed_text(service, ontology, taxonomy):
    proposal = _propose(service, taxonomy, {"vision": INSERT_BUYING})
    operation = proposal.operations[0]
    ontology.update_taxonomy(taxonomy, vision="Rewritten.")

    service.apply(proposal.id, [operation.id], force_stale=[operation.id])
    assert ontology.get_taxonomy(taxonomy).vision == operation.fields["vision"]


def test_another_field_of_the_same_operation_still_goes_stale(service, ontology, taxonomy):
    proposal = _propose(service, taxonomy, {"vision": INSERT_BUYING, "title": "Home"})
    ontology.update_taxonomy(taxonomy, title="Household")
    assert service.stale_operation_ids(proposal) == {proposal.operations[0].id}


def test_amending_reapplies_the_edits_to_the_current_text(service, ontology, taxonomy):
    proposal = _propose(service, taxonomy, {"vision": INSERT_BUYING})
    ontology.update_taxonomy(taxonomy, vision=VISION.replace("repairs.", "repairs and upkeep."))
    edits = {"edits": [{"after": "upkeep.", "insert": " Weekly."}]}
    amended = service.amend(
        proposal.id, replace=[OperationDraft(1, T.UPDATE, K.TAXONOMY, taxonomy, fields={"vision": edits})]
    ).operations[0]
    assert amended.text_edits == {"vision": edits["edits"]}
    assert amended.base == {"vision": VISION.replace("repairs.", "repairs and upkeep.")}
    assert amended.fields["vision"].endswith("repairs and upkeep. Weekly.\n")
    assert amended.amendments[0]["text_edits"] == {"vision": INSERT_BUYING["edits"]}
