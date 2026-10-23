"""
Unit tests for explicit reviewer selections on pipeline apply.

Covers candidate identity (domain.pipelines.candidate_ids), accepted-candidate
selection and per-mention recognition decisions for individual extraction, and
accepted-candidate selection for schema extraction. In-memory fakes only.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

from unittest.mock import MagicMock

import pytest

from domain.extraction.ports import RecognitionMatch
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.services import OntologyService
from domain.pipelines.apply_result import ApplyResult, MergedMention
from domain.pipelines.apply_selection import RecognitionDecision
from domain.pipelines.candidate_ids import (
    enumerate_schema_candidates,
    enumerate_schema_connections,
    enumerate_triples,
    mention_key,
)
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import ApplySelectionError, PipelineInputError
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from domain.pipelines.schema_extraction.apply_service import SchemaExtractionApplyService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_individual_recognizer import FakeIndividualRecognizer
from tests.fakes.fake_ontology_repository import FakeOntologyRepository

TAXONOMY_ID = "tx-1"
SCHEME_ID = "cs-1"
CLASS_ID = "cls-person"


@pytest.fixture()
def repo():
    r = FakeOntologyRepository()
    r.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="test_tax", title="Test Taxonomy"))
    r.save_concept_scheme(
        ConceptScheme(
            id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, identifier="test_scheme", title="Scheme"
        )
    )
    r.save_class(
        Class(
            id=CLASS_ID,
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="person",
            title="Person",
        )
    )
    return r


@pytest.fixture()
def recognizer():
    return FakeIndividualRecognizer()


@pytest.fixture()
def svc(repo, recognizer):
    ontology_service = OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=FakeEventPublisher(),
    )
    return IndividualExtractionApplyService(
        ontology_service, repo, individual_recognizer=recognizer
    )


@pytest.fixture()
def schema_svc(repo):
    return SchemaExtractionApplyService(repo)


def _run(output_summary, pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION):
    run = MagicMock()
    run.id = "run-sel-1"
    run.pipeline_type = pipeline_type
    run.status = PipelineRunStatus.COMPLETED
    run.output_summary = output_summary
    return run


def _triple(label, confidence=0.9, obj_label=None, prop_id=None):
    triple = {
        "subject": {"kind": "individual", "id": "", "label": label, "class_ids": [CLASS_ID]},
        "confidence": confidence,
    }
    if obj_label:
        triple["predicate"] = {"property_definition_id": prop_id, "label": "knows"}
        triple["object"] = {"kind": "individual", "id": "", "label": obj_label}
    return triple


def _titles(repo):
    return sorted(i.title for i in repo.list_individuals(class_id=CLASS_ID, limit=None))


# ---------------------------------------------------------------------------
# Candidate identity
# ---------------------------------------------------------------------------


class TestCandidateIds:
    def test_triple_ids_are_positional(self):
        summary = {"triples": [_triple("A"), _triple("B")]}
        assert [cid for cid, _ in enumerate_triples(summary)] == ["triple-0", "triple-1"]

    def test_schema_candidate_ids_are_per_kind_and_skip_unknown_kinds(self):
        summary = {
            "candidates": [
                {"kind": "class", "label": "A"},
                {"kind": "property_definition", "label": "p"},
                {"kind": "mystery", "label": "?"},
                {"kind": "class", "label": "B"},
            ],
            "connections": [{"subject_ref": "A", "predicate": "p", "object_ref": "B"}],
        }
        assert [cid for cid, _ in enumerate_schema_candidates(summary)] == [
            "class-0",
            "property-0",
            "class-1",
        ]
        assert [cid for cid, _ in enumerate_schema_connections(summary)] == ["connection-0"]

    def test_empty_or_missing_summary_yields_no_ids(self):
        assert enumerate_triples(None) == []
        assert enumerate_schema_candidates({}) == []

    def test_mention_key_strips_and_lowercases(self):
        assert mention_key("  Acme Corp ") == "acme corp"
        assert mention_key(None) == ""

    def test_apply_selection_error_is_pipeline_input_error(self):
        assert issubclass(ApplySelectionError, PipelineInputError)


# ---------------------------------------------------------------------------
# Individual extraction: accepted candidates
# ---------------------------------------------------------------------------


class TestIndividualAcceptedCandidates:
    def test_threshold_only_apply_reports_outcomes_and_is_otherwise_unchanged(self, svc, repo):
        run = _run({"triples": [_triple("Alice", 0.9), _triple("Bob", 0.2)]})
        result = svc.apply(run, confidence_threshold=0.5)
        assert result.individuals_created == 1
        assert result.individuals_skipped == 1
        assert result.applied_candidate_ids == ["triple-0"]
        assert result.skipped_candidate_ids == ["triple-1"]
        assert _titles(repo) == ["Alice"]

    def test_selection_overrides_threshold_both_ways(self, svc, repo):
        """Reject a high-confidence triple and accept a low-confidence one."""
        run = _run({"triples": [_triple("Alice", 0.95), _triple("Bob", 0.1)]})
        result = svc.apply(run, confidence_threshold=0.5, accepted_candidate_ids=["triple-1"])
        assert _titles(repo) == ["Bob"]
        assert result.applied_candidate_ids == ["triple-1"]
        assert result.skipped_candidate_ids == ["triple-0"]
        assert result.individuals_skipped == 1

    def test_empty_selection_applies_nothing(self, svc, repo):
        run = _run({"triples": [_triple("Alice")]})
        result = svc.apply(run, accepted_candidate_ids=[])
        assert result.individuals_created == 0
        assert result.skipped_candidate_ids == ["triple-0"]
        assert _titles(repo) == []

    def test_unknown_candidate_ids_raise_before_any_write(self, svc, repo):
        run = _run({"triples": [_triple("Alice")]})
        with pytest.raises(ApplySelectionError, match="triple-7"):
            svc.apply(run, accepted_candidate_ids=["triple-0", "triple-7"])
        assert _titles(repo) == []

    def test_selected_relationship_carries_source_run_id(self, svc, repo):
        repo.save_property_definition(
            PropertyDefinition(id="p-knows", identifier="knows", title="Knows")
        )
        run = _run(
            {
                "triples": [
                    _triple("Bob"),
                    _triple("Alice", obj_label="Bob", prop_id="p-knows"),
                ]
            }
        )
        result = svc.apply(run, accepted_candidate_ids=["triple-0", "triple-1"])
        assert result.relationships_created == 1
        rel = repo.list_relationships(property_id="p-knows")[0]
        assert rel.source_run_id == "run-sel-1"


# ---------------------------------------------------------------------------
# Individual extraction: recognition decisions
# ---------------------------------------------------------------------------


class TestRecognitionDecisions:
    def test_merge_adopts_target_without_calling_recognizer(self, svc, repo, recognizer):
        repo.save_individual(Individual(id="ind-k8s", class_ids=[CLASS_ID], title="Kubernetes"))
        run = _run({"triples": [_triple("K8s")]})
        result = svc.apply(
            run,
            recognition_decisions=[
                RecognitionDecision(mention_label="k8s ", decision="merge", individual_id="ind-k8s")
            ],
        )
        assert recognizer.calls == []
        assert result.individuals_created == 0
        assert result.recognized_individual_ids == ["ind-k8s"]
        assert result.merged_mentions == [MergedMention("K8s", "ind-k8s", "decision")]
        assert result.applied_candidate_ids == ["triple-0"]
        assert _titles(repo) == ["Kubernetes"]

    def test_merged_mention_resolves_as_later_relationship_object(self, svc, repo):
        repo.save_individual(Individual(id="ind-k8s", class_ids=[CLASS_ID], title="Kubernetes"))
        repo.save_property_definition(
            PropertyDefinition(id="p-uses", identifier="uses", title="Uses")
        )
        run = _run(
            {
                "triples": [
                    _triple("K8s"),
                    _triple("Alice", obj_label="K8s", prop_id="p-uses"),
                ]
            }
        )
        svc.apply(
            run,
            recognition_decisions=[
                RecognitionDecision(mention_label="K8s", decision="merge", individual_id="ind-k8s")
            ],
        )
        rels = repo.list_relationships(property_id="p-uses")
        assert [r.target_id for r in rels] == ["ind-k8s"]

    def test_separate_skips_recognizer_and_mints_new(self, svc, repo, recognizer):
        repo.save_individual(Individual(id="ind-k8s", class_ids=[CLASS_ID], title="Kubernetes"))
        recognizer.add_match("K8s", RecognitionMatch("ind-k8s", "Kubernetes", 0.95, "vector"))
        run = _run({"triples": [_triple("K8s")]})
        result = svc.apply(run, recognition_decisions=[RecognitionDecision("K8s", "separate")])
        assert recognizer.calls == []
        assert result.individuals_created == 1
        assert result.merged_mentions == []
        assert _titles(repo) == ["K8s", "Kubernetes"]

    def test_separate_with_same_title_in_class_resolves_to_existing_and_is_reported(
        self, svc, repo
    ):
        repo.save_individual(Individual(id="ind-k8s", class_ids=[CLASS_ID], title="K8s"))
        run = _run({"triples": [_triple("K8s")]})
        result = svc.apply(run, recognition_decisions=[RecognitionDecision("K8s", "separate")])
        assert result.individuals_created == 0
        assert result.merged_mentions == [MergedMention("K8s", "ind-k8s", "existing_title")]

    def test_undecided_mentions_still_use_recognizer(self, svc, repo, recognizer):
        repo.save_individual(Individual(id="ind-k8s", class_ids=[CLASS_ID], title="Kubernetes"))
        recognizer.add_match("K8s", RecognitionMatch("ind-k8s", "Kubernetes", 0.95, "vector"))
        run = _run({"triples": [_triple("K8s"), _triple("Alice")]})
        result = svc.apply(run, recognition_decisions=[RecognitionDecision("Alice", "separate")])
        assert [c["label"] for c in recognizer.calls] == ["K8s"]
        assert result.merged_mentions == [MergedMention("K8s", "ind-k8s", "recognition")]
        assert result.individuals_created == 1

    def test_invalid_decisions_collected_into_one_error_before_writes(self, svc, repo):
        run = _run({"triples": [_triple("Alice"), _triple("Bob"), _triple("Carol")]})
        with pytest.raises(ApplySelectionError) as exc_info:
            svc.apply(
                run,
                recognition_decisions=[
                    RecognitionDecision("Nobody", "separate"),
                    RecognitionDecision("Alice", "merge", individual_id="ind-missing"),
                    RecognitionDecision("Bob", "merge"),
                    RecognitionDecision("Carol", "separate"),
                    RecognitionDecision("carol", "separate"),
                ],
            )
        message = str(exc_info.value)
        assert "Nobody" in message
        assert "ind-missing" in message
        assert "no individual_id" in message
        assert "more than one decision" in message
        assert _titles(repo) == []


# ---------------------------------------------------------------------------
# Schema extraction: accepted candidates
# ---------------------------------------------------------------------------


def _schema_summary():
    return {
        "candidates": [
            {"kind": "class", "label": "Service", "confidence": 0.95},
            {"kind": "class", "label": "Client", "confidence": 0.2},
            {"kind": "property_definition", "label": "calls", "confidence": 0.9},
        ],
        "connections": [
            {
                "subject_ref": "Client",
                "predicate": "calls",
                "object_ref": "Service",
                "confidence": 0.9,
            }
        ],
    }


class TestSchemaAcceptedCandidates:
    def test_threshold_only_apply_reports_outcomes(self, schema_svc, repo):
        run = _run(_schema_summary(), PipelineType.SCHEMA_EXTRACTION)
        result = schema_svc.apply(run, SCHEME_ID, TAXONOMY_ID, confidence_threshold=0.5)
        assert result.classes_created == 1
        assert result.applied_candidate_ids == ["class-0", "property-0"]
        # Connection skipped because its subject class (Client) was below threshold.
        assert result.skipped_candidate_ids == ["class-1", "connection-0"]

    def test_selection_overrides_threshold(self, schema_svc, repo):
        run = _run(_schema_summary(), PipelineType.SCHEMA_EXTRACTION)
        result = schema_svc.apply(
            run,
            SCHEME_ID,
            TAXONOMY_ID,
            confidence_threshold=0.5,
            accepted_candidate_ids=["class-0", "class-1", "property-0", "connection-0"],
        )
        titles = sorted(c.title for c in repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None))
        assert titles == ["Client", "Person", "Service"]
        assert result.relationships_created == 1
        assert result.skipped_candidate_ids == []
        rel = repo.get_relationship(result.created_relationship_ids[0])
        assert rel.source_run_id == "run-sel-1"

    def test_accepted_connection_with_unaccepted_class_is_skipped(self, schema_svc, repo):
        run = _run(_schema_summary(), PipelineType.SCHEMA_EXTRACTION)
        result = schema_svc.apply(
            run,
            SCHEME_ID,
            TAXONOMY_ID,
            accepted_candidate_ids=["class-0", "property-0", "connection-0"],
        )
        assert result.relationships_created == 0
        assert result.skipped_candidate_ids == ["class-1", "connection-0"]

    def test_unknown_ids_raise_before_any_write(self, schema_svc, repo):
        run = _run(_schema_summary(), PipelineType.SCHEMA_EXTRACTION)
        with pytest.raises(ApplySelectionError, match="class-9"):
            schema_svc.apply(run, SCHEME_ID, TAXONOMY_ID, accepted_candidate_ids=["class-9"])
        assert len(repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)) == 1


class TestApplyResultValidation:
    def test_candidate_cannot_be_applied_and_skipped(self):
        with pytest.raises(ValueError, match="both applied and skipped"):
            ApplyResult(applied_candidate_ids=["triple-0"], skipped_candidate_ids=["triple-0"])
