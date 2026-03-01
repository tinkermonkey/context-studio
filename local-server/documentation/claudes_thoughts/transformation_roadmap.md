# Context Studio: Transformation Roadmap

## From Organic Monolith to Hexagonal Architecture

**Date:** 2026-03-01
**Companion Document:** `architecture_design.md`
**Approach:** Strangler Fig — incremental migration with continuous deployability

---

## Guiding Principles

1. **Never break the running system.** Every phase ends with a working application. Old and new code coexist during transition.
2. **Terminology migration is decoupled from structural migration.** Rename things first (low risk), restructure second.
3. **One bounded context at a time.** Migrate the core ontology context first since everything depends on it, then fan out.
4. **Tests gate each phase.** No phase is complete until the existing test suite passes against the new structure and new tests cover the migrated code.
5. **Front-end remains stable.** The API contract (OpenAPI) is maintained throughout. Route paths can change with redirects, but request/response shapes stay compatible.

---

## Phase 0: Foundation (1–2 weeks)

**Goal:** Establish the new directory structure and shared infrastructure without moving any existing code.

### Tasks

**0.1 Create the skeleton directory structure**
Create all directories from the target layout in `architecture_design.md`. Add `__init__.py` files. No code moves yet—just the scaffolding.

```
local-server/
├── domain/
│   ├── ontology/
│   ├── graph/
│   ├── extraction/
│   ├── pipeline/
│   ├── versioning/
│   └── admin/
├── adapters/
│   ├── persistence/sqlite/
│   ├── persistence/duckdb/
│   ├── embedding/
│   ├── llm/
│   ├── nlp/
│   ├── reference/
│   ├── sync/
│   └── web/
```

**0.2 Define shared value objects and enums**
Create `domain/ontology/value_objects.py` with the new `NodeType` enum (`TAXONOMY`, `CONCEPT_SCHEME`, `CLASS`, `INDIVIDUAL`) and shared value objects (`ExternalReference`, `LexicalSense`). These can be imported by both old and new code.

**0.3 Create port interfaces**
Write the `Protocol` classes for all driven ports in each bounded context's `ports.py`. These are just interface definitions—no implementations yet. This forces us to think through the contracts before writing code.

**0.4 Set up import aliasing**
Create compatibility aliases so that existing code can gradually switch:
```python
# domain/ontology/compat.py
# Temporary bridge during migration
from database.models import StructureNode as LegacyStructureNode
```

### Exit Criteria
- New directory structure exists alongside old
- Port interfaces are defined and documented
- All existing tests still pass
- No behavior changes

---

## Phase 1: Terminology Migration (2–3 weeks)

**Goal:** Rename domain concepts throughout the codebase to use standard terminology. This is a refactoring phase—behavior stays identical.

### Tasks

**1.1 Database migration script**
Create a new migration (version 019) that:
- Renames `structure_nodes` → `ontology_entities` (or keeps the table name but updates the model mapping)
- Renames `node_type` enum values: `layer` → `taxonomy`, `domain` → `concept_scheme`, `term` → `class`
- Renames `structure_node_links` → `relationships`
- Renames `predicates` → `property_definitions`
- Renames `pipeline_flavors` → `pipeline_configurations`
- Preserves all data with ALTER TABLE / UPDATE statements
- Includes rollback capability

**Important:** The `node_type` column value rename (`layer`→`taxonomy`, etc.) is the highest-risk change. The migration must update all rows and the enum handling code must accept both old and new values during the transition window.

**1.2 Update SQLAlchemy models**
Rename model classes and update column references:
- `StructureNode` → `OntologyEntity` (intermediate name; will split later)
- `StructureNodeLink` → `Relationship`
- `Predicate` → `PropertyDefinition`
- `PipelineFlavor` → `PipelineConfiguration`

Keep old names as aliases for backwards compatibility:
```python
StructureNode = OntologyEntity  # Deprecated alias
```

**1.3 Update service layer terminology**
Rename service classes:
- `NodeService` → `OntologyEntityService` (intermediate)
- `NodeLinkService` → `RelationshipService`
- Rename methods: `create_node` → `create_entity`, etc.
- Keep old method names as deprecated wrappers

**1.4 Update API routes and schemas**
- Rename Pydantic schemas: `NodeCreate` → `EntityCreate`, `NodeOut` → `EntityOut`, etc.
- Add new route paths alongside old ones (e.g., `/api/classes/` alongside `/api/structure_nodes/`)
- Mark old routes as deprecated in OpenAPI spec
- Regenerate OpenAPI spec and front-end types

**1.5 Update front-end types**
- Run `npm run generate-types` to pick up new API types
- Update hooks and services to use new type names (can be done incrementally)

### Exit Criteria
- All tests pass with new terminology
- Old API routes still work (deprecated but functional)
- New API routes available
- Database migration tested forward and backward

---

## Phase 2: Domain Core Extraction — Ontology Context (3–4 weeks)

**Goal:** Extract the core ontology domain logic into the new `domain/ontology/` package with proper entity classes and services that depend only on port interfaces.

### Tasks

**2.1 Create domain entities**
Write pure Python dataclass entities in `domain/ontology/entities.py`:
- `Taxonomy`, `ConceptScheme`, `Class` (split from unified `OntologyEntity`)
- `Individual` (new, empty for now)
- `Relationship`
- `PropertyDefinition`

Each entity carries its own validation logic (e.g., "a class cannot be its own parent").

**2.2 Create domain service**
Write `domain/ontology/services.py` with `OntologyService`:
- Depends on `OntologyRepository`, `EmbeddingService`, `EventPublisher` (ports)
- Contains all business rules currently in `NodeService`:
  - Type-specific validation
  - Circular reference detection
  - Embedding generation coordination
  - Event emission
- **No SQLAlchemy imports.** The service works with domain entities only.

**2.3 Implement SQLite adapter for OntologyRepository**
Write `adapters/persistence/sqlite/ontology_repo.py`:
- Implements `OntologyRepository` protocol
- Maps between SQLAlchemy ORM models and domain entities
- Contains all persistence logic currently scattered across `NodeService`

**2.4 Implement EmbeddingService adapter**
Write `adapters/embedding/sentence_transformer.py`:
- Wraps the existing singleton `SentenceTransformer` model
- Implements the `EmbeddingService` port
- Preserves the existing thread-safety and caching behavior

**2.5 Create domain event infrastructure**
Write a simple in-process event publisher:
- `InProcessEventPublisher` implements `EventPublisher`
- Replaces direct `ChangeEventHandler` calls
- Domain events are translated to `ChangeEvent` persistence at the adapter level

**2.6 Wire new ontology service into FastAPI**
Write `adapters/web/ontology_routes.py`:
- New route handlers that delegate to `OntologyService`
- Pydantic schemas for request/response validation
- Register alongside existing routes (both work during transition)

**2.7 Update ServiceFactory**
Remove ontology-related service creation from `ServiceFactory`. The composition root in `app.py` now creates `OntologyService` directly. `ServiceFactory` still manages other services.

### Exit Criteria
- `domain/ontology/` has zero imports from `database/`, `services/`, or any adapter
- Domain unit tests pass with fake/mock ports
- Integration tests pass with SQLite adapter
- Both old and new API routes work
- Existing front-end works without changes

---

## Phase 3: Domain Core Extraction — Graph & Extraction Contexts (3–4 weeks)

**Goal:** Extract graph analysis and knowledge extraction into their own bounded contexts.

### Tasks

**3.1 Graph Analysis context**
- Create `domain/graph/entities.py` with `KnowledgeGraph`, `GraphMetrics`, `PathResult`
- Create `domain/graph/services.py` with `GraphAnalysisService`
- Define `GraphEngine` and `SemanticQueryEngine` ports
- Implement `adapters/persistence/sqlite/` methods for graph data loading (reusing `OntologyRepository`)
- Create `NetworkXGraphEngine` adapter wrapping existing `NetworkService`
- Create `RDFLibQueryEngine` adapter wrapping existing `SPARQLService`
- Wire into routes

**3.2 Knowledge Extraction context**
- Create `domain/extraction/entities.py` with `ExtractionResult`, `ExtractionLayer`
- Create `domain/extraction/services.py` with `ExtractionService`
- Define `LLMProvider`, `NLPProcessor`, `ReferenceSource` ports
- Implement adapters:
  - `adapters/llm/openai_provider.py` and `adapters/llm/anthropic_provider.py` (from existing `llm/service.py`)
  - `adapters/nlp/spacy_processor.py` (from existing `nlp/pipeline.py`)
  - `adapters/reference/conceptnet.py`, `dbpedia.py`, `wikidata.py` (from existing `reference_api/`)
- Wire into routes

### Exit Criteria
- Both contexts have zero infrastructure imports in their domain packages
- Graph analysis works through new service layer
- RAG extraction pipeline works through new service layer
- All tests pass

---

## Phase 4: Domain Core Extraction — Pipeline, Versioning, Admin (2–3 weeks)

**Goal:** Migrate remaining bounded contexts.

### Tasks

**4.1 LLM Pipeline Management context**
- Extract `PipelineConfiguration` and `Execution` entities
- Create `PipelineService` depending on `PipelineRepository` and `LLMProvider` ports
- Move pipeline CRUD and execution tracking behind the port boundary

**4.2 Version Control & Collaboration context**
- Extract `ChangeEvent`, `EntityVersion`, `Changeset`, `Proposal` entities
- Create `VersioningService` and `ConflictResolver` domain services
- Implement `ChangeRepository` and `SyncTarget` ports
- Move `VersionManager`, `WorkingTreeManager`, `DiffGenerator`, `ChangesetManager`, `ProposalManager`, `CRDTMergeEngine`, `ConflictResolutionEngine`, `IncrementalSyncEngine` logic into domain services
- Create persistence adapters for change tracking

**4.3 System Administration context**
- Extract health, metrics, config, and background task management
- Create appropriate ports and adapters

### Exit Criteria
- All bounded contexts live in `domain/`
- All infrastructure code lives in `adapters/`
- `ServiceFactory` is eliminated, replaced by composition root

---

## Phase 5: Cleanup & Consolidation (2–3 weeks)

**Goal:** Remove all legacy code, consolidate the codebase, and ensure everything is clean.

### Tasks

**5.1 Remove deprecated routes and aliases**
- Remove old API routes (e.g., `/api/structure_nodes/`)
- Remove model aliases (`StructureNode = OntologyEntity`)
- Remove compatibility shims

**5.2 Remove old directory structure**
- Delete `services/` (all logic now in `domain/` or `adapters/`)
- Delete `graph/`, `nlp/`, `llm/`, `rag/`, `reference_api/`, `reference_db/`, `embeddings/` (all in `adapters/`)
- Delete `database/models.py` (now in `adapters/persistence/sqlite/models.py`)
- Keep `database/migrations/` or move to `adapters/persistence/sqlite/migrations/`

**5.3 Update OpenAPI spec generation**
- Regenerate specs from new route structure
- Run `npm run generate-types` for final front-end type update

**5.4 Update CLAUDE.md**
- Reflect new directory structure and conventions
- Update code style guidelines for hexagonal architecture
- Document bounded contexts and port/adapter pattern

**5.5 Full test suite review**
- Ensure test coverage meets or exceeds pre-migration levels
- Add missing domain unit tests
- Clean up test directory structure to match new layout

**5.6 Front-end migration**
- Update all API hooks to use new route paths
- Remove references to old type names
- Verify all UX workflows end-to-end

### Exit Criteria
- No legacy code remains
- Clean directory structure matching architecture design
- All tests pass
- Front-end fully functional against new API
- CLAUDE.md updated

---

## Phase 6: Enterprise Readiness (Future / Optional)

**Goal:** Demonstrate the value of the hexagonal architecture by adding alternative adapters.

### Tasks (not scoped in detail)
- `PostgresOntologyRepository` adapter for enterprise persistence
- Authentication adapter (OIDC/OAuth2)
- `OpenAIEmbeddingAdapter` as alternative to local SentenceTransformer
- Kafka/event streaming adapter for `SyncTarget`
- Multi-tenant configuration adapter

---

## Timeline Summary

| Phase | Duration | Risk | Key Deliverable |
|---|---|---|---|
| 0: Foundation | 1–2 weeks | Low | Skeleton structure, port interfaces |
| 1: Terminology | 2–3 weeks | Medium | Renamed DB, models, services, routes |
| 2: Ontology Core | 3–4 weeks | High | Pure domain core for ontology |
| 3: Graph & Extraction | 3–4 weeks | Medium | Two more bounded contexts extracted |
| 4: Pipeline, Versioning, Admin | 2–3 weeks | Medium | All contexts extracted |
| 5: Cleanup | 2–3 weeks | Low | Legacy removed, consolidated |
| **Total** | **~13–19 weeks** | | |

---

## Risk Mitigation

### Phase Gate Decisions

Each phase has a **go/no-go checkpoint** before the next phase begins:

| After Phase | Gate Criteria |
|---|---|
| 0 → 1 | Port interfaces reviewed and approved. Skeleton structure committed. |
| 1 → 2 | Database migration tested forward AND backward on a copy of real data. Dual-name support confirmed working. All tests pass with new terminology. |
| 2 → 3 | `domain/ontology/` has zero infrastructure imports (verified by import linter). Old and new routes both serve identical responses (verified by API diff test). |
| 3 → 4 | Graph and extraction contexts pass all existing integration tests through new service layer. |
| 4 → 5 | All bounded contexts extracted. ServiceFactory is no longer imported by any domain code. |

If a phase fails its gate, the team stops, resolves issues, and re-validates before proceeding. The strangler fig approach means the old code still works, so there is no urgency to push forward.

### Note on Individual Entity

The `Individual` entity (concrete instances of Classes) is defined in the domain model but **not implemented** in Phases 0–5. The `OntologyRepository` port includes stub method signatures for `get_individual`, `list_individuals`, etc. to future-proof the interface, but adapters should raise `NotImplementedError` until Individual support is actively developed (Phase 6 or later).

### Highest Risk: Phase 1 Database Migration
The terminology rename touches every row in the database. Mitigation:
- Write and test the migration against a copy of production data
- Include explicit rollback logic
- Keep dual-name support (old enum values still accepted) for at least one full phase

### Second Highest Risk: Phase 2 Domain Extraction
Extracting business logic from `NodeService` into a pure domain service is the largest refactoring. Mitigation:
- Write comprehensive characterization tests before touching `NodeService`
- Extract one method at a time, verifying tests pass after each extraction
- Keep `NodeService` as a thin wrapper delegating to `OntologyService` during transition

### Ongoing Risk: Front-End Breakage
API changes can break the UX. Mitigation:
- Maintain old routes with deprecation warnings through Phase 4
- Run front-end integration tests after each API change
- Use OpenAPI spec diff to catch unintended contract changes

---

## Success Metrics

The migration is successful when:

1. **Domain purity:** `domain/` packages have zero imports from `adapters/`, `database/`, or any framework code
2. **Test speed:** Domain unit tests run in under 5 seconds total
3. **Adapter swappability:** A new adapter (e.g., Postgres) can be added by implementing a port interface without modifying domain code
4. **Terminology clarity:** A developer familiar with OWL/RDF/SKOS can navigate the codebase without a translation guide
5. **No regression:** All existing functionality works identically from the user's perspective
