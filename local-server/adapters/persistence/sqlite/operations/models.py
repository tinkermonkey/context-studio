"""
SQLAlchemy ORM models for operations.db (Background Tasks).

This module is currently empty. Legacy models (PipelineConfiguration, Execution,
PipelineFlavorModel) have been removed in Phase 1 legacy demolition.
"""

from sqlalchemy.orm import declarative_base

OperationsBase = declarative_base()  # type: ignore[valid-type]
