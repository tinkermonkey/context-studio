"""
LLM service for handling Langchain interactions.
"""

from typing import Optional, Dict, Any
import os
import asyncio
from langchain.chat_models import init_chat_model
from langchain.schema import HumanMessage, SystemMessage
from openai import RateLimitError, APITimeoutError, APIError, AuthenticationError

from .models import DefinitionSuggestionRequest, DefinitionSuggestionResponse
from .prompts import DefinitionPromptTemplate
from .exceptions import (
    LLMConfigurationError, 
    LLMProcessingError, 
    LLMTimeoutError, 
    LLMQuotaExceededError
)
from utils.logger import get_logger


class LLMService:
    """Service for handling LLM interactions using Langchain"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo", temperature: float = 0):
        self.logger = get_logger(__name__)
        self.model_name = model_name
        self.temperature = temperature
        self._llm = None
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
    
    async def suggest_definition(self, request: DefinitionSuggestionRequest) -> DefinitionSuggestionResponse:
        """Generate a definition suggestion based on provided context"""
        self.logger.info(f"Starting definition suggestion for term: '{request.term}'")
        self.logger.debug(f"Request details - Domain: {request.domain_title}, Parent: {request.parent_term_title}")
        
        try:
            # Validate that LLM is initialized
            if self._llm is None:
                self.logger.error("LLM not initialized")
                raise LLMConfigurationError("LLM service not properly initialized")
            
            # Get prompt template
            prompt_template = DefinitionPromptTemplate()
            
            # Create the prompt (using exact format from requirements)
            prompt = prompt_template.create_prompt(request, "")
            
            # Log prompt creation (debug level to avoid spam)
            self.logger.debug(f"Generated prompt for term '{request.term}' (length: {len(prompt)} chars)")
            
            # Execute the chain with timeout
            messages = [
                SystemMessage(content=prompt_template.get_system_prompt()),
                HumanMessage(content=prompt)
            ]
            
            # Add timeout to the async call
            timeout = int(os.getenv("LLM_TIMEOUT", "30"))
            try:
                response = await asyncio.wait_for(
                    self._llm.ainvoke(messages), 
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                self.logger.warning(f"LLM request timed out after {timeout} seconds for term: '{request.term}'")
                raise LLMTimeoutError(f"Request timed out after {timeout} seconds")
            
            # Parse the response using the exact format from requirements
            parsed_response = self._parse_definition_response(response.content)
            
            self.logger.info(f"Successfully generated definition for term: '{request.term}'")
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
            self.logger.error(f"Unexpected error generating definition for term '{request.term}': {e}")
            raise LLMProcessingError(f"Failed to generate definition: {str(e)}")
    
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
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model configuration"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "provider": "openai",
            "initialized": self._llm is not None
        }
