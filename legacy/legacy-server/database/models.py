import datetime
import uuid
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import Mapped, declarative_base, relationship, synonym

from database.custom_types import NodeTypeColumn, RecordTypeColumn
from database.enums import NodeType, RecordType

Base: Any = declarative_base()

# Enums for the new normalized schema (moved to database.enums to avoid circular imports)


class PipelineConfiguration(Base):
    __tablename__ = "pipeline_configurations"

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
    date_created = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC)
    )

    __table_args__ = (
        UniqueConstraint("pipeline", "title", name="_pipeline_title_uc"),
    )


# Legacy alias for backwards compatibility
PipelineFlavor = PipelineConfiguration


class PropertyDefinition(Base):
    __tablename__ = "property_definitions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String, unique=True, nullable=False)
    title = Column(String, unique=True, nullable=False)
    definition = Column(Text, nullable=True)
    mapping = Column(Text, nullable=True)  # JSON string
    is_relevant = Column(
        Boolean, nullable=True
    )  # None=not evaluated, True=relevant, False=irrelevant
    date_created = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC)
    )
    date_modified = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Relationships for new unified schema
    ontology_entities = relationship(
        "OntologyEntity", back_populates="structural_predicate_ref"
    )
    relationships = relationship(
        "Relationship", back_populates="predicate_ref"
    )


# Legacy alias for backwards compatibility
Predicate = PropertyDefinition


# New Normalized Schema Models


class OntologyEntity(Base):
    """Unified ontology entity table for taxonomies, concept schemes, and classes."""

    __tablename__ = "ontology_entities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_type: Mapped[NodeType] = cast(
        Mapped[NodeType], Column(NodeTypeColumn(), nullable=False)
    )
    parent_entity_id = Column(
        String, ForeignKey("ontology_entities.id", ondelete="CASCADE"), nullable=True
    )
    title = Column(String, nullable=False)
    definition = Column(Text, nullable=True)
    structural_predicate_id = Column(
        String, ForeignKey("property_definitions.id"), nullable=True
    )
    title_embedding = Column(BLOB, nullable=True, default=None)
    definition_embedding = Column(BLOB, nullable=True, default=None)
    reference_links = Column(
        Text, nullable=True
    )  # JSON array of reference links
    word_senses = Column(Text, nullable=True)  # JSON array of word senses
    attributes = Column(Text, nullable=True)  # JSON array of attributes
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC)
    )
    version = Column(Integer, default=1)
    last_modified = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Self-referential relationship for hierarchy
    # Note: Using lazy="noload" prevents automatic loading of parent to avoid circular reference issues with JSON serialization
    parent = relationship("OntologyEntity", remote_side=[id], lazy="noload")

    # Relationship to property definitions
    structural_predicate_ref = relationship(
        "PropertyDefinition", back_populates="ontology_entities", lazy="select"
    )

    # Legacy aliases for backwards compatibility with old column names
    parent_node_id = synonym("parent_entity_id")
    property_def = synonym("structural_predicate_ref")

    def __init__(self, **kwargs):
        """Handle legacy parameter names for backwards compatibility."""
        # Map old parameter names to new ones
        if "parent_node_id" in kwargs and "parent_entity_id" not in kwargs:
            kwargs["parent_entity_id"] = kwargs.pop("parent_node_id")
        super().__init__(**kwargs)


# Legacy alias for backwards compatibility
StructureNode = OntologyEntity


class Relationship(Base):
    """Unified relationships table for all ontology entity relationships."""

    __tablename__ = "relationships"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_entity_id = Column(
        String, ForeignKey("ontology_entities.id", ondelete="CASCADE"), nullable=False
    )
    target_entity_id = Column(
        String, ForeignKey("ontology_entities.id", ondelete="CASCADE"), nullable=False
    )
    predicate = Column(String, nullable=False)
    predicate_id = Column(String, ForeignKey("property_definitions.id"), nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC)
    )

    # Relationships
    source_entity = relationship(
        "OntologyEntity", foreign_keys=[source_entity_id], lazy="select"
    )
    target_entity = relationship(
        "OntologyEntity", foreign_keys=[target_entity_id], lazy="select"
    )
    predicate_ref = relationship(
        "PropertyDefinition", back_populates="relationships", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint(
            "source_entity_id", "target_entity_id", "predicate", name="_relationship_uc"
        ),
    )

    # Legacy aliases for backwards compatibility with old column names
    source_node_id = synonym("source_entity_id")
    target_node_id = synonym("target_entity_id")
    property_def = synonym("predicate_ref")

    def __init__(self, **kwargs):
        """Handle legacy parameter names for backwards compatibility."""
        # Map old parameter names to new ones
        if "source_node_id" in kwargs and "source_entity_id" not in kwargs:
            kwargs["source_entity_id"] = kwargs.pop("source_node_id")
        if "target_node_id" in kwargs and "target_entity_id" not in kwargs:
            kwargs["target_entity_id"] = kwargs.pop("target_node_id")
        super().__init__(**kwargs)


# Legacy alias for backwards compatibility
StructureNodeLink = Relationship


class ChangeEvent(Base):
    """Unified events table for all change events across record types."""

    __tablename__ = "change_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)  # create, update, delete
    record_type: Mapped[RecordType] = cast(
        Mapped[RecordType], Column(RecordTypeColumn(), nullable=False)
    )  # structure_node, structure_node_link, predicate
    record_id = Column(String, nullable=True)  # ID of the affected record
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    timestamp = Column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False
    )
    processed = Column(Boolean, default=False, nullable=False)


# Legacy alias for backwards compatibility during transition
NodeEvent = ChangeEvent

# Legacy aliases for backwards compatibility - OntologyEntity replaced Layer, Domain, and Term
Layer = OntologyEntity
Domain = OntologyEntity
Term = OntologyEntity
