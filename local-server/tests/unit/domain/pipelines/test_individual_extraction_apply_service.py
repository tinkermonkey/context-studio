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
        assert result.individuals_recognized == 1
        assert result.recognized_individual_ids == ["ind-concurrent"]

    def test_lookup_failure_after_duplicate_entity_error_is_logged_and_propagates(
        self, svc, repo, ontology_service, monkeypatch, caplog
    ):
        """If the label lookup performed inside the DuplicateEntityError handler
        itself raises, the error must propagate (sibling except Exception cannot
        catch errors raised from within another except block) and must be logged
        with context before propagating."""
        from domain.ontology.exceptions import DuplicateEntityError

        def fake_create_individual(*args, **kwargs):
            raise DuplicateEntityError("Individual with title 'Alice' already exists")

        monkeypatch.setattr(ontology_service, "create_individual", fake_create_individual)

        # The first call to _find_individual_by_label happens inside
        # _resolve_individual_id, before creation is even attempted, and must
        # succeed (return None) so the flow reaches create_individual. Only the
        # second call — made from inside the DuplicateEntityError handler — should
        # fail, to isolate the handler's own error-propagation behavior.
        call_count = {"n": 0}

        def flaky_lookup(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(svc, "_find_individual_by_label", flaky_lookup)

        run = _make_run(triples=[_make_triple("Alice")])
        with caplog.at_level("ERROR"):
            with pytest.raises(RuntimeError, match="db unavailable"):
                svc.apply(run)

        assert any("Alice" in record.getMessage() for record in caplog.records)


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

    def test_recognition_threshold_defaults_to_none(self, svc_with_recognizer, repo, recognizer):
        run = _make_run(triples=[_make_triple("K8s")])
        svc_with_recognizer.apply(run)

        assert recognizer.calls[0]["threshold"] is None

    def test_recognition_threshold_is_forwarded_to_recognizer(
        self, svc_with_recognizer, repo, recognizer
    ):
        run = _make_run(triples=[_make_triple("K8s")])
        svc_with_recognizer.apply(run, recognition_threshold=0.75)

        assert recognizer.calls[0]["threshold"] == 0.75


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


class TestRecognitionStageFailureHandling:
    """A recognizer failure is best-effort (treated as no-match) only for
    genuine operational errors. Programming bugs must surface rather than be
    swallowed into a silently-minted duplicate individual."""

    @pytest.mark.parametrize("exc_type", [TypeError, AttributeError, KeyError, IndexError])
    def test_programming_bug_in_recognizer_propagates(
        self, svc_with_recognizer, repo, recognizer, monkeypatch, exc_type
    ):
        def broken_recognize(*args, **kwargs):
            raise exc_type("boom")

        monkeypatch.setattr(recognizer, "recognize", broken_recognize)

        run = _make_run(triples=[_make_triple("Alice")])
        with pytest.raises(exc_type, match="boom"):
            svc_with_recognizer.apply(run)

    def test_operational_error_in_recognizer_is_treated_as_no_match(
        self, svc_with_recognizer, repo, recognizer, monkeypatch
    ):
        def broken_recognize(*args, **kwargs):
            raise RuntimeError("vector index unavailable")

        monkeypatch.setattr(recognizer, "recognize", broken_recognize)

        run = _make_run(triples=[_make_triple("Alice")])
        result = svc_with_recognizer.apply(run)

        assert result.individuals_created == 1
        assert result.individuals_recognized == 0


class TestClasslessRecognitionCache:
    """Classless (open_v1) mentions must be cached after recognition, same as
    class-scoped mentions, so a repeated mention hits the in-pass cache
    instead of triggering a redundant recognizer call."""

    def test_repeated_classless_mention_uses_cache_after_first_recognition(
        self, svc_with_recognizer, repo, recognizer
    ):
        existing = Individual(id="ind-kubernetes", class_ids=[CLASS_ID], title="Kubernetes")
        repo.save_individual(existing)
        recognizer.add_match(
            "kubernetes", RecognitionMatch("ind-kubernetes", "Kubernetes", 0.93, "vector")
        )

        run = _make_run(
            triples=[
                _make_open_v1_triple("kubernetes"),
                _make_open_v1_triple("kubernetes"),
            ]
        )
        result = svc_with_recognizer.apply(run)

        # Only the first occurrence triggers the recognizer; the second is a cache hit.
        assert len(recognizer.calls) == 1
        assert result.individuals_recognized == 1
        assert result.recognized_individual_ids == ["ind-kubernetes"]


class TestSameRunMergingGuard:
    """Recognition must resolve only against individuals that existed in the
    graph before this apply pass — never against a sibling mention minted
    earlier in the same pass. Uses the real CascadeIndividualRecognizer wired
    to a vector index shared with OntologyService (mirroring the shared
    instance wiring in app.py), the same setup that surfaced the bug."""

    def test_recognizer_match_pointing_at_individual_created_this_run_is_ignored(
        self, repo
    ):
        from adapters.recognition.individual_recognizer import CascadeIndividualRecognizer
        from tests.fakes.fake_event_publisher import FakeEventPublisher
        from tests.fakes.fake_individual_vector_index import FakeIndividualVectorIndex

        class _ConstantEmbeddingService:
            """Every mention embeds identically, so the second mention is a
            guaranteed vector match against anything already indexed -
            isolating the same-run guard from embedding-quality concerns."""

            def embed(self, text):
                return [1.0, 0.0]

            def embed_batch(self, texts):
                return [self.embed(t) for t in texts]

            def similarity(self, a, b):
                return 1.0

        # vectors maps indexed title -> vector; the fake's search() looks up
        # a candidate's score by its stored title, so "Order Service" (the
        # first mention, once created) must resolve to the same vector the
        # constant embedding service returns for any query.
        shared_index = FakeIndividualVectorIndex(
            vectors={"Order Service": [1.0, 0.0]}, repo=repo
        )
        embedding_service = _ConstantEmbeddingService()
        ontology_service = OntologyService(
            repository=repo,
            embedding_service=embedding_service,
            event_publisher=FakeEventPublisher(),
            individual_index=shared_index,
        )
        recognizer = CascadeIndividualRecognizer(
            individual_index=shared_index,
            embedding_service=embedding_service,
            threshold=0.5,
        )
        svc = IndividualExtractionApplyService(
            ontology_service, repo, individual_recognizer=recognizer
        )

        run = _make_run(
            triples=[
                _make_triple("Order Service"),
                _make_triple("Order Service V2"),
            ]
        )
        result = svc.apply(run)

        assert result.individuals_created == 2
        assert result.individuals_recognized == 0
        titles = {i.title for i in repo.list_individuals(class_id=CLASS_ID, limit=None)}
        assert titles == {"Order Service", "Order Service V2"}


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
