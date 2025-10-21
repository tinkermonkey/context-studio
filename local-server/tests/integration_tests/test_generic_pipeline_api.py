"""
Integration tests for the generic pipeline execution API endpoints.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, AsyncMock
import tempfile
from fastapi.testclient import TestClient

from app import create_app
from pipeline.manager import PipelineDatabaseManager
from llm.models import PipelineType


class TestGenericPipelineAPIIntegration:
    
    def setup_method(self):
        """Set up test fixtures with temporary pipeline database."""
        # Create temporary pipeline database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Initialize pipeline database manager with temp file
        self.pipeline_manager = PipelineDatabaseManager(self.temp_db.name)
        
        # Create test client
        self.app = create_app()
        self.client = TestClient(self.app)
        
    def teardown_method(self):
        """Clean up test fixtures."""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_execute_pipeline_endpoint_success(self, mock_get_session):
        """Test successful execution of generic pipeline endpoint."""

        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()

        # Mock the LLM service using FastAPI dependency override
        mock_service = AsyncMock()

        # Mock the generic execution response
        mock_response = Mock()
        mock_response.response_content = "Test definition response"
        mock_response.execution_id = "test-execution-123"
        mock_response.flavor_id = "test-flavor-456"
        mock_response.pipeline_type = "suggest_term_definition"
        mock_response.token_usage = {
            "input_tokens": 15,
            "output_tokens": 25,
            "total_tokens": 40
        }
        mock_response.structured_output = None
        mock_service.execute_pipeline_flavor.return_value = mock_response

        # Override the dependency
        from api.dependencies.llm_services import get_default_llm_service
        self.app.dependency_overrides[get_default_llm_service] = lambda: mock_service
        
        # Test request payload
        request_payload = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": {
                "term": "integration test term",
                "domain_title": "Test Domain",
                "domain_definition": "A domain for testing purposes",
                "parent_term_title": None,
                "parent_term_definition": None,
                "parent_relationship_predicate": None,
                "component_terms": "",
                "current_definition": None,
                "conceptnet_relations": "",
                "wikidata_context": "Not specified",
                "dbpedia_context": "Not specified"
            }
        }
        
        # Make the API request
        response = self.client.post(
            "/api/llm/execute_pipeline",
            json=request_payload
        )
        
        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["response_content"] == "Test definition response"
        assert response_data["execution_id"] == "test-execution-123"
        assert response_data["flavor_id"] == "test-flavor-456"
        assert response_data["pipeline_type"] == "suggest_term_definition"
        assert response_data["token_usage"]["total_tokens"] == 40
        
        # Verify the service was called correctly
        mock_service.execute_pipeline_flavor.assert_called_once()
        call_args = mock_service.execute_pipeline_flavor.call_args[0][0]
        assert call_args.flavor_id == "default"
        assert call_args.pipeline_type == PipelineType.SUGGEST_TERM_DEFINITION
        assert call_args.context_data["term"] == "integration test term"

        # Clean up dependency override
        from api.dependencies.llm_services import get_default_llm_service
        del self.app.dependency_overrides[get_default_llm_service]
    
    def test_execute_pipeline_endpoint_validation_error(self):
        """Test validation error handling in generic pipeline endpoint."""

        # Mock the LLM service using FastAPI dependency override
        mock_service = AsyncMock()
        from api.dependencies.llm_services import get_default_llm_service
        self.app.dependency_overrides[get_default_llm_service] = lambda: mock_service

        # Test request payload with missing context_data
        request_payload = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": {}
        }

        # Make the API request
        response = self.client.post(
            "/api/llm/execute_pipeline",
            json=request_payload
        )

        # Verify error response (422 for validation errors)
        assert response.status_code == 422
        response_data = response.json()
        assert any("context_data cannot be empty" in error.get("msg", "") for error in response_data["detail"])

        # Clean up dependency override
        del self.app.dependency_overrides[get_default_llm_service]

    def test_execute_pipeline_endpoint_context_too_large(self):
        """Test context data size validation in generic pipeline endpoint."""

        # Mock the LLM service using FastAPI dependency override
        mock_service = AsyncMock()
        from api.dependencies.llm_services import get_default_llm_service
        self.app.dependency_overrides[get_default_llm_service] = lambda: mock_service

        # Create very large context data
        large_data = "x" * 60000
        request_payload = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": {"large_field": large_data}
        }
        
        # Make the API request
        response = self.client.post(
            "/api/llm/execute_pipeline",
            json=request_payload
        )
        
        # Verify error response
        assert response.status_code == 400
        response_data = response.json()
        assert "Context data is too large" in response_data["detail"]

        # Clean up dependency override
        del self.app.dependency_overrides[get_default_llm_service]
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_execute_pipeline_streaming_endpoint_success(self, mock_get_session):
        """Test successful execution of generic streaming pipeline endpoint."""

        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()

        # Mock the LLM service using FastAPI dependency override
        mock_service = AsyncMock()
        
        # Mock streaming responses
        async def mock_streaming():
            from llm.models import StreamingLLMResponse
            yield StreamingLLMResponse(
                flavor_id="test-flavor-456",
                execution_id="test-execution-123",
                done=False
            )
            yield StreamingLLMResponse(
                token="Hello",
                flavor_id="test-flavor-456",
                done=False
            )
            yield StreamingLLMResponse(
                token=" world",
                flavor_id="test-flavor-456",
                done=False
            )
            yield StreamingLLMResponse(
                flavor_id="test-flavor-456",
                done=True
            )
        
        mock_service.execute_pipeline_flavor_streaming.return_value = mock_streaming()

        # Override the dependency
        from api.dependencies.llm_services import get_default_llm_service
        self.app.dependency_overrides[get_default_llm_service] = lambda: mock_service

        # Test request payload
        request_payload = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": {
                "term": "streaming test term",
                "domain_title": "Test Domain"
            }
        }
        
        # Make the API request
        response = self.client.post(
            "/api/llm/execute_pipeline/stream",
            json=request_payload
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        
        # Parse streaming response
        response_text = response.text
        assert "data: " in response_text
        
        # Verify the service was called correctly
        mock_service.execute_pipeline_flavor_streaming.assert_called_once()
        call_args = mock_service.execute_pipeline_flavor_streaming.call_args[0][0]
        assert call_args.flavor_id == "default"
        assert call_args.pipeline_type == PipelineType.SUGGEST_TERM_DEFINITION
        assert call_args.context_data["term"] == "streaming test term"

        # Clean up dependency override
        from api.dependencies.llm_services import get_default_llm_service
        del self.app.dependency_overrides[get_default_llm_service]
    
    def test_execute_pipeline_streaming_validation_error(self):
        """Test validation error handling in streaming pipeline endpoint."""

        # Mock the LLM service using FastAPI dependency override
        mock_service = AsyncMock()
        from api.dependencies.llm_services import get_default_llm_service
        self.app.dependency_overrides[get_default_llm_service] = lambda: mock_service

        # Test request payload with empty context_data
        request_payload = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": {}
        }
        
        # Make the API request
        response = self.client.post(
            "/api/llm/execute_pipeline/stream",
            json=request_payload
        )

        # Verify error response (422 for validation errors)
        assert response.status_code == 422
        response_data = response.json()
        assert any("context_data cannot be empty" in error.get("msg", "") for error in response_data["detail"])

        # Clean up dependency override
        del self.app.dependency_overrides[get_default_llm_service]

    def test_execute_pipeline_different_pipeline_types(self):
        """Test generic pipeline endpoint with different pipeline types."""

        # Mock the LLM service using FastAPI dependency override
        mock_service = AsyncMock()
        from api.dependencies.llm_services import get_default_llm_service
        self.app.dependency_overrides[get_default_llm_service] = lambda: mock_service
        
        # Test data for different pipeline types
        test_cases = [
            {
                "pipeline_type": "suggest_layer_definition",
                "context_data": {
                    "layer_title": "Test Layer",
                    "contained_domains": "Domain1, Domain2",
                    "layer_description": "Test layer description",
                    "layer_purpose": "Test layer purpose",
                    "parent_layer_title": "Parent Layer",
                    "parent_layer_definition": "Parent layer definition",
                    "current_definition": "Current definition",
                    "reference_context": "Test reference context"
                }
            },
            {
                "pipeline_type": "suggest_domain_definition",
                "context_data": {
                    "domain_title": "Test Domain",
                    "contained_terms": "Term1, Term2",
                    "layer_title": "Parent Layer",
                    "domain_description": "Test domain description",
                    "domain_scope": "Test domain scope",
                    "layer_definition": "Parent layer definition",
                    "related_domains": "Related Domain1, Related Domain2",
                    "current_definition": "Current definition",
                    "reference_context": "Test reference context"
                }
            }
        ]
        
        for test_case in test_cases:
            # Mock response for each pipeline type
            mock_response = Mock()
            mock_response.response_content = f"Response for {test_case['pipeline_type']}"
            mock_response.execution_id = f"exec-{test_case['pipeline_type']}"
            mock_response.flavor_id = "test-flavor"
            mock_response.pipeline_type = test_case['pipeline_type']
            mock_response.token_usage = None
            mock_response.structured_output = None
            mock_service.execute_pipeline_flavor.return_value = mock_response
            
            # Test request
            request_payload = {
                "flavor_id": "default",
                "pipeline_type": test_case['pipeline_type'],
                "context_data": test_case['context_data']
            }
            
            response = self.client.post(
                "/api/llm/execute_pipeline",
                json=request_payload
            )
            
            # Verify response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["pipeline_type"] == test_case['pipeline_type']
            assert response_data["response_content"] == f"Response for {test_case['pipeline_type']}"

        # Cleanup dependency override
        del self.app.dependency_overrides[get_default_llm_service]
    
    @patch('llm.execution_tracker.get_pipeline_session')
    def test_backward_compatibility_with_generic_implementation(self, mock_get_session):
        """Test that the generic implementation can handle legacy suggest_term_definition requests."""

        # Use real database session from our test pipeline manager
        mock_get_session.side_effect = lambda: self.pipeline_manager.get_session()

        # Mock the LLM service using FastAPI dependency override
        mock_service = AsyncMock()

        # Mock the generic execution response (the new way)
        mock_response = Mock()
        mock_response.response_content = "A test term definition"
        mock_response.execution_id = "test-execution-456"
        mock_response.flavor_id = "test-flavor-456"
        mock_response.pipeline_type = "suggest_term_definition"
        mock_response.token_usage = {
            "input_tokens": 20,
            "output_tokens": 30,
            "total_tokens": 50
        }
        mock_response.structured_output = None
        mock_service.execute_pipeline_flavor.return_value = mock_response

        # Override the dependency
        from api.dependencies.llm_services import get_default_llm_service
        self.app.dependency_overrides[get_default_llm_service] = lambda: mock_service

        # Test using the generic endpoint with legacy-style data
        request_payload = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": {
                "term": "integration test term",
                "domain_title": "Test Domain",
                "domain_definition": "A domain for testing purposes",
                "parent_term_title": None,
                "parent_term_definition": None,
                "parent_relationship_predicate": None,
                "component_terms": "",
                "current_definition": None,
                "conceptnet_relations": "",
                "wikidata_context": "Not specified",
                "dbpedia_context": "Not specified"
            }
        }

        response = self.client.post(
            "/api/llm/execute_pipeline",
            json=request_payload
        )

        # Verify response uses the new generic format
        assert response.status_code == 200
        response_data = response.json()

        assert response_data["response_content"] == "A test term definition"
        assert response_data["execution_id"] == "test-execution-456"
        assert response_data["pipeline_type"] == "suggest_term_definition"
        assert response_data["token_usage"]["total_tokens"] == 50

        # Verify the generic service method was called
        mock_service.execute_pipeline_flavor.assert_called_once()
        call_args = mock_service.execute_pipeline_flavor.call_args[0][0]
        assert call_args.flavor_id == "default"
        assert call_args.pipeline_type == PipelineType.SUGGEST_TERM_DEFINITION
        assert call_args.context_data["term"] == "integration test term"

        # Clean up dependency override
        del self.app.dependency_overrides[get_default_llm_service]
    
    def test_error_handling_consistency(self):
        """Test that error handling is consistent between generic and specific endpoints."""

        # Mock the LLM service to raise an error using FastAPI dependency override
        from llm.exceptions import LLMProcessingError
        mock_service = AsyncMock()
        mock_service.execute_pipeline_flavor.side_effect = LLMProcessingError("Test processing error")

        from api.dependencies.llm_services import get_default_llm_service
        self.app.dependency_overrides[get_default_llm_service] = lambda: mock_service
        
        # Test generic endpoint error
        generic_payload = {
            "flavor_id": "default",
            "pipeline_type": "suggest_term_definition",
            "context_data": {
                "term": "test",
                "domain_title": "Test Domain",
                "domain_definition": "Test domain definition",
                "parent_term_title": "Parent Term",
                "parent_term_definition": "Parent term definition",
                "parent_relationship_predicate": "is_a",
                "component_terms": "Component1, Component2",
                "current_definition": "Current definition",
                "conceptnet_relations": "Test relations",
                "wikidata_context": "Test wikidata context",
                "dbpedia_context": "Test dbpedia context"
            }
        }
        
        generic_response = self.client.post(
            "/api/llm/execute_pipeline",
            json=generic_payload
        )
        
        # Test generic endpoint error handling
        assert generic_response.status_code == 400
        generic_error = generic_response.json()
        assert "Test processing error" in generic_error["detail"]

        # Cleanup dependency override
        del self.app.dependency_overrides[get_default_llm_service]
    
    def test_api_endpoint_documentation(self):
        """Test that the generic endpoints are properly documented in OpenAPI."""
        
        # Get OpenAPI schema
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_spec = response.json()
        paths = openapi_spec["paths"]
        
        # Verify generic endpoints are documented
        assert "/api/llm/execute_pipeline" in paths
        assert "/api/llm/execute_pipeline/stream" in paths
        
        # Verify the execute_pipeline endpoint has proper documentation
        execute_pipeline = paths["/api/llm/execute_pipeline"]["post"]
        assert "Execute a generic pipeline with arbitrary context data" in execute_pipeline["description"]
        
        # Verify request schema includes GenericPipelineExecutionRequest
        request_schema = execute_pipeline["requestBody"]["content"]["application/json"]["schema"]
        assert "$ref" in request_schema
        
        # Verify response schema includes GenericPipelineExecutionResponse
        response_schema = execute_pipeline["responses"]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in response_schema
        
        # Verify streaming endpoint documentation
        execute_stream = paths["/api/llm/execute_pipeline/stream"]["post"]
        assert "Execute a generic pipeline with streaming response" in execute_stream["description"]