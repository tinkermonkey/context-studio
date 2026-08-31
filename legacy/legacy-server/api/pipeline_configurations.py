"""
Pipeline Configurations API Endpoints

This module implements the new pipeline_configurations API endpoints using new terminology  # noqa: E501
alongside the existing pipeline_flavors API.

Endpoints:
- POST /api/pipeline_configurations - Create a new configuration
- GET /api/pipeline_configurations - List configurations
- GET /api/pipeline_configurations/{configuration_id} - Get a specific configuration  # noqa: E501
- PUT /api/pipeline_configurations/{configuration_id} - Update a configuration
- DELETE /api/pipeline_configurations/{configuration_id} - Delete a configuration  # noqa: E501
"""


from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from llm.exceptions import FlavorNotFoundError, FlavorValidationError
from llm.flavor_service import PipelineFlavorService
from llm.models import (
    CreatePipelineFlavorRequest,
    PipelineFlavor,
    PipelineFlavorListResponse,
    PipelineType,
    UpdatePipelineFlavorRequest,
)
from utils.logger import get_logger

from api.dependencies.llm_services import get_pipeline_flavor_service

router = APIRouter(
    prefix="/api/pipeline_configurations", tags=["Pipeline Configurations"]
)
logger = get_logger(__name__)


@router.post(
    "", response_model=PipelineFlavor, status_code=status.HTTP_201_CREATED
)
async def create_configuration(
    request: CreatePipelineFlavorRequest,
    flavor_service: PipelineFlavorService = Depends(
        get_pipeline_flavor_service
    ),
):
    """
    Create a new pipeline configuration.

    This endpoint creates a pipeline configuration using new terminology
    alongside the pipeline_flavors API.
    """
    try:
        logger.info(
            f"Creating new configuration '{request.title}' for pipeline '{request.pipeline.value}'"
        )
        flavor = flavor_service.create_flavor(request)
        logger.info(f"Successfully created configuration with ID: {flavor.id}")
        return flavor

    except FlavorValidationError as e:
        logger.warning(f"Configuration validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("", response_model=PipelineFlavorListResponse)
async def list_configurations(
    pipeline: PipelineType | None = Query(
        None, description="Filter by pipeline type"
    ),
    flavor_service: PipelineFlavorService = Depends(
        get_pipeline_flavor_service
    ),
):
    """
    List all pipeline configurations, optionally filtered by pipeline type.

    This endpoint lists pipeline configurations using new terminology
    alongside the pipeline_flavors API.
    """
    try:
        logger.info(
            f"Listing configurations for pipeline: {pipeline.value if pipeline else 'all'}"
        )
        flavors = flavor_service.list_flavors(pipeline)
        return PipelineFlavorListResponse(flavors=flavors, total_count=len(flavors))

    except Exception as e:
        logger.error(f"Error listing configurations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{configuration_id}", response_model=PipelineFlavor)
async def get_configuration(
    configuration_id: str = Path(
        ..., description="The ID of the configuration to retrieve"
    ),
    pipeline: PipelineType | None = Query(
        None, description="Pipeline type (required for default configuration)"
    ),
    flavor_service: PipelineFlavorService = Depends(
        get_pipeline_flavor_service
    ),
):
    """
    Get a specific pipeline configuration by ID.

    Handles the special case of "default" configuration which requires
    a pipeline parameter.
    """
    try:
        # Handle default configuration special case
        if configuration_id == "default":
            if not pipeline:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Pipeline parameter required when requesting default configuration",
                )
            return flavor_service.get_default_flavor(pipeline)

        flavor = flavor_service.get_flavor_by_id(configuration_id)
        return flavor

    except FlavorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration {configuration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{configuration_id}", response_model=PipelineFlavor)
async def update_configuration(
    configuration_id: str = Path(
        ..., description="The ID of the configuration to update"
    ),
    request: UpdatePipelineFlavorRequest = Body(...),
    flavor_service: PipelineFlavorService = Depends(
        get_pipeline_flavor_service
    ),
):
    """
    Update an existing pipeline configuration.

    Prevents updating default configurations. Create a new configuration
    instead if you need different settings.
    """
    # Prevent updating default configurations
    if configuration_id == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update default configuration. Create a new configuration instead.",
        )

    try:
        logger.info(f"Updating configuration {configuration_id}")
        flavor = flavor_service.update_flavor(configuration_id, request)
        logger.info(f"Successfully updated configuration {configuration_id}")
        return flavor

    except FlavorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except FlavorValidationError as e:
        logger.warning(f"Configuration validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating configuration {configuration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_configuration(
    configuration_id: str = Path(
        ..., description="The ID of the configuration to delete"
    ),
    flavor_service: PipelineFlavorService = Depends(
        get_pipeline_flavor_service
    ),
):
    """
    Delete a pipeline configuration.

    Prevents deleting default configurations.
    """
    # Prevent deleting default configurations
    if configuration_id == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete default configuration",
        )

    try:
        logger.info(f"Deleting configuration {configuration_id}")
        flavor_service.delete_flavor(configuration_id)
        logger.info(f"Successfully deleted configuration {configuration_id}")

    except FlavorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )
    except FlavorValidationError as e:
        logger.warning(f"Configuration validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting configuration {configuration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
