from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UniqueConstraint  # noqa: E501
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import declarative_base, relationship, Mapped
from typing import Any, cast
import uuid
import datetime

from sqlalchemy import JSON, Boolean
from database.custom_types import NodeTypeColumn, RecordTypeColumn
from database.enums import NodeType, RecordType

Base: Any = declarative_base()

# Enums for the new normalized schema (moved to database.enums to avoid circular imports)  # noqa: E501


class PipelineFlavor(Base):
    __tablename__ = "pipeline_flavors"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline = Column(String, nullable=False)
    title = Column(String, nullable=False)
    llm_provider = Column(String, nullable=False)
    llm_model = Column(String, nullable=False)
    llm_config = Column(JSON, nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    last_updated = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
    date_created = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))  # noqa: E501

    __table_args__ = (UniqueConstraint("pipeline", "title", name="_pipeline_title_uc"),)  # noqa: E501


class Predicate(Base):
    __tablename__ = "predicates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String, unique=True, nullable=False)
    title = Column(String, unique=True, nullable=False)
    definition = Column(Text, nullable=True)
    mapping = Column(Text, nullable=True)  # JSON string
    is_relevant = Column(Boolean, nullable=True)  # None=not evaluated, True=relevant, False=irrelevant  # noqa: E501
    date_created = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))  # noqa: E501
    date_modified = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Relationships for new unified schema
    structure_nodes = relationship("StructureNode", back_populates="structural_predicate_ref")  # noqa: E501
    structure_node_links = relationship("StructureNodeLink", back_populates="predicate_ref")  # noqa: E501


# New Normalized Schema Models


class StructureNode(Base):
    """Unified structure_node table for layers, domains, and terms."""

    __tablename__ = "structure_nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_type: Mapped[NodeType] = cast(Mapped[NodeType], Column(NodeTypeColumn(), nullable=False))  # noqa: E501
    parent_node_id = Column(String, ForeignKey("structure_nodes.id", ondelete="CASCADE"), nullable=True)  # noqa: E501
    title = Column(String, nullable=False)
    definition = Column(Text, nullable=True)
    structural_predicate_id = Column(String, ForeignKey("predicates.id"), nullable=True)  # noqa: E501
    title_embedding = Column(BLOB, nullable=True, default=None)
    definition_embedding = Column(BLOB, nullable=True, default=None)
    reference_links = Column(Text, nullable=True)  # JSON array of reference links  # noqa: E501
    word_senses = Column(Text, nullable=True)  # JSON array of word senses
    attributes = Column(Text, nullable=True)  # JSON array of attributes
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))  # noqa: E501
    version = Column(Integer, default=1)
    last_modified = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Self-referential relationship for hierarchy
    # Note: Using lazy="noload" prevents automatic loading of parent to avoid circular reference issues with JSON serialization  # noqa: E501
    parent = relationship("StructureNode", remote_side=[id], lazy="noload")

    # Relationship to predicates
    structural_predicate_ref = relationship("Predicate", back_populates="structure_nodes", lazy="select")  # noqa: E501


class StructureNodeLink(Base):
    """Unified links table for all structure_node relationships."""

    __tablename__ = "structure_node_links"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_node_id = Column(String, ForeignKey("structure_nodes.id", ondelete="CASCADE"), nullable=False)  # noqa: E501
    target_node_id = Column(String, ForeignKey("structure_nodes.id", ondelete="CASCADE"), nullable=False)  # noqa: E501
    predicate = Column(String, nullable=False)
    predicate_id = Column(String, ForeignKey("predicates.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))  # noqa: E501

    # Relationships
    source_node = relationship("StructureNode", foreign_keys=[source_node_id], lazy="select")  # noqa: E501
    target_node = relationship("StructureNode", foreign_keys=[target_node_id], lazy="select")  # noqa: E501
    predicate_ref = relationship("Predicate", back_populates="structure_node_links", lazy="select")  # noqa: E501

    __table_args__ = (UniqueConstraint("source_node_id", "target_node_id", "predicate", name="_node_link_uc"),)  # noqa: E501


class ChangeEvent(Base):
    """Unified events table for all change events across record types."""

    __tablename__ = "change_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)  # create, update, delete
    record_type: Mapped[RecordType] = cast(Mapped[RecordType], Column(RecordTypeColumn(), nullable=False))  # structure_node, structure_node_link, predicate  # noqa: E501
    record_id = Column(String, nullable=True)  # ID of the affected record
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)  # noqa: E501
    processed = Column(Boolean, default=False, nullable=False)


# Legacy alias for backwards compatibility during transition
NodeEvent = ChangeEvent
