"""
Data models for the reference database.

This module defines the SQLAlchemy models for storing reference nodes and links
from external knowledge sources (e.g., Schema.org, WikiData).
"""

from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint, LargeBinary, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from typing import Dict, Any

Base = declarative_base()


class ReferenceNode(Base):
    """
    Represents a reference node from an external knowledge source.

    Reference nodes contain structured knowledge from sources like Schema.org or WikiData,
    with support for semantic embeddings for similarity matching.

    Attributes:
        id: Auto-generated UUID primary key
        title: Human-readable title (required)
        definition: Detailed description or definition (required)
        source: Source identifier (e.g., 'schema.org', 'wikidata') (required)
        external_id: Source-specific identifier (e.g., 'Person', 'Q5') (required)
        attributes: JSON-serializable dictionary of additional metadata
        title_embedding: Vector embedding of the title for semantic search
        definition_embedding: Vector embedding of the definition for semantic search
        created_at: Timestamp of record creation
        updated_at: Timestamp of last update

    Constraints:
        UNIQUE(source, external_id): Prevents duplicate entries from the same source
    """

    __tablename__ = 'reference_nodes'

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False, index=True)
    definition = Column(Text, nullable=False)
    source = Column(String, nullable=False, index=True)
    external_id = Column(String, nullable=False, index=True)
    attributes = Column(Text, nullable=True)  # JSON-serialized Dict[str, Any]
    title_embedding = Column(LargeBinary, nullable=True)  # BLOB for vector data
    definition_embedding = Column(LargeBinary, nullable=True)  # BLOB for vector data
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    # Relationships
    subject_links = relationship(
        'ReferenceLink',
        foreign_keys='ReferenceLink.subject_node',
        back_populates='subject',
        cascade='all, delete-orphan'
    )
    object_links = relationship(
        'ReferenceLink',
        foreign_keys='ReferenceLink.object_node',
        back_populates='object',
        cascade='all, delete-orphan'
    )

    # UNIQUE constraint on (source, external_id)
    __table_args__ = (
        UniqueConstraint('source', 'external_id', name='uq_source_external_id'),
    )

    def __repr__(self) -> str:
        """Return a readable string representation of the reference node."""
        return (
            f"ReferenceNode(id='{self.id}', source='{self.source}', "
            f"external_id='{self.external_id}', title='{self.title[:50]}...')"
        )


class ReferenceLink(Base):
    """
    Represents a semantic relationship between two reference nodes.

    Reference links capture the relationships defined in external knowledge sources,
    such as "Person subClassOf Thing" in Schema.org.

    Attributes:
        id: Auto-generated UUID primary key
        subject_node: UUID of the source reference node (required)
        predicate: Relationship type (e.g., 'subClassOf', 'relatedTo') (required)
        object_node: UUID of the target reference node (required)
        attributes: JSON-serializable dictionary of additional metadata
        created_at: Timestamp of record creation
        updated_at: Timestamp of last update

    Relationships:
        subject: Foreign key relationship to subject ReferenceNode (CASCADE delete)
        object: Foreign key relationship to object ReferenceNode (CASCADE delete)
    """

    __tablename__ = 'reference_links'

    id = Column(String, primary_key=True)
    subject_node = Column(String, ForeignKey('reference_nodes.id', ondelete='CASCADE'), nullable=False, index=True)
    predicate = Column(String, nullable=False, index=True)
    object_node = Column(String, ForeignKey('reference_nodes.id', ondelete='CASCADE'), nullable=False, index=True)
    attributes = Column(Text, nullable=True)  # JSON-serialized Dict[str, Any]
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    # Relationships
    subject = relationship('ReferenceNode', foreign_keys=[subject_node], back_populates='subject_links')
    object = relationship('ReferenceNode', foreign_keys=[object_node], back_populates='object_links')

    def __repr__(self) -> str:
        """Return a readable string representation of the reference link."""
        return (
            f"ReferenceLink(id='{self.id}', "
            f"subject='{self.subject_node}', predicate='{self.predicate}', "
            f"object='{self.object_node}')"
        )
