"""
Pydantic schemas for the Data Interchange bounded context.

Request schemas:
- ExportRequest: For export operations
- ImportRequest: For import operations (multipart form data)

Response schemas:
- SerializationScopeResponse: Describes what was serialized
- ImportConflictResponse: Conflict details
- ImportPlanResponse: Result of import dry-run
- ResolutionRecordResponse: Applied resolution
- ImportRunResponse: Import run details
- ChangeEventResponse: Change event details
"""

from datetime import datetime
from typing import Optional, Any, List

from pydantic import BaseModel, ConfigDict, Field
from adapters.web.schemas.ontology import ListResponse


# ==================== Serialization Scope Schemas ====================


class SerializationScopeRequest(BaseModel):
    """Request to specify what to export."""

    scope_type: str = Field(
        ..., description="Scope type: whole_graph, taxonomy, scheme, or entity_set"
    )
    taxonomy_id: Optional[str] = Field(None, description="Taxonomy ID for taxonomy scope")
    scheme_id: Optional[str] = Field(None, description="Scheme ID for scheme scope")
    include_descendants: bool = Field(
        False, description="Include descendants for scheme scope"
    )
    entity_ids: Optional[List[str]] = Field(None, description="Entity IDs for entity_set scope")


class SerializationScopeResponse(BaseModel):
    """Response describing what was serialized."""

    scope_type: str
    taxonomy_id: Optional[str] = None
    scheme_id: Optional[str] = None
    include_descendants: bool = False
    entity_ids: Optional[List[str]] = None


# ==================== Export Schemas ====================


class ExportRequest(BaseModel):
    """Request to export ontology data."""

    format: str = Field(
        ..., description="Export format: skos, owl, graphml, etc.", min_length=1
    )
    scope: SerializationScopeRequest = Field(..., description="What to export")


# ==================== Import Conflict and Plan Schemas ====================


class ImportConflictResponse(BaseModel):
    """Represents a conflict detected during import."""

    match_kind: str = Field(
        ..., description="Type of match: external_reference, uuid, or title"
    )
    incoming: dict[str, Any] = Field(..., description="Incoming entity data")
    existing: Optional[str] = Field(None, description="Reference to existing entity")
    default_resolution: str = Field(..., description="Default resolution strategy")
    available_resolutions: List[str] = Field(..., description="Available resolutions")


class ResolutionRecordResponse(BaseModel):
    """Record of a resolution applied during import."""

    match_kind: str = Field(..., description="Type of match that was resolved")
    entity_id: str = Field(..., description="Entity ID involved")
    resolution_chosen: str = Field(..., description="Resolution applied")


class ImportPlanResponse(BaseModel):
    """Result of an import dry-run, describing what would be imported."""

    conflicts: List[ImportConflictResponse] = Field(
        default_factory=list, description="Detected conflicts"
    )
    new_entity_count: int = Field(
        ..., description="Number of new entities to be created"
    )
    import_run_id: Optional[str] = Field(None, description="Prospective import run ID")
    warnings: List[str] = Field(
        default_factory=list, description="Warning messages"
    )
    source_hash: Optional[str] = Field(None, description="SHA256 hash of imported bytes")
    scope: Optional[SerializationScopeResponse] = Field(None, description="Import scope")


# ==================== Import Run Schemas ====================


class ImportRunResponse(BaseModel):
    """Response containing import run data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    created_by: Optional[str] = Field(None, description="User who initiated the import")
    format: str = Field(..., description="Format of imported file")
    source_uri: Optional[str] = Field(None, description="URI or filename of source")
    source_hash: str = Field(..., description="SHA256 hash of imported bytes")
    scope: SerializationScopeResponse = Field(..., description="Import scope")
    resolutions: List[ResolutionRecordResponse] = Field(
        default_factory=list, description="Applied conflict resolutions"
    )
    affected_entity_ids: List[str] = Field(
        default_factory=list, description="Entities affected by import"
    )
    status: str = Field(
        ..., description="Current status: pending, committed, failed, or rolled_back"
    )


# ==================== Change Event Schemas ====================


class ChangeEventResponse(BaseModel):
    """Response containing change event data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier")
    timestamp: datetime = Field(..., description="When the change occurred")
    entity_id: str = Field(..., description="Entity that changed")
    entity_type: str = Field(..., description="Type of entity")
    operation: str = Field(..., description="Operation performed")
    new_state: Optional[dict[str, Any]] = Field(None, description="New state after change")
    previous_state: Optional[dict[str, Any]] = Field(
        None, description="Previous state before change"
    )


