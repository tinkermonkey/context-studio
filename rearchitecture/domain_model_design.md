# Context Studio: Domain Model Design

## Detailed Entity, Value Object, and Relationship Specifications

**Date:** 2026-03-13
**Companion Documents:** `architecture_design.md`, `transformation_roadmap.md`

---

## 1. Ontology Management Domain Model

This is the heart of Context Studio. The domain model replaces the current unified `StructureNode` table with distinct entity types that map to industry-standard ontology concepts.

### 1.1 Entity Hierarchy

```
                    ┌─────────────┐
                    │  Taxonomy    │  (was: StructureNode[node_type=layer])
                    │              │  Top-level organizational container
                    └──────┬──────┘
                           │ contains
                    ┌──────┴──────┐
                    │ConceptScheme │  (was: StructureNode[node_type=domain])
                    │              │  A coherent group of concepts
                    └──────┬──────┘
                           │ contains
                    ┌──────┴──────┐
                    │    Class     │  (was: StructureNode[node_type=term])
                    │              │  An ontology concept / category
                    └──────┬──────┘
                           │ instantiatedBy (future)
                    ┌──────┴──────┐
                    │  Individual  │  (new — not yet implemented)
                    │              │  A concrete instance of a Class
                    └─────────────┘
```

### 1.2 Entity Definitions

#### Taxonomy

The top-level organizational container. Represents a broad domain of knowledge (e.g., "Technology", "Biology", "Finance").

```python
@dataclass
class Taxonomy:
    id: str
    title: str
    definition: Optional[str] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    version: int = 1
```

**Invariants:**
- `title` must be non-empty and unique across taxonomies
- A taxonomy has no parent (it is a root-level entity)


---

#### ConceptScheme

A coherent grouping of related concepts within a taxonomy. Inspired by SKOS `ConceptScheme`. Examples: within a "Technology" taxonomy, schemes might be "Programming Languages", "Data Stores", "Protocols".

```python
@dataclass
class ConceptScheme:
    id: str
    title: str
    taxonomy_id: str                        # which Taxonomy this belongs to
    definition: Optional[str] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    version: int = 1
```

**Invariants:**
- `title` must be unique within its parent taxonomy
- `taxonomy_id` must reference an existing Taxonomy
- A concept scheme cannot exist without a taxonomy


---

#### Class

An ontology concept that defines a category of things. Classes can form subclass hierarchies (via `parent_class_id`) and carry metadata like external references and lexical senses.

This is the primary working entity in Context Studio — what users spend most of their time creating, organizing, and relating.

```python
@dataclass
class Class:
    id: str
    title: str
    concept_scheme_id: str                  # which ConceptScheme this belongs to
    definition: Optional[str] = None
    parent_class_id: Optional[str] = None   # subClassOf hierarchy
    structural_property_id: Optional[str] = None  # primary structural relationship
    external_references: list[ExternalReference] = field(default_factory=list)
    lexical_senses: list[LexicalSense] = field(default_factory=list)
    data_properties: list[DataPropertyValue] = field(default_factory=list)
    title_embedding: Optional[bytes] = None
    definition_embedding: Optional[bytes] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    version: int = 1
```

**Invariants:**
- `title` must be non-empty
- `concept_scheme_id` must reference an existing ConceptScheme
- `parent_class_id`, if set, must not create a cycle in the subclass hierarchy
- `parent_class_id` cannot equal `id` (self-reference check)
- `structural_property_id`, if set, must reference a valid PropertyDefinition

**Note on parent disambiguation:** `concept_scheme_id` (always set) defines where the class lives in the hierarchy. `parent_class_id` (optional) defines the subclass relationship within that scheme. These were conflated in the legacy model's `parent_node_id` column.

---

#### Individual (Future)

A concrete instance of a Class. For example, "SQLite" is an individual of the class "Embedded Database".

```python
@dataclass
class Individual:
    id: str
    title: str
    class_id: str                           # rdf:type — which Class this instantiates
    definition: Optional[str] = None
    data_properties: list[DataPropertyValue] = field(default_factory=list)
    external_references: list[ExternalReference] = field(default_factory=list)
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    version: int = 1
```

**Invariants:**
- `class_id` must reference an existing Class
- An individual can instantiate only one primary class (additional typing via relationships)

**Implementation note:** This entity does not exist in the current data model. It will be added when the system needs to distinguish between ontology concepts and concrete instances. The database migration for individuals can be deferred past the initial re-architecture.

---

#### Relationship

A typed, directed edge between two ontology entities. Replaces `StructureNodeLink`.

```python
@dataclass
class Relationship:
    id: str
    source_id: str                          # the subject entity
    target_id: str                          # the object entity
    property_definition_id: str             # the type of relationship
    property_label: str                     # denormalized label for display
    created_at: Optional[datetime] = None
```

**Invariants:**
- `source_id` and `target_id` must reference existing entities
- `property_definition_id` must reference a valid PropertyDefinition
- The triple `(source_id, target_id, property_definition_id)` must be unique
- `source_id` != `target_id` (no self-loops, enforced at domain level)


---

#### PropertyDefinition

Defines a type of relationship (object property) that can exist between entities. Replaces `Predicate`.

```python
@dataclass
class PropertyDefinition:
    id: str
    identifier: str                         # machine-readable identifier (e.g., "is_a", "part_of")
    title: str                              # human-readable label
    definition: Optional[str] = None
    ontology_mapping: Optional[OntologyMapping] = None  # mapping to external ontology
    is_relevant: Optional[bool] = None      # None=not evaluated, True=relevant, False=irrelevant
    date_created: Optional[datetime] = None
    date_modified: Optional[datetime] = None
```

**Invariants:**
- `identifier` must be unique
- `title` must be unique
- `identifier` should follow a consistent naming convention (snake_case)


---

### 1.3 Value Objects

Value objects are immutable, identity-less data structures that describe aspects of entities.

#### NodeType

```python
class NodeType(str, Enum):
    TAXONOMY = "taxonomy"
    CONCEPT_SCHEME = "concept_scheme"
    CLASS = "class"
    INDIVIDUAL = "individual"
```


---

#### ExternalReference

Represents a link to an external knowledge source (DBpedia, Wikidata, ConceptNet, etc.).

```python
@dataclass(frozen=True)
class ExternalReference:
    source: str                 # e.g., "dbpedia", "wikidata", "conceptnet"
    uri: str                    # the external URI
    label: Optional[str] = None # human-readable label from the source
    confidence: Optional[float] = None  # match confidence score
    metadata: Optional[dict] = None     # source-specific metadata
```


---

#### LexicalSense

Word sense disambiguation data, typically from WordNet.

```python
@dataclass(frozen=True)
class LexicalSense:
    synset_id: str              # WordNet synset identifier
    definition: str             # the sense definition
    lemma: str                  # the lemma/word form
    confidence: Optional[float] = None
    source: str = "wordnet"
```


---

#### DataPropertyValue

A literal-valued attribute on an entity (corresponds to OWL DatatypeProperty).

```python
@dataclass(frozen=True)
class DataPropertyValue:
    key: str                    # attribute name
    value: Any                  # attribute value (string, number, boolean, etc.)
    datatype: Optional[str] = None  # optional type hint (e.g., "xsd:string", "xsd:integer")
```


---

#### OntologyMapping

Maps a PropertyDefinition to an external ontology standard.

```python
@dataclass(frozen=True)
class OntologyMapping:
    ontology: str               # e.g., "owl", "rdfs", "skos", "conceptnet"
    uri: str                    # the property URI in that ontology
    label: Optional[str] = None
    exact_match: bool = False   # whether this is an exact semantic match
```


---

#### SearchCriteria

Encapsulates search parameters for querying ontology entities.

```python
@dataclass(frozen=True)
class SearchCriteria:
    query: Optional[str] = None              # text search
    node_type: Optional[NodeType] = None     # filter by type
    taxonomy_id: Optional[str] = None        # filter by taxonomy
    scheme_id: Optional[str] = None          # filter by concept scheme
    parent_id: Optional[str] = None          # filter by parent
    use_semantic_search: bool = False         # use embedding similarity
    limit: int = 50
    offset: int = 0
```

---

## 2. Graph Analysis Domain Model

### 2.1 Entities

#### KnowledgeGraph

An in-memory representation of the ontology as a graph structure.

```python
@dataclass
class KnowledgeGraph:
    node_count: int
    edge_count: int
    is_directed: bool = True
    last_built: Optional[datetime] = None
```

This is a lightweight descriptor; the actual graph data lives behind the `GraphEngine` port. The domain service doesn't hold a NetworkX graph directly—it asks the engine to perform operations.

---

#### GraphMetrics

Results from graph analysis algorithms.

```python
@dataclass
class GraphMetrics:
    density: float
    average_degree: float
    connected_components: int
    centrality: dict[str, float]            # node_id → centrality score
    communities: list[set[str]]             # list of community node sets
    algorithm: str                          # which algorithm produced these
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

---

#### PathResult

```python
@dataclass
class PathResult:
    source_id: str
    target_id: str
    path: list[str]                         # ordered node IDs from source to target
    length: int
    relationships: list[str]                # property labels along the path
```

---

## 3. Knowledge Extraction Domain Model

### 3.1 Entities

#### ExtractionResult

The output of the RAG pipeline.

```python
@dataclass
class ExtractionResult:
    input_text: str
    extracted_entities: list[ExtractedEntity]
    layers_executed: list[ExtractionLayerResult]
    total_duration_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

#### ExtractedEntity

```python
@dataclass
class ExtractedEntity:
    label: str
    entity_type: str                        # "class", "individual", "property", etc.
    confidence: float
    source_layer: int                       # which extraction layer found this
    matched_class_id: Optional[str] = None  # linked to existing Class, if resolved
    context: Optional[str] = None           # surrounding text context
```

#### ExtractionLayerResult

```python
@dataclass
class ExtractionLayerResult:
    layer_number: int
    layer_name: str                         # "kg_context", "llm_extraction", "nlp_gap", "reference_resolution"
    entities_found: int
    duration_ms: float
    metadata: Optional[dict] = None
```

---

## 4. LLM Pipeline Domain Model

### 4.1 Entities

#### PipelineConfiguration

Replaces `PipelineFlavor`.

```python
@dataclass
class PipelineConfiguration:
    id: str
    pipeline: str                           # which pipeline this config belongs to
    title: str
    provider: str                           # "openai", "anthropic", etc.
    model: str                              # model identifier
    config: dict                            # provider-specific configuration
    system_prompt: str
    user_prompt: str
    version: int = 1
    enabled: bool = True
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
```

#### Execution

A traced LLM call.

```python
@dataclass
class Execution:
    id: str
    pipeline_config_id: str
    input_text: str
    output_text: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    status: str                             # "success", "error", "timeout"
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 5. Version Control Domain Model

### 5.1 Entities

#### ChangeEvent

Unchanged from current model — already well-designed.

```python
@dataclass
class ChangeEvent:
    id: Optional[int]                       # auto-increment
    event_type: str                         # "create", "update", "delete"
    record_type: str                        # entity type that changed
    record_id: Optional[str]
    old_data: Optional[dict]
    new_data: Optional[dict]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed: bool = False
```

#### EntityVersion

```python
@dataclass
class EntityVersion:
    entity_id: str
    version: int
    state: ChangeState
    snapshot: dict                          # serialized entity state at this version
    created_at: datetime
    parent_version: Optional[int] = None
```

#### ChangeState

```python
class ChangeState(str, Enum):
    WORKING = "working"
    STAGED = "staged"
    PROPOSED = "proposed"
    APPROVED = "approved"
    MERGED = "merged"
```

---

## 6. Persistence Mapping Strategy

The SQLAlchemy ORM models in `adapters/persistence/sqlite/models.py` are the **source of truth for the database schema**. They remain completely separate from domain entities. Each repository adapter contains mapper methods to translate between the two representations.

```python
# adapters/persistence/sqlite/ontology_repo.py

class SQLiteOntologyRepository:
    """Implements OntologyRepository port using SQLAlchemy + SQLite."""

    def _to_domain(self, orm_entity: OntologyEntityORM) -> Class:
        """Map from ORM model to domain entity."""
        return Class(
            id=orm_entity.id,
            title=orm_entity.title,
            definition=orm_entity.definition,
            concept_scheme_id=orm_entity.concept_scheme_id,
            parent_class_id=orm_entity.parent_class_id,
            external_references=self._parse_references(orm_entity.reference_links),
            lexical_senses=self._parse_senses(orm_entity.word_senses),
            data_properties=self._parse_attributes(orm_entity.attributes),
            title_embedding=orm_entity.title_embedding,
            definition_embedding=orm_entity.definition_embedding,
            version=orm_entity.version,
            created_at=orm_entity.created_at,
            last_modified=orm_entity.last_modified,
        )

    def _to_orm(self, cls: Class) -> OntologyEntityORM:
        """Map from domain entity to ORM model."""
        return OntologyEntityORM(
            id=cls.id,
            node_type=NodeType.CLASS.value,
            title=cls.title,
            definition=cls.definition,
            concept_scheme_id=cls.concept_scheme_id,
            parent_class_id=cls.parent_class_id,
            reference_links=json.dumps([asdict(r) for r in cls.external_references]),
            word_senses=json.dumps([asdict(s) for s in cls.lexical_senses]),
            attributes=json.dumps([asdict(a) for a in cls.data_properties]),
            title_embedding=cls.title_embedding,
            definition_embedding=cls.definition_embedding,
            version=cls.version,
        )
```

### Database Schema Decision: Unified Table

A single `ontology_entities` table with a `node_type` discriminator column stores taxonomies, concept schemes, and classes. The adapter maps rows to the correct domain entity type at runtime.

This keeps the hierarchy query simple (a single join on `concept_scheme_id` or `parent_class_id`) while the domain layer presents distinct types. `individuals` will be added as a separate table when that feature is built.

---

## 7. Domain Event Catalog

Domain events are emitted by domain services and consumed by infrastructure to trigger side effects (persistence of change events, cache invalidation, webhook notifications, etc.).

| Event | Emitted By | Data |
|---|---|---|
| `ClassCreated` | OntologyService | class_id, title, scheme_id |
| `ClassUpdated` | OntologyService | class_id, changed_fields, old_values, new_values |
| `ClassDeleted` | OntologyService | class_id, title |
| `ClassMoved` | OntologyService | class_id, old_parent_id, new_parent_id |
| `RelationshipCreated` | OntologyService | rel_id, source_id, target_id, property_id |
| `RelationshipDeleted` | OntologyService | rel_id, source_id, target_id, property_id |
| `PropertyDefinitionCreated` | OntologyService | prop_id, identifier, title |
| `SchemeCreated` | OntologyService | scheme_id, title, taxonomy_id |
| `TaxonomyCreated` | OntologyService | taxonomy_id, title |
| `GraphInvalidated` | OntologyService | reason |
| `ExtractionCompleted` | ExtractionService | result_id, entity_count, duration_ms |
| `PipelineExecuted` | PipelineService | execution_id, pipeline_id, status |

### Event Handling Pattern

```python
# In the adapter layer, not the domain
class ChangeEventRecorder:
    """Subscribes to domain events and persists ChangeEvent records."""

    def __init__(self, change_repo: ChangeRepository):
        self.change_repo = change_repo

    def on_class_created(self, event: ClassCreated):
        self.change_repo.record_change(ChangeEvent(
            event_type="create",
            record_type="class",
            record_id=event.class_id,
            new_data={"title": event.title, "scheme_id": event.scheme_id},
        ))

    def on_class_updated(self, event: ClassUpdated):
        self.change_repo.record_change(ChangeEvent(
            event_type="update",
            record_type="class",
            record_id=event.class_id,
            old_data=event.old_values,
            new_data=event.new_values,
        ))
```

This pattern keeps change event persistence out of the domain service and makes it easy to add other event consumers (e.g., WebSocket notifications, graph cache invalidation) without modifying domain code.

---

## 8. Domain Event Base Definition

All domain events inherit from a common base:

```python
@dataclass
class DomainEvent:
    """Base class for all domain events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class ClassCreated(DomainEvent):
    class_id: str = ""
    title: str = ""
    concept_scheme_id: str = ""

@dataclass
class ClassUpdated(DomainEvent):
    class_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    old_values: dict = field(default_factory=dict)
    new_values: dict = field(default_factory=dict)

@dataclass
class ClassDeleted(DomainEvent):
    class_id: str = ""
    title: str = ""

@dataclass
class RelationshipCreated(DomainEvent):
    relationship_id: str = ""
    source_id: str = ""
    target_id: str = ""
    property_definition_id: str = ""

@dataclass
class GraphInvalidated(DomainEvent):
    reason: str = ""
```

---

## 9. Admin Context Entities

#### SystemHealth

```python
@dataclass
class SystemHealth:
    status: str                             # "healthy", "degraded", "unhealthy"
    database_connected: bool
    embedding_model_loaded: bool
    nlp_pipeline_ready: bool
    llm_providers_available: list[str]
    uptime_seconds: float
    issues: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

#### BackgroundTask

```python
@dataclass
class BackgroundTask:
    id: str
    name: str
    status: str                             # "pending", "running", "completed", "failed"
    progress: Optional[float] = None        # 0.0–1.0
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

#### AppConfiguration

```python
@dataclass
class AppConfiguration:
    """Application configuration. Loaded from config.json."""
    server: dict                            # host, port, cors settings
    database: dict                          # paths, pool settings
    llm: dict                               # provider keys, default models
    nlp: dict                               # model name, components
    embedding: dict                         # model name
    reference_sources: dict                 # enabled sources, rate limits
    sync: Optional[dict] = None             # S3/remote sync settings
    logging: dict = field(default_factory=lambda: {"level": "INFO"})
```

---

## 10. Versioning Context: Conflict Resolution Entities

#### ConflictReport

```python
@dataclass
class ConflictReport:
    """Report of conflicts detected between two sets of changes."""
    conflicts: list[Conflict]
    auto_resolvable: int                    # count of conflicts with automatic resolution
    manual_required: int                    # count needing human intervention
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class Conflict:
    entity_id: str
    entity_type: str
    field_name: str
    local_value: Any
    remote_value: Any
    resolution_strategy: Optional[str] = None  # "local_wins", "remote_wins", "merge", "manual"
    resolved_value: Optional[Any] = None
```

#### MergeResult

```python
@dataclass
class MergeResult:
    """Result of merging two sets of changes."""
    success: bool
    merged_changes: int
    conflicts_resolved: int
    conflicts_remaining: int
    errors: list[str] = field(default_factory=list)
    merged_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 11. Cross-Context Dependency Map

Bounded contexts communicate only through their ports. Here is the dependency graph:

```
  Ontology Management ◄──── Graph Analysis
        ▲                        (reads ontology data to build graphs)
        │
        ├──── Knowledge Extraction
        │     (reads KG context for RAG layer 0)
        │
        ├──── Version Control
        │     (reads current entity state for diff computation)
        │
        └──── LLM Pipeline Management
              (no direct dependency on ontology, but extraction uses LLM)

  Shared ports:
  ─ OntologyRepository is consumed by Ontology, Graph, and Extraction contexts
  ─ LLMProvider is consumed by Extraction and Pipeline contexts
  ─ EventPublisher is consumed by Ontology and produces events for Version Control
```

The key rule: contexts never import each other's services directly. They share data through ports (primarily `OntologyRepository` for read access).
