"""
API Models for Version Management

This module contains the Pydantic models for the version management system,
supporting entity versioning, working tree state, and diff operations.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum
from datetime import datetime


class ChangeStateEnum(str, Enum):
    """API enum for version change states."""
    WORKING = "WORKING"
    STAGED = "STAGED"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    MERGED = "MERGED"
    REJECTED = "REJECTED"


class EntityTypeEnum(str, Enum):
    """API enum for entity types that support versioning."""
    STRUCTURE_NODE = "structure_node"
    STRUCTURE_NODE_LINK = "structure_node_link"


# Version Management Models

class EntityVersionBase(BaseModel):
    """Base model for entity version data."""
    entity_type: EntityTypeEnum
    entity_id: UUID
    content: Dict[str, Any] = Field(..., description="Full entity snapshot as JSON")
    state: ChangeStateEnum = ChangeStateEnum.WORKING
    author_id: str = Field(..., min_length=1, max_length=255)
    metadata: Optional[Dict[str, Any]] = None


class EntityVersionOut(EntityVersionBase):
    """Model for entity version output/response."""
    id: UUID
    version_number: int
    parent_version_id: Optional[UUID] = None
    changeset_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntityVersionSummary(BaseModel):
    """Summary model for entity version (without full content)."""
    id: UUID
    entity_type: EntityTypeEnum
    entity_id: UUID
    version_number: int
    state: ChangeStateEnum
    author_id: str
    created_at: datetime
    parent_version_id: Optional[UUID] = None
    changeset_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


# Working Tree Models

class WorkingTreeEntryOut(BaseModel):
    """Model for working tree entry output/response."""
    entity_type: EntityTypeEnum
    entity_id: UUID
    current_version_id: UUID
    canonical_version_id: UUID
    staged: bool
    modified_at: datetime
    has_changes: bool = Field(..., description="Whether working differs from canonical")

    model_config = ConfigDict(from_attributes=True)


class WorkingTreeStatusOut(BaseModel):
    """Model for working tree status output/response."""
    total_entities: int
    modified_entities: int
    staged_entities: int
    unstaged_entities: int
    entries: List[WorkingTreeEntryOut]


# Diff Models

class DiffSummaryOut(BaseModel):
    """Model for diff summary output/response."""
    added_items: int = 0
    removed_items: int = 0
    modified_items: int = 0
    type_changes: int = 0
    moved_items: int = 0
    total_changes: int = 0


class EntityDiffOut(BaseModel):
    """Model for entity diff output/response."""
    entity_type: EntityTypeEnum
    entity_id: UUID
    before_version: Optional[EntityVersionSummary] = None
    after_version: EntityVersionSummary
    changes: Dict[str, Any] = Field(..., description="Structured diff using DeepDiff format")
    summary: DiffSummaryOut
    has_changes: bool
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Request Models

class RollbackRequest(BaseModel):
    """Model for rollback operation request."""
    target_version_number: int = Field(..., ge=1, description="Version number to rollback to")
    author_id: str = Field(..., min_length=1, max_length=255)


class StateUpdateRequest(BaseModel):
    """Model for updating version state."""
    new_state: ChangeStateEnum
    author_id: str = Field(..., min_length=1, max_length=255)


class CommitRequest(BaseModel):
    """Model for committing staged changes."""
    author_id: str = Field(..., min_length=1, max_length=255)
    message: Optional[str] = Field(None, max_length=1000, description="Optional commit message")


class StageRequest(BaseModel):
    """Model for staging/unstaging entities."""
    entity_type: EntityTypeEnum
    entity_id: UUID


# Batch Operation Models

class BatchStageRequest(BaseModel):
    """Model for batch staging operations."""
    entities: List[StageRequest] = Field(..., min_items=1)


class BatchOperationResult(BaseModel):
    """Model for batch operation results."""
    successful: List[Dict[str, Any]]
    failed: List[Dict[str, Any]]
    total_requested: int
    total_successful: int
    total_failed: int


# Query Models

class VersionQueryParams(BaseModel):
    """Model for version query parameters."""
    entity_type: Optional[EntityTypeEnum] = None
    entity_id: Optional[UUID] = None
    state: Optional[ChangeStateEnum] = None
    author_id: Optional[str] = None
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class DiffFormatEnum(str, Enum):
    """Enum for diff format options."""
    SUMMARY = "summary"
    DETAILED = "detailed" 
    JSON = "json"


class DiffRequest(BaseModel):
    """Model for requesting diffs."""
    entity_type: EntityTypeEnum
    entity_id: UUID
    before_version_number: Optional[int] = Field(None, ge=1)
    after_version_number: int = Field(..., ge=1)
    format: DiffFormatEnum = DiffFormatEnum.SUMMARY


# Health and Status Models

class VersionManagementHealthOut(BaseModel):
    """Model for version management system health."""
    status: str = Field(..., description="Overall health status: healthy, warning, error")
    total_versions: int
    total_working_tree_entries: int
    total_staged_entities: int
    total_modified_entities: int
    issues: List[str] = Field(default_factory=list)
    last_event_processed: Optional[datetime] = None
    database_status: str


class VersionManagementStatsOut(BaseModel):
    """Model for version management statistics."""
    versions_by_entity_type: Dict[str, int]
    versions_by_state: Dict[str, int]
    working_tree_summary: WorkingTreeStatusOut
    recent_activity: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]