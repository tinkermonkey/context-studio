# Context Studio: Transformation Roadmap

## Greenfield Build — Hexagonal Architecture

**Date:** 2026-03-13
**Companion Document:** `architecture_design.md`
**Approach:** Greenfield build. The legacy server (`legacy-server/`) is frozen as a functional reference. The new server (`local-server/`) is built clean.

---

## Guiding Principles

1. **No backwards compatibility required.** The new server defines new API contracts. The front-end will be updated once the server reaches feature parity.
2. **No database migration from legacy.** The new schema is designed right from the start. The legacy database is reference material only.
3. **Domain first.** Write domain entities and services before any infrastructure. Tests prove business logic before a single database row exists.
4. **One bounded context at a time.** Build the Ontology context to full working state, then fan out.
5. **Tests gate each phase.** Domain unit tests must pass before moving to adapters. Adapter tests must pass before wiring routes.

---

## Persistence Approach: Alembic + SQLAlchemy

Schema management was a persistent pain point in the legacy server. Hand-written migration scripts accumulated to 19 versions of complex, fragile SQL.

The new server uses **Alembic** — the standard SQLAlchemy migration tool — with auto-generation:

- Model changes are reflected in SQLAlchemy ORM models (`adapters/persistence/sqlite/models.py`)
- Running `alembic revision --autogenerate -m "description"` generates the migration script
- Running `alembic upgrade head` applies it
- Rollback is `alembic downgrade -1`

This eliminates hand-written SQL for schema changes. The ORM model *is* the source of truth for the schema.

### Database Layout

The new server retains the multi-database pattern from the legacy server, but with clean boundaries:

| Database | Purpose |
|---|---|
| `local.db` | Primary workspace: ontology entities, relationships, change events |
| `operations.db` | LLM pipeline configurations, execution logs, background tasks |
| `reference_api_cache.db` | Cached responses from external knowledge sources |
| `reference.db` | Imported reference knowledge (ConceptNet, DBpedia, schema.org) |

Each database has its own Alembic environment under `adapters/persistence/sqlite/`.

---

## Phase 0: Project Setup (1 week)

**Goal:** A running FastAPI server with correct structure, Alembic configured, and a health endpoint.

### Tasks

**0.1 Directory scaffold**
Create the full directory structure from `architecture_design.md`. All `__init__.py` files. No business logic yet.

**0.2 Dependencies**
Set up `requirements.txt` with:
- `fastapi`, `uvicorn[standard]`
- `sqlalchemy`, `alembic`
- `pydantic`
- `pytest`, `httpx` (for testing)

Add dev dependencies (`requirements-dev.txt`): `black`, `ruff`, `mypy`.

**0.3 Configuration**
Port the config system from the legacy server's `config.py` / `config.json` pattern. Keep configuration managed through `config.json` — no environment variable overrides for app settings.

**0.4 Alembic setup**
Initialize Alembic for `local.db` and `operations.db`:
```
adapters/persistence/sqlite/
├── alembic.ini
├── env.py
└── versions/
```

**0.5 Health endpoint**
A single `GET /api/health` route that returns server status. This is the first end-to-end slice: domain entity → adapter → route.

**0.6 Logging**
Port the logger utility. All modules log at appropriate levels.

### Exit Criteria
- `python app.py` starts without errors
- `GET /api/health` returns 200
- `pytest tests/` finds and runs (even if there are no tests yet)
- Alembic migrations run cleanly on a fresh database

---

## Phase 1: Domain Core — Ontology Context (1–2 weeks)

**Goal:** The entire Ontology Management domain is implemented as pure Python with no infrastructure dependencies. All business rules are tested.

### Tasks

**1.1 Value objects**
Write `domain/ontology/value_objects.py`:
- `NodeType` enum: `TAXONOMY`, `CONCEPT_SCHEME`, `CLASS`, `INDIVIDUAL`
- `ExternalReference`, `LexicalSense`, `DataPropertyValue`, `OntologyMapping`, `SearchCriteria`

**1.2 Domain entities**
Write `domain/ontology/entities.py`:
- `Taxonomy`, `ConceptScheme`, `Class`, `Individual` (stub), `Relationship`, `PropertyDefinition`
- Each entity enforces its own invariants (e.g., `Class` rejects self-referential `parent_class_id`)

**1.3 Domain events**
Write `domain/ontology/events.py`:
- `ClassCreated`, `ClassUpdated`, `ClassDeleted`, `ClassMoved`
- `RelationshipCreated`, `RelationshipDeleted`
- `PropertyDefinitionCreated`
- `TaxonomyCreated`, `SchemeCreated`
- `GraphInvalidated`

**1.4 Port interfaces**
Write `domain/ontology/ports.py`:
- `OntologyRepository`, `EmbeddingService`, `EventPublisher`

**1.5 Domain service**
Write `domain/ontology/services.py` with `OntologyService`:
- Depends only on the port interfaces defined in 1.4
- Contains all business rules: type-specific validation, circular reference detection, embedding coordination, event emission
- Zero imports from `adapters/`, `database/`, or any framework

**1.6 Unit tests**
Write `tests/unit/domain/test_ontology_service.py` and `test_ontology_entities.py`:
- Use fake in-memory implementations of ports
- Cover all business rules and invariants
- Target: domain unit tests run in under 5 seconds

### Exit Criteria
- `domain/ontology/` has zero infrastructure imports (verified by `scripts/check_domain_imports.py`)
- All domain unit tests pass
- No SQLAlchemy, FastAPI, or SQLite imports anywhere in `domain/`

---

## Phase 2: Persistence Adapter — Ontology Context (1–2 weeks)

**Goal:** The SQLite persistence adapter for the Ontology context is complete and tested against a real database.

### Tasks

**2.1 SQLAlchemy models**
Write `adapters/persistence/sqlite/models.py` with ORM models for:
- `OntologyEntityORM` — unified table for taxonomies, concept schemes, and classes (discriminated by `node_type`)
- `RelationshipORM`
- `PropertyDefinitionORM`
- `ChangeEventORM`

**2.2 Initial Alembic migration**
Run `alembic revision --autogenerate -m "initial_schema"` to generate the first migration from the models. Review and commit.

**2.3 SQLite repository**
Write `adapters/persistence/sqlite/ontology_repo.py`:
- Implements `OntologyRepository` protocol
- Maps between ORM models and domain entities
- Handles the `node_type` discriminator for the unified entity table

**2.4 Adapter tests**
Write `tests/integration/test_sqlite_ontology_repo.py`:
- Use an in-memory SQLite database with migrations applied
- Test all CRUD operations and search
- Verify that domain entities round-trip correctly through the adapter

### Exit Criteria
- `alembic upgrade head` creates a clean schema from scratch
- All adapter integration tests pass against a real SQLite database
- `OntologyService` works end-to-end with the SQLite adapter (wired manually in tests)

---

## Phase 3: Web Adapter — Ontology Context (1 week)

**Goal:** The ontology management API is fully functional via HTTP.

### Tasks

**3.1 Pydantic schemas**
Write `adapters/web/schemas/ontology.py` with request/response models for all ontology operations.

**3.2 Routes**
Write `adapters/web/ontology_routes.py`:
- All CRUD routes for taxonomies, concept schemes, classes, relationships, property definitions
- Delegate to `OntologyService` injected via FastAPI dependency

**3.3 Dependency wiring**
Write `adapters/web/dependencies.py` with FastAPI dependency providers for all services.

**3.4 Composition root**
Wire everything together in `app.py`:
- Create SQLite engine
- Instantiate adapters
- Instantiate domain services
- Mount route routers

**3.5 Route tests**
Write `tests/integration/test_ontology_api.py`:
- Use `httpx.AsyncClient` with the full app
- Test all endpoints end-to-end through HTTP

**3.6 Update OpenAPI spec**
Run `utils/update_api_specs.py` to generate `documentation/openapi.json`.

### Exit Criteria
- All ontology CRUD operations work through the HTTP API
- OpenAPI spec is generated and accurate
- Route integration tests pass

---

## Phase 4: Remaining Domain Contexts (2–3 weeks)

Build each remaining bounded context in the same order: domain entities → ports → service → adapter → routes.

**4.1 Graph Analysis context**
- `domain/graph/` entities, ports, `GraphAnalysisService`
- `adapters/persistence/sqlite/` read-side for graph data
- `adapters/graph/networkx_engine.py` wrapping NetworkX
- `adapters/graph/rdflib_engine.py` wrapping RDFLib
- Routes for graph construction, path queries, SPARQL, network metrics

**4.2 Knowledge Extraction (RAG) context**
- `domain/extraction/` entities, ports, `ExtractionService`
- `adapters/llm/` (OpenRouter/OpenAI/Anthropic providers)
- `adapters/nlp/spacy_processor.py`
- `adapters/reference/` (ConceptNet, DBpedia, Wikidata, schema.org)
- Routes for text analysis and entity extraction

**4.3 LLM Pipeline Management context**
- `domain/pipeline/` entities, ports, `PipelineService`
- `adapters/persistence/sqlite/` pipeline repo (in `operations.db`)
- Alembic migration for `operations.db`
- Routes for pipeline configuration CRUD and execution

**4.4 Version Control & Collaboration context**
- `domain/versioning/` entities, ports, `VersioningService`
- Change event persistence, changeset management, proposal workflow, conflict resolution
- DuckDB-based sync adapter

**4.5 System Administration context**
- `domain/admin/` health, background tasks, configuration
- Routes for health, metrics, background task management

### Exit Criteria
- All bounded contexts implemented with domain tests and adapter tests
- All routes functional through HTTP
- Full OpenAPI spec generated

---

## Phase 5: Feature Parity & Front-End Integration (1–2 weeks)

**Goal:** The new server covers all functionality present in the legacy server.

### Tasks

**5.1 Feature audit**
Walk through `legacy-server/api/` route by route and verify each capability is present in the new server. Track gaps.

**5.2 Resolve gaps**
Implement any missing functionality discovered in the audit.

**5.3 Front-end update**
- Run `npm run generate-types` in `/ux` to pick up new API types
- Update all hooks and services to use new API contracts
- Verify all UX workflows end-to-end

**5.4 E2E tests**
Run the full E2E test suite (per `e2e_test_strategy.md`) against the new server.

**5.5 Update CLAUDE.md**
Reflect new directory structure and conventions.

### Exit Criteria
- Feature parity with legacy server confirmed by E2E tests
- Front-end fully functional against new server
- Legacy server decommissioned (can remain in `legacy-server/` for reference indefinitely)

---

## Timeline Summary

| Phase | Duration | Deliverable |
|---|---|---|
| 0: Setup | 1 week | Running server skeleton with health endpoint |
| 1: Ontology Domain | 1–2 weeks | Pure domain core with tests |
| 2: Persistence Adapter | 1–2 weeks | SQLite adapter with Alembic migrations |
| 3: Web Adapter | 1 week | Ontology API functional via HTTP |
| 4: Remaining Contexts | 2–3 weeks | All bounded contexts implemented |
| 5: Parity & Integration | 1–2 weeks | Front-end working, E2E green |
| **Total** | **7–11 weeks** | |

---

## What Changes vs. the Legacy Approach

| Concern | Legacy (Strangler Fig) | New (Greenfield) |
|---|---|---|
| Migration strategy | Incremental in-place | Clean break |
| DB compatibility | Backwards compatible | No constraint |
| API compatibility | Old routes maintained | New contracts |
| Test burden | Keep all old tests green | Write tests for new structure only |
| Schema management | Hand-written SQL migration scripts | Alembic autogenerate |
| Pace | ~100 min/issue due to compat overhead | Build forward without constraint |
