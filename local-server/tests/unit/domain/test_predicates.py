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
from domain.versioning.proposals import OperationKind, OperationStatus, OperationType, ProposalSource
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
