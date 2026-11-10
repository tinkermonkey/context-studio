"""
Unit tests (#1482): a relationship type's structure (cardinality, hierarchy,
symmetric) is first-class and well formed, and its edge attributes are
attribute definitions its relationships' attributes are checked against.
"""

import pytest

from domain.ontology.entities import AttributeDefinition, PropertyDefinition
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

T, K = OperationType, OperationKind


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
        return RevertResult(run_id=run_id, events_reverted=0)


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def proposals(ontology):
    from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

    return ProposalService(
        FakeChangeProposalRepository(), ontology, ontology._repository, StubRevertService()
    )


@pytest.fixture()
def house(ontology):
    """A House: Task requires Resource (quantity, unit); Place part_of Place."""
    taxonomy = ontology.create_taxonomy(title="House", identifier="house")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Kinds")
    task = ontology.create_class(scheme.id, "Task", identifier="task")
    resource = ontology.create_class(scheme.id, "Resource", identifier="resource")
    place = ontology.create_class(scheme.id, "Place", identifier="place")
    requires = ontology.create_property_definition(
        "task_requires_resource",
        "requires",
        canonical_predicate="requires",
        domain_class_id=task.id,
        range_class_id=resource.id,
        create_missing_predicate=True,
    )
    ontology.create_attribute_definition(
        None, "quantity", "Quantity", "number", property_definition_id=requires.id
    )
    ontology.create_attribute_definition(
        None,
        "unit",
        "Unit",
        "string",
        allowed_values=["each", "kg"],
        default_value="each",
        is_required=True,
        property_definition_id=requires.id,
    )
    sweep = ontology.create_individual(task.id, "Sweep")
    broom = ontology.create_individual(resource.id, "Broom")
    return {
        "taxonomy": taxonomy.id,
        "task": task.id,
        "resource": resource.id,
        "place": place.id,
        "requires": requires.id,
        "sweep": sweep.id,
        "broom": broom.id,
    }


def prop(**fields):
    return PropertyDefinition(id="p", identifier="p", title="p", **fields)


class TestStructure:
    def test_a_default_type_is_well_formed(self):
        assert prop().structure_problems() == []

    @pytest.mark.parametrize(
        "fields, problem",
        [
            ({"min_per_source": -1}, "can't be negative"),
            ({"max_per_source": 0}, "max_per_source must be a whole number of at least 1"),
            ({"max_per_target": 1.5}, "max_per_target must be a whole number"),
            ({"min_per_source": 2, "max_per_source": 1}, "is above max_per_source"),
            ({"hierarchy": True, "domain_class_id": "a", "range_class_id": "b"}, "same domain"),
            ({"symmetric": True, "domain_class_id": "a"}, "a symmetric relationship type needs"),
        ],
    )
    def test_ill_formed_structure_is_named(self, fields, problem):
        assert any(problem in p for p in prop(**fields).structure_problems())

    def test_a_tree_is_a_hierarchy_with_one_parent(self, ontology, house):
        part_of = ontology.create_property_definition(
            "place_part_of_place",
            "part of",
            domain_class_id=house["place"],
            range_class_id=house["place"],
            hierarchy=True,
            max_per_source=1,
        )
        assert (part_of.hierarchy, part_of.max_per_source) == (True, 1)

    def test_the_service_refuses_ill_formed_structure(self, ontology, house):
        with pytest.raises(ValueError, match="same domain and range"):
            ontology.create_property_definition(
                "task_next_resource",
                "next",
                domain_class_id=house["task"],
                range_class_id=house["resource"],
                symmetric=True,
            )
        with pytest.raises(ValueError, match="is above max_per_source"):
            ontology.update_property_definition(
                house["requires"], structure={"min_per_source": 3, "max_per_source": 2}
            )

    def test_an_update_clears_a_maximum(self, ontology, house):
        ontology.update_property_definition(house["requires"], structure={"max_per_target": 1})
        updated = ontology.update_property_definition(
            house["requires"], structure={"max_per_target": None}
        )
        assert updated.max_per_target is None


class TestEdgeAttributes:
    def test_an_attribute_belongs_to_exactly_one_owner(self):
        with pytest.raises(ValueError, match="exactly one"):
            AttributeDefinition(
                id="a",
                class_id="c",
                property_definition_id="p",
                identifier="note",
                title="Note",
                datatype="string",
            )

    def test_an_edge_attribute_holds_a_single_value(self, ontology, house):
        with pytest.raises(ValueError, match="single value"):
            ontology.create_attribute_definition(
                None, "parts", "Parts", "array", property_definition_id=house["requires"]
            )

    def test_relationship_attributes_are_checked_and_a_default_fills_in(self, ontology, house):
        rel = ontology.create_relationship(
            house["sweep"], house["broom"], house["requires"], attributes={"quantity": 2}
        )
        assert rel.attributes == {"quantity": 2, "unit": "each"}

    @pytest.mark.parametrize(
        "attributes, problem",
        [
            ({"colour": "red"}, "does not allow attributes ['colour']"),
            ({"quantity": "two"}, "'quantity' is number, so 'two' doesn't fit"),
            ({"unit": "lb"}, "'unit' allows only ['each', 'kg'], not 'lb'"),
        ],
    )
    def test_an_unknown_or_mistyped_attribute_is_refused(self, ontology, house, attributes, problem):
        with pytest.raises(ValueError, match=problem.replace("[", r"\[").replace("]", r"\]")):
            ontology.create_relationship(
                house["sweep"], house["broom"], house["requires"], attributes=attributes
            )


class TestProposals:
    def test_a_proposal_sets_structure_and_adds_an_edge_attribute(
        self, proposals, ontology, house
    ):
        drafts = [
            OperationDraft(
                1,
                T.UPDATE,
                K.PROPERTY,
                house["requires"],
                fields={"min_per_source": 1, "max_per_target": None},
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.ATTRIBUTE,
                fields={
                    "property_definition_id": house["requires"],
                    "identifier": "optional",
                    "title": "Optional",
                    "datatype": "boolean",
                },
            ),
        ]
        proposal = proposals.propose(house["taxonomy"], "Structure", drafts, ProposalSource.MCP)
        applied = proposals.apply(proposal.id, [o.id for o in proposal.operations]).operations

        assert [o.status for o in applied] == [OperationStatus.APPLIED] * 2, [
            o.reason for o in applied
        ]
        assert ontology.get_property_definition(house["requires"]).min_per_source == 1
        names = [
            a.identifier
            for a in ontology.list_attribute_definitions(property_definition_id=house["requires"])
        ]
        assert sorted(names) == ["optional", "quantity", "unit"]

    def test_an_attribute_create_needs_exactly_one_owner(self, proposals, house):
        draft = OperationDraft(
            1,
            T.CREATE,
            K.ATTRIBUTE,
            fields={
                "class_id": house["task"],
                "property_definition_id": house["requires"],
                "identifier": "x",
                "title": "x",
                "datatype": "string",
            },
        )
        with pytest.raises(ProposalValidationError) as excinfo:
            proposals.propose(house["taxonomy"], "Two owners", [draft], ProposalSource.MCP)
        assert "exactly one owner" in excinfo.value.errors[0].message

    def test_an_ill_formed_structure_fails_as_it_applies(self, proposals, house):
        draft = OperationDraft(
            1, T.UPDATE, K.PROPERTY, house["requires"], fields={"hierarchy": True}
        )
        proposal = proposals.propose(house["taxonomy"], "Tree", [draft], ProposalSource.MCP)
        (applied,) = proposals.apply(proposal.id, [proposal.operations[0].id]).operations

        assert applied.status is OperationStatus.FAILED
        assert "same domain and range" in applied.reason


class TestReviewFixes:
    def test_an_edge_attribute_cant_be_updated_to_array(self, ontology, house):
        [quantity] = [
            a
            for a in ontology.list_attribute_definitions(property_definition_id=house["requires"])
            if a.identifier == "quantity"
        ]
        with pytest.raises(ValueError, match="single value"):
            ontology.update_attribute_definition(quantity.id, datatype="array")

    def test_deleting_a_type_deletes_its_edge_attributes_with_events(self, ontology, house):
        from domain.ontology.events import AttributeDefinitionDeleted

        ontology.delete_property_definition(house["requires"])

        deleted = ontology._event_publisher.get_events_of_type(AttributeDefinitionDeleted)
        assert sorted(e.identifier for e in deleted) == ["quantity", "unit"]
        assert all(e.snapshot["property_definition_id"] == house["requires"] for e in deleted)

    def test_an_edge_attribute_create_is_never_auto_applied(self, proposals, house):
        draft = OperationDraft(
            1,
            T.CREATE,
            K.ATTRIBUTE,
            fields={
                "property_definition_id": house["requires"],
                "identifier": "note",
                "title": "Note",
                "datatype": "string",
            },
        )
        proposal = proposals.propose(house["taxonomy"], "Note", [draft], ProposalSource.MCP)
        assert not proposals._inside_taxonomy(proposal.operations[0], house["taxonomy"])
