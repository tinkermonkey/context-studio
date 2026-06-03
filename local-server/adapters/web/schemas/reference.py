"""
Pydantic schemas for the Reference Sources API.

Request schemas (for POST):
- ReferenceSearchRequest
- ReferenceRelationsRequest

Response schemas (for GET/returns):
- ReferenceResultSchema
- ReferenceRelationSchema
- ReferenceSearchResponseSchema
- ReferenceRelationsResponseSchema
- ReferenceSourceStatusSchema
- ReferenceStatusResponseSchema

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReferenceSearchRequest(BaseModel):
    """Request to search for references across available sources."""

    term: str = Field(..., description="Search term", min_length=1)
    limit: int = Field(10, description="Maximum results per source", ge=1, le=100)
    sources: Optional[list[str]] = Field(
        None, description="Specific sources to search (if None, searches all available)"
    )


class ReferenceRelationsRequest(BaseModel):
    """Request to retrieve relationships for a reference URI."""

    uri: str = Field(..., description="Reference URI", min_length=1)
    limit: int = Field(10, description="Maximum relations to return", ge=1, le=100)
    sources: Optional[list[str]] = Field(
        None, description="Specific sources to query (if None, queries all available)"
    )


class ReferenceResultSchema(BaseModel):
    """Response containing a single reference search result."""

    model_config = ConfigDict(from_attributes=True)

    uri: str = Field(..., description="Unique URI for this resource")
    label: str = Field(..., description="Human-readable label")
    description: Optional[str] = Field(None, description="Optional description")
    confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="Confidence score (0.0-1.0)"
    )
    source: str = Field(..., description="Reference source name")


class ReferenceRelationSchema(BaseModel):
    """Response containing a single reference relationship."""

    model_config = ConfigDict(from_attributes=True)

    subject_uri: str = Field(..., description="Source concept URI")
    predicate: str = Field(..., description="Relationship type")
    object_uri: str = Field(..., description="Target concept URI")
    weight: Optional[float] = Field(None, description="Optional relationship weight")
    source: str = Field(..., description="Reference source name")


class ReferenceSearchResponseSchema(BaseModel):
    """Response containing search results aggregated from multiple sources."""

    model_config = ConfigDict(from_attributes=True)

    term: str = Field(..., description="The search term that was executed")
    results: list[ReferenceResultSchema] = Field(
        default_factory=list,
        description="Aggregated results from all sources",
    )
    sources_searched: list[str] = Field(
        default_factory=list,
        description="Names of sources that were searched",
    )
    sources_failed: list[str] = Field(
        default_factory=list,
        description="Names of sources that failed or were unavailable",
    )
    total_results: int = Field(
        0,
        description="Total number of results returned",
    )


class ReferenceRelationsResponseSchema(BaseModel):
    """Response containing relationships aggregated from multiple sources."""

    model_config = ConfigDict(from_attributes=True)

    uri: str = Field(..., description="The URI that was queried")
    relations: list[ReferenceRelationSchema] = Field(
        default_factory=list,
        description="Aggregated relationships from all sources",
    )
    sources_queried: list[str] = Field(
        default_factory=list,
        description="Names of sources that were queried",
    )
    sources_failed: list[str] = Field(
        default_factory=list,
        description="Names of sources that failed or were unavailable",
    )
    total_relations: int = Field(
        0,
        description="Total number of relations returned",
    )


class ReferenceSourceStatusSchema(BaseModel):
    """Status information for a single reference source."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Source name")
    available: bool = Field(..., description="Whether source is currently available")
    last_checked: Optional[str] = Field(
        None,
        description="ISO 8601 timestamp of last availability check",
    )


class ReferenceStatusResponseSchema(BaseModel):
    """Response containing status of all reference sources."""

    model_config = ConfigDict(from_attributes=True)

    sources: list[ReferenceSourceStatusSchema] = Field(
        default_factory=list,
        description="Status of each reference source",
    )
    sources_available: int = Field(
        0,
        description="Count of available sources",
    )
    timestamp: str = Field(..., description="ISO 8601 timestamp of this status check")


# ==================== Grounding Workflow Schemas ====================


class GroundingWorkflowCreate(BaseModel):
    """Request to create a new grounding workflow."""

    title: str = Field(..., description="Human-readable workflow name", min_length=1)
    source: str = Field(
        ...,
        description="External knowledge source name (e.g. 'ConceptNet', 'schema.org')",
        min_length=1,
    )
    class_scope: list[str] = Field(
        default_factory=list,
        description="List of class IDs or names to scope enrichment",
    )
    description: Optional[str] = Field(None, description="Optional description")


class GroundingWorkflowUpdate(BaseModel):
    """Request to update an existing grounding workflow."""

    title: Optional[str] = Field(
        None, description="Human-readable workflow name", min_length=1
    )
    source: Optional[str] = Field(None, description="External knowledge source name")
    class_scope: Optional[list[str]] = Field(
        None, description="List of class IDs or names to scope enrichment"
    )
    status: Optional[str] = Field(
        None, description="Workflow status: active, inactive, error"
    )
    description: Optional[str] = Field(None, description="Optional description")


class GroundingWorkflowResponse(BaseModel):
    """Response containing a grounding workflow record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Workflow UUID")
    title: str = Field(..., description="Human-readable workflow name")
    description: Optional[str] = Field(None, description="Optional description")
    source: str = Field(..., description="External knowledge source name")
    class_scope: list[str] = Field(
        default_factory=list,
        description="List of class IDs or names to scope enrichment",
    )
    status: str = Field(..., description="Workflow status: active, inactive, error")
    last_run: Optional[str] = Field(
        None, description="ISO 8601 timestamp of most recent run"
    )
    last_run_record_count: Optional[int] = Field(
        None, description="Record count from most recent run"
    )


class WorkflowRunResponse(BaseModel):
    """Response containing a single workflow run record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Run UUID")
    workflow_id: str = Field(..., description="Parent workflow UUID")
    status: str = Field(..., description="Run status: running, success, failed")
    record_count: int = Field(0, description="Number of records processed")
    timestamp: str = Field(..., description="ISO 8601 timestamp when run was initiated")
    error_message: Optional[str] = Field(
        None, description="Error message if status is failed"
    )
