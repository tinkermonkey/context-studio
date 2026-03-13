"""Pydantic models for dataset management."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class DatasetMetrics(BaseModel):
    """Metrics for a dataset."""

    layers_count: int
    domains_count: int
    terms_count: int
    relationships_count: int


class DatasetInfo(BaseModel):
    """Information about a dataset."""

    id: str
    title: str
    filename: str
    created_at: datetime
    last_accessed: datetime
    schema_version: int
    metrics: DatasetMetrics


class CreateDatasetRequest(BaseModel):
    """Request to create a new dataset."""

    title: str
    filename: str


class AddExistingDatasetRequest(BaseModel):
    """Request to add an existing dataset file."""

    title: str
    file_path: str


class UpdateDatasetDirectoryRequest(BaseModel):
    """Request to update the datasets directory."""

    datasets_directory: str


class MigrationStatus(BaseModel):
    """Status of database migrations."""

    current_version: int
    target_version: int
    pending_migrations: List[str]
    needs_migration: bool


class DatasetResponse(BaseModel):
    """Response model for dataset operations."""

    id: str
    title: str
    filename: str
    created_at: datetime
    last_accessed: datetime
    schema_version: int
    metrics: DatasetMetrics
    is_active: bool


class ActionLogEntry(BaseModel):
    """A single action log entry."""

    timestamp: datetime
    action: str
    dataset_id: str
    dataset_title: Optional[str]
    details: Dict[str, Any]


class ActionLogResponse(BaseModel):
    """Response model for action log."""

    entries: List[ActionLogEntry]
    total_count: int
