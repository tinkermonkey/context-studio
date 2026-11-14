"""
Integration tests for pipeline configuration CRUD route handlers.

Tests cover create, get, update, and delete endpoints via TestClient,
verifying request validation, 404 handling, and the 503 when the repo
is not wired into app.state.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.persistence.sqlite.operations.models import OperationsBase
from adapters.persistence.sqlite.pipeline_config_repo import (
    PipelineConfigurationRepository,
)
from adapters.web.pipelines_routes import config_router, router
from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionOrchestrator
from domain.pipelines.schema_extraction.prompts import SCHEMA_EXTRACTION_STAGES

_CREATE_BODY = {
    "name": "Test Config",
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "parameters": {"temperature": 0.4, "max_tokens": 800, "top_p": 0.9},
    "enabled": True,
}


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OperationsBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def config_repo(session_factory):
    return PipelineConfigurationRepository(session_factory)


@pytest.fixture
def config_registry():
    return PipelineConfigurationRegistry()


@pytest.fixture
def impl_registry():
    reg = PipelineImplementationRegistry()
    reg.register_impl(
        __import__(
            "domain.pipelines.entities", fromlist=["PipelineType"]
        ).PipelineType.INDIVIDUAL_EXTRACTION,
        "default",
        object,  # placeholder — CRUD routes don't invoke it
    )
    reg.register_impl(
        PipelineType.SCHEMA_EXTRACTION, "default", SchemaExtractionOrchestrator, default=True
    )
    return reg


@pytest.fixture
def client(config_repo, config_registry, impl_registry):
    app = FastAPI()
    app.include_router(router)
    app.include_router(config_router)
    app.state.pipeline_config_repo = config_repo
    app.state.config_registry = config_registry
    app.state.implementation_registry = impl_registry
    return TestClient(app)


@pytest.fixture
def client_no_repo(config_registry, impl_registry):
    """Client where pipeline_config_repo is NOT wired — for 503 tests."""
    app = FastAPI()
    app.include_router(config_router)
    app.state.config_registry = config_registry
    app.state.implementation_registry = impl_registry
    return TestClient(app)


def _create_config(client):
    """Helper: POST a configuration via the type-scoped create endpoint and return the response."""
    return client.post(
        "/api/pipelines/types/individual_extraction/implementations/default/configurations",
        json=_CREATE_BODY,
    )


class TestCreateConfiguration:
    def test_create_returns_201(self, client):
        response = _create_config(client)
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_response_has_id(self, client):
        response = _create_config(client)
        body = response.json()
        assert "id" in body
        assert body["id"]

    def test_create_response_fields_match_request(self, client):
        response = _create_config(client)
        body = response.json()
        assert body["name"] == "Test Config"
        assert body["provider"] == "anthropic"
        assert body["model"] == "claude-3-5-sonnet-20241022"
        assert body["version"] == 1
        assert body["is_system"] is False

    def test_create_invalid_type_returns_400(self, client):
        response = client.post(
            "/api/pipelines/types/invalid_type/implementations/default/configurations",
            json=_CREATE_BODY,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_missing_impl_returns_404(self, client):
        response = client.post(
            "/api/pipelines/types/individual_extraction/implementations/missing/configurations",
            json=_CREATE_BODY,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_without_repo_returns_503(self, client_no_repo, impl_registry):
        # Rebuild a client that has impl_registry but no pipeline_config_repo,
        # wired to the type-scoped create endpoint via the main router
        app = FastAPI()
        app.include_router(router)
        app.state.config_registry = PipelineConfigurationRegistry()
        app.state.implementation_registry = impl_registry
        c = TestClient(app)
        response = c.post(
            "/api/pipelines/types/individual_extraction/implementations/default/configurations",
            json=_CREATE_BODY,
        )
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_create_missing_required_field_returns_422(self, client):
        body = dict(_CREATE_BODY)
        del body["name"]
        response = client.post(
            "/api/pipelines/types/individual_extraction/implementations/default/configurations",
            json=body,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetConfiguration:
    def test_get_existing_config_returns_200(self, client):
        created = _create_config(client).json()
        response = client.get(f"/api/pipeline_configurations/{created['id']}")
        assert response.status_code == status.HTTP_200_OK

    def test_get_returns_correct_fields(self, client):
        created = _create_config(client).json()
        response = client.get(f"/api/pipeline_configurations/{created['id']}")
        body = response.json()
        assert body["id"] == created["id"]
        assert body["name"] == "Test Config"

    def test_get_nonexistent_returns_404(self, client):
        response = client.get("/api/pipeline_configurations/00000000-0000-0000-0000-000000000000")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_without_repo_returns_503(self, client_no_repo):
        response = client_no_repo.get("/api/pipeline_configurations/any-id")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestUpdateConfiguration:
    def test_update_returns_200(self, client):
        created = _create_config(client).json()
        update_body = {
            **_CREATE_BODY,
            "name": "Updated",
            "parameters": _CREATE_BODY["parameters"],
        }
        response = client.put(f"/api/pipeline_configurations/{created['id']}", json=update_body)
        assert response.status_code == status.HTTP_200_OK

    def test_update_increments_version(self, client):
        created = _create_config(client).json()
        update_body = {
            **_CREATE_BODY,
            "name": "Updated",
            "parameters": _CREATE_BODY["parameters"],
        }
        response = client.put(f"/api/pipeline_configurations/{created['id']}", json=update_body)
        assert response.json()["version"] == 2

    def test_update_persists_new_name(self, client):
        created = _create_config(client).json()
        update_body = {
            **_CREATE_BODY,
            "name": "New Name",
            "parameters": _CREATE_BODY["parameters"],
        }
        response = client.put(f"/api/pipeline_configurations/{created['id']}", json=update_body)
        assert response.json()["name"] == "New Name"

    def test_update_nonexistent_returns_404(self, client):
        update_body = {**_CREATE_BODY, "parameters": _CREATE_BODY["parameters"]}
        response = client.put(
            "/api/pipeline_configurations/00000000-0000-0000-0000-000000000000",
            json=update_body,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_without_repo_returns_503(self, client_no_repo):
        update_body = {**_CREATE_BODY, "parameters": _CREATE_BODY["parameters"]}
        response = client_no_repo.put("/api/pipeline_configurations/any-id", json=update_body)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_update_missing_required_field_returns_422(self, client):
        created = _create_config(client).json()
        bad_body = {"name": "x"}  # missing provider, model, parameters
        response = client.put(f"/api/pipeline_configurations/{created['id']}", json=bad_body)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestDeleteConfiguration:
    def test_delete_returns_204(self, client):
        created = _create_config(client).json()
        response = client.delete(f"/api/pipeline_configurations/{created['id']}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_makes_get_return_404(self, client):
        created = _create_config(client).json()
        client.delete(f"/api/pipeline_configurations/{created['id']}")
        response = client.get(f"/api/pipeline_configurations/{created['id']}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_returns_404(self, client):
        nonexistent_id = "00000000-0000-0000-0000-000000000000"
        response = client.delete(f"/api/pipeline_configurations/{nonexistent_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_twice_returns_404_second_time(self, client):
        created = _create_config(client).json()
        client.delete(f"/api/pipeline_configurations/{created['id']}")
        response = client.delete(f"/api/pipeline_configurations/{created['id']}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_without_repo_returns_503(self, client_no_repo):
        response = client_no_repo.delete("/api/pipeline_configurations/any-id")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


_SCHEMA_CONFIGS = "/api/pipelines/types/schema_extraction/implementations/default/configurations"
_DEFAULT_DISAMBIGUATION = next(s for s in SCHEMA_EXTRACTION_STAGES if s.key == "disambiguation")


class TestStagePrompts:
    def test_impl_without_stages_has_no_stage_prompts(self, client):
        assert _create_config(client).json()["stage_prompts"] is None

    def test_new_config_shows_every_stage_with_defaults(self, client):
        body = client.post(_SCHEMA_CONFIGS, json=_CREATE_BODY).json()
        stages = body["stage_prompts"]
        assert [s["key"] for s in stages] == [s.key for s in SCHEMA_EXTRACTION_STAGES]
        assert all(s["is_default"] for s in stages)
        disambiguation = stages[-1]
        assert disambiguation["system"] == _DEFAULT_DISAMBIGUATION.default.system
        assert set(disambiguation["placeholders"]) == {"terms", "context"}

    def test_override_is_returned_and_stored_sparsely(self, client, config_repo):
        body = {
            **_CREATE_BODY,
            "stage_prompts": {
                "disambiguation": {"system": "Only split real homonyms."},
                # Equal to the default: nothing to store
                "definition_synthesis": {
                    "system": SCHEMA_EXTRACTION_STAGES[1].default.system,
                },
            },
        }
        created = client.post(_SCHEMA_CONFIGS, json=body).json()
        by_key = {s["key"]: s for s in created["stage_prompts"]}
        assert by_key["disambiguation"]["system"] == "Only split real homonyms."
        assert by_key["disambiguation"]["user"] == _DEFAULT_DISAMBIGUATION.default.user
        assert by_key["disambiguation"]["is_default"] is False
        assert by_key["definition_synthesis"]["is_default"] is True
        assert config_repo.get(created["id"]).stage_prompts == {
            "disambiguation": {"system": "Only split real homonyms."}
        }

    def test_override_reaches_the_registry(self, client, config_registry):
        body = {**_CREATE_BODY, "stage_prompts": {"disambiguation": {"user": "Terms: {terms}"}}}
        created = client.post(_SCHEMA_CONFIGS, json=body).json()
        version = config_registry.get_latest(
            PipelineType.SCHEMA_EXTRACTION, "default", created["config_ref"]
        )
        assert version.config["stage_prompts"] == {"disambiguation": {"user": "Terms: {terms}"}}

    def test_update_with_null_stage_resets_it_to_default(self, client):
        body = {**_CREATE_BODY, "stage_prompts": {"disambiguation": {"system": "Custom."}}}
        created = client.post(_SCHEMA_CONFIGS, json=body).json()
        updated = client.put(
            f"/api/pipeline_configurations/{created['id']}",
            json={**_CREATE_BODY, "stage_prompts": {"disambiguation": None}},
        ).json()
        assert all(s["is_default"] for s in updated["stage_prompts"])

    def test_unknown_stage_returns_422(self, client):
        body = {**_CREATE_BODY, "stage_prompts": {"no_such_stage": {"system": "x"}}}
        response = client.post(_SCHEMA_CONFIGS, json=body)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "no_such_stage" in response.json()["detail"]

    def test_unknown_placeholder_returns_422(self, client):
        body = {**_CREATE_BODY, "stage_prompts": {"disambiguation": {"user": "Terms: {term}"}}}
        response = client.post(_SCHEMA_CONFIGS, json=body)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "{term}" in response.json()["detail"]
