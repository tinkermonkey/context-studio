"""
Unit tests for Layer and Domain LLM functionality
"""

import pytest
import sys
import os
from unittest.mock import patch

# Add the project root to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLLMLayerDomainModels:
    """Test Layer and Domain LLM models"""

    def test_model_imports(self):
        """Test that all new models can be imported"""
        from llm.models import (
            LayerDefinitionRequest,
            LayerDefinitionResponse,
            DomainDefinitionRequest,
            DomainDefinitionResponse,
            LayerLLMSuccessResponse,
            DomainLLMSuccessResponse,
        )

        # All models should be importable
        assert LayerDefinitionRequest is not None
        assert LayerDefinitionResponse is not None
        assert DomainDefinitionRequest is not None
        assert DomainDefinitionResponse is not None
        assert LayerLLMSuccessResponse is not None
        assert DomainLLMSuccessResponse is not None

    def test_layer_definition_request_validation(self):
        """Test LayerDefinitionRequest validation"""
        from llm.models import LayerDefinitionRequest

        # Test valid request
        valid_request = LayerDefinitionRequest(
            layer_title="Test Layer", contained_domains=["Domain 1", "Domain 2"]
        )
        assert valid_request.layer_title == "Test Layer"
        assert len(valid_request.contained_domains) == 2

        # Test empty title should fail
        with pytest.raises(ValueError):
            LayerDefinitionRequest(layer_title="", contained_domains=["Domain 1"])

        # Test empty domains should fail
        with pytest.raises(ValueError):
            LayerDefinitionRequest(layer_title="Test", contained_domains=[])

    def test_domain_definition_request_validation(self):
        """Test DomainDefinitionRequest validation"""
        from llm.models import DomainDefinitionRequest

        # Test valid request
        valid_request = DomainDefinitionRequest(
            domain_title="Test Domain", contained_terms=["Term 1", "Term 2"]
        )
        assert valid_request.domain_title == "Test Domain"
        assert len(valid_request.contained_terms) == 2

        # Test empty title should fail
        with pytest.raises(ValueError):
            DomainDefinitionRequest(domain_title="", contained_terms=["Term 1"])

        # Test empty terms should fail
        with pytest.raises(ValueError):
            DomainDefinitionRequest(domain_title="Test", contained_terms=[])


class TestLLMLayerDomainService:
    """Test Layer and Domain LLM service methods"""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-for-testing"})
    def test_service_method_existence(self):
        """Test that service methods exist"""
        from llm.service import LLMService

        service = LLMService()

        # Check that new methods exist
        assert hasattr(service, "suggest_layer_definition")
        assert callable(service.suggest_layer_definition)

        assert hasattr(service, "suggest_domain_definition")
        assert callable(service.suggest_domain_definition)

        assert hasattr(service, "_parse_layer_definition_response")
        assert callable(service._parse_layer_definition_response)

        assert hasattr(service, "_parse_domain_definition_response")
        assert callable(service._parse_domain_definition_response)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-for-testing"})
    def test_layer_response_parsing(self):
        """Test layer definition response parsing"""
        from llm.service import LLMService
        from llm.exceptions import LLMProcessingError

        service = LLMService()

        # Test valid layer response
        valid_response = """Definition: A logical grouping of related domains
Purpose: To organize and structure knowledge domains
Rationale: This provides better organization"""

        result = service._parse_layer_definition_response(valid_response)
        assert result.definition == "A logical grouping of related domains"
        assert result.purpose == "To organize and structure knowledge domains"
        assert result.rationale == "This provides better organization"

        # Test invalid response
        with pytest.raises(LLMProcessingError):
            service._parse_layer_definition_response("Invalid response format")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-for-testing"})
    def test_domain_response_parsing(self):
        """Test domain definition response parsing"""
        from llm.service import LLMService
        from llm.exceptions import LLMProcessingError

        service = LLMService()

        # Test valid domain response
        valid_response = """Definition: A specific area of knowledge
Purpose: To contain related terms and concepts
Scope: Covers all aspects of the subject area"""

        result = service._parse_domain_definition_response(valid_response)
        assert result.definition == "A specific area of knowledge"
        assert result.purpose == "To contain related terms and concepts"
        assert result.scope == "Covers all aspects of the subject area"

        # Test invalid response
        with pytest.raises(LLMProcessingError):
            service._parse_domain_definition_response("Invalid response format")


class TestLLMLayerDomainPrompts:
    """Test Layer and Domain prompt templates"""

    def test_prompt_template_methods(self):
        """Test that prompt template methods exist"""
        from llm.prompts import DefinitionPromptTemplate

        template = DefinitionPromptTemplate()

        # Check layer prompt methods
        assert hasattr(template, "get_layer_definition_system_prompt")
        assert callable(template.get_layer_definition_system_prompt)

        assert hasattr(template, "create_layer_definition_prompt")
        assert callable(template.create_layer_definition_prompt)

        # Check domain prompt methods
        assert hasattr(template, "get_domain_definition_system_prompt")
        assert callable(template.get_domain_definition_system_prompt)

        assert hasattr(template, "create_domain_definition_prompt")
        assert callable(template.create_domain_definition_prompt)

    def test_layer_system_prompt_content(self):
        """Test layer system prompt contains appropriate content"""
        from llm.prompts import DefinitionPromptTemplate

        template = DefinitionPromptTemplate()
        system_prompt = template.get_layer_definition_system_prompt()

        assert "knowledge architect" in system_prompt
        assert "layer" in system_prompt.lower()
        assert "definition" in system_prompt.lower()

    def test_domain_system_prompt_content(self):
        """Test domain system prompt contains appropriate content"""
        from llm.prompts import DefinitionPromptTemplate

        template = DefinitionPromptTemplate()
        system_prompt = template.get_domain_definition_system_prompt()

        assert "domain analyst" in system_prompt
        assert "domain" in system_prompt.lower()
        assert "definition" in system_prompt.lower()

    def test_layer_prompt_creation(self):
        """Test layer prompt creation with sample data"""
        from llm.prompts import DefinitionPromptTemplate
        from llm.models import LayerDefinitionRequest

        template = DefinitionPromptTemplate()

        request = LayerDefinitionRequest(
            layer_title="Test Layer", contained_domains=["Domain 1", "Domain 2"]
        )

        user_prompt = template.create_layer_definition_prompt(request, "")

        assert "Test Layer" in user_prompt
        assert "Domain 1" in user_prompt
        assert "Domain 2" in user_prompt

    def test_domain_prompt_creation(self):
        """Test domain prompt creation with sample data"""
        from llm.prompts import DefinitionPromptTemplate
        from llm.models import DomainDefinitionRequest

        template = DefinitionPromptTemplate()

        request = DomainDefinitionRequest(
            domain_title="Test Domain", contained_terms=["Term 1", "Term 2"]
        )

        user_prompt = template.create_domain_definition_prompt(request, "")

        assert "Test Domain" in user_prompt
        assert "Term 1" in user_prompt
        assert "Term 2" in user_prompt


class TestLLMLayerDomainAPI:
    """Test Layer and Domain API endpoints"""

    def test_api_endpoints_registered(self):
        """Test that API endpoints are registered"""
        from api.llm import router

        found_endpoints = []
        for route in router.routes:
            if hasattr(route, "path") and "/llm/" in route.path:
                found_endpoints.append(route.path)

        expected_endpoints = [
            "/llm/suggest_layer_definition",
            "/llm/suggest_domain_definition",
        ]

        for expected in expected_endpoints:
            assert expected in found_endpoints, f"Endpoint {expected} not found"

    def test_app_integration(self):
        """Test that endpoints are integrated with main application"""
        try:
            from app import create_app

            app = create_app()

            full_app_routes = []
            for route in app.routes:
                if hasattr(route, "path") and "/api/llm/" in route.path:
                    full_app_routes.append(route.path)

            expected_full_routes = [
                "/api/llm/suggest_layer_definition",
                "/api/llm/suggest_domain_definition",
            ]

            for expected in expected_full_routes:
                assert (
                    expected in full_app_routes
                ), f"Endpoint {expected} not integrated in main app"

        except Exception as e:
            pytest.fail(f"App integration test failed: {e}")


class TestLLMResponseModels:
    """Test Layer and Domain response models"""

    def test_layer_response_models(self):
        """Test layer response model creation"""
        from llm.models import LayerDefinitionResponse, LayerLLMSuccessResponse

        # Test LayerDefinitionResponse
        layer_def = LayerDefinitionResponse(
            definition="Test definition",
            purpose="Test purpose",
            rationale="Test rationale",
            execution_id="test-execution-id-123",
        )
        assert layer_def.definition == "Test definition"
        assert layer_def.purpose == "Test purpose"
        assert layer_def.rationale == "Test rationale"
        assert layer_def.execution_id == "test-execution-id-123"

        # Test LayerLLMSuccessResponse
        success_response = LayerLLMSuccessResponse(
            success=True, data=layer_def, execution_id="test-execution-id-123"
        )
        assert success_response.success is True
        assert success_response.data == layer_def
        assert success_response.execution_id == "test-execution-id-123"

    def test_domain_response_models(self):
        """Test domain response model creation"""
        from llm.models import DomainDefinitionResponse, DomainLLMSuccessResponse

        # Test DomainDefinitionResponse
        domain_def = DomainDefinitionResponse(
            definition="Test definition",
            purpose="Test purpose",
            scope="Test scope",
            execution_id="test-execution-id-456",
        )
        assert domain_def.definition == "Test definition"
        assert domain_def.purpose == "Test purpose"
        assert domain_def.scope == "Test scope"
        assert domain_def.execution_id == "test-execution-id-456"

        # Test DomainLLMSuccessResponse
        success_response = DomainLLMSuccessResponse(
            success=True, data=domain_def, execution_id="test-execution-id-456"
        )
        assert success_response.success is True
        assert success_response.data == domain_def
        assert success_response.execution_id == "test-execution-id-456"
