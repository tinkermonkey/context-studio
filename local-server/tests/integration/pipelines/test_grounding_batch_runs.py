"""
Integration tests: the grounding wizard enqueues one run per selected class as a
single batch through the batch route, each spec naming its node_id, node_type,
configuration_ref and sources. The background workers execute them.

A node_id names a class (a property definition's id is no class), so the run
for one fails with the reason, and the wizard offers classes only.
"""

import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor
from adapters.web.pipelines_routes import router
from domain.pipelines.bootstrap import register_pipelines
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)

CLASSES = {"class-1": "Bicycle", "class-2": "Wheel"}
SOURCES = ["DBpedia", "schema.org"]


class RecordingGroundingAdapter:
    """Stands in for the grounding adapter: records each query and finds nothing."""

    def __init__(self) -> None:
        self.queries: list[dict] = []

    async def query_sources(self, label, sources=None):
        self.queries.append({"label": label, "sources": sources})
        return []


def grounding_spec(node_id: str) -> dict:
    """One run spec as the grounding wizard sends it."""
    return {
        "pipeline_type": "schema_node_grounding",
        "configuration_ref": "grounding-default",
        "input_data": {"node_id": node_id, "node_type": "Class", "sources": SOURCES},
    }


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def grounding_adapter():
    return RecordingGroundingAdapter()


@pytest.fixture()
def app(session_factory, grounding_adapter):
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_pipelines(implementations, configurations)
    app = FastAPI()
    app.include_router(router)
    app.state.pipeline_run_repo = PipelineRepository(session_factory=session_factory)
    app.state.batch_repo = BatchRepository(session_factory=session_factory)
    app.state.implementation_registry = implementations
    app.state.config_registry = configurations
    app.state.llm_router = MagicMock()
    app.state.ontology_repo = MagicMock()
    app.state.ontology_repo.get_class.side_effect = lambda node_id: (
        SimpleNamespace(title=CLASSES[node_id]) if node_id in CLASSES else None
    )
    app.state.grounding_adapter = grounding_adapter
    app.state.grounding_scorer = MagicMock()
    app.state.run_executor = BackgroundRunExecutor(
        runs=app.state.pipeline_run_repo,
        batches=app.state.batch_repo,
        implementations=implementations,
        configurations=configurations,
        llm_provider=app.state.llm_router,
        app_state=app.state,
        poll_seconds=0.02,
    )
    app.state.run_executor.start()
    yield app
    app.state.run_executor.stop()


@pytest.fixture()
def client(app):
    return TestClient(app)


def finished(app, run_id, timeout=10.0):
    """The run, once a background worker has brought it to an end."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = app.state.pipeline_run_repo.get(run_id)
        if run.status not in (PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING):
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


def enqueue(client, specs: list[dict]) -> dict:
    batch = client.post("/api/pipelines/batches").json()
    response = client.post(f"/api/pipelines/batches/{batch['id']}/runs", json={"runs": specs})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


class TestGroundingBatch:
    def test_a_batch_of_grounding_specs_with_node_ids_runs_one_run_per_class(
        self, client, app, grounding_adapter
    ):
        enqueued = enqueue(client, [grounding_spec("class-1"), grounding_spec("class-2")])

        assert enqueued["run_count"] == 2
        runs = [finished(app, run_id) for run_id in enqueued["run_ids"]]
        for run in runs:
            assert run.status == PipelineRunStatus.COMPLETED, run.failure_reason
            assert run.batch_run_id == enqueued["batch_id"]
            assert run.implementation_id == "default"
            assert run.configuration_ref == "grounding-default"
        # Each class's title is what was grounded, from the sources the spec named
        assert sorted(q["label"] for q in grounding_adapter.queries) == ["Bicycle", "Wheel"]
        assert all(q["sources"] == SOURCES for q in grounding_adapter.queries)

    def test_a_spec_that_names_no_configuration_runs_the_registered_default(self, client, app):
        spec = grounding_spec("class-1")
        del spec["configuration_ref"]

        (run_id,) = enqueue(client, [spec])["run_ids"]

        run = finished(app, run_id)
        assert run.status == PipelineRunStatus.COMPLETED, run.failure_reason
        assert run.configuration_ref == "grounding-default"

    def test_a_node_id_that_is_no_class_fails_its_run_and_not_the_others(self, client, app):
        enqueued = enqueue(client, [grounding_spec("property-1"), grounding_spec("class-1")])

        property_run, class_run = (finished(app, run_id) for run_id in enqueued["run_ids"])
        assert property_run.status == PipelineRunStatus.FAILED
        assert "No class with id 'property-1'" in property_run.failure_reason
        assert class_run.status == PipelineRunStatus.COMPLETED, class_run.failure_reason
