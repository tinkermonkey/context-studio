"""
Unit tests for SchemaRecognitionPreviewService.

Uses FakeOntologyRepository and FakeSchemaVectorIndex — no database, no I/O.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.ontology.entities import (
    Class,
    ConceptScheme,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.ports import SchemaMatch
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.schema_extraction.recognition_preview import (
    SchemaRecognitionHit,
    SchemaRecognitionPreviewService,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_schema_vector_index import FakeSchemaVectorIndex

TAXONOMY_ID = "tx-1"
SCHEME_ID = "cs-1"
OTHER_SCHEME_ID = "cs-2"


def _class(cid, title, scheme=SCHEME_ID):
    return Class(
        id=cid,
        concept_scheme_id=scheme,
        taxonomy_id=TAXONOMY_ID,
        identifier=cid.replace("-", "_"),
        title=title,
    )


@pytest.fixture()
def repo():
    r = FakeOntologyRepository()
    r.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="tax", title="Tax"))
    for sid in (SCHEME_ID, OTHER_SCHEME_ID):
        r.save_concept_scheme(
            ConceptScheme(
                id=sid, taxonomy_id=TAXONOMY_ID, identifier=sid.replace("-", "_"), title=sid
            )
        )
    r.save_class(_class("cls-service", "Service"))
    r.save_class(_class("cls-database", "Database"))
    r.save_class(_class("cls-other", "Queue", scheme=OTHER_SCHEME_ID))
    r.save_property_definition(PropertyDefinition(id="prop-uses", identifier="uses", title="uses"))
    r.save_relationship(
        Relationship(
            id="rel-1",
            source_id="cls-service",
            target_id="cls-database",
            property_definition_id="prop-uses",
        )
    )
    return r


def _summary(candidates=(), connections=()):
    return {"candidates": list(candidates), "connections": list(connections)}


def _cls(label):
    return {"kind": "class", "label": label, "confidence": 0.8}


def _match(entity_id, label, score, field="title"):
    return SchemaMatch(
        entity_id=entity_id, kind="class", label=label, score=score, matched_field=field
    )


def _index(*matches):
    index = FakeSchemaVectorIndex()
    index.set_search_results(list(matches), {m.entity_id: TAXONOMY_ID for m in matches})
    return index


def _svc(repo, index=None):
    return SchemaRecognitionPreviewService(
        repo, schema_index=index, embedding_service=FakeEmbeddingService() if index else None
    )


def test_exact_class_title_matches_case_insensitively(repo):
    hits = _svc(repo).preview(_summary([_cls("service"), _cls("Cache")]), TAXONOMY_ID)

    assert hits[0] == SchemaRecognitionHit(
        candidate_id="class-0",
        candidate_type="schema_class",
        label="service",
        will_match_existing=True,
        existing_entity_id="cls-service",
        existing_entity_title="Service",
        match_method="exact",
        match_score=1.0,
    )
    assert hits[1].candidate_id == "class-1"
    assert hits[1].will_match_existing is False
    assert hits[1].existing_entity_id is None


def test_exact_match_ignores_spacing_like_apply(repo):
    repo.save_class(_class("cls-data-object", "DataObject"))
    hits = _svc(repo).preview(_summary([_cls("Data Object")]), TAXONOMY_ID)
    assert hits[0].will_match_existing is True
    assert hits[0].existing_entity_title == "DataObject"


def test_exact_match_spans_every_scheme_in_the_taxonomy(repo):
    hits = _svc(repo).preview(_summary([_cls("Queue")]), TAXONOMY_ID)
    assert hits[0].will_match_existing is True
    assert hits[0].existing_entity_id == "cls-other"


def test_exact_match_ignores_other_taxonomies(repo):
    repo.save_taxonomy(Taxonomy(id="tx-2", identifier="other", title="Other"))
    repo.save_concept_scheme(
        ConceptScheme(id="cs-x", taxonomy_id="tx-2", identifier="cs_x", title="X")
    )
    cache = _class("cls-cache", "Cache", scheme="cs-x")
    cache.taxonomy_id = "tx-2"
    repo.save_class(cache)
    hits = _svc(repo).preview(_summary([_cls("Cache")]), TAXONOMY_ID)
    assert hits[0].existing_entity_id is None


def test_same_title_in_two_schemes_matches_the_oldest_scheme(repo):
    repo.save_class(_class("cls-service-2", "Service", scheme=OTHER_SCHEME_ID))
    hits = _svc(repo).preview(_summary([_cls("Service")]), TAXONOMY_ID)
    assert hits[0].existing_entity_id == "cls-service"


def test_vector_hint_for_a_clear_title_match_is_advisory(repo):
    index = _index(_match("cls-database", "Database", 0.94))

    hits = _svc(repo, index).preview(_summary([_cls("Data store")]), TAXONOMY_ID)

    assert hits[0].match_method == "vector"
    assert hits[0].existing_entity_id == "cls-database"
    assert hits[0].existing_entity_title == "Database"
    assert hits[0].match_score == pytest.approx(0.94)
    # Apply still creates a new class for a merely similar label.
    assert hits[0].will_match_existing is False


def test_vector_hint_withheld_below_threshold(repo):
    index = _index(_match("cls-database", "Database", 0.85))
    hits = _svc(repo, index).preview(_summary([_cls("Data store")]), TAXONOMY_ID)
    assert hits[0].match_method is None


def test_vector_hint_withheld_when_ambiguous(repo):
    index = _index(
        _match("cls-database", "Database", 0.94),
        _match("cls-service", "Service", 0.92),
    )
    hits = _svc(repo, index).preview(_summary([_cls("Data service")]), TAXONOMY_ID)
    assert hits[0].match_method is None


def test_vector_hint_ignores_definition_matches(repo):
    index = _index(_match("cls-database", "Database", 0.97, field="definition"))
    hits = _svc(repo, index).preview(_summary([_cls("Data store")]), TAXONOMY_ID)
    assert hits[0].match_method is None


def test_vector_hint_covers_other_schemes_in_the_taxonomy(repo):
    index = _index(_match("cls-other", "Queue", 0.96))
    hits = _svc(repo, index).preview(_summary([_cls("Message queue")]), TAXONOMY_ID)
    assert hits[0].match_method == "vector"
    assert hits[0].existing_entity_id == "cls-other"


def test_exact_match_wins_over_vector(repo):
    index = _index(_match("cls-database", "Database", 0.99))
    hits = _svc(repo, index).preview(_summary([_cls("Service")]), TAXONOMY_ID)
    assert hits[0].match_method == "exact"
    assert hits[0].existing_entity_id == "cls-service"


def test_property_matches_by_identifier(repo):
    props = [
        {"kind": "property_definition", "label": "Uses", "confidence": 0.7},
        {"kind": "property_definition", "label": "depends on", "confidence": 0.7},
    ]
    hits = _svc(repo).preview(_summary(props), TAXONOMY_ID)

    assert [h.candidate_id for h in hits] == ["property-0", "property-1"]
    assert hits[0].candidate_type == "schema_property"
    assert hits[0].will_match_existing is True
    assert hits[0].existing_entity_id == "prop-uses"
    assert hits[1].will_match_existing is False


def test_connection_matches_an_existing_relationship(repo):
    connections = [
        {"subject_ref": "service", "predicate": "uses", "object_ref": "database"},
        {"subject_ref": "Database", "predicate": "uses", "object_ref": "Service"},
        {"subject_ref": "Service", "predicate": "uses", "object_ref": "Cache"},
    ]
    hits = _svc(repo).preview(_summary(connections=connections), TAXONOMY_ID)

    assert [h.candidate_id for h in hits] == ["connection-0", "connection-1", "connection-2"]
    assert hits[0].label == "service → uses → database"
    assert hits[0].will_match_existing is True
    assert hits[0].existing_entity_id == "rel-1"
    assert hits[0].existing_entity_title == "Service → uses → Database"
    assert hits[1].will_match_existing is False
    assert hits[2].will_match_existing is False


def test_hits_keep_candidate_ids_across_kinds(repo):
    summary = _summary(
        [_cls("A"), {"kind": "property_definition", "label": "p"}, _cls("B")],
        [{"subject_ref": "A", "predicate": "p", "object_ref": "B"}],
    )
    hits = _svc(repo).preview(summary, TAXONOMY_ID)
    assert [h.candidate_id for h in hits] == ["class-0", "property-0", "class-1", "connection-0"]


def test_requires_an_existing_taxonomy(repo):
    with pytest.raises(PipelineInputError):
        _svc(repo).preview(_summary(), "")
    with pytest.raises(PipelineInputError):
        _svc(repo).preview(_summary(), "missing")


def test_preview_writes_nothing(repo):
    before = (len(repo.list_classes(limit=None)), len(repo.list_relationships(limit=None)))
    _svc(repo).preview(
        _summary(
            [_cls("New")], [{"subject_ref": "New", "predicate": "x", "object_ref": "Service"}]
        ),
        TAXONOMY_ID,
    )
    assert (len(repo.list_classes(limit=None)), len(repo.list_relationships(limit=None))) == before


def test_hit_invariants():
    with pytest.raises(ValueError):
        SchemaRecognitionHit("class-0", "schema_class", "x", will_match_existing=True)
    with pytest.raises(ValueError):
        SchemaRecognitionHit("class-0", "schema_class", "x", match_method="vector")
    with pytest.raises(ValueError):
        SchemaRecognitionHit(
            "class-0",
            "schema_class",
            "x",
            existing_entity_id="c",
            match_method="vector",
            will_match_existing=True,
        )
