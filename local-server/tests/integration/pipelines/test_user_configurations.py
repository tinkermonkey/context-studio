"""
Integration tests: user-created configurations and the runs that use them.

A user-created configuration need not set a temperature or an output-token
limit: what it leaves unset is the implementation's default configuration's,
never a form default. A run executes with the parameters it was accepted
with, across an edit of its configuration and a restart of the server. A
deleted configuration starts no new run and is not offered as one that can.
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
from adapters.persistence.sqlite.operations.models import OperationsBase
from adapters.persistence.sqlite.pipeline_config_repo import (
    PipelineConfigurationRepository,
    load_user_configurations,
)
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor
from adapters.web.pipelines_routes import config_router, router
from domain.pipelines.bootstrap import register_pipelines
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)

EXTRACTION = PipelineType.INDIVIDUAL_EXTRACTION
CONFIGURATIONS = "/api/pipelines/types/individual_extraction/implementations/default/configurations"
RUN = "/api/pipelines/individual_extraction/run"
# The configurations here are of the two-pass implementation, whose id is "default"
# (a name: individual extraction's default implementation is find-then-type)
BODY = {
    "text": "Ada Lovelace wrote the first program.",
    "ontology_id": "tax-1",
    "implementation_id": "default",
}
# What extraction-default, that implementation's default configuration, sets
DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS = 0.0, 20000
# Why a run queued with an earlier version of a stored configuration fails
CHANGED = (
    "The configuration {ref!r} of individual_extraction:default was changed or deleted after"
    " this run was queued: version 1, which the run was accepted with, no longer exists, so"
    " the run cannot execute as it was accepted. Submit the run again."
)


class RecordingExtraction:
    """Stands in for the extraction service: records what each call was asked to use."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def extract_triples(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            triples=[],
            warnings=[],
            metadata={"model": kwargs["model"], "tokens_used": 0, "duration_ms": 1},
            failure_reason=None,
            incomplete_response=False,
            provider_failed=False,
            provider_refused=False,
        )

    def parameters(self) -> list[tuple]:
        """(model, temperature, output limit) of each call made."""
        return [(c["model"], c["temperature"], c["max_tokens"]) for c in self.calls]


@pytest.fixture()
def databases(tmp_path):
    """Session factories over a local and an operations database that outlive a 'restart'."""
    local = create_engine(f"sqlite:///{tmp_path / 'local.db'}")
    operations = create_engine(f"sqlite:///{tmp_path / 'operations.db'}")
    Base.metadata.create_all(local)
    OperationsBase.metadata.create_all(operations)
    yield SimpleNamespace(local=sessionmaker(bind=local), operations=sessionmaker(bind=operations))
    local.dispose()
    operations.dispose()


@pytest.fixture()
def extraction():
    return RecordingExtraction()


@pytest.fixture()
def server(databases, extraction):
    """Starts a server over the databases; calling it again is a restart."""
    executors = []

    def start() -> TestClient:
        for executor in executors:
            executor.stop()
        implementations = PipelineImplementationRegistry()
        configurations = PipelineConfigurationRegistry()
        register_pipelines(implementations, configurations)
        config_repo = PipelineConfigurationRepository(databases.operations)
        # As app.py does at startup: stored user configurations join the registry
        load_user_configurations(config_repo, configurations)
        app = FastAPI()
        app.include_router(router)
        app.include_router(config_router)
        app.state.pipeline_run_repo = PipelineRepository(session_factory=databases.local)
        app.state.batch_repo = BatchRepository(session_factory=databases.local)
        app.state.pipeline_config_repo = config_repo
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
        executors.append(app.state.run_executor)
        return TestClient(app)

    yield start
    for executor in executors:
        executor.stop()


def create(client, **fields) -> dict:
    response = client.post(
        CONFIGURATIONS,
        json={"name": "Mine", "provider": "anthropic", "model": "my-model", **fields},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def update(client, configuration: dict, **fields) -> dict:
    body = {
        "name": configuration["name"],
        "provider": configuration["provider"],
        "model": configuration["model"],
        # What it sets, sent back as it came: an unset value stays unset
        "parameters": configuration["parameter_settings"],
        "enabled": True,
        **fields,
    }
    response = client.put(f"/api/pipeline_configurations/{configuration['id']}", json=body)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def finished(client, run_id, timeout=10.0):
    """The run, once a background worker has brought it to an end."""
    runs = client.app.state.pipeline_run_repo
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = runs.get(run_id)
        if run.status not in (PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING):
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


class TestUnsetParameters:
    def test_what_a_configuration_leaves_unset_is_the_implementations_default(
        self, server, extraction, databases
    ):
        client = server()

        configuration = create(client)

        # Nothing was stored for it: no form default stands in
        (record,) = PipelineConfigurationRepository(databases.operations).list_all()
        assert (record.temperature, record.max_tokens) == (None, None)
        # The listing shows what its runs will use
        assert configuration["parameters"]["temperature"] == DEFAULT_TEMPERATURE
        assert configuration["parameters"]["max_tokens"] == DEFAULT_MAX_TOKENS

        response = client.post(RUN, json={**BODY, "configuration_ref": configuration["config_ref"]})

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert extraction.parameters() == [("my-model", DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS)]

    def test_what_it_sets_is_used(self, server, extraction):
        client = server()
        configuration = create(client, parameters={"temperature": 0.3, "max_tokens": 12000})

        client.post(RUN, json={**BODY, "configuration_ref": configuration["config_ref"]})

        assert configuration["parameters"] == {
            "temperature": 0.3,
            "max_tokens": 12000,
            "top_p": 0.9,
        }
        assert extraction.parameters() == [("my-model", 0.3, 12000)]

    def test_one_unset_parameter_is_inherited_on_its_own(self, server, extraction):
        client = server()
        configuration = create(client, parameters={"temperature": 0.5})

        client.post(RUN, json={**BODY, "configuration_ref": configuration["config_ref"]})

        assert extraction.parameters() == [("my-model", 0.5, DEFAULT_MAX_TOKENS)]

    def test_a_row_stored_with_the_old_form_defaults_keeps_them(
        self, server, extraction, databases
    ):
        # Before this change a row always held a temperature and a limit (0.4 and
        # 800 unless the form said otherwise); such a row still means what it says
        PipelineConfigurationRepository(databases.operations).create(
            pipeline_type=EXTRACTION.value,
            implementation_id="default",
            name="Old",
            provider="anthropic",
            model="old-model",
            temperature=0.4,
            max_tokens=800,
        )
        client = server()

        client.post(RUN, json={**BODY, "configuration_ref": "cfg_old"})

        assert extraction.parameters() == [("old-model", 0.4, 800)]

    @pytest.mark.parametrize("max_tokens", [20001, 64000])
    def test_a_limit_no_provider_can_send_is_refused(self, server, max_tokens):
        # The Anthropic client refuses a request that does not stream above ~21,000
        response = server().post(
            CONFIGURATIONS,
            json={
                "name": "Too much",
                "provider": "anthropic",
                "model": "m",
                "parameters": {"max_tokens": max_tokens},
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_the_system_configurations_fit_the_limit(self, server):
        listed = server().get(CONFIGURATIONS)

        assert listed.status_code == status.HTTP_200_OK, listed.text
        assert max(c["parameters"]["max_tokens"] for c in listed.json()) == 20000


class TestParameterSettings:
    """A response says what a configuration sets, beside what is in effect."""

    def test_an_unset_value_is_null_in_the_settings_and_a_number_in_effect(self, server):
        configuration = create(server(), parameters={"temperature": 0.5})

        assert configuration["parameter_settings"] == {
            "temperature": 0.5,
            "max_tokens": None,
            "top_p": 0.9,
        }
        assert configuration["parameters"] == {
            "temperature": 0.5,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "top_p": 0.9,
        }

    def test_saving_the_settings_back_keeps_an_inherited_value_inherited(
        self, server, extraction, databases
    ):
        client = server()
        configuration = create(client)

        # As an editor that saves one field at a time does: rename, settings as they came
        renamed = update(client, configuration, name="Renamed")

        (record,) = PipelineConfigurationRepository(databases.operations).list_all()
        assert (record.name, record.temperature, record.max_tokens) == ("Renamed", None, None)
        assert renamed["parameter_settings"] == configuration["parameter_settings"]
        assert renamed["parameters"]["max_tokens"] == DEFAULT_MAX_TOKENS

    def test_saving_the_values_in_effect_sets_them(self, server, databases):
        client = server()
        configuration = create(client)

        saved = update(client, configuration, parameters=configuration["parameters"])

        (record,) = PipelineConfigurationRepository(databases.operations).list_all()
        assert (record.temperature, record.max_tokens) == (DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS)
        assert saved["parameter_settings"]["max_tokens"] == DEFAULT_MAX_TOKENS

    def test_an_update_that_names_no_parameters_leaves_them_unset(self, server, databases):
        client = server()
        configuration = create(client, parameters={"temperature": 0.3, "max_tokens": 12000})

        response = client.put(
            f"/api/pipeline_configurations/{configuration['id']}",
            json={"name": "Mine", "provider": "anthropic", "model": "my-model", "enabled": True},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["parameter_settings"] == {
            "temperature": None,
            "max_tokens": None,
            "top_p": 0.9,
        }

    def test_a_system_configuration_shows_what_it_sets(self, server):
        listed = {c["config_ref"]: c for c in server().get(CONFIGURATIONS).json()}

        default = listed["extraction-default"]
        assert default["parameter_settings"] == default["parameters"]
        assert default["parameters"]["max_tokens"] == DEFAULT_MAX_TOKENS

    def test_a_type_whose_runs_take_no_parameters_shows_none(self, server):
        client = server()
        triage = "/api/pipelines/types/claim_triage/implementations/default/configurations"

        created = client.post(
            triage, json={"name": "Mine", "provider": "anthropic", "model": "unused"}
        )
        listed = client.get(triage).json()

        assert created.status_code == status.HTTP_201_CREATED, created.text
        # Claim triage asks a decision model: its configurations set no temperature or limit
        assert [(c["parameters"], c["parameter_settings"]) for c in listed] == [(None, None)] * 2


class TestAcrossAnEditAndARestart:
    def test_a_queued_run_is_stored_with_the_parameters_it_was_submitted_with(
        self, server, extraction
    ):
        client = server()
        configuration = create(client, model="first-model")
        pending = client.post(
            RUN, json={**BODY, "configuration_ref": configuration["config_ref"], "async": True}
        ).json()
        client.app.state.run_executor.start()

        run = finished(client, pending["id"])
        assert run.status == PipelineRunStatus.COMPLETED, run.failure_reason
        assert extraction.parameters() == [("first-model", DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS)]
        assert run.llm_metadata["model"] == "first-model"

    @pytest.mark.parametrize("restart", [False, True], ids=["no restart", "restart"])
    def test_a_run_queued_before_its_configuration_was_edited_fails_saying_so(
        self, server, extraction, restart
    ):
        client = server()
        configuration = create(client, model="first-model")
        pending = client.post(
            RUN, json={**BODY, "configuration_ref": configuration["config_ref"], "async": True}
        ).json()

        # Edited while the run waits; only the latest content of a stored
        # configuration is kept, so the version the run was accepted with is gone
        update(client, configuration, model="edited-model")
        if restart:
            client = server()
        client.app.state.run_executor.start()

        run = finished(client, pending["id"])
        assert run.status == PipelineRunStatus.FAILED
        assert run.failure_reason == CHANGED.format(ref=configuration["config_ref"])
        # It did not run with the edited configuration instead
        assert extraction.calls == []

    @pytest.mark.parametrize("restart", [False, True], ids=["no restart", "restart"])
    def test_a_run_queued_before_its_configuration_was_deleted_fails_saying_so(
        self, server, extraction, restart
    ):
        client = server()
        configuration = create(client)
        pending = client.post(
            RUN, json={**BODY, "configuration_ref": configuration["config_ref"], "async": True}
        ).json()

        client.delete(f"/api/pipeline_configurations/{configuration['id']}")
        if restart:
            client = server()
        client.app.state.run_executor.start()

        run = finished(client, pending["id"])
        assert run.status == PipelineRunStatus.FAILED
        assert run.failure_reason == CHANGED.format(ref=configuration["config_ref"])
        assert extraction.calls == []

    def test_a_run_pinned_to_the_latest_version_runs_after_a_restart(self, server, extraction):
        client = server()
        configuration = create(client, model="first-model")
        configuration = update(client, configuration, model="second-model")
        configuration = update(client, configuration, model="third-model")
        pending = client.post(
            RUN, json={**BODY, "configuration_ref": configuration["config_ref"], "async": True}
        ).json()
        stored = client.app.state.pipeline_run_repo.get(pending["id"])
        assert stored.configuration_version == configuration["version"] == 3

        client = server()  # restart: the registry is rebuilt from code and the stored rows
        client.app.state.run_executor.start()

        run = finished(client, pending["id"])
        assert run.status == PipelineRunStatus.COMPLETED, run.failure_reason
        assert extraction.parameters() == [("third-model", DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS)]

    def test_a_restart_registers_a_configuration_under_its_stored_version(self, server):
        client = server()
        configuration = update(client, create(client), model="second-model")

        registry = server().app.state.config_registry

        latest = registry.get_latest(EXTRACTION, "default", configuration["config_ref"])
        assert (latest.version, latest.config["model"]) == (2, "second-model")
        assert registry.get_version(EXTRACTION, "default", configuration["config_ref"], 1) is None


class TestDeletedConfiguration:
    def test_no_run_can_start_with_it_and_it_is_not_offered(self, server, extraction):
        client = server()
        configuration = create(client)
        assert (
            client.delete(f"/api/pipeline_configurations/{configuration['id']}").status_code == 204
        )

        named = client.post(RUN, json={**BODY, "configuration_ref": configuration["config_ref"]})
        other = client.post(RUN, json={**BODY, "configuration_ref": "no-such"})

        assert named.status_code == status.HTTP_404_NOT_FOUND
        assert named.json()["detail"] == (
            f"'{configuration['config_ref']}' is not a configuration of the 'default'"
            " implementation of individual_extraction"
            " (one of: extraction-default, extraction-openrouter-default)"
        )
        assert configuration["config_ref"] not in other.json()["detail"]
        assert extraction.calls == []


class TestListingStoredValues:
    """A listing shows stored values as they are; it is a run that is refused."""

    def test_a_stored_limit_above_the_bound_is_listed_not_an_error(
        self, server, databases, extraction
    ):
        # Only a row written under an earlier bound, or by hand, can hold one
        PipelineConfigurationRepository(databases.operations).create(
            pipeline_type=EXTRACTION.value,
            implementation_id="default",
            name="Too much",
            provider="anthropic",
            model="m",
            max_tokens=64000,
        )
        client = server()

        listed = client.get(CONFIGURATIONS)
        run = client.post(RUN, json={**BODY, "configuration_ref": "cfg_too_much"})

        assert listed.status_code == status.HTTP_200_OK, listed.text
        stored = next(c for c in listed.json() if c["config_ref"] == "cfg_too_much")
        assert stored["parameters"]["max_tokens"] == 64000
        assert stored["parameter_settings"]["max_tokens"] == 64000
        assert client.get(f"/api/pipeline_configurations/{stored['id']}").status_code == 200
        # The run, not the listing, is what the bound refuses
        assert run.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "The 'cfg_too_much' configuration sets max_tokens 64000" in run.json()["detail"]
        assert extraction.calls == []

    def test_a_value_nothing_sets_is_null_not_a_placeholder(self, server):
        client = server()
        # An implementation whose default configuration sets a temperature and no limit
        client.app.state.implementation_registry.register_impl(EXTRACTION, "probe", object)
        client.app.state.config_registry.register(
            EXTRACTION, "probe", "probe-default", {"model": "m", "temperature": 0.2}, default=True
        )
        client.app.state.config_registry.register(
            EXTRACTION, "probe", "probe-other", {"model": "n"}
        )

        listed = client.get(
            "/api/pipelines/types/individual_extraction/implementations/probe/configurations"
        )

        assert listed.status_code == status.HTTP_200_OK, listed.text
        shown = {c["config_ref"]: (c["parameters"], c["parameter_settings"]) for c in listed.json()}
        assert shown == {
            # No limit is set anywhere: the run is given none, and none is shown
            "probe-default": (
                {"temperature": 0.2, "max_tokens": None, "top_p": 0.9},
                {"temperature": 0.2, "max_tokens": None, "top_p": 0.9},
            ),
            # It sets neither: its temperature in effect is the default configuration's
            "probe-other": (
                {"temperature": 0.2, "max_tokens": None, "top_p": 0.9},
                {"temperature": None, "max_tokens": None, "top_p": 0.9},
            ),
        }
