"""
Pydantic schemas for the admin and system endpoints.

Request schemas:
- ConfigSectionUpdateRequest - Request to update a configuration section

Response schemas:
- SystemHealthResponse - Health check endpoint response
- AppConfigurationResponse - Full application configuration
- BackgroundTaskResponse - Background task status and metadata

These schemas handle serialization/deserialization between HTTP and domain models.
API key masking is applied at serialization time in AppConfigurationResponse.
"""

import copy
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class ConfigSectionUpdateRequest(BaseModel):
    """Request to update a configuration section."""

    updates: dict = Field(
        ...,
        description="Dictionary of key-value pairs to update in the section"
    )


class AppConfigurationResponse(BaseModel):
    """Response containing application configuration with masked API keys."""

    sections: dict = Field(
        ...,
        description="Configuration sections with sensitive values masked"
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, config) -> 'AppConfigurationResponse':
        """
        Convert domain AppConfiguration to response, masking sensitive values.

        API keys in the 'llm' section are replaced with '***<last4>' to prevent
        exposure in logs and API responses.

        Args:
            config: Domain AppConfiguration entity

        Returns:
            AppConfigurationResponse with masked API keys
        """
        sections = copy.deepcopy(config.sections)
        key_fields = {'openai_api_key', 'anthropic_api_key', 's3_secret_key'}

        for section in sections.values():
            if isinstance(section, dict):
                for field_name in list(section.keys()):
                    if field_name in key_fields and section[field_name]:
                        val = str(section[field_name])
                        section[field_name] = f'***{val[-4:]}' if len(val) >= 4 else '***'

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
    error: Optional[str] = Field(
        default=None,
        description="Error message if task failed"
    )
    result: Optional[dict] = Field(
        default=None,
        description="Result data if task completed successfully"
    )

    model_config = ConfigDict(from_attributes=True)
