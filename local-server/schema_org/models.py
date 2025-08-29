"""
SQLAlchemy models for the schema.org local database.

This file contains lightweight model definitions used by the schema_org manager.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import declarative_base, relationship
import uuid
import datetime

Base = declarative_base()


class SchemaOrgEntity(Base):
    """Represents a schema.org entity (class).

    Fields mirror the design in documentation/requirements/08.1_schema_org_requirements.md
    """

    __tablename__ = "schema_org_entities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    title_embedding = Column(BLOB, nullable=True)
    definition = Column(Text, nullable=True)
    definition_embedding = Column(BLOB, nullable=True)
    parent_identifier = Column(String, nullable=True)
    parent_id = Column(String, ForeignKey("schema_org_entities.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    raw = Column(JSON, nullable=False)

    parent = relationship("SchemaOrgEntity", remote_side=[id], backref="children")


class SchemaOrgProperty(Base):
    """Represents a schema.org property definition."""

    __tablename__ = "schema_org_properties"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    title_embedding = Column(BLOB, nullable=True)
    definition = Column(Text, nullable=True)
    definition_embedding = Column(BLOB, nullable=True)
    contributors = Column(JSON, nullable=True)
    domain_includes = Column(JSON, nullable=True)
    range_includes = Column(JSON, nullable=True)
    inverse_of = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    raw = Column(JSON, nullable=False)
