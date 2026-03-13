"""
API endpoints for managing enabled LLM models configuration.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from llm.enabled_models import (
    EnabledModelConfig,
    ProviderType,
    get_enabled_models_manager,
)
from utils.logger import get_logger

router = APIRouter(prefix="/api/enabled-models", tags=["Enabled Models"])
logger = get_logger(__name__)


class EnabledModelResponse(BaseModel):
    """Response model for enabled model configuration"""

    model_name: str
    provider_type: ProviderType
    display_name: str
    enabled: bool
    api_key_env_var: Optional[str] = None
    custom_endpoint: Optional[str] = None
    model_override: Optional[str] = None
    description: Optional[str] = None
    cost_tier: Optional[str] = None
    tags: List[str] = []


class EnabledModelsListResponse(BaseModel):
    """Response model for list of enabled models"""

    models: List[EnabledModelResponse]
    total_count: int


class AddModelRequest(BaseModel):
    """Request model for adding a new enabled model"""

    model_name: str
    provider_type: ProviderType
    display_name: str
    enabled: bool = True
    api_key_env_var: Optional[str] = None
    custom_endpoint: Optional[str] = None
    model_override: Optional[str] = None
    description: Optional[str] = None
    cost_tier: Optional[str] = None
    tags: List[str] = []


class UpdateModelRequest(BaseModel):
    """Request model for updating enabled model configuration"""

    provider_type: Optional[ProviderType] = None
    display_name: Optional[str] = None
    enabled: Optional[bool] = None
    api_key_env_var: Optional[str] = None
    custom_endpoint: Optional[str] = None
    model_override: Optional[str] = None
    description: Optional[str] = None
    cost_tier: Optional[str] = None
    tags: Optional[List[str]] = None


def _config_to_response(config: EnabledModelConfig) -> EnabledModelResponse:
    """Convert EnabledModelConfig to response model"""
    return EnabledModelResponse(
        model_name=config.model_name,
        provider_type=config.provider_type,
        display_name=config.display_name,
        enabled=config.enabled,
        api_key_env_var=config.api_key_env_var,
        custom_endpoint=config.custom_endpoint,
        model_override=config.model_override,
        description=config.description,
        cost_tier=config.cost_tier,
        tags=config.tags,
    )


@router.get("", response_model=EnabledModelsListResponse)
async def list_enabled_models(
    enabled_only: bool = Query(True, description="Only return enabled models"),
    provider_type: Optional[ProviderType] = Query(
        None, description="Filter by provider type"
    ),  # noqa: E501
    tag: Optional[str] = Query(None, description="Filter by tag"),
):
    """List configured models with optional filtering"""
    try:
        manager = get_enabled_models_manager()

        # Get models based on enabled_only flag
        if enabled_only:
            models = manager.get_enabled_models()
        else:
            models = manager.get_all_models()

        # Apply provider filter
        if provider_type:
            models = [m for m in models if m.provider_type == provider_type]

        # Apply tag filter
        if tag:
            models = [m for m in models if tag in m.tags]

        logger.info(
            f"Listed {len(models)} models (enabled_only={enabled_only}, provider={provider_type}, tag={tag})"
        )  # noqa: E501

        response_models = [_config_to_response(config) for config in models]

        return EnabledModelsListResponse(
            models=response_models, total_count=len(response_models)
        )

    except Exception as e:
        logger.error(f"Error listing enabled models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{model_name}", response_model=EnabledModelResponse)
async def get_enabled_model(model_name: str):
    """Get configuration for a specific enabled model"""
    try:
        manager = get_enabled_models_manager()
        config = manager.get_model_config(model_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        logger.info(f"Retrieved configuration for model: {model_name}")
        return _config_to_response(config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("", response_model=EnabledModelResponse)
async def add_enabled_model(request: AddModelRequest):
    """Add a new enabled model configuration"""
    try:
        manager = get_enabled_models_manager()

        # Check if model already exists
        if manager.get_model_config(request.model_name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Model '{request.model_name}' already exists",
            )

        # Create configuration
        config = EnabledModelConfig(
            model_name=request.model_name,
            provider_type=request.provider_type,
            display_name=request.display_name,
            enabled=request.enabled,
            api_key_env_var=request.api_key_env_var,
            custom_endpoint=request.custom_endpoint,
            model_override=request.model_override,
            description=request.description,
            cost_tier=request.cost_tier,
            tags=request.tags,
        )

        # Add to manager
        success = manager.add_model(config)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save model configuration",
            )

        logger.info(f"Added new enabled model: {request.model_name}")
        return _config_to_response(config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding model {request.model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{model_name}", response_model=EnabledModelResponse)
async def update_enabled_model(model_name: str, request: UpdateModelRequest):
    """Update an existing enabled model configuration"""
    try:
        manager = get_enabled_models_manager()

        # Get existing configuration
        config = manager.get_model_config(model_name)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        # Update fields that were provided
        if request.provider_type is not None:
            config.provider_type = request.provider_type
        if request.display_name is not None:
            config.display_name = request.display_name
        if request.enabled is not None:
            config.enabled = request.enabled
        if request.api_key_env_var is not None:
            config.api_key_env_var = request.api_key_env_var
        if request.custom_endpoint is not None:
            config.custom_endpoint = request.custom_endpoint
        if request.model_override is not None:
            config.model_override = request.model_override
        if request.description is not None:
            config.description = request.description
        if request.cost_tier is not None:
            config.cost_tier = request.cost_tier
        if request.tags is not None:
            config.tags = request.tags

        # Save updated configuration
        success = manager.add_model(config)  # add_model also updates existing
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save updated model configuration",
            )

        logger.info(f"Updated enabled model: {model_name}")
        return _config_to_response(config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating model {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{model_name}")
async def delete_enabled_model(model_name: str):
    """Remove an enabled model configuration"""
    try:
        manager = get_enabled_models_manager()

        # Check if model exists
        if not manager.get_model_config(model_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        # Remove model
        success = manager.remove_model(model_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove model configuration",
            )

        logger.info(f"Removed enabled model: {model_name}")
        return {"message": f"Model '{model_name}' removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing model {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/{model_name}/enable")
async def enable_model(model_name: str):
    """Enable a specific model"""
    try:
        manager = get_enabled_models_manager()

        # Check if model exists
        if not manager.get_model_config(model_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        # Enable model
        success = manager.enable_model(model_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enable model",
            )

        logger.info(f"Enabled model: {model_name}")
        return {"message": f"Model '{model_name}' enabled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling model {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/{model_name}/disable")
async def disable_model(model_name: str):
    """Disable a specific model"""
    try:
        manager = get_enabled_models_manager()

        # Check if model exists
        if not manager.get_model_config(model_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        # Disable model
        success = manager.disable_model(model_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to disable model",
            )

        logger.info(f"Disabled model: {model_name}")
        return {"message": f"Model '{model_name}' disabled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling model {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/providers/summary")
async def get_provider_summary():
    """Get summary of models grouped by provider"""
    try:
        manager = get_enabled_models_manager()
        all_models = manager.get_all_models()

        # Group by provider
        provider_summary = {}
        for provider_type in ProviderType:
            models = [
                m for m in all_models if m.provider_type == provider_type
            ]  # noqa: E501
            enabled_count = len([m for m in models if m.enabled])

            provider_summary[provider_type.value] = {
                "total_models": len(models),
                "enabled_models": enabled_count,
                "models": [m.model_name for m in models],
            }

        logger.info("Generated provider summary")
        return {"providers": provider_summary}

    except Exception as e:
        logger.error(f"Error generating provider summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
