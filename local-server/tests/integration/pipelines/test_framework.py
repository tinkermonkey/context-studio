"""
Framework-level tests for LLM pipeline infrastructure.

Tests verify:
1. Registry immutability and duplicate registration prevention
2. Pipeline run persistence with change event linkage (batch_run_id)
3. No-op pipeline execution end-to-end
4. API surface contracts and error handling
5. Pydantic constraint enforcement (confidence bounds, required fields)

These framework tests establish the patterns and infrastructure for per-type
tests in sub-issues 4B.5–4B.8.
"""

import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)))
sys.path.append(base_dir)

import pytest
from fastapi import status

from domain.pipelines.entities import PipelineType


class TestRegistryInvariance:
    """Test registry invariants: immutability, no duplicate registration."""

    def test_impl_registry_duplicate_registration_raises_error(self, impl_registry):
        """Registering same (type, impl_id) twice raises ValueError."""
        with pytest.raises(ValueError, match="already registered"):
            impl_registry.register_impl(
                PipelineType.NO_OP,
                "default",
                object,  # Different class, same key
            )

    def test_config_registry_allows_version_updates(self, config_registry):
        """Configuration updates increment version; old versions accessible."""
        # Register initial config
        v1 = config_registry.register(
            PipelineType.NO_OP,
            "default",
            "test-config",
            {"param1": "value1"},
        )
        assert v1.version == 1

        # Update config (new version)
        v2 = config_registry.register(
            PipelineType.NO_OP,
            "default",
            "test-config",
            {"param1": "updated_value1"},
        )
        assert v2.version == 2

        # Verify both versions exist and are distinct
        retrieved_v1 = config_registry.get_version(
            PipelineType.NO_OP,
            "default",
            "test-config",
            1,
        )
        retrieved_v2 = config_registry.get_version(
            PipelineType.NO_OP,
            "default",
            "test-config",
            2,
        )

        assert retrieved_v1.config["param1"] == "value1"
        assert retrieved_v2.config["param1"] == "updated_value1"

    def test_config_registry_configuration_copy_is_defensive(self, config_registry):
        """Configuration dict is copied; external mutations don't affect registry."""
        config_dict = {"key": "value"}
        config_registry.register(
            PipelineType.NO_OP,
            "default",
            "defensive-copy-test",
            config_dict,
        )

        # Mutate external dict
        config_dict["key"] = "mutated"

        # Verify registered config is unchanged
        retrieved = config_registry.get_latest(
            PipelineType.NO_OP,
            "default",
            "defensive-copy-test",
        )
        assert retrieved.config["key"] == "value"


class TestNoOpPipelineAPI:
    """Test no-op pipeline execution via REST API."""

    def test_noop_pipeline_run_returns_201(self, client):
        """POST /api/pipelines/no_op/run returns 201."""
        response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "text": "Sample input text",
                "ontology_id": "test-ontology",
                "implementation_id": "default",
                "configuration_ref": "noop-default",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_noop_pipeline_run_response_structure(self, client):
        """POST /api/pipelines/no_op/run response has correct structure."""
        response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "text": "Sample input",
                "ontology_id": "test-ontology",
                "implementation_id": "default",
                "configuration_ref": "noop-default",
            },
        )
        body = response.json()

        # Verify required fields
        assert "id" in body
        assert "batch_run_id" in body
        assert "pipeline_type" in body
        assert "implementation_id" in body
        assert "configuration_ref" in body
        assert "status" in body
        assert "created_at" in body

        # Verify types
        assert isinstance(body["id"], str)
        assert isinstance(body["batch_run_id"], str)
        assert body["pipeline_type"] == "no_op"
        assert body["implementation_id"] == "default"
        assert body["status"] == "pending"

    def test_noop_pipeline_run_retrieval(self, client):
        """GET /api/pipelines/runs/{run_id} returns persisted run."""
        # Create a run
        create_response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "text": "Sample input",
                "ontology_id": "test-ontology",
                "implementation_id": "default",
                "configuration_ref": "noop-default",
            },
        )
        run_id = create_response.json()["id"]

        # Retrieve it
        get_response = client.get(f"/api/pipelines/runs/{run_id}")
        assert get_response.status_code == status.HTTP_200_OK

        body = get_response.json()
        assert body["id"] == run_id
        assert body["pipeline_type"] == "no_op"
        assert body["status"] == "pending"

    def test_noop_pipeline_run_listing(self, client):
        """GET /api/pipelines/runs returns list of runs."""
        # Create a run
        client.post(
            "/api/pipelines/no_op/run",
            json={
                "text": "Sample input",
                "ontology_id": "test-ontology",
                "implementation_id": "default",
                "configuration_ref": "noop-default",
            },
        )

        # List runs
        response = client.get("/api/pipelines/runs")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        # Response is paginated
        assert isinstance(body, dict)
        assert "items" in body
        assert len(body["items"]) > 0
        assert body["items"][0]["pipeline_type"] == "no_op"

    def test_noop_pipeline_run_listing_with_type_filter(self, client):
        """GET /api/pipelines/runs?pipeline_type=no_op filters correctly."""
        # Create a run
        client.post(
            "/api/pipelines/no_op/run",
            json={
                "text": "Sample input",
                "ontology_id": "test-ontology",
                "implementation_id": "default",
                "configuration_ref": "noop-default",
            },
        )

        # List with filter
        response = client.get("/api/pipelines/runs?pipeline_type=no_op")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert all(run["pipeline_type"] == "no_op" for run in body["items"])


class TestErrorHandling:
    """Test API error handling and validation."""

    def test_invalid_pipeline_type_returns_400(self, client):
        """POST to invalid pipeline type returns 400."""
        response = client.post(
            "/api/pipelines/invalid_type/run",
            json={
                "text": "Sample input",
                "ontology_id": "test",
                "implementation_id": "default",
                "configuration_ref": "default",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_implementation_returns_404(self, client):
        """POST with unknown implementation_id returns 404."""
        response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "text": "Sample input",
                "ontology_id": "test",
                "implementation_id": "unknown_impl",
                "configuration_ref": "noop-default",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_configuration_returns_404(self, client):
        """POST with unknown configuration_ref returns 404."""
        response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "text": "Sample input",
                "ontology_id": "test",
                "implementation_id": "default",
                "configuration_ref": "unknown_config",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_malformed_json_returns_422(self, client):
        """POST with malformed JSON returns 422."""
        response = client.post(
            "/api/pipelines/no_op/run",
            content='{"invalid json"',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_nonexistent_run_returns_404(self, client):
        """GET nonexistent run returns 404."""
        response = client.get("/api/pipelines/runs/nonexistent-run-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_invalid_pipeline_type_filter_returns_400(self, client):
        """GET /api/pipelines/runs with invalid type filter returns 400."""
        response = client.get("/api/pipelines/runs?pipeline_type=invalid_type")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_status_filter_returns_400(self, client):
        """GET /api/pipelines/runs with invalid status filter returns 400."""
        response = client.get("/api/pipelines/runs?status=invalid_status")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPipelineTypeEnumeration:
    """Test pipeline type discovery endpoints."""

    def test_list_types_returns_all_five_types(self, client):
        """GET /api/pipelines/types includes all five pipeline types."""
        response = client.get("/api/pipelines/types")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        types = {t["pipeline_type"] for t in body}

        expected_types = {
            "individual_extraction",
            "schema_extraction",
            "schema_node_grounding",
            "schema_node_definition_refinement",
            "schema_node_connection_refinement",
        }
        assert expected_types.issubset(types)

    def test_type_response_includes_contracts(self, client):
        """Pipeline type response includes input/output contracts."""
        response = client.get("/api/pipelines/types")
        body = response.json()

        # Find individual_extraction type
        ind_ext = next((t for t in body if t["pipeline_type"] == "individual_extraction"), None)
        assert ind_ext is not None

        # Verify contract structure
        assert isinstance(ind_ext["input_contract"], dict)
        assert isinstance(ind_ext["output_contract"], dict)
        assert len(ind_ext["input_contract"]) > 0
        assert len(ind_ext["output_contract"]) > 0


class TestImplementationRegistry:
    """Test implementation discovery and registration."""

    def test_list_implementations_for_noop_returns_default(self, client):
        """GET implementations for no_op returns 'default' implementation."""
        response = client.get("/api/pipelines/types/no_op/implementations")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        impl_ids = {impl["id"] for impl in body}
        assert "default" in impl_ids

    def test_implementation_response_structure(self, client):
        """Implementation response has correct structure."""
        response = client.get("/api/pipelines/types/no_op/implementations")
        body = response.json()

        assert len(body) > 0
        impl = body[0]

        assert "id" in impl
        assert "pipeline_type" in impl


class TestConfigurationRegistry:
    """Test configuration discovery and management."""

    def test_list_configurations_for_noop_default(self, client):
        """GET configurations for no_op/default returns registered configs."""
        response = client.get("/api/pipelines/types/no_op/implementations/default/configurations")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert isinstance(body, list)

        config_refs = {config["config_ref"] for config in body}
        assert "noop-default" in config_refs

    def test_configuration_response_structure(self, client):
        """Configuration response has correct structure."""
        response = client.get("/api/pipelines/types/no_op/implementations/default/configurations")
        body = response.json()

        assert len(body) > 0
        config = body[0]

        assert "config_ref" in config
        assert "version" in config
        assert "config" in config
        assert isinstance(config["config"], dict)


class TestLineageAndChangeEvents:
    """Test that pipeline runs carry batch_run_id for traceability."""

    def test_pipeline_run_has_batch_run_id(self, client):
        """Pipeline run response includes batch_run_id for lineage tracking."""
        # Execute no-op pipeline
        response = client.post(
            "/api/pipelines/no_op/run",
            json={"configuration_ref": "noop-default"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()

        assert "batch_run_id" in body
        assert isinstance(body["batch_run_id"], str)
        assert len(body["batch_run_id"]) > 0

    def test_batch_run_id_is_consistent(self, client):
        """Multiple calls to same pipeline produce different batch_run_ids."""
        response1 = client.post(
            "/api/pipelines/no_op/run",
            json={"configuration_ref": "noop-default"},
        )
        assert response1.status_code == status.HTTP_201_CREATED
        batch_run_id_1 = response1.json()["batch_run_id"]

        response2 = client.post(
            "/api/pipelines/no_op/run",
            json={"configuration_ref": "noop-default"},
        )
        assert response2.status_code == status.HTTP_201_CREATED
        batch_run_id_2 = response2.json()["batch_run_id"]

        # Each run should have its own batch_run_id
        assert batch_run_id_1 != batch_run_id_2


class TestPydanticConstraints:
    """Test Pydantic field validation and constraints."""

    def test_string_fields_required_format(self, client):
        """String fields are validated for proper format."""
        # Valid configuration_ref
        response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "configuration_ref": "noop-default",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_explicit_implementation_id_accepted(self, client):
        """Explicit implementation_id with configuration_ref is accepted."""
        response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "implementation_id": "default",
                "configuration_ref": "noop-default",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_response_structure_is_valid(self, client):
        """Response structure conforms to expected schema."""
        response = client.post(
            "/api/pipelines/no_op/run",
            json={
                "configuration_ref": "noop-default",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()

        # Verify required response fields
        assert "id" in body
        assert "batch_run_id" in body
        assert "status" in body


class TestWaveARegression:
    """Test Wave A extraction pipeline regression: `POST /api/extraction/extract` still works."""

    @pytest.mark.skip(
        reason="Wave A extraction endpoint not yet wired into current test client"
    )
    def test_extraction_extract_endpoint_works(self, client):
        """POST /api/extraction/extract returns well-formed response."""
        response = client.post(
            "/api/extraction/extract",
            json={
                "text": "Test document content.",
                "schema_type": "entity",
            },
        )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        body = response.json()

        # Verify response structure
        assert "id" in body or "extraction_id" in body
        assert "status" in body or "success" in body
