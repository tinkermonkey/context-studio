"""
Unit tests for IndividualExtractionApplyService.

Uses FakeOntologyRepository for in-memory testing — no database, no I/O.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from unittest.mock import MagicMock

import pytest

from domain.extraction.ports import RecognitionMatch
from domain.ontology.entities import Class, ConceptScheme, Individual, PropertyDefinition, Taxonomy
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import Status
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_individual_recognizer import FakeIndividualRecognizer
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
    r.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="test_tax", title="Test Taxonomy"))
    r.save_concept_scheme(
        ConceptScheme(
            id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="test_scheme",
            title="Test Scheme",
        )
    )
    r.save_class(
        Class(
            id=CLASS_ID,
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="cls_test",
            title="Person",
        )
    )
    return r


@pytest.fixture()
def ontology_service(repo):
    return OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=FakeEventPublisher(),
    )


@pytest.fixture()
def svc(ontology_service, repo):
    return IndividualExtractionApplyService(ontology_service, repo)


@pytest.fixture()
def recognizer():
    return FakeIndividualRecognizer()


@pytest.fixture()
def svc_with_recognizer(ontology_service, repo, recognizer):
    return IndividualExtractionApplyService(
        ontology_service, repo, individual_recognizer=recognizer
    )


def _make_run(triples=None, run_id="run-ind-1"):
    """Build a minimal completed individual extraction PipelineRun mock."""
    run = MagicMock()
    run.id = run_id
    run.pipeline_type = PipelineType.INDIVIDUAL_EXTRACTION
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = {"triples": triples or []}
    return run


def _make_triple(
    subject_label,
    class_ids=None,
    confidence=0.9,
    predicate_prop_id=None,
    obj_id=None,
    obj_kind="class",
):
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
        triple["predicate"] = {
            "property_definition_id": predicate_prop_id,
            "label": "test-pred",
        }
        triple["object"] = {
            "kind": obj_kind,
            "id": obj_id or "tgt-id",
            "label": "Target",
        }
    return triple


def _make_open_v1_triple(subject_label, object_label="downstream_thing", confidence=0.75):
    """
    Build a triple shaped like open_v1's relation-triple output: no explicit
    subject id and no subject.class_ids (open_v1 emits untyped relation
    triples directly; typing, when it happens, is a separate is_a triple whose
    object — not the relation subject — carries the class reference). Exercises
    the recognition stage's unscoped-search path.
    """
    return {
        "subject": {"label": subject_label, "kind": "individual"},
        "predicate": {"label": "relates_to", "kind": "property"},
        "object": {"label": object_label, "kind": "individual"},
        "confidence": confidence,
    }


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
        run = _make_run(
            triples=[
                {
                    "subject": {
                        "kind": "class",
                        "id": "cls-x",
                        "label": "SomeClass",
                        "class_ids": [CLASS_ID],
                    },
                    "confidence": 0.9,
                }
            ]
        )
        result = svc.apply(run)
        assert result.individuals_created == 0

    def test_skips_individual_when_class_not_found(self, svc, repo):
        """Individuals with non-existent class_ids should be skipped."""
        run = _make_run(triples=[_make_triple("Bob", class_ids=["nonexistent-class-id"])])
        result = svc.apply(run)
        assert result.individuals_created == 0
        assert result.individuals_skipped == 1


# ---------------------------------------------------------------------------
# DuplicateEntityError handling
# ---------------------------------------------------------------------------


class TestDuplicateEntityErrorHandling:
    def test_duplicate_entity_error_resolves_to_existing_individual(
        self, svc, repo, ontology_service, monkeypatch
    ):
        """If OntologyService.create_individual raises DuplicateEntityError (e.g. the
        individual was created concurrently between the dedup check and the write),
        the apply service resolves to the existing individual's ID instead of failing
        or skipping the triple."""
        from domain.ontology.exceptions import DuplicateEntityError

        def fake_create_individual(*args, **kwargs):
            concurrent = Individual(id="ind-concurrent", class_ids=[CLASS_ID], title="Alice")
            repo.save_individual(concurrent)
            raise DuplicateEntityError("Individual with title 'Alice' already exists")

        monkeypatch.setattr(ontology_service, "create_individual", fake_create_individual)

        run = _make_run(triples=[_make_triple("Alice")])
        result = svc.apply(run)

        assert result.individuals_created == 0
        individuals = repo.list_individuals(class_id=CLASS_ID, limit=None)
        assert len(individuals) == 1
        assert individuals[0].id == "ind-concurrent"


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
        run = _make_run(
            triples=[
                _make_triple("Alice", confidence=0.9),
                _make_triple("Bob", confidence=0.2),
            ]
        )
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
        target_cls = Class(
            id="cls-org",
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            title="Org",
        )
        repo.save_class(target_cls)

        run = _make_run(
            triples=[
                _make_triple(
                    "Alice",
                    predicate_prop_id="prop-knows",
                    obj_id="cls-org",
                    obj_kind="class",
                ),
            ]
        )
        result = svc.apply(run)

        assert result.individuals_created == 1
        assert result.relationships_created == 1
        alice = repo.list_individuals(class_id=CLASS_ID, limit=None)[0]
        rels = repo.list_relationships(source_id=alice.id, property_id="prop-knows")
        assert len(rels) == 1
        assert rels[0].source_run_id == "run-ind-1"


# ---------------------------------------------------------------------------
# Recognition stage
# ---------------------------------------------------------------------------


class TestRecognitionStageNoOp:
    """No recognizer configured -> apply() is unchanged from pre-recognition behavior."""

    def test_no_recognizer_creates_new_individual_as_before(self, svc, repo):
        run = _make_run(triples=[_make_triple("Alice")])
        result = svc.apply(run)

        assert result.individuals_created == 1
        assert result.individuals_recognized == 0
        assert result.recognized_individual_ids == []

    def test_no_recognizer_skips_untyped_open_v1_triple_as_before(self, svc, repo):
        """An open_v1 relation triple with no subject.class_ids has nothing to
        type it as, and no recognizer to fall back on -> skipped, matching
        current (pre-recognition) behavior for untyped individuals."""
        run = _make_run(triples=[_make_open_v1_triple("kubernetes")])
        result = svc.apply(run)

        assert result.individuals_created == 0
        assert result.individuals_skipped == 1
        assert repo.list_individuals(class_id=CLASS_ID, limit=None) == []


class TestRecognitionStageMatch:
    """A configured recognizer resolving a mention to an existing individual."""

    def test_matched_mention_resolves_to_existing_individual_default_shaped(
        self, svc_with_recognizer, repo, recognizer
    ):
        existing = Individual(id="ind-kubernetes", class_ids=[CLASS_ID], title="Kubernetes")
        repo.save_individual(existing)
        recognizer.add_match(
            "K8s", RecognitionMatch("ind-kubernetes", "Kubernetes", 0.95, "vector")
        )

        run = _make_run(triples=[_make_triple("K8s")])
        result = svc_with_recognizer.apply(run)

        assert result.individuals_created == 0
        assert result.individuals_recognized == 1
        assert result.recognized_individual_ids == ["ind-kubernetes"]
        # No duplicate was minted alongside the pre-existing node.
        assert [i.id for i in repo.list_individuals(class_id=CLASS_ID, limit=None)] == [
            "ind-kubernetes"
        ]

    def test_matched_mention_resolves_open_v1_shaped_triple_via_unscoped_search(
        self, svc_with_recognizer, repo, recognizer
    ):
        """open_v1 relation triples carry no subject.class_ids; recognition must
        still be attempted (unscoped) rather than skipping outright."""
        existing = Individual(id="ind-kubernetes", class_ids=[CLASS_ID], title="Kubernetes")
        repo.save_individual(existing)
        recognizer.add_match(
            "kubernetes", RecognitionMatch("ind-kubernetes", "Kubernetes", 0.93, "vector")
        )

        run = _make_run(triples=[_make_open_v1_triple("kubernetes")])
        result = svc_with_recognizer.apply(run)

        assert result.individuals_created == 0
        assert result.individuals_recognized == 1
        assert result.recognized_individual_ids == ["ind-kubernetes"]
        assert recognizer.calls[0]["class_ids"] == []

    def test_recognized_individual_used_as_relationship_source(
        self, svc_with_recognizer, repo, recognizer
    ):
        existing = Individual(id="ind-kubernetes", class_ids=[CLASS_ID], title="Kubernetes")
        repo.save_individual(existing)
        recognizer.add_match(
            "K8s", RecognitionMatch("ind-kubernetes", "Kubernetes", 0.95, "vector")
        )
        prop = PropertyDefinition(id="prop-knows", identifier="knows", title="Knows")
        repo.save_property_definition(prop)
        target_cls = Class(
            id="cls-org", concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, title="Org"
        )
        repo.save_class(target_cls)

        run = _make_run(
            triples=[
                _make_triple(
                    "K8s", predicate_prop_id="prop-knows", obj_id="cls-org", obj_kind="class"
                )
            ]
        )
        result = svc_with_recognizer.apply(run)

        assert result.relationships_created == 1
        rels = repo.list_relationships(source_id="ind-kubernetes", property_id="prop-knows")
        assert len(rels) == 1


class TestRecognitionStageNoMatch:
    """No match found -> falls through to minting a new individual, unchanged."""

    def test_unmatched_mention_creates_new_individual(self, svc_with_recognizer, repo, recognizer):
        run = _make_run(triples=[_make_triple("Bob")])
        result = svc_with_recognizer.apply(run)

        assert result.individuals_created == 1
        assert result.individuals_recognized == 0
        individuals = repo.list_individuals(class_id=CLASS_ID, limit=None)
        assert individuals[0].title == "Bob"

    def test_similar_looking_individuals_in_same_run_are_not_merged(
        self, svc_with_recognizer, repo, recognizer
    ):
        """Two distinct, superficially similar mentions that neither match an
        existing graph node must both be created — never merged into each
        other. The recognizer only ever sees the persisted graph, so it
        reports no match for either."""
        run = _make_run(
            triples=[
                _make_triple("Order Service"),
                _make_triple("Order Service V2"),
            ]
        )
        result = svc_with_recognizer.apply(run)

        assert result.individuals_created == 2
        assert result.individuals_recognized == 0
        titles = {i.title for i in repo.list_individuals(class_id=CLASS_ID, limit=None)}
        assert titles == {"Order Service", "Order Service V2"}

    def test_unmatched_untyped_open_v1_triple_is_skipped(
        self, svc_with_recognizer, repo, recognizer
    ):
        """No match and no class info to type it as -> skipped, same as the
        no-recognizer case; recognition never fabricates a class."""
        run = _make_run(triples=[_make_open_v1_triple("some_new_thing")])
        result = svc_with_recognizer.apply(run)

        assert result.individuals_created == 0
        assert result.individuals_skipped == 1
        assert result.individuals_recognized == 0


class TestRecognitionStageBothOrchestrators:
    """Recognition is one shared stage — exercised identically regardless of
    which orchestrator's triple shape it receives."""

    def test_default_and_open_v1_shaped_triples_share_one_recognition_pass(
        self, svc_with_recognizer, repo, recognizer
    ):
        existing = Individual(id="ind-kubernetes", class_ids=[CLASS_ID], title="Kubernetes")
        repo.save_individual(existing)
        recognizer.add_match(
            "K8s", RecognitionMatch("ind-kubernetes", "Kubernetes", 0.95, "vector")
        )
        recognizer.add_match(
            "kubernetes", RecognitionMatch("ind-kubernetes", "Kubernetes", 0.93, "vector")
        )

        run = _make_run(
            triples=[
                _make_triple("K8s"),  # default-shaped: carries class_ids
                _make_open_v1_triple("kubernetes"),  # open_v1-shaped: no class_ids
                _make_triple("Carol"),  # unmatched default-shaped -> created
            ]
        )
        result = svc_with_recognizer.apply(run)

        assert result.individuals_recognized == 2
        assert set(result.recognized_individual_ids) == {"ind-kubernetes"}
        assert result.individuals_created == 1
        titles = {i.title for i in repo.list_individuals(class_id=CLASS_ID, limit=None)}
        assert titles == {"Kubernetes", "Carol"}
