"""
SQLAlchemy ORM models for Context Studio.

This module will contain all SQLAlchemy models for the primary database (local.db).
Models are defined here and serve as the source of truth for Alembic migrations.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
