"""
Pydantic schemas for the LLM Pipeline Management bounded context.

Request schemas (for POST/PUT):
- PipelineConfigurationCreate
- PipelineExecuteRequest

Response schemas (for GET/returns):
- PipelineConfigurationResponse
- ExecutionResponse

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineConfigurationCreate(BaseModel):
    """Request to create a new pipeline configuration."""

    pipeline: str = Field(
        ..., description="Pipeline identifier/slug for categorization", min_length=1
    )
    title: str = Field(
        ..., description="Human-readable title for the pipeline", min_length=1
    )
    provider: str = Field(
        ..., description="LLM provider name (openai, anthropic)", min_length=1
    )
    model: str = Field(
        ..., description="Model identifier (e.g., gpt-4, claude-opus)", min_length=1
    )
    config: dict = Field(
        default_factory=dict, description="Provider-specific configuration"
    )
    system_prompt: str = Field(
        ..., description="System prompt to guide model behavior", min_length=1
    )
    user_prompt: str = Field(
        ..., description="User message template with {text} placeholder", min_length=1
    )
    enabled: bool = Field(
        default=True, description="Whether this configuration is active"
    )


class PipelineConfigurationUpdate(BaseModel):
    """Request to update a pipeline configuration."""

    title: Optional[str] = Field(None, description="Updated title", min_length=1)
    provider: Optional[str] = Field(None, description="Updated provider", min_length=1)
    model: Optional[str] = Field(None, description="Updated model", min_length=1)
    config: Optional[dict] = Field(None, description="Updated configuration")
    system_prompt: Optional[str] = Field(
        None, description="Updated system prompt", min_length=1
    )
    user_prompt: Optional[str] = Field(
        None, description="Updated user prompt", min_length=1
    )
    enabled: Optional[bool] = Field(None, description="Updated enabled status")


class PipelineConfigurationResponse(BaseModel):
    """Response containing pipeline configuration data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier")
    pipeline: str = Field(..., description="Pipeline identifier/slug")
    title: str = Field(..., description="Human-readable title")
    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model identifier")
    config: dict = Field(
        default_factory=dict, description="Provider-specific configuration"
    )
    system_prompt: str = Field(..., description="System prompt")
    user_prompt: str = Field(..., description="User message template")
    version: int = Field(..., description="Configuration version number")
    enabled: bool = Field(..., description="Whether this configuration is active")
    created_at: datetime = Field(..., description="ISO 8601 creation timestamp")
    last_updated: datetime = Field(..., description="ISO 8601 last update timestamp")


class PipelineExecuteRequest(BaseModel):
    """Request to execute a pipeline."""

    input_text: str = Field(..., description="Input text to process", min_length=1)


class ExecutionResponse(BaseModel):
    """Response containing pipeline execution record data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier for this execution")
    pipeline_config_id: str = Field(
        ..., description="ID of the executed PipelineConfiguration"
    )
    output_text: str = Field(..., description="The generated response from the LLM")
    provider: str = Field(..., description="LLM provider that executed the request")
    model: str = Field(..., description="Model that generated the response")
    tokens_in: int = Field(..., description="Number of tokens in the input")
    tokens_out: int = Field(..., description="Number of tokens in the output")
    duration_ms: int = Field(..., description="Execution duration in milliseconds")
    status: Literal["success", "error", "timeout"] = Field(
        ..., description="Completion status (success, error, timeout)"
    )
    error_message: Optional[str] = Field(
        None, description="Error description if applicable"
    )
    timestamp: datetime = Field(..., description="ISO 8601 execution timestamp")


class ExecutionWithPipelineResponse(BaseModel):
    """Response containing execution record with associated pipeline configuration name."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier for this execution")
    pipeline_config_id: str = Field(
        ..., description="ID of the executed PipelineConfiguration"
    )
    pipeline_title: str = Field(
        ..., description="Title of the pipeline configuration that was executed"
    )
    output_text: str = Field(..., description="The generated response from the LLM")
    provider: str = Field(..., description="LLM provider that executed the request")
    model: str = Field(..., description="Model that generated the response")
    tokens_in: int = Field(..., description="Number of tokens in the input")
    tokens_out: int = Field(..., description="Number of tokens in the output")
    duration_ms: int = Field(..., description="Execution duration in milliseconds")
    status: Literal["success", "error", "timeout"] = Field(
        ..., description="Completion status (success, error, timeout)"
    )
    error_message: Optional[str] = Field(
        None, description="Error description if applicable"
    )
    timestamp: datetime = Field(..., description="ISO 8601 execution timestamp")
