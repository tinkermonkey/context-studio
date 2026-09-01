"""
API Models for Version Management

This module contains the Pydantic models for the version management system,
supporting entity versioning, working tree state, and diff operations.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    content: dict[str, Any] = Field(
        ..., description="Full entity snapshot as JSON"
    )
    state: ChangeStateEnum = ChangeStateEnum.WORKING
    author_id: str = Field(..., min_length=1, max_length=255)
    metadata: dict[str, Any] | None = None


class EntityVersionOut(EntityVersionBase):
    """Model for entity version output/response."""

    id: UUID
    version_number: int
    parent_version_id: UUID | None = None
    changeset_id: UUID | None = None
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
    parent_version_id: UUID | None = None
    changeset_id: UUID | None = None

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
    has_changes: bool = Field(
        ..., description="Whether working differs from canonical"
    )

    model_config = ConfigDict(from_attributes=True)


class WorkingTreeStatusOut(BaseModel):
    """Model for working tree status output/response."""

    total_entities: int
    modified_entities: int
    staged_entities: int
    unstaged_entities: int
    entries: list[WorkingTreeEntryOut]


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
    before_version: EntityVersionSummary | None = None
    after_version: EntityVersionSummary
    changes: dict[str, Any] = Field(
        ..., description="Structured diff using DeepDiff format"
    )
    summary: DiffSummaryOut
    has_changes: bool
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Request Models


class RollbackRequest(BaseModel):
    """Model for rollback operation request."""

    target_version_number: int = Field(
        ..., ge=1, description="Version number to rollback to", alias="target_version"
    )
    author_id: str = Field(..., min_length=1, max_length=255)

    model_config = ConfigDict(populate_by_name=True)


class StateUpdateRequest(BaseModel):
    """Model for updating version state."""

    new_state: ChangeStateEnum
    author_id: str = Field(..., min_length=1, max_length=255)


class CommitRequest(BaseModel):
    """Model for committing staged changes."""

    author_id: str = Field(..., min_length=1, max_length=255)
    message: str | None = Field(
        None, max_length=1000, description="Optional commit message"
    )


class StageRequest(BaseModel):
    """Model for staging/unstaging entities."""

    entity_type: EntityTypeEnum
    entity_id: UUID


# Batch Operation Models


class BatchStageRequest(BaseModel):
    """Model for batch staging operations."""

    entities: list[StageRequest] = Field(..., min_length=1)


class BatchOperationResult(BaseModel):
    """Model for batch operation results."""

    successful: list[dict[str, Any]]
    failed: list[dict[str, Any]]
    total_requested: int
    total_successful: int
    total_failed: int


# Query Models


class VersionQueryParams(BaseModel):
    """Model for version query parameters."""

    entity_type: EntityTypeEnum | None = None
    entity_id: UUID | None = None
    state: ChangeStateEnum | None = None
    author_id: str | None = None
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
    before_version_number: int | None = Field(
        None, ge=0, alias="before_version"
    )  # Allow 0
    after_version_number: int = Field(..., ge=1, alias="after_version")
    format: DiffFormatEnum = DiffFormatEnum.SUMMARY

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("before_version_number")
    @classmethod
    def validate_before_version(cls, v, info):
        if v is not None and "after_version_number" in info.data:
            if v >= info.data["after_version_number"]:
                raise ValueError(
                    "before_version must be less than after_version"
                )
        return v


# Health and Status Models


class VersionManagementHealthOut(BaseModel):
    """Model for version management system health."""

    status: str = Field(
        ..., description="Overall health status: healthy, warning, error"
    )
    total_versions: int
    total_working_tree_entries: int
    total_staged_entities: int
    total_modified_entities: int
    issues: list[str] = Field(default_factory=list)
    last_event_processed: datetime | None = None
    database_status: str


class VersionManagementStatsOut(BaseModel):
    """Model for version management statistics."""

    versions_by_entity_type: dict[str, int]
    versions_by_state: dict[str, int]
    working_tree_summary: WorkingTreeStatusOut
    recent_activity: list[dict[str, Any]]
    performance_metrics: dict[str, Any]
