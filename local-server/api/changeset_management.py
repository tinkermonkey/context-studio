"""
Changeset Management API Endpoints

This module implements the changeset management API endpoints for collaborative
change workflows, bundling related changes for proposal and review.

Endpoints:
- POST /api/changesets - Create changeset from staged changes
- GET /api/changesets - List changesets with optional filtering
- GET /api/changesets/{changeset_id} - Get changeset details
- PUT /api/changesets/{changeset_id} - Update changeset metadata
- DELETE /api/changesets/{changeset_id} - Delete changeset
- POST /api/changesets/{changeset_id}/push - Push changeset to S3
- GET /api/changesets/{changeset_id}/versions - Get changeset version details
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Path
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from services.changeset_manager import ChangesetManager
from services.collaboration_models import ChangesetState
from services.service_factory import ServiceFactory
from database.utils import get_db
from sqlalchemy.orm import Session
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/changesets", tags=["changeset_management"])


# Request/Response Models
class CreateChangesetRequest(BaseModel):
    """Request model for creating a changeset."""
    title: str
    description: str
    author_id: str
    include_staged: bool = True


class UpdateChangesetRequest(BaseModel):
    """Request model for updating a changeset."""
    title: Optional[str] = None
    description: Optional[str] = None


class ChangesetResponse(BaseModel):
    """Response model for changeset data."""
    id: str
    title: str
    description: str
    state: str
    branch_name: Optional[str]
    parent_changeset_id: Optional[str]
    author_id: str
    created_at: datetime
    merged_at: Optional[datetime]
    metadata: Optional[dict]


class ChangesetListResponse(BaseModel):
    """Response model for changeset list."""
    changesets: List[ChangesetResponse]
    total_count: int


class ChangesetVersionsResponse(BaseModel):
    """Response model for changeset version details."""
    changeset_id: str
    version_ids: List[str]
    version_count: int


# Dependency injection
def get_changeset_manager(
    db: Session = Depends(get_db),
    service_factory: ServiceFactory = Depends()
) -> ChangesetManager:
    """Get ChangesetManager instance via service factory."""
    return service_factory.create_changeset_manager(db)


# API Endpoints
@router.post("", response_model=ChangesetResponse)
def create_changeset(
    request: CreateChangesetRequest,
    changeset_manager: ChangesetManager = Depends(get_changeset_manager)
):
    """
    Create a new changeset from staged or working changes.
    
    Args:
        request: Changeset creation request
        changeset_manager: ChangesetManager dependency
        
    Returns:
        Created changeset details
        
    Raises:
        HTTPException: If no changes available or creation fails
    """
    logger.info(f"Creating changeset '{request.title}' by {request.author_id}")
    
    try:
        changeset = changeset_manager.create_changeset(
            title=request.title,
            description=request.description,
            author_id=request.author_id,
            include_staged=request.include_staged
        )
        
        return ChangesetResponse(
            id=changeset.id,
            title=changeset.title,
            description=changeset.description,
            state=changeset.state.value,
            branch_name=changeset.branch_name,
            parent_changeset_id=changeset.parent_changeset_id,
            author_id=changeset.author_id,
            created_at=changeset.created_at,
            merged_at=changeset.merged_at,
            metadata=changeset.metadata
        )
        
    except ValueError as e:
        logger.warning(f"Invalid changeset creation request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Failed to create changeset: {e}")
        raise HTTPException(status_code=500, detail="Failed to create changeset")


@router.get("", response_model=ChangesetListResponse)
def list_changesets(
    author_id: Optional[str] = Query(None, description="Filter by author ID"),
    state: Optional[str] = Query(None, description="Filter by changeset state"),
    limit: int = Query(100, description="Maximum number of results", le=1000),
    changeset_manager: ChangesetManager = Depends(get_changeset_manager)
):
    """
    List changesets with optional filtering.
    
    Args:
        author_id: Optional author ID filter
        state: Optional changeset state filter
        limit: Maximum number of results
        changeset_manager: ChangesetManager dependency
        
    Returns:
        List of changesets matching filters
        
    Raises:
        HTTPException: If invalid state provided
    """
    logger.debug(f"Listing changesets (author={author_id}, state={state}, limit={limit})")
    
    try:
        # Validate state if provided
        changeset_state = None
        if state:
            try:
                changeset_state = ChangesetState(state)
            except ValueError:
                valid_states = [s.value for s in ChangesetState]
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid state '{state}'. Valid states: {valid_states}"
                )
        
        changesets = changeset_manager.list_changesets(
            author_id=author_id,
            state=changeset_state,
            limit=limit
        )
        
        changeset_responses = []
        for changeset in changesets:
            changeset_responses.append(ChangesetResponse(
                id=changeset.id,
                title=changeset.title,
                description=changeset.description,
                state=changeset.state.value,
                branch_name=changeset.branch_name,
                parent_changeset_id=changeset.parent_changeset_id,
                author_id=changeset.author_id,
                created_at=changeset.created_at,
                merged_at=changeset.merged_at,
                metadata=changeset.metadata
            ))
        
        return ChangesetListResponse(
            changesets=changeset_responses,
            total_count=len(changeset_responses)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list changesets: {e}")
        raise HTTPException(status_code=500, detail="Failed to list changesets")


@router.get("/{changeset_id}", response_model=ChangesetResponse)
def get_changeset(
    changeset_id: str = Path(..., description="Changeset ID"),
    changeset_manager: ChangesetManager = Depends(get_changeset_manager)
):
    """
    Get changeset details by ID.
    
    Args:
        changeset_id: Changeset identifier
        changeset_manager: ChangesetManager dependency
        
    Returns:
        Changeset details
        
    Raises:
        HTTPException: If changeset not found
    """
    logger.debug(f"Getting changeset {changeset_id}")
    
    try:
        changeset = changeset_manager.get_changeset(changeset_id)
        if not changeset:
            raise HTTPException(status_code=404, detail=f"Changeset {changeset_id} not found")
        
        return ChangesetResponse(
            id=changeset.id,
            title=changeset.title,
            description=changeset.description,
            state=changeset.state.value,
            branch_name=changeset.branch_name,
            parent_changeset_id=changeset.parent_changeset_id,
            author_id=changeset.author_id,
            created_at=changeset.created_at,
            merged_at=changeset.merged_at,
            metadata=changeset.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get changeset {changeset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get changeset")


@router.put("/{changeset_id}", response_model=ChangesetResponse)
def update_changeset(
    changeset_id: str = Path(..., description="Changeset ID"),
    request: UpdateChangesetRequest = ...,
    changeset_manager: ChangesetManager = Depends(get_changeset_manager)
):
    """
    Update changeset metadata.
    
    Args:
        changeset_id: Changeset identifier
        request: Update request with new values
        changeset_manager: ChangesetManager dependency
        
    Returns:
        Updated changeset details
        
    Raises:
        HTTPException: If changeset not found or update fails
    """
    logger.info(f"Updating changeset {changeset_id}")

    try:
        # Validate that at least one field is provided
        if not request.title and not request.description:
            raise HTTPException(
                status_code=400,
                detail="At least one field (title or description) must be provided for update"
            )

        # Check if changeset exists
        changeset = changeset_manager.get_changeset(changeset_id)
        if not changeset:
            raise HTTPException(status_code=404, detail=f"Changeset {changeset_id} not found")

        # Update changeset
        success = changeset_manager.update_changeset(
            changeset_id=changeset_id,
            title=request.title,
            description=request.description
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="No updates provided or changeset not found")
        
        # Get updated changeset
        updated_changeset = changeset_manager.get_changeset(changeset_id)
        if not updated_changeset:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated changeset")
        
        return ChangesetResponse(
            id=updated_changeset.id,
            title=updated_changeset.title,
            description=updated_changeset.description,
            state=updated_changeset.state.value,
            branch_name=updated_changeset.branch_name,
            parent_changeset_id=updated_changeset.parent_changeset_id,
            author_id=updated_changeset.author_id,
            created_at=updated_changeset.created_at,
            merged_at=updated_changeset.merged_at,
            metadata=updated_changeset.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update changeset {changeset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update changeset")


@router.delete("/{changeset_id}")
def delete_changeset(
    changeset_id: str = Path(..., description="Changeset ID"),
    changeset_manager: ChangesetManager = Depends(get_changeset_manager)
):
    """
    Delete a changeset.
    
    Args:
        changeset_id: Changeset identifier
        changeset_manager: ChangesetManager dependency
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If changeset not found or deletion fails
    """
    logger.info(f"Deleting changeset {changeset_id}")
    
    try:
        success = changeset_manager.delete_changeset(changeset_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Changeset {changeset_id} not found")
        
        return {"message": f"Changeset {changeset_id} deleted successfully"}
        
    except ValueError as e:
        logger.warning(f"Invalid changeset deletion: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Failed to delete changeset {changeset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete changeset")


@router.post("/{changeset_id}/push")
def push_changeset_to_s3(
    changeset_id: str = Path(..., description="Changeset ID"),
    changeset_manager: ChangesetManager = Depends(get_changeset_manager)
):
    """
    Push changeset to S3 for collaboration.
    
    Args:
        changeset_id: Changeset identifier
        changeset_manager: ChangesetManager dependency
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If changeset not found or push fails
    """
    logger.info(f"Pushing changeset {changeset_id} to S3")
    
    try:
        success = changeset_manager.push_changeset_to_s3(changeset_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to push changeset to S3")
        
        return {"message": f"Changeset {changeset_id} pushed to S3 successfully"}
        
    except Exception as e:
        logger.error(f"Failed to push changeset {changeset_id} to S3: {e}")
        raise HTTPException(status_code=500, detail="Failed to push changeset to S3")


@router.get("/{changeset_id}/versions", response_model=ChangesetVersionsResponse)
def get_changeset_versions(
    changeset_id: str = Path(..., description="Changeset ID"),
    changeset_manager: ChangesetManager = Depends(get_changeset_manager)
):
    """
    Get version details for a changeset.
    
    Args:
        changeset_id: Changeset identifier
        changeset_manager: ChangesetManager dependency
        
    Returns:
        Changeset version details
        
    Raises:
        HTTPException: If changeset not found
    """
    logger.debug(f"Getting versions for changeset {changeset_id}")
    
    try:
        # Check if changeset exists
        changeset = changeset_manager.get_changeset(changeset_id)
        if not changeset:
            raise HTTPException(status_code=404, detail=f"Changeset {changeset_id} not found")
        
        version_ids = changeset_manager.get_changeset_versions(changeset_id)
        
        return ChangesetVersionsResponse(
            changeset_id=changeset_id,
            version_ids=version_ids,
            version_count=len(version_ids)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get versions for changeset {changeset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get changeset versions")