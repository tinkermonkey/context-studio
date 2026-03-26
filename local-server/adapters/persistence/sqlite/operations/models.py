"""
SQLAlchemy ORM models for operations.db (LLM Pipeline Management, Background Tasks).

This module will contain ORM models for:
- PipelineConfiguration
- Execution (execution logs and LLM traceability)
- BackgroundTask

Models are defined here and serve as the source of truth for Alembic migrations.
Currently a placeholder for the operations.db Alembic environment.
"""

from sqlalchemy.orm import declarative_base

OperationsBase = declarative_base()
