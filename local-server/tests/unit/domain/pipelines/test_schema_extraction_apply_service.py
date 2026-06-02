"""
Unit tests for SchemaExtractionApplyService.

Uses FakeOntologyRepository for in-memory testing — no database, no I/O.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from unittest.mock import MagicMock

import pytest

from domain.ontology.entities import Class, ConceptScheme, PropertyDefinition, Taxonomy
from domain.ontology.value_objects import Status
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.schema_extraction.apply_service import SchemaExtractionApplyService
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TAXONOMY_ID = "tx-1"
SCHEME_ID = "cs-1"


@pytest.fixture()
def repo():
    r = FakeOntologyRepository()
    r.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="test_tax", title="Test Taxonomy"))
    r.save_concept_scheme(
        ConceptScheme(
            id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="test_scheme",
            title="Test Scheme",
        )
    )
    return r


@pytest.fixture()
def svc(repo):
    return SchemaExtractionApplyService(repo)


def _make_run(candidates=None, connections=None, run_id="run-abc"):
    """Build a minimal completed PipelineRun mock with given output_summary."""
    run = MagicMock()
    run.id = run_id
    run.pipeline_type = PipelineType.SCHEMA_EXTRACTION
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {
        "candidates": candidates or [],
        "connections": connections or [],
    }
    return run


# ---------------------------------------------------------------------------
# Class creation
# ---------------------------------------------------------------------------


class TestClassCreation:
    def test_creates_classes_with_draft_status(self, svc, repo):
        run = _make_run(
            candidates=[
                {
                    "kind": "class",
                    "label": "Microservice",
                    "proposed_definition": "A small service",
                    "confidence": 0.9,
                },
                {
                    "kind": "class",
                    "label": "Gateway",
                    "proposed_definition": "An API gateway",
                    "confidence": 0.8,
                },
            ]
        )
        result = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result.classes_created == 2
        assert result.classes_skipped == 0
        classes = repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)
        assert len(classes) == 2
        for cls in classes:
            assert cls.status == Status.DRAFT
            assert cls.source_run_id == "run-abc"
            assert cls.concept_scheme_id == SCHEME_ID
            assert cls.taxonomy_id == TAXONOMY_ID

    def test_sets_description_from_proposed_definition(self, svc, repo):
        run = _make_run(
            candidates=[
                {
                    "kind": "class",
                    "label": "Cache",
                    "proposed_definition": "Stores data temporarily",
                    "confidence": 0.8,
                },
            ]
        )
        svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)
        classes = repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)
        assert classes[0].description == "Stores data temporarily"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_apply_creates_no_duplicates(self, svc, repo):
        run = _make_run(
            candidates=[
                {"kind": "class", "label": "Service", "confidence": 0.9},
            ]
        )
        svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)
        result2 = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result2.classes_created == 0
        assert result2.classes_skipped == 1
        classes = repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)
        assert len(classes) == 1

    def test_case_insensitive_dedup(self, svc, repo):
        run1 = _make_run(candidates=[{"kind": "class", "label": "Service", "confidence": 0.9}])
        run2 = _make_run(candidates=[{"kind": "class", "label": "service", "confidence": 0.9}])
        svc.apply(run1, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)
        result2 = svc.apply(run2, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result2.classes_created == 0
        assert len(repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)) == 1


# ---------------------------------------------------------------------------
# Confidence threshold
# ---------------------------------------------------------------------------


class TestConfidenceThreshold:
    def test_skips_candidates_below_threshold(self, svc, repo):
        run = _make_run(
            candidates=[
                {"kind": "class", "label": "HighConf", "confidence": 0.9},
                {"kind": "class", "label": "LowConf", "confidence": 0.3},
            ]
        )
        result = svc.apply(
            run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, confidence_threshold=0.5
        )

        assert result.classes_created == 1
        assert result.classes_skipped == 1
        assert repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)[0].title == "HighConf"

    def test_zero_threshold_includes_all(self, svc, repo):
        run = _make_run(
            candidates=[
                {"kind": "class", "label": "A", "confidence": 0.0},
                {"kind": "class", "label": "B", "confidence": 0.01},
            ]
        )
        result = svc.apply(
            run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, confidence_threshold=0.0
        )
        assert result.classes_created == 2


# ---------------------------------------------------------------------------
# Property Definitions
# ---------------------------------------------------------------------------


class TestPropertyDefinitions:
    def test_creates_property_definitions_with_slugified_identifier(self, svc, repo):
        run = _make_run(
            candidates=[
                {
                    "kind": "property_definition",
                    "label": "Is Part Of",
                    "proposed_definition": "Membership",
                    "confidence": 0.8,
                },
            ]
        )
        result = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result.properties_created == 1
        prop = repo.get_property_definition_by_identifier("is_part_of")
        assert prop is not None
        assert prop.status == Status.DRAFT
        assert prop.source_run_id == "run-abc"
        assert prop.title == "Is Part Of"

    def test_skips_existing_property_definitions(self, svc, repo):
        run = _make_run(
            candidates=[
                {"kind": "property_definition", "label": "Has Component", "confidence": 0.9},
            ]
        )
        svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)
        result2 = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result2.properties_created == 0
        assert result2.properties_skipped == 1


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


class TestRelationships:
    def test_creates_relationship_when_subject_object_and_property_resolve(self, svc, repo):
        # Pre-create classes and property so relationship can be resolved
        cls_a = Class(
            id="cls-a", concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Alpha"
        )
        cls_b = Class(
            id="cls-b", concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Beta"
        )
        repo.save_class(cls_a)
        repo.save_class(cls_b)
        prop = PropertyDefinition(id="prop-1", identifier="sub_class_of", title="Sub Class Of")
        repo.save_property_definition(prop)

        run = _make_run(
            connections=[
                {
                    "subject_ref": "Alpha",
                    "predicate": "Sub Class Of",
                    "object_ref": "Beta",
                    "confidence": 0.9,
                },
            ]
        )
        result = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result.relationships_created == 1
        rels = repo.list_relationships(source_id="cls-a", target_id="cls-b", property_id="prop-1")
        assert len(rels) == 1
        assert rels[0].source_run_id == "run-abc"

    def test_skips_relationship_when_predicate_unresolvable(self, svc, repo):
        cls_a = Class(
            id="cls-a", concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Alpha"
        )
        cls_b = Class(
            id="cls-b", concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Beta"
        )
        repo.save_class(cls_a)
        repo.save_class(cls_b)

        run = _make_run(
            connections=[
                {
                    "subject_ref": "Alpha",
                    "predicate": "Unknown Predicate",
                    "object_ref": "Beta",
                    "confidence": 0.9,
                },
            ]
        )
        result = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result.relationships_created == 0
        assert result.relationships_skipped == 1

    def test_relationship_dedup_on_second_apply(self, svc, repo):
        cls_a = Class(
            id="cls-a", concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Alpha"
        )
        cls_b = Class(
            id="cls-b", concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Beta"
        )
        repo.save_class(cls_a)
        repo.save_class(cls_b)
        prop = PropertyDefinition(id="prop-1", identifier="related_to", title="Related To")
        repo.save_property_definition(prop)

        run = _make_run(
            connections=[
                {
                    "subject_ref": "Alpha",
                    "predicate": "Related To",
                    "object_ref": "Beta",
                    "confidence": 0.9,
                },
            ]
        )
        svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)
        result2 = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result2.relationships_created == 0
        assert result2.relationships_skipped == 1

    def test_classes_created_in_same_apply_are_available_for_relationships(self, svc, repo):
        """Classes created during apply can be linked by connections in the same apply."""
        prop = PropertyDefinition(id="prop-1", identifier="uses", title="Uses")
        repo.save_property_definition(prop)

        run = _make_run(
            candidates=[
                {"kind": "class", "label": "Client", "confidence": 0.9},
                {"kind": "class", "label": "Server", "confidence": 0.9},
            ],
            connections=[
                {
                    "subject_ref": "Client",
                    "predicate": "Uses",
                    "object_ref": "Server",
                    "confidence": 0.9,
                },
            ],
        )
        result = svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID)

        assert result.classes_created == 2
        assert result.relationships_created == 1


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_raises_when_concept_scheme_id_empty(self, svc):
        run = _make_run()
        with pytest.raises(ValueError, match="concept_scheme_id"):
            svc.apply(run, concept_scheme_id="", taxonomy_id=TAXONOMY_ID)

    def test_raises_when_taxonomy_id_empty(self, svc):
        run = _make_run()
        with pytest.raises(ValueError, match="taxonomy_id"):
            svc.apply(run, concept_scheme_id=SCHEME_ID, taxonomy_id="")

    def test_returns_accurate_counts(self, svc, repo):
        run = _make_run(
            candidates=[
                {"kind": "class", "label": "A", "confidence": 0.9},
                {"kind": "class", "label": "B", "confidence": 0.2},  # below threshold
                {"kind": "property_definition", "label": "Has Role", "confidence": 0.8},
            ]
        )
        result = svc.apply(
            run, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, confidence_threshold=0.5
        )
        assert result.classes_created == 1
        assert result.classes_skipped == 1
        assert result.properties_created == 1
        assert result.properties_skipped == 0
        assert result.relationships_created == 0
