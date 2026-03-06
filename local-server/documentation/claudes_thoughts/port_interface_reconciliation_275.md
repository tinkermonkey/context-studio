# Port Interface Specifications Reconciliation - Issue #275

**Date:** 2026-03-06
**Issue:** [PR Feedback] Port Interface Specifications
**Status:** Complete

---

## Executive Summary

All 8 port interface definitions in the domain layer have been reconciled with the canonical specification in `/workspace/rearchitecture/port_and_adapter_specs.md`. The port interfaces now accurately represent the system's hexagonal architecture contracts and serve as the definitive interface between domain logic and infrastructure adapters.

### Files Modified
- `domain/graph/ports.py` - GraphEngine port
- `domain/extraction/ports.py` - LLMProvider, ReferenceSource, dataclasses
- `domain/ontology/ports.py` - OntologyRepository port
- `domain/versioning/ports.py` - ChangeRepository port
- `domain/admin/ports.py` - ConfigurationStore, MetricsCollector ports
- `domain/pipeline/ports.py` - PipelineRepository port

**Total Changes:** 210 insertions, 54 deletions across 6 files

---

## Detailed Port-by-Port Analysis

### 1. GraphEngine Port (domain/graph/ports.py)

**Previous Design (Taxonomy-Scoped)**
```python
class GraphEngine(Protocol):
    def build_graph(self, taxonomy_id: str) -> KnowledgeGraph: ...
    def find_path(self, source_id: str, target_id: str, taxonomy_id: str) -> Optional[PathResult]: ...
    def get_metrics(self, taxonomy_id: str) -> GraphMetrics: ...
    def invalidate(self, taxonomy_id: str) -> None: ...
```

**Issues:**
- Assumes taxonomy concept exists (not yet implemented)
- Generic methods named find_path and get_metrics obscure actual capabilities
- No graph structure introspection methods
- No algorithm flexibility

**New Design (Data-Driven)**
```python
class GraphEngine(Protocol):
    def build_from_data(self, nodes: Sequence[dict], edges: Sequence[dict]) -> None: ...
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

**Benefits:**
- Decoupled from domain entity types
- Flexible algorithm selection
- Complete graph analysis toolkit
- Stateless computation model
- Enables composition of graph operations

**Adapter Impact:**
NetworkXGraphEngine adapter must now implement all analysis methods instead of taxonomy-scoped wrappers.

---

### 2. LLMProvider Port (domain/extraction/ports.py)

**Previous Design**
```python
class LLMProvider(Protocol):
    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse: ...
    def embed(self, text: str) -> List[float]: ...
```

**Issues:**
- Conflates text completion with embedding generation
- No model selection mechanism
- Minimal response metadata (only content, model, token_count)
- Parameter management unclear

**New Design**
```python
@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    finish_reason: str  # "stop", "length", "error"
    raw_response: dict = field(default_factory=dict)

class LLMProvider(Protocol):
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

**Benefits:**
- Separate completion and embedding into different concerns
- Full control over model selection and parameters
- Comprehensive response diagnostics (input/output tokens, duration, finish reason)
- Model availability checking
- Supports structured output formats

**Breaking Changes:**
- `embed()` removed (embeddings now handled by separate EmbeddingService in OntologyRepository)
- Parameter order changed (system before user)
- Explicit model parameter required for routing

**Adapter Impact:**
All LLM providers (OpenAI, Anthropic, etc.) must update their complete() signature and return full diagnostic metadata.

---

### 3. ReferenceSource Port (domain/extraction/ports.py)

**Previous Design**
```python
class ReferenceSource(Protocol):
    def lookup(self, term: str) -> Optional[ReferenceResult]: ...
    def search(self, query: str, limit: int = 10) -> List[ReferenceResult]: ...
```

**Issues:**
- No source identification for result aggregation
- No relationship discovery
- No availability checking
- No quality/confidence metrics
- Result metadata inconsistent

**New Design**
```python
@dataclass
class ReferenceResult:
    uri: str
    label: str
    description: Optional[str]
    source: str                    # NEW
    confidence: float              # NEW
    metadata: Optional[dict] = None

@dataclass
class ReferenceRelation:
    subject_uri: str
    predicate: str
    object_uri: str
    object_label: Optional[str] = None
    weight: Optional[float] = None

class ReferenceSource(Protocol):
    @property
    def source_name(self) -> str: ...  # NEW

    def search(self, term: str, limit: int = 10) -> list[ReferenceResult]: ...
    def get_relations(self, uri: str, limit: int = 20) -> list[ReferenceRelation]: ...  # NEW
    def is_available(self) -> bool: ...  # NEW
```

**Benefits:**
- Source identification enables proper attribution
- Confidence scores allow filtering by quality
- Relationship discovery enables semantic enrichment
- Availability checking enables graceful degradation
- Standardized metadata structure

**Breaking Changes:**
- `lookup()` removed (search with limit=1 instead)
- Must implement `source_name` property
- Must implement `get_relations()`
- Must implement `is_available()`

**Adapter Impact:**
ConceptNet, DBpedia, Wikidata, Schema.org adapters must implement relation discovery and availability checking.

---

### 4. OntologyRepository Port (domain/ontology/ports.py)

**Previous Design**
```python
def list_classes(self, scheme_id: str) -> Sequence[Class]: ...
def get_property_definition(self, property_id: str) -> Optional[PropertyDefinition]: ...
def list_property_definitions(self) -> Sequence[PropertyDefinition]: ...
# Missing: count, query, bulk methods
```

**Issues:**
- list_classes() lacks pagination and hierarchy filtering
- No count() method for UI pagination
- No by-identifier lookup for property definitions
- No bulk entity retrieval
- No Individual operations

**New Design**
```python
def list_classes(
    self,
    scheme_id: Optional[str] = None,
    parent_class_id: Optional[str] = None,  # NEW
    limit: int = 100,                       # NEW
    offset: int = 0,                        # NEW
) -> Sequence[Class]: ...

def count_classes(self, scheme_id: Optional[str] = None) -> int: ...  # NEW
def get_property_definition_by_identifier(self, identifier: str) -> Optional[PropertyDefinition]: ...  # NEW
def list_property_definitions(self, is_relevant: Optional[bool] = None) -> Sequence[PropertyDefinition]: ...  # Enhanced
def list_individuals(self, class_id: Optional[str] = None) -> Sequence[Individual]: ...  # NEW (future)
def delete_individual(self, individual_id: str) -> bool: ...  # NEW (future)
def get_all_entities_and_relationships(self) -> tuple[Sequence, Sequence[Relationship]]: ...  # NEW
```

**Benefits:**
- Pagination support for large concept schemes
- Hierarchy navigation without fetching entire scheme
- Count method enables lazy UI pagination
- Property lookup by identifier simplifies configuration
- Bulk entity export for graph operations
- Future-proofs Individual operations

**Adapter Impact:**
SQLiteOntologyRepository must support pagination, hierarchical filtering, and bulk export. Future Individual support reserved but must raise NotImplementedError.

---

### 5. ChangeRepository Port (domain/versioning/ports.py)

**Previous Design**
```python
def record_change(self, event: ChangeEvent) -> ChangeEvent: ...
def list_changes(self, since: Optional[str] = None) -> Sequence[ChangeEvent]: ...
def get_change(self, event_id: str) -> Optional[ChangeEvent]: ...
```

**Issues:**
- No event processing state tracking
- No version snapshots
- No record filtering
- No change state management
- No version query interface

**New Design**
```python
@dataclass
class EntityVersion:
    entity_id: str
    version: int
    state: dict
    created_at: datetime

class ChangeRepository(Protocol):
    def record_change(self, event: ChangeEvent) -> ChangeEvent: ...

    def get_changes(
        self,
        record_type: Optional[str] = None,      # NEW
        record_id: Optional[str] = None,        # NEW
        since: Optional[datetime] = None,       # Enhanced type
        processed: Optional[bool] = None,       # NEW
        limit: int = 100,                       # NEW
    ) -> Sequence[ChangeEvent]: ...

    def mark_processed(self, event_ids: Sequence[int]) -> int: ...  # NEW

    def save_version(self, version: EntityVersion) -> EntityVersion: ...  # NEW
    def get_version(self, entity_id: str, version: int) -> Optional[EntityVersion]: ...  # NEW
    def get_latest_version(self, entity_id: str) -> Optional[EntityVersion]: ...  # NEW
    def list_versions(self, entity_id: str) -> Sequence[EntityVersion]: ...  # NEW
```

**Benefits:**
- Processing state enables idempotent event consumers
- Version snapshots enable time-travel queries
- Rich filtering supports audit log queries
- Separate version storage enables fast revert operations
- Multi-dimensional change tracking

**Adapter Impact:**
SQLiteChangeRepository must implement processed flag tracking, version snapshots in separate table, and multi-filter queries.

---

### 6. ConfigurationStore Port (domain/admin/ports.py)

**Previous Design**
```python
class ConfigurationStore(Protocol):
    def load(self) -> AppConfiguration: ...
    def save(self, config: AppConfiguration) -> None: ...
```

**Issues:**
- Full replacement semantics lose partial update capability
- No defaults reset mechanism
- No update semantics distinction

**New Design**
```python
class ConfigurationStore(Protocol):
    def get_config(self) -> AppConfiguration: ...
    def update_config(self, updates: dict) -> AppConfiguration: ...  # Partial update
    def reset_to_defaults(self) -> AppConfiguration: ...  # New
```

**Benefits:**
- Explicit read operation (get vs load)
- Partial updates prevent accidental field loss
- Reset capability for configuration repair
- Clearer intent in client code

**Adapter Impact:**
JSONFileConfigStore must implement partial update merging and defaults reset without full file replacement.

---

### 7. MetricsCollector Port (domain/admin/ports.py)

**Previous Design**
```python
class MetricsCollector(Protocol):
    def record_latency(self, operation: str, duration_ms: float) -> None: ...
    def get_health(self) -> SystemHealth: ...
```

**Issues:**
- Only latency recording (incomplete metrics)
- Generic health status insufficient for multi-layer system
- No visibility into service dependencies
- No background task tracking
- No embedding/NLP model status

**New Design**
```python
class MetricsCollector(Protocol):
    def get_database_health(self) -> dict: ...                  # Size, query perf, index stats
    def get_service_metrics(self) -> dict: ...                  # Request counts, latencies
    def get_embedding_model_status(self) -> dict: ...           # Model, throughput, cache
    def get_nlp_pipeline_status(self) -> dict: ...              # Model, latency, throughput
    def get_background_task_summary(self) -> dict: ...          # Queue depth, execution times
```

**Benefits:**
- Multi-dimensional health assessment
- Per-component status visibility
- Enables targeted performance optimization
- Supports dependency-aware monitoring
- Complete observability stack

**Adapter Impact:**
SystemMetricsCollector must aggregate metrics from:
- SQLite database (size, performance)
- Service layer (request metrics, latencies)
- Embedding service (model, throughput, cache)
- NLP pipeline (model, performance)
- Background task queue (depth, timing)

---

### 8. PipelineRepository Port (domain/pipeline/ports.py)

**Previous Design**
```python
class PipelineRepository(Protocol):
    def get_configuration(self, pipeline_id: str) -> Optional[PipelineConfiguration]: ...
    def list_configurations(self) -> Sequence[PipelineConfiguration]: ...
    def save_configuration(self, config: PipelineConfiguration) -> PipelineConfiguration: ...
    def record_execution(self, execution: Execution) -> Execution: ...
    def get_execution(self, execution_id: str) -> Optional[Execution]: ...
```

**Issues:**
- Method names inconsistent (get_configuration vs record_execution)
- No filtering on list_configurations()
- No delete capability
- Single execution retrieval instead of history

**New Design**
```python
class PipelineRepository(Protocol):
    def get_config(self, config_id: str) -> Optional[PipelineConfiguration]: ...

    def list_configs(
        self,
        pipeline: Optional[str] = None,    # Filter by pipeline type
        enabled_only: bool = False,        # Filter by enabled status
    ) -> Sequence[PipelineConfiguration]: ...

    def save_config(self, config: PipelineConfiguration) -> PipelineConfiguration: ...
    def delete_config(self, config_id: str) -> bool: ...  # NEW

    def record_execution(self, execution: Execution) -> Execution: ...
    def get_executions(self, pipeline_config_id: str, limit: int = 50) -> Sequence[Execution]: ...  # NEW
```

**Benefits:**
- Consistent method naming (config not configuration)
- Filtering enables UI pagination and filtering
- Delete capability enables configuration cleanup
- Execution history retrieval supports audit and optimization

**Breaking Changes:**
- `get_configuration()` → `get_config()`
- `list_configurations()` → `list_configs()` with filtering parameters
- `save_configuration()` → `save_config()`
- `get_execution()` → `get_executions()` returning Sequence

**Adapter Impact:**
SQLitePipelineRepository must support configuration filtering and return execution history instead of single record.

---

## Design Principles Applied

### 1. **Separation of Concerns**
- Embedding service separated from LLM provider
- Configuration updates separate from persistence
- Metrics collection separated by subsystem

### 2. **Explicit Over Implicit**
- Model selection explicit in LLMProvider.complete()
- Update semantics explicit in ConfigurationStore
- Change filtering explicit in ChangeRepository.get_changes()

### 3. **Stateless Operations**
- GraphEngine builds from data rather than maintaining internal state
- No assumption of prior graph loads
- Composable operations

### 4. **Query Flexibility**
- Optional filtering parameters with sensible defaults
- Pagination support (limit, offset)
- Multi-dimensional filtering (record_type, record_id, processed)

### 5. **Observability**
- Full response diagnostics (tokens, duration, finish_reason)
- Comprehensive metrics collection
- Change processing state tracking
- Availability checking for external services

---

## Migration Path for Adapters

### Priority 1 (Critical)
1. **LLMProvider** - Multiple providers depend on this
2. **PipelineRepository** - Core execution tracking
3. **GraphEngine** - Foundation for analysis features

### Priority 2 (High)
4. **ChangeRepository** - Version tracking and audit
5. **OntologyRepository** - Bulk operations, pagination
6. **ReferenceSource** - Relationship discovery

### Priority 3 (Standard)
7. **ConfigurationStore** - Partial updates
8. **MetricsCollector** - Comprehensive health

### Adapter Updates Required
Each adapter must:
1. Update method signatures to match new port
2. Implement new methods with correct semantics
3. Update response objects with new fields
4. Add filtering and pagination support where applicable
5. Update unit tests for new behavior

---

## Testing Implications

### Unit Test Updates
- Mock implementations must match new port signatures
- Stub responses must include all required fields
- Filtering behavior must be tested

### Integration Test Updates
- API routes using ports must update parameter passing
- Response parsing must handle new fields
- Filtering and pagination must be tested end-to-end

### Adapter Tests
- Each adapter must test new methods
- Edge cases for filtering and pagination
- Availability checking and error handling

---

## Conclusion

The port interface reconciliation ensures the domain layer accurately represents the system's hexagonal architecture. By aligning all 8 ports with the canonical specification, we:

1. **Establish clear contracts** between domain and infrastructure layers
2. **Enable multiple adapter implementations** without coupling
3. **Support future extensibility** (e.g., Individual operations)
4. **Improve observability** through comprehensive metrics
5. **Simplify integration testing** with clearer interfaces

All changes are specification corrections — they don't alter system behavior but make the existing capabilities and constraints explicit in the domain layer contracts.
