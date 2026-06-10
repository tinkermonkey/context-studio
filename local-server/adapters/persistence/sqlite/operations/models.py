"""
SQLAlchemy ORM models for operations.db.
"""

from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

OperationsBase = declarative_base()  # type: ignore[valid-type]


class PipelineConfiguration(OperationsBase):
    """
    User-created pipeline configuration record.

    System configs are code-defined and live in the in-memory registry.
    User-created configs are persisted here and loaded into the registry at startup.
    """

    __tablename__ = "pipeline_configurations"

    id = Column(String, primary_key=True)
    config_ref = Column(String, nullable=False, index=True)
    pipeline_type = Column(String, nullable=False, index=True)
    implementation_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    system_prompt = Column(Text)
    user_prompt_template = Column(Text, nullable=False)
    temperature = Column(Float, nullable=False, default=0.4)
    max_tokens = Column(Integer, nullable=False, default=800)
    top_p = Column(Float, nullable=False, default=0.9)
    enabled = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    deleted_at = Column(String)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
