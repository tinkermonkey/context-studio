"""API endpoints for dataset management."""

import os
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from dataset.manager import DatasetManager
from dataset.models import (
    DatasetResponse, CreateDatasetRequest, UpdateDatasetDirectoryRequest,
    AddExistingDatasetRequest, DatasetInfo, ActionLogResponse, ActionLogEntry
)
from database.utils import get_dataset_manager, get_db_for_current_dataset, switch_active_database
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_dataset_manager_dependency() -> DatasetManager:
    """Dependency to get dataset manager."""
    return get_dataset_manager()


@router.get("/datasets", response_model=List[DatasetResponse])
async def list_datasets(
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """List all known datasets with metrics."""
    try:
        datasets = dataset_manager.list_datasets()
        active_dataset_id = dataset_manager.active_dataset_id
        
        return [
            DatasetResponse(
                id=dataset.id,
                title=dataset.title,
                filename=dataset.filename,
                created_at=dataset.created_at,
                last_accessed=dataset.last_accessed,
                schema_version=dataset.schema_version,
                metrics=dataset.metrics,
                is_active=(dataset.id == active_dataset_id)
            )
            for dataset in datasets
        ]
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets", response_model=DatasetResponse)
async def create_dataset(
    request: CreateDatasetRequest,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Create a new dataset."""
    try:
        dataset = dataset_manager.create_dataset(request.title, request.filename)
        
        return DatasetResponse(
            id=dataset.id,
            title=dataset.title,
            filename=dataset.filename,
            created_at=dataset.created_at,
            last_accessed=dataset.last_accessed,
            schema_version=dataset.schema_version,
            metrics=dataset.metrics,
            is_active=(dataset.id == dataset_manager.active_dataset_id)
        )
    except ValueError as e:
        error_message = str(e)
        
        # Provide more helpful error messages for dataset creation
        if "already exists" in error_message and "title" in error_message:
            raise HTTPException(
                status_code=409, 
                detail=f"Duplicate title: A dataset with the title '{request.title}' already exists. Please choose a different title."
            )
        elif "already exists" in error_message and "filename" in error_message:
            raise HTTPException(
                status_code=409, 
                detail=f"Duplicate filename: A dataset with the filename '{request.filename}' already exists. Please choose a different filename."
            )
        elif "Invalid filename" in error_message:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid filename: '{request.filename}' is not a valid filename. Please use a valid filename with .db extension."
            )
        else:
            # Fallback for any other ValueError
            raise HTTPException(status_code=400, detail=f"Validation error: {error_message}")
    except Exception as e:
        logger.error(f"Failed to create dataset: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the dataset. Please check the server logs for more details.")


@router.get("/datasets/active", response_model=DatasetResponse)
async def get_active_dataset(
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Get currently active dataset information."""
    try:
        dataset = dataset_manager.get_active_dataset()
        if not dataset:
            raise HTTPException(status_code=404, detail="No active dataset")
        
        return DatasetResponse(
            id=dataset.id,
            title=dataset.title,
            filename=dataset.filename,
            created_at=dataset.created_at,
            last_accessed=dataset.last_accessed,
            schema_version=dataset.schema_version,
            metrics=dataset.metrics,
            is_active=True
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get active dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets/directory")
async def get_datasets_directory(
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Get the current datasets directory path."""
    try:
        return {"datasets_directory": dataset_manager.datasets_directory}
    except Exception as e:
        logger.error(f"Failed to get datasets directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets/startup-info")
async def get_startup_info(
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Get information about which dataset will be loaded on server startup."""
    try:
        return dataset_manager.get_startup_behavior_info()
    except Exception as e:
        logger.error(f"Failed to get startup info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/add-existing", response_model=DatasetResponse)
async def add_existing_dataset(
    request: AddExistingDatasetRequest,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Add an existing dataset file to the inventory."""
    try:
        dataset = dataset_manager.add_existing_dataset(request.title, request.file_path)
        
        return DatasetResponse(
            id=dataset.id,
            title=dataset.title,
            filename=dataset.filename,
            created_at=dataset.created_at,
            last_accessed=dataset.last_accessed,
            schema_version=dataset.schema_version,
            metrics=dataset.metrics,
            is_active=(dataset.id == dataset_manager.active_dataset_id)
        )
    except ValueError as e:
        error_message = str(e)
        
        # Provide more helpful error messages based on the specific validation failure
        if "does not exist" in error_message:
            raise HTTPException(
                status_code=400, 
                detail=f"File not found: The specified file '{request.file_path}' does not exist. Please check the file path and try again."
            )
        elif "already exists" in error_message and "title" in error_message:
            raise HTTPException(
                status_code=409, 
                detail=f"Duplicate title: A dataset with the title '{request.title}' already exists. Please choose a different title."
            )
        elif "already exists" in error_message and "filename" in error_message:
            filename = os.path.basename(request.file_path)
            raise HTTPException(
                status_code=409, 
                detail=f"Duplicate filename: A dataset with the filename '{filename}' already exists. Please rename the file or choose a different file."
            )
        elif "does not appear to be a valid Context Studio dataset" in error_message:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid dataset: The file '{request.file_path}' is not a valid Context Studio dataset. It may be empty, corrupted, or from a different application."
            )
        elif "Failed to validate dataset file" in error_message:
            raise HTTPException(
                status_code=400, 
                detail=f"Database validation failed: The file '{request.file_path}' could not be validated as a SQLite database. It may be corrupted or not a database file."
            )
        else:
            # Fallback for any other ValueError
            raise HTTPException(status_code=400, detail=f"Validation error: {error_message}")
    except Exception as e:
        logger.error(f"Failed to add existing dataset: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while adding the dataset. Please check the server logs for more details.")


@router.post("/datasets/directory")
async def update_datasets_directory(
    request: UpdateDatasetDirectoryRequest,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Update the datasets directory path."""
    try:
        success = dataset_manager.update_datasets_directory(request.datasets_directory)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update datasets directory")
        
        return {
            "message": "Datasets directory updated successfully",
            "datasets_directory": request.datasets_directory
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update datasets directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets/action-log", response_model=ActionLogResponse)
async def get_action_log(
    days: int = 30,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Get dataset action log for the specified number of days."""
    try:
        action_log = dataset_manager.get_action_log(days=days)
        
        entries = [
            ActionLogEntry(
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                action=entry["action"],
                dataset_id=entry["dataset_id"],
                dataset_title=entry.get("dataset_title"),
                details=entry.get("details", {})
            )
            for entry in action_log
        ]
        
        return ActionLogResponse(
            entries=entries,
            total_count=len(entries)
        )
    except Exception as e:
        logger.error(f"Failed to get action log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Get dataset details and metrics."""
    try:
        datasets = dataset_manager.list_datasets()
        dataset = next((d for d in datasets if d.id == dataset_id), None)
        
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        return DatasetResponse(
            id=dataset.id,
            title=dataset.title,
            filename=dataset.filename,
            created_at=dataset.created_at,
            last_accessed=dataset.last_accessed,
            schema_version=dataset.schema_version,
            metrics=dataset.metrics,
            is_active=(dataset.id == dataset_manager.active_dataset_id)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/{dataset_id}/activate")
async def activate_dataset(
    dataset_id: str,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Switch to the specified dataset."""
    try:
        # First check if the dataset exists
        datasets = dataset_manager.list_datasets()
        dataset_exists = any(d.id == dataset_id for d in datasets)
        
        if not dataset_exists:
            raise HTTPException(
                status_code=404, 
                detail=f"Dataset not found: No dataset with ID '{dataset_id}' exists in the inventory."
            )
        
        success = switch_active_database(dataset_id)
        if not success:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to activate dataset: Could not switch to dataset '{dataset_id}'. The dataset file may be missing, corrupted, or inaccessible."
            )
        
        return {"message": f"Dataset {dataset_id} activated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred while activating dataset '{dataset_id}'. Please check the server logs for more details."
        )


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Delete a dataset."""
    try:
        # First check if the dataset exists
        datasets = dataset_manager.list_datasets()
        dataset = next((d for d in datasets if d.id == dataset_id), None)
        
        if not dataset:
            raise HTTPException(
                status_code=404, 
                detail=f"Dataset not found: No dataset with ID '{dataset_id}' exists in the inventory."
            )
        
        success = dataset_manager.delete_dataset(dataset_id)
        if not success:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to delete dataset: Could not delete dataset '{dataset.title}' ({dataset_id}). The dataset may be currently active or the file may be in use."
            )
        
        return {"message": f"Dataset {dataset_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred while deleting dataset '{dataset_id}'. Please check the server logs for more details."
        )


@router.post("/datasets/{dataset_id}/forget")
async def forget_dataset(
    dataset_id: str,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Remove a dataset from inventory but leave the file intact."""
    try:
        # First check if the dataset exists
        datasets = dataset_manager.list_datasets()
        dataset = next((d for d in datasets if d.id == dataset_id), None)
        
        if not dataset:
            raise HTTPException(
                status_code=404, 
                detail=f"Dataset not found: No dataset with ID '{dataset_id}' exists in the inventory."
            )
        
        success = dataset_manager.forget_dataset(dataset_id)
        if not success:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to forget dataset: Could not remove dataset '{dataset.title}' ({dataset_id}) from inventory. The dataset may be currently active."
            )
        
        return {"message": f"Dataset {dataset_id} forgotten successfully (file preserved)"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to forget dataset {dataset_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred while forgetting dataset '{dataset_id}'. Please check the server logs for more details."
        )


@router.get("/datasets/directory")
async def get_datasets_directory(
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Get the current datasets directory path."""
    try:
        return {"datasets_directory": dataset_manager.datasets_directory}
    except Exception as e:
        logger.error(f"Failed to get datasets directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/directory")
async def update_datasets_directory(
    request: UpdateDatasetDirectoryRequest,
    dataset_manager: DatasetManager = Depends(get_dataset_manager_dependency)
):
    """Update the datasets directory path."""
    try:
        success = dataset_manager.update_datasets_directory(request.datasets_directory)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update datasets directory")
        
        return {
            "message": "Datasets directory updated successfully",
            "datasets_directory": request.datasets_directory
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update datasets directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))
