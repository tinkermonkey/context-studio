"""
Unit tests (#1415): a proposal sets an individual's attribute values
(data_properties), checked against its classes' attributes, inherited ones
included, and their datatypes.
"""

import pytest

from domain.ontology.events import IndividualCreated
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import DataPropertyValue
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    ChangeScope,
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
S = ChangeScope


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
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
def house(ontology):
    """Resource (brand, required count) > Tool (powered, size in S/M/L); Place beside them."""
    taxonomy = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Life")
    resource = ontology.create_class(scheme.id, "Resource", identifier="resource")
    tool = ontology.create_class(scheme.id, "Tool", identifier="tool", parent_class_id=resource.id)
    place = ontology.create_class(scheme.id, "Place", identifier="place")
    ontology.create_attribute_definition(resource.id, "brand", "Brand", "string")
    ontology.create_attribute_definition(resource.id, "count", "Count", "integer", is_required=True)
    ontology.create_attribute_definition(tool.id, "powered", "Powered", "boolean")
    ontology.create_attribute_definition(
        tool.id, "size", "Size", "string", allowed_values=["S", "M", "L"]
    )
    ontology.create_attribute_definition(place.id, "floor", "Floor", "integer")
    drill = ontology.create_individual(tool.id, "Drill")
    ontology.update_individual(
        drill.id,
        data_properties=[
            DataPropertyValue("brand", "Bosch", "xsd:string"),
            DataPropertyValue("count", 1, "xsd:integer"),
        ],
    )
    return {
        "taxonomy": taxonomy.id,
        "scheme": scheme.id,
        "resource": resource.id,
        "tool": tool.id,
        "place": place.id,
        "drill": drill.id,
    }


def propose(service, house, *drafts):
    return service.propose(house["taxonomy"], "Kit", list(drafts), ProposalSource.MCP)


def create(seq, class_ids, title, data, ref=None):
    return OperationDraft(
        seq,
        T.CREATE,
        K.INDIVIDUAL,
        ref=ref,
        fields={"class_ids": class_ids, "title": title, "data_properties": data},
    )


def update(seq, target, data, **fields):
    return OperationDraft(
        seq, T.UPDATE, K.INDIVIDUAL, target, fields={"data_properties": data, **fields}
    )


def apply_all(service, proposal):
    return service.apply(proposal.id, [o.id for o in proposal.operations])


def values(ontology, individual_id):
    individual = ontology.get_individual(individual_id)
    return {v.property_identifier: (v.value, v.datatype) for v in individual.data_properties}


def problems(excinfo):
    return [(e.seq, e.code, e.message) for e in excinfo.value.errors]


class TestCreate:
    def test_a_create_sets_values_of_own_and_inherited_attributes(self, service, house, ontology):
        data = {"brand": "Makita", "count": 2, "powered": True, "size": "M"}
        proposal = propose(service, house, create(1, [house["tool"]], "Saw", data))
        op = proposal.operations[0]
        assert op.scope is S.ADDITIVE

        applied = apply_all(service, proposal).operations[0]

        assert applied.status is OperationStatus.APPLIED, applied.reason
        assert values(ontology, applied.result_entity_id) == {
            "brand": ("Makita", "xsd:string"),
            "count": (2, "xsd:integer"),
            "powered": (True, "xsd:boolean"),
            "size": ("M", "xsd:string"),
        }

    def test_an_attribute_the_classes_dont_have_fails_with_a_clear_reason(self, service, house):
        with pytest.raises(ProposalValidationError) as excinfo:
            propose(service, house, create(1, [house["resource"]], "Rope", {"powered": True}))
        ((seq, code, message),) = problems(excinfo)
        assert (seq, code) == (1, "invalid")
        assert message == (
            "data_properties 'powered' is not an attribute of the individual's classes "
            "(theirs and inherited: brand, count)"
        )

    @pytest.mark.parametrize(
        "data, expected",
        [
            ({"count": "two"}, "data_properties 'count' is integer, so 'two' doesn't fit"),
            ({"count": True}, "data_properties 'count' is integer, so True doesn't fit"),
            ({"powered": "yes"}, "data_properties 'powered' is boolean, so 'yes' doesn't fit"),
            ({"size": "XL"}, "data_properties 'size' allows only ['S', 'M', 'L'], not ['XL']"),
            ({"brand": None}, "data_properties ['brand'] can't be null on a create"),
        ],
    )
    def test_a_value_that_doesnt_fit_its_datatype_fails(self, service, house, data, expected):
        with pytest.raises(ProposalValidationError) as excinfo:
            propose(service, house, create(1, [house["tool"]], "Saw", data))
        assert problems(excinfo) == [(1, "invalid", expected)]

    def test_values_must_be_a_map_of_identifiers(self, service, house):
        with pytest.raises(ProposalValidationError) as excinfo:
            propose(service, house, create(1, [house["tool"]], "Saw", [{"brand": "x"}]))
        assert problems(excinfo)[0][2].startswith("data_properties has the wrong type")

    def test_an_attribute_of_a_class_the_proposal_creates_is_checked_when_applied(
        self, service, house, ontology
    ):
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.CLASS,
                ref="ladder",
                fields={
                    "concept_scheme_id": house["scheme"],
                    "title": "Ladder",
                    "parent_class_id": house["tool"],
                },
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.ATTRIBUTE,
                fields={
                    "class_id": "$ladder",
                    "identifier": "rungs",
                    "title": "Rungs",
                    "datatype": "integer",
                },
            ),
            create(3, ["$ladder"], "Step ladder", {"rungs": 3, "brand": "Werner"}),
            create(4, ["$ladder"], "Bad ladder", {"rungs": "three"}),
        ]
        proposal = apply_all(service, propose(service, house, *drafts))

        statuses = [o.status for o in proposal.operations]
        assert statuses[:3] == [OperationStatus.APPLIED] * 3
        assert values(ontology, proposal.operations[2].result_entity_id) == {
            "rungs": (3, "xsd:integer"),
            "brand": ("Werner", "xsd:string"),
        }
        bad = proposal.operations[3]
        assert bad.status is OperationStatus.FAILED
        assert bad.reason == "error: data_properties 'rungs' is integer, so 'three' doesn't fit"

    def test_an_inherited_datatype_is_checked_at_propose_even_with_a_new_class(
        self, service, house
    ):
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.CLASS,
                ref="ladder",
                fields={"concept_scheme_id": house["scheme"], "title": "Ladder"},
            ),
            create(2, [house["tool"], "$ladder"], "Step ladder", {"powered": "no"}),
        ]
        with pytest.raises(ProposalValidationError) as excinfo:
            propose(service, house, *drafts)
        assert problems(excinfo) == [
            (2, "invalid", "data_properties 'powered' is boolean, so 'no' doesn't fit")
        ]


class TestUpdate:
    def test_adding_a_value_is_additive_and_keeps_the_others(self, service, house, ontology):
        proposal = propose(service, house, update(1, house["drill"], {"powered": True}))
        op = proposal.operations[0]
        assert op.scope is S.ADDITIVE
        assert op.base == {"data_properties": {"powered": None}}

        applied = apply_all(service, proposal).operations[0]

        assert applied.status is OperationStatus.APPLIED, applied.reason
        assert values(ontology, house["drill"]) == {
            "brand": ("Bosch", "xsd:string"),
            "count": (1, "xsd:integer"),
            "powered": (True, "xsd:boolean"),
        }

    def test_changing_or_removing_a_value_is_editorial(self, service, house, ontology):
        proposal = propose(service, house, update(1, house["drill"], {"brand": None}))
        assert proposal.operations[0].scope is S.EDITORIAL
        proposal = propose(service, house, update(1, house["drill"], {"brand": "DeWalt"}))
        op = proposal.operations[0]
        assert op.scope is S.EDITORIAL
        assert op.base == {"data_properties": {"brand": "Bosch"}}

        apply_all(service, proposal)
        assert values(ontology, house["drill"])["brand"] == ("DeWalt", "xsd:string")

    def test_changing_or_removing_a_required_value_is_breaking(self, service, house, ontology):
        for data in ({"count": 3}, {"count": None}):
            proposal = propose(service, house, update(1, house["drill"], data))
            assert proposal.operations[0].scope is S.BREAKING
        apply_all(service, proposal)
        assert "count" not in values(ontology, house["drill"])

    def test_setting_a_value_it_already_has_changes_nothing(self, service, house):
        proposal = propose(service, house, update(1, house["drill"], {"brand": "Bosch"}))
        assert proposal.operations[0].scope is S.EDITORIAL

    def test_values_are_checked_against_the_classes_it_will_have(self, service, house, ontology):
        retype = update(1, house["drill"], {"floor": 2}, class_ids=[house["tool"], house["place"]])
        applied = apply_all(service, propose(service, house, retype)).operations[0]
        assert applied.status is OperationStatus.APPLIED, applied.reason
        assert values(ontology, house["drill"])["floor"] == (2, "xsd:integer")

        with pytest.raises(ProposalValidationError) as excinfo:
            propose(
                service, house, update(1, house["drill"], {"floor": 2}, class_ids=[house["tool"]])
            )
        assert "'floor' is not an attribute" in problems(excinfo)[0][2]

    def test_invalid_values_fail_the_operation(self, service, house):
        with pytest.raises(ProposalValidationError) as excinfo:
            propose(
                service,
                house,
                update(1, house["drill"], {"size": "XS"}),
                update(2, house["drill"], {"nope": 1}),
            )
        assert [(seq, code) for seq, code, _ in problems(excinfo)] == [
            (1, "invalid"),
            (2, "invalid"),
        ]

    def test_a_stray_value_can_be_removed(self, service, house, ontology):
        ontology.update_individual(
            house["drill"],
            data_properties=[
                *ontology.get_individual(house["drill"]).data_properties,
                DataPropertyValue("colour", "red", "xsd:string"),
            ],
        )
        proposal = propose(service, house, update(1, house["drill"], {"colour": None}))
        apply_all(service, proposal)
        assert "colour" not in values(ontology, house["drill"])

    def test_staleness_follows_only_the_values_it_touches(self, service, house, ontology):
        proposal = propose(service, house, update(1, house["drill"], {"powered": True}))
        current = ontology.get_individual(house["drill"]).data_properties
        ontology.update_individual(
            house["drill"],
            data_properties=[current[0], DataPropertyValue("count", 5, "xsd:integer")],
        )
        assert service.stale_operation_ids(proposal) == set()

        ontology.update_individual(
            house["drill"],
            data_properties=[*current, DataPropertyValue("powered", False, "xsd:boolean")],
        )
        assert service.stale_operation_ids(proposal) == {proposal.operations[0].id}
        applied = apply_all(service, proposal).operations[0]
        assert applied.reason == "target_changed: data_properties changed since proposed"

    def test_a_datatype_changed_since_proposed_fails_the_apply(self, service, house, ontology):
        proposal = propose(service, house, update(1, house["drill"], {"powered": True}))
        powered = next(
            a
            for a in ontology.list_attribute_definitions(class_id=house["tool"])
            if a.identifier == "powered"
        )
        ontology.update_attribute_definition(powered.id, datatype="string")

        applied = apply_all(service, proposal).operations[0]

        assert applied.status is OperationStatus.FAILED
        assert applied.reason == "error: data_properties 'powered' is string, so True doesn't fit"
        assert "powered" not in values(ontology, house["drill"])


class TestReviewRound:
    def test_allowed_values_apply_to_numbers_and_booleans_by_their_json_text(
        self, service, house, ontology
    ):
        ontology.create_attribute_definition(
            house["tool"], "voltage", "Voltage", "integer", allowed_values=["12", "18"]
        )
        ontology.create_attribute_definition(
            house["tool"], "cordless", "Cordless", "boolean", allowed_values=["true"]
        )
        proposal = propose(
            service, house, update(1, house["drill"], {"voltage": 18, "cordless": True})
        )
        assert apply_all(service, proposal).operations[0].status is OperationStatus.APPLIED

        for data, expected in (
            ({"voltage": 24}, "data_properties 'voltage' allows only ['12', '18'], not [24]"),
            ({"cordless": False}, "data_properties 'cordless' allows only ['true'], not [False]"),
        ):
            with pytest.raises(ProposalValidationError) as excinfo:
                propose(service, house, update(1, house["drill"], data))
            assert problems(excinfo) == [(1, "invalid", expected)]

    def test_the_created_event_carries_the_values(self, service, house, ontology):
        proposal = propose(service, house, create(1, [house["tool"]], "Saw", {"brand": "Makita"}))
        apply_all(service, proposal)

        created = ontology._event_publisher.get_events_of_type(IndividualCreated)[-1]
        assert created.data_properties == [
            {"property_identifier": "brand", "value": "Makita", "datatype": "xsd:string"}
        ]
