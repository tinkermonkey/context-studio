"""
Pydantic schemas for the Version Control & Collaboration bounded context.

Request schemas (for POST/PUT bodies):
- ChangesetCreateRequest
- RejectProposalRequest
- ResolveConflictsRequest

Response schemas (for HTTP responses):
- ChangeEventResponse
- ChangeHistoryResponse
- ChangesetResponse
- ProposalResponse
- ConflictResponse
- ConflictReportResponse
- MergeResultResponse
- SyncStatusResponse
- SyncResultResponse
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

from domain.versioning.value_objects import ChangeOperation, ProposalState


# ============================================================================
# Request Schemas
# ============================================================================


class ChangesetCreateRequest(BaseModel):
    """Request to create a new changeset"""

    name: str = Field(..., min_length=1, description="Human-readable name for the changeset")
    description: Optional[str] = Field(default=None, description="Detailed description")
    event_ids: list[str] = Field(default_factory=list, description="Change event IDs to include")


class RejectProposalRequest(BaseModel):
    """Request to reject a proposal"""

    reason: str = Field(..., min_length=1, description="Reason for rejection")


class ResolveConflictsRequest(BaseModel):
    """Request to resolve conflicts in a proposal"""

    resolutions: dict[str, dict[str, Any]] = Field(
        ..., description="Mapping of entity_id -> {field_name: resolved_value}"
    )


# ============================================================================
# Response Schemas
# ============================================================================


class ChangeEventResponse(BaseModel):
    """Response representing a change event"""

    id: str = Field(..., description="Unique identifier of the change event")
    entity_id: str = Field(..., description="ID of the entity that changed")
    entity_type: str = Field(..., description="Type of the entity")
    operation: ChangeOperation = Field(..., description="Type of operation (create, update, delete)")
    timestamp: datetime = Field(..., description="When the change occurred")
    processed: bool = Field(..., description="Whether change has been synced to remote")
    user_id: Optional[str] = Field(default=None, description="User who made the change")
    change_reason: Optional[str] = Field(default=None, description="Why the change was made")

    class Config:
        from_attributes = True


class EntityVersionResponse(BaseModel):
    """Response representing an entity version"""

    entity_id: str = Field(..., description="ID of the entity")
    version: int = Field(..., description="Version number")
    state: str = Field(..., description="State of the entity at this version")
    snapshot: dict = Field(..., description="Snapshot of entity data at this version")
    created_at: datetime = Field(..., description="When this version was created")
    parent_version: Optional[int] = Field(
        default=None, description="Version number of parent; None if this is the first version"
    )

    class Config:
        from_attributes = True


class ChangeHistoryResponse(BaseModel):
    """Response with paginated change history results"""

    events: list[ChangeEventResponse] = Field(..., description="List of change events matching the query (limited by limit parameter)")
    total: int = Field(..., description="Total count of all events matching the query (without limit applied)")


class ChangesetResponse(BaseModel):
    """Response representing a changeset"""

    id: str = Field(..., description="Unique identifier of the changeset")
    name: str = Field(..., description="Human-readable name")
    description: Optional[str] = Field(default=None, description="Detailed description")
    state: str = Field(..., description="Current state (working, staged, proposed, approved, merged)")
    created_at: datetime = Field(..., description="When the changeset was created")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class ProposalResponse(BaseModel):
    """Response representing a proposal"""

    id: str = Field(..., description="Unique identifier of the proposal")
    changeset_id: str = Field(..., description="ID of the associated changeset")
    state: ProposalState = Field(..., description="Current state (open, approved, rejected, merged)")
    submitted_at: datetime = Field(..., description="When the proposal was submitted")
    reviewed_at: Optional[datetime] = Field(default=None, description="When the proposal was reviewed")
    reviewer_notes: Optional[str] = Field(default=None, description="Notes from reviewer")

    class Config:
        from_attributes = True


class ConflictResponse(BaseModel):
    """Response representing a detected conflict"""

    entity_id: str = Field(..., description="ID of the entity with the conflict")
    field_name: str = Field(..., description="Name of the field in conflict")
    base_value: Any = Field(..., description="Value from the base changeset")
    incoming_value: Any = Field(..., description="Value from the incoming changeset")


class ConflictReportResponse(BaseModel):
    """Response with conflict detection results"""

    proposal_id: str = Field(..., description="ID of the proposal")
    conflicts: list[ConflictResponse] = Field(default_factory=list, description="List of conflicts")
    has_conflicts: bool = Field(..., description="Whether any conflicts were detected")


class MergeResultResponse(BaseModel):
    """Response with merge operation results"""

    proposal_id: str = Field(..., description="ID of the merged proposal")
    merged_at: datetime = Field(..., description="When the merge occurred")
    events_applied: int = Field(..., description="Number of change events applied")
    conflicts_resolved: int = Field(..., description="Number of conflicts resolved")

    class Config:
        from_attributes = True


class SyncStatusResponse(BaseModel):
    """Response with synchronization status"""

    unprocessed_count: int = Field(..., description="Number of unprocessed (unsynced) changes")
    is_configured: bool = Field(..., description="Whether remote sync is configured")
    last_pushed_at: Optional[str] = Field(
        default=None, description="ISO timestamp of last successful push"
    )
    last_pulled_at: Optional[str] = Field(
        default=None, description="ISO timestamp of last successful pull"
    )

    class Config:
        from_attributes = True


class SyncResultResponse(BaseModel):
    """Response with synchronization operation results"""

    pushed: int = Field(..., description="Number of events pushed")
    pulled: int = Field(..., description="Number of events pulled")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    class Config:
        from_attributes = True
