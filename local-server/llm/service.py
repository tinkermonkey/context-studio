"""
LLM service for handling Langchain interactions.
"""

from typing import Optional, Dict, Any, AsyncGenerator
import os
import time
import asyncio
import string
import json
from langchain.chat_models import init_chat_model
from langchain.schema import HumanMessage, SystemMessage
from openai import RateLimitError, APITimeoutError, APIError, AuthenticationError

from .models import (
    PipelineType,
    StreamingLLMResponse,
    PipelineFlavor,
    PipelineExecutionRequest,
    PipelineExecutionResponse,
    PIPELINE_STRUCTURED_OUTPUT_MAPPING,
)
from .model_capabilities import validate_model_config
from .provider_router import get_provider_router
from .exceptions import (
    LLMConfigurationError,
    LLMProcessingError,
    LLMTimeoutError,
    LLMQuotaExceededError,
    FlavorNotFoundError,
)
from .flavor_service import PipelineFlavorService
from .execution_tracker import ExecutionTracker
from utils.logger import get_logger


class LLMService:
    """Service for handling LLM interactions using dynamic provider routing"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.flavor_service = PipelineFlavorService()
        self.execution_tracker = ExecutionTracker()

        # Initialize provider router
        self.provider_router = get_provider_router()

        # Validate that at least one model is properly configured
        self._validate_configuration()

        self.logger.info(f"LLM Service initialized with dynamic provider routing")
        self.initialized = True

    def _validate_configuration(self):
        """
        Validate that at least one model has proper API key configuration.
        This ensures fail-fast behavior at initialization time.
        """
        from .enabled_models import ProviderType

        enabled_models = self.provider_router.get_enabled_models()

        if not enabled_models:
            raise LLMConfigurationError("No models are enabled in configuration")

        # Check that at least one enabled model has a valid API key
        has_valid_config = False
        validation_errors = []

        for model_name in enabled_models:
            try:
                config = self.provider_router.models_manager.get_model_config(model_name)
                if not config:
                    continue

                # Determine the API key environment variable for this model
                if config.provider_type == ProviderType.NATIVE_OPENAI:
                    api_key_var = config.api_key_env_var or "OPENAI_API_KEY"
                    api_key = os.getenv(api_key_var)
                    if api_key:
                        # Validate OpenAI API key format
                        if not api_key.startswith("sk-"):
                            validation_errors.append(
                                f"Invalid OpenAI API key format in '{api_key_var}' (must start with 'sk-')"
                            )
                            continue
                        has_valid_config = True
                        break
                    else:
                        validation_errors.append(
                            f"Environment variable '{api_key_var}' not set for model '{model_name}'"
                        )

                elif config.provider_type == ProviderType.NATIVE_ANTHROPIC:
                    api_key_var = config.api_key_env_var or "ANTHROPIC_API_KEY"
                    api_key = os.getenv(api_key_var)
                    if api_key:
                        has_valid_config = True
                        break
                    else:
                        validation_errors.append(
                            f"Environment variable '{api_key_var}' not set for model '{model_name}'"
                        )

                elif config.provider_type == ProviderType.NATIVE_GOOGLE:
                    api_key_var = config.api_key_env_var or "GOOGLE_API_KEY"
                    api_key = os.getenv(api_key_var)
                    if api_key:
                        has_valid_config = True
                        break
                    else:
                        validation_errors.append(
                            f"Environment variable '{api_key_var}' not set for model '{model_name}'"
                        )

                elif config.provider_type == ProviderType.OPENROUTER:
                    api_key_var = config.api_key_env_var or "OPENROUTER_API_KEY"
                    api_key = os.getenv(api_key_var)
                    if api_key:
                        has_valid_config = True
                        break
                    else:
                        validation_errors.append(
                            f"Environment variable '{api_key_var}' not set for model '{model_name}'"
                        )

            except Exception as e:
                validation_errors.append(f"Error validating model '{model_name}': {str(e)}")
                continue

        if not has_valid_config:
            error_msg = "No valid API key configuration found for any enabled model"
            if validation_errors:
                error_msg += f": {'; '.join(validation_errors)}"
            raise LLMConfigurationError(error_msg)

    def is_configured(self) -> bool:
        """Check if the LLM service is properly configured with at least one valid model"""
        try:
            self._validate_configuration()
            return True
        except LLMConfigurationError:
            return False

    def is_initialized(self) -> bool:
        """Check if the LLM service is properly initialized"""
        return self.initialized

    def get_available_models(self) -> list[str]:
        """Get list of currently available (enabled) models"""
        return self.provider_router.get_enabled_models()

    def is_model_available(self, model_name: str) -> bool:
        """Check if a specific model is available"""
        return self.provider_router.is_model_available(model_name)

    def get_provider_for_model(self, model_name: str) -> Optional[str]:
        """Get the provider type for a model"""
        provider_type = self.provider_router.get_provider_for_model(model_name)
        return provider_type.value if provider_type else None

    async def execute_pipeline_flavor(self, request: PipelineExecutionRequest) -> PipelineExecutionResponse:
        """Generic pipeline execution method with arbitrary context data"""
        start_time = time.time()
        execution_id = "unknown"

        self.logger.info(
            f"Starting generic pipeline execution - Type: {request.pipeline_type}, Flavor: {request.flavor_id}"
        )
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
                user_prompt=user_prompt,
            )

            # Get structured output class for this pipeline type
            structured_output_class = PIPELINE_STRUCTURED_OUTPUT_MAPPING.get(request.pipeline_type)

            # Initialize LLM with flavor configuration and structured output
            llm = self._create_llm_from_flavor(flavor, structured_output_class)

            messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

            # Add timeout to the async call
            timeout = int(os.getenv("LLM_TIMEOUT", "30"))
            try:
                response = await asyncio.wait_for(llm.ainvoke(messages), timeout=timeout)
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"LLM request timed out after {timeout} seconds for pipeline: {request.pipeline_type}"
                )
                raise LLMTimeoutError(f"Request timed out after {timeout} seconds")

            # Track token usage if available
            token_usage = None
            if hasattr(response, "response_metadata") and response.response_metadata.get("token_usage"):
                usage = response.response_metadata["token_usage"]
                token_usage = {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }

            # Handle structured output using generic parsing
            structured_output, response_content = self._process_response_with_structured_output(
                response, structured_output_class, request.pipeline_type
            )

            # Complete execution tracking
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message=response_content,
                success=True,
                token_usage=token_usage,
                start_time=start_time,
                structured_output=structured_output,
            )

            self.logger.info(
                f"Successfully executed generic pipeline - Type: {request.pipeline_type}, Flavor: '{flavor.title}', execution: {execution_id}"
            )

            return PipelineExecutionResponse(
                response_content=response_content,
                execution_id=execution_id,
                flavor_id=flavor.id,
                pipeline_type=request.pipeline_type.value,
                token_usage=token_usage,
                structured_output=structured_output,
            )

        except (LLMConfigurationError, LLMTimeoutError):
            # Complete execution tracking with error
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message="Configuration or timeout error",
                start_time=start_time,
            )
            raise
        except RateLimitError as e:
            self.logger.warning(f"OpenAI rate limit exceeded for pipeline {request.pipeline_type}: {e}")
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message=f"Rate limit exceeded: {str(e)}",
                start_time=start_time,
            )
            raise LLMQuotaExceededError(f"API rate limit exceeded: {str(e)}")
        except APITimeoutError as e:
            self.logger.warning(f"OpenAI API timeout for pipeline {request.pipeline_type}: {e}")
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message=f"API timeout: {str(e)}",
                start_time=start_time,
            )
            raise LLMTimeoutError(f"API request timeout: {str(e)}")
        except AuthenticationError as e:
            self.logger.error(f"OpenAI authentication error for pipeline {request.pipeline_type}: {e}")
            self.execution_tracker.complete_execution(
                execution_id=execution_id,
                response_message="",
                success=False,
                error_message=f"Authentication failed: {str(e)}",
                start_time=start_time,
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
                start_time=start_time,
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
                start_time=start_time,
            )
            raise LLMProcessingError(f"Failed to execute pipeline: {str(e)}")

    async def execute_pipeline_flavor_streaming(
        self, request: PipelineExecutionRequest
    ) -> AsyncGenerator[StreamingLLMResponse, None]:
        """Generic streaming pipeline execution method with arbitrary context data"""
        execution_id = "unknown"

        self.logger.info(
            f"Starting generic streaming pipeline execution - Type: {request.pipeline_type}, Flavor: {request.flavor_id}"
        )
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
                user_prompt=user_prompt,
            )

            # Initialize LLM with flavor configuration
            llm = self._create_llm_from_flavor(flavor)

            messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

            # Send initial response with execution_id
            yield StreamingLLMResponse(flavor_id=flavor.id, execution_id=execution_id, done=False)

            # Stream the response
            async for chunk in llm.astream(messages):
                if hasattr(chunk, "content") and chunk.content:
                    yield StreamingLLMResponse(token=chunk.content, flavor_id=flavor.id, done=False)

            # Send completion signal
            yield StreamingLLMResponse(flavor_id=flavor.id, done=True)

        except Exception as e:
            self.logger.error(f"Error in streaming generic pipeline execution: {e}")
            yield StreamingLLMResponse(
                flavor_id=flavor.id if "flavor" in locals() else "unknown", done=True, error=str(e)
            )

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

    def _create_llm_from_flavor(self, flavor: PipelineFlavor, structured_output_class=None):
        """Create LLM instance with automatic capability detection and parameter validation"""
        # Create base LLM with validated configuration
        llm = self._create_base_llm(flavor)

        # Add structured output if specified
        if structured_output_class:
            try:
                # Suppress LangChain warnings about method selection by using a warning filter
                import warnings

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="langchain_openai")
                    structured_llm = llm.with_structured_output(structured_output_class)

                self.logger.debug(f"Structured output enabled for {flavor.llm_model}")
                return structured_llm

            except Exception as e:
                self.logger.warning(
                    f"Structured output not available for {flavor.llm_model}: {e}. " f"Will use text parsing fallback."
                )
                return llm

        return llm

    def _create_base_llm(self, flavor: PipelineFlavor):
        """Create base LLM with validated configuration parameters using provider router"""
        config = flavor.llm_config.model_dump()

        # Remove None values to avoid passing empty parameters
        filtered_config = {k: v for k, v in config.items() if v is not None}

        self.logger.debug(f"Creating {flavor.llm_model} with config: {list(filtered_config.keys())}")

        # Use provider router to get appropriate LLM
        provider_router = get_provider_router()

        try:
            return provider_router.get_llm_for_model(flavor.llm_model, **filtered_config)
        except Exception as e:
            self.logger.error(f"Failed to create LLM for model {flavor.llm_model}: {e}")
            # Fallback to legacy hardcoded behavior if provider routing fails
            self.logger.warning("Falling back to legacy LLM creation")
            return self._create_legacy_llm(flavor.llm_model, filtered_config)

    def _create_legacy_llm(self, model_name: str, config: dict):
        """Legacy LLM creation for backward compatibility"""
        # Validate and filter configuration based on model capabilities
        filtered_config, warnings = validate_model_config(model_name, config)

        # Log any parameter adjustments
        for warning in warnings:
            self.logger.warning(warning)

        # Remove None values to avoid passing empty parameters
        filtered_config = {k: v for k, v in filtered_config.items() if v is not None}

        # Default to OpenAI for legacy compatibility
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise LLMConfigurationError("OPENAI_API_KEY environment variable not set")

        return init_chat_model(
            model=model_name, model_provider="openai", openai_api_key=openai_api_key, **filtered_config
        )

    def _process_response_with_structured_output(
        self, response: Any, structured_output_class: Optional[type], pipeline_type: PipelineType
    ) -> tuple[Optional[Dict[str, Any]], str]:
        """
        Process LLM response with structured output, handling both direct structured responses
        and fallback text parsing.

        Returns:
            tuple: (structured_output_dict, response_content_string)
        """
        structured_output = None
        response_content = ""

        if structured_output_class:
            # First, try to extract structured output from LangChain structured response
            structured_output = self._extract_structured_output_from_response(response, structured_output_class)

            if structured_output:
                # Convert structured output back to text for compatibility
                response_content = self._structured_output_to_text(structured_output, structured_output_class)
                self.logger.debug(
                    f"Successfully extracted structured output using LangChain for pipeline {pipeline_type}"
                )
            else:
                # Fall back to text parsing
                self.logger.warning(
                    f"LangChain structured output failed for pipeline {pipeline_type}, falling back to regex parsing"
                )
                response_content = response.content if hasattr(response, "content") else str(response)
                structured_output = self._parse_structured_output_from_text(
                    response_content, structured_output_class, pipeline_type
                )
        else:
            # No structured output expected, just get the text content
            response_content = response.content if hasattr(response, "content") else str(response)
            self.logger.debug(f"No structured output class configured for pipeline {pipeline_type}")

        return structured_output, response_content

    def _extract_structured_output_from_response(
        self, response: Any, structured_output_class: type
    ) -> Optional[Dict[str, Any]]:
        """Extract structured output from LangChain structured response object."""
        try:
            if not structured_output_class:
                return None

            # Get field names from the Pydantic model
            field_names = list(structured_output_class.model_fields.keys())

            # Check if response has the expected structured output attributes
            if not any(hasattr(response, field_name) for field_name in field_names):
                return None

            # Extract all fields defined in the structured output class
            extracted_data = {}
            for field_name in field_names:
                value = getattr(response, field_name, None)
                # Convert empty strings to None for optional fields
                if value == "":
                    value = None
                extracted_data[field_name] = value

            # Validate that at least one required field has content
            required_fields = [
                name for name, field in structured_output_class.model_fields.items() if field.is_required()
            ]

            if required_fields and not any(extracted_data.get(field) for field in required_fields):
                return None

            return extracted_data

        except Exception as e:
            self.logger.warning(f"Failed to extract structured output from response: {e}")
            return None

    def _structured_output_to_text(self, structured_output: Dict[str, Any], structured_output_class: type) -> str:
        """Convert structured output dictionary back to formatted text."""
        try:
            field_names = list(structured_output_class.model_fields.keys())
            text_parts = []

            for field_name in field_names:
                value = structured_output.get(field_name)
                if value:
                    # Capitalize field name for display
                    display_name = field_name.replace("_", " ").title()
                    text_parts.append(f"{display_name}: {value}")

            return "\n".join(text_parts)

        except Exception as e:
            self.logger.warning(f"Failed to convert structured output to text: {e}")
            # Fallback to simple formatting
            return str(structured_output)

    def _parse_structured_output_from_text(
        self, response_content: str, structured_output_class: type, pipeline_type: PipelineType
    ) -> Optional[Dict[str, Any]]:
        """Parse structured output from raw text response using regex based on Pydantic model fields."""
        try:
            if not structured_output_class:
                return None

            import re

            # Get field names from the Pydantic model
            field_names = list(structured_output_class.model_fields.keys())
            parsed_output = {}

            # Create regex patterns dynamically based on field names
            for field_name in field_names:
                # Convert field_name to display format (e.g., "definition" -> "Definition")
                display_name = field_name.replace("_", " ").title()

                # Create pattern to match "FieldName: content" format
                # Match until next field name or end of string
                next_fields = [fn.replace("_", " ").title() for fn in field_names if fn != field_name]
                if next_fields:
                    next_pattern = "|".join(re.escape(f"{nf}:") for nf in next_fields)
                    pattern = rf"{re.escape(display_name)}:\s*(.+?)(?=\n(?:{next_pattern})|$)"
                else:
                    pattern = rf"{re.escape(display_name)}:\s*(.+?)(?=\n|$)"

                match = re.search(pattern, response_content, re.DOTALL)
                if match:
                    value = match.group(1).strip()
                    # Convert empty strings to None
                    parsed_output[field_name] = value if value else None
                else:
                    parsed_output[field_name] = None

            # Validate that at least one required field has content
            required_fields = [
                name for name, field in structured_output_class.model_fields.items() if field.is_required()
            ]

            if required_fields and not any(parsed_output.get(field) for field in required_fields):
                self.logger.warning(f"No required fields found in text parsing for pipeline {pipeline_type}")
                return None

            self.logger.info(f"Successfully parsed structured output from text for pipeline {pipeline_type}")
            return parsed_output

        except Exception as e:
            self.logger.error(f"Failed to parse structured output from text for pipeline {pipeline_type}: {e}")
            return None

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

            # Use a custom formatter that provides default values for missing variables
            class SafeFormatter(string.Formatter):
                def get_value(self, key, args, kwargs):
                    if isinstance(key, str):
                        try:
                            return kwargs[key]
                        except KeyError:
                            # Return default value for missing variables
                            return "Not specified"
                    else:
                        return super().get_value(key, args, kwargs)

            # Render the template with the safe context data using the custom formatter
            formatter = SafeFormatter()
            rendered_prompt = formatter.format(template, **safe_context)

            self.logger.debug(
                f"Successfully rendered generic user prompt template (length: {len(rendered_prompt)} chars)"
            )
            return rendered_prompt

        except KeyError as e:
            self.logger.error(f"Missing template variable in user prompt template: {e}")
            raise LLMProcessingError(f"Template rendering failed: missing variable {str(e)}")
        except Exception as e:
            self.logger.error(f"Error rendering generic user prompt template: {e}")
            raise LLMProcessingError(f"Template rendering failed: {str(e)}")
