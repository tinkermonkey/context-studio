# Context Studio

Context Studio is a local-first application for creating and curating knowledge graphs, and using those graphs for RAG and communication for both humans and agents.

## Architecture

Context Studio is local-first, designed to be packaged as a desktop app and run locally on end-user workstations.

- **Back End:** Python, FastAPI, SQLite with SQLiteVector, configurable LLM pipelines, remote sync via duckdb & parquet
- **Front End:** React, Vite, Flowbite-React, TanStack Router/Query/Tables/Forms, Tailwind CSS
- **Architecture Pattern:** Hexagonal (ports & adapters) with bounded contexts — see `rearchitecture/` for full design

## Repository Structure

```
/app                # Tauri desktop app shell — future packaging of /ux as a native app (not yet active)
/documentation      # Product documentation
/legacy-server      # REFERENCE ONLY — the previous back-end implementation (frozen)
/local-server       # Python back-end for the desktop app (active greenfield build)
/rearchitecture     # Architecture design documents for the new back-end
/ux                 # React front-end for the desktop app (Vite build)
```

`/app` is a Tauri v2 scaffold intended to eventually package `/ux` as a native desktop application. It is not yet wired to `/ux` and contains only the default Tauri starter. Do not develop in `/app` until that integration work is scoped.

### Important: `legacy-server/` is reference only

**Do not run tests in `legacy-server/`.** Do not modify code there. It exists solely as a functional reference for what the new server needs to implement. Its tests are useful as a reference for expected behavior, but are not part of the active test suite.

**There is no backwards compatibility requirement.** The new server defines new API contracts and a new database schema. Nothing in `legacy-server/` constrains the design of `local-server/`.

## Specialized Sub-Agents

| Agent | Domain | When to Use |
|-------|---------|-------------|
| local-server-engineer | back-end implementation specialist | implementing features, domain entities, adapters, routes, or tests in local-server/ |
| local-server-reviewer | back-end code reviewer | reviewing any local-server/ code after implementation |
| local-server-architect | back-end architecture specialist | designing what to build before implementation begins — new contexts, ports, API contracts |

---

## Core Principles

**IMPORTANT: You MUST follow these principles in all code changes:**

### KISS (Keep It Simple, Stupid)

- Simplicity should be a key goal in design
- Choose straightforward solutions over complex ones whenever possible
- Simple solutions are easier to understand, maintain, and debug

### YAGNI (You Aren't Gonna Need It)

- Avoid building functionality on speculation
- Implement features only when they are needed, not when you anticipate they might be useful in the future

### General Guidelines

- **Do not create documentation files** like implementation reports, design docs, etc.
- Use meaningful variable and function names - **avoid terms like "enhanced", "improved", "optimized"** in names
- **Configuration Management**: This is a desktop app - configuration is managed exclusively through the config.json file. Do not implement environment variable overrides for configuration settings. The .env file may be used for development convenience (e.g., setting CONFIG_PATH), but should not override application configuration.

---

## Change Management & API Updates

Functionality is built in the back-end first, tested and validated, then the UX is built.

### API Update Workflow

When back-end APIs are added/updated/removed:

1. **Update OpenAPI specs**: Run `/local-server/scripts/update_api_specs.py` to update the `openapi.json` file for both back-end and front-end
2. **Generate front-end types**: Run `npm run generate-types` in the UX directory to update the digested view of the APIs and types
3. **Update hooks and services**: Update the API hooks and services to use the new types
4. **Build UX workflows**: Only after hooks/services are complete, build out user experience and workflows

---

## Back-End Development (`/local-server`)

The new back-end uses a **hexagonal (ports & adapters) architecture** organized around bounded contexts. See `rearchitecture/architecture_design.md` for the full design.

### Technology Stack

- **Language**: Python 3.x
- **Web Server**: uvicorn
- **API Framework**: FastAPI
- **Database**: SQLite with SQLiteVector for vector storage
- **Schema Migrations**: Alembic (autogenerate from SQLAlchemy models)
- **Data Validation**: Pydantic (in adapter layer only — domain entities use dataclasses)
- **Test Framework**: pytest

### Bounded Contexts

The back-end is organized into six bounded contexts, each owning its domain entities, ports, and use cases:

1. **Ontology Management** — taxonomies, concept schemes, classes, relationships, property definitions
2. **Graph Analysis** — in-memory graph construction, traversal, SPARQL, network metrics
3. **Knowledge Extraction** — RAG pipeline, NLP processing, external knowledge enrichment
4. **LLM Pipeline Management** — pipeline configurations and execution tracking
5. **Version Control & Collaboration** — change events, changesets, proposals, conflict resolution, sync
6. **System Administration** — health, background tasks, configuration

### Database Files

- **`local.db`**: Primary workspace database (Alembic-managed)
  - `ontology_entities` — unified table for taxonomies, concept schemes, and classes (discriminated by `node_type`)
  - `relationships` — typed, directed edges between ontology entities
  - `property_definitions` — defined relationship types (object properties)
  - `change_events` — audit trail of all entity changes

- **`operations.db`**: Operational database (Alembic-managed)
  - `pipeline_configurations` — LLM pipeline configurations
  - `pipeline_executions` — execution records and LLM traceability logs
  - Background task management

- **`reference_api_cache.db`**: Cached responses from external knowledge sources (no migrations — can be dropped and rebuilt)

- **`reference.db`**: Imported reference data from ConceptNet, DBpedia, schema.org (no migrations — can be dropped and rebuilt)

All databases use SQLite with the SQLiteVector extension for embedding storage and semantic search.

### Schema Management

Schema changes are managed with **Alembic**. The SQLAlchemy ORM models in `adapters/persistence/sqlite/models.py` are the source of truth for the schema.

Alembic is configured under `adapters/persistence/sqlite/` with separate environments for `local.db` and `operations.db`:

To make a schema change for **`local.db`**:
1. Edit the ORM model in `adapters/persistence/sqlite/models.py`
2. Run `alembic --config adapters/persistence/sqlite/alembic.ini revision --autogenerate -m "description of change"`
3. Review the generated script in `adapters/persistence/sqlite/versions/`, then run `alembic --config adapters/persistence/sqlite/alembic.ini upgrade head`
4. To roll back: `alembic --config adapters/persistence/sqlite/alembic.ini downgrade -1`

To make a schema change for **`operations.db`** (when models are implemented):
1. Edit the ORM model in `adapters/persistence/sqlite/operations/models.py`
2. Run `alembic --config adapters/persistence/sqlite/alembic.ini -x db=operations revision --autogenerate -m "description of change"`
3. Review the generated script in `adapters/persistence/sqlite/operations/versions/`, then run `alembic --config adapters/persistence/sqlite/alembic.ini -x db=operations upgrade head`

**Never write migration SQL by hand.** Always use autogenerate.

### Code Structure

```text
/local-server/
├── app.py                          # FastAPI app, lifespan, composition root (adapter wiring)
├── config.py                       # Configuration loading from config.json
├── domain/                         # THE CORE — zero infrastructure imports
│   ├── ontology/                   # entities.py, value_objects.py, services.py, events.py, ports.py
│   ├── graph/                      # entities.py, services.py, ports.py
│   ├── extraction/                 # entities.py, services.py, ports.py
│   ├── pipeline/                   # entities.py, services.py, ports.py
│   ├── versioning/                 # entities.py, services.py, ports.py
│   └── admin/                      # entities.py, services.py, ports.py
├── adapters/
│   ├── persistence/sqlite/         # SQLAlchemy models, repository implementations, Alembic
│   │   ├── alembic.ini             # Alembic configuration for both databases
│   │   ├── env.py                  # Alembic environment for local.db
│   │   ├── models.py               # SQLAlchemy ORM models (source of truth for local.db schema)
│   │   ├── versions/               # Auto-generated Alembic migration scripts for local.db
│   │   ├── operations/             # Separate environment for operations.db
│   │   │   ├── env.py              # Alembic environment for operations.db
│   │   │   ├── models.py           # SQLAlchemy ORM models for operations.db (placeholder)
│   │   │   └── versions/           # Auto-generated Alembic migration scripts for operations.db
│   │   ├── ontology_repo.py        # Repository implementation for ontology context
│   │   ├── change_repo.py          # Repository implementation for versioning context
│   │   └── pipeline_repo.py        # Repository implementation for pipeline context
│   ├── embedding/                  # SentenceTransformer adapter
│   ├── llm/                        # OpenAI, Anthropic, provider router
│   ├── nlp/                        # spaCy processor adapter
│   ├── reference/                  # ConceptNet, DBpedia, Wikidata, schema.org adapters
│   ├── sync/                       # S3 and DuckDB sync adapters
│   └── web/                        # FastAPI routes and Pydantic schemas (per context)
├── tests/
│   ├── unit/                       # Domain logic tests — no I/O, no DB, run in seconds
│   ├── integration/                # Adapter tests with real SQLite
│   ├── e2e/                        # Full-stack tests with real external services
│   └── performance/
├── documentation/
│   └── claudes_thoughts/           # Claude's notes and analysis
├── scripts/
│   ├── check_domain_imports.py     # Verify domain/ has no infrastructure imports
│   ├── run_migrations.py           # Helper to run Alembic migrations for local.db and operations.db
│   └── update_api_specs.py
└── utils/
    └── logger.py
```

### Setup & Running

All Python work — virtual environment, dependency installation, running the server, and running tests — happens inside `/local-server/`. Never run Python commands from the repo root.

```bash
cd local-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

- The `.venv` directory lives at `local-server/.venv` and is gitignored
- Server logs are at `local-server/logs/context_studio.log`

### Dependency Rule

All imports point inward. `domain/` has **zero imports** from `adapters/`, `database/`, FastAPI, SQLAlchemy, or any other infrastructure. Verify with `scripts/check_domain_imports.py`.

### Code Style

- All markdown reports and summaries other than README.md should be placed in `documentation/claudes_thoughts/`
- Always place all import statements at the top of the file
- Use snake_case for variable and function names
- Use CamelCase for class names
- Use triple double quotes for docstrings

### Best Practices

- **Schema Management**: Use Alembic autogenerate — never hand-write migration SQL. Alembic configuration is at `adapters/persistence/sqlite/alembic.ini` with separate environments for `local.db` and `operations.db`
- **Domain purity**: Domain entities use Python dataclasses, not Pydantic or SQLAlchemy. Pydantic lives in `adapters/web/schemas/` only
- **Code Quality**: Follow PEP 8 style guide for Python code
- **Testing**: Write domain unit tests first (using fake port implementations), then adapter tests, then route tests
- **Environment Variables**: Use `.env` files for sensitive configurations and secrets
- **Virtual Environment**: Always use `local-server/.venv` — activate it before running any Python command
- **Alembic Migrations**: Run migrations from `local-server/` directory with `--config adapters/persistence/sqlite/alembic.ini` or use the helper script `scripts/run_migrations.py`

### Common Pitfalls

- When comparing UUID values, always cast them to strings, as SQLite stores UUIDs as text
- Do not import from `legacy-server/` — use it as a reading reference only
- Do not add backwards compatibility shims for the legacy API or database schema

### Testing

- Use `pytest` for running tests
- To avoid having to set `PYTHONPATH` for each test run, update the system path in test files:

```python
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

---

## Front-End Development (`/ux`)

### Technology Stack

- **Language**: TypeScript
- **Build Tool**: Vite
- **Framework**: React
- **Components**: Flowbite React, TanStack Tables, TanStack Forms
- **Routing**: TanStack Router
- **State Management**: TanStack Query
- **UI State**: Zustand for complex UI state management
- **CSS Framework**: Tailwind CSS
- **Icons**: Lucide React
- **API Client**: Type-safe API client built with Axios and OpenAPI
- **Testing**: Jest, React Testing Library

### Code Structure

```text
/ux/
├── .env                            # Dev environment variables (not in git)
├── .env.example                    # Environment variables example (in git)
├── .env.production                 # Production environment variables (not in git, very sensitive)
├── README.md                       # Project documentation
├── tailwind.config.js              # Tailwind configuration
├── tsconfig.json                   # TypeScript config
├── package.json                    # Project dependencies and scripts
├── node_modules/                   # Managed by npm
├── src/                            # Source code
│   ├── api/                        # API client and services
│   │   ├── services/               # API service files
│   │   ├── hooks/                  # Custom React hooks for API interactions
│   │   └── types/                  # Type definitions for API responses
│   ├── components/                 # Reusable React components
│   │   ├── node_selectors/         # Components for selecting nodes
│   │   ├── node_tables/            # Components for displaying node tables
│   │   ├── ui/                     # UI components (buttons, inputs, etc.)
│   │   └── layout/                 # Layout components
```

### Code Style

- All markdown reports and summaries other than README.md should be placed in `documentation/task_reports/`
- Use `@/` as the base path for imports

### Best Practices

- Write clean, readable, and maintainable code
- When API signatures change, run `npm run generate-types` to regenerate API types, then update hooks and services

### API Client Architecture

- Prefer type-safe clients generated from OpenAPI specs
- Use TanStack Query for state management and caching
- Implement proper error handling with custom error classes
- Structure API code in services layer with React hooks

### UI Architecture

1. **React**: All UX must be React components
2. **Flowbite React**: Use Flowbite React components for interface elements where possible
3. **Promote User Focus**: UX should be clean and focused without extraneous elements and decoration
4. **Error Handling**: Implement error catching within user workflows utilizing tools like useButterToast to communicate errors
5. **Asynchronous**: Where possible, user interactions should be asynchronous to maintain performance and statelessness

### Testing Strategy

- Unit tests for services and utilities
- Integration tests for React hooks and components
- Mock external dependencies (APIs, native modules)
- Separate test configs for different test types (API vs integration)
- Comprehensive unit tests: Test individual components and functions in isolation where possible
- End-to-End testing: Create scenarios that test the full user journey
- Good logging: Make sure all files have good logging
- Graceful degradation: Implement fallback strategies when components fail
