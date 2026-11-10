"""
SQLAlchemy ORM models for Context Studio's primary database (local.db).

This module defines all ORM models for the Ontology Management bounded context:
- OntologyEntity: Single-table inheritance pattern for taxonomies, concept schemes, classes,
individuals
- Relationship: Typed, directed edges between entities
- PropertyDefinition: Registry of defined object property types
- Predicate: A taxonomy's catalog of relation verbs, used by relationship types

Models are the source of truth for Alembic migrations via autogenerate.

Design Notes:
- Single-table inheritance (STI) via node_type discriminator column
- All timestamps are UTC
- JSON storage for nested value objects (external_references, lexical_senses, data_properties)
- PropertyDefinition appears in both ontology_entities (for referential integrity) and
property_definitions (optimized queries)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    select,
    text,
)
from sqlalchemy.orm import column_property, declarative_base

Base = declarative_base()  # type: ignore[valid-type]


class OntologyEntity(Base):  # type: ignore[valid-type,misc]
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
        description: Longer description (optional); a taxonomy's one-paragraph summary
        vision: Full vision statement in markdown (for taxonomy, optional)
        created_at: Timestamp of creation (UTC, auto-set)
        last_modified: Timestamp of last modification (UTC, auto-set)
        version: Version number for optimistic concurrency control
        status: Publication status (draft or published, default draft)
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
        predicate_id: The Predicate the relationship type uses (for property_definition)
        canonical_predicate: Read-only identifier of that predicate (a correlated
            subquery on predicates, defined below the Predicate model)
        ontology_mapping: JSON mapping to external ontologies (for property_definition)
        is_relevant: Tri-state relevance flag (for property_definition)
        min_per_source: Fewest relationships of the type per source (for property_definition)
        max_per_source: Most relationships of the type per source, NULL for no limit
            (for property_definition)
        max_per_target: Most relationships of the type per target, NULL for no limit
            (for property_definition)
        hierarchy: The type's relationships form no cycles (for property_definition)
        symmetric: The type holds both ways (for property_definition)
    """

    __tablename__ = "ontology_entities"

    # Core identity and versioning
    id = Column(String(36), primary_key=True, nullable=False)
    node_type = Column(
        String(20),
        nullable=False,
        index=True,
        doc=("Discriminator: taxonomy, concept_scheme, class, individual," " property_definition"),
    )
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    vision = Column(
        Text,
        nullable=True,
        doc="Full vision statement in markdown (for taxonomy); description holds its summary",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of creation",
    )
    last_modified = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of last modification",
    )
    version = Column(Integer, nullable=False, default=1, doc="For optimistic locking")
    status = Column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
        doc="Publication status: draft or published",
    )

    # Hierarchy and containment relationships
    taxonomy_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Parent taxonomy (for concept_scheme, class, individual)",
    )
    concept_scheme_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Parent concept scheme (for class, individual)",
    )
    class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Class being instantiated (for individual, rdf:type)",
    )
    parent_class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Parent class for hierarchy (for class, rdfs:subClassOf)",
    )
    structural_property_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Primary structural property definition (for class)",
    )
    domain_class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Source/domain Class for this relationship type (for property_definition, rdfs:domain)",
    )
    range_class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Target/range Class for this relationship type (for property_definition, rdfs:range)",
    )
    # predicates.taxonomy_id points back here; use_alter marks the known cycle so
    # metadata DROP can sort the tables (SQLite still renders the FK inline). It
    # also means one flush inserts ontology_entities rows before predicates, so a
    # predicate must be flushed before the relationship type that uses it.
    predicate_id = Column(
        String(36),
        ForeignKey("predicates.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
        index=True,
        doc=(
            "Predicate in its taxonomy's catalog this relationship type uses (for"
            " property_definition). NULL for other node types and types imported"
            " without one. A predicate still in use can't be deleted."
        ),
    )
    derived = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        doc=(
            "Computed by the client from other data (for class and property_definition):"
            " no direct creates of its individuals or relationships, not an extraction"
            " target. False for other node types."
        ),
    )
    # Relationship-type structure (for property_definition); not enforced on
    # stored relationships. Other node types keep the defaults.
    min_per_source = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        doc="Fewest relationships of this type per source (for property_definition; 0: optional)",
    )
    max_per_source = Column(
        Integer,
        nullable=True,
        doc="Most relationships of this type per source (for property_definition; NULL: no limit)",
    )
    max_per_target = Column(
        Integer,
        nullable=True,
        doc="Most relationships of this type per target (for property_definition; NULL: no limit)",
    )
    hierarchy = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        doc="Its relationships form no cycles (for property_definition)",
    )
    symmetric = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        doc="A relationship one way holds the other way too (for property_definition)",
    )

    # Nested value objects (stored as JSON)
    external_references = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {source, identifier, uri, metadata}",
    )
    lexical_senses = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {label, language_code, sense_type}",
    )
    data_properties = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {property_identifier, value, datatype}",
    )

    # Embeddings and indexing
    embedding = Column(
        LargeBinary, nullable=True, doc="Binary embedding vector (for class, optional)"
    )
    title_embedding = Column(
        LargeBinary,
        nullable=True,
        doc="float32 blob: embedding of title alone, for schema vector search",
    )
    definition_embedding = Column(
        LargeBinary,
        nullable=True,
        doc="float32 blob: embedding of description alone, for schema vector search",
    )
    is_indexed = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether included in semantic indexes",
    )

    # Pipeline traceability
    source_run_id = Column(
        String(36),
        nullable=True,
        index=True,
        doc="ID of the pipeline run that created or last modified this entity",
    )

    dataset_id = Column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Dataset the individual belongs to (for individual; NULL for other node types)",
    )

    # Slug identifier — used by property_definition, taxonomy, concept_scheme, class.
    # Unique across all entities in the workspace; populated for the four kinds above
    # and NULL for individuals.
    identifier = Column(
        String(255),
        nullable=True,
        unique=True,
        doc=(
            "Machine-readable slug identifier (unique). Required for property_definition,"
            " taxonomy, concept_scheme, and class entities."
        ),
    )
    color = Column(
        String(7),
        nullable=True,
        doc=(
            "Optional hex color string (#rrggbb) for taxonomy, concept_scheme, and class"
            " entities. Used by the UI for swatches."
        ),
    )
    ontology_mapping = Column(
        JSON,
        nullable=True,
        doc="Mapping to external ontologies (for property_definition)",
    )
    is_relevant = Column(
        Integer,
        nullable=True,
        doc="Tri-state relevance: NULL=not evaluated, 0=not relevant, 1=relevant",
    )
    mirrored = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        doc="The taxonomy mirrors an external source of truth (for taxonomy)",
    )
    source_revision = Column(
        JSON(none_as_null=True),
        nullable=True,
        doc="{repo, commit, spec_version} the taxonomy was last imported at (for taxonomy)",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('taxonomy', 'concept_scheme', 'class', 'individual',"
            " 'property_definition')",
            name="check_valid_node_type",
        ),
        CheckConstraint(
            "node_type != 'individual' OR dataset_id IS NOT NULL",
            name="check_individual_dataset",
        ),
        Index("idx_node_type_title", "node_type", "title"),
    )

    def __repr__(self) -> str:
        return f"<OntologyEntity(id={self.id}, type={self.node_type}, title={self.title})>"


class Predicate(Base):  # type: ignore[valid-type,misc]
    """
    A relation verb in a taxonomy's predicate catalog (e.g. "part_of", "navigates-to").

    Every relationship type (property_definition) of the taxonomy points at one
    through ontology_entities.predicate_id. Each taxonomy holds its own catalog, so
    the identifier is unique per taxonomy, not workspace-wide. Deleting the taxonomy
    deletes its catalog; a predicate a relationship type still uses can't be deleted.

    Attributes:
        id: UUID as string, primary key
        taxonomy_id: The taxonomy whose catalog holds it (FK with CASCADE)
        identifier: The verb, unique within the taxonomy
        title: Display name
        description: What the relation means (optional)
        external_references: JSON list of client metadata, e.g. DR's inverse,
            category, archimate_alignment and semantics
        status: Publication status (draft or published, default draft)
        version: Version number for optimistic concurrency control
        created_at: Timestamp of creation (UTC, auto-set)
        last_modified: Timestamp of last modification (UTC, auto-set)
    """

    __tablename__ = "predicates"

    id = Column(String(36), primary_key=True, nullable=False)
    taxonomy_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Taxonomy whose catalog holds the predicate (required, with cascade delete)",
    )
    identifier = Column(
        String(255),
        nullable=False,
        doc="The relation verb, unique within its taxonomy",
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    external_references = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {source, identifier, uri, metadata}",
    )
    status = Column(
        String(20),
        nullable=False,
        default="draft",
        doc="Publication status: draft or published",
    )
    version = Column(Integer, nullable=False, default=1, doc="For optimistic locking")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of creation",
    )
    last_modified = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of last modification",
    )

    __table_args__ = (
        UniqueConstraint("taxonomy_id", "identifier", name="uk_predicate_taxonomy_identifier"),
    )

    def __repr__(self) -> str:
        return (
            f"<Predicate(id={self.id}, taxonomy_id={self.taxonomy_id},"
            f" identifier={self.identifier})>"
        )


# Read-only: a relationship type's predicate identifier, read through predicate_id.
# Not a table column, so autogenerate ignores it; writes go through predicate_id.
OntologyEntity.canonical_predicate = column_property(
    select(Predicate.identifier)
    .where(Predicate.id == OntologyEntity.predicate_id)
    .correlate_except(Predicate)
    .scalar_subquery(),
    doc=(
        "Identifier of the predicate this relationship type uses, e.g. 'navigates-to'"
        " (the form predicate grounding clamps to); NULL without one."
    ),
)


class IndividualClass(Base):  # type: ignore[valid-type,misc]
    """
    Join table for ordered parent class membership of Individual entities.

    Represents the many-to-many relationship between an Individual and its parent Classes
    with an explicit position column to preserve order for property attribute inheritance
    (first-class-wins conflict resolution).

    Attributes:
        individual_id: ID of the Individual entity
        class_id: ID of the parent Class entity
        position: Zero-based position in the ordered list (determines inheritance precedence)
    """

    __tablename__ = "individual_classes"

    individual_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID of the Individual",
    )
    class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID of the parent Class",
    )
    position = Column(
        Integer,
        nullable=False,
        doc=("Zero-based position in the ordered list (determines inheritance" " precedence)"),
    )

    __table_args__ = (
        PrimaryKeyConstraint("individual_id", "class_id", name="pk_individual_classes"),
        UniqueConstraint("individual_id", "position", name="uk_individual_position"),
    )

    def __repr__(self) -> str:
        return (
            f"<IndividualClass(individual_id={self.individual_id},"
            f" class_id={self.class_id}, position={self.position})>"
        )


class Relationship(Base):  # type: ignore[valid-type,misc]
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
        doc="Source entity",
    )
    target_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Target entity",
    )
    property_definition_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="PropertyDefinition that types this relationship",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of creation (immutable)",
    )
    source_run_id = Column(
        String(36),
        nullable=True,
        index=True,
        doc="ID of the pipeline run that created this relationship",
    )
    attributes = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
        doc="Values carried on the edge (quantity, unit, ...), keyed by name",
    )

    __table_args__ = (
        CheckConstraint("source_id != target_id", name="check_no_self_loop"),
        UniqueConstraint(
            "source_id",
            "target_id",
            "property_definition_id",
            name="uk_relationship_triple",
        ),
    )

    def __repr__(self) -> str:
        return f"<Relationship(id={self.id}, source={self.source_id}," f" target={self.target_id})>"


class PropertyDefinition(Base):  # type: ignore[valid-type,misc]
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
        doc="Must match OntologyEntity.id with node_type='property_definition'",
    )
    identifier = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="Machine-readable identifier, unique constraint",
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    ontology_mapping = Column(JSON, nullable=True, doc="JSON mapping to external ontologies")
    domain_class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Source/domain Class for this relationship type (rdfs:domain)",
    )
    range_class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Target/range Class for this relationship type (rdfs:range)",
    )
    is_relevant = Column(
        Integer,
        nullable=True,
        doc="Tri-state: NULL=not evaluated, 0=not relevant, 1=relevant",
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


class AttributeDefinition(Base):  # type: ignore[valid-type,misc]
    """
    Defines the type-level (TBox) declaration of an attribute (OWL DatatypeProperty) on a
    Class, or on a relationship type (an edge attribute, such as a kit's quantity).

    Represents schema metadata: "Class X (or relationship type R) has an attribute named Y of
    type Z with these constraints", scoped to exactly one owner, a class or a relationship type
    (the ck_attribute_one_owner check). Unlike instances with data property values
    (DataPropertyValue) or relationship attributes, AttributeDefinitions are schema-level
    declarations that define the structure and constraints of those values.

    Stored in a dedicated table (not STI) because AttributeDefinition is schema metadata,
    not a graph node.

    Attributes:
        id: UUID as string, primary key
        class_id: ID of the class this attribute is scoped to (FK with CASCADE; NULL for an
            edge attribute)
        property_definition_id: ID of the relationship type an edge attribute is on (FK with
            CASCADE; NULL for a class attribute)
        identifier: Machine-readable identifier for the attribute, unique within its owner
        title: Display name for the attribute
        datatype: The data type (string, integer, number, date, boolean, array or object)
        description: Optional longer description
        is_required: Whether this attribute must be present on instances
        allowed_values: Enum constraint; a list of allowed string values, or None
        default_value: Optional default value (as string)
        sort_order: Display order within the owner's attribute list
        external_references: JSON list of external knowledge base links (e.g., DR provenance)
        created_at: Timestamp of creation (UTC, auto-set)
        last_modified: Timestamp of last modification (UTC, auto-set)
        version: Version number for optimistic concurrency control
        status: Publication status (draft or published, default draft)
        source_run_id: ID of the pipeline run that created or last modified this entity
    """

    __tablename__ = "attribute_definitions"

    id = Column(String(36), primary_key=True, nullable=False)
    class_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Class this attribute is scoped to (NULL for an edge attribute; cascade delete)",
    )
    property_definition_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Relationship type an edge attribute is on (NULL for a class attribute; cascade)",
    )
    identifier = Column(
        String(255),
        nullable=False,
        doc="Machine-readable identifier for the attribute, unique within its owner",
    )
    title = Column(String(255), nullable=False, index=True)
    datatype = Column(
        String(50),
        nullable=False,
        doc="Data type: string, integer, number, date, boolean, array or object",
    )
    description = Column(Text, nullable=True)
    is_required = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether this attribute must be present on instances",
    )
    allowed_values = Column(
        JSON,
        nullable=True,
        doc="Enum constraint: list of allowed string values, or None if unconstrained",
    )
    default_value = Column(String(255), nullable=True, doc="Optional default value")
    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Display order within the owner's attribute list",
    )
    external_references = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {source, identifier, uri, metadata}",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of creation",
    )
    last_modified = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        doc="UTC timestamp of last modification",
    )
    version = Column(Integer, nullable=False, default=1, doc="For optimistic locking")
    status = Column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
        doc="Publication status: draft or published",
    )
    source_run_id = Column(
        String(36),
        nullable=True,
        index=True,
        doc="ID of the pipeline run that created or last modified this entity",
    )

    __table_args__ = (
        CheckConstraint(
            "(class_id IS NULL) <> (property_definition_id IS NULL)",
            name="ck_attribute_one_owner",
        ),
        UniqueConstraint("class_id", "identifier", name="uk_attribute_class_identifier"),
        UniqueConstraint(
            "property_definition_id", "identifier", name="uk_attribute_property_identifier"
        ),
        Index("idx_class_id_sort_order", "class_id", "sort_order"),
    )

    def __repr__(self) -> str:
        return (
            f"<AttributeDefinition(id={self.id}, class_id={self.class_id},"
            f" property_definition_id={self.property_definition_id},"
            f" identifier={self.identifier})>"
        )


class ChangeEvent(Base):  # type: ignore[valid-type,misc]
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
        batch_run_id: Optional ID of the batch run that produced this change (import or extraction)
    """

    __tablename__ = "change_events"

    id = Column(String(36), primary_key=True, nullable=False)
    entity_id = Column(String(36), nullable=False, index=True, doc="Entity that changed")
    entity_type = Column(
        String(20),
        nullable=False,
        doc="Type of entity (taxonomy, concept_scheme, class, etc.)",
    )
    operation = Column(
        String(10),
        nullable=False,
        index=True,
        doc="Operation type: create, update, delete",
    )
    previous_state = Column(
        JSON, nullable=True, doc="JSON snapshot before change (null for create)"
    )
    new_state = Column(JSON, nullable=False, doc="JSON snapshot after change (null for delete)")
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp of the change",
    )
    user_id = Column(String(36), nullable=True, doc="Optional ID of user who made the change")
    change_reason = Column(Text, nullable=True, doc="Optional explanation of the change")
    batch_run_id = Column(
        String(36),
        ForeignKey("batch_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Optional batch run (import or extraction) that produced this change",
    )
    processed = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether this change has been synchronized to remote",
    )

    __table_args__ = (
        Index("idx_entity_id_timestamp", "entity_id", "timestamp"),
        Index("idx_processed", "processed"),
        Index("idx_batch_run_id", "batch_run_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ChangeEvent(id={self.id}, entity_id={self.entity_id},"
            f" operation={self.operation})>"
        )


class ExtractionResult(Base):  # type: ignore[valid-type,misc]
    """
    Persistence model for an extraction operation result.

    Stores the complete output of an extraction pipeline execution including
    extracted entities, layer execution metadata, and performance metrics.

    Attributes:
        id: UUID as string, primary key
        text: The source text that was extracted
        extracted_entities: JSON list of ExtractedEntity objects
        layers_executed: JSON list of ExtractionLayerResult metadata
        total_duration_ms: Total time spent on extraction (milliseconds)
        created_at: Timestamp when extraction completed (UTC)
    """

    __tablename__ = "extraction_results"

    id = Column(String(36), primary_key=True, nullable=False)
    text = Column(Text, nullable=False)
    extracted_entities = Column(
        JSON,
        nullable=False,
        default=list,
        doc=(
            "JSON list of {id, label, entity_type, source_layer, confidence, uri,"
            " description, properties}"
        ),
    )
    layers_executed = Column(
        JSON,
        nullable=False,
        default=list,
        doc=(
            "JSON list of {layer_number, layer_name, entities_found, duration_ms,"
            " success, error_message}"
        ),
    )
    total_duration_ms = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total time spent on extraction (milliseconds)",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp of extraction completion",
    )

    __table_args__ = (Index("idx_created_at", "created_at"),)

    def __repr__(self) -> str:
        return (
            f"<ExtractionResult(id={self.id}, text_len={len(self.text or '')},"
            f" entities={len(self.extracted_entities or [])})>"
        )


class Batch(Base):  # type: ignore[valid-type,misc]
    """
    Aggregate root for a batch of pipeline runs.

    A batch is a container for one or more pipeline runs, providing lifecycle
    management and aggregated status. Each batch has its own UUID identity,
    independent of any single run.

    Attributes:
        id: UUID as string, primary key
        status: Current status (pending, running, completed, failed, cancelled)
        created_at: UTC timestamp of batch creation
        started_at: UTC timestamp when batch transitioned to RUNNING (nullable)
        completed_at: UTC timestamp when batch transitioned to terminal state (nullable)
        last_updated: UTC timestamp of last status change or run update
    """

    __tablename__ = "batches"

    id = Column(String(36), primary_key=True, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        doc="Current status (pending, running, completed, failed, cancelled)",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp of batch creation",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="UTC timestamp when batch transitioned to RUNNING",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="UTC timestamp when batch transitioned to terminal state",
    )
    last_updated = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp of last status change or run update",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="check_valid_batch_status",
        ),
        Index("idx_batch_id_status", "id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Batch(id={self.id}, status={self.status})>"


class BatchRun(Base):  # type: ignore[valid-type,misc]
    """
    Abstract base class for all batch run types using joined-table inheritance.

    Batch runs (imports, extractions, etc.) share common fields and are
    distinguished by the run_type discriminator column. Subclasses use
    joined-table inheritance, with their own tables containing type-specific fields.

    This class is abstract and should not be instantiated directly.
    Use ImportRun or ExtractionRun instead.

    Attributes:
        id: UUID as string, primary key
        batch_id: FK to batches.id for batch aggregation (the containing batch)
        created_at: UTC timestamp of run initiation
        created_by: Optional ID of the user who initiated the run
        status: Current status (pending, committed, failed, etc. depending on type)
        affected_entity_ids: JSON list of entity IDs affected by this run
        run_type: Discriminator column (import, extraction, etc.)
    """

    __tablename__ = "batch_runs"

    id = Column(String(36), primary_key=True, nullable=False)
    batch_id = Column(
        String(36),
        ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="FK to batches.id for batch aggregation",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp of run initiation",
    )
    created_by = Column(String(36), nullable=True, doc="Optional ID of user who initiated the run")
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        doc="Current status (semantics depend on run_type)",
    )
    affected_entity_ids = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of entity IDs affected by this run",
    )
    run_type = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Discriminator: import, extraction, etc.",
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_on": run_type,
    }
    # No CHECK on run_type: the subclasses' polymorphic identities are the only
    # values ever written, and new run types (e.g. 'proposal') need no table rebuild.
    __table_args__ = (Index("idx_run_type_status", "run_type", "status"),)

    def __repr__(self) -> str:
        return f"<BatchRun(id={self.id}, type={self.run_type}, status={self.status})>"


class ImportRun(BatchRun):
    """
    Record of an import operation.

    Tracks import runs from initiation through completion, correlating
    a batch of change_events with the operation that produced them.
    Uses joined-table inheritance from BatchRun.

    Attributes:
        id: UUID as string, primary key (FK to batch_runs.id)
        format: Format of imported file (skos, owl, graphml, etc.)
        source_uri: Optional URI or filename of the import source
        source_hash: SHA256 hash of the imported bytes
        scope_type: Type of scope (whole_graph, taxonomy, scheme, entity_set)
        scope_taxonomy_id: For taxonomy scope, the taxonomy ID
        scope_scheme_id: For scheme scope, the scheme ID
        scope_include_descendants: For scheme scope, whether to include descendants
        scope_entity_ids: For entity_set scope, JSON list of entity IDs
        resolutions: JSON list of applied resolutions (match_kind, entity_id, resolution)
    """

    __tablename__ = "import_runs"

    id = Column(
        String(36),
        ForeignKey("batch_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    format = Column(
        String(20),
        nullable=False,
        doc="Format of imported file (skos, owl, graphml, etc.)",
    )
    source_uri = Column(Text, nullable=True, doc="Optional URI or filename of the import source")
    source_hash = Column(String(64), nullable=False, doc="SHA256 hash of the imported bytes")
    scope_type = Column(
        String(20),
        nullable=False,
        doc="Type of scope (whole_graph, taxonomy, scheme, entity_set)",
    )
    scope_taxonomy_id = Column(String(36), nullable=True, doc="For taxonomy scope, the taxonomy ID")
    scope_scheme_id = Column(String(36), nullable=True, doc="For scheme scope, the scheme ID")
    scope_include_descendants = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="For scheme scope, whether to include descendants",
    )
    scope_entity_ids = Column(
        JSON,
        nullable=True,
        default=list,
        doc="For entity_set scope, JSON list of entity IDs",
    )
    resolutions = Column(JSON, nullable=False, default=list, doc="JSON list of applied resolutions")

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "import",
    }

    def __repr__(self) -> str:
        return f"<ImportRun(id={self.id}, format={self.format}, status={self.status})>"


class ExtractionRun(BatchRun):
    """
    Record of an extraction operation.

    Tracks extraction runs from initiation through completion, recording
    pipeline configuration, LLM settings, resource metrics, and outcome counts.
    Uses joined-table inheritance from BatchRun.

    Attributes:
        id: UUID as string, primary key (FK to batch_runs.id)
        source_document_uri: Optional URI or filename of the source document
        source_text_hash: SHA256 hash of the extracted-from text (audit only)
        pipeline_config_ref: Pipeline configuration slug (e.g., "extraction-default")
        model: LLM model name (e.g., "claude-opus-4-7")
        temperature: Sampling temperature (0.0–2.0)
        tokens_used: Total tokens consumed by the LLM call
        duration_ms: Total wall-clock execution time (milliseconds)
        triples_extracted: Count of triples returned by the LLM API
        triples_committed: Count of triples persisted after review
    """

    __tablename__ = "extraction_runs"

    id = Column(
        String(36),
        ForeignKey("batch_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    source_document_uri = Column(
        Text, nullable=True, doc="Optional URI or filename of the source document"
    )
    source_text_hash = Column(
        String(64), nullable=False, doc="SHA256 hash of source text (audit only)"
    )
    pipeline_config_ref = Column(
        String(100),
        nullable=False,
        doc="Pipeline configuration slug (e.g., 'extraction-default')",
    )
    model = Column(String(100), nullable=False, doc="LLM model name")
    temperature = Column(Float, nullable=False, doc="Sampling temperature (0.0–2.0)")
    tokens_used = Column(Integer, nullable=False, doc="Total tokens consumed")
    duration_ms = Column(Integer, nullable=False, doc="Total execution time (ms)")
    triples_extracted = Column(Integer, nullable=False, doc="Count of triples returned by API")
    triples_committed = Column(
        Integer, nullable=False, doc="Count of triples persisted after review"
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "extraction",
    }
    __table_args__: Tuple[Any, ...] = (
        CheckConstraint("temperature >= 0.0", name="check_temperature_min"),
        CheckConstraint("temperature <= 2.0", name="check_temperature_max"),
        CheckConstraint("tokens_used >= 0", name="check_tokens_non_negative"),
        CheckConstraint("duration_ms >= 0", name="check_duration_non_negative"),
        CheckConstraint("triples_extracted >= 0", name="check_triples_extracted_non_negative"),
        CheckConstraint("triples_committed >= 0", name="check_triples_committed_non_negative"),
        CheckConstraint(
            "triples_committed <= triples_extracted",
            name="check_triples_committed_le_extracted",
        ),
    )

    def __repr__(self) -> str:
        return f"<ExtractionRun(id={self.id}, model={self.model}, status={self.status})>"


class PipelineRun(BatchRun):
    """
    Base class for pipeline execution records.

    Intermediate joined-table between BatchRun and per-type pipeline subclasses.
    Carries pipeline-shared fields that all pipeline types use.
    Uses joined-table inheritance from BatchRun (polymorphic_abstract=True).
    Concrete subclasses define their own polymorphic_identity values
    (e.g., individual_extraction, schema_extraction).

    Attributes:
        id: UUID as string, primary key (FK to batch_runs.id)
        pipeline_type: Type of pipeline (individual_extraction | schema_extraction | ...)
        implementation_id: Reference to registered implementation
        configuration_ref: Versioned configuration reference (immutable once set)
        input_summary: JSON dict with input metadata (small)
        output_summary: JSON dict with output counts and metrics
        llm_metadata: JSON dict with model, tokens_used, duration_ms
        source_text: Input text the run extracted from (text-input pipeline types only)
        input_data: The run's full input, kept so a background worker can execute it
        items_done: Work items finished so far (progress)
        items_total: Work items the run will process (progress)
        proposal_id: The change proposal the run produced (no FK: a proposal is a
            batch run of its own, and the run's record outlives it)
    """

    __tablename__ = "pipeline_runs"

    id = Column(
        String(36),
        ForeignKey("batch_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    pipeline_type = Column(
        String(50),
        nullable=False,
        doc="Pipeline type discriminator (individual_extraction | schema_extraction | ...)",
    )
    implementation_id = Column(
        String(100),
        nullable=False,
        doc="Reference to registered implementation",
    )
    configuration_ref = Column(
        String(255),
        nullable=False,
        doc="Versioned configuration reference (immutable once set)",
    )
    configuration_slug = Column(
        String(255),
        nullable=False,
        doc="Configuration slug part (immutable once set)",
    )
    configuration_version = Column(
        Integer,
        nullable=False,
        default=1,
        doc="Configuration version part (immutable once set)",
    )
    input_summary = Column(
        JSON,
        nullable=False,
        default=dict,
        doc="Input metadata (small JSON dict)",
    )
    output_summary = Column(
        JSON,
        nullable=False,
        default=dict,
        doc="Output counts and metrics (JSON dict)",
    )
    llm_metadata = Column(
        JSON,
        nullable=False,
        default=dict,
        doc="LLM metadata: model, tokens_used, duration_ms (JSON dict)",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when run transitioned to RUNNING status",
    )
    failure_reason = Column(
        Text,
        nullable=True,
        doc="String description of failure reason if status=FAILED",
    )
    source_text = Column(
        Text,
        nullable=True,
        doc="Input text the run extracted from; provenance span offsets index into it",
    )
    input_data = Column(
        JSON(none_as_null=True),
        nullable=True,
        doc="Full run input, kept so a background worker can execute the run",
    )
    items_done = Column(Integer, nullable=True, doc="Work items finished so far")
    items_total = Column(Integer, nullable=True, doc="Work items the run will process")
    proposal_id = Column(String(36), nullable=True, doc="The change proposal the run produced")

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_abstract": True,
    }
    __table_args__: Tuple[Any, ...] = (Index("idx_pipeline_impl_id", "implementation_id"),)

    def __repr__(self) -> str:
        return f"<PipelineRun(id={self.id}, type={self.pipeline_type}, status={self.status})>"


class NoOpPipelineRun(PipelineRun):
    """
    No-op pipeline for testing the framework end-to-end.

    Exercises the full pipeline infrastructure without domain logic:
    - Pipeline type and implementation registration
    - LangGraph state machine construction
    - PipelineRun persistence
    - change_events linkage

    Uses joined-table inheritance from PipelineRun with discriminator
    run_type='no_op'.

    Attributes:
        id: UUID as string, primary key (FK to pipeline_runs.id)
    """

    __tablename__ = "no_op_runs"

    id = Column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "no_op",
    }

    def __repr__(self) -> str:
        return f"<NoOpPipelineRun(id={self.id}, status={self.status})>"


class IndividualExtractionRun(PipelineRun):
    """
    Extraction of RDF triples from individual text documents.

    Migrated from Wave A's ExtractionRun; maintains backward compatibility
    with extraction configurations and results.

    Uses joined-table inheritance from PipelineRun with discriminator
    run_type='individual_extraction'.

    Attributes:
        id: UUID as string, primary key (FK to pipeline_runs.id)
        source_text_hash: SHA256 hash of extracted-from text (audit)
        source_document_uri: Optional URI or filename of the source document
    """

    __tablename__ = "individual_extraction_runs"

    id = Column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    source_text_hash = Column(
        String(64),
        nullable=False,
        doc="SHA256 hash of source text (audit only)",
    )
    source_document_uri = Column(
        Text,
        nullable=True,
        doc="Optional URI or filename of the source document",
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "individual_extraction",
    }

    def __repr__(self) -> str:
        return (
            f"<IndividualExtractionRun(id={self.id},"
            f" hash={self.source_text_hash[:8]}, status={self.status})>"  # type: ignore[index]
        )


class SchemaExtractionRun(PipelineRun):
    """
    Schema-level extraction operations.

    Uses joined-table inheritance from PipelineRun with discriminator
    pipeline_type='schema_extraction'.

    Per-type fields: (none at this stage; added in concrete implementation)
    """

    __tablename__ = "schema_extraction_runs"

    id = Column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "schema_extraction",
    }

    def __repr__(self) -> str:
        return f"<SchemaExtractionRun(id={self.id}, status={self.status})>"


class SchemaGroundingRun(PipelineRun):
    """
    Schema node grounding operations.

    Uses joined-table inheritance from PipelineRun with discriminator
    run_type='schema_node_grounding'.

    Per-type fields: (none at this stage; added in concrete implementation)
    """

    __tablename__ = "schema_node_grounding_runs"

    id = Column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "schema_node_grounding",
    }

    def __repr__(self) -> str:
        return f"<SchemaGroundingRun(id={self.id}, status={self.status})>"


class SchemaDefinitionRefinementRun(PipelineRun):
    """
    Schema node definition refinement operations.

    Uses joined-table inheritance from PipelineRun with discriminator
    run_type='schema_node_definition_refinement'.

    Per-type fields: (none at this stage; added in concrete implementation)
    """

    __tablename__ = "schema_node_definition_refinement_runs"

    id = Column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "schema_node_definition_refinement",
    }

    def __repr__(self) -> str:
        return f"<SchemaDefinitionRefinementRun(id={self.id}, status={self.status})>"


class SchemaConnectionRefinementRun(PipelineRun):
    """
    Schema node connection refinement operations.

    Uses joined-table inheritance from PipelineRun with discriminator
    run_type='schema_node_connection_refinement'.

    Per-type fields: (none at this stage; added in concrete implementation)
    """

    __tablename__ = "schema_node_connection_refinement_runs"

    id = Column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "schema_node_connection_refinement",
    }

    def __repr__(self) -> str:
        return f"<SchemaConnectionRefinementRun(id={self.id}, status={self.status})>"


class SchemaRelationshipReflectionRun(PipelineRun):
    """
    Schema relationship reflection runs (sorting questions per relationship
    type, emitted as a change proposal).

    Uses joined-table inheritance from PipelineRun with discriminator
    run_type='schema_relationship_reflection'.

    Per-type fields: (none)
    """

    __tablename__ = "schema_relationship_reflection_runs"

    id = Column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "schema_relationship_reflection",
    }

    def __repr__(self) -> str:
        return f"<SchemaRelationshipReflectionRun(id={self.id}, status={self.status})>"


class ClaimTriageRun(PipelineRun):
    """
    Claim triage runs (decision-model questions per claim, saved on the claims).

    Uses joined-table inheritance from PipelineRun with discriminator
    run_type='claim_triage'.

    Per-type fields: (none)
    """

    __tablename__ = "claim_triage_runs"

    id = Column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "claim_triage",
    }

    def __repr__(self) -> str:
        return f"<ClaimTriageRun(id={self.id}, status={self.status})>"


class ChangeProposalRun(BatchRun):
    """
    A change proposal: ontology changes proposed by an agent, pipeline, bundle
    import or person, decided per operation.

    The proposal's id is its batch run id, so change events of applied
    operations are tagged with it and reverting the run undoes them. Status
    (open, done, reverted) lives in batch_runs.status.

    Attributes:
        id: UUID as string, primary key (FK to batch_runs.id)
        taxonomy_id: The taxonomy the changes are about (no FK: the history
            outlives a deleted taxonomy)
        title: Short summary
        rationale: Why these changes, as a whole
        source: chat, mcp, pipeline, bundle or user
        source_detail: More about the source (MCP client, conversation, file)
        source_revision: {repo, commit, spec_version} of the source the proposal
            was drafted against
        landed: {repo, commit, spec_version, landed_at} once the client landed
            the decided proposal in its source; NULL while unlanded
        client_metadata: JSON object the proposing client keeps on the proposal
            (e.g. a DR plan's predicate_retirements); {} when none
    """

    __tablename__ = "change_proposals"

    id = Column(
        String(36),
        ForeignKey("batch_runs.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    taxonomy_id = Column(String(36), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    rationale = Column(Text, nullable=True)
    source = Column(String(20), nullable=False, index=True)
    source_detail = Column(String(255), nullable=True)
    source_revision = Column(JSON(none_as_null=True), nullable=True)
    landed = Column(JSON(none_as_null=True), nullable=True)
    client_metadata = Column(JSON, nullable=False, default=dict, server_default="{}")
    dataset_id = Column(
        String(36),
        nullable=True,
        doc="The dataset its individual and relationship operations are in (None: no data ops)",
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "proposal",
    }

    def __repr__(self) -> str:
        return f"<ChangeProposalRun(id={self.id}, source={self.source}, status={self.status})>"


class ProposalOperation(Base):  # type: ignore[valid-type,misc]
    """
    One proposed create, update, move or delete of one ontology entity, with its outcome.

    Attributes:
        id: UUID as string, primary key
        proposal_id: FK to change_proposals.id
        seq: Position in the proposal; operations apply in this order
        op: create, update, move or delete
        kind: taxonomy, scheme, class, property, attribute, individual or relationship
        target_id: The existing entity (update, move, delete)
        ref: Name a create gives its new entity for "$ref" use later in the proposal
        fields: JSON of the fields set (all for a create, changed ones otherwise)
        base: JSON of the touched fields' values when proposed (whole entity for a delete)
        rationale: Why this change
        notes: Free-text notes the proposer keeps with the change; never applied
        evidence: JSON list of {quote, url, entity_id}
        probability: Proposer's confidence, 0 to 1
        scope: editorial, additive or breaking
        status: pending, applied, rejected or failed
        result_entity_id: Entity created or changed, once applied
        reason: Why it failed or was rejected
        applied_fields: JSON of the fields actually applied when a reviewer edited the
            operation (always as an update); null when applied as proposed or not applied
        resolution: JSON {strategy, replacement_property_id, replacement_identifier,
            edges} when a relationship-type delete was applied with the relationships
            using it moved or deleted; null otherwise
        proposed_replacement_id: A relationship-type or class delete only: the type the
            proposer names as its replacement, an id or "$<ref>" of a create of the same
            kind in the same proposal; null otherwise
        type_change: JSON {action, before, after, swap, replacement} when an applied
            relationship-type create, update or delete changed the type (see the
            domain's TypeChange); null otherwise
    """

    __tablename__ = "proposal_operations"

    id = Column(String(36), primary_key=True, nullable=False)
    proposal_id = Column(
        String(36),
        ForeignKey("change_proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq = Column(Integer, nullable=False)
    op = Column(String(10), nullable=False)
    kind = Column(String(20), nullable=False)
    target_id = Column(String(36), nullable=True, index=True)
    ref = Column(String(100), nullable=True)
    fields = Column(JSON, nullable=False, default=dict)
    base = Column(JSON, nullable=False, default=dict)
    rationale = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=False, default=list)
    probability = Column(Float, nullable=True)
    scope = Column(String(10), nullable=False)
    status = Column(String(10), nullable=False, default="pending", index=True)
    result_entity_id = Column(String(36), nullable=True)
    reason = Column(Text, nullable=True)
    applied_fields = Column(JSON, nullable=True)
    resolution = Column(JSON, nullable=True)
    proposed_replacement_id = Column(String(101), nullable=True)
    type_change = Column(JSON, nullable=True)

    __table_args__ = (UniqueConstraint("proposal_id", "seq", name="uq_proposal_operation_seq"),)

    def __repr__(self) -> str:
        return f"<ProposalOperation(proposal={self.proposal_id}, seq={self.seq}, op={self.op})>"


class ProposalDecisionRecord(Base):  # type: ignore[valid-type,misc]
    """
    Gold: one reviewer or policy decision on a proposal operation.

    Attributes:
        id: UUID as string, primary key
        operation_id: FK to proposal_operations.id
        proposal_id: FK to change_proposals.id
        taxonomy_id: The proposal's taxonomy
        seq, kind, op: The operation's seq, entity kind and type (copied for filtering)
        decision: applied, rejected or applied_with_edits
        decided_at: When (UTC)
        decided_by: user, policy, an agent source, or unknown (backfilled)
        proposed: JSON of the operation as proposed
        applied_fields: JSON of the fields finally applied; null when rejected
        result_entity_id: Entity created or changed, when applied
        reason: Why (a reject note)
        resolution: JSON of an applied relationship-type delete's in-use resolution
        chosen_alternative: JSON of the alternative the reviewer chose, if any
        probability: The operation's probability, if any
        model: The decision model that produced the probability, if any
        superseded_at, superseded_by: Set when a revert undid the decision
    """

    __tablename__ = "proposal_decisions"

    id = Column(String(36), primary_key=True, nullable=False)
    operation_id = Column(
        String(36),
        ForeignKey("proposal_operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposal_id = Column(
        String(36),
        ForeignKey("change_proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    taxonomy_id = Column(String(36), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    kind = Column(String(20), nullable=False)
    op = Column(String(10), nullable=False)
    decision = Column(String(20), nullable=False, index=True)
    decided_at = Column(DateTime(timezone=True), nullable=False, index=True)
    decided_by = Column(String(50), nullable=False, index=True)
    proposed = Column(JSON, nullable=False, default=dict)
    applied_fields = Column(JSON, nullable=True)
    result_entity_id = Column(String(36), nullable=True)
    reason = Column(Text, nullable=True)
    resolution = Column(JSON, nullable=True)
    chosen_alternative = Column(JSON, nullable=True)
    probability = Column(Float, nullable=True)
    model = Column(String(100), nullable=True)
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    superseded_by = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<ProposalDecisionRecord(operation={self.operation_id}, decision={self.decision})>"


class ClaimRecord(Base):  # type: ignore[valid-type,misc]
    """
    One atomic claim about a taxonomy, split from a reviewer's or maintainer's note.

    Attributes:
        id: UUID as string, primary key
        taxonomy_id: The taxonomy it is about (deleted with it)
        key: Unique within the taxonomy: "<note_ref>#<n>"
        note_ref, note_source, note_text: The note it came from
        subject_id: The entity the note was about, if any
        text: The claim
        category_hint: The splitter's category guess
        affected_ids: JSON list of the entity ids it names
        unresolved_refs: JSON list of names that matched no entity
        proposed_change: The change the note suggests, if any
        source_run_id: The run that split it, if any
        triage: JSON of the decision model's answers (ClaimTriage), or null
        verdict: JSON of a person's verdict (ClaimVerdict), or null
        created_at, updated_at: Timestamps (UTC)
    """

    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, nullable=False)
    taxonomy_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key = Column(String(255), nullable=False)
    note_ref = Column(String(255), nullable=False, index=True)
    note_source = Column(String(20), nullable=False)
    note_text = Column(Text, nullable=True)
    subject_id = Column(String(36), nullable=True, index=True)
    text = Column(Text, nullable=False)
    category_hint = Column(String(100), nullable=True)
    affected_ids = Column(JSON, nullable=False, default=list)
    unresolved_refs = Column(JSON, nullable=False, default=list)
    proposed_change = Column(Text, nullable=True)
    source_run_id = Column(String(36), nullable=True)
    # none_as_null: an untriaged claim stores SQL NULL, not JSON 'null', so it filters
    triage = Column(JSON(none_as_null=True), nullable=True)
    verdict = Column(JSON(none_as_null=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("taxonomy_id", "key", name="uq_claim_taxonomy_key"),)

    def __repr__(self) -> str:
        return f"<ClaimRecord(taxonomy={self.taxonomy_id}, key={self.key})>"


class ApprovalPolicyRecord(Base):  # type: ignore[valid-type,misc]
    """
    A taxonomy's approval policy: which proposed operations may apply on their own.

    Attributes:
        taxonomy_id: The taxonomy it governs (deleted with it)
        rules: {"auto_apply": [{"op", "kind", "class", "scope"}, ...], "min_probability": n}
        updated_at: When the policy was last set
    """

    __tablename__ = "approval_policies"

    taxonomy_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    rules = Column(JSON, nullable=False, default=dict)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ApprovalPolicyRecord(taxonomy={self.taxonomy_id})>"


class GroundingWorkflow(Base):  # type: ignore[valid-type,misc]
    """
    Configuration record for a grounding workflow.

    A grounding workflow defines how enrichment runs against an external
    knowledge source (e.g. ConceptNet, schema.org) scoped to a set of classes.

    Attributes:
        id: UUID as string, primary key
        title: Human-readable name
        description: Optional longer description
        source: External knowledge source name (e.g. "ConceptNet", "schema.org")
        class_scope: JSON list of class IDs or names to scope enrichment
        status: Workflow status (active, inactive, error)
        last_run: UTC timestamp of most recent run (nullable)
        last_run_record_count: Record count from most recent run (nullable)
        created_at: UTC timestamp of creation
        updated_at: UTC timestamp of last modification
    """

    __tablename__ = "grounding_workflows"

    id = Column(String(36), primary_key=True, nullable=False)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    source = Column(String(255), nullable=False)
    class_scope = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of class IDs or names to scope enrichment",
    )
    status = Column(
        String(20),
        nullable=False,
        default="inactive",
        index=True,
        doc="Workflow status: active, inactive, error",
    )
    last_run = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp of most recent run",
    )
    last_run_record_count = Column(
        Integer,
        nullable=True,
        doc="Record count from most recent run",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'error')",
            name="check_valid_workflow_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<GroundingWorkflow(id={self.id}, title={self.title}," f" status={self.status})>"


class WorkflowRun(Base):  # type: ignore[valid-type,misc]
    """
    Record of a single execution of a grounding workflow.

    Attributes:
        id: UUID as string, primary key
        workflow_id: FK to grounding_workflows.id
        status: Run status (running, success, failed)
        record_count: Number of records processed (default 0)
        timestamp: UTC timestamp when the run was initiated
        error_message: Optional error message if status is failed
    """

    __tablename__ = "workflow_runs"

    id = Column(String(36), primary_key=True, nullable=False)
    workflow_id = Column(
        String(36),
        ForeignKey("grounding_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent grounding workflow",
    )
    status = Column(
        String(20),
        nullable=False,
        default="running",
        index=True,
        doc="Run status: running, success, failed",
    )
    record_count = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of records processed",
    )
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp when the run was initiated",
    )
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'failed')",
            name="check_valid_run_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowRun(id={self.id}, workflow_id={self.workflow_id}," f" status={self.status})>"
        )


class Dataset(Base):  # type: ignore[valid-type,misc]
    """
    A named body of data (individuals and their relationships) over one taxonomy's schema.

    Several datasets can share a taxonomy's schema; each individual belongs to
    exactly one (`ontology_entities.dataset_id`), and a relationship belongs to
    its source individual's dataset.

    Attributes:
        id: UUID as string, primary key
        taxonomy_id: The taxonomy whose schema the dataset's data uses
        identifier: Machine-readable slug, unique within the taxonomy
        title: Display name
        yields_to_schema: Schema operations never block on this dataset's data;
            its data follows them instead
        created_at: Timestamp of creation (UTC)
        last_modified: Timestamp of last modification (UTC)
    """

    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, nullable=False)
    taxonomy_id = Column(
        String(36),
        ForeignKey("ontology_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Taxonomy whose schema the dataset's data uses",
    )
    identifier = Column(String(255), nullable=False, doc="Slug, unique within the taxonomy")
    title = Column(String(255), nullable=False)
    yields_to_schema = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        doc="Schema operations never block on this dataset's data",
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

    __table_args__ = (
        UniqueConstraint("taxonomy_id", "identifier", name="uk_dataset_taxonomy_identifier"),
    )

    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, identifier={self.identifier})>"
