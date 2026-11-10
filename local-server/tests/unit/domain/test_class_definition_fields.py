"""
Unit tests for a class's operational definition (#1513): distinguish_from,
evidence_signals and standard_reference are set on create and update, checked,
cleared, and recorded in change events (so history and revert carry them).
"""

import pytest

from domain.ontology.entities import Class
from domain.ontology.events import ClassUpdated
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import normalize_distinguish_from, normalize_evidence_signals
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


@pytest.fixture
def publisher():
    return FakeEventPublisher()


@pytest.fixture
def service(publisher):
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), publisher)


@pytest.fixture
def dr(service):
    taxonomy = service.create_taxonomy(title="DR", identifier="dr")
    scheme = service.create_scheme(taxonomy_id=taxonomy.id, title="API")
    other = service.create_taxonomy(title="House", identifier="house")
    other_scheme = service.create_scheme(taxonomy_id=other.id, title="Rooms")
    return {
        "scheme": scheme,
        "operation": service.create_class(scheme.id, "Operation", identifier="api_operation"),
        "endpoint": service.create_class(scheme.id, "Endpoint", identifier="api_endpoint"),
        "room": service.create_class(other_scheme.id, "Room", identifier="house_room"),
    }


class TestNormalize:
    def test_distinguish_from_is_trimmed_and_checked(self):
        assert normalize_distinguish_from(None) == []
        assert normalize_distinguish_from([{"class_id": " c1 ", "when": " a path "}]) == [
            {"class_id": "c1", "when": "a path"}
        ]

    @pytest.mark.parametrize(
        "items, message",
        [
            ("c1", "must be a list"),
            (["c1"], "{class_id, when}"),
            ([{"class_id": "c1", "when": "x", "p": 1}], "{class_id, when}"),
            ([{"when": "x"}], "needs a class_id"),
            ([{"class_id": "c1", "when": " "}], "needs a when"),
            ([{"class_id": "c1", "when": "x"}, {"class_id": "c1", "when": "y"}], "twice"),
        ],
    )
    def test_malformed_distinguish_from_is_refused(self, items, message):
        with pytest.raises(ValueError, match=message):
            normalize_distinguish_from(items)

    def test_evidence_signals_drop_blanks(self):
        assert normalize_evidence_signals([" a ", "", "b"]) == ["a", "b"]
        with pytest.raises(ValueError, match="list of text"):
            normalize_evidence_signals("a")

    def test_the_entity_normalizes_its_fields(self):
        cls = Class(
            id="c",
            concept_scheme_id="s",
            taxonomy_id="t",
            title="C",
            evidence_signals=[" e "],
            standard_reference="  ",
        )
        assert (cls.evidence_signals, cls.standard_reference, cls.distinguish_from) == (
            ["e"],
            None,
            [],
        )


class TestService:
    def test_create_sets_the_definition(self, service, dr):
        created = service.create_class(
            dr["scheme"].id,
            "Callback",
            distinguish_from=[{"class_id": dr["operation"].id, "when": "it is called by a client"}],
            evidence_signals=["a webhook URL", " "],
            standard_reference=" OpenAPI 3.0 Callback Object ",
        )

        stored = service.get_class(created.id)
        assert stored.distinguish_from == [
            {"class_id": dr["operation"].id, "when": "it is called by a client"}
        ]
        assert stored.evidence_signals == ["a webhook URL"]
        assert stored.standard_reference == "OpenAPI 3.0 Callback Object"

    @pytest.mark.parametrize("target", ["room", "missing"])
    def test_distinguish_from_must_name_a_class_of_the_taxonomy(self, service, dr, target):
        class_id = dr[target].id if target in dr else "nope"
        with pytest.raises(ValueError, match="not a class of this taxonomy"):
            service.create_class(
                dr["scheme"].id, "Callback", distinguish_from=[{"class_id": class_id, "when": "x"}]
            )

    def test_distinguish_from_cant_name_the_class_itself(self, service, dr):
        operation = dr["operation"]
        with pytest.raises(ValueError, match="the class itself"):
            service.update_class(
                operation.id, distinguish_from=[{"class_id": operation.id, "when": "x"}]
            )

    def test_update_records_old_and_new_values(self, service, dr, publisher):
        operation, endpoint = dr["operation"], dr["endpoint"]
        distinguish = [{"class_id": endpoint.id, "when": "it is a URL path, not an action"}]

        service.update_class(
            operation.id,
            distinguish_from=distinguish,
            evidence_signals=["an HTTP method on a path"],
            standard_reference="OpenAPI 3.0 Operation Object",
        )

        event = publisher.get_events_of_type(ClassUpdated)[-1]
        assert set(event.changed_fields) == {
            "distinguish_from",
            "evidence_signals",
            "standard_reference",
        }
        assert event.old_values == {
            "distinguish_from": [],
            "evidence_signals": [],
            "standard_reference": None,
        }
        assert event.new_values["distinguish_from"] == distinguish
        assert service.get_class(operation.id).standard_reference == "OpenAPI 3.0 Operation Object"

    def test_empty_values_clear_and_none_leaves_alone(self, service, dr, publisher):
        operation, endpoint = dr["operation"], dr["endpoint"]
        service.update_class(
            operation.id,
            distinguish_from=[{"class_id": endpoint.id, "when": "x"}],
            evidence_signals=["e"],
            standard_reference="S",
        )

        service.update_class(operation.id, title="Operation")  # no change at all
        assert service.get_class(operation.id).evidence_signals == ["e"]

        service.update_class(
            operation.id, distinguish_from=[], evidence_signals=[], standard_reference=""
        )
        cleared = service.get_class(operation.id)
        assert (cleared.distinguish_from, cleared.evidence_signals) == ([], [])
        assert cleared.standard_reference is None

    def test_an_unchanged_definition_records_nothing(self, service, dr, publisher):
        operation = dr["operation"]
        before = len(publisher.get_events())
        service.update_class(operation.id, evidence_signals=[], standard_reference="")
        assert len(publisher.get_events()) == before
