"""
LLM service for handling Langchain interactions.
"""

from typing import Optional, Dict, Any, AsyncGenerator
import os
import asyncio
from langchain.chat_models import init_chat_model
from langchain.schema import HumanMessage, SystemMessage
from openai import RateLimitError, APITimeoutError, APIError, AuthenticationError

from .models import (
    DefinitionSuggestionRequest, 
    DefinitionSuggestionResponse,
    LayerDefinitionRequest,
    LayerDefinitionResponse,
    DomainDefinitionRequest,
    DomainDefinitionResponse,
    PipelineType,
    StreamingLLMResponse,
    PipelineFlavor
)
from .prompts import DefinitionPromptTemplate
from .exceptions import (
    LLMConfigurationError, 
    LLMProcessingError, 
    LLMTimeoutError, 
    LLMQuotaExceededError,
    FlavorNotFoundError
)
from .flavor_service import PipelineFlavorService
from utils.logger import get_logger


class LLMService:
    """Service for handling LLM interactions using Langchain"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo", temperature: float = 0):
        self.logger = get_logger(__name__)
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None
        self.flavor_service = PipelineFlavorService()
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
    
    async def suggest_term_definition_streaming(
        self, 
        request: DefinitionSuggestionRequest,
        flavor_id: Optional[str] = None
    ) -> AsyncGenerator[StreamingLLMResponse, None]:
        """Stream term definition suggestion using specified flavor"""
        
        # Get flavor
        flavor = await self._get_flavor(PipelineType.SUGGEST_TERM_DEFINITION, flavor_id or request.flavor)
        
        # Initialize LLM with flavor configuration
        llm = self._create_llm_from_flavor(flavor)
        
        # Create prompt using flavor templates
        system_prompt = flavor.system_prompt
        user_prompt = self._render_user_prompt(flavor.user_prompt, request)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
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
            self.logger.error(f"Error in streaming LLM request: {e}")
            yield StreamingLLMResponse(
                flavor_id=flavor.id,
                done=True,
                error=str(e)
            )
    
    async def suggest_layer_definition_streaming(
        self, 
        request: LayerDefinitionRequest,
        flavor_id: Optional[str] = None
    ) -> AsyncGenerator[StreamingLLMResponse, None]:
        """Stream layer definition suggestion using specified flavor"""
        
        # Get flavor
        flavor = await self._get_flavor(PipelineType.SUGGEST_LAYER_DEFINITION, flavor_id or request.flavor)
        
        # Initialize LLM with flavor configuration
        llm = self._create_llm_from_flavor(flavor)
        
        # Create prompt using flavor templates
        system_prompt = flavor.system_prompt
        user_prompt = self._render_user_prompt(flavor.user_prompt, request)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
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
            self.logger.error(f"Error in streaming layer definition request: {e}")
            yield StreamingLLMResponse(
                flavor_id=flavor.id,
                done=True,
                error=str(e)
            )
    
    async def suggest_domain_definition_streaming(
        self, 
        request: DomainDefinitionRequest,
        flavor_id: Optional[str] = None
    ) -> AsyncGenerator[StreamingLLMResponse, None]:
        """Stream domain definition suggestion using specified flavor"""
        
        # Get flavor
        flavor = await self._get_flavor(PipelineType.SUGGEST_DOMAIN_DEFINITION, flavor_id or request.flavor)
        
        # Initialize LLM with flavor configuration
        llm = self._create_llm_from_flavor(flavor)
        
        # Create prompt using flavor templates
        system_prompt = flavor.system_prompt
        user_prompt = self._render_user_prompt(flavor.user_prompt, request)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
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
            self.logger.error(f"Error in streaming domain definition request: {e}")
            yield StreamingLLMResponse(
                flavor_id=flavor.id,
                done=True,
                error=str(e)
            )
    
    async def suggest_term_definition(self, request: DefinitionSuggestionRequest) -> DefinitionSuggestionResponse:
        """Generate a term definition suggestion based on provided context"""
        self.logger.info(f"Starting term definition suggestion for term: '{request.term}'")
        self.logger.debug(f"Request details - Domain: {request.domain_title}, Parent: {request.parent_term_title}")
        
        try:
            # Get flavor (use default if none specified)
            flavor = await self._get_flavor(PipelineType.SUGGEST_TERM_DEFINITION, request.flavor)
            
            # Initialize LLM with flavor configuration
            llm = self._create_llm_from_flavor(flavor)
            
            # Create prompt using flavor templates
            system_prompt = flavor.system_prompt
            user_prompt = self._render_user_prompt(flavor.user_prompt, request)
            
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
                self.logger.warning(f"LLM request timed out after {timeout} seconds for term: '{request.term}'")
                raise LLMTimeoutError(f"Request timed out after {timeout} seconds")
            
            # Parse the response using the exact format from requirements
            parsed_response = self._parse_definition_response(response.content)
            
            self.logger.info(f"Successfully generated term definition for term: '{request.term}' using flavor '{flavor.title}'")
            return parsed_response
            
        except LLMConfigurationError:
            # Re-raise configuration errors as-is
            raise
        except LLMTimeoutError:
            # Re-raise timeout errors as-is
            raise
        except RateLimitError as e:
            self.logger.warning(f"OpenAI rate limit exceeded for term '{request.term}': {e}")
            raise LLMQuotaExceededError(f"API rate limit exceeded: {str(e)}")
        except APITimeoutError as e:
            self.logger.warning(f"OpenAI API timeout for term '{request.term}': {e}")
            raise LLMTimeoutError(f"API request timeout: {str(e)}")
        except AuthenticationError as e:
            self.logger.error(f"OpenAI authentication error for term '{request.term}': {e}")
            raise LLMConfigurationError(f"Authentication failed: {str(e)}")
        except APIError as e:
            self.logger.error(f"OpenAI API error for term '{request.term}': {e}")
            # Check if it's a quota/billing issue
            if "quota" in str(e).lower() or "billing" in str(e).lower():
                raise LLMQuotaExceededError(f"API quota/billing error: {str(e)}")
            else:
                raise LLMProcessingError(f"API error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error generating term definition for term '{request.term}': {e}")
            raise LLMProcessingError(f"Failed to generate term definition: {str(e)}")
    
    async def suggest_layer_definition(self, request: LayerDefinitionRequest) -> LayerDefinitionResponse:
        """Generate a layer definition suggestion based on provided context"""
        self.logger.info(f"Starting layer definition suggestion for layer: '{request.layer_title}'")
        self.logger.debug(f"Request details - Parent: {request.parent_layer_title}, Domains: {len(request.contained_domains)}")
        
        try:
            # Get flavor (use default if none specified)
            flavor = await self._get_flavor(PipelineType.SUGGEST_LAYER_DEFINITION, request.flavor)
            
            # Initialize LLM with flavor configuration
            llm = self._create_llm_from_flavor(flavor)
            
            # Create prompt using flavor templates
            system_prompt = flavor.system_prompt
            user_prompt = self._render_user_prompt(flavor.user_prompt, request)
            
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
                self.logger.warning(f"LLM request timed out after {timeout} seconds for layer: '{request.layer_title}'")
                raise LLMTimeoutError(f"Request timed out after {timeout} seconds")
            
            # Parse the response
            parsed_response = self._parse_layer_definition_response(response.content)
            
            self.logger.info(f"Successfully generated layer definition for layer: '{request.layer_title}' using flavor '{flavor.title}'")
            return parsed_response
            
        except LLMConfigurationError:
            # Re-raise configuration errors as-is
            raise
        except LLMTimeoutError:
            # Re-raise timeout errors as-is
            raise
        except RateLimitError as e:
            self.logger.warning(f"OpenAI rate limit exceeded for layer '{request.layer_title}': {e}")
            raise LLMQuotaExceededError(f"API rate limit exceeded: {str(e)}")
        except APITimeoutError as e:
            self.logger.warning(f"OpenAI API timeout for layer '{request.layer_title}': {e}")
            raise LLMTimeoutError(f"API request timeout: {str(e)}")
        except AuthenticationError as e:
            self.logger.error(f"OpenAI authentication error for layer '{request.layer_title}': {e}")
            raise LLMConfigurationError(f"Authentication failed: {str(e)}")
        except APIError as e:
            self.logger.error(f"OpenAI API error for layer '{request.layer_title}': {e}")
            # Check if it's a quota/billing issue
            if "quota" in str(e).lower() or "billing" in str(e).lower():
                raise LLMQuotaExceededError(f"API quota/billing error: {str(e)}")
            else:
                raise LLMProcessingError(f"API error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error generating layer definition for layer '{request.layer_title}': {e}")
            raise LLMProcessingError(f"Failed to generate layer definition: {str(e)}")

    async def suggest_domain_definition(self, request: DomainDefinitionRequest) -> DomainDefinitionResponse:
        """Generate a domain definition suggestion based on provided context"""
        self.logger.info(f"Starting domain definition suggestion for domain: '{request.domain_title}'")
        self.logger.debug(f"Request details - Layer: {request.layer_title}, Terms: {len(request.contained_terms)}")
        
        try:
            # Get flavor (use default if none specified)
            flavor = await self._get_flavor(PipelineType.SUGGEST_DOMAIN_DEFINITION, request.flavor)
            
            # Initialize LLM with flavor configuration
            llm = self._create_llm_from_flavor(flavor)
            
            # Create prompt using flavor templates
            system_prompt = flavor.system_prompt
            user_prompt = self._render_user_prompt(flavor.user_prompt, request)
            
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
                self.logger.warning(f"LLM request timed out after {timeout} seconds for domain: '{request.domain_title}'")
                raise LLMTimeoutError(f"Request timed out after {timeout} seconds")
            
            # Parse the response
            parsed_response = self._parse_domain_definition_response(response.content)
            
            self.logger.info(f"Successfully generated domain definition for domain: '{request.domain_title}' using flavor '{flavor.title}'")
            return parsed_response
            
        except LLMConfigurationError:
            # Re-raise configuration errors as-is
            raise
        except LLMTimeoutError:
            # Re-raise timeout errors as-is
            raise
        except RateLimitError as e:
            self.logger.warning(f"OpenAI rate limit exceeded for domain '{request.domain_title}': {e}")
            raise LLMQuotaExceededError(f"API rate limit exceeded: {str(e)}")
        except APITimeoutError as e:
            self.logger.warning(f"OpenAI API timeout for domain '{request.domain_title}': {e}")
            raise LLMTimeoutError(f"API request timeout: {str(e)}")
        except AuthenticationError as e:
            self.logger.error(f"OpenAI authentication error for domain '{request.domain_title}': {e}")
            raise LLMConfigurationError(f"Authentication failed: {str(e)}")
        except APIError as e:
            self.logger.error(f"OpenAI API error for domain '{request.domain_title}': {e}")
            # Check if it's a quota/billing issue
            if "quota" in str(e).lower() or "billing" in str(e).lower():
                raise LLMQuotaExceededError(f"API quota/billing error: {str(e)}")
            else:
                raise LLMProcessingError(f"API error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error generating domain definition for domain '{request.domain_title}': {e}")
            raise LLMProcessingError(f"Failed to generate domain definition: {str(e)}")
    
    def _parse_definition_response(self, response_text: str) -> DefinitionSuggestionResponse:
        """Parse the LLM response in the exact format specified in requirements"""
        self.logger.debug(f"Parsing LLM response (length: {len(response_text)} chars)")
        
        if not response_text or not response_text.strip():
            self.logger.error("Empty response from LLM")
            raise LLMProcessingError("Empty response from LLM")
        
        lines = response_text.strip().split('\n')
        definition = ""
        reasoning = ""
        discrepancies = None
        
        try:
            for line in lines:
                line = line.strip()
                if line.startswith("Definition:"):
                    definition = line[len("Definition:"):].strip()
                elif line.startswith("Reasoning:"):
                    reasoning = line[len("Reasoning:"):].strip()
                elif line.startswith("Discrepancies:"):
                    discrepancies_text = line[len("Discrepancies:"):].strip()
                    if discrepancies_text and discrepancies_text.lower() not in ["", "none", "n/a"]:
                        discrepancies = discrepancies_text
            
            if not definition:
                self.logger.error("Could not extract definition from LLM response")
                self.logger.debug(f"Response text: {response_text[:500]}...")  # Log first 500 chars for debugging
                raise LLMProcessingError("Could not extract definition from LLM response")
            if not reasoning:
                self.logger.error("Could not extract reasoning from LLM response")
                self.logger.debug(f"Response text: {response_text[:500]}...")  # Log first 500 chars for debugging
                raise LLMProcessingError("Could not extract reasoning from LLM response")
            
            self.logger.debug(f"Successfully parsed response - Definition: {len(definition)} chars, Reasoning: {len(reasoning)} chars")
            
            return DefinitionSuggestionResponse(
                definition=definition,
                reasoning=reasoning,
                discrepancies=discrepancies
            )
            
        except LLMProcessingError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error parsing LLM response: {e}")
            raise LLMProcessingError(f"Failed to parse LLM response: {str(e)}")
    
    def _parse_layer_definition_response(self, response_text: str) -> LayerDefinitionResponse:
        """Parse the LLM response for layer definition in the specified format"""
        self.logger.debug(f"Parsing layer definition LLM response (length: {len(response_text)} chars)")
        
        if not response_text or not response_text.strip():
            self.logger.error("Empty response from LLM")
            raise LLMProcessingError("Empty response from LLM")
        
        lines = response_text.strip().split('\n')
        definition = ""
        reasoning = ""
        discrepancies = None
        
        try:
            for line in lines:
                line = line.strip()
                if line.startswith("Definition:"):
                    definition = line[len("Definition:"):].strip()
                elif line.startswith("Reasoning:"):
                    reasoning = line[len("Reasoning:"):].strip()
                elif line.startswith("Discrepancies:"):
                    discrepancies_text = line[len("Discrepancies:"):].strip()
                    if discrepancies_text and discrepancies_text.lower() not in ["", "none", "n/a"]:
                        discrepancies = discrepancies_text
            
            if not definition:
                self.logger.error("Could not extract definition from layer LLM response")
                self.logger.debug(f"Response text: {response_text[:500]}...")
                raise LLMProcessingError("Could not extract definition from LLM response")
            if not reasoning:
                self.logger.error("Could not extract reasoning from layer LLM response")
                self.logger.debug(f"Response text: {response_text[:500]}...")
                raise LLMProcessingError("Could not extract reasoning from LLM response")
            
            self.logger.debug(f"Successfully parsed layer response - Definition: {len(definition)} chars, Reasoning: {len(reasoning)} chars")
            
            return LayerDefinitionResponse(
                definition=definition,
                reasoning=reasoning,
                discrepancies=discrepancies
            )
            
        except LLMProcessingError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error parsing layer LLM response: {e}")
            raise LLMProcessingError(f"Failed to parse LLM response: {str(e)}")

    def _parse_domain_definition_response(self, response_text: str) -> DomainDefinitionResponse:
        """Parse the LLM response for domain definition in the specified format"""
        self.logger.debug(f"Parsing domain definition LLM response (length: {len(response_text)} chars)")
        
        if not response_text or not response_text.strip():
            self.logger.error("Empty response from LLM")
            raise LLMProcessingError("Empty response from LLM")
        
        lines = response_text.strip().split('\n')
        definition = ""
        reasoning = ""
        discrepancies = None
        
        try:
            for line in lines:
                line = line.strip()
                if line.startswith("Definition:"):
                    definition = line[len("Definition:"):].strip()
                elif line.startswith("Reasoning:"):
                    reasoning = line[len("Reasoning:"):].strip()
                elif line.startswith("Discrepancies:"):
                    discrepancies_text = line[len("Discrepancies:"):].strip()
                    if discrepancies_text and discrepancies_text.lower() not in ["", "none", "n/a"]:
                        discrepancies = discrepancies_text
            
            if not definition:
                self.logger.error("Could not extract definition from domain LLM response")
                self.logger.debug(f"Response text: {response_text[:500]}...")
                raise LLMProcessingError("Could not extract definition from LLM response")
            if not reasoning:
                self.logger.error("Could not extract reasoning from domain LLM response")
                self.logger.debug(f"Response text: {response_text[:500]}...")
                raise LLMProcessingError("Could not extract reasoning from LLM response")
            
            self.logger.debug(f"Successfully parsed domain response - Definition: {len(definition)} chars, Reasoning: {len(reasoning)} chars")
            
            return DomainDefinitionResponse(
                definition=definition,
                reasoning=reasoning,
                discrepancies=discrepancies
            )
            
        except LLMProcessingError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error parsing domain LLM response: {e}")
            raise LLMProcessingError(f"Failed to parse LLM response: {str(e)}")
    
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
    
    def _render_user_prompt(self, template: str, request) -> str:
        """Render user prompt template with request data using flavor template"""
        self.logger.debug(f"Rendering user prompt template with request data")
        
        try:
            # Extract field values based on request type
            if hasattr(request, 'term'):
                # Term definition request
                from .prompts import DefinitionPromptTemplate
                prompt_template = DefinitionPromptTemplate()
                
                # Format component terms
                component_definitions = prompt_template._format_component_terms(request.component_terms)
                conceptnet_relations = prompt_template._format_conceptnet_relations(request.component_terms)
                wikidata_context = prompt_template._format_context_dict(request.wikidata_context)
                dbpedia_context = prompt_template._format_context_dict(request.dbpedia_context)
                
                # Replace template variables with actual values
                rendered_prompt = template.format(
                    term=request.term or "Not specified",
                    domain_title=request.domain_title or "Not specified",
                    domain_definition=request.domain_definition or "Not specified",
                    parent_term_title=request.parent_term_title or "Not specified",
                    parent_term_definition=request.parent_term_definition or "Not specified",
                    parent_relationship_predicate=request.parent_relationship_predicate or "Not specified",
                    component_terms=component_definitions,
                    current_definition=request.current_definition or "Not specified",
                    conceptnet_relations=conceptnet_relations,
                    wikidata_context=wikidata_context,
                    dbpedia_context=dbpedia_context
                )
                
            elif hasattr(request, 'layer_title'):
                # Layer definition request
                contained_domains_text = ", ".join(request.contained_domains) if request.contained_domains else "Not specified"
                reference_context = str(request.reference_context) if request.reference_context else "Not specified"
                
                # Replace template variables with actual values
                rendered_prompt = template.format(
                    layer_title=request.layer_title or "Not specified",
                    layer_description=request.layer_description or "Not specified",
                    layer_purpose=request.layer_purpose or "Not specified",
                    parent_layer_title=request.parent_layer_title or "Not specified",
                    parent_layer_definition=request.parent_layer_definition or "Not specified",
                    contained_domains=contained_domains_text,
                    current_definition=request.current_definition or "Not specified",
                    reference_context=reference_context
                )
                
            elif hasattr(request, 'domain_title'):
                # Domain definition request
                contained_terms_text = ", ".join(request.contained_terms) if request.contained_terms else "Not specified"
                related_domains_text = ", ".join(request.related_domains) if request.related_domains else "Not specified"
                reference_context = str(request.reference_context) if request.reference_context else "Not specified"
                
                # Replace template variables with actual values
                rendered_prompt = template.format(
                    domain_title=request.domain_title or "Not specified",
                    domain_description=request.domain_description or "Not specified",
                    domain_scope=request.domain_scope or "Not specified",
                    layer_title=request.layer_title or "Not specified",
                    layer_definition=request.layer_definition or "Not specified",
                    contained_terms=contained_terms_text,
                    related_domains=related_domains_text,
                    current_definition=request.current_definition or "Not specified",
                    reference_context=reference_context
                )
                
            else:
                # Fallback - return template as-is
                self.logger.warning(f"Unknown request type, returning template as-is")
                rendered_prompt = template
            
            self.logger.debug(f"Successfully rendered user prompt template (length: {len(rendered_prompt)} chars)")
            return rendered_prompt
            
        except KeyError as e:
            self.logger.error(f"Missing template variable: {e}")
            raise LLMProcessingError(f"Template rendering failed - missing variable: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error rendering user prompt template: {e}")
            raise LLMProcessingError(f"Template rendering failed: {str(e)}")
