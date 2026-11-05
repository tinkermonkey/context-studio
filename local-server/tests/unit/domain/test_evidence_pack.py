"""
Unit tests for EvidencePackBuilder (domain/ontology/evidence.py).

Each section of an evidence pack (intent, attribute peers, pair edges,
predicate context) is checked against the fake ontology repository, on a small
House-style taxonomy, with and without a predicate catalog.
"""

import os
import sys

import pytest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from domain.ontology.entities import (  # noqa: E402
    AttributeDefinition,
    Class,
    ConceptScheme,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.evidence import (  # noqa: E402
    NO_EVIDENCE,
    ContextPolicy,
    EvidencePackBuilder,
)
from domain.ontology.exceptions import EntityNotFoundError  # noqa: E402
from tests.fakes.fake_ontology_repository import FakeOntologyRepository  # noqa: E402

LONG_DEFINITION = (
    "Floor area of the room in square feet, measured wall to wall, "
    "excluding closets and any built-in fixtures."
)


def _prop(repo, prop_id, domain, predicate, range_, description=None):
    repo.save_property_definition(
        PropertyDefinition(
            id=prop_id,
            identifier=f"{domain}_{predicate}_{range_}",
            title=f"{domain} {predicate} {range_}",
            description=description,
            canonical_predicate=predicate,
            domain_class_id=domain,
            range_class_id=range_,
        )
    )


def _attr(repo, attr_id, class_id, identifier, datatype, **kwargs):
    repo.save_attribute_definition(
        AttributeDefinition(
            id=attr_id,
            class_id=class_id,
            identifier=identifier,
            title=identifier.title(),
            datatype=datatype,
            **kwargs,
        )
    )


@pytest.fixture
def repo():
    repo = FakeOntologyRepository()
    repo.save_taxonomy(
        Taxonomy(
            id="house",
            title="House",
            identifier="house",
            description="Rooms and fixtures of a house.",
            vision="# House charter\n\nModel what a home inspector would record.",
        )
    )
    repo.save_concept_scheme(
        ConceptScheme(
            id="rooms",
            taxonomy_id="house",
            title="Rooms",
            identifier="rooms",
            description="Spaces people occupy.",
        )
    )
    repo.save_concept_scheme(
        ConceptScheme(id="fixtures", taxonomy_id="house", title="Fixtures", identifier="fixtures")
    )
    for class_id, scheme, definition in [
        ("kitchen", "rooms", "A room for preparing food."),
        ("bedroom", "rooms", "A room for sleeping."),
        ("bathroom", "rooms", None),
        ("sink", "fixtures", "A basin with a tap."),
    ]:
        repo.save_class(
            Class(
                id=class_id,
                concept_scheme_id=scheme,
                taxonomy_id="house",
                title=class_id.title(),
                identifier=class_id,
                description=definition,
            )
        )
    _prop(repo, "p1", "kitchen", "adjacent-to", "bedroom", "Shares a wall with")
    _prop(repo, "p2", "kitchen", "opens-to", "bedroom", "Has a door into")
    _prop(repo, "p3", "bedroom", "adjacent-to", "kitchen", "Shares a wall with")
    _prop(repo, "p4", "kitchen", "contains", "sink", "Holds")
    _prop(repo, "p5", "kitchen", "connects", "kitchen", "Links two of the same")
    _prop(repo, "p6", "bedroom", "connects", "bedroom", "Links two of the same")
    _prop(repo, "p7", "bathroom", "adjacent-to", "bedroom", "Shares a wall with")
    _attr(repo, "a1", "kitchen", "area", "integer", is_required=True, description=LONG_DEFINITION)
    _attr(repo, "a2", "bedroom", "area", "string", allowed_values=["small", "large"])
    _attr(repo, "a3", "bedroom", "windows", "integer")
    _attr(repo, "a4", "sink", "area", "integer")
    return repo


CATALOG = {
    "adjacent-to": {"description": "Shares a boundary"},
    "opens-to": {"description": "Has an opening into"},
    "connects": {"description": "Joins"},
}


class TestIntent:
    def test_summary_gives_taxonomy_summary_scope_note_and_definition_without_charter(self, repo):
        pack = EvidencePackBuilder(repo).build("kitchen", policy=ContextPolicy.SUMMARY)

        assert pack.intent.taxonomy_summary == "Rooms and fixtures of a house."
        assert pack.intent.scheme_scope_note == "Spaces people occupy."
        assert pack.intent.class_definition == "A room for preparing food."
        assert pack.intent.charter is None
        assert pack.text.startswith(
            "Design intent:\n"
            "  Taxonomy summary: Rooms and fixtures of a house.\n"
            "  Scheme rooms scope: Spaces people occupy.\n"
            "  Class kitchen definition: A room for preparing food."
        )
        assert "charter" not in pack.text

    def test_full_adds_the_charter(self, repo):
        pack = EvidencePackBuilder(repo).build("kitchen", policy=ContextPolicy.FULL)

        assert pack.intent.charter.startswith("# House charter")
        assert (
            "  Charter:\n# House charter\n\nModel what a home inspector would record." in pack.text
        )

    def test_none_gives_no_intent(self, repo):
        pack = EvidencePackBuilder(repo).build("kitchen", policy="none")

        assert pack.policy is ContextPolicy.NONE
        assert pack.intent is None
        assert "Design intent" not in pack.text

    def test_missing_intent_fields_are_left_out(self, repo):
        pack = EvidencePackBuilder(repo).build("sink", policy=ContextPolicy.SUMMARY)

        assert pack.intent.scheme_scope_note is None
        assert "Scheme fixtures scope" not in pack.text
        assert "  Class sink definition: A basin with a tap." in pack.text


class TestAttributePeers:
    def test_lists_every_class_in_the_scheme_that_declares_the_attribute(self, repo):
        pack = EvidencePackBuilder(repo).build_for_attribute("kitchen", "area", ContextPolicy.NONE)

        [evidence] = pack.attributes
        assert evidence.scheme_label == "rooms"
        # Bathroom has no `area`; the sink's is in another scheme.
        assert [p.class_id for p in evidence.peers] == ["bedroom", "kitchen"]
        bedroom, kitchen = evidence.peers
        assert (bedroom.datatype, bedroom.allowed_values, bedroom.is_required) == (
            "string",
            ("small", "large"),
            False,
        )
        assert (kitchen.datatype, kitchen.is_required) == ("integer", True)
        assert kitchen.definition == LONG_DEFINITION[:90]
        # The kitchen's self-loop follows as its pair section (subject alone).
        assert pack.text.split("\n\n")[0] == (
            "Attribute 'area' as declared across scheme rooms (2 classes):\n"
            "  bedroom.area: type=string enum[small|large] required=false (no description)\n"
            f'  kitchen.area: type=integer required=true desc="{LONG_DEFINITION[:90]}"'
        )

    def test_attribute_nobody_declares_lists_none(self, repo):
        pack = EvidencePackBuilder(repo).build_for_attribute(
            "kitchen", "ceiling", ContextPolicy.NONE
        )

        assert pack.attributes[0].peers == ()
        assert (
            "Attribute 'ceiling' as declared across scheme rooms (0 classes):\n  (none)"
            in pack.text
        )


class TestPairEdges:
    def test_lists_relationship_types_both_ways_with_meanings(self, repo):
        pack = EvidencePackBuilder(repo, CATALOG).build(
            "kitchen", named_class_ids=["bedroom"], policy=ContextPolicy.NONE
        )

        triples = [(e.domain_label, e.predicate, e.range_label) for e in pack.pair.edges]
        # The subject's self-loop is left out; the named class's is in (as DR does).
        assert triples == [
            ("bedroom", "adjacent-to", "kitchen"),
            ("bedroom", "connects", "bedroom"),
            ("kitchen", "adjacent-to", "bedroom"),
            ("kitchen", "opens-to", "bedroom"),
        ]
        assert pack.text == (
            "Relationship types between kitchen, bedroom (exact list, 4 types):\n"
            "  bedroom --[adjacent-to]--> kitchen  (adjacent-to: Shares a boundary)\n"
            "  bedroom --[connects]--> bedroom  (connects: Joins)\n"
            "  kitchen --[adjacent-to]--> bedroom  (adjacent-to: Shares a boundary)\n"
            "  kitchen --[opens-to]--> bedroom  (opens-to: Has an opening into)"
        )

    def test_three_classes_include_edges_between_named_classes(self, repo):
        pack = EvidencePackBuilder(repo).build(
            "kitchen", named_class_ids=["bedroom", "bathroom"], policy=ContextPolicy.NONE
        )

        assert ("bathroom", "adjacent-to", "bedroom") in {
            (e.domain_label, e.predicate, e.range_label) for e in pack.pair.edges
        }

    def test_subject_alone_lists_its_self_loops(self, repo):
        pack = EvidencePackBuilder(repo).build("kitchen", policy=ContextPolicy.NONE)

        assert [e.property_id for e in pack.pair.edges] == ["p5"]

    def test_no_edges_and_no_named_classes_means_no_pair_section(self, repo):
        pack = EvidencePackBuilder(repo).build("sink", policy=ContextPolicy.NONE)

        assert pack.pair is None
        assert pack.text == NO_EVIDENCE

    def test_without_a_catalog_the_relationship_type_description_is_the_meaning(self, repo):
        pack = EvidencePackBuilder(repo).build(
            "kitchen", named_class_ids=["sink"], policy=ContextPolicy.NONE
        )

        assert [(e.predicate, e.meaning) for e in pack.pair.edges] == [("contains", "Holds")]

    def test_predicate_missing_from_the_catalog_has_unknown_meaning(self, repo):
        pack = EvidencePackBuilder(repo, CATALOG).build(
            "kitchen", named_class_ids=["sink"], policy=ContextPolicy.NONE
        )

        assert pack.pair.edges[0].meaning is None
        assert "(contains: ?)" in pack.text

    def test_unknown_named_class_is_skipped(self, repo):
        pack = EvidencePackBuilder(repo).build(
            "kitchen", named_class_ids=["nope"], policy=ContextPolicy.NONE
        )

        assert pack.pair.class_ids == ("kitchen",)


class TestPredicateContext:
    def test_relationship_type_pack_names_meaning_same_pair_and_reverse_predicates(self, repo):
        pack = EvidencePackBuilder(repo, CATALOG).build_for_relationship_type(
            "p1", ContextPolicy.NONE
        )

        assert pack.subject_class_id == "kitchen"
        [context] = pack.predicates
        assert context.edge.predicate == "adjacent-to"
        assert context.edge.meaning == "Shares a boundary"
        assert context.same_pair_predicates == ("adjacent-to", "opens-to")
        assert context.reverse_predicates == ("adjacent-to",)
        assert pack.text.endswith(
            "Relationship type kitchen --[adjacent-to]--> bedroom: predicate adjacent-to "
            "(Shares a boundary); all predicates kitchen -> bedroom: [adjacent-to, opens-to]; "
            "reverse direction bedroom -> kitchen: [adjacent-to]"
        )
        assert pack.pair.class_ids == ("kitchen", "bedroom")

    def test_no_reverse_predicates_reads_none(self, repo):
        pack = EvidencePackBuilder(repo).build_for_relationship_type("p4", ContextPolicy.NONE)

        assert pack.predicates[0].reverse_predicates == ()
        assert "reverse direction sink -> kitchen: [none]" in pack.text

    def test_relationship_type_pack_carries_intent_by_default(self, repo):
        pack = EvidencePackBuilder(repo).build_for_relationship_type("p1")

        assert pack.policy is ContextPolicy.SUMMARY
        assert pack.intent.class_label == "kitchen"

    def test_unknown_relationship_type_raises(self, repo):
        with pytest.raises(EntityNotFoundError):
            EvidencePackBuilder(repo).build_for_relationship_type("nope")

    def test_unknown_relationship_type_in_a_general_build_is_skipped(self, repo):
        pack = EvidencePackBuilder(repo).build(
            "kitchen", relationship_type_ids=["nope"], policy=ContextPolicy.NONE
        )

        assert pack.predicates == ()


def test_unknown_subject_raises(repo):
    with pytest.raises(EntityNotFoundError):
        EvidencePackBuilder(repo).build("nope")
