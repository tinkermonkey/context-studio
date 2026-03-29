"""
SQLAlchemy ORM models for Context Studio's primary database (local.db).

This module defines all ORM models for the Ontology Management bounded context:
- OntologyEntity: Single-table inheritance pattern for taxonomies, concept schemes, classes, individuals
- Relationship: Typed, directed edges between entities
- PropertyDefinition: Registry of defined object property types

Models are the source of truth for Alembic migrations via autogenerate.

Design Notes:
- Single-table inheritance (STI) via node_type discriminator column
- All timestamps are UTC
- JSON storage for nested value objects (external_references, lexical_senses, data_properties)
- PropertyDefinition appears in both ontology_entities (for referential integrity) and property_definitions (optimized queries)
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    JSON,
    LargeBinary,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class OntologyEntity(Base):
    """
    Unified table for all ontology entity types using single-table inheritance.

    Node types:
    - 'taxonomy': Top-level container for classification hierarchies
    - 'concept_scheme': Coherent group of concepts within a taxonomy
    - 'class': Concept in the ontology (the main entity type)
    - 'individual': Concrete instance of a class
    - 'property_definition': Defined relationship type (object property)

    Attributes:
        id: UUID as string, primary key
        node_type: Discriminator column determining entity type
        title: Display name (required)
        description: Longer description (optional)
        created_at: Timestamp of creation (UTC, auto-set)
        last_modified: Timestamp of last modification (UTC, auto-set)
        version: Version number for optimistic concurrency control
        taxonomy_id: Parent taxonomy ID (for concept_scheme, class, individual)
        concept_scheme_id: Parent concept scheme ID (for class, individual)
        class_id: Class being instantiated (for individual, rdf:type)
        parent_class_id: Parent class for hierarchy (for class, rdfs:subClassOf)
        structural_property_id: Primary structural relationship property (for class)
        external_references: JSON list of external knowledge base links
        lexical_senses: JSON list of word sense disambiguation entries
        data_properties: JSON list of data property values
        embedding: Binary blob of embedding vector (for class, optional)
        is_indexed: Whether this entity is included in semantic indexes
        identifier: Machine-readable identifier (unique, for property_definition only)
        ontology_mapping: JSON mapping to external ontologies (for property_definition)
        is_relevant: Tri-state relevance flag (for property_definition)
    """

    __tablename__ = "ontology_entities"

    # Core identity and versioning
    id = Column(String(36), primary_key=True, nullable=False)
    node_type = Column(
        String(20),
        nullable=False,
        index=True,
        doc="Discriminator: taxonomy, concept_scheme, class, individual, property_definition"
    )
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of creation"
    )
    last_modified = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of last modification"
    )
    version = Column(Integer, nullable=False, default=1, doc="For optimistic locking")

    # Hierarchy and containment relationships
    taxonomy_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Parent taxonomy (for concept_scheme, class, individual)"
    )
    concept_scheme_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Parent concept scheme (for class, individual)"
    )
    class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=True,
        doc="Class being instantiated (for individual, rdf:type)"
    )
    parent_class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Parent class for hierarchy (for class, rdfs:subClassOf)"
    )
    structural_property_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="SET NULL"),
        nullable=True,
        doc="Primary structural property definition (for class)"
    )

    # Nested value objects (stored as JSON)
    external_references = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {source, identifier, uri, metadata}"
    )
    lexical_senses = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {label, language_code, sense_type}"
    )
    data_properties = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {property_identifier, value, datatype}"
    )

    # Embeddings and indexing
    embedding = Column(
        LargeBinary,
        nullable=True,
        doc="Binary embedding vector (for class, optional)"
    )
    is_indexed = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether included in semantic indexes"
    )

    # Property definition fields (only used when node_type='property_definition')
    identifier = Column(
        String(255),
        nullable=True,
        unique=True,
        doc="Machine-readable identifier (unique, for property_definition)"
    )
    ontology_mapping = Column(
        JSON,
        nullable=True,
        doc="Mapping to external ontologies (for property_definition)"
    )
    is_relevant = Column(
        Integer,
        nullable=True,
        doc="Tri-state relevance: NULL=not evaluated, 0=not relevant, 1=relevant"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('taxonomy', 'concept_scheme', 'class', 'individual', 'property_definition')",
            name="check_valid_node_type"
        ),
        Index("idx_node_type_title", "node_type", "title"),
    )

    def __repr__(self) -> str:
        return f"<OntologyEntity(id={self.id}, type={self.node_type}, title={self.title})>"


class Relationship(Base):
    """
    A typed, directed edge between two ontology entities.

    Represents relationships like:
    - rdfs:subClassOf (class hierarchy)
    - skos:broader / skos:narrower (concept relationships)
    - Custom object properties (defined via PropertyDefinition)

    Attributes:
        id: UUID as string, primary key
        source_id: ID of source entity (must exist in ontology_entities)
        target_id: ID of target entity (must exist in ontology_entities)
        property_definition_id: ID of PropertyDefinition that defines this relationship type
        created_at: Timestamp of creation (UTC, immutable)
    """

    __tablename__ = "relationships"

    id = Column(String(36), primary_key=True, nullable=False)
    source_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Source entity"
    )
    target_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Target entity"
    )
    property_definition_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="PropertyDefinition that types this relationship"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of creation (immutable)"
    )

    __table_args__ = (
        CheckConstraint(
            "source_id != target_id",
            name="check_no_self_loop"
        ),
        UniqueConstraint("source_id", "target_id", "property_definition_id", name="uk_relationship_triple"),
    )

    def __repr__(self) -> str:
        return f"<Relationship(id={self.id}, source={self.source_id}, target={self.target_id})>"


class PropertyDefinition(Base):
    """
    Registry of defined object property types (OWL:ObjectProperty).

    This table exists alongside OntologyEntity entries (with node_type='property_definition')
    to optimize property-specific queries and enforce semantic constraints.

    All PropertyDefinitions must also have a corresponding OntologyEntity row for
    referential integrity in the relationship graph.

    Attributes:
        id: UUID as string, primary key (matches OntologyEntity.id)
        identifier: Machine-readable identifier (unique, immutable)
        title: Display name
        description: Longer description
        ontology_mapping: JSON mapping to external ontology standards
        is_relevant: Tri-state relevance flag (None=not evaluated, 0=not relevant, 1=relevant)
        created_at: Timestamp of creation
        last_modified: Timestamp of last modification
        version: Version number for optimistic concurrency control
    """

    __tablename__ = "property_definitions"

    id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="Must match OntologyEntity.id with node_type='property_definition'"
    )
    identifier = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="Machine-readable identifier, unique constraint"
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    ontology_mapping = Column(
        JSON,
        nullable=True,
        doc="JSON mapping to external ontologies"
    )
    is_relevant = Column(
        Integer,
        nullable=True,
        doc="Tri-state: NULL=not evaluated, 0=not relevant, 1=relevant"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_modified = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    version = Column(Integer, nullable=False, default=1)

    __table_args__ = ()

    def __repr__(self) -> str:
        return f"<PropertyDefinition(id={self.id}, identifier={self.identifier})>"


class ChangeEvent(Base):
    """
    Audit trail of all changes to ontology entities.

    Supports versioning, change tracking, and collaboration features.
    Used by the Version Control & Collaboration bounded context.

    Attributes:
        id: UUID as string, primary key
        entity_id: ID of the entity that changed
        entity_type: Type of the entity (taxonomy, concept_scheme, class, etc.)
        operation: Type of operation (create, update, delete)
        previous_state: JSON snapshot of entity before change (for updates)
        new_state: JSON snapshot of entity after change
        timestamp: UTC timestamp of the change
        user_id: Optional ID of the user who made the change
        change_reason: Optional explanation of why the change was made
        changeset_id: Optional ID of a changeset this event belongs to
    """

    __tablename__ = "change_events"

    id = Column(String(36), primary_key=True, nullable=False)
    entity_id = Column(
        String(36),
        nullable=False,
        index=True,
        doc="Entity that changed"
    )
    entity_type = Column(
        String(20),
        nullable=False,
        doc="Type of entity (taxonomy, concept_scheme, class, etc.)"
    )
    operation = Column(
        String(10),
        nullable=False,
        index=True,
        doc="Operation type: create, update, delete"
    )
    previous_state = Column(
        JSON,
        nullable=True,
        doc="JSON snapshot before change (null for create)"
    )
    new_state = Column(
        JSON,
        nullable=False,
        doc="JSON snapshot after change (null for delete)"
    )
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp of the change"
    )
    user_id = Column(
        String(36),
        nullable=True,
        doc="Optional ID of user who made the change"
    )
    change_reason = Column(
        Text,
        nullable=True,
        doc="Optional explanation of the change"
    )
    changeset_id = Column(
        String(36),
        nullable=True,
        index=True,
        doc="Optional changeset this event belongs to"
    )

    __table_args__ = (
        Index("idx_entity_id_timestamp", "entity_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<ChangeEvent(id={self.id}, entity_id={self.entity_id}, operation={self.operation})>"
