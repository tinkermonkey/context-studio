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
from typing import Optional, Any, Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from domain.admin.entities import AppConfiguration
from domain.admin.value_objects import CREDENTIAL_FIELD_NAMES, BackgroundTaskStatus, BackgroundTaskSummary
from utils.logger import get_logger

logger = get_logger(__name__)


def _mask_credentials(section: dict) -> dict:
    """
    Mask sensitive credential fields in a configuration section.

    Replaces credential values with '***<last4>' format to prevent exposure
    in API responses. Recursively masks credentials in nested dicts.

    Args:
        section: Dictionary of configuration

    Returns:
        Deep copy of section with credential fields masked (including nested dicts)
    """
    masked_section = copy.deepcopy(section)

    def mask_dict(d: dict) -> None:
        """Recursively mask credentials in a dictionary."""
        for key, value in d.items():
            if key in CREDENTIAL_FIELD_NAMES and value:
                val = str(value)
                d[key] = f'***{val[-4:]}' if len(val) >= 4 else '***'
            elif isinstance(value, dict):
                mask_dict(value)

    mask_dict(masked_section)
    return masked_section


class SystemHealthResponse(BaseModel):
    """Response containing system health status and component readiness."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
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

    @classmethod
    def from_domain(cls, summary: BackgroundTaskSummary) -> 'BackgroundTaskSummaryResponse':
        """
        Convert domain BackgroundTaskSummary to response, converting enum keys to strings.

        Domain objects use BackgroundTaskStatus enum keys, but JSON responses
        require string keys. This method handles the conversion.

        Args:
            summary: Domain BackgroundTaskSummary entity

        Returns:
            BackgroundTaskSummaryResponse with enum keys converted to string values
        """
        by_status_strings = {
            status.value if isinstance(status, BackgroundTaskStatus) else status: count
            for status, count in summary.by_status.items()
        }
        return cls(total=summary.total, by_status=by_status_strings)


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

    sections: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="All configuration sections with masked credentials"
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, config: AppConfiguration) -> 'AppConfigurationResponse':
        """
        Convert domain AppConfiguration to response, masking sensitive values.

        Credential fields are replaced with '***<last4>' to prevent exposure in logs
        and API responses.

        Args:
            config: Domain AppConfiguration entity

        Returns:
            AppConfigurationResponse with masked credential fields in sections
        """
        sections_masked = {}
        for section_name, section_config in config.sections.items():
            sections_masked[section_name] = _mask_credentials(section_config)

        return cls(sections=sections_masked)


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
    status: Literal["pending", "running", "completed", "failed"] = Field(
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
    error: Optional[str] = Field(
        default=None,
        description="Error message if task failed"
    )
    result: Optional[dict] = Field(
        default=None,
        description="Result data if task completed successfully"
    )

    model_config = ConfigDict(from_attributes=True)
