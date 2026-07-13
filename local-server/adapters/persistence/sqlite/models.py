"""
SQLAlchemy ORM models for Context Studio's primary database (local.db).

This module defines all ORM models for the Ontology Management bounded context:
- OntologyEntity: Single-table inheritance pattern for taxonomies, concept schemes, classes,
individuals
- Relationship: Typed, directed edges between entities
- PropertyDefinition: Registry of defined object property types

Models are the source of truth for Alembic migrations via autogenerate.

Design Notes:
- Single-table inheritance (STI) via node_type discriminator column
- All timestamps are UTC
- JSON storage for nested value objects (external_references, lexical_senses, data_properties)
- PropertyDefinition appears in both ontology_entities (for referential integrity) and
property_definitions (optimized queries)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

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
)
from sqlalchemy.orm import declarative_base

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
        description: Longer description (optional)
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
        doc=("Discriminator: taxonomy, concept_scheme, class, individual," " property_definition"),
    )
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
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
    canonical_predicate = Column(
        String(255),
        nullable=True,
        doc=(
            "Bare canonical relation verb, e.g. 'navigates-to' (for "
            "property_definition; the form predicate grounding clamps to). NULL "
            "for other node types and property definitions with none supplied."
        ),
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

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('taxonomy', 'concept_scheme', 'class', 'individual',"
            " 'property_definition')",
            name="check_valid_node_type",
        ),
        Index("idx_node_type_title", "node_type", "title"),
    )

    def __repr__(self) -> str:
        return f"<OntologyEntity(id={self.id}, type={self.node_type}, title={self.title})>"


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
        changeset_id: Optional ID of a changeset this event belongs to
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
    changeset_id = Column(
        String(36),
        nullable=True,
        index=True,
        doc="Optional changeset this event belongs to",
    )
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


class EntityVersion(Base):  # type: ignore[valid-type,misc]
    """
    Point-in-time snapshot of an entity's state.

    Tracks versioning history for entities, where each version represents
    a distinct state in the entity's lifecycle.

    Attributes:
        entity_id: ID of the entity being versioned
        version: Version number (increments with each change)
        state: State code or label (e.g., 'active', 'archived')
        snapshot: Full JSON snapshot of entity at this version
        created_at: UTC timestamp when this version was created
        parent_version: Version number of parent (for tracking lineage)
    """

    __tablename__ = "entity_versions"

    entity_id = Column(String(36), primary_key=True, nullable=False)
    version = Column(Integer, primary_key=True, nullable=False)
    state = Column(String(20), nullable=False)
    snapshot = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    parent_version = Column(Integer, nullable=True)

    __table_args__ = ()

    def __repr__(self) -> str:
        return f"<EntityVersion(entity_id={self.entity_id}, version={self.version})>"


class Changeset(Base):  # type: ignore[valid-type,misc]
    """
    A grouped set of related change events (a transaction).

    Changesets progress through a workflow: working → staged → proposed → approved → merged.
    They represent a logical unit of work that can be reviewed and applied as a whole.

    Attributes:
        id: UUID as string, primary key
        name: Human-readable name for the changeset
        description: Optional detailed description
        state: Current state ('working', 'staged', 'proposed', 'approved', 'merged')
        created_at: UTC timestamp of creation
        updated_at: UTC timestamp of last modification
    """

    __tablename__ = "changesets"

    id = Column(String(36), primary_key=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    state = Column(String(20), nullable=False, default="working")
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

    __table_args__ = ()

    def __repr__(self) -> str:
        return f"<Changeset(id={self.id}, name={self.name}, state={self.state})>"


class ChangesetEvent(Base):  # type: ignore[valid-type,misc]
    """
    Junction table linking change events to changesets.

    Represents the many-to-many relationship between changesets
    and the change events they contain.

    Attributes:
        changeset_id: ID of the changeset
        change_event_id: ID of the change event
    """

    __tablename__ = "changeset_events"

    changeset_id = Column(
        String(36),
        ForeignKey("changesets.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    change_event_id = Column(
        String(36),
        ForeignKey("change_events.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_changeset_events_changeset_id", "changeset_id"),
        Index("ix_changeset_events_change_event_id", "change_event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ChangesetEvent(changeset_id={self.changeset_id},"
            f" change_event_id={self.change_event_id})>"
        )


class Proposal(Base):  # type: ignore[valid-type,misc]
    """
    A formal request to merge a changeset.

    Proposals allow review and discussion before changes are applied.
    They track submission time, reviewer comments, and approval status.

    Attributes:
        id: UUID as string, primary key
        changeset_id: ID of the changeset being proposed
        state: Current state ('open', 'approved', 'rejected', 'merged')
        submitted_at: UTC timestamp when proposal was submitted
        reviewed_at: UTC timestamp when proposal was reviewed (None if not reviewed)
        reviewer_notes: Optional notes from the reviewer
    """

    __tablename__ = "proposals"

    id = Column(String(36), primary_key=True, nullable=False)
    changeset_id = Column(
        String(36),
        ForeignKey("changesets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state = Column(String(20), nullable=False, default="open")
    submitted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_notes = Column(Text, nullable=True)

    __table_args__ = ()

    def __repr__(self) -> str:
        return f"<Proposal(id={self.id}, changeset_id={self.changeset_id}," f" state={self.state})>"


class ConflictResolution(Base):  # type: ignore[valid-type,misc]
    """
    A stored resolution for a conflict in a proposal.

    Conflict resolutions are persisted when resolve_conflicts() is called,
    allowing the resolution information to be retrieved when merge_proposal() executes.

    Attributes:
        id: UUID as string, primary key
        proposal_id: ID of the proposal containing the conflict
        entity_id: ID of the entity with the conflict
        field_name: Name of the field with the conflict
        resolved_value: The resolved value for this field
    """

    __tablename__ = "conflict_resolutions"

    id = Column(String(36), primary_key=True, nullable=False)
    proposal_id = Column(
        String(36),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id = Column(String(36), nullable=False, index=True)
    field_name = Column(String(255), nullable=False)
    resolved_value = Column(Text, nullable=False)

    __table_args__ = ()

    def __repr__(self) -> str:
        return (
            f"<ConflictResolution(proposal_id={self.proposal_id},"
            f" entity_id={self.entity_id}, field_name={self.field_name})>"
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
    __table_args__ = (
        CheckConstraint(
            "run_type IN ('import', 'extraction', 'individual_extraction', "
            "'schema_extraction', 'schema_node_grounding', "
            "'schema_node_definition_refinement', 'schema_node_connection_refinement', "
            "'no_op')",
            name="check_valid_run_type",
        ),
        Index("idx_run_type_status", "run_type", "status"),
    )

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


class GroundingWorkflow(Base):  # type: ignore[valid-type,misc,assignment]
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

    id: str = Column(String(36), primary_key=True, nullable=False)  # type: ignore[assignment]
    title: str = Column(String(255), nullable=False, index=True)  # type: ignore[assignment]
    description: Optional[str] = Column(Text, nullable=True)  # type: ignore[assignment]
    source: str = Column(String(255), nullable=False)  # type: ignore[assignment]
    class_scope: list[str] = Column(  # type: ignore[assignment]
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of class IDs or names to scope enrichment",
    )
    status: str = Column(  # type: ignore[assignment]
        String(20),
        nullable=False,
        default="inactive",
        index=True,
        doc="Workflow status: active, inactive, error",
    )
    last_run: Optional[datetime] = Column(  # type: ignore[assignment]
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp of most recent run",
    )
    last_run_record_count: Optional[int] = Column(  # type: ignore[assignment]
        Integer,
        nullable=True,
        doc="Record count from most recent run",
    )
    created_at: datetime = Column(  # type: ignore[assignment]
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Column(  # type: ignore[assignment]
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


class WorkflowRun(Base):  # type: ignore[valid-type,misc,assignment]
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

    id: str = Column(String(36), primary_key=True, nullable=False)  # type: ignore[assignment]
    workflow_id: str = Column(  # type: ignore[assignment]
        String(36),
        ForeignKey("grounding_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent grounding workflow",
    )
    status: str = Column(  # type: ignore[assignment]
        String(20),
        nullable=False,
        default="running",
        index=True,
        doc="Run status: running, success, failed",
    )
    record_count: int = Column(  # type: ignore[assignment]
        Integer,
        nullable=False,
        default=0,
        doc="Number of records processed",
    )
    timestamp: datetime = Column(  # type: ignore[assignment]
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp when the run was initiated",
    )
    error_message: Optional[str] = Column(Text, nullable=True)  # type: ignore[assignment]

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
    Persistence model for datasets (importable database files).

    Stores dataset metadata and cached metrics about the dataset's contents.

    Attributes:
        id: UUID as string, primary key
        title: Display name
        filename: Original filename
        description: Optional longer description
        created_at: Timestamp of creation (UTC, auto-set)
        last_accessed: Timestamp of last import/activation
        schema_version: Database schema version string
        layers_count: Cached count of taxonomies
        domains_count: Cached count of concept schemes
        terms_count: Cached count of classes
        relationships_count: Cached count of relationships
        individuals_count: Cached count of individuals
        is_active: Boolean flag for active dataset
        version: Version number for optimistic concurrency
    """

    __tablename__ = "datasets"

    id: str = Column(String(36), primary_key=True, nullable=False)  # type: ignore[assignment]
    title: str = Column(String(255), nullable=False, index=True)  # type: ignore[assignment]
    filename: str = Column(String(255), nullable=False)  # type: ignore[assignment]
    description: Optional[str] = Column(Text, nullable=True)  # type: ignore[assignment]
    created_at: datetime = Column(  # type: ignore[assignment]
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="Timestamp of creation",
    )
    last_accessed: Optional[datetime] = Column(  # type: ignore[assignment]
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of last activation/import",
    )
    schema_version: str = Column(  # type: ignore[assignment]
        String(20),
        nullable=False,
        default="1.0",
        doc="Database schema version",
    )
    layers_count: int = Column(  # type: ignore[assignment]
        Integer,
        nullable=False,
        default=0,
        doc="Cached count of taxonomies",
    )
    domains_count: int = Column(  # type: ignore[assignment]
        Integer,
        nullable=False,
        default=0,
        doc="Cached count of concept schemes",
    )
    terms_count: int = Column(  # type: ignore[assignment]
        Integer,
        nullable=False,
        default=0,
        doc="Cached count of classes",
    )
    relationships_count: int = Column(  # type: ignore[assignment]
        Integer,
        nullable=False,
        default=0,
        doc="Cached count of relationships",
    )
    individuals_count: int = Column(  # type: ignore[assignment]
        Integer,
        nullable=False,
        default=0,
        doc="Cached count of individuals",
    )
    is_active: bool = Column(  # type: ignore[assignment]
        Boolean,
        nullable=False,
        default=False,
        index=True,
        doc="Whether this is the active dataset",
    )
    version: int = Column(  # type: ignore[assignment]
        Integer,
        nullable=False,
        default=1,
        doc="Version number for optimistic concurrency",
    )

    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, title={self.title}, is_active={self.is_active})>"
