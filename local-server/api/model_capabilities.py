"""
API endpoints for model capabilities information.
"""
# mypy: ignore-errors

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from llm.models import ModelCapabilitiesResponse, SupportedModelsResponse
from llm.model_capabilities import (
    get_model_capabilities,
    get_supported_models,
    get_models_by_provider
)
from llm.openrouter_discovery import get_openrouter_discovery_service
from utils.logger import get_logger

router = APIRouter(prefix="/api/model-capabilities", tags=["Model Capabilities"])
logger = get_logger(__name__)


@router.get("", response_model=SupportedModelsResponse)
async def list_supported_models(
    provider: Optional[str] = Query(None, description="Filter by provider (openai, anthropic, etc.)")
):
    """List all supported models with their capabilities"""
    try:
        if provider:
            model_names = get_models_by_provider(provider)
            logger.info(f"Listing {len(model_names)} models for provider: {provider}")
        else:
            model_names = get_supported_models()
            logger.info(f"Listing all {len(model_names)} supported models")

        models = []
        for model_name in model_names:
            capabilities = get_model_capabilities(model_name)

            # Convert dataclass to dict for API response
            capabilities_dict = {
                "supports_temperature": capabilities.supports_temperature,
                "supports_top_p": capabilities.supports_top_p,
                "supports_top_k": capabilities.supports_top_k,
                "supports_max_tokens": capabilities.supports_max_tokens,
                "supports_frequency_penalty": capabilities.supports_frequency_penalty,
                "supports_presence_penalty": capabilities.supports_presence_penalty,
                "supports_structured_output": capabilities.supports_structured_output,
                "supports_function_calling": capabilities.supports_function_calling,
                "supports_streaming": capabilities.supports_streaming,
                "max_tokens_limit": capabilities.max_tokens_limit,
                "context_window": capabilities.context_window,
                "provider": capabilities.provider,
                "model_family": capabilities.model_family
            }

            models.append(ModelCapabilitiesResponse(
                model_name=model_name,
                capabilities=capabilities_dict
            ))

        return SupportedModelsResponse(
            models=models,
            total_count=len(models)
        )

    except Exception as e:
        logger.error(f"Error listing supported models: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/{model_name}", response_model=ModelCapabilitiesResponse)
async def get_model_capabilities_endpoint(model_name: str):
    """Get capabilities for a specific model"""
    try:
        logger.info(f"Getting capabilities for model: {model_name}")

        capabilities = get_model_capabilities(model_name)

        # Convert dataclass to dict for API response
        capabilities_dict = {
            "supports_temperature": capabilities.supports_temperature,
            "supports_top_p": capabilities.supports_top_p,
            "supports_top_k": capabilities.supports_top_k,
            "supports_max_tokens": capabilities.supports_max_tokens,
            "supports_frequency_penalty": capabilities.supports_frequency_penalty,
            "supports_presence_penalty": capabilities.supports_presence_penalty,
            "supports_structured_output": capabilities.supports_structured_output,
            "supports_function_calling": capabilities.supports_function_calling,
            "supports_streaming": capabilities.supports_streaming,
            "max_tokens_limit": capabilities.max_tokens_limit,
            "context_window": capabilities.context_window,
            "provider": capabilities.provider,
            "model_family": capabilities.model_family
        }

        return ModelCapabilitiesResponse(
            model_name=model_name,
            capabilities=capabilities_dict
        )

    except Exception as e:
        logger.error(f"Error getting capabilities for model {model_name}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/providers/{provider_name}", response_model=SupportedModelsResponse)
async def list_models_by_provider(provider_name: str):
    """List all models for a specific provider"""
    try:
        logger.info(f"Listing models for provider: {provider_name}")

        model_names = get_models_by_provider(provider_name)

        if not model_names:
            logger.warning(f"No models found for provider: {provider_name}")
            return SupportedModelsResponse(models=[], total_count=0)

        models = []
        for model_name in model_names:
            capabilities = get_model_capabilities(model_name)

            capabilities_dict = {
                "supports_temperature": capabilities.supports_temperature,
                "supports_top_p": capabilities.supports_top_p,
                "supports_top_k": capabilities.supports_top_k,
                "supports_max_tokens": capabilities.supports_max_tokens,
                "supports_frequency_penalty": capabilities.supports_frequency_penalty,
                "supports_presence_penalty": capabilities.supports_presence_penalty,
                "supports_structured_output": capabilities.supports_structured_output,
                "supports_function_calling": capabilities.supports_function_calling,
                "supports_streaming": capabilities.supports_streaming,
                "max_tokens_limit": capabilities.max_tokens_limit,
                "context_window": capabilities.context_window,
                "provider": capabilities.provider,
                "model_family": capabilities.model_family
            }

            models.append(ModelCapabilitiesResponse(
                model_name=model_name,
                capabilities=capabilities_dict
            ))

        return SupportedModelsResponse(
            models=models,
            total_count=len(models)
        )

    except Exception as e:
        logger.error(f"Error listing models for provider {provider_name}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/openrouter/discover", response_model=SupportedModelsResponse)
async def discover_openrouter_models(
    provider_filter: Optional[str] = Query(None, description="Filter by provider (anthropic, openai, etc.)"),
    min_context: Optional[int] = Query(None, description="Minimum context window size"),
    api_key: Optional[str] = Query(None, description="OpenRouter API key (optional)")
):
    """Discover available models from OpenRouter API"""
    try:
        logger.info("Discovering models from OpenRouter API")

        discovery_service = get_openrouter_discovery_service(api_key)
        openrouter_models = await discovery_service.fetch_available_models()

        if not openrouter_models:
            logger.warning("No models returned from OpenRouter")
            return SupportedModelsResponse(models=[], total_count=0)

        # Apply filters if specified
        if provider_filter or min_context:
            criteria = {}
            if provider_filter:
                criteria["provider"] = [provider_filter]
            if min_context:
                criteria["min_context"] = min_context

            openrouter_models = discovery_service.filter_models(openrouter_models, criteria)

        # Convert to our format
        capabilities_map = discovery_service.convert_to_model_capabilities(openrouter_models)

        models = []
        for model_name, capabilities in capabilities_map.items():
            capabilities_dict = {
                "supports_temperature": capabilities.supports_temperature,
                "supports_top_p": capabilities.supports_top_p,
                "supports_top_k": capabilities.supports_top_k,
                "supports_max_tokens": capabilities.supports_max_tokens,
                "supports_frequency_penalty": capabilities.supports_frequency_penalty,
                "supports_presence_penalty": capabilities.supports_presence_penalty,
                "supports_structured_output": capabilities.supports_structured_output,
                "supports_function_calling": capabilities.supports_function_calling,
                "supports_streaming": capabilities.supports_streaming,
                "max_tokens_limit": capabilities.max_tokens_limit,
                "context_window": capabilities.context_window,
                "provider": capabilities.provider,
                "model_family": capabilities.model_family
            }

            models.append(ModelCapabilitiesResponse(
                model_name=model_name,
                capabilities=capabilities_dict
            ))

        logger.info(f"Successfully discovered {len(models)} models from OpenRouter")

        return SupportedModelsResponse(
            models=models,
            total_count=len(models)
        )

    except Exception as e:
        logger.error(f"Error discovering OpenRouter models: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/openrouter/sync")
async def sync_openrouter_models(
    api_key: Optional[str] = Query(None, description="OpenRouter API key (optional)"),
    provider_filter: Optional[str] = Query(None, description="Only sync models from specific provider")
):
    """Sync OpenRouter models into our static registry (admin endpoint)"""
    try:
        logger.info("Syncing OpenRouter models into static registry")

        discovery_service = get_openrouter_discovery_service(api_key)
        dynamic_registry = await discovery_service.get_dynamic_model_registry()

        if not dynamic_registry:
            logger.warning("No models to sync from OpenRouter")
            return {"synced": 0, "message": "No models available to sync"}

        # Filter by provider if specified
        if provider_filter:
            filtered_registry = {
                name: caps for name, caps in dynamic_registry.items()
                if caps.provider == provider_filter
            }
            dynamic_registry = filtered_registry

        # This is where you'd merge with your static registry
        # For now, just return the discovered models
        synced_count = len(dynamic_registry)

        logger.info(f"Would sync {synced_count} models from OpenRouter")

        return {
            "synced": synced_count,
            "message": f"Discovered {synced_count} models from OpenRouter",
            "models": list(dynamic_registry.keys())
        }

    except Exception as e:
        logger.error(f"Error syncing OpenRouter models: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")