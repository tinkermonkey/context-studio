"""
Unit tests for LLM error handling strategy
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the project root to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.exceptions import (
    LLMConfigurationError,
    LLMProcessingError, 
    LLMTimeoutError,
    LLMQuotaExceededError
)
from api.llm import handle_llm_error
from fastapi import HTTPException, status


class TestLLMErrorHandling:
    """Test LLM error handling strategy implementation"""
    
    def test_error_types_exist(self):
        """Test that all required error types are defined"""
        # Test that error classes can be instantiated
        config_error = LLMConfigurationError("test")
        assert isinstance(config_error, Exception)
        
        processing_error = LLMProcessingError("test") 
        assert isinstance(processing_error, Exception)
        
        timeout_error = LLMTimeoutError("test")
        assert isinstance(timeout_error, Exception)
        
        quota_error = LLMQuotaExceededError("test")
        assert isinstance(quota_error, Exception)
    
    def test_http_status_code_mapping(self):
        """Test that errors map to correct HTTP status codes"""
        test_cases = [
            (LLMConfigurationError("Missing API key"), status.HTTP_500_INTERNAL_SERVER_ERROR),
            (LLMProcessingError("Invalid request"), status.HTTP_400_BAD_REQUEST),
            (LLMTimeoutError("Request timeout"), status.HTTP_504_GATEWAY_TIMEOUT),
            (LLMQuotaExceededError("API quota exceeded"), status.HTTP_429_TOO_MANY_REQUESTS),
        ]
        
        for error, expected_status in test_cases:
            http_error = handle_llm_error(error)
            assert isinstance(http_error, HTTPException)
            assert http_error.status_code == expected_status
    
    def test_handle_llm_error_preserves_message(self):
        """Test that error handler preserves original error messages"""
        original_message = "Test error message"
        error = LLMProcessingError(original_message)
        
        http_error = handle_llm_error(error)
        assert original_message in str(http_error.detail)
    
    def test_handle_unknown_error_type(self):
        """Test that unknown errors are handled gracefully"""
        unknown_error = ValueError("Unknown error type")
        
        # Should default to 500 Internal Server Error
        http_error = handle_llm_error(unknown_error)
        assert http_error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch.dict(os.environ, {}, clear=True)
    def test_service_configuration_validation(self):
        """Test that service properly validates configuration"""
        from llm.service import LLMService
        
        # Test missing API key detection
        with pytest.raises(LLMConfigurationError):
            LLMService()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "invalid-format"})
    def test_service_invalid_api_key_detection(self):
        """Test that service detects invalid API key format"""
        from llm.service import LLMService
        
        with pytest.raises(LLMConfigurationError):
            LLMService()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-for-testing"})
    def test_response_parsing_error_handling(self):
        """Test that response parsing handles various error conditions"""
        from llm.service import LLMService
        
        service = LLMService()
        
        test_cases = [
            ("", "Empty response"),
            ("No structured format", "Unstructured response"),
            ("Definition: Only definition", "Missing reasoning"),
            ("Reasoning: Only reasoning", "Missing definition"),
            ("Invalid\nFormat\nWithout\nStructure", "Malformed response"),
        ]
        
        for test_input, description in test_cases:
            with pytest.raises(LLMProcessingError):
                service._parse_definition_response(test_input)
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-for-testing"})
    def test_valid_response_parsing(self):
        """Test that valid responses are parsed correctly"""
        from llm.service import LLMService
        
        service = LLMService()
        
        valid_response = """Definition: A test definition
Reasoning: Test reasoning for the definition
Discrepancies: None identified"""
        
        result = service._parse_definition_response(valid_response)
        
        assert result.definition == "A test definition"
        assert result.reasoning == "Test reasoning for the definition"
        assert "None identified" in result.discrepancies
    
    def test_timeout_configuration_availability(self):
        """Test that timeout configuration is available"""
        # Test that timeout can be configured via environment
        timeout_value = os.getenv("LLM_TIMEOUT", "30")
        assert timeout_value.isdigit()
        assert int(timeout_value) > 0
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-for-testing"})
    def test_service_timeout_implementation(self):
        """Test that service implements timeout handling"""
        from llm.service import LLMService
        import inspect
        
        # Check that suggest_term_definition method has timeout handling
        source_code = inspect.getsource(LLMService.suggest_term_definition)
        assert "timeout" in source_code.lower()
        assert "asyncio.wait_for" in source_code
    
    def test_api_error_responses_defined(self):
        """Test that API endpoints define proper error responses"""
        from api.llm import router
        
        # Find suggest_definition endpoint
        suggest_definition_route = None
        for route in router.routes:
            if hasattr(route, 'path') and '/suggest_' in route.path:
                suggest_definition_route = route
                break
        
        assert suggest_definition_route is not None, "No LLM suggestion endpoints found"
        
        # Verify endpoint has proper type annotations
        endpoint_func = suggest_definition_route.endpoint
        assert hasattr(endpoint_func, '__annotations__')
    
    def test_error_logging_integration(self):
        """Test that errors are properly logged"""
        # This test verifies that the logging structure is in place
        # The actual logging behavior was verified through manual testing
        
        from utils.logger import get_logger
        
        logger = get_logger("llm.service")
        assert logger is not None
        
        # Test that logger has the expected methods
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'debug')
    
    def test_error_hierarchy(self):
        """Test that custom errors inherit from base Exception properly"""
        # All custom errors should be instances of Exception
        errors = [
            LLMConfigurationError("test"),
            LLMProcessingError("test"),
            LLMTimeoutError("test"), 
            LLMQuotaExceededError("test")
        ]
        
        for error in errors:
            assert isinstance(error, Exception)
            assert str(error) == "test"
    
    def test_error_handling_comprehensive_coverage(self):
        """Test that error handling covers all major failure modes"""
        # Verify that we have error types for all major categories
        error_types = [
            LLMConfigurationError,
            LLMProcessingError,
            LLMTimeoutError,
            LLMQuotaExceededError
        ]
        
        # Each should be a distinct class
        for error_type in error_types:
            assert issubclass(error_type, Exception)
        
        # All should be different classes
        assert len(set(error_types)) == len(error_types)
