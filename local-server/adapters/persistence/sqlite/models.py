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
from typing import Any, Dict, Tuple

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    JSON,
    LargeBinary,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()  # type: ignore[name-defined,var-annotated]


class OntologyEntity(Base):  # type: ignore[misc,valid-type]
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
        doc="Discriminator: taxonomy, concept_scheme, class, individual, property_definition",
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
    is_indexed = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether included in semantic indexes",
    )

    # Property definition fields (only used when node_type='property_definition')
    identifier = Column(
        String(255),
        nullable=True,
        unique=True,
        doc="Machine-readable identifier (unique, for property_definition)",
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
            "node_type IN ('taxonomy', 'concept_scheme', 'class', 'individual', 'property_definition')",
            name="check_valid_node_type",
        ),
        Index("idx_node_type_title", "node_type", "title"),
    )

    def __repr__(self) -> str:
        return (
            f"<OntologyEntity(id={self.id}, type={self.node_type}, title={self.title})>"
        )


class IndividualClass(Base):  # type: ignore[misc,valid-type]
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
        doc="Zero-based position in the ordered list (determines inheritance precedence)",
    )

    __table_args__ = (
        PrimaryKeyConstraint("individual_id", "class_id", name="pk_individual_classes"),
        UniqueConstraint("individual_id", "position", name="uk_individual_position"),
    )

    def __repr__(self) -> str:
        return f"<IndividualClass(individual_id={self.individual_id}, class_id={self.class_id}, position={self.position})>"


class Relationship(Base):  # type: ignore[misc,valid-type]
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
        return f"<Relationship(id={self.id}, source={self.source_id}, target={self.target_id})>"


class PropertyDefinition(Base):  # type: ignore[misc,valid-type]
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
    ontology_mapping = Column(
        JSON, nullable=True, doc="JSON mapping to external ontologies"
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


class ChangeEvent(Base):  # type: ignore[misc,valid-type]
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
    entity_id = Column(
        String(36), nullable=False, index=True, doc="Entity that changed"
    )
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
    new_state = Column(
        JSON, nullable=False, doc="JSON snapshot after change (null for delete)"
    )
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp of the change",
    )
    user_id = Column(
        String(36), nullable=True, doc="Optional ID of user who made the change"
    )
    change_reason = Column(
        Text, nullable=True, doc="Optional explanation of the change"
    )
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
        return f"<ChangeEvent(id={self.id}, entity_id={self.entity_id}, operation={self.operation})>"


class ExtractionResult(Base):  # type: ignore[misc,valid-type]
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
        doc="JSON list of {id, label, entity_type, source_layer, confidence, uri, description, properties}",
    )
    layers_executed = Column(
        JSON,
        nullable=False,
        default=list,
        doc="JSON list of {layer_number, layer_name, entities_found, duration_ms, success, error_message}",
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
        return f"<ExtractionResult(id={self.id}, text_len={len(self.text or '')}, entities={len(self.extracted_entities or [])})>"


class EntityVersion(Base):  # type: ignore[misc,valid-type]
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


class Changeset(Base):  # type: ignore[misc,valid-type]
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


class ChangesetEvent(Base):  # type: ignore[misc,valid-type]
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
        return f"<ChangesetEvent(changeset_id={self.changeset_id}, change_event_id={self.change_event_id})>"


class Proposal(Base):  # type: ignore[misc,valid-type]
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
        return f"<Proposal(id={self.id}, changeset_id={self.changeset_id}, state={self.state})>"


class ConflictResolution(Base):  # type: ignore[misc,valid-type]
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
        return f"<ConflictResolution(proposal_id={self.proposal_id}, entity_id={self.entity_id}, field_name={self.field_name})>"


class BatchRun(Base):  # type: ignore[misc,valid-type]
    """
    Abstract base class for all batch run types using joined-table inheritance.

    Batch runs (imports, extractions, etc.) share common fields and are
    distinguished by the run_type discriminator column. Subclasses use
    joined-table inheritance, with their own tables containing type-specific fields.

    This class is abstract and should not be instantiated directly.
    Use ImportRun or ExtractionRun instead.

    Attributes:
        id: UUID as string, primary key
        created_at: UTC timestamp of run initiation
        created_by: Optional ID of the user who initiated the run
        status: Current status (pending, committed, failed, etc. depending on type)
        affected_entity_ids: JSON list of entity IDs affected by this run
        run_type: Discriminator column (import, extraction, etc.)
    """

    __tablename__ = "batch_runs"

    id = Column(String(36), primary_key=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        doc="UTC timestamp of run initiation",
    )
    created_by = Column(
        String(36), nullable=True, doc="Optional ID of user who initiated the run"
    )
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
        String(20),
        nullable=False,
        index=True,
        doc="Discriminator: import, extraction, etc.",
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_on": run_type,
    }
    __table_args__ = (
        CheckConstraint(
            "run_type IN ('import', 'extraction')", name="check_valid_run_type"
        ),
        Index("idx_run_type_status", "run_type", "status"),
    )

    def __repr__(self) -> str:
        return f"<BatchRun(id={self.id}, type={self.run_type}, status={self.status})>"


class ImportRun(BatchRun):  # type: ignore[misc,valid-type]
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
    source_uri = Column(
        Text, nullable=True, doc="Optional URI or filename of the import source"
    )
    source_hash = Column(
        String(64), nullable=False, doc="SHA256 hash of the imported bytes"
    )
    scope_type = Column(
        String(20),
        nullable=False,
        doc="Type of scope (whole_graph, taxonomy, scheme, entity_set)",
    )
    scope_taxonomy_id = Column(
        String(36), nullable=True, doc="For taxonomy scope, the taxonomy ID"
    )
    scope_scheme_id = Column(
        String(36), nullable=True, doc="For scheme scope, the scheme ID"
    )
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
    resolutions = Column(
        JSON, nullable=False, default=list, doc="JSON list of applied resolutions"
    )

    __mapper_args__: Dict[str, Any] = {
        "polymorphic_identity": "import",
    }

    def __repr__(self) -> str:
        return f"<ImportRun(id={self.id}, format={self.format}, status={self.status})>"


class ExtractionRun(BatchRun):  # type: ignore[misc,valid-type]
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
    triples_extracted = Column(
        Integer, nullable=False, doc="Count of triples returned by API"
    )
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
