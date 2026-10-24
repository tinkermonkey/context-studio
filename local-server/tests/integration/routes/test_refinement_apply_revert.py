"""
Integration tests: refinement-pipeline applies record ChangeEvents and revert cleanly.

Covers schema_node_grounding, schema_node_definition_refinement and
schema_node_connection_refinement through POST /runs/{id}/apply and
POST /runs/{id}/revert, with real SQLite and an in-process event publisher wired
to the ChangeEventRecorder (as in app.py). Each test applies a seeded completed
run, asserts change events were recorded under the run's batch, reverts, and
asserts the ontology is back to its prior state. No LLM calls, no cassettes.
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
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.events import (
    ClassUpdated,
    RelationshipCreated,
    RelationshipDeleted,
)
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.schema_node_connection_refinement.apply_service import (
    SchemaConnectionRefinementApplyService,
)
from domain.pipelines.schema_node_definition_refinement.apply_service import (
    SchemaDefinitionRefinementApplyService,
)
from domain.pipelines.schema_node_grounding.apply_service import SchemaGroundingApplyService
from domain.versioning.revert_service import RevertService
from domain.versioning.services import VersioningService
from tests.fakes.fake_embedding_service import FakeEmbeddingService

TAXONOMY_ID = "tx-ref"
SCHEME_ID = "cs-ref"
SERVICE_ID = "cls-service"
DATABASE_ID = "cls-database"
QUEUE_ID = "cls-queue"
USES_ID = "prop-uses"
EXISTING_REL_ID = "rel-service-uses-queue"
ORIGINAL_DEFINITION = "A deployable unit."
EXISTING_REF_URI = "https://www.wikidata.org/wiki/Q1"


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
    repo.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="ref_tax", title="Ref Taxonomy"))
    repo.save_concept_scheme(
        ConceptScheme(id=SCHEME_ID, taxonomy_id=TAXONOMY_ID, identifier="ref_scheme", title="Ref")
    )
    existing_ref = ExternalReference(
        source="wikidata", identifier=EXISTING_REF_URI, uri=EXISTING_REF_URI
    )
    for class_id, title in [
        (SERVICE_ID, "Service"),
        (DATABASE_ID, "Database"),
        (QUEUE_ID, "Queue"),
    ]:
        is_service = class_id == SERVICE_ID
        repo.save_class(
            Class(
                id=class_id,
                concept_scheme_id=SCHEME_ID,
                taxonomy_id=TAXONOMY_ID,
                identifier=title.lower(),
                title=title,
                description=ORIGINAL_DEFINITION if is_service else None,
                external_references=[existing_ref] if is_service else [],
            )
        )
    repo.save_property_definition(PropertyDefinition(id=USES_ID, identifier="uses", title="uses"))
    repo.save_relationship(
        Relationship(
            id=EXISTING_REL_ID,
            source_id=SERVICE_ID,
            target_id=QUEUE_ID,
            property_definition_id=USES_ID,
        )
    )
    return repo


@pytest.fixture()
def change_repo(session_factory):
    return SQLiteChangeRepository(session_factory=session_factory)


@pytest.fixture()
def client(session_factory, pipeline_repo, ontology_repo, change_repo):
    publisher = InProcessEventPublisher()
    recorder = ChangeEventRecorder(change_repo)
    publisher.subscribe(ClassUpdated, recorder.on_class_updated)
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
    app.state.schema_grounding_apply_svc = SchemaGroundingApplyService(
        ontology_service, ontology_repo
    )
    app.state.schema_definition_apply_svc = SchemaDefinitionRefinementApplyService(
        ontology_service, ontology_repo
    )
    app.state.schema_connection_apply_svc = SchemaConnectionRefinementApplyService(
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
        configuration_ref="refinement-default",
        configuration_slug="refinement-default",
        configuration_version=1,
    )
    pipeline_repo.update_status(run.id, PipelineRunStatus.COMPLETED)
    pipeline_repo.update_summaries(run.id, output_summary=output_summary)
    return run.id


def _change_events(client, run_id):
    response = client.get(f"/api/pipelines/runs/{run_id}/change-events")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["items"]


def _revert(client, run_id):
    response = client.post(f"/api/pipelines/runs/{run_id}/revert")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def _ref_uris(ontology_repo, class_id):
    return sorted(ref.uri for ref in ontology_repo.get_class(class_id).external_references)


class TestGroundingApplyRevert:
    def test_apply_records_change_event_and_revert_restores_references(
        self, client, pipeline_repo, ontology_repo
    ):
        new_uri = "https://dbpedia.org/resource/Service"
        run_id = _completed_run(
            pipeline_repo,
            PipelineType.SCHEMA_NODE_GROUNDING,
            {
                "groundings": [
                    {"uri": new_uri, "source": "dbpedia", "confidence": 0.9},
                    {"uri": EXISTING_REF_URI, "source": "wikidata", "confidence": 0.9},
                ]
            },
        )

        applied = client.post(f"/api/pipelines/runs/{run_id}/apply", params={"node_id": SERVICE_ID})
        assert applied.status_code == status.HTTP_200_OK, applied.text
        assert applied.json()["external_references_created"] == 1
        assert _ref_uris(ontology_repo, SERVICE_ID) == sorted([EXISTING_REF_URI, new_uri])

        events = _change_events(client, run_id)
        assert [(e["entity_id"], e["operation"]) for e in events] == [(SERVICE_ID, "update")]

        reverted = _revert(client, run_id)
        assert reverted["events_reverted"] == 1
        restored = ontology_repo.get_class(SERVICE_ID)
        assert _ref_uris(ontology_repo, SERVICE_ID) == [EXISTING_REF_URI]
        assert restored.external_references[0].source == "wikidata"
        assert restored.description == ORIGINAL_DEFINITION


class TestDefinitionRefinementApplyRevert:
    def test_apply_records_change_event_and_revert_restores_definition(
        self, client, pipeline_repo, ontology_repo
    ):
        run_id = _completed_run(
            pipeline_repo,
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            {
                "node_id": SERVICE_ID,
                "candidates": [
                    {"definition": "A refined definition.", "confidence": 0.9},
                    {"definition": "A weaker definition.", "confidence": 0.5},
                ],
            },
        )

        applied = client.post(f"/api/pipelines/runs/{run_id}/apply")
        assert applied.status_code == status.HTTP_200_OK, applied.text
        assert applied.json()["classes_updated"] == 1
        assert ontology_repo.get_class(SERVICE_ID).description == "A refined definition."

        events = _change_events(client, run_id)
        assert [(e["entity_id"], e["operation"]) for e in events] == [(SERVICE_ID, "update")]

        reverted = _revert(client, run_id)
        assert reverted["events_reverted"] == 1
        assert ontology_repo.get_class(SERVICE_ID).description == ORIGINAL_DEFINITION


class TestConnectionRefinementApplyRevert:
    def test_apply_records_change_events_and_revert_restores_relationships(
        self, client, pipeline_repo, ontology_repo
    ):
        run_id = _completed_run(
            pipeline_repo,
            PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            {
                "scope_id": SERVICE_ID,
                "deltas": [
                    {
                        "operation": "add",
                        "subject": "Service",
                        "predicate": "uses",
                        "object": "Database",
                        "confidence": 0.9,
                    },
                    {
                        "operation": "remove",
                        "subject": "Service",
                        "predicate": "uses",
                        "object": "Queue",
                        "confidence": 0.9,
                    },
                ],
            },
        )

        def triples():
            return sorted(
                (r.source_id, r.property_definition_id, r.target_id)
                for r in ontology_repo.list_relationships(limit=None)
            )

        before = triples()
        assert before == [(SERVICE_ID, USES_ID, QUEUE_ID)]

        applied = client.post(f"/api/pipelines/runs/{run_id}/apply")
        assert applied.status_code == status.HTTP_200_OK, applied.text
        body = applied.json()
        assert body["relationships_created"] == 1
        assert body["relationships_removed"] == 1
        assert triples() == [(SERVICE_ID, USES_ID, DATABASE_ID)]

        events = _change_events(client, run_id)
        assert sorted(e["operation"] for e in events) == ["create", "delete"]
        assert EXISTING_REL_ID in {e["entity_id"] for e in events}

        reverted = _revert(client, run_id)
        assert reverted["events_reverted"] == 2
        assert reverted["relationships_deleted"] == 1
        assert triples() == before
        # The removed relationship is restored under its original id.
        assert ontology_repo.get_relationship(EXISTING_REL_ID) is not None

        # Revert is idempotent.
        assert _revert(client, run_id)["events_reverted"] == 0
        assert triples() == before
