# Context Studio Back-End Architecture Design

## Hexagonal Architecture with Domain-Driven Design

**Date:** 2026-03-01
**Status:** Proposed
**Scope:** Back-end (`/local-server`) re-architecture

---

## 1. Motivation

Context Studio has grown organically into a capable knowledge graph platform, but the current codebase suffers from three structural problems that limit velocity and flexibility:

1. **Inconsistent terminology.** The domain layer uses ad-hoc names (`StructureNode`, `node_type=layer|domain|term`, `StructureNodeLink`) rather than industry-standard ontology terms. This creates a translation burden for anyone familiar with OWL/RDF/SKOS and makes integration with external tooling harder than it should be.

2. **Blurred boundaries.** Business logic, persistence concerns, and external API calls are intermixed. Services like `NodeService` directly import SQLAlchemy models and issue queries, while API route handlers sometimes contain business rules. This makes it difficult to test domain logic in isolation or swap infrastructure components.

3. **Monolithic service factory.** The `ServiceFactory` has become a god-object that knows about every service in the system. Adding a new capability requires touching multiple unrelated files, and the flat `services/` directory makes it hard to reason about module boundaries.

The re-architecture addresses all three by adopting a **hexagonal (ports & adapters) architecture** organized around **bounded contexts** with **standardized ontology terminology**.

---

## 2. Terminology Alignment

The single most impactful change is adopting standard knowledge representation terminology throughout the codebase. This table maps current names to their replacements:

| Current Term | New Term | Standard Basis | Notes |
|---|---|---|---|
| `StructureNode` (node_type=layer) | `Taxonomy` | Organizational grouping | Top-level container for a classification hierarchy |
| `StructureNode` (node_type=domain) | `ConceptScheme` | SKOS:ConceptScheme | A coherent group of concepts within a taxonomy |
| `StructureNode` (node_type=term) | `Class` | OWL:Class / rdfs:Class | A concept in the ontology that can be instantiated |
| (not yet implemented) | `Individual` | OWL:NamedIndividual | A concrete instance of a Class |
| `StructureNodeLink` | `Relationship` | — | A directed, typed edge between two nodes |
| `predicate` (on links) | `ObjectProperty` | OWL:ObjectProperty | The type/label of a relationship between entities |
| `Predicate` (table) | `PropertyDefinition` | OWL:ObjectProperty | The registry of defined object properties. Named `PropertyDefinition` (not `ObjectProperty`) because it's a *definition record*, not the property itself. Corresponds to OWL's `ObjectProperty` concept. |
| `attributes` (JSON on node) | `DataPropertyValue` | OWL:DatatypeProperty | Literal-valued attributes on a class or individual (already stored as JSON; formalized as value object) |
| `ChangeEvent` | `ChangeEvent` | (no change) | Already clear |
| `PipelineFlavor` | `PipelineConfiguration` | — | Clearer name; "flavor" is informal |
| `reference_links` (JSON) | `ExternalReference` | — | Links to external knowledge sources |
| `word_senses` (JSON) | `LexicalSense` | — | WordNet/lexical disambiguation data |

### Hierarchy Relationships

| Current Pattern | New Term | Standard |
|---|---|---|
| Layer → Domain (parent_node_id) | Taxonomy → ConceptScheme containment | Organizational |
| Domain → Term (parent_node_id) | ConceptScheme → Class membership | SKOS:inScheme-like |
| Term → Term (parent_node_id) | Class → Class subclass hierarchy | rdfs:subClassOf |
| (future) Class → Individual | Instantiation | rdf:type |

---

## 3. Hexagonal Architecture Overview

```
                    ┌─────────────────────────────────────┐
                    │          Driving Adapters            │
                    │  (FastAPI routes, CLI, WebSocket)    │
                    └──────────────┬──────────────────────┘
                                   │
                          ╔════════╧═════════╗
                          ║   Driving Ports   ║
                          ║   (Use Cases /    ║
                          ║    Commands /     ║
                          ║    Queries)       ║
                          ╚════════╤═════════╝
                                   │
                    ┌──────────────┴──────────────────────┐
                    │                                      │
                    │          DOMAIN CORE                 │
                    │                                      │
                    │   ┌────────────────────────────┐    │
                    │   │     Domain Entities         │    │
                    │   │  (Class, Individual,        │    │
                    │   │   ObjectProperty, etc.)     │    │
                    │   └────────────────────────────┘    │
                    │                                      │
                    │   ┌────────────────────────────┐    │
                    │   │     Domain Services         │    │
                    │   │  (OntologyService,          │    │
                    │   │   GraphAnalysisService,     │    │
                    │   │   VersioningService)        │    │
                    │   └────────────────────────────┘    │
                    │                                      │
                    │   ┌────────────────────────────┐    │
                    │   │     Domain Events           │    │
                    │   │  (ClassCreated,             │    │
                    │   │   RelationshipChanged, ...) │    │
                    │   └────────────────────────────┘    │
                    │                                      │
                    └──────────────┬──────────────────────┘
                                   │
                          ╔════════╧═════════╗
                          ║  Driven Ports     ║
                          ║  (Repository,     ║
                          ║   Embedding,      ║
                          ║   LLM, Reference  ║
                          ║   interfaces)     ║
                          ╚════════╤═════════╝
                                   │
                    ┌──────────────┴──────────────────────┐
                    │          Driven Adapters             │
                    │  (SQLite repos, SentenceTransformer, │
                    │   OpenAI/Anthropic clients,          │
                    │   ConceptNet/DBpedia/Wikidata)       │
                    └─────────────────────────────────────┘
```

### Key Principle: Dependency Rule

All dependencies point inward. The domain core has **zero imports** from infrastructure, framework, or adapter code. It depends only on Python standard library and its own port interfaces (defined as abstract base classes or Protocols).

---

## 4. Bounded Contexts

The system decomposes into six bounded contexts. Each context owns its domain entities, ports, and use cases. Cross-context communication happens through well-defined interfaces, never by reaching into another context's internals.

### 4.1 Ontology Management (Core)

**Responsibility:** CRUD and validation for the knowledge graph schema—taxonomies, concept schemes, classes, individuals, property definitions, and relationships.

**Domain Entities:**
- `Taxonomy` — top-level organizational container
- `ConceptScheme` — a coherent grouping of classes
- `Class` — an ontology concept (the "term" replacement)
- `Individual` — a concrete instance of a class (future)
- `PropertyDefinition` — a defined relationship type (object property)
- `DataPropertyDefinition` — a defined attribute type (data property, future)
- `Relationship` — a typed, directed edge between two entities
- `ExternalReference` — a link to an external knowledge source
- `LexicalSense` — word sense disambiguation data

**Driving Ports (Use Cases):**
- `CreateClass`, `UpdateClass`, `DeleteClass`, `GetClass`, `SearchClasses`
- `CreateRelationship`, `UpdateRelationship`, `DeleteRelationship`
- `ManagePropertyDefinitions` (CRUD for object properties)
- `ManageTaxonomies`, `ManageConceptSchemes`
- `LinkExternalReference`, `ResolveLexicalSense`

**Driven Ports:**
- `OntologyRepository` — persistence of all ontology entities
- `EmbeddingService` — generate vector embeddings for search
- `EventPublisher` — emit domain events

### 4.2 Graph Analysis

**Responsibility:** In-memory graph construction, traversal, metrics, SPARQL queries, and network analysis.

**Domain Entities:**
- `KnowledgeGraph` — the in-memory graph representation
- `GraphMetrics` — centrality, density, community results
- `PathResult`, `SubgraphResult`

**Driving Ports:**
- `BuildGraph`, `QueryGraph`, `AnalyzeNetwork`, `ExecuteSPARQL`

**Driven Ports:**
- `OntologyRepository` — read ontology data to build the graph
- `GraphEngine` — abstraction over NetworkX
- `SemanticQueryEngine` — abstraction over RDFLib

### 4.3 Knowledge Extraction (RAG + NLP)

**Responsibility:** Extract entities from text using the RAG pipeline, NLP processing, and external knowledge enrichment.

**Domain Entities:**
- `ExtractionResult` — entities extracted from text
- `ExtractionLayer` — one stage of the pipeline
- `ProcessingMetrics`

**Driving Ports:**
- `ExtractEntities`, `AnalyzeText`, `EnrichFromReferences`

**Driven Ports:**
- `LLMProvider` — abstraction over OpenAI/Anthropic/etc.
- `NLPProcessor` — abstraction over spaCy pipeline
- `ReferenceSource` — abstraction over ConceptNet/DBpedia/Wikidata
- `OntologyRepository` — read existing KG for context

### 4.4 LLM Pipeline Management

**Responsibility:** Configuration and execution of LLM-powered processing pipelines.

**Domain Entities:**
- `PipelineConfiguration` — replaces `PipelineFlavor`
- `Execution` — a traced LLM call with inputs/outputs/metrics

**Driving Ports:**
- `ManagePipelines` (CRUD)
- `ExecutePipeline`, `TraceExecution`

**Driven Ports:**
- `PipelineRepository` — persistence for configurations and execution logs
- `LLMProvider` — the actual LLM call interface

### 4.5 Version Control & Collaboration

**Responsibility:** Change tracking, versioning, changesets, proposals, conflict resolution, and sync.

**Domain Entities:**
- `ChangeEvent` — an atomic change record
- `EntityVersion`, `ChangeState`
- `Changeset`, `Proposal`
- `ConflictReport`, `MergeResult`

**Driving Ports:**
- `TrackChanges`, `ManageVersions`
- `CreateChangeset`, `SubmitProposal`, `ResolveConflicts`
- `SyncWorkspace`

**Driven Ports:**
- `ChangeRepository` — persistence for change events and versions
- `SyncTarget` — abstraction over S3/DuckDB sync
- `OntologyRepository` — read current state for diff computation

### 4.6 System Administration

**Responsibility:** Health monitoring, configuration management, background tasks, database management.

**Domain Entities:**
- `SystemHealth`, `ServiceMetrics`
- `BackgroundTask`
- `AppConfiguration`

**Driving Ports:**
- `CheckHealth`, `GetMetrics`
- `ManageBackgroundTasks`
- `ManageConfiguration`

**Driven Ports:**
- `ConfigurationStore` — persistence for config
- `MetricsCollector` — system metrics gathering

---

## 5. Target Directory Structure

```
local-server/
├── app.py                          # FastAPI app setup, lifespan, adapter wiring
├── config.py                       # Configuration loading (infrastructure concern)
├── ports.py                        # Shared port interfaces (or per-context)
│
├── domain/                         # THE CORE — no infrastructure imports
│   ├── __init__.py
│   │
│   ├── ontology/                   # Bounded context: Ontology Management
│   │   ├── __init__.py
│   │   ├── entities.py             # Class, Taxonomy, ConceptScheme, Individual, etc.
│   │   ├── value_objects.py        # ExternalReference, LexicalSense, NodeType enum
│   │   ├── services.py             # OntologyService (business rules, validation)
│   │   ├── events.py               # ClassCreated, RelationshipChanged, etc.
│   │   └── ports.py                # OntologyRepository, EmbeddingService, EventPublisher
│   │
│   ├── graph/                      # Bounded context: Graph Analysis
│   │   ├── __init__.py
│   │   ├── entities.py             # KnowledgeGraph, GraphMetrics
│   │   ├── services.py             # GraphAnalysisService
│   │   └── ports.py                # GraphEngine, SemanticQueryEngine
│   │
│   ├── extraction/                 # Bounded context: Knowledge Extraction
│   │   ├── __init__.py
│   │   ├── entities.py             # ExtractionResult, ExtractionLayer
│   │   ├── services.py             # ExtractionService
│   │   └── ports.py                # LLMProvider, NLPProcessor, ReferenceSource
│   │
│   ├── pipeline/                   # Bounded context: LLM Pipeline Management
│   │   ├── __init__.py
│   │   ├── entities.py             # PipelineConfiguration, Execution
│   │   ├── services.py             # PipelineService
│   │   └── ports.py                # PipelineRepository, LLMProvider
│   │
│   ├── versioning/                 # Bounded context: Version Control & Collaboration
│   │   ├── __init__.py
│   │   ├── entities.py             # ChangeEvent, EntityVersion, Changeset, Proposal
│   │   ├── services.py             # VersioningService, ConflictResolver
│   │   └── ports.py                # ChangeRepository, SyncTarget
│   │
│   └── admin/                      # Bounded context: System Administration
│       ├── __init__.py
│       ├── entities.py             # SystemHealth, BackgroundTask
│       ├── services.py             # AdminService
│       └── ports.py                # ConfigurationStore, MetricsCollector
│
├── adapters/                       # Infrastructure implementations
│   ├── __init__.py
│   │
│   ├── persistence/                # Driven: Database adapters
│   │   ├── __init__.py
│   │   ├── sqlite/
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # SQLAlchemy ORM models
│   │   │   ├── ontology_repo.py    # Implements OntologyRepository
│   │   │   ├── change_repo.py      # Implements ChangeRepository
│   │   │   ├── pipeline_repo.py    # Implements PipelineRepository
│   │   │   ├── connection.py       # Connection management, pooling
│   │   │   └── migrations/         # Schema migrations
│   │   │       ├── manager.py
│   │   │       └── versions/
│   │   └── duckdb/
│   │       ├── __init__.py
│   │       └── analytics_repo.py   # DuckDB-based analytics queries
│   │
│   ├── embedding/                  # Driven: Embedding generation
│   │   ├── __init__.py
│   │   └── sentence_transformer.py # Implements EmbeddingService
│   │
│   ├── llm/                        # Driven: LLM providers
│   │   ├── __init__.py
│   │   ├── openai_provider.py      # Implements LLMProvider for OpenAI
│   │   ├── anthropic_provider.py   # Implements LLMProvider for Anthropic
│   │   └── provider_router.py      # Routes to correct provider
│   │
│   ├── nlp/                        # Driven: NLP processing
│   │   ├── __init__.py
│   │   └── spacy_processor.py      # Implements NLPProcessor
│   │
│   ├── reference/                  # Driven: External knowledge sources
│   │   ├── __init__.py
│   │   ├── conceptnet.py           # Implements ReferenceSource
│   │   ├── dbpedia.py
│   │   ├── wikidata.py
│   │   ├── schema_org.py
│   │   └── cache.py                # Reference API caching adapter
│   │
│   ├── sync/                       # Driven: Synchronization
│   │   ├── __init__.py
│   │   ├── s3_sync.py              # Implements SyncTarget for S3
│   │   └── parquet_sync.py         # DuckDB/Parquet sync
│   │
│   └── web/                        # Driving: HTTP API adapters
│       ├── __init__.py
│       ├── ontology_routes.py      # FastAPI routes for ontology management
│       ├── graph_routes.py         # FastAPI routes for graph analysis
│       ├── extraction_routes.py    # FastAPI routes for knowledge extraction
│       ├── pipeline_routes.py      # FastAPI routes for LLM pipelines
│       ├── versioning_routes.py    # FastAPI routes for version control
│       ├── admin_routes.py         # FastAPI routes for admin
│       ├── schemas.py              # Pydantic request/response models
│       └── dependencies.py         # FastAPI dependency injection wiring
│
├── database/                       # (Transitional — migrates into adapters/persistence)
├── services/                       # (Transitional — migrates into domain/)
├── graph/                          # (Transitional — migrates into domain/graph + adapters)
├── nlp/                            # (Transitional — migrates into adapters/nlp)
├── llm/                            # (Transitional — migrates into adapters/llm + domain/pipeline)
├── rag/                            # (Transitional — migrates into domain/extraction + adapters)
├── reference_api/                  # (Transitional — migrates into adapters/reference)
├── reference_db/                   # (Transitional — migrates into adapters/persistence)
├── embeddings/                     # (Transitional — migrates into adapters/embedding)
│
├── tests/
│   ├── unit/                       # Pure domain logic tests (no DB, no network)
│   │   ├── domain/
│   │   │   ├── test_ontology_service.py
│   │   │   ├── test_graph_service.py
│   │   │   └── ...
│   │   └── adapters/
│   │       ├── test_sqlite_repo.py
│   │       └── ...
│   ├── integration/                # Tests with real adapters
│   │   ├── test_ontology_api.py
│   │   └── ...
│   └── performance/
│       └── ...
│
├── documentation/
│   ├── requirements/
│   ├── claudes_thoughts/
│   └── openapi.json
│
└── utils/
    ├── logger.py
    └── update_api_specs.py
```

---

## 6. Port Interface Definitions

Ports are defined as Python `Protocol` classes (or ABCs) in each bounded context's `ports.py`. They define **what** the domain needs without saying **how** it's provided.

### 6.1 Core Ports

```python
# domain/ontology/ports.py

from typing import Protocol, Optional, Sequence
from domain.ontology.entities import Class, Taxonomy, ConceptScheme, Relationship, PropertyDefinition
from domain.ontology.value_objects import NodeType, SearchCriteria

class OntologyRepository(Protocol):
    """Port for persisting and retrieving ontology entities."""

    def get_class(self, class_id: str) -> Optional[Class]: ...
    def list_classes(self, scheme_id: Optional[str] = None,
                     parent_id: Optional[str] = None) -> Sequence[Class]: ...
    def save_class(self, cls: Class) -> Class: ...
    def delete_class(self, class_id: str) -> bool: ...
    def search_classes(self, criteria: SearchCriteria) -> Sequence[Class]: ...

    def get_taxonomy(self, taxonomy_id: str) -> Optional[Taxonomy]: ...
    def list_taxonomies(self) -> Sequence[Taxonomy]: ...
    def save_taxonomy(self, taxonomy: Taxonomy) -> Taxonomy: ...
    def delete_taxonomy(self, taxonomy_id: str) -> bool: ...

    def get_concept_scheme(self, scheme_id: str) -> Optional[ConceptScheme]: ...
    def list_concept_schemes(self, taxonomy_id: Optional[str] = None) -> Sequence[ConceptScheme]: ...
    def save_concept_scheme(self, scheme: ConceptScheme) -> ConceptScheme: ...
    def delete_concept_scheme(self, scheme_id: str) -> bool: ...

    def get_relationship(self, rel_id: str) -> Optional[Relationship]: ...
    def list_relationships(self, source_id: Optional[str] = None,
                           target_id: Optional[str] = None) -> Sequence[Relationship]: ...
    def save_relationship(self, rel: Relationship) -> Relationship: ...
    def delete_relationship(self, rel_id: str) -> bool: ...

    def get_property_definition(self, prop_id: str) -> Optional[PropertyDefinition]: ...
    def list_property_definitions(self) -> Sequence[PropertyDefinition]: ...
    def save_property_definition(self, prop: PropertyDefinition) -> PropertyDefinition: ...
    def delete_property_definition(self, prop_id: str) -> bool: ...


class EmbeddingService(Protocol):
    """Port for generating vector embeddings."""

    def embed_text(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class EventPublisher(Protocol):
    """Port for publishing domain events."""

    def publish(self, event: "DomainEvent") -> None: ...
```

```python
# domain/extraction/ports.py

from typing import Protocol, Sequence, Optional
from domain.extraction.entities import ExtractionResult

class LLMProvider(Protocol):
    """Port for LLM inference."""

    def complete(self, system_prompt: str, user_prompt: str,
                 model: str, temperature: float = 0.0,
                 max_tokens: Optional[int] = None) -> str: ...

    def is_available(self, model: str) -> bool: ...


class NLPProcessor(Protocol):
    """Port for NLP text processing."""

    def process(self, text: str) -> "NLPResult": ...
    def extract_entities(self, text: str) -> Sequence["Entity"]: ...


class ReferenceSource(Protocol):
    """Port for querying external knowledge sources."""

    def query(self, term: str, limit: int = 10) -> Sequence["ReferenceResult"]: ...
    def get_relations(self, uri: str) -> Sequence["Relation"]: ...
```

```python
# domain/graph/ports.py

from typing import Protocol, Sequence, Optional, Any

class GraphEngine(Protocol):
    """Port for graph computation (abstracts NetworkX)."""

    def build_from_nodes_and_edges(self, nodes: Sequence, edges: Sequence) -> None: ...
    def shortest_path(self, source: str, target: str) -> Sequence[str]: ...
    def centrality(self, algorithm: str = "betweenness") -> dict[str, float]: ...
    def communities(self) -> Sequence[set[str]]: ...
    def subgraph(self, node_ids: Sequence[str]) -> Any: ...


class SemanticQueryEngine(Protocol):
    """Port for semantic/SPARQL queries (abstracts RDFLib)."""

    def load_ontology(self, nodes: Sequence, edges: Sequence) -> None: ...
    def execute_sparql(self, query: str) -> Sequence[dict]: ...
```

### 6.2 Cross-Cutting Ports

```python
# domain/versioning/ports.py

class ChangeRepository(Protocol):
    """Port for persisting change events and versions."""

    def record_change(self, event: "ChangeEvent") -> "ChangeEvent": ...
    def get_changes(self, entity_id: str) -> Sequence["ChangeEvent"]: ...
    def get_version(self, entity_id: str, version: int) -> Optional["EntityVersion"]: ...


class SyncTarget(Protocol):
    """Port for remote synchronization."""

    def push_changes(self, changes: Sequence["ChangeEvent"]) -> "SyncResult": ...
    def pull_changes(self, since: "datetime") -> Sequence["ChangeEvent"]: ...
```

---

## 7. Adapter Wiring

The `app.py` lifespan function becomes the **composition root** where adapters are instantiated and injected into domain services:

```python
# Conceptual wiring in app.py

from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.llm.provider_router import LLMProviderRouter
from domain.ontology.services import OntologyService
from domain.graph.services import GraphAnalysisService

async def lifespan(app: FastAPI):
    # Create driven adapters
    db_engine = create_engine(config.database_url)
    ontology_repo = SQLiteOntologyRepository(db_engine)
    embedding_svc = SentenceTransformerEmbedding()
    event_publisher = InProcessEventPublisher()
    llm_provider = LLMProviderRouter(config.llm)

    # Create domain services (injected with ports, not concrete adapters)
    ontology_service = OntologyService(
        repository=ontology_repo,
        embedding=embedding_svc,
        events=event_publisher,
    )
    graph_service = GraphAnalysisService(
        repository=ontology_repo,
        graph_engine=NetworkXGraphEngine(),
        query_engine=RDFLibQueryEngine(),
    )

    # Store on app.state for dependency injection into routes
    app.state.ontology_service = ontology_service
    app.state.graph_service = graph_service
    # ...

    yield

    # Cleanup
    db_engine.dispose()
```

---

## 8. Domain Entity Design

Domain entities are plain Python dataclasses or Pydantic models with **no SQLAlchemy dependency**. They carry identity, enforce invariants, and define behavior.

```python
# domain/ontology/entities.py (conceptual)

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence
from domain.ontology.value_objects import NodeType

@dataclass
class Class:
    """An ontology class representing a concept that can be instantiated."""
    id: str
    title: str
    definition: Optional[str] = None
    node_type: NodeType = NodeType.CLASS
    parent_id: Optional[str] = None           # subClassOf relationship
    concept_scheme_id: Optional[str] = None   # which scheme this belongs to
    property_definition_id: Optional[str] = None  # structural property
    external_references: list["ExternalReference"] = field(default_factory=list)
    lexical_senses: list["LexicalSense"] = field(default_factory=list)
    data_properties: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None

    def rename(self, new_title: str) -> "ClassRenamed":
        """Rename the class and return a domain event."""
        old_title = self.title
        self.title = new_title
        return ClassRenamed(class_id=self.id, old_title=old_title, new_title=new_title)

    def add_subclass_of(self, parent_id: str) -> None:
        """Set the parent class (subClassOf relationship)."""
        if parent_id == self.id:
            raise ValueError("A class cannot be its own parent")
        self.parent_id = parent_id
```

---

## 9. Testing Strategy

The hexagonal architecture enables three distinct testing tiers:

### Tier 1: Domain Unit Tests (fast, no I/O)
Test domain services with mock/fake port implementations. These run in milliseconds and validate business rules.

```python
def test_class_cannot_be_its_own_parent():
    cls = Class(id="1", title="Database")
    with pytest.raises(ValueError):
        cls.add_subclass_of("1")
```

### Tier 2: Adapter Integration Tests (moderate, real I/O)
Test that adapters correctly implement ports against real infrastructure (SQLite in-memory, etc.).

```python
def test_sqlite_repo_saves_and_retrieves_class():
    repo = SQLiteOntologyRepository(in_memory_engine)
    cls = Class(id="1", title="Database")
    repo.save_class(cls)
    retrieved = repo.get_class("1")
    assert retrieved.title == "Database"
```

### Tier 3: End-to-End Tests (slow, full stack)
Test through the FastAPI routes with real adapters wired together.

---

## 10. Enterprise Extensibility

The adapter pattern directly enables future enterprise deployments:

| Concern | Desktop (Current) | Enterprise (Future) |
|---|---|---|
| Persistence | `SQLiteOntologyRepository` | `PostgresOntologyRepository` |
| Sync | `S3SyncAdapter` | `KafkaEventSync` |
| Auth | None (local) | `OIDCAuthAdapter` |
| Embedding | `SentenceTransformerEmbedding` | `OpenAIEmbeddingAdapter` |
| Config | `JSONFileConfigStore` | `VaultConfigStore` |

Swapping implementations requires only writing a new adapter that satisfies the port interface and changing the wiring in `app.py`. Zero domain code changes.

---

## 11. Design Decisions

### Why Protocols over ABCs?
Python `Protocol` (structural subtyping) is preferred because it doesn't require adapters to explicitly inherit from a base class. This reduces coupling and makes testing with simple fakes easier.

### Why dataclasses over Pydantic for domain entities?
Domain entities should be minimal and framework-free. Pydantic is excellent for API schemas (request/response validation) and lives in the adapter layer. Domain entities use `dataclass` to stay lightweight. If validation at the domain boundary is needed, it lives in domain service methods.

### Why bounded contexts, not just layers?
A pure layered architecture (API → Service → Repository) still allows lateral coupling between features. Bounded contexts enforce vertical slices that can evolve independently and eventually be extracted into separate deployable units if needed.

### Why keep the current service factory during transition?
The existing `ServiceFactory` works. Ripping it out immediately would be a big-bang rewrite. Instead, the roadmap phases it out gradually by migrating services one context at a time into the new structure. The factory becomes thinner with each phase until it's replaced by the composition root in `app.py`.
