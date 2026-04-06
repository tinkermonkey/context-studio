"""
Pydantic schemas for the admin and system endpoints.

Request schemas:
- ConfigSectionUpdateRequest - Request to update a configuration section

Response schemas:
- SystemHealthResponse - Health check endpoint response
- DatabaseHealthResponse - Database health status details
- ServiceMetricsResponse - Service-level metrics
- ComponentStatusResponse - Individual component status
- BackgroundTaskSummaryResponse - Summary of background task execution
- AppConfigurationResponse - Full application configuration (reused for retrieval and reset)
- BackgroundTaskResponse - Background task status and metadata

These schemas handle serialization/deserialization between HTTP and domain models.
API key masking is applied at serialization time in AppConfigurationResponse.
"""

import copy
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from domain.admin.value_objects import CREDENTIAL_FIELD_NAMES
from utils.logger import get_logger

logger = get_logger(__name__)


def _mask_credential_sections(sections: dict) -> dict:
    """
    Mask sensitive credential fields in configuration sections.

    Replaces credential values with '***<last4>' format to prevent exposure
    in logs and API responses. Non-dict section values are replaced with None
    to prevent potential credential leakage from corrupted configuration.

    Args:
        sections: Dictionary of configuration sections

    Returns:
        Deep copy of sections with credential fields masked and invalid sections replaced with None
    """
    masked_sections = copy.deepcopy(sections)

    for section_name, section in masked_sections.items():
        if section is None:
            continue
        if not isinstance(section, dict):
            logger.warning(
                f"Configuration section '{section_name}' is not a dict: {type(section).__name__}. "
                "Replacing with None to prevent credential leakage."
            )
            masked_sections[section_name] = None
            continue
        for field_name in list(section.keys()):
            if field_name in CREDENTIAL_FIELD_NAMES and section[field_name]:
                val = str(section[field_name])
                section[field_name] = f'***{val[-4:]}' if len(val) >= 4 else '***'

    return masked_sections


class SystemHealthResponse(BaseModel):
    """Response containing system health status and component readiness."""

    status: str = Field(
        ...,
        description='Overall health status: "healthy", "degraded", or "unhealthy"'
    )
    database_connected: bool = Field(
        ...,
        description="Whether database is accessible"
    )
    nlp_pipeline_ready: bool = Field(
        ...,
        description="Whether spaCy NLP model is loaded and ready"
    )
    embedding_model_loaded: bool = Field(
        ...,
        description="Whether embedding model is loaded in memory"
    )
    llm_providers_available: list[str] = Field(
        default_factory=list,
        description="List of available LLM provider names"
    )
    uptime_seconds: float = Field(
        ...,
        description="System uptime in seconds since startup"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of identified health issues (if any)"
    )
    checked_at: datetime = Field(
        ...,
        description="Timestamp when health check was performed"
    )

    model_config = ConfigDict(from_attributes=True)


class DatabaseHealthResponse(BaseModel):
    """Response containing database health status details."""

    connected: bool = Field(
        ...,
        description="Whether database is accessible"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of any database issues encountered"
    )

    model_config = ConfigDict(from_attributes=True)


class ServiceMetricsResponse(BaseModel):
    """Response containing service-level metrics."""

    uptime_seconds: float = Field(
        ...,
        description="System uptime in seconds since startup"
    )
    llm_providers_available: list[str] = Field(
        default_factory=list,
        description="List of available LLM provider names"
    )

    model_config = ConfigDict(from_attributes=True)


class ComponentStatusResponse(BaseModel):
    """Response containing individual component status."""

    available: bool = Field(
        ...,
        description="Whether the component is available/ready"
    )
    details: str = Field(
        default="",
        description="Human-readable detail about component status"
    )

    model_config = ConfigDict(from_attributes=True)


class BackgroundTaskSummaryResponse(BaseModel):
    """Response containing summary of background task execution status."""

    total: int = Field(
        ...,
        description="Total number of background tasks registered"
    )
    by_status: dict[str, int] = Field(
        default_factory=dict,
        description="Count of tasks grouped by status"
    )

    model_config = ConfigDict(from_attributes=True)


class ConfigSectionUpdateRequest(BaseModel):
    """Request to update a configuration section."""

    updates: dict = Field(
        ...,
        description="Dictionary of key-value pairs to update in the section"
    )


class AppConfigurationResponse(BaseModel):
    """Response containing application configuration with masked API keys.

    Used for both configuration retrieval and reset operations. Sensitive values
    (API keys and other credentials) are masked to prevent exposure in logs and
    API responses.
    """

    sections: dict = Field(
        ...,
        description="Configuration sections with sensitive values masked"
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, config) -> 'AppConfigurationResponse':
        """
        Convert domain AppConfiguration to response, masking sensitive values.

        Credential fields are replaced with '***<last4>' to prevent exposure in logs
        and API responses.

        Args:
            config: Domain AppConfiguration entity

        Returns:
            AppConfigurationResponse with masked credential fields
        """
        sections = _mask_credential_sections(config.sections)
        return cls(sections=sections)


class BackgroundTaskResponse(BaseModel):
    """Response containing background task status and metadata."""

    id: str = Field(
        ...,
        description="Unique task identifier"
    )
    name: str = Field(
        ...,
        description="Human-readable task name"
    )
    status: str = Field(
        ...,
        description='Task status: "pending", "running", "completed", or "failed"'
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when task was registered"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when task execution began"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when task finished"
    )
    progress: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Task progress as a float between 0.0 and 1.0"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if task failed"
    )
    result: Optional[dict] = Field(
        default=None,
        description="Result data if task completed successfully"
    )

    model_config = ConfigDict(from_attributes=True)
