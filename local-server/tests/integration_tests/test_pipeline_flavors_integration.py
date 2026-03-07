"""
Integration tests for pipeline flavor API endpoints.
"""

import pytest
import sys
import os
import json

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPipelineFlavorAPI:
    """Integration tests for pipeline flavor API endpoints"""

    @pytest.fixture
    def sample_flavor_data(self):
        """Sample flavor data for testing"""
        import uuid

        test_id = str(uuid.uuid4())[:8]

        return {
            "pipeline": "suggest_term_definition",
            "title": f"IntegrationTest-{test_id}",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "llm_config": {"temperature": 0.7, "max_tokens": 1000, "top_p": 0.9},  # noqa: E501
            "system_prompt": "You are an expert ontologist and taxonomist specializing in creating precise definitions.",  # noqa: E501
            "user_prompt": "Generate a definition for the term {term} in the context of {domain_title}.",  # noqa: E501
        }

    @pytest.mark.skip_suite
    def test_create_flavor_endpoint(self, client):
        """Test flavor creation endpoint"""
        import uuid

        test_id = str(uuid.uuid4())[:8]

        flavor_data = {
            "pipeline": "suggest_term_definition",
            "title": f"TestAPI-{test_id}",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "llm_config": {"temperature": 0.7, "max_tokens": 1000},
            "system_prompt": "Test system prompt",
            "user_prompt": "Test user prompt",
        }

        response = client.post("/api/pipeline-flavors", json=flavor_data)

        assert response.status_code == 201
        result = response.json()
        assert result["title"] == f"TestAPI-{test_id}"
        assert result["pipeline"] == "suggest_term_definition"

    def test_create_flavor_endpoint_invalid_data(self, client):
        """Test flavor creation endpoint with invalid data"""
        invalid_data = {
            "pipeline": "invalid_pipeline",  # Invalid pipeline type
            "title": "",  # Empty title
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "llm_config": {"temperature": 0.7},
            "system_prompt": "Test",
            "user_prompt": "Test",
        }

        response = client.post("/api/pipeline-flavors", json=invalid_data)

        # Should return validation error
        assert response.status_code == 422  # Unprocessable Entity

    @pytest.mark.skip_suite
    def test_create_flavor_endpoint_duplicate_title(self, client, sample_flavor_data):  # noqa: E501
        """Test flavor creation with duplicate title"""
        # Create first flavor
        response1 = client.post("/api/pipeline-flavors", json=sample_flavor_data)  # noqa: E501
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = client.post("/api/pipeline-flavors", json=sample_flavor_data)  # noqa: E501
        assert response2.status_code == 400  # Bad Request
        assert "already exists" in response2.json()["detail"]

    @pytest.mark.skip_suite
    def test_list_flavors_endpoint(self, client):
        """Test listing flavors endpoint"""
        response = client.get("/api/pipeline-flavors")

        # Check response status
        assert response.status_code == 200

        # Check response structure
        result = response.json()
        assert "flavors" in result
        assert "total_count" in result
        assert isinstance(result["flavors"], list)
        assert isinstance(result["total_count"], int)
        assert result["total_count"] >= 0

    @pytest.mark.skip_suite
    def test_list_flavors_filtered_by_pipeline(self, client):
        """Test listing flavors filtered by pipeline type"""
        response = client.get("/api/pipeline-flavors?pipeline=suggest_term_definition")  # noqa: E501

        # Check response status
        assert response.status_code == 200

        # Check filtering
        result = response.json()
        for flavor in result["flavors"]:
            assert flavor["pipeline"] == "suggest_term_definition"

    @pytest.mark.skip_suite
    def test_get_flavor_by_id_success(self, client, sample_flavor_data):
        """Test getting a specific flavor by ID"""
        # Create a flavor first
        create_response = client.post("/api/pipeline-flavors", json=sample_flavor_data)  # noqa: E501
        assert create_response.status_code == 201

        flavor_id = create_response.json()["id"]

        # Get the flavor
        response = client.get(f"/api/pipeline-flavors/{flavor_id}")

        # Check response
        assert response.status_code == 200
        result = response.json()
        assert result["id"] == flavor_id
        assert result["title"] == sample_flavor_data["title"]

    def test_get_flavor_by_id_not_found(self, client):
        """Test getting non-existent flavor by ID"""
        response = client.get("/api/pipeline-flavors/nonexistent-id")

        # Should return 404
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.skip_suite
    def test_update_flavor_endpoint(self, client, sample_flavor_data):
        """Test updating a flavor"""
        # Create a flavor first
        create_response = client.post("/api/pipeline-flavors", json=sample_flavor_data)  # noqa: E501
        assert create_response.status_code == 201

        flavor_id = create_response.json()["id"]

        # Update the flavor
        import uuid

        test_id = str(uuid.uuid4())[:8]
        update_data = {
            "title": f"UpdatedTest-{test_id}",
            "llm_config": {"temperature": 0.5, "max_tokens": 1500},
            "enabled": False,
        }

        response = client.put(f"/api/pipeline-flavors/{flavor_id}", json=update_data)  # noqa: E501

        # Check response
        assert response.status_code == 200
        result = response.json()
        assert result["title"] == f"UpdatedTest-{test_id}"
        assert result["llm_config"]["temperature"] == 0.5
        assert result["llm_config"]["max_tokens"] == 1500
        assert result["enabled"] is False
        assert (
            result["version"] > 1
        )  # Version should increment    def test_update_flavor_not_found(self, client):  # noqa: E501
        """Test updating non-existent flavor"""
        update_data = {"title": "New Title"}

        response = client.put("/api/pipeline-flavors/nonexistent-id", json=update_data)  # noqa: E501

        # Should return 404
        assert response.status_code == 404

    @pytest.mark.skip_suite
    def test_delete_flavor_endpoint(self, client, sample_flavor_data):
        """Test deleting a flavor"""
        # Create a flavor first
        create_response = client.post("/api/pipeline-flavors", json=sample_flavor_data)  # noqa: E501
        assert create_response.status_code == 201

        flavor_id = create_response.json()["id"]

        # Delete the flavor
        response = client.delete(f"/api/pipeline-flavors/{flavor_id}")

        # Check response
        assert response.status_code == 204

        # Verify it's deleted
        get_response = client.get(f"/api/pipeline-flavors/{flavor_id}")
        assert get_response.status_code == 404

    def test_delete_flavor_not_found(self, client):
        """Test deleting non-existent flavor"""
        response = client.delete("/api/pipeline-flavors/nonexistent-id")

        # Should return 404
        assert response.status_code == 404

    @pytest.mark.skip_suite
    def test_delete_default_flavor_forbidden(self, client):
        """Test that deleting default flavor is forbidden"""
        # First, find a default flavor
        list_response = client.get("/api/pipeline-flavors")
        assert list_response.status_code == 200

        flavors = list_response.json()["flavors"]
        default_flavor = next((f for f in flavors if f["title"] == "Default"), None)  # noqa: E501

        if default_flavor:
            # Try to delete default flavor
            response = client.delete(f"/api/pipeline-flavors/{default_flavor['id']}")  # noqa: E501

            # Should be forbidden
            assert response.status_code == 400
            assert "Cannot delete default flavor" in response.json()["detail"]


class TestLLMStreamingEndpoints:
    """Integration tests for streaming LLM endpoints"""

    @pytest.fixture
    def sample_term_request(self):
        """Sample term definition request with all required template variables"""  # noqa: E501
        return {
            "term": "machine learning",
            "domain_title": "Artificial Intelligence",
            "domain_definition": "The field of computer science that focuses on creating intelligent systems",  # noqa: E501
            "parent_term_title": "Artificial Intelligence",
            "parent_term_definition": "Intelligence demonstrated by machines",
            "parent_relationship_predicate": "is_a",
            "component_terms": "algorithm, data, model",
            "current_definition": "Current definition of machine learning",
            "conceptnet_relations": "Test conceptnet relations",
            "wikidata_context": "Test wikidata context",
            "dbpedia_context": "Test dbpedia context",
            "flavor": "default",
        }

    @pytest.fixture
    def sample_layer_request(self):
        """Sample layer definition request with all required template variables"""  # noqa: E501
        return {
            "layer_title": "Technology Layer",
            "layer_description": "Layer containing technology-related domains",
            "contained_domains": "Software, Hardware, AI",
            "layer_purpose": "Organize technology-related knowledge",
            "parent_layer_title": "Root Layer",
            "parent_layer_definition": "Root layer definition",
            "current_definition": "Current definition",
            "reference_context": "Test reference context",
            "flavor": "default",
        }

    @pytest.fixture
    def sample_domain_request(self):
        """Sample domain definition request with all required template variables"""  # noqa: E501
        return {
            "domain_title": "Machine Learning",
            "layer_title": "Technology",
            "contained_terms": "neural network, algorithm, training",
            "domain_description": "Domain focused on machine learning",
            "domain_scope": "Machine learning algorithms and techniques",
            "layer_definition": "Technology layer definition",
            "related_domains": "AI, Data Science",
            "current_definition": "Current definition",
            "reference_context": "Test reference context",
            "flavor": "default",
        }

    def test_streaming_term_definition_endpoint(self, client, sample_term_request):  # noqa: E501
        """Test streaming term definition endpoint using generic pipeline API"""  # noqa: E501
        # Convert legacy request format to generic pipeline format
        pipeline_request = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": sample_term_request
        }

        response = client.post(
            "/api/llm/execute_pipeline/stream", json=pipeline_request
        )

        # Check response status and headers
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert "Cache-Control" in response.headers
        assert response.headers["Cache-Control"] == "no-cache"

        # Check streaming response format
        content = response.content.decode()
        assert "data:" in content

        # Parse streaming data
        lines = content.strip().split("\n")
        data_lines = [line for line in lines if line.startswith("data:")]

        assert len(data_lines) > 0

        # Check format of data lines
        for line in data_lines:
            data_json = line[5:].strip()  # Remove 'data:' prefix
            if data_json:  # Skip empty lines
                data = json.loads(data_json)
                assert "flavor_id" in data
                assert "done" in data
                assert isinstance(data["done"], bool)

    def test_streaming_term_definition_invalid_request(self, client):
        """Test streaming endpoint with invalid request"""
        invalid_request = {"term": "", "domain_title": "Test Domain"}  # Empty term  # noqa: E501

        # Convert to generic pipeline format
        pipeline_request = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": invalid_request
        }

        response = client.post(
            "/api/llm/execute_pipeline/stream", json=pipeline_request
        )

        # Should still return 200 but with error in stream
        assert response.status_code == 200

        content = response.content.decode()
        assert "data:" in content

        # Should contain error
        assert "error" in content.lower()

    def test_streaming_layer_definition_endpoint(self, client, sample_layer_request):  # noqa: E501
        """Test streaming layer definition endpoint using generic pipeline API"""  # noqa: E501
        # Convert legacy request format to generic pipeline format
        pipeline_request = {
            "flavor_id": "default",
            "pipeline_type": "suggest_layer_definition",
            "context_data": sample_layer_request
        }

        response = client.post(
            "/api/llm/execute_pipeline/stream", json=pipeline_request
        )

        # Check response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

        # Check streaming response format
        content = response.content.decode()
        assert "data:" in content

    def test_streaming_domain_definition_endpoint(self, client, sample_domain_request):  # noqa: E501
        """Test streaming domain definition endpoint using generic pipeline API"""  # noqa: E501
        # Convert legacy request format to generic pipeline format
        pipeline_request = {
            "flavor_id": "default",
            "pipeline_type": "suggest_domain_definition",
            "context_data": sample_domain_request
        }

        response = client.post(
            "/api/llm/execute_pipeline/stream", json=pipeline_request
        )

        # Check response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

        # Check streaming response format
        content = response.content.decode()
        assert "data:" in content

    @pytest.mark.skip_suite
    def test_llm_health_endpoint(self, client):
        """Test LLM health check endpoint"""
        response = client.get("/api/llm/health")

        # Should return health status
        assert response.status_code == 200
        result = response.json()
        assert "status" in result
        assert "model_info" in result
        assert "timestamp" in result


class TestDefaultFlavorPopulation:
    """Integration tests for default flavor population"""

    @pytest.mark.skip_suite
    def test_default_flavors_exist(self, client):
        """Test that default flavors are populated on startup"""
        response = client.get("/api/pipeline-flavors")
        assert response.status_code == 200

        flavors = response.json()["flavors"]

        # Check that default flavors exist for each pipeline type
        pipeline_types = [
            "suggest_term_definition",
            "suggest_layer_definition",
            "suggest_domain_definition",
        ]

        for pipeline_type in pipeline_types:
            default_exists = any(
                f["title"] == "Default" and f["pipeline"] == pipeline_type
                for f in flavors
            )
            assert default_exists, f"Default flavor missing for {pipeline_type}"  # noqa: E501

    @pytest.mark.skip_suite
    def test_default_flavor_properties(self, client):
        """Test that default flavors have correct properties"""
        response = client.get("/api/pipeline-flavors")
        assert response.status_code == 200

        flavors = response.json()["flavors"]
        default_flavors = [f for f in flavors if f["title"] == "Default"]

        for flavor in default_flavors:
            # Check required properties
            assert flavor["title"] == "Default"
            assert flavor["enabled"] is True
            assert flavor["llm_provider"] == "openai"
            assert flavor["llm_model"] in ["gpt-3.5-turbo", "gpt-4"]
            assert len(flavor["system_prompt"]) > 0
            assert len(flavor["user_prompt"]) > 0
            assert "temperature" in flavor["llm_config"]


class TestAPIErrorHandling:
    """Integration tests for API error handling"""

    def test_invalid_json_request(self, client):
        """Test API handling of invalid JSON"""
        response = client.post(
            "/api/pipeline-flavors",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        # Should return 422 for invalid JSON
        assert response.status_code == 422

    def test_missing_required_fields(self, client):
        """Test API handling of missing required fields"""
        incomplete_data = {
            "title": "Test Flavor"
            # Missing required fields: pipeline, llm_provider, etc.
        }

        response = client.post("/api/pipeline-flavors", json=incomplete_data)

        # Should return validation error
        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert isinstance(error_detail, list)
        assert len(error_detail) > 0

    def test_invalid_pipeline_type(self, client):
        """Test API handling of invalid pipeline type"""
        invalid_data = {
            "pipeline": "invalid_pipeline_type",
            "title": "Test Flavor",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "llm_config": {"temperature": 0.7},
            "system_prompt": "Test",
            "user_prompt": "Test",
        }

        response = client.post("/api/pipeline-flavors", json=invalid_data)

        # Should return validation error
        assert response.status_code == 422

    def test_invalid_llm_config_values(self, client):
        """Test API handling of invalid LLM config values"""
        invalid_data = {
            "pipeline": "suggest_term_definition",
            "title": "Test Flavor",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "llm_config": {
                "temperature": 5.0,  # Invalid: too high
                "max_tokens": -100,  # Invalid: negative
            },
            "system_prompt": "Test",
            "user_prompt": "Test",
        }

        response = client.post("/api/pipeline-flavors", json=invalid_data)

        # Should return validation error
        assert response.status_code == 422
