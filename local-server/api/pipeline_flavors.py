"""
API endpoints for managing pipeline flavors.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status, Response

from api.dependencies.llm_services import get_pipeline_flavor_service
from llm.flavor_service import PipelineFlavorService
from llm.models import (
    PipelineFlavor,
    CreatePipelineFlavorRequest,
    UpdatePipelineFlavorRequest,
    PipelineFlavorListResponse,
    PipelineType,
)
from llm.exceptions import FlavorNotFoundError, FlavorValidationError
from utils.logger import get_logger

router = APIRouter(prefix="/api/pipeline-flavors", tags=["Pipeline Flavors"])
logger = get_logger(__name__)


def get_flavor_service() -> PipelineFlavorService:
    """Legacy dependency to get flavor service instance"""
    return PipelineFlavorService()


@router.post(
    "", response_model=PipelineFlavor, status_code=status.HTTP_201_CREATED
)  # noqa: E501
async def create_flavor(
    response: Response,
    request: CreatePipelineFlavorRequest,
    flavor_service: PipelineFlavorService = Depends(
        get_pipeline_flavor_service
    ),  # noqa: E501
):
    """Create a new pipeline flavor"""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Phase 3"
    try:
        logger.info(
            f"Creating new flavor '{request.title}' for pipeline '{request.pipeline.value}'"
        )  # noqa: E501
        flavor = flavor_service.create_flavor(request)
        logger.info(f"Successfully created flavor with ID: {flavor.id}")
        return flavor

    except FlavorValidationError as e:
        logger.warning(f"Flavor validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )  # noqa: E501
    except Exception as e:
        logger.error(f"Error creating flavor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )  # noqa: E501


@router.get("", response_model=PipelineFlavorListResponse)
async def list_flavors(
    response: Response,
    pipeline: Optional[PipelineType] = Query(
        None, description="Filter by pipeline type"
    ),  # noqa: E501
    flavor_service: PipelineFlavorService = Depends(
        get_pipeline_flavor_service
    ),  # noqa: E501
):
    """List all flavors, optionally filtered by pipeline"""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Phase 3"
    try:
        logger.info(
            f"Listing flavors for pipeline: {pipeline.value if pipeline else 'all'}"
        )  # noqa: E501
        flavors = flavor_service.list_flavors(pipeline)
        return PipelineFlavorListResponse(flavors=flavors, total_count=len(flavors))

    except Exception as e:
        logger.error(f"Error listing flavors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )  # noqa: E501


@router.get("/{flavor_id}", response_model=PipelineFlavor)
async def get_flavor(
    response: Response,
    flavor_id: str,
    pipeline: Optional[PipelineType] = Query(
        None, description="Pipeline type (required for default flavor)"
    ),  # noqa: E501
    flavor_service: PipelineFlavorService = Depends(get_flavor_service),
):
    """Get a specific flavor by ID"""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Phase 3"
    try:
        # Handle default flavor special case
        if flavor_id == "default":
            if not pipeline:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Pipeline parameter required when requesting default flavor",  # noqa: E501
                )
            return flavor_service.get_default_flavor(pipeline)

        flavor = flavor_service.get_flavor_by_id(flavor_id)
        return flavor

    except FlavorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )  # noqa: E501
    except HTTPException:
        # Let HTTPExceptions bubble up naturally
        raise
    except Exception as e:
        logger.error(f"Error getting flavor {flavor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )  # noqa: E501


@router.put("/{flavor_id}", response_model=PipelineFlavor)
async def update_flavor(
    response: Response,
    flavor_id: str,
    request: UpdatePipelineFlavorRequest,
    flavor_service: PipelineFlavorService = Depends(get_flavor_service),
):
    """Update an existing flavor"""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Phase 3"
    # Prevent updating default flavors
    if flavor_id == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update default flavor. Create a new flavor instead.",
        )

    try:
        logger.info(f"Updating flavor {flavor_id}")
        flavor = flavor_service.update_flavor(flavor_id, request)
        logger.info(f"Successfully updated flavor {flavor_id}")
        return flavor

    except FlavorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )  # noqa: E501
    except FlavorValidationError as e:
        logger.warning(f"Flavor validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )  # noqa: E501
    except Exception as e:
        logger.error(f"Error updating flavor {flavor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )  # noqa: E501


@router.delete("/{flavor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flavor(
    response: Response,
    flavor_id: str,
    flavor_service: PipelineFlavorService = Depends(get_flavor_service),
):
    """Delete a flavor"""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Phase 3"
    # Prevent deleting default flavors
    if flavor_id == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete default flavor",
        )

    try:
        logger.info(f"Deleting flavor {flavor_id}")
        flavor_service.delete_flavor(flavor_id)
        logger.info(f"Successfully deleted flavor {flavor_id}")

    except FlavorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )  # noqa: E501
    except FlavorValidationError as e:
        logger.warning(f"Flavor validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )  # noqa: E501
    except Exception as e:
        logger.error(f"Error deleting flavor {flavor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )  # noqa: E501
