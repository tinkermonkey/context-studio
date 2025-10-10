"""
Operations Database Models

These models are for operational data (task management, LLM traceability, etc.)
stored in the operations.db database, separate from dataset data.

Schema is automatically managed - no manual migrations needed.
SQLAlchemy's metadata.create_all() handles schema updates automatically.

Note: For change tracking, use the ChangeEvent model in database.models instead.
"""

from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean
from sqlalchemy.orm import declarative_base
import datetime

# Separate base for operations database
OperationsBase = declarative_base()


class PipelineFlavor(OperationsBase):
    """Pipeline flavor configuration for LLM operations."""

    __tablename__ = "pipeline_flavors"

    id = Column(String, primary_key=True)
    pipeline = Column(String, nullable=False)
    title = Column(String, nullable=False)
    llm_provider = Column(String, nullable=False)
    llm_model = Column(String, nullable=False)
    llm_config = Column(Text, nullable=False)  # JSON string
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<PipelineFlavor(pipeline='{self.pipeline}', title='{self.title}')>"


class PipelineFlavorExecution(OperationsBase):
    """Execution record for pipeline flavor runs (LLM traceability)."""

    __tablename__ = "pipeline_flavor_executions"

    id = Column(String, primary_key=True)
    pipeline_flavor_id = Column(String, nullable=False, index=True)
    pipeline_type = Column(String, nullable=False)
    pipeline_flavor_version = Column(Integer, nullable=False)
    request_context = Column(Text, nullable=False)  # JSON
    user_prompt = Column(Text, nullable=False)
    response_message = Column(Text, nullable=True)
    structured_output = Column(Text, nullable=True)  # JSON structured output data
    execution_time_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    execution_status = Column(String, nullable=False)  # success, error, timeout
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<PipelineFlavorExecution(id='{self.id}', status='{self.execution_status}')>"
