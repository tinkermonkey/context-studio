"""
SQLAlchemy ORM models for operations.db (LLM Pipeline Management, Background Tasks).

This module contains ORM models for:
- PipelineConfiguration: Configuration for LLM pipelines with provider settings and prompts
- Execution: Execution logs and LLM traceability with instrumentation (tokens, duration, status)

Models are defined here and serve as the source of truth for Alembic migrations.
"""


from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, Index
from sqlalchemy.orm import declarative_base

OperationsBase = declarative_base()  # type: ignore[name-defined,var-annotated]


class PipelineConfigurationModel(OperationsBase):  # type: ignore[misc,valid-type]
    """
    SQLAlchemy ORM model for LLM pipeline configurations in operations.db.

    Attributes:
        id: UUID as string, primary key
        pipeline: Pipeline identifier/slug for categorization
        title: Human-readable title
        provider: LLM provider name ("openai" | "anthropic")
        model: Model identifier (e.g., "gpt-4", "claude-opus")
        config: JSON dict of provider-specific settings (timeout, temperature, etc.)
        system_prompt: System prompt to guide model behavior
        user_prompt: User message template with {text} placeholder
        version: Configuration version number for tracking changes
        enabled: Whether this configuration is active
        created_at: UTC timestamp of creation
        last_updated: UTC timestamp of most recent update
    """

    __tablename__ = "pipeline_configurations"

    id = Column(String(36), primary_key=True, nullable=False)
    pipeline = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(255), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    last_updated = Column(DateTime, nullable=False)


class ExecutionModel(OperationsBase):  # type: ignore[misc,valid-type]
    """
    SQLAlchemy ORM model for pipeline execution records in operations.db.

    Tracks each LLM invocation with complete instrumentation for observability
    and debugging.

    Attributes:
        id: UUID as string, primary key
        pipeline_config_id: Foreign key to the PipelineConfiguration that was executed
        input_text: The text provided to the LLM
        output_text: The generated response from the LLM
        provider: LLM provider that executed the request
        model: Model that generated the response
        tokens_in: Number of tokens in the input
        tokens_out: Number of tokens in the output
        duration_ms: Execution duration in milliseconds
        status: Completion status ("success" | "error" | "timeout")
        error_message: Error description if status is "error", None otherwise
        timestamp: UTC timestamp when the execution occurred
    """

    __tablename__ = "pipeline_executions"

    id = Column(String(36), primary_key=True, nullable=False)
    pipeline_config_id = Column(String(36), nullable=False, index=True)
    input_text = Column(Text, nullable=True)
    output_text = Column(Text, nullable=True)
    provider = Column(String(50), nullable=True)
    model = Column(String(255), nullable=True)
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Index for common query patterns: list executions for a config ordered by timestamp
    __table_args__ = (
        Index("ix_executions_config_timestamp", "pipeline_config_id", "timestamp"),
    )
