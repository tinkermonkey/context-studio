"""
Unit tests (#1480): predicates are first-class, one catalog per taxonomy. A
relationship type's predicate must be in its taxonomy's catalog; Context
Studio's own editors add a missing one, clients (proposals) can't.
"""

import pytest

from domain.ontology.entities import Predicate
from domain.ontology.exceptions import DuplicateEntityError, EntityInUseError
from domain.ontology.services import OntologyService
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
)
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

T, K = OperationType, OperationKind


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
        return RevertResult(run_id=run_id, events_reverted=0)


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def proposals(ontology):
    return ProposalService(
        FakeChangeProposalRepository(), ontology, ontology._repository, StubRevertService()
    )


@pytest.fixture()
def house(ontology):
    """Two taxonomies that both say part_of: House (Place, Room) and Garden (Bed)."""
    house = ontology.create_taxonomy(title="House", identifier="house")
    scheme = ontology.create_scheme(taxonomy_id=house.id, title="Spaces")
    place = ontology.create_class(scheme.id, "Place", identifier="place")
    room = ontology.create_class(scheme.id, "Room", identifier="room")
    garden = ontology.create_taxonomy(title="Garden", identifier="garden")
    beds = ontology.create_scheme(taxonomy_id=garden.id, title="Beds")
    bed = ontology.create_class(beds.id, "Bed", identifier="bed")
    part_of = ontology.create_predicate(house.id, "part_of", description="Whole and part")
    return {
        "taxonomy": house.id,
        "garden": garden.id,
        "place": place.id,
        "room": room.id,
        "bed": bed.id,
        "part_of": part_of.id,
    }


class TestPredicateEntity:
    @pytest.mark.parametrize("identifier", ["part_of", "navigates-to", "is_a", "p2"])
    def test_a_verb_is_a_predicate_identifier(self, identifier):
        assert Predicate(id="1", taxonomy_id="t", identifier=identifier).title == identifier

    @pytest.mark.parametrize("identifier", ["", "Part Of", "part of", "-x", "2p", "a.b"])
    def test_anything_else_is_refused(self, identifier):
        with pytest.raises(ValueError):
            Predicate(id="1", taxonomy_id="t", identifier=identifier)


class TestCatalog:
    def test_each_taxonomy_has_its_own_catalog(self, ontology, house):
        ontology.create_predicate(house["garden"], "part_of")

        assert [p.identifier for p in ontology.list_predicates(house["taxonomy"])] == ["part_of"]
        assert [p.identifier for p in ontology.list_predicates(house["garden"])] == ["part_of"]

    def test_a_taxonomy_holds_a_predicate_once(self, ontology, house):
        with pytest.raises(DuplicateEntityError):
            ontology.create_predicate(house["taxonomy"], "part_of")

    def test_an_update_keeps_the_identifier(self, ontology, house):
        updated = ontology.update_predicate(house["part_of"], description="Contained in")

        assert (updated.identifier, updated.description) == ("part_of", "Contained in")

    def test_a_taxonomy_whose_predicates_types_use_cant_be_deleted(self, ontology):
        empty = ontology.create_taxonomy(title="Empty", identifier="empty")
        ontology.create_predicate(empty.id, "near")
        ontology.create_property_definition(
            "near", "Near", canonical_predicate="near", taxonomy_id=empty.id
        )
        with pytest.raises(EntityInUseError):
            ontology.delete_taxonomy(empty.id)


class TestRelationshipTypes:
    def test_a_type_points_at_its_taxonomys_predicate(self, ontology, house):
        prop = ontology.create_property_definition(
            "room_part_of_place",
            "Room part of place",
            canonical_predicate="part_of",
            domain_class_id=house["room"],
            range_class_id=house["place"],
        )

        assert (prop.predicate_id, prop.canonical_predicate) == (house["part_of"], "part_of")

    def test_a_predicate_the_catalog_lacks_is_refused(self, ontology, house):
        with pytest.raises(ValueError, match="isn't in taxonomy"):
            ontology.create_property_definition(
                "room_next_to_place",
                "Room next to place",
                canonical_predicate="next_to",
                domain_class_id=house["room"],
            )
        assert ontology.list_predicates(house["taxonomy"])[0].identifier == "part_of"

    def test_cs_editors_add_a_missing_predicate(self, ontology, house):
        prop = ontology.create_property_definition(
            "room_next_to_place",
            "Room next to place",
            canonical_predicate="next_to",
            domain_class_id=house["room"],
            create_missing_predicate=True,
        )

        added = ontology.get_predicate(prop.predicate_id)
        assert (added.taxonomy_id, added.identifier) == (house["taxonomy"], "next_to")

    def test_the_catalog_is_the_domain_classs_taxonomy_else_the_ranges(self, ontology, house):
        garden_part_of = ontology.create_predicate(house["garden"], "part_of")

        prop = ontology.create_property_definition(
            "bed_part_of_place",
            "Bed part of place",
            canonical_predicate="part_of",
            range_class_id=house["bed"],
        )

        assert prop.predicate_id == garden_part_of.id

    def test_a_type_with_no_ends_uses_the_given_taxonomy_or_none(self, ontology, house):
        prop = ontology.create_property_definition(
            "part_of", "Part of", canonical_predicate="part_of", taxonomy_id=house["taxonomy"]
        )
        assert prop.predicate_id == house["part_of"]
        with pytest.raises(ValueError, match="needs a taxonomy"):
            ontology.create_property_definition(
                "contains", "Contains", canonical_predicate="part_of"
            )

    def test_changing_the_predicate_looks_it_up_again(self, ontology, house):
        prop = ontology.create_property_definition(
            "room_part_of_place",
            "Room part of place",
            canonical_predicate="part_of",
            domain_class_id=house["room"],
        )
        within = ontology.create_predicate(house["taxonomy"], "within")

        updated = ontology.update_property_definition(
            prop.id, canonical_predicate="within", update_canonical_predicate=True
        )

        assert (updated.predicate_id, updated.canonical_predicate) == (within.id, "within")
        with pytest.raises(ValueError, match="isn't in taxonomy"):
            ontology.update_property_definition(
                prop.id, canonical_predicate="beside", update_canonical_predicate=True
            )

    def test_a_types_predicate_cant_be_cleared(self, ontology, house):
        prop = ontology.create_property_definition(
            "room_part_of_place",
            "Room part of place",
            canonical_predicate="part_of",
            domain_class_id=house["room"],
        )
        with pytest.raises(ValueError, match="can't be cleared"):
            ontology.update_property_definition(
                prop.id, canonical_predicate=None, update_canonical_predicate=True
            )


def propose(proposals, house, fields, op=T.CREATE, target_id=None):
    draft = OperationDraft(1, op, K.PROPERTY, target_id, fields=fields)
    return proposals.propose(house["taxonomy"], "Types", [draft], ProposalSource.MCP)


class TestProposals:
    def test_a_proposal_may_use_a_catalog_predicate(self, proposals, ontology, house):
        proposal = propose(
            proposals,
            house,
            {
                "identifier": "room_part_of_place",
                "title": "Room part of place",
                "canonical_predicate": "part_of",
                "domain_class_id": house["room"],
                "range_class_id": house["place"],
            },
        )
        applied = proposals.apply(proposal.id, [proposal.operations[0].id]).operations[0]

        assert applied.status is OperationStatus.APPLIED, applied.reason
        prop = ontology.get_property_definition(applied.result_entity_id)
        assert prop.predicate_id == house["part_of"]

    def test_a_proposal_cant_use_a_predicate_the_catalog_lacks(self, proposals, house):
        with pytest.raises(ProposalValidationError) as excinfo:
            propose(
                proposals,
                house,
                {
                    "identifier": "room_next_to_place",
                    "title": "Room next to place",
                    "canonical_predicate": "next_to",
                    "domain_class_id": house["room"],
                },
            )
        ((error),) = excinfo.value.errors
        assert error.code == "unknown_predicate"
        assert "'next_to'" in error.message

    def test_the_catalog_checked_is_the_domain_classs_taxonomy(self, proposals, house):
        # Garden has no part_of, so a type whose domain is a Garden class can't use it.
        with pytest.raises(ProposalValidationError) as excinfo:
            propose(
                proposals,
                house,
                {
                    "identifier": "bed_part_of_place",
                    "title": "Bed part of place",
                    "canonical_predicate": "part_of",
                    "domain_class_id": house["bed"],
                },
            )
        assert excinfo.value.errors[0].code == "unknown_predicate"

    def test_a_proposal_cant_clear_a_predicate(self, proposals, ontology, house):
        prop = ontology.create_property_definition(
            "room_part_of_place",
            "Room part of place",
            canonical_predicate="part_of",
            domain_class_id=house["room"],
        )
        with pytest.raises(ProposalValidationError):
            propose(proposals, house, {"canonical_predicate": None}, T.UPDATE, prop.id)

    def test_a_type_with_no_ends_finds_its_predicate_in_the_proposals_taxonomy(
        self, proposals, ontology, house
    ):
        proposal = propose(
            proposals,
            house,
            {"identifier": "part_of", "title": "Part of", "canonical_predicate": "part_of"},
        )
        applied = proposals.apply(proposal.id, [proposal.operations[0].id]).operations[0]

        assert applied.status is OperationStatus.APPLIED, applied.reason
        assert ontology.get_property_definition(applied.result_entity_id).predicate_id == (
            house["part_of"]
        )

    def test_a_new_domain_in_another_taxonomy_needs_the_predicate_there(
        self, proposals, ontology, house
    ):
        prop = ontology.create_property_definition(
            "room_part_of_place",
            "Room part of place",
            canonical_predicate="part_of",
            domain_class_id=house["room"],
        )
        with pytest.raises(ProposalValidationError) as excinfo:
            propose(proposals, house, {"domain_class_id": house["bed"]}, T.UPDATE, prop.id)
        assert excinfo.value.errors[0].code == "unknown_predicate"

        garden_part_of = ontology.create_predicate(house["garden"], "part_of")
        proposal = propose(proposals, house, {"domain_class_id": house["bed"]}, T.UPDATE, prop.id)
        applied = proposals.apply(proposal.id, [proposal.operations[0].id]).operations[0]
        assert applied.status is OperationStatus.APPLIED, applied.reason
        assert ontology.get_property_definition(prop.id).predicate_id == garden_part_of.id

    def test_a_reviewer_edit_moving_the_domain_is_checked_too(self, proposals, ontology, house):
        prop = ontology.create_property_definition(
            "room_part_of_place",
            "Room part of place",
            canonical_predicate="part_of",
            domain_class_id=house["room"],
        )
        proposal = propose(proposals, house, {"title": "Room within place"}, T.UPDATE, prop.id)
        op_id = proposal.operations[0].id

        applied = proposals.apply(
            proposal.id, [op_id], edits={op_id: {"domain_class_id": house["bed"]}}
        ).operations[0]

        assert applied.status is OperationStatus.FAILED
        assert applied.reason.startswith("invalid_edit: predicate 'part_of' isn't in taxonomy")


def apply_all(proposals, proposal):
    return proposals.apply(proposal.id, [o.id for o in proposal.operations])


class TestPredicateProposals:
    """#1481: predicates are created, changed and retired by proposal."""

    def test_a_proposal_creates_a_predicate_and_uses_it_in_a_later_operation(
        self, proposals, ontology, house
    ):
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.PREDICATE,
                ref="next",
                fields={"identifier": "next_to", "description": "Beside"},
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.PROPERTY,
                fields={
                    "identifier": "room_next_to_place",
                    "title": "Room next to place",
                    "canonical_predicate": "next_to",
                    "domain_class_id": house["room"],
                },
            ),
        ]
        proposal = proposals.propose(house["taxonomy"], "Next to", drafts, ProposalSource.MCP)
        assert [o.scope.value for o in proposal.operations] == ["additive", "additive"]

        applied = apply_all(proposals, proposal).operations

        assert [o.status for o in applied] == [OperationStatus.APPLIED] * 2, applied
        predicate = ontology.get_predicate(applied[0].result_entity_id)
        assert (predicate.taxonomy_id, predicate.identifier) == (house["taxonomy"], "next_to")
        assert ontology.get_property_definition(applied[1].result_entity_id).predicate_id == (
            predicate.id
        )

    @pytest.mark.parametrize(
        "identifier, code",
        [("part_of", "duplicate"), ("Part Of", "invalid"), (None, "missing_field")],
    )
    def test_a_create_needs_a_new_valid_identifier(self, proposals, house, identifier, code):
        draft = OperationDraft(1, T.CREATE, K.PREDICATE, fields={"identifier": identifier})
        with pytest.raises(ProposalValidationError) as excinfo:
            proposals.propose(house["taxonomy"], "Dup", [draft], ProposalSource.MCP)
        assert excinfo.value.errors[0].code == code

    def test_an_update_changes_wording_and_metadata_not_the_identifier(
        self, proposals, ontology, house
    ):
        refs = [{"source": "documentation_robotics", "identifier": "part_of", "metadata": {}}]
        draft = OperationDraft(
            1,
            T.UPDATE,
            K.PREDICATE,
            house["part_of"],
            fields={"description": "Contained in", "external_references": refs},
        )
        proposal = proposals.propose(house["taxonomy"], "Reword", [draft], ProposalSource.MCP)
        assert apply_all(proposals, proposal).operations[0].status is OperationStatus.APPLIED

        predicate = ontology.get_predicate(house["part_of"])
        assert (predicate.identifier, predicate.description) == ("part_of", "Contained in")
        assert predicate.external_references[0].source == "documentation_robotics"
        bad = OperationDraft(1, T.UPDATE, K.PREDICATE, house["part_of"], fields={"identifier": "x"})
        with pytest.raises(ProposalValidationError):
            proposals.propose(house["taxonomy"], "Rename", [bad], ProposalSource.MCP)

    def test_a_delete_in_use_needs_a_replacement(self, proposals, ontology, house):
        ontology.create_property_definition(
            "room_part_of_place",
            "Room part of place",
            canonical_predicate="part_of",
            domain_class_id=house["room"],
        )
        draft = OperationDraft(1, T.DELETE, K.PREDICATE, house["part_of"])
        with pytest.raises(ProposalValidationError) as excinfo:
            proposals.propose(house["taxonomy"], "Retire", [draft], ProposalSource.MCP)
        assert excinfo.value.errors[0].code == "in_use"

    def test_a_delete_with_a_replacement_moves_the_types_using_it(self, proposals, ontology, house):
        prop = ontology.create_property_definition(
            "room_part_of_place",
            "Room part of place",
            canonical_predicate="part_of",
            domain_class_id=house["room"],
        )
        within = ontology.create_predicate(house["taxonomy"], "within")
        draft = OperationDraft(1, T.DELETE, K.PREDICATE, house["part_of"], replacement="within")
        proposal = proposals.propose(house["taxonomy"], "Retire", [draft], ProposalSource.MCP)
        operation = proposal.operations[0]
        assert (operation.scope.value, operation.proposed_replacement_id) == ("breaking", within.id)

        applied = apply_all(proposals, proposal).operations[0]

        assert applied.status is OperationStatus.APPLIED, applied.reason
        assert ontology._repository.get_predicate(house["part_of"]) is None
        moved = ontology.get_property_definition(prop.id)
        assert (moved.predicate_id, moved.canonical_predicate) == (within.id, "within")

    def test_a_replacement_comes_from_the_same_catalog(self, proposals, ontology, house):
        elsewhere = ontology.create_predicate(house["garden"], "within")
        draft = OperationDraft(1, T.DELETE, K.PREDICATE, house["part_of"], replacement=elsewhere.id)
        with pytest.raises(ProposalValidationError) as excinfo:
            proposals.propose(house["taxonomy"], "Retire", [draft], ProposalSource.MCP)
        assert excinfo.value.errors[0].code == "replacement_not_found"

    def test_a_predicate_of_another_taxonomy_cant_be_changed_here(self, proposals, ontology, house):
        elsewhere = ontology.create_predicate(house["garden"], "grows_in")
        draft = OperationDraft(1, T.UPDATE, K.PREDICATE, elsewhere.id, fields={"title": "x"})
        with pytest.raises(ProposalValidationError) as excinfo:
            proposals.propose(house["taxonomy"], "Reword", [draft], ProposalSource.MCP)
        assert "another taxonomy" in excinfo.value.errors[0].message
