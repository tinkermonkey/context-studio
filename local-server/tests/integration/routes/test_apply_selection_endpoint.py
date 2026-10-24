"""
Integration tests for explicit reviewer selections on POST /runs/{run_id}/apply.

Real SQLite (pipeline runs, ontology, change events) with an in-process event
publisher wired to the ChangeEventRecorder, so the tests also prove that
explicitly-selected applies still record ChangeEvents and revert cleanly.
Candidates are stored run fixtures — no LLM calls, no cassettes.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.web.pipelines_routes import router
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.events import (
    ClassCreated,
    ClassDeleted,
    IndividualCreated,
    IndividualDeleted,
    PropertyDefinitionCreated,
    PropertyDefinitionDeleted,
    RelationshipCreated,
    RelationshipDeleted,
)
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.apply_service import (
    IndividualExtractionApplyService,
)
from domain.pipelines.schema_extraction.apply_service import SchemaExtractionApplyService
from domain.versioning.revert_service import RevertService
from domain.versioning.services import VersioningService
from tests.fakes.fake_embedding_service import FakeEmbeddingService

TAXONOMY_ID = "tx-sel"
SCHEME_ID = "cs-sel"
CLASS_ID = "cls-org"
EXISTING_ID = "ind-acme"


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def pipeline_repo(session_factory):
    return PipelineRepository(session_factory=session_factory)


@pytest.fixture()
def ontology_repo(session_factory):
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    repo.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="sel_tax", title="Sel Taxonomy"))
    repo.save_concept_scheme(
        ConceptScheme(id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, identifier="sel_scheme", title="Sel")
    )
    repo.save_class(
        Class(
            id=CLASS_ID,
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            identifier="organization",
            title="Organization",
        )
    )
    repo.save_individual(Individual(id=EXISTING_ID, class_ids=[CLASS_ID], title="Acme Corp"))
    return repo


@pytest.fixture()
def change_repo(session_factory):
    return SQLiteChangeRepository(session_factory=session_factory)


@pytest.fixture()
def client(session_factory, pipeline_repo, ontology_repo, change_repo):
    publisher = InProcessEventPublisher()
    recorder = ChangeEventRecorder(change_repo)
    publisher.subscribe(IndividualCreated, recorder.on_individual_created)
    publisher.subscribe(IndividualDeleted, recorder.on_individual_deleted)
    publisher.subscribe(ClassCreated, recorder.on_class_created)
    publisher.subscribe(ClassDeleted, recorder.on_class_deleted)
    publisher.subscribe(PropertyDefinitionCreated, recorder.on_property_definition_created)
    publisher.subscribe(PropertyDefinitionDeleted, recorder.on_property_definition_deleted)
    publisher.subscribe(RelationshipCreated, recorder.on_relationship_created)
    publisher.subscribe(RelationshipDeleted, recorder.on_relationship_deleted)
    ontology_service = OntologyService(
        repository=ontology_repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=publisher,
    )

    app = FastAPI()
    app.include_router(router)
    app.state.pipeline_run_repo = pipeline_repo
    app.state.batch_repo = BatchRepository(session_factory=session_factory)
    app.state.implementation_registry = MagicMock()
    app.state.config_registry = MagicMock()
    app.state.llm_router = MagicMock()
    app.state.ontology_repo = ontology_repo
    app.state.individual_extraction_apply_svc = IndividualExtractionApplyService(
        ontology_service, ontology_repo
    )
    app.state.schema_extraction_apply_svc = SchemaExtractionApplyService(
        ontology_service, ontology_repo
    )
    app.state.revert_service = RevertService(change_repo=change_repo, ontology_repo=ontology_repo)
    app.state.versioning_service = VersioningService(
        change_repo=change_repo, sync_target=MagicMock(), event_publisher=MagicMock()
    )
    return TestClient(app)


def _completed_run(pipeline_repo, pipeline_type, output_summary):
    run = pipeline_repo.create(
        batch_run_id=str(uuid4()),
        pipeline_type=pipeline_type,
        implementation_id="default",
        configuration_ref="extraction-default",
        configuration_slug="extraction-default",
        configuration_version=1,
        specific_data=(
            {"source_text_hash": "abc123"}
            if pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION
            else None
        ),
    )
    pipeline_repo.update_status(run.id, PipelineRunStatus.COMPLETED)
    pipeline_repo.update_summaries(run.id, output_summary=output_summary)
    return run.id


def _org_triple(label, confidence, subject_id=""):
    return {
        "subject": {
            "kind": "individual",
            "id": subject_id,
            "label": label,
            "class_ids": [CLASS_ID],
        },
        "predicate": {"property_definition_id": None, "label": "is_a"},
        "object": {"kind": "class", "id": CLASS_ID, "label": "organization"},
        "confidence": confidence,
    }


@pytest.fixture()
def individual_run(pipeline_repo):
    return _completed_run(
        pipeline_repo,
        PipelineType.INDIVIDUAL_EXTRACTION,
        {
            "triples": [
                _org_triple("Globex", 0.95),  # triple-0: reviewer rejects
                _org_triple("Initech", 0.2),  # triple-1: reviewer accepts despite low conf
                _org_triple("ACME Corporation", 0.9),  # triple-2: reviewer merges
                _org_triple("Acme Corp", 0.9, subject_id=EXISTING_ID),  # triple-3: mapped
            ]
        },
    )


def _apply(client, run_id, body=None, **params):
    return client.post(f"/api/pipelines/runs/{run_id}/apply", params=params, json=body)


class TestCandidateIdentity:
    def test_individual_candidates_carry_ids_and_mapped_titles(self, client, individual_run):
        response = client.get(
            f"/api/pipelines/runs/{individual_run}/individual-extraction-candidates"
        )
        assert response.status_code == status.HTTP_200_OK
        items = response.json()
        assert [c["candidate_id"] for c in items] == [
            "triple-0",
            "triple-1",
            "triple-2",
            "triple-3",
        ]
        assert items[0]["subject"]["title"] is None  # new mention
        assert items[0]["object"]["title"] == "Organization"  # mapped class
        assert items[3]["subject"]["title"] == "Acme Corp"  # mapped individual

    def test_schema_candidates_carry_per_kind_ids(self, client, pipeline_repo):
        run_id = _completed_run(
            pipeline_repo,
            PipelineType.SCHEMA_EXTRACTION,
            {
                "candidates": [
                    {"kind": "class", "label": "Service", "confidence": 0.9},
                    {"kind": "property_definition", "label": "calls", "confidence": 0.9},
                    {"kind": "class", "label": "Client", "confidence": 0.9},
                ],
                "connections": [
                    {"subject_ref": "Client", "predicate": "calls", "object_ref": "Service"}
                ],
            },
        )
        response = client.get(f"/api/pipelines/runs/{run_id}/schema-extraction-candidates")
        assert [c["candidate_id"] for c in response.json()] == [
            "class-0",
            "property-0",
            "class-1",
            "connection-0",
        ]


class TestIndividualSelectionApply:
    def test_explicit_selection_and_decisions_round_trip_from_candidates(
        self, client, individual_run, ontology_repo, change_repo
    ):
        candidates = client.get(
            f"/api/pipelines/runs/{individual_run}/individual-extraction-candidates"
        ).json()
        accepted = [c["candidate_id"] for c in candidates if c["subject"]["label"] != "Globex"]

        response = _apply(
            client,
            individual_run,
            body={
                "accepted_candidate_ids": accepted,
                "recognition_decisions": [
                    {
                        "mention_label": "acme corporation",
                        "decision": "merge",
                        "individual_id": EXISTING_ID,
                    },
                    {"mention_label": "Initech", "decision": "separate"},
                ],
            },
            confidence_threshold=0.5,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["individuals_created"] == 1
        assert body["applied_candidate_ids"] == ["triple-1", "triple-2", "triple-3"]
        assert body["skipped_candidate_ids"] == ["triple-0"]
        assert body["merged_mentions"] == [
            {
                "mention_label": "ACME Corporation",
                "individual_id": EXISTING_ID,
                "source": "decision",
            }
        ]
        titles = sorted(
            i.title for i in ontology_repo.list_individuals(class_id=CLASS_ID, limit=None)
        )
        assert titles == ["Acme Corp", "Initech"]

        # ChangeEvents were recorded for the created individual, and revert removes it
        # while leaving the merge target untouched.
        events = client.get(f"/api/pipelines/runs/{individual_run}/change-events")
        assert events.status_code == status.HTTP_200_OK
        created_ids = set(body["created_individual_ids"])
        assert created_ids and created_ids <= {e["entity_id"] for e in events.json()["items"]}
        revert = client.post(f"/api/pipelines/runs/{individual_run}/revert")
        assert revert.status_code == status.HTTP_200_OK, revert.text
        assert revert.json()["individuals_deleted"] == 1
        titles = sorted(
            i.title for i in ontology_repo.list_individuals(class_id=CLASS_ID, limit=None)
        )
        assert titles == ["Acme Corp"]

    def test_threshold_only_apply_without_body_is_unchanged(self, client, individual_run):
        body = _apply(client, individual_run, confidence_threshold=0.5).json()
        # Globex + ACME Corporation created; Initech below threshold; Acme Corp mapped.
        assert body["individuals_created"] == 2
        assert body["individuals_skipped"] == 1
        assert body["skipped_candidate_ids"] == ["triple-1"]
        assert body["merged_mentions"] == []

    def test_unknown_candidate_id_returns_422_and_writes_nothing(
        self, client, individual_run, ontology_repo
    ):
        response = _apply(client, individual_run, body={"accepted_candidate_ids": ["triple-99"]})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "triple-99" in response.json()["detail"]
        assert len(ontology_repo.list_individuals(class_id=CLASS_ID, limit=None)) == 1

    def test_merge_into_missing_individual_returns_422(self, client, individual_run):
        response = _apply(
            client,
            individual_run,
            body={
                "recognition_decisions": [
                    {"mention_label": "Globex", "decision": "merge", "individual_id": "nope"}
                ]
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "nope" in response.json()["detail"]

    def test_decision_for_unknown_mention_returns_422(self, client, individual_run):
        response = _apply(
            client,
            individual_run,
            body={"recognition_decisions": [{"mention_label": "Nobody", "decision": "separate"}]},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_merge_without_individual_id_fails_validation(self, client, individual_run):
        response = _apply(
            client,
            individual_run,
            body={"recognition_decisions": [{"mention_label": "Globex", "decision": "merge"}]},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_relationship_between_existing_individuals_is_reverted(
        self, client, pipeline_repo, ontology_repo
    ):
        ontology_repo.save_individual(
            Individual(id="ind-globex", class_ids=[CLASS_ID], title="Globex")
        )
        ontology_repo.save_property_definition(
            PropertyDefinition(id="prop-partner", identifier="partners_with", title="partners with")
        )
        run_id = _completed_run(
            pipeline_repo,
            PipelineType.INDIVIDUAL_EXTRACTION,
            {
                "triples": [
                    {
                        "subject": {
                            "kind": "individual",
                            "id": EXISTING_ID,
                            "label": "Acme Corp",
                            "class_ids": [CLASS_ID],
                        },
                        "predicate": {
                            "property_definition_id": "prop-partner",
                            "label": "partners with",
                        },
                        "object": {"kind": "individual", "id": "ind-globex", "label": "Globex"},
                        "confidence": 0.9,
                    }
                ]
            },
        )
        body = _apply(client, run_id).json()
        assert body["individuals_created"] == 0
        assert body["relationships_created"] == 1

        revert = client.post(f"/api/pipelines/runs/{run_id}/revert")
        assert revert.status_code == status.HTTP_200_OK, revert.text
        assert revert.json()["relationships_deleted"] == 1
        assert ontology_repo.get_relationship(body["created_relationship_ids"][0]) is None
        assert ontology_repo.get_individual(EXISTING_ID) is not None
        assert ontology_repo.get_individual("ind-globex") is not None


class TestSchemaSelectionApply:
    def test_accepted_ids_override_threshold(self, client, pipeline_repo, ontology_repo):
        run_id = _completed_run(
            pipeline_repo,
            PipelineType.SCHEMA_EXTRACTION,
            {
                "candidates": [
                    {"kind": "class", "label": "Service", "confidence": 0.95},
                    {"kind": "class", "label": "Client", "confidence": 0.1},
                ],
                "connections": [],
            },
        )
        response = _apply(
            client,
            run_id,
            body={"accepted_candidate_ids": ["class-1"]},
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
            confidence_threshold=0.5,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["classes_created"] == 1
        assert body["applied_candidate_ids"] == ["class-1"]
        assert body["skipped_candidate_ids"] == ["class-0"]
        titles = {
            c.title for c in ontology_repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)
        }
        assert "Client" in titles and "Service" not in titles

    def test_recognition_decisions_rejected_for_schema_runs(self, client, pipeline_repo):
        run_id = _completed_run(
            pipeline_repo, PipelineType.SCHEMA_EXTRACTION, {"candidates": [], "connections": []}
        )
        response = _apply(
            client,
            run_id,
            body={"recognition_decisions": [{"mention_label": "X", "decision": "separate"}]},
            concept_scheme_id=SCHEME_ID,
            taxonomy_id=TAXONOMY_ID,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_applied_schema_entities_record_change_events_and_revert(
        self, client, pipeline_repo, ontology_repo
    ):
        run_id = _completed_run(
            pipeline_repo,
            PipelineType.SCHEMA_EXTRACTION,
            {
                "candidates": [
                    {"kind": "class", "label": "Knowledge Curator", "confidence": 0.9},
                    {"kind": "class", "label": "Hosted Model", "confidence": 0.9},
                    {"kind": "property_definition", "label": "curates", "confidence": 0.9},
                ],
                "connections": [
                    {
                        "subject_ref": "Knowledge Curator",
                        "predicate": "curates",
                        "object_ref": "Hosted Model",
                        "confidence": 0.9,
                    }
                ],
            },
        )
        body = _apply(client, run_id, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID).json()
        assert body["classes_created"] == 2
        assert body["properties_created"] == 1
        assert body["relationships_created"] == 1
        created_ids = (
            set(body["created_class_ids"])
            | set(body["created_property_definition_ids"])
            | set(body["created_relationship_ids"])
        )

        events = client.get(f"/api/pipelines/runs/{run_id}/change-events").json()["items"]
        assert created_ids <= {e["entity_id"] for e in events}

        revert = client.post(f"/api/pipelines/runs/{run_id}/revert")
        assert revert.status_code == status.HTTP_200_OK, revert.text
        reverted = revert.json()
        assert reverted["classes_deleted"] == 2
        assert reverted["properties_deleted"] == 1
        assert reverted["relationships_deleted"] == 1
        titles = {
            c.title for c in ontology_repo.list_classes(concept_scheme_id=SCHEME_ID, limit=None)
        }
        assert titles == {"Organization"}
        assert ontology_repo.get_property_definition_by_identifier("curates") is None

        again = client.post(f"/api/pipelines/runs/{run_id}/revert").json()
        assert again["events_reverted"] == 0

    def test_existing_class_title_is_reported_as_existing_not_created(
        self, client, pipeline_repo
    ):
        run_id = _completed_run(
            pipeline_repo,
            PipelineType.SCHEMA_EXTRACTION,
            {
                "candidates": [
                    {"kind": "class", "label": "organization", "confidence": 0.9},
                    {"kind": "class", "label": "Hosted Model", "confidence": 0.9},
                ],
                "connections": [],
            },
        )
        body = _apply(client, run_id, concept_scheme_id=SCHEME_ID, taxonomy_id=TAXONOMY_ID).json()
        assert body["classes_created"] == 1
        assert body["applied_candidate_ids"] == ["class-0", "class-1"]
        assert body["existing_candidate_ids"] == ["class-0"]
        assert body["skipped_candidate_ids"] == []

        # Revert removes only what this run created; the pre-existing class stays.
        revert = client.post(f"/api/pipelines/runs/{run_id}/revert").json()
        assert revert["classes_deleted"] == 1

    def test_taxonomy_not_owning_scheme_returns_400(self, client, pipeline_repo):
        run_id = _completed_run(
            pipeline_repo, PipelineType.SCHEMA_EXTRACTION, {"candidates": [], "connections": []}
        )
        response = _apply(client, run_id, concept_scheme_id=SCHEME_ID, taxonomy_id="tx-other")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
