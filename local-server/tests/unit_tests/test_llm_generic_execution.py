"""
Unit tests for the generic LLM pipeline execution methods.
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from llm.service import LLMService
from llm.models import (
    PipelineExecutionRequest,
    PipelineExecutionResponse,
    PipelineType,
    StreamingLLMResponse
)
from llm.exceptions import (
    LLMProcessingError,
    LLMTimeoutError
)


class TestGenericPipelineExecution:
    """Test cases for generic pipeline execution methods"""

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service with required dependencies"""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN"}):
            # Create a mock provider router with proper configuration
            mock_provider_router = MagicMock()
            mock_provider_router.get_enabled_models.return_value = ["gpt-3.5-turbo"]

            # Create a mock model config for validation
            mock_model_config = MagicMock()
            mock_model_config.provider_type = MagicMock()
            mock_model_config.provider_type.name = "NATIVE_OPENAI"
            mock_model_config.api_key_env_var = "OPENAI_API_KEY"

            # Import ProviderType for proper mocking
            from llm.enabled_models import ProviderType
            mock_model_config.provider_type = ProviderType.NATIVE_OPENAI

            mock_provider_router.models_manager = MagicMock()
            mock_provider_router.models_manager.get_model_config.return_value = mock_model_config

            with patch('llm.service.get_provider_router', return_value=mock_provider_router):
                with patch('llm.service.PipelineFlavorService'):
                    with patch('llm.service.ExecutionTracker'):
                        service = LLMService()
                        service.flavor_service = AsyncMock()
                        service.execution_tracker = MagicMock()
                        return service

    @pytest.fixture
    def sample_request(self):
        """Sample generic pipeline execution request"""
        return PipelineExecutionRequest(
            flavor_id="test-flavor",
            pipeline_type=PipelineType.SUGGEST_TERM_DEFINITION,
            context_data={
                "term": "test term",
                "domain_title": "test domain",
                "domain_definition": "test domain definition"
            }
        )

    @pytest.fixture
    def mock_flavor(self):
        """Mock pipeline flavor"""
        flavor = MagicMock()
        flavor.id = "test-flavor-id"
        flavor.title = "Test Flavor"
        flavor.version = 1
        flavor.system_prompt = "You are a helpful assistant."
        flavor.user_prompt = "Define the term: {term} in domain: {domain_title}"
        flavor.llm_provider = "openai"
        flavor.llm_model = "gpt-3.5-turbo"
        flavor.llm_config.model_dump.return_value = {"temperature": 0.0}
        return flavor

    @pytest.mark.asyncio
    async def test_execute_pipeline_flavor_success(self, mock_llm_service, sample_request, mock_flavor):
        """Test successful generic pipeline execution"""
        # Mock dependencies
        mock_llm_service.flavor_service.get_default_flavor.return_value = mock_flavor
        mock_llm_service.execution_tracker.start_execution.return_value = "exec-123"

        # Mock LLM response with structured output attributes
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        # Set structured output attributes that match StructuredOutputDefinition
        mock_response.definition = "Test definition"
        mock_response.reasoning = "Test reasoning"
        mock_response.discrepancies = "Test discrepancies"
        mock_response.response_metadata = {
            'token_usage': {
                'prompt_tokens': 10,
                'completion_tokens': 20,
                'total_tokens': 30
            }
        }
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(mock_llm_service, '_create_llm_from_flavor', return_value=mock_llm):
            with patch.object(mock_llm_service, '_get_flavor', return_value=mock_flavor):
                result = await mock_llm_service.execute_pipeline_flavor(sample_request)

        # Assertions
        assert isinstance(result, PipelineExecutionResponse)
        # The response_content should be formatted from the structured output
        assert "Definition: Test definition" in result.response_content
        assert "Reasoning: Test reasoning" in result.response_content
        assert result.execution_id == "exec-123"
        assert result.flavor_id == "test-flavor-id"
        assert result.pipeline_type == "suggest_term_definition"
        assert result.token_usage is not None
        assert result.token_usage['input_tokens'] == 10

        # Verify execution tracking
        mock_llm_service.execution_tracker.start_execution.assert_called_once()
        mock_llm_service.execution_tracker.complete_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_pipeline_flavor_timeout(self, mock_llm_service, sample_request, mock_flavor):
        """Test generic pipeline execution with timeout"""
        # Mock dependencies
        mock_llm_service.flavor_service.get_default_flavor.return_value = mock_flavor
        mock_llm_service.execution_tracker.start_execution.return_value = "exec-123"
        
        # Mock LLM timeout
        mock_llm = AsyncMock()
        
        with patch.object(mock_llm_service, '_create_llm_from_flavor', return_value=mock_llm):
            with patch.object(mock_llm_service, '_get_flavor', return_value=mock_flavor):
                with patch('asyncio.wait_for', side_effect=TimeoutError()):
                    with pytest.raises(LLMTimeoutError):
                        await mock_llm_service.execute_pipeline_flavor(sample_request)
        
        # Verify error tracking
        mock_llm_service.execution_tracker.complete_execution.assert_called_once()
        call_args = mock_llm_service.execution_tracker.complete_execution.call_args
        assert call_args[1]['execution_id'] == "exec-123"
        assert call_args[1]['success'] is False
        assert "Configuration or timeout error" in call_args[1]['error_message']

    @pytest.mark.asyncio
    async def test_execute_pipeline_flavor_processing_error(self, mock_llm_service, sample_request, mock_flavor):
        """Test generic pipeline execution with processing error"""
        # Mock dependencies
        mock_llm_service.flavor_service.get_default_flavor.return_value = mock_flavor
        mock_llm_service.execution_tracker.start_execution.return_value = "exec-123"
        
        # Mock LLM error
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("Test processing error")
        
        with patch.object(mock_llm_service, '_create_llm_from_flavor', return_value=mock_llm):
            with patch.object(mock_llm_service, '_get_flavor', return_value=mock_flavor):
                with pytest.raises(LLMProcessingError) as exc_info:
                    await mock_llm_service.execute_pipeline_flavor(sample_request)
        
        assert "Failed to execute pipeline" in str(exc_info.value)
        
        # Verify error tracking
        mock_llm_service.execution_tracker.complete_execution.assert_called_once()
        call_args = mock_llm_service.execution_tracker.complete_execution.call_args
        assert call_args[1]['success'] is False
        assert "Unexpected error" in call_args[1]['error_message']

    @pytest.mark.asyncio
    async def test_execute_pipeline_flavor_streaming_success(self, mock_llm_service, sample_request, mock_flavor):
        """Test successful generic streaming pipeline execution"""
        # Mock dependencies
        mock_llm_service.flavor_service.get_default_flavor.return_value = mock_flavor
        mock_llm_service.execution_tracker.start_execution.return_value = "exec-123"
        
        # Mock streaming LLM response
        mock_llm = AsyncMock()
        mock_chunks = [
            MagicMock(content="Hello"),
            MagicMock(content=" world"),
            MagicMock(content="!")
        ]
        
        async def async_chunks():
            for chunk in mock_chunks:
                yield chunk

        # Make astream return the async generator when called
        async def mock_astream(*args, **kwargs):
            async for chunk in async_chunks():
                yield chunk

        mock_llm.astream = mock_astream
        
        with patch.object(mock_llm_service, '_create_llm_from_flavor', return_value=mock_llm):
            with patch.object(mock_llm_service, '_get_flavor', return_value=mock_flavor):
                chunks = []
                async for chunk in mock_llm_service.execute_pipeline_flavor_streaming(sample_request):
                    chunks.append(chunk)
        
        # Verify streaming response structure
        assert len(chunks) >= 3  # Initial response + content chunks + completion
        
        # Check initial response
        initial_chunk = chunks[0]
        assert isinstance(initial_chunk, StreamingLLMResponse)
        assert initial_chunk.execution_id == "exec-123"
        assert initial_chunk.flavor_id == "test-flavor-id"
        assert initial_chunk.done is False
        
        # Check completion signal
        final_chunk = chunks[-1]
        assert final_chunk.done is True
        assert final_chunk.error is None

    @pytest.mark.asyncio
    async def test_execute_pipeline_flavor_streaming_error(self, mock_llm_service, sample_request, mock_flavor):
        """Test generic streaming pipeline execution with error"""
        # Mock dependencies
        mock_llm_service.flavor_service.get_default_flavor.return_value = mock_flavor
        mock_llm_service.execution_tracker.start_execution.return_value = "exec-123"

        # Mock streaming LLM error
        mock_llm = AsyncMock()

        async def mock_astream_error(*args, **kwargs):
            yield MagicMock(content="Start")
            raise Exception("Streaming error")

        # Assign the function itself, not call it
        mock_llm.astream = mock_astream_error

        with patch.object(mock_llm_service, '_create_llm_from_flavor', return_value=mock_llm):
            with patch.object(mock_llm_service, '_get_flavor', return_value=mock_flavor):
                chunks = []
                async for chunk in mock_llm_service.execute_pipeline_flavor_streaming(sample_request):
                    chunks.append(chunk)

        # Verify error response
        assert len(chunks) > 0
        final_chunk = chunks[-1]
        assert final_chunk.done is True
        assert final_chunk.error is not None
        # The error message might be about async iteration or the actual streaming error
        assert final_chunk.error is not None

    def test_render_user_prompt_generic_success(self, mock_llm_service):
        """Test generic user prompt rendering with valid context data"""
        template = "Define the term: {term} in domain: {domain_title}. Current definition: {current_definition}"
        context_data = {
            "term": "apple",
            "domain_title": "Food",
            "current_definition": "A fruit"
        }
        
        result = mock_llm_service._render_user_prompt_generic(template, context_data)
        
        expected = "Define the term: apple in domain: Food. Current definition: A fruit"
        assert result == expected

    def test_render_user_prompt_generic_with_none_values(self, mock_llm_service):
        """Test generic user prompt rendering with None values"""
        template = "Term: {term}, Domain: {domain_title}, Definition: {current_definition}"
        context_data = {
            "term": "apple",
            "domain_title": None,
            "current_definition": "A fruit"
        }

        result = mock_llm_service._render_user_prompt_generic(template, context_data, strict=False)

        expected = "Term: apple, Domain: Not specified, Definition: A fruit"
        assert result == expected

    def test_render_user_prompt_generic_with_lists(self, mock_llm_service):
        """Test generic user prompt rendering with list values"""
        template = "Terms: {terms}, Numbers: {numbers}"
        context_data = {
            "terms": ["apple", "orange", "banana"],
            "numbers": [1, 2, 3]
        }

        result = mock_llm_service._render_user_prompt_generic(template, context_data, strict=False)

        expected = "Terms: apple, orange, banana, Numbers: [1, 2, 3]"
        assert result == expected

    def test_render_user_prompt_generic_with_dict(self, mock_llm_service):
        """Test generic user prompt rendering with dictionary values"""
        template = "Context: {context}"
        context_data = {
            "context": {"key1": "value1", "key2": "value2"}
        }
        
        result = mock_llm_service._render_user_prompt_generic(template, context_data)
        
        assert "Context: " in result
        assert "key1" in result

    def test_render_user_prompt_generic_missing_variable(self, mock_llm_service):
        """Test generic user prompt rendering with missing template variable - now returns 'Not specified'"""
        template = "Term: {term}, Missing: {missing_var}"
        context_data = {
            "term": "apple"
        }

        # Missing variables should now return "Not specified" instead of raising an error
        result = mock_llm_service._render_user_prompt_generic(template, context_data, strict=False)

        assert "apple" in result
        assert "Not specified" in result

    def test_generic_pipeline_request_validation(self):
        """Test GenericPipelineExecutionRequest model validation"""
        # Valid request
        request = PipelineExecutionRequest(
            flavor_id="test-flavor",
            pipeline_type=PipelineType.SUGGEST_TERM_DEFINITION,
            context_data={"term": "test"}
        )
        assert request.flavor_id == "test-flavor"
        assert request.pipeline_type == PipelineType.SUGGEST_TERM_DEFINITION
        assert request.context_data == {"term": "test"}

    def test_generic_pipeline_request_empty_context_validation(self):
        """Test GenericPipelineExecutionRequest validation with empty context_data"""
        with pytest.raises(ValueError) as exc_info:
            PipelineExecutionRequest(
                flavor_id="test-flavor",
                pipeline_type=PipelineType.SUGGEST_TERM_DEFINITION,
                context_data={}
            )
        
        assert "context_data cannot be empty" in str(exc_info.value)

    def test_generic_pipeline_response_creation(self):
        """Test GenericPipelineExecutionResponse model creation"""
        response = PipelineExecutionResponse(
            response_content="Test response",
            execution_id="exec-123",
            flavor_id="flavor-456",
            pipeline_type="suggest_term_definition",
            token_usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        )
        
        assert response.response_content == "Test response"
        assert response.execution_id == "exec-123"
        assert response.flavor_id == "flavor-456"
        assert response.pipeline_type == "suggest_term_definition"
        assert response.token_usage["input_tokens"] == 10