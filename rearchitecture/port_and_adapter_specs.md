# Context Studio: Port & Adapter Specifications

## Detailed Interface Contracts and Migration Mapping

**Date:** 2026-03-13
**Companion Documents:** `architecture_design.md`, `transformation_roadmap.md`, `domain_model_design.md`

---

## 1. Port Catalog

This document specifies every port interface in the system, its contract, and which adapter(s) implement it. Ports are grouped by the bounded context that defines them.

---

## 2. Ontology Context Ports

### 2.1 OntologyRepository

**Purpose:** Persistence of all ontology entities (taxonomies, concept schemes, classes, individuals, relationships, property definitions).

**Defined in:** `domain/ontology/ports.py`

**Contract:**

```python
class OntologyRepository(Protocol):
    """
    Repository for ontology entity persistence.

    All methods that accept or return domain entities work with the types
    defined in domain.ontology.entities. The repository is responsible for
    mapping these to/from whatever storage format is used.

    Methods that return Optional return None when the entity is not found.
    Methods that return Sequence return an empty sequence when no matches exist.
    Delete methods return True if the entity was deleted, False if it didn't exist.
    Save methods perform upsert: create if new, update if existing (matched by id).
    """

    # --- Taxonomy ---
    def get_taxonomy(self, taxonomy_id: str) -> Optional[Taxonomy]: ...
    def list_taxonomies(self) -> Sequence[Taxonomy]: ...
    def save_taxonomy(self, taxonomy: Taxonomy) -> Taxonomy: ...
    def delete_taxonomy(self, taxonomy_id: str) -> bool: ...

    # --- ConceptScheme ---
    def get_concept_scheme(self, scheme_id: str) -> Optional[ConceptScheme]: ...
    def list_concept_schemes(self, taxonomy_id: Optional[str] = None) -> Sequence[ConceptScheme]: ...
    def save_concept_scheme(self, scheme: ConceptScheme) -> ConceptScheme: ...
    def delete_concept_scheme(self, scheme_id: str) -> bool: ...

    # --- Class ---
    def get_class(self, class_id: str) -> Optional[Class]: ...
    def list_classes(
        self,
        scheme_id: Optional[str] = None,
        parent_class_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Class]: ...
    def save_class(self, cls: Class) -> Class: ...
    def delete_class(self, class_id: str) -> bool: ...
    def search_classes(self, criteria: SearchCriteria) -> Sequence[Class]: ...
    def count_classes(self, scheme_id: Optional[str] = None) -> int: ...

    # --- Individual (future) ---
    def get_individual(self, individual_id: str) -> Optional[Individual]: ...
    def list_individuals(self, class_id: Optional[str] = None) -> Sequence[Individual]: ...
    def save_individual(self, individual: Individual) -> Individual: ...
    def delete_individual(self, individual_id: str) -> bool: ...

    # --- Relationship ---
    def get_relationship(self, rel_id: str) -> Optional[Relationship]: ...
    def list_relationships(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        property_id: Optional[str] = None,
    ) -> Sequence[Relationship]: ...
    def save_relationship(self, rel: Relationship) -> Relationship: ...
    def delete_relationship(self, rel_id: str) -> bool: ...

    # --- PropertyDefinition ---
    def get_property_definition(self, prop_id: str) -> Optional[PropertyDefinition]: ...
    def get_property_definition_by_identifier(self, identifier: str) -> Optional[PropertyDefinition]: ...
    def list_property_definitions(self, is_relevant: Optional[bool] = None) -> Sequence[PropertyDefinition]: ...
    def save_property_definition(self, prop: PropertyDefinition) -> PropertyDefinition: ...
    def delete_property_definition(self, prop_id: str) -> bool: ...

    # --- Bulk operations ---
    def get_all_entities_and_relationships(self) -> tuple[Sequence[Any], Sequence[Relationship]]:
        """Return all entities and relationships for graph building."""
        ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `SQLiteOntologyRepository` | `adapters/persistence/sqlite/ontology_repo.py` | Primary implementation. Uses SQLAlchemy ORM. Maps unified `ontology_entities` table to typed domain entities. |
| `PostgresOntologyRepository` | (future) | Enterprise deployment. Same port, different connection/dialect. |
| `InMemoryOntologyRepository` | `tests/fakes/` | For domain unit tests. Simple dict-based storage. |

**Current code this replaces:**
- `services/node_service.py` (the persistence parts — `_create_node`, `_get_node`, query methods)
- `services/node_link_service.py` (all persistence)
- Direct SQLAlchemy queries in API route handlers

---

### 2.2 EmbeddingService

**Purpose:** Generate vector embeddings for text, used for semantic search.

**Defined in:** `domain/ontology/ports.py`

**Contract:**

```python
class EmbeddingService(Protocol):
    """
    Service for generating vector embeddings from text.

    Embeddings are returned as bytes (serialized float32 numpy arrays)
    matching the current storage format in the database.

    The embed_text method must be thread-safe.
    """

    def embed_text(self, text: str) -> bytes: ...
    def embed_batch(self, texts: list[str]) -> list[bytes]: ...
    def similarity(self, embedding_a: bytes, embedding_b: bytes) -> float: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `SentenceTransformerEmbedding` | `adapters/embedding/sentence_transformer.py` | Wraps existing `all-MiniLM-L12-v2` singleton. Thread-safe with retry logic. |
| `OpenAIEmbeddingAdapter` | (future) | Uses OpenAI's embedding API for higher-quality embeddings. |
| `FakeEmbeddingService` | `tests/fakes/` | Returns deterministic fake embeddings for testing. |

**Current code this replaces:**
- `embeddings/generate_embeddings.py` (the `generate_embedding` function)

---

### 2.3 EventPublisher

**Purpose:** Publish domain events so that side effects (change tracking, cache invalidation, notifications) can react without coupling to the domain.

**Defined in:** `domain/ontology/ports.py`

**Contract:**

```python
class EventPublisher(Protocol):
    """
    Publisher for domain events.

    Events are fire-and-forget from the domain's perspective.
    The publisher is responsible for routing events to all registered handlers.
    Handlers execute synchronously within the same transaction boundary
    (for the in-process implementation) or asynchronously (for message-based).
    """

    def publish(self, event: DomainEvent) -> None: ...
    def subscribe(self, event_type: type, handler: Callable) -> None: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `InProcessEventPublisher` | `adapters/events/in_process.py` | Simple observer pattern. Handlers execute synchronously. |
| `AsyncEventPublisher` | (future) | Uses asyncio queues for non-blocking event handling. |

**Current code this replaces:**
- `services/change_event_handler.py` (converted from direct calls to event subscription)

---

### 2.4 SchemaVectorIndex

**Purpose:** Semantic vector search over existing **schema** entities (classes, property definitions, relationships). Maintains the title/definition embeddings of schema entities (kept in sync on write) and searches them by a query embedding. Used by the extraction grounding flow to find which existing schema nodes and relation types an extracted phrase plausibly instantiates.

**Defined in:** `domain/ontology/ports.py`

**Contract:**

```python
@dataclass(frozen=True)
class SchemaMatch:
    entity_id: str
    kind: SchemaKind                     # "class" | "property_definition" | "relationship"
    label: str
    score: float                         # 0.0-1.0
    matched_field: MatchedField          # "title" | "definition"
    external_id: str | None = None       # e.g. DR spec node id "motivation.goal"
    predicate: str | None = None         # bare relation verb for property/relationship matches


class SchemaVectorIndex(Protocol):
    def index_entity(self, entity_id: str, title: str, description: str | None) -> None: ...
    def search(
        self,
        query_embedding: list[float],
        kinds: Sequence[SchemaKind],
        top_k: int = 20,
        threshold: float = 0.0,
        taxonomy_id: str | None = None,
    ) -> list[SchemaMatch]: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `SqliteSchemaVectorIndex` | `adapters/persistence/sqlite/schema_vector_index.py` | Brute-force numpy cosine over stored title/definition embeddings. `taxonomy_id` scoping lets multiple ontologies coexist without cross-contaminating grounding. |
| `FakeSchemaVectorIndex` | `tests/fakes/` | Deterministic matches for domain unit tests. |

**Current code this replaces:** New capability — no legacy equivalent.

---

### 2.5 IndividualVectorIndex

**Purpose:** Semantic vector search over existing graph **individuals** (instances) — the recognition counterpart to `SchemaVectorIndex`. Where schema search matches a specific instance to a *generic* class and is deliberately generous, recognition matches a specific extracted mention to a *specific* existing individual and is deliberately conservative (a high threshold plus an ambiguity margin guard against false merges). Backs `ExtractionService._recognize_individuals`, which resolves an extracted mention to an existing node so apply reuses that node rather than creating a duplicate. The index is kept in sync by the `IndividualCreated`/`Updated`/`Deleted` events.

**Defined in:** `domain/ontology/ports.py`

**Contract:**

```python
@dataclass(frozen=True)
class IndividualMatch:
    individual_id: str
    class_ids: list[str]                 # rdf:type memberships, for class-compatibility gating
    title: str                           # canonical title recognition adopts on resolve
    score: float                         # cosine 0.0-1.0


class IndividualVectorIndex(Protocol):
    def index_individual(self, individual_id: str, title: str, description: str | None) -> None: ...
    def remove_individual(self, individual_id: str) -> None: ...
    def reindex_all_individuals(self) -> int: ...
    def search(
        self,
        query_embedding: list[float],
        class_ids: Sequence[str],        # scope candidates to these classes; empty = unscoped
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[IndividualMatch]: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `SqliteIndividualVectorIndex` | `adapters/persistence/sqlite/individual_vector_index.py` | Class-scoped brute-force cosine over individual title embeddings. |
| `FakeIndividualVectorIndex` | `tests/fakes/fake_individual_vector_index.py` | Deterministic matches for domain unit tests. |

**Known limitation:** vector recognition resolves surface variants (casing/pluralization) but not abbreviation-aliases (e.g. `K8s`↔`Kubernetes`, embedding cosine ~0.39). Alias resolution is deferred to a future data-model alias registry (issue #1142).

**Current code this replaces:** New capability — no legacy equivalent.

---

## 3. Graph Analysis Context Ports

### 3.1 GraphEngine

**Purpose:** Graph computation — building graphs from data, running algorithms, extracting subgraphs.

**Defined in:** `domain/graph/ports.py`

**Contract:**

```python
class GraphEngine(Protocol):
    """
    Engine for graph computation.

    The engine maintains an internal graph representation.
    Call build_from_data to populate it, then use analysis methods.
    The engine does not persist anything — it's purely computational.
    """

    def build_from_data(
        self,
        nodes: Sequence[dict],      # [{id, title, node_type, ...}]
        edges: Sequence[dict],      # [{source_id, target_id, property_label, ...}]
    ) -> None: ...

    def node_count(self) -> int: ...
    def edge_count(self) -> int: ...

    def shortest_path(self, source_id: str, target_id: str) -> Optional[list[str]]: ...
    def all_paths(self, source_id: str, target_id: str, max_depth: int = 5) -> list[list[str]]: ...

    def centrality(self, algorithm: str = "betweenness") -> dict[str, float]: ...
    def degree_distribution(self) -> dict[str, int]: ...

    def communities(self, algorithm: str = "louvain") -> list[set[str]]: ...

    def subgraph(self, node_ids: Sequence[str]) -> "GraphEngine": ...
    def neighbors(self, node_id: str, depth: int = 1) -> set[str]: ...

    def has_cycle(self, source_id: str, target_id: str) -> bool: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `NetworkXGraphEngine` | `adapters/graph/networkx_engine.py` | Wraps existing NetworkX-based graph operations from `graph/network_service.py`. |

**Current code this replaces:**
- `graph/network_service.py`

---

### 3.2 SemanticQueryEngine

**Purpose:** Execute SPARQL and semantic queries against an RDF representation of the ontology.

**Defined in:** `domain/graph/ports.py`

**Contract:**

```python
class SemanticQueryEngine(Protocol):
    """
    Engine for semantic/SPARQL queries.

    Maintains an RDF graph representation that can be queried with SPARQL.
    The engine is lazy-loaded — the RDF graph is built on first query.
    """

    def load_ontology(
        self,
        nodes: Sequence[dict],
        edges: Sequence[dict],
        property_definitions: Sequence[dict],
    ) -> None: ...

    def execute_sparql(self, query: str) -> list[dict]: ...

    def get_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
    ) -> list[tuple[str, str, str]]: ...

    def is_loaded(self) -> bool: ...
    def triple_count(self) -> int: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `RDFLibQueryEngine` | `adapters/graph/rdflib_engine.py` | Wraps existing RDFLib SPARQL service from `graph/sparql_service.py`. |

**Current code this replaces:**
- `graph/sparql_service.py`

---

## 4. Knowledge Extraction Context Ports

### 4.1 LLMProvider

**Purpose:** Send prompts to a language model and receive completions. Shared across extraction and pipeline contexts.

**Defined in:** `domain/extraction/ports.py`

**Contract:**

```python
class LLMProvider(Protocol):
    """
    Provider for LLM inference.

    Implementations route to specific providers (OpenAI, Anthropic, etc.)
    based on the model identifier.
    """

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,  # "json", "text"
    ) -> LLMResponse: ...

    def is_model_available(self, model: str) -> bool: ...
    def list_available_models(self) -> list[str]: ...
```

```python
@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    finish_reason: str  # "stop", "length", "error"
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `OpenAIProvider` | `adapters/llm/openai_provider.py` | Handles GPT models. |
| `AnthropicProvider` | `adapters/llm/anthropic_provider.py` | Handles Claude models. |
| `LLMProviderRouter` | `adapters/llm/provider_router.py` | Routes to correct provider based on model name. Implements `LLMProvider` by delegating. |
| `FakeLLMProvider` | `tests/fakes/` | Returns canned responses for testing. |

**Current code this replaces:**
- `llm/service.py` (the `LLMService` class)
- Provider-specific logic in the current LLM module

---

### 4.2 NLPProcessor

**Purpose:** Process text through NLP pipelines for entity extraction, linguistic analysis, and gap detection.

**Defined in:** `domain/extraction/ports.py`

**Contract:**

```python
class NLPProcessor(Protocol):
    """
    Processor for NLP text analysis.

    Wraps a full NLP pipeline (tokenization, NER, entity linking, etc.)
    behind a simple interface.
    """

    def process(self, text: str) -> NLPResult: ...
    def extract_entities(self, text: str) -> list[NLPEntity]: ...
    def is_ready(self) -> bool: ...
```

```python
@dataclass
class NLPResult:
    entities: list[NLPEntity]
    tokens: list[str]
    noun_chunks: list[str]
    language: str

@dataclass
class NLPEntity:
    text: str
    label: str          # NER label (PERSON, ORG, CONCEPT, etc.)
    start: int
    end: int
    confidence: float
    linked_uri: Optional[str] = None  # DBpedia/ConceptNet URI if linked
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `SpacyNLPProcessor` | `adapters/nlp/spacy_processor.py` | Wraps existing spaCy pipeline with concepcy, dbpedia_spotlight, wordnet components. |

**Current code this replaces:**
- `nlp/pipeline.py` (the `NLPPipeline` class)
- `nlp/processor_models.py`

---

### 4.3 ReferenceSource

**Purpose:** Query external knowledge sources for concept enrichment.

**Defined in:** `domain/extraction/ports.py`

**Contract:**

```python
class ReferenceSource(Protocol):
    """
    A source of reference knowledge for concept enrichment.

    Each implementation wraps a specific external API (ConceptNet, DBpedia, etc.).
    The interface is intentionally simple — complex multi-source aggregation
    is handled by the domain service, not the adapter.
    """

    @property
    def source_name(self) -> str: ...

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]: ...
    def get_relations(self, uri: str, limit: int = 20) -> list[ReferenceRelation]: ...
    def is_available(self) -> bool: ...
```

```python
@dataclass
class ReferenceResult:
    uri: str
    label: str
    description: Optional[str]
    source: str
    confidence: float
    metadata: Optional[dict] = None

@dataclass
class ReferenceRelation:
    subject_uri: str
    predicate: str
    object_uri: str
    object_label: Optional[str]
    weight: Optional[float] = None
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `ConceptNetSource` | `adapters/reference/conceptnet.py` | ConceptNet API with caching. |
| `DBpediaSource` | `adapters/reference/dbpedia.py` | DBpedia Lookup + SPARQL + Spotlight. |
| `WikidataSource` | `adapters/reference/wikidata.py` | Wikidata SPARQL endpoint. |
| `SchemaOrgSource` | `adapters/reference/schema_org.py` | Schema.org vocabulary. |
| `CachedReferenceSource` | `adapters/reference/cache.py` | Decorator that adds caching to any ReferenceSource. Uses `reference_api_cache.db`. |

**Current code this replaces:**
- `reference_api/service.py` and all source-specific modules
- `reference_api/sources/`

---

## 5. Pipeline Context Ports

### 5.1 PipelineRepository

**Purpose:** Persist and retrieve LLM pipeline configurations and execution records.

**Defined in:** `domain/pipeline/ports.py`

**Contract:**

```python
class PipelineRepository(Protocol):
    """Repository for pipeline configurations and execution logs."""

    def get_config(self, config_id: str) -> Optional[PipelineConfiguration]: ...
    def list_configs(self, pipeline: Optional[str] = None, enabled_only: bool = False) -> Sequence[PipelineConfiguration]: ...
    def save_config(self, config: PipelineConfiguration) -> PipelineConfiguration: ...
    def delete_config(self, config_id: str) -> bool: ...

    def record_execution(self, execution: Execution) -> Execution: ...
    def get_executions(self, pipeline_config_id: str, limit: int = 50) -> Sequence[Execution]: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `SQLitePipelineRepository` | `adapters/persistence/sqlite/pipeline_repo.py` | Uses `operations.db` for storage. Maps `pipeline_configurations` and `pipeline_executions` tables. |

**Current code this replaces:**
- `llm/flavor_service.py` (formerly `PipelineFlavorService` — renamed to `PipelineConfiguration`)
- `llm/execution_tracker.py`

---

## 6. Versioning Context Ports

### 6.1 ChangeRepository

**Purpose:** Record and query change events and entity versions.

**Defined in:** `domain/versioning/ports.py`

**Contract:**

```python
class ChangeRepository(Protocol):
    """Repository for change events and entity version history."""

    def record_change(self, event: ChangeEvent) -> ChangeEvent: ...
    def get_changes(
        self,
        record_type: Optional[str] = None,
        record_id: Optional[str] = None,
        since: Optional[datetime] = None,
        processed: Optional[bool] = None,
        limit: int = 100,
    ) -> Sequence[ChangeEvent]: ...
    def mark_processed(self, event_ids: Sequence[int]) -> int: ...

    def save_version(self, version: EntityVersion) -> EntityVersion: ...
    def get_version(self, entity_id: str, version: int) -> Optional[EntityVersion]: ...
    def get_latest_version(self, entity_id: str) -> Optional[EntityVersion]: ...
    def list_versions(self, entity_id: str) -> Sequence[EntityVersion]: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `SQLiteChangeRepository` | `adapters/persistence/sqlite/change_repo.py` | Uses `change_events` table in `local.db`. |

**Current code this replaces:**
- Persistence parts of `services/version_manager.py`
- `services/change_event_handler.py` (the recording logic)

---

### 6.2 SyncTarget

**Purpose:** Push and pull changes to/from a remote synchronization target.

**Defined in:** `domain/versioning/ports.py`

**Contract:**

```python
class SyncTarget(Protocol):
    """Target for remote synchronization of changes."""

    def push_changes(self, changes: Sequence[ChangeEvent], metadata: dict) -> SyncResult: ...
    def pull_changes(self, since: datetime) -> Sequence[ChangeEvent]: ...
    def get_sync_status(self) -> SyncStatus: ...
```

```python
@dataclass
class SyncResult:
    success: bool
    changes_pushed: int
    remote_version: Optional[str]
    errors: list[str] = field(default_factory=list)

@dataclass
class SyncStatus:
    last_sync: Optional[datetime]
    pending_changes: int
    remote_reachable: bool
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `S3SyncAdapter` | `adapters/sync/s3_sync.py` | S3 + DuckDB/Parquet sync. Wraps existing `S3SyncManager`. |
| `LocalSyncAdapter` | (future) | For local backup/export. |

**Current code this replaces:**
- `services/s3_sync_manager.py`
- `services/incremental_sync_engine.py`

---

## 7. Admin Context Ports

### 7.1 ConfigurationStore

**Purpose:** Read and write application configuration.

**Defined in:** `domain/admin/ports.py`

**Contract:**

```python
class ConfigurationStore(Protocol):
    """Store for application configuration."""

    def get_config(self) -> AppConfiguration: ...
    def update_config(self, updates: dict) -> AppConfiguration: ...
    def reset_to_defaults(self) -> AppConfiguration: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `JSONFileConfigStore` | `adapters/config/json_store.py` | Reads/writes `config.json`. Wraps existing `config.py`. |

---

### 7.2 MetricsCollector

**Purpose:** Gather system-level metrics for health monitoring and performance tracking.

**Defined in:** `domain/admin/ports.py`

**Contract:**

```python
class MetricsCollector(Protocol):
    """Collects system and application metrics."""

    def get_database_health(self) -> dict: ...
    def get_service_metrics(self) -> dict: ...
    def get_embedding_model_status(self) -> dict: ...
    def get_nlp_pipeline_status(self) -> dict: ...
    def get_background_task_summary(self) -> dict: ...
```

**Adapters:**

| Adapter | Location | Notes |
|---|---|---|
| `SystemMetricsCollector` | `adapters/metrics/system_collector.py` | Aggregates metrics from SQLite, service factory stats, NLP/embedding status. Replaces current `PerformanceMonitor`. |

**Current code this replaces:**
- `services/performance_monitor.py`
- `api/admin/service_monitoring.py`
- `api/admin/database_monitoring.py`

---

### 7.3 Error Handling Pattern

Domain services raise domain-specific exceptions. The web adapter layer translates these to HTTP responses:

```python
# domain/ontology/exceptions.py
class OntologyError(Exception):
    """Base exception for ontology domain."""
    pass

class EntityNotFoundError(OntologyError):
    """Raised when a requested entity does not exist."""
    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} '{entity_id}' not found")

class CircularReferenceError(OntologyError):
    """Raised when a parent assignment would create a cycle."""
    pass

class DuplicateEntityError(OntologyError):
    """Raised when a uniqueness constraint would be violated."""
    pass
```

```python
# adapters/web/error_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse

async def ontology_error_handler(request: Request, exc: OntologyError):
    status_map = {
        EntityNotFoundError: 404,
        CircularReferenceError: 422,
        DuplicateEntityError: 409,
    }
    status = status_map.get(type(exc), 400)
    return JSONResponse(status_code=status, content={"detail": str(exc)})
```

This keeps error semantics in the domain and HTTP mapping in the adapter.

---

## 8. Migration Mapping: Current File → New Location

This table maps every significant current source file to its destination in the new architecture.

| Current File | New Location | Notes |
|---|---|---|
| `database/models.py` | `adapters/persistence/sqlite/models.py` | ORM models (adapter concern) |
| `database/utils.py` | `adapters/persistence/sqlite/connection.py` | Connection management |
| `database/enums.py` | `domain/ontology/value_objects.py` | NodeType, RecordType enums become domain value objects |
| `database/custom_types.py` | `adapters/persistence/sqlite/custom_types.py` | SQLAlchemy custom types |
| `database/migrations/` | `adapters/persistence/sqlite/migrations/` | Schema migrations |
| `services/node_service.py` | Split: `domain/ontology/services.py` (logic) + `adapters/persistence/sqlite/ontology_repo.py` (persistence) | Largest refactoring |
| `services/node_link_service.py` | Split: `domain/ontology/services.py` + `adapters/persistence/sqlite/ontology_repo.py` | Merged into ontology service |
| `services/change_event_handler.py` | `adapters/events/change_recorder.py` | Becomes an event subscriber |
| `services/version_manager.py` | Split: `domain/versioning/services.py` + `adapters/persistence/sqlite/change_repo.py` | |
| `services/working_tree_manager.py` | `domain/versioning/services.py` | Business logic stays in domain |
| `services/diff_generator.py` | `domain/versioning/services.py` | |
| `services/changeset_manager.py` | `domain/versioning/services.py` | |
| `services/proposal_manager.py` | `domain/versioning/services.py` | |
| `services/crdt_merge_engine.py` | `domain/versioning/services.py` | |
| `services/conflict_resolution_engine.py` | `domain/versioning/services.py` | |
| `services/incremental_sync_engine.py` | `adapters/sync/s3_sync.py` | Infrastructure concern |
| `services/s3_sync_manager.py` | `adapters/sync/s3_sync.py` | |
| `services/s3_storage_optimizer.py` | `adapters/sync/s3_optimizer.py` | |
| `services/duckdb_service.py` | `adapters/persistence/duckdb/analytics_repo.py` | |
| `services/duckdb_query_optimizer.py` | `adapters/persistence/duckdb/query_optimizer.py` | |
| `services/hierarchical_diff_engine.py` | `domain/versioning/services.py` | |
| `services/batch_operation_processor.py` | `domain/ontology/services.py` or `domain/versioning/services.py` | Depends on what it batches |
| `services/performance_monitor.py` | `domain/admin/services.py` + adapters | |
| `services/identity_manager.py` | `domain/versioning/services.py` | |
| `services/service_factory.py` | `app.py` (composition root) | Eliminated as a class |
| `services/service_registry.py` | `app.py` (composition root) | |
| `graph/graph_service.py` | `domain/graph/services.py` | Orchestration logic |
| `graph/network_service.py` | `adapters/graph/networkx_engine.py` | |
| `graph/sparql_service.py` | `adapters/graph/rdflib_engine.py` | |
| `nlp/pipeline.py` | `adapters/nlp/spacy_processor.py` | |
| `nlp/processor_models.py` | `domain/extraction/entities.py` (domain parts) + `adapters/nlp/spacy_processor.py` (spaCy parts) | |
| `nlp/model_downloader.py` | `adapters/nlp/model_downloader.py` | |
| `nlp/proxy_manager.py` | `adapters/reference/proxy_manager.py` | |
| `llm/service.py` | `adapters/llm/provider_router.py` | |
| `llm/flavor_service.py` (PipelineFlavorService → PipelineConfiguration) | `adapters/persistence/sqlite/pipeline_repo.py` | |
| `llm/execution_tracker.py` | `adapters/persistence/sqlite/pipeline_repo.py` | |
| `llm/provider_router.py` | `adapters/llm/provider_router.py` | |
| `llm/model_capabilities.py` | `adapters/llm/model_capabilities.py` | |
| `rag/pipeline_service.py` | `domain/extraction/services.py` | |
| `rag/standard_pipeline.py` | `domain/extraction/services.py` | |
| `rag/processors/` | Split across domain and adapters | |
| `rag/observability.py` | `adapters/metrics/` | |
| `reference_api/service.py` | `adapters/reference/` (split by source) | |
| `reference_api/sources/` | `adapters/reference/` | |
| `reference_api/cache.py` | `adapters/reference/cache.py` | |
| `reference_db/` | `adapters/persistence/sqlite/reference_repo.py` | |
| `embeddings/generate_embeddings.py` | `adapters/embedding/sentence_transformer.py` | |
| `config.py` | `adapters/config/json_store.py` + `config.py` (minimal bootstrap) | |
| `api/*.py` | `adapters/web/*.py` | Routes become thin adapters |
| `api/admin/*.py` | `adapters/web/admin_routes.py` | |

---

## 9. Dependency Injection Wiring

The composition root in `app.py` replaces the `ServiceFactory`. Here's the complete wiring:

```python
# app.py — composition root (conceptual)

async def lifespan(app: FastAPI):
    config = load_config()

    # --- Driven Adapters ---

    # Persistence
    db_engine = create_sqlite_engine(config.database)
    run_migrations(db_engine)
    ontology_repo = SQLiteOntologyRepository(db_engine)
    change_repo = SQLiteChangeRepository(db_engine)
    pipeline_repo = SQLitePipelineRepository(config.operations_db_path)

    # Embedding
    embedding_svc = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")

    # LLM
    openai = OpenAIProvider(config.llm.openai_api_key)
    anthropic = AnthropicProvider(config.llm.anthropic_api_key)
    llm_provider = LLMProviderRouter(providers=[openai, anthropic])

    # NLP
    nlp_processor = SpacyNLPProcessor(model="en_core_web_sm")

    # Reference sources
    conceptnet = CachedReferenceSource(ConceptNetSource(), cache_db=config.reference_cache_db)
    dbpedia = CachedReferenceSource(DBpediaSource(), cache_db=config.reference_cache_db)
    wikidata = CachedReferenceSource(WikidataSource(), cache_db=config.reference_cache_db)
    reference_sources = [conceptnet, dbpedia, wikidata]

    # Graph engines
    graph_engine = NetworkXGraphEngine()
    query_engine = RDFLibQueryEngine()

    # Events
    event_publisher = InProcessEventPublisher()

    # Sync
    sync_target = S3SyncAdapter(config.sync)

    # --- Domain Services ---

    ontology_service = OntologyService(
        repository=ontology_repo,
        embedding=embedding_svc,
        events=event_publisher,
    )

    graph_service = GraphAnalysisService(
        repository=ontology_repo,
        graph_engine=graph_engine,
        query_engine=query_engine,
    )

    extraction_service = ExtractionService(
        llm=llm_provider,
        nlp=nlp_processor,
        reference_sources=reference_sources,
        ontology_repo=ontology_repo,
    )

    pipeline_service = PipelineService(
        repository=pipeline_repo,
        llm=llm_provider,
    )

    versioning_service = VersioningService(
        change_repo=change_repo,
        sync_target=sync_target,
    )

    # --- Event Subscriptions ---

    change_recorder = ChangeEventRecorder(change_repo)
    event_publisher.subscribe(ClassCreated, change_recorder.on_class_created)
    event_publisher.subscribe(ClassUpdated, change_recorder.on_class_updated)
    event_publisher.subscribe(ClassDeleted, change_recorder.on_class_deleted)
    # ... more subscriptions

    graph_invalidator = GraphCacheInvalidator(graph_service)
    event_publisher.subscribe(ClassCreated, graph_invalidator.invalidate)
    event_publisher.subscribe(RelationshipCreated, graph_invalidator.invalidate)

    # --- Store on app.state ---

    app.state.ontology_service = ontology_service
    app.state.graph_service = graph_service
    app.state.extraction_service = extraction_service
    app.state.pipeline_service = pipeline_service
    app.state.versioning_service = versioning_service

    yield

    # Cleanup
    db_engine.dispose()
    embedding_svc.cleanup()
```

### FastAPI Dependencies

```python
# adapters/web/dependencies.py

from fastapi import Request

def get_ontology_service(request: Request) -> OntologyService:
    return request.app.state.ontology_service

def get_graph_service(request: Request) -> GraphAnalysisService:
    return request.app.state.graph_service

def get_extraction_service(request: Request) -> ExtractionService:
    return request.app.state.extraction_service
```

### Route Handlers

```python
# adapters/web/ontology_routes.py

from fastapi import APIRouter, Depends
from adapters.web.dependencies import get_ontology_service
from adapters.web.schemas import ClassCreateRequest, ClassResponse

router = APIRouter(prefix="/api/classes", tags=["classes"])

@router.post("/", response_model=ClassResponse)
async def create_class(
    request: ClassCreateRequest,
    service: OntologyService = Depends(get_ontology_service),
):
    cls = service.create_class(
        title=request.title,
        scheme_id=request.concept_scheme_id,
        definition=request.definition,
        parent_class_id=request.parent_class_id,
    )
    return ClassResponse.from_domain(cls)
```

This wiring pattern makes the dependency graph explicit and visible in one place, replacing the scattered creation logic in the current `ServiceFactory`.

---

## 10. Session Management Note

One important distinction from the current architecture: the current `ServiceFactory` creates a new service instance per request because services hold a reference to the SQLAlchemy `Session`. In the hexagonal architecture, the `OntologyRepository` adapter manages its own session lifecycle.

Two approaches:

**Option A: Session-per-request (current pattern)**
The repository adapter receives a session factory and creates a new session per method call or per unit-of-work.

**Option B: Unit of Work pattern**
Introduce a `UnitOfWork` port that wraps a transaction boundary. The domain service receives a UoW, uses it to get repositories, and commits at the end.

```python
class UnitOfWork(Protocol):
    ontology: OntologyRepository
    changes: ChangeRepository

    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

**Recommendation:** Start with Option A (simpler) and introduce UoW if cross-repository transactions become needed. The current system uses single-entity operations that fit well with session-per-method.
