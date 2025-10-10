from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import declarative_base, relationship, backref
import uuid
import datetime

from sqlalchemy import JSON, Boolean
from database.custom_types import NodeTypeColumn, RecordTypeColumn

Base = declarative_base()

# Enums for the new normalized schema (moved to database.enums to avoid circular imports)


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
    date_created = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    __table_args__ = (UniqueConstraint("pipeline", "title", name="_pipeline_title_uc"),)


class Predicate(Base):
    __tablename__ = "predicates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String, unique=True, nullable=False)
    title = Column(String, unique=True, nullable=False)
    definition = Column(Text, nullable=True)
    mapping = Column(Text, nullable=True)  # JSON string
    is_relevant = Column(Boolean, nullable=True)  # None=not evaluated, True=relevant, False=irrelevant
    date_created = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    date_modified = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Relationships for new unified schema
    structure_nodes = relationship("StructureNode", back_populates="structural_predicate_ref")
    structure_node_links = relationship("StructureNodeLink", back_populates="predicate_ref")


# New Normalized Schema Models


class StructureNode(Base):
    """Unified structure_node table for layers, domains, and terms."""

    __tablename__ = "structure_nodes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_type = Column(NodeTypeColumn(), nullable=False)
    parent_node_id = Column(String, ForeignKey("structure_nodes.id", ondelete="CASCADE"), nullable=True)
    title = Column(String, nullable=False)
    definition = Column(Text, nullable=True)
    structural_predicate_id = Column(String, ForeignKey("predicates.id"), nullable=True)
    title_embedding = Column(BLOB, nullable=True, default=None)
    definition_embedding = Column(BLOB, nullable=True, default=None)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    version = Column(Integer, default=1)
    last_modified = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Self-referential relationship for hierarchy
    parent = relationship("StructureNode", remote_side=[id], backref=backref("children", lazy="noload"))

    # Relationship to predicates
    structural_predicate_ref = relationship("Predicate", back_populates="structure_nodes", lazy="select")


class StructureNodeLink(Base):
    """Unified links table for all structure_node relationships."""

    __tablename__ = "structure_node_links"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_node_id = Column(String, ForeignKey("structure_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(String, ForeignKey("structure_nodes.id", ondelete="CASCADE"), nullable=False)
    predicate = Column(String, nullable=False)
    predicate_id = Column(String, ForeignKey("predicates.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    source_node = relationship("StructureNode", foreign_keys=[source_node_id], lazy="select")
    target_node = relationship("StructureNode", foreign_keys=[target_node_id], lazy="select")
    predicate_ref = relationship("Predicate", back_populates="structure_node_links", lazy="select")

    __table_args__ = (UniqueConstraint("source_node_id", "target_node_id", "predicate", name="_node_link_uc"),)


class ChangeEvent(Base):
    """Unified events table for all change events across record types."""

    __tablename__ = "change_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)  # create, update, delete
    record_type = Column(RecordTypeColumn(), nullable=False)  # structure_node, structure_node_link, predicate
    record_id = Column(String, nullable=True)  # ID of the affected record
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)
    processed = Column(Boolean, default=False, nullable=False)


# Legacy alias for backwards compatibility during transition
NodeEvent = ChangeEvent
