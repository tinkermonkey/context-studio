"""
Dependency injection for LLM and Pipeline services

This module provides optimized dependency injection for LLM and pipeline-related services
using the service factory pattern for better performance.
"""

from fastapi import Depends

from services.service_factory import get_service_factory
from llm.flavor_service import PipelineFlavorService
from llm.service import LLMService


def get_pipeline_flavor_service() -> PipelineFlavorService:
    """
    Optimized dependency injection for PipelineFlavorService using service factory.
    
    Note: PipelineFlavorService manages its own database connections internally.
    
    Returns:
        PipelineFlavorService instance
    """
    factory = get_service_factory()
    return factory.create_pipeline_flavor_service()


def get_llm_service(
    model_name: str = "gpt-3.5-turbo",
    temperature: float = 0
) -> LLMService:
    """
    Optimized dependency injection for LLMService using service factory.
    
    Args:
        model_name: LLM model name
        temperature: Temperature setting for the model
        
    Returns:
        LLMService instance configured with the provided parameters
    """
    factory = get_service_factory()
    return factory.create_llm_service(model_name, temperature)


def get_default_llm_service() -> LLMService:
    """
    Get LLMService with default configuration for most endpoints.
    
    Returns:
        LLMService instance with default GPT-3.5-turbo configuration
    """
    return get_llm_service()


def get_creative_llm_service() -> LLMService:
    """
    Get LLMService with higher temperature for creative tasks.
    
    Returns:
        LLMService instance with higher temperature setting
    """
    return get_llm_service(temperature=0.7)
