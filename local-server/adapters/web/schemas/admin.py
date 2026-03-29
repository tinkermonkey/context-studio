"""
Pydantic schemas for the admin and system endpoints.

Response schemas:
- SystemHealthResponse - Health check endpoint response

These schemas handle serialization/deserialization between HTTP and domain models.
"""

from pydantic import BaseModel, Field


class SystemHealthResponse(BaseModel):
    """Response containing system health status and capabilities."""

    status: str = Field(
        ...,
        description='Overall health status: "healthy", "degraded", or "unhealthy"'
    )
    nlp_pipeline_ready: bool = Field(
        ...,
        description="Whether spaCy NLP model is loaded and ready"
    )
    llm_providers_available: list[str] = Field(
        default_factory=list,
        description="List of available LLM model identifiers"
    )

    class Config:
        from_attributes = True
