"""
LLM service for handling Langchain interactions.
"""

from typing import Optional, Dict, Any, AsyncGenerator
import os
import time
import asyncio
from langchain.chat_models import init_chat_model
from langchain.schema import HumanMessage, SystemMessage
from openai import RateLimitError, APITimeoutError, APIError, AuthenticationError

from .models import (
    PipelineType,
    StreamingLLMResponse,
    PipelineFlavor,
    GenericPipelineExecutionRequest,
    GenericPipelineExecutionResponse
)
from .exceptions import (
    LLMConfigurationError, 
    LLMProcessingError, 
    LLMTimeoutError, 
    LLMQuotaExceededError,
    FlavorNotFoundError
)
from .flavor_service import PipelineFlavorService
from .execution_tracker import ExecutionTracker
from utils.logger import get_logger


class LLMService:
    """Service for handling LLM interactions using Langchain"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo", temperature: float = 0):
        self.logger = get_logger(__name__)
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None
        self.flavor_service = PipelineFlavorService()
        self.execution_tracker = ExecutionTracker()
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the LLM with proper configuration"""
        try:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                self.logger.error("OPENAI_API_KEY environment variable not set")
                raise LLMConfigurationError("OPENAI_API_KEY environment variable not set")
            
            # Validate API key format (basic check)
            if not openai_api_key.startswith("sk-"):
                self.logger.error("Invalid OpenAI API key format")
                raise LLMConfigurationError("Invalid OpenAI API key format")
            
            self.logger.debug(f"Initializing LLM with model: {self.model_name}, temperature: {self.temperature}")
            
            self._llm = init_chat_model(
                self.model_name,
                model_provider="openai",
                temperature=self.temperature,
                openai_api_key=openai_api_key
            )
            self.logger.info(f"LLM initialized successfully with model: {self.model_name}")
            
        except LLMConfigurationError:
            # Re-raise our custom errors as-is
            raise
        except AuthenticationError as e:
            self.logger.error(f"OpenAI authentication failed: {e}")
            raise LLMConfigurationError(f"OpenAI authentication failed: {str(e)}")
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM: {e}")
            raise LLMConfigurationError(f"LLM initialization failed: {str(e)}")
    
    
    
    
    async def execute_pipeline_flavor(self, request: GenericPipelineExecutionRequest) -> GenericPipelineExecutionResponse:
        """Generic pipeline execution method with arbitrary context data"""
        start_time = time.time()
        execution_id = "unknown"
        
        self.logger.info(f"Starting generic pipeline execution - Type: {request.pipeline_type}, Flavor: {request.flavor_id}")
        self.logger.debug(f"Context data keys: {list(request.context_data.keys())}")
        
        try:
            # Get flavor
            flavor = await self._get_flavor(request.pipeline_type, request.flavor_id)
            
            # Create prompt using flavor templates and generic context data
            system_prompt = flavor.system_prompt
            user_prompt = self._render_user_prompt_generic(flavor.user_prompt, request.context_data)
            
            # Start execution tracking
            execution_id = self.execution_tracker.start_execution(
                pipeline_flavor_id=flavor.id,
                pipeline_type=request.pipeline_type.value,
                pipeline_flavor_version=flavor.version,
                request=request,
                user_prompt=user_prompt
            )
            
            # Initialize LLM with flavor configuration
            llm = self._create_llm_from_flavor(flavor)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Add timeout to the async call
            timeout = int(os.getenv("LLM_TIMEOUT", "30"))
            try:
                response = await asyncio.wait_for(
                    llm.ainvoke(messages), 
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                self.logger.warning(f"LLM request timed out after {timeout} seconds for pipeline: {request.pipeline_type}")
                raise LLMTimeoutError(f"Request timed out after {timeout} seconds")
            
            # Track token usage if available
            token_usage = None
            if hasattr(response, 'response_metadata') and response.response_metadata.get('token_usage'):
                usage = response.response_metadata['token_usage']
                token_usage = {
                    'input_tokens': usage.get('prompt_tokens', 0),
                    'output_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0)
                }
            
            # Complete execution tracking
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message=response.content,
                success=True,
                token_usage=token_usage,
                start_time=start_time
            )
            
            self.logger.info(f"Successfully executed generic pipeline - Type: {request.pipeline_type}, Flavor: '{flavor.title}', execution: {execution_id}")
            
            return GenericPipelineExecutionResponse(
                response_content=response.content,
                execution_id=execution_id,
                flavor_id=flavor.id,
                pipeline_type=request.pipeline_type.value,
                token_usage=token_usage
            )
            
        except (LLMConfigurationError, LLMTimeoutError):
            # Complete execution tracking with error
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message="Configuration or timeout error",
                start_time=start_time
            )
            raise
        except RateLimitError as e:
            self.logger.warning(f"OpenAI rate limit exceeded for pipeline {request.pipeline_type}: {e}")
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message=f"Rate limit exceeded: {str(e)}",
                start_time=start_time
            )
            raise LLMQuotaExceededError(f"API rate limit exceeded: {str(e)}")
        except APITimeoutError as e:
            self.logger.warning(f"OpenAI API timeout for pipeline {request.pipeline_type}: {e}")
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message=f"API timeout: {str(e)}",
                start_time=start_time
            )
            raise LLMTimeoutError(f"API request timeout: {str(e)}")
        except AuthenticationError as e:
            self.logger.error(f"OpenAI authentication error for pipeline {request.pipeline_type}: {e}")
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message=f"Authentication failed: {str(e)}",
                start_time=start_time
            )
            raise LLMConfigurationError(f"Authentication failed: {str(e)}")
        except APIError as e:
            self.logger.error(f"OpenAI API error for pipeline {request.pipeline_type}: {e}")
            error_msg = f"API error: {str(e)}"
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message=error_msg,
                start_time=start_time
            )
            # Check if it's a quota/billing issue
            if "quota" in str(e).lower() or "billing" in str(e).lower():
                raise LLMQuotaExceededError(f"API quota/billing error: {str(e)}")
            else:
                raise LLMProcessingError(error_msg)
        except Exception as e:
            self.logger.error(f"Unexpected error executing pipeline {request.pipeline_type}: {e}")
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message=f"Unexpected error: {str(e)}",
                start_time=start_time
            )
            raise LLMProcessingError(f"Failed to execute pipeline: {str(e)}")

    async def execute_pipeline_flavor_streaming(self, request: GenericPipelineExecutionRequest) -> AsyncGenerator[StreamingLLMResponse, None]:
        """Generic streaming pipeline execution method with arbitrary context data"""
        execution_id = "unknown"
        
        self.logger.info(f"Starting generic streaming pipeline execution - Type: {request.pipeline_type}, Flavor: {request.flavor_id}")
        self.logger.debug(f"Context data keys: {list(request.context_data.keys())}")
        
        try:
            # Get flavor
            flavor = await self._get_flavor(request.pipeline_type, request.flavor_id)
            
            # Create prompt using flavor templates and generic context data
            system_prompt = flavor.system_prompt
            user_prompt = self._render_user_prompt_generic(flavor.user_prompt, request.context_data)
            
            # Start execution tracking
            execution_id = self.execution_tracker.start_execution(
                pipeline_flavor_id=flavor.id,
                pipeline_type=request.pipeline_type.value,
                pipeline_flavor_version=flavor.version,
                request=request,
                user_prompt=user_prompt
            )
            
            # Initialize LLM with flavor configuration
            llm = self._create_llm_from_flavor(flavor)
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Send initial response with execution_id
            yield StreamingLLMResponse(
                flavor_id=flavor.id,
                execution_id=execution_id,
                done=False
            )
            
            # Stream the response
            async for chunk in llm.astream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    yield StreamingLLMResponse(
                        token=chunk.content,
                        flavor_id=flavor.id,
                        done=False
                    )
            
            # Send completion signal
            yield StreamingLLMResponse(
                flavor_id=flavor.id,
                done=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in streaming generic pipeline execution: {e}")
            yield StreamingLLMResponse(
                flavor_id=flavor.id if 'flavor' in locals() else "unknown",
                done=True,
                error=str(e)
            )

    

    
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model configuration"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "provider": "openai",
            "initialized": self._llm is not None
        }
    
    
    async def _get_flavor(self, pipeline: PipelineType, flavor_identifier: Optional[str]) -> PipelineFlavor:
        """Get flavor by ID, title, or default"""
        if not flavor_identifier:
            return await self.flavor_service.get_default_flavor(pipeline)
        
        # Check for default flavor by ID or title
        if flavor_identifier == "default" or flavor_identifier.lower() == "default":
            return await self.flavor_service.get_default_flavor(pipeline)
        
        # Try by ID first (for user-created flavors)
        try:
            return await self.flavor_service.get_flavor_by_id(flavor_identifier)
        except FlavorNotFoundError:
            pass
        
        # Try by title (for user-created flavors)
        try:
            return await self.flavor_service.get_flavor_by_title(pipeline, flavor_identifier)
        except FlavorNotFoundError:
            self.logger.warning(f"Flavor '{flavor_identifier}' not found, using default")
            return await self.flavor_service.get_default_flavor(pipeline)
    
    def _create_llm_from_flavor(self, flavor: PipelineFlavor):
        """Create LLM instance from flavor configuration"""
        config = flavor.llm_config.model_dump()
        
        # Filter out parameters not supported by specific providers
        if flavor.llm_provider.lower() == 'openai':
            # OpenAI doesn't support top_k parameter
            config.pop('top_k', None)
        elif flavor.llm_provider.lower() in ['anthropic', 'claude']:
            # Anthropic might have different parameter restrictions
            # Add filtering as needed
            pass
        
        # Remove None values to avoid passing empty parameters
        config = {k: v for k, v in config.items() if v is not None}
        
        return init_chat_model(
            model=flavor.llm_model,
            model_provider=flavor.llm_provider,
            **config
        )
    
    def _render_user_prompt_generic(self, template: str, context_data: Dict[str, Any]) -> str:
        """Render user prompt template with arbitrary context data"""
        self.logger.debug("Rendering generic user prompt template with context data")
        
        try:
            # Create a safe copy of context_data with None values replaced
            safe_context = {}
            for key, value in context_data.items():
                if value is None:
                    safe_context[key] = "Not specified"
                elif isinstance(value, (list, tuple)):
                    # Handle lists by joining them or converting to string
                    if all(isinstance(item, str) for item in value):
                        safe_context[key] = ", ".join(value) if value else "Not specified"
                    else:
                        safe_context[key] = str(value) if value else "Not specified"
                elif isinstance(value, dict):
                    # Handle dictionaries by converting to string representation
                    safe_context[key] = str(value) if value else "Not specified"
                else:
                    safe_context[key] = str(value)
            
            # Render the template with the safe context data
            rendered_prompt = template.format(**safe_context)
            
            self.logger.debug(f"Successfully rendered generic user prompt template (length: {len(rendered_prompt)} chars)")
            return rendered_prompt
            
        except KeyError as e:
            self.logger.error(f"Missing template variable: {e}")
            raise LLMProcessingError(f"Template rendering failed - missing variable: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error rendering generic user prompt template: {e}")
            raise LLMProcessingError(f"Template rendering failed: {str(e)}")

