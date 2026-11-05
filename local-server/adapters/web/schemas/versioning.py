"""
Pydantic schemas for the Version Control & Collaboration bounded context.

Response schemas (for HTTP responses):
- VersioningChangeEventResponse
- ChangeHistoryResponse
- SyncStatusResponse
- SyncResultResponse
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.versioning.value_objects import ChangeOperation

class VersioningChangeEventResponse(BaseModel):
    """Response representing a versioning change event"""

    id: str = Field(..., description="Unique identifier of the change event")
    entity_id: str = Field(..., description="ID of the entity that changed")
    entity_type: str = Field(..., description="Type of the entity")
    operation: ChangeOperation = Field(
        ..., description="Type of operation (create, update, delete)"
    )
    new_state: dict = Field(..., description="New state of the entity after this change")
    timestamp: datetime = Field(..., description="When the change occurred")
    processed: bool = Field(..., description="Whether change has been synced to remote")
    user_id: Optional[str] = Field(default=None, description="User who made the change")
    change_reason: Optional[str] = Field(default=None, description="Why the change was made")
    previous_state: Optional[dict] = Field(
        default=None, description="Previous state of the entity before this change"
    )

    model_config = ConfigDict(from_attributes=True)


class ChangeHistoryResponse(BaseModel):
    """Response with paginated change history results"""

    events: list[VersioningChangeEventResponse] = Field(
        ...,
        description=("List of change events matching the query (limited by limit parameter)"),
    )
    total: int = Field(
        ...,
        description=("Total count of all events matching the query (without limit applied)"),
    )


class SyncStatusResponse(BaseModel):
    """Response with synchronization status"""

    unprocessed_count: int = Field(..., description="Number of unprocessed (unsynced) changes")
    is_configured: bool = Field(..., description="Whether remote sync is configured")
    is_degraded: bool = Field(
        default=False,
        description=(
            "Whether sync status is degraded due to errors (unprocessed_count may be" " unreliable)"
        ),
    )
    last_pushed_at: Optional[datetime] = Field(
        default=None, description="ISO timestamp of last successful push"
    )
    last_pulled_at: Optional[datetime] = Field(
        default=None, description="ISO timestamp of last successful pull"
    )

    model_config = ConfigDict(from_attributes=True)


class SyncResultResponse(BaseModel):
    """Response with synchronization operation results"""

    pushed: int = Field(..., description="Number of events pushed")
    pulled: int = Field(..., description="Number of events pulled")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")
    started_at: Optional[datetime] = Field(
        default=None, description="ISO timestamp when sync operation started"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="ISO timestamp when sync operation completed"
    )

    model_config = ConfigDict(from_attributes=True)
