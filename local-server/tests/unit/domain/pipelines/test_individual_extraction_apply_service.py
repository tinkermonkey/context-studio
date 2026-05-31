"""
Unit tests for IndividualExtractionApplyService.

Uses FakeOntologyRepository for in-memory testing — no database, no I/O.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from unittest.mock import MagicMock

import pytest

from domain.ontology.entities import Class, ConceptScheme, PropertyDefinition, Taxonomy
from domain.ontology.value_objects import Status
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.apply_service import IndividualExtractionApplyService
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TAXONOMY_ID = "tx-1"
SCHEME_ID = "cs-1"
CLASS_ID = "cls-person"


@pytest.fixture()
def repo():
    r = FakeOntologyRepository()
    r.save_taxonomy(Taxonomy(id=TAXONOMY_ID, title="Test Taxonomy"))
    r.save_concept_scheme(ConceptScheme(id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Test Scheme"))
    r.save_class(Class(id=CLASS_ID, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Person"))
    return r


@pytest.fixture()
def svc(repo):
    return IndividualExtractionApplyService(repo)


def _make_run(triples=None, run_id="run-ind-1"):
    """Build a minimal completed individual extraction PipelineRun mock."""
    run = MagicMock()
    run.id = run_id
    run.pipeline_type = PipelineType.INDIVIDUAL_EXTRACTION
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {"triples": triples or []}
    return run


def _make_triple(subject_label, class_ids=None, confidence=0.9, predicate_prop_id=None, obj_id=None, obj_kind="class"):
    """Helper to build a triple dict matching the individual extraction output format."""
    triple = {
        "subject": {
            "kind": "individual",
            "id": "",
            "label": subject_label,
            "class_ids": class_ids or [CLASS_ID],
        },
        "confidence": confidence,
    }
    if predicate_prop_id:
        triple["predicate"] = {"property_definition_id": predicate_prop_id, "label": "test-pred"}
        triple["object"] = {"kind": obj_kind, "id": obj_id or "tgt-id", "label": "Target"}
    return triple


# ---------------------------------------------------------------------------
# Individual creation
# ---------------------------------------------------------------------------

class TestIndividualCreation:
    def test_creates_individual_with_draft_status_and_source_run_id(self, svc, repo):
        run = _make_run(triples=[_make_triple("Alice")])
        result = svc.apply(run)

        assert result.individuals_created == 1
        individuals = repo.list_individuals(class_id=CLASS_ID, limit=None)
        assert len(individuals) == 1
        alice = individuals[0]
        assert alice.title == "Alice"
        assert alice.status == Status.DRAFT
        assert alice.source_run_id == "run-ind-1"
        assert CLASS_ID in alice.class_ids

    def test_skips_triples_where_subject_is_not_individual(self, svc, repo):
        """Triples with subject.kind != 'individual' should be ignored."""
        run = _make_run(triples=[{
            "subject": {"kind": "class", "id": "cls-x", "label": "SomeClass", "class_ids": [CLASS_ID]},
            "confidence": 0.9,
        }])
        result = svc.apply(run)
        assert result.individuals_created == 0

    def test_skips_individual_when_class_not_found(self, svc, repo):
        """Individuals with non-existent class_ids should be skipped."""
        run = _make_run(triples=[_make_triple("Bob", class_ids=["nonexistent-class-id"])])
        result = svc.apply(run)
        assert result.individuals_created == 0
        assert result.individuals_skipped == 1


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_second_apply_skips_existing_individuals(self, svc, repo):
        run = _make_run(triples=[_make_triple("Alice")])
        svc.apply(run)
        result2 = svc.apply(run)

        # Second apply finds Alice by label+class lookup and skips
        assert result2.individuals_created == 0
        individuals = repo.list_individuals(class_id=CLASS_ID, limit=None)
        assert len(individuals) == 1

    def test_lookup_by_explicit_id_skips_existing(self, svc, repo):
        """If the subject already has an ID that resolves, we skip."""
        run1 = _make_run(triples=[_make_triple("Alice")])
        svc.apply(run1)
        existing = repo.list_individuals(class_id=CLASS_ID, limit=None)[0]

        # Second run includes the existing individual's ID
        triple_with_id = _make_triple("Alice")
        triple_with_id["subject"]["id"] = existing.id
        run2 = _make_run(triples=[triple_with_id])
        result2 = svc.apply(run2)

        assert result2.individuals_created == 0
        assert len(repo.list_individuals(class_id=CLASS_ID, limit=None)) == 1


# ---------------------------------------------------------------------------
# Confidence threshold
# ---------------------------------------------------------------------------

class TestConfidenceThreshold:
    def test_skips_triples_below_threshold(self, svc, repo):
        run = _make_run(triples=[
            _make_triple("Alice", confidence=0.9),
            _make_triple("Bob", confidence=0.2),
        ])
        result = svc.apply(run, confidence_threshold=0.5)

        assert result.individuals_created == 1
        assert result.individuals_skipped == 1
        individuals = repo.list_individuals(class_id=CLASS_ID, limit=None)
        assert individuals[0].title == "Alice"


# ---------------------------------------------------------------------------
# Relationship creation
# ---------------------------------------------------------------------------

class TestRelationshipCreation:
    def test_creates_relationship_from_triple_predicate(self, svc, repo):
        prop = PropertyDefinition(id="prop-knows", identifier="knows", title="Knows")
        repo.save_property_definition(prop)
        target_cls = Class(id="cls-org", concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Org")
        repo.save_class(target_cls)

        run = _make_run(triples=[
            _make_triple("Alice", predicate_prop_id="prop-knows", obj_id="cls-org", obj_kind="class"),
        ])
        result = svc.apply(run)

        assert result.individuals_created == 1
        assert result.relationships_created == 1
        alice = repo.list_individuals(class_id=CLASS_ID, limit=None)[0]
        rels = repo.list_relationships(source_id=alice.id, property_id="prop-knows")
        assert len(rels) == 1
        assert rels[0].source_run_id == "run-ind-1"
