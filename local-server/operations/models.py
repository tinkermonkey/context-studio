"""
Operations Database Models

These models are for operational data (audit logs, task management, etc.)
stored in the operations.db database, separate from dataset data.

Schema is automatically managed - no manual migrations needed.
SQLAlchemy's metadata.create_all() handles schema updates automatically.
"""

from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean
from sqlalchemy.orm import declarative_base
import datetime

# Separate base for operations database
OperationsBase = declarative_base()


class AuditLog(OperationsBase):
    """
    Audit log for tracking changes to critical entities.
    
    Tracks who changed what, when, and what the changes were.
    Used for compliance, debugging, and change tracking.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String, nullable=False, index=True)  # e.g., "predicate", "structure_node"
    entity_id = Column(String, nullable=False, index=True)  # ID of the affected entity
    action = Column(String, nullable=False)  # create, update, delete
    user_id = Column(String, nullable=True)  # Optional user ID (may not have auth)
    old_value = Column(Text, nullable=True)  # Previous state as JSON string (for updates/deletes)
    new_value = Column(Text, nullable=True)  # New state as JSON string (for creates/updates)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False, index=True)
    execution_time_ms = Column(Integer, nullable=True)  # Time taken for operation

    def __repr__(self):
        return f"<AuditLog(entity_type='{self.entity_type}', entity_id='{self.entity_id}', action='{self.action}')>"


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
