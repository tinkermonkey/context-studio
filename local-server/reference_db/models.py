"""
SQLAlchemy models for the reference database.

This module defines ReferenceNode and ReferenceLink models for storing
multi-source reference data with embeddings.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import declarative_base, relationship
import uuid
import datetime


Base = declarative_base()


def generate_uuid():
    """Generate a UUID string for use as default column value."""
    return str(uuid.uuid4())


class ReferenceNode(Base):
    """
    Represents a reference node from external knowledge sources.

    Stores nodes from DBpedia, ConceptNet, Wikidata, Schema.org and other
    reference sources with semantic embeddings for similarity search.

    Fields:
        id: UUID primary key
        source: Source system identifier (e.g., 'dbpedia', 'conceptnet')
        external_id: Original identifier from source system
        title: Primary label or title
        definition: Description or definition text
        attributes: JSON metadata specific to the source
        title_embedding: Vector embedding of title for semantic search
        definition_embedding: Vector embedding of definition for semantic search
        created_at: Timestamp when node was created

    Constraints:
        - UNIQUE(source, external_id): Prevents duplicate nodes from same source
    """

    __tablename__ = "reference_nodes"

    id = Column(String, primary_key=True, default=generate_uuid, nullable=False)
    source = Column(String, nullable=False, index=True)
    external_id = Column(String, nullable=False)
    title = Column(String, nullable=False, index=True)
    definition = Column(Text, nullable=True)
    attributes = Column(Text, nullable=True)  # JSON string for source-specific metadata
    title_embedding = Column(BLOB, nullable=True)
    definition_embedding = Column(BLOB, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    __table_args__ = (
        UniqueConstraint('source', 'external_id', name='_source_external_id_uc'),
    )


class ReferenceLink(Base):
    """
    Represents a relationship between reference nodes.

    Stores directed relationships from external knowledge sources,
    enabling graph traversal and relationship queries.

    Fields:
        id: UUID primary key
        subject_node: ID of the source node
        predicate: Relationship type (e.g., 'IsA', 'PartOf')
        object_node: ID of the target node
        attributes: JSON metadata about the relationship
        created_at: Timestamp when link was created
    """

    __tablename__ = "reference_links"

    id = Column(String, primary_key=True, default=generate_uuid, nullable=False)
    subject_node_id = Column(String, ForeignKey("reference_nodes.id", ondelete="CASCADE"), nullable=False)
    predicate = Column(String, nullable=False, index=True)
    object_node_id = Column(String, ForeignKey("reference_nodes.id", ondelete="CASCADE"), nullable=False)
    attributes = Column(Text, nullable=True)  # JSON string for relationship metadata
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    subject_node = relationship("ReferenceNode", foreign_keys=[subject_node_id])
    object_node = relationship("ReferenceNode", foreign_keys=[object_node_id])
