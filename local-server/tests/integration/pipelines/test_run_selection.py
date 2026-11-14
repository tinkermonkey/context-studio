"""
Integration tests: every entry point that starts a run selects it the same way
(domain/pipelines/selection.py).

The run API (synchronous and background), the batch route, the run_refinement
tool and scripts/run_pipeline.py: an implementation left out is the type's
default, a configuration left out is the implementation's default, what cannot
be selected is refused naming what can, and the run executes with its
configuration's model, temperature and output-token limit unless its input
names its own.
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

from adapters.chat.run_tools import RunRefinementTool
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor
from adapters.web.pipelines_routes import router
from domain.pipelines.bootstrap import register_pipelines
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import PipelineExecutionError
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.requested_via import RequestedVia
from scripts import run_pipeline

EXTRACTION = PipelineType.INDIVIDUAL_EXTRACTION
RUN = "/api/pipelines/individual_extraction/run"
BODY = {"text": "Ada Lovelace wrote the first program.", "ontology_id": "tax-1"}
# Individual extraction's default implementation is find-then-type; what its
# default configuration (extraction-find-then-type) sets
DEFAULT_PARAMETERS = {"model": "claude-haiku-5-5", "temperature": 0.0, "max_tokens": 16000}
# The two-pass implementation is registered under the id "default": a name, not
# the type's default. What its default configuration (extraction-default) sets
TWO_PASS = {"implementation_id": "default"}
TWO_PASS_PARAMETERS = {"model": "claude-haiku-5-5", "temperature": 0.0, "max_tokens": 20000}


class RecordingExtraction:
    """
    Stands in for the extraction service: records what each call was asked to
    use. It finds nothing in any text, by either implementation's calls.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        # Which of the service's calls were made: extract_triples is two-pass's,
        # find_mentions find-then-type's
        self.made: list[str] = []

    def _nothing(self, call: str, kwargs: dict, **result):
        self.made.append(call)
        self.calls.append(kwargs)
        return SimpleNamespace(
            warnings=[],
            metadata={"model": kwargs["model"], "tokens_used": 0, "duration_ms": 1},
            failure_reason=None,
            incomplete_response=False,
            provider_failed=False,
            provider_refused=False,
            **result,
        )

    def extract_triples(self, **kwargs):
        return self._nothing("extract_triples", kwargs, triples=[])

    def find_mentions(self, **kwargs):
        return self._nothing("find_mentions", kwargs, mentions=[])

    def recognize(self, triples, ontology_id, dataset_id=None):
        return triples

    def parameters(self) -> dict:
        """The model, temperature and output limit of the one call made."""
        (call,) = self.calls
        return {key: call[key] for key in ("model", "temperature", "max_tokens")}


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def registries():
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_pipelines(implementations, configurations)
    return implementations, configurations


@pytest.fixture()
def extraction():
    return RecordingExtraction()


@pytest.fixture()
def app(session_factory, registries, extraction):
    implementations, configurations = registries
    app = FastAPI()
    app.include_router(router)
    app.state.pipeline_run_repo = PipelineRepository(session_factory=session_factory)
    app.state.batch_repo = BatchRepository(session_factory=session_factory)
    app.state.implementation_registry = implementations
    app.state.config_registry = configurations
    app.state.llm_router = MagicMock()
    app.state.ontology_repo = MagicMock()
    app.state.ontology_repo.get_taxonomy.return_value = None
    app.state.extraction_service = extraction
    app.state.run_executor = BackgroundRunExecutor(
        runs=app.state.pipeline_run_repo,
        batches=app.state.batch_repo,
        implementations=implementations,
        configurations=configurations,
        llm_provider=app.state.llm_router,
        app_state=app.state,
        poll_seconds=0.02,
    )
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


class TestRunApi:
    def test_nothing_named_runs_find_then_type_with_its_configurations_model(
        self, client, extraction
    ):
        # No implementation, no configuration and no model in the body
        response = client.post(RUN, json=BODY)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        run = response.json()
        assert run["implementation_id"] == "find_then_type"
        assert run["configuration_ref"] == "extraction-find-then-type"
        assert run["status"] == "completed"
        assert extraction.made == ["find_mentions"]
        assert extraction.parameters() == DEFAULT_PARAMETERS
        # The run records the model it used
        assert run["llm_metadata"]["model"] == DEFAULT_PARAMETERS["model"]

    def test_the_implementation_named_default_is_two_pass_and_still_runs(self, client, extraction):
        # "default" is the two-pass implementation's id, no longer the type's default
        response = client.post(RUN, json={**BODY, **TWO_PASS})

        assert response.status_code == status.HTTP_201_CREATED, response.text
        run = response.json()
        assert run["implementation_id"] == "default"
        assert run["configuration_ref"] == "extraction-default"
        assert extraction.made == ["extract_triples"]
        assert extraction.parameters() == TWO_PASS_PARAMETERS
        # Each extraction records the configuration it ran with
        assert extraction.calls[0]["configuration_ref"] == "extraction-default"

    def test_a_named_configuration_supplies_the_runs_parameters(self, client, extraction):
        response = client.post(
            RUN, json={**BODY, **TWO_PASS, "configuration_ref": "extraction-openrouter-default"}
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert response.json()["configuration_ref"] == "extraction-openrouter-default"
        assert extraction.parameters() == {
            "model": "google/gemini-3-flash-preview",
            "temperature": 0.0,
            "max_tokens": 8000,
        }

    def test_a_model_in_the_body_overrides_the_configurations(self, client, extraction):
        response = client.post(RUN, json={**BODY, "model": "another-model", "temperature": 0.3})

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert extraction.parameters() == {
            "model": "another-model",
            "temperature": 0.3,
            "max_tokens": DEFAULT_PARAMETERS["max_tokens"],
        }

    @pytest.mark.parametrize("run_async", [False, True])
    def test_a_configuration_of_another_implementation_is_refused(
        self, client, app, extraction, run_async
    ):
        response = client.post(
            RUN,
            json={
                **BODY,
                "implementation_id": "find_then_type",
                "configuration_ref": "extraction-default",
                "async": run_async,
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == (
            "'extraction-default' is a configuration of the default implementation, not of the"
            " 'find_then_type' implementation of individual_extraction"
            " (one of: extraction-find-then-type)"
        )
        assert app.state.pipeline_run_repo.list() == []
        assert extraction.calls == []

    @pytest.mark.parametrize("run_async", [False, True])
    def test_an_unknown_implementation_is_refused_naming_the_registered_ones(
        self, client, run_async
    ):
        response = client.post(
            RUN, json={**BODY, "implementation_id": "no_such", "async": run_async}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == (
            "'no_such' is not an implementation of individual_extraction"
            " (one of: default, find_then_type, open_v1)"
        )

    @pytest.mark.parametrize("run_async", [False, True])
    def test_a_disabled_configuration_starts_no_run(
        self, client, app, registries, extraction, run_async
    ):
        _, configurations = registries
        configurations.register(
            EXTRACTION, "default", "switched-off", {"model": "m", "enabled": False}
        )

        response = client.post(
            RUN,
            json={**BODY, **TWO_PASS, "configuration_ref": "switched-off", "async": run_async},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "'switched-off' configuration" in response.json()["detail"]
        assert "is disabled" in response.json()["detail"]
        assert app.state.pipeline_run_repo.list() == []
        assert extraction.calls == []

    @pytest.mark.parametrize("run_async", [False, True])
    def test_a_disabled_default_is_not_used_for_a_run_that_names_nothing(
        self, client, app, registries, extraction, run_async
    ):
        _, configurations = registries
        configurations.register(
            EXTRACTION,
            "default",
            "extraction-default",
            {"model": "m", "enabled": False},
            default=True,
        )

        response = client.post(RUN, json={**BODY, **TWO_PASS, "async": run_async})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["detail"] == (
            "No configuration was named and the default one, 'extraction-default', of the"
            " 'default' implementation of individual_extraction is disabled"
            " (enabled: extraction-openrouter-default)"
        )
        assert app.state.pipeline_run_repo.list() == []
        assert extraction.calls == []

    def test_a_background_run_executes_with_its_configurations_model(self, client, app, extraction):
        app.state.run_executor.start()

        response = client.post(RUN, json={**BODY, "async": True})

        assert response.status_code == status.HTTP_202_ACCEPTED, response.text
        pending = response.json()
        assert pending["implementation_id"] == "find_then_type"
        assert pending["configuration_ref"] == "extraction-find-then-type"
        run = finished(app, pending["id"])
        assert run.status == PipelineRunStatus.COMPLETED, run.failure_reason
        assert extraction.made == ["find_mentions"]
        assert extraction.parameters() == DEFAULT_PARAMETERS

    @pytest.mark.parametrize("run_async", [False, True])
    def test_a_limit_in_the_body_above_what_a_provider_can_send_is_refused(
        self, client, app, extraction, run_async
    ):
        # The Anthropic client refuses a request that does not stream above ~21,000
        response = client.post(RUN, json={**BODY, "max_tokens": 30000, "async": run_async})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["detail"] == (
            "The run's input names max_tokens 30000: the output-token limit of a run is a"
            " whole number from 1 to 20000, the most every provider can be asked for in one"
            " request"
        )
        assert app.state.pipeline_run_repo.list() == []
        assert extraction.calls == []

    def test_a_limit_in_the_body_within_the_bound_is_the_runs(self, client, extraction):
        response = client.post(RUN, json={**BODY, "max_tokens": 20000})

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert extraction.parameters()["max_tokens"] == 20000

    @pytest.mark.parametrize("run_async", [False, True])
    def test_a_configuration_whose_stored_limit_is_above_the_bound_starts_no_run(
        self, client, app, registries, extraction, run_async
    ):
        # Only a row written under an earlier bound, or by hand, can hold one
        _, configurations = registries
        configurations.register(
            EXTRACTION, "default", "too-much", {"model": "m", "max_tokens": 64000}
        )

        response = client.post(
            RUN, json={**BODY, **TWO_PASS, "configuration_ref": "too-much", "async": run_async}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["detail"] == (
            "The 'too-much' configuration sets max_tokens 64000: the output-token limit of a"
            " run is a whole number from 1 to 20000, the most every provider can be asked for"
            " in one request; edit the configuration, or name a limit in the run's input"
        )
        assert app.state.pipeline_run_repo.list() == []
        assert extraction.calls == []

    def test_a_limit_named_in_the_body_lets_such_a_configuration_run(
        self, client, registries, extraction
    ):
        _, configurations = registries
        configurations.register(
            EXTRACTION, "default", "too-much", {"model": "m", "max_tokens": 64000}
        )

        response = client.post(
            RUN, json={**BODY, **TWO_PASS, "configuration_ref": "too-much", "max_tokens": 9000}
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert extraction.parameters()["max_tokens"] == 9000

    @pytest.mark.parametrize(
        "pipeline_type",
        [t for t in PipelineType if t is not PipelineType.NO_OP],
        ids=lambda t: t.value,
    )
    def test_every_registered_type_accepts_a_run_that_names_nothing(
        self, client, app, registries, pipeline_type
    ):
        implementations, configurations = registries

        # Workers are not started: the run is accepted and stays pending
        response = client.post(f"/api/pipelines/{pipeline_type.value}/run", json={"async": True})

        assert response.status_code == status.HTTP_202_ACCEPTED, response.text
        run = response.json()
        assert run["implementation_id"] == implementations.default_implementation(pipeline_type)
        assert run["configuration_ref"] == configurations.default_configuration(
            pipeline_type, run["implementation_id"]
        )

    def test_a_type_with_no_implementation_has_nothing_to_run(self, client):
        response = client.post("/api/pipelines/no_op/run", json={})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "no_op has no default implementation and none to run"


class TestBatchRoute:
    @pytest.fixture()
    def batch_id(self, client):
        response = client.post("/api/pipelines/batches", json={})
        assert response.status_code == status.HTTP_201_CREATED, response.text
        return response.json()["id"]

    def test_a_run_that_names_nothing_gets_the_defaults_and_their_model(
        self, client, app, extraction, batch_id
    ):
        app.state.run_executor.start()

        response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={"runs": [{"pipeline_type": "individual_extraction", "input_data": BODY}]},
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        (run_id,) = response.json()["run_ids"]
        run = finished(app, run_id)
        assert run.status == PipelineRunStatus.COMPLETED, run.failure_reason
        assert (run.implementation_id, run.configuration_ref) == (
            "find_then_type",
            "extraction-find-then-type",
        )
        assert extraction.parameters() == DEFAULT_PARAMETERS

    def test_a_run_is_stored_with_the_version_and_parameters_it_was_accepted_with(
        self, client, app, registries, batch_id
    ):
        # A second version of two-pass's default configuration: the run is pinned
        # to it, and stored with its parameters, when it is enqueued
        _, configurations = registries
        configurations.register(
            EXTRACTION,
            "default",
            "extraction-default",
            {"model": "second-model", "temperature": 0.2, "max_tokens": 1234},
            default=True,
        )

        response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [{"pipeline_type": "individual_extraction", **TWO_PASS, "input_data": BODY}]
            },
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        # The workers are not started: the run waits as it was stored
        stored, stored_input = app.state.pipeline_run_repo.claim_next_pending()
        assert stored.id == response.json()["run_ids"][0]
        assert (stored.configuration_slug, stored.configuration_version) == (
            "extraction-default",
            2,
        )
        assert {key: stored_input[key] for key in ("model", "temperature", "max_tokens")} == {
            "model": "second-model",
            "temperature": 0.2,
            "max_tokens": 1234,
        }

    def test_a_limit_above_what_a_provider_can_send_is_refused(self, client, app, batch_id):
        response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "individual_extraction",
                        "input_data": {**BODY, "max_tokens": 30000},
                    }
                ]
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "from 1 to 20000" in response.json()["detail"]
        assert app.state.pipeline_run_repo.list() == []

    def test_a_configuration_of_another_implementation_is_refused(self, client, app, batch_id):
        response = client.post(
            f"/api/pipelines/batches/{batch_id}/runs",
            json={
                "runs": [
                    {
                        "pipeline_type": "schema_extraction",
                        "implementation_id": "open_v1",
                        "configuration_ref": "schema-extraction-default",
                    }
                ]
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "is a configuration of the default implementation" in response.json()["detail"]
        assert app.state.pipeline_run_repo.list() == []


class TestRunRefinementTool:
    @pytest.fixture()
    def tool(self, app):
        ontology = SimpleNamespace(get_taxonomy=lambda taxonomy_id: SimpleNamespace(title="DR"))
        return RunRefinementTool(app.state.run_executor, ontology, RequestedVia.MCP)

    def test_it_offers_the_pipelines_that_have_an_implementation(self, tool):
        offered = tool.input_schema["properties"]["pipeline"]["enum"]

        # no_op is a pipeline type with nothing registered to run
        assert "no_op" not in offered
        assert set(offered) == {t.value for t in PipelineType} - {"no_op"}

    def test_a_pipeline_with_nothing_to_run_is_a_bad_argument(self, tool):
        outcome = tool._run_safely({"taxonomy_id": "tax-1", "pipeline": "no_op"})

        assert outcome.is_error
        assert "'pipeline' must be one of" in outcome.content

    @pytest.mark.parametrize(
        "pipeline, configuration",
        [
            ("schema_node_definition_refinement", "definition-refinement-default"),
            ("schema_node_connection_refinement", "connection-refinement-default"),
            ("schema_node_grounding", "grounding-default"),
            ("schema_extraction", "schema-extraction-default"),
            ("claim_triage", "default"),
        ],
    )
    def test_a_pass_that_names_nothing_runs_the_registered_defaults(
        self, tool, app, pipeline, configuration
    ):
        outcome = tool._run_safely({"taxonomy_id": "tax-1", "pipeline": pipeline})

        assert not outcome.is_error, outcome.content
        (run,) = app.state.pipeline_run_repo.list()
        assert run.implementation_id == "default"
        assert run.configuration_ref == configuration

    def test_a_configuration_of_another_implementation_is_refused(self, tool, app):
        outcome = tool._run_safely(
            {
                "taxonomy_id": "tax-1",
                "pipeline": "schema_extraction",
                "options": {
                    "implementation_id": "open_v1",
                    "configuration_ref": "schema-extraction-default",
                },
            }
        )

        assert outcome.is_error
        assert "is a configuration of the default implementation" in outcome.content
        assert app.state.pipeline_run_repo.list() == []


class TestRunPipelineScript:
    @staticmethod
    def _dry_run(monkeypatch, tmp_path, *selection) -> int:
        input_path = tmp_path / "input.json"
        input_path.write_text("{}")
        monkeypatch.setattr(
            sys, "argv", ["run_pipeline.py", "--input", str(input_path), "--dry-run", *selection]
        )
        return run_pipeline.main()

    @pytest.mark.parametrize(
        "pipeline_type",
        [t.value for t in PipelineType if t is not PipelineType.NO_OP],
    )
    def test_every_registered_type_is_selected_with_nothing_named(
        self, monkeypatch, tmp_path, pipeline_type
    ):
        assert self._dry_run(monkeypatch, tmp_path, "--type", pipeline_type) == 0

    def test_a_named_implementation_and_configuration_are_selected(self, monkeypatch, tmp_path):
        assert (
            self._dry_run(
                monkeypatch,
                tmp_path,
                "--type",
                "individual_extraction",
                "--implementation",
                "find_then_type",
                "--configuration",
                "extraction-find-then-type",
            )
            == 0
        )

    def test_a_configuration_of_another_implementation_is_refused(self, monkeypatch, tmp_path):
        assert (
            self._dry_run(
                monkeypatch,
                tmp_path,
                "--type",
                "individual_extraction",
                "--implementation",
                "find_then_type",
                "--configuration",
                "extraction-default",
            )
            == 1
        )


class _FailingOrchestrator:
    """Fails as an orchestrator that reports nothing about its model calls does."""

    async def execute(self, state):
        raise PipelineExecutionError("The model's answer could not be used")


class TestFailedRunRecordsItsModel:
    """A failed run says which model it was given, as a completed one does."""

    @pytest.fixture(autouse=True)
    def failing(self, monkeypatch):
        monkeypatch.setattr(
            "adapters.factories.orchestrator_factory.create_orchestrator",
            lambda *args, **kwargs: _FailingOrchestrator(),
        )

    @pytest.mark.parametrize(
        "pipeline, model",
        [
            ("schema_extraction", "google/gemini-3-flash-preview"),
            ("schema_node_definition_refinement", "google/gemini-3-flash-preview"),
            ("individual_extraction", "claude-haiku-5-5"),
        ],
    )
    def test_a_synchronous_run(self, client, app, pipeline, model):
        response = client.post(f"/api/pipelines/{pipeline}/run", json={})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        (run,) = app.state.pipeline_run_repo.list()
        assert run.status == PipelineRunStatus.FAILED
        assert run.llm_metadata == {"model": model}

    def test_a_background_run(self, client, app):
        app.state.run_executor.start()

        pending = client.post("/api/pipelines/schema_extraction/run", json={"async": True}).json()

        run = finished(app, pending["id"])
        assert run.status == PipelineRunStatus.FAILED
        assert run.llm_metadata == {"model": "google/gemini-3-flash-preview"}

    def test_a_model_named_in_the_body_is_the_one_recorded(self, client, app):
        client.post("/api/pipelines/schema_extraction/run", json={"model": "named-model"})

        (run,) = app.state.pipeline_run_repo.list()
        assert run.llm_metadata == {"model": "named-model"}
