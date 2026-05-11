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
- **Screenshots**: Save all debugging/review screenshots to `/screenshots/` at the repo root. This directory is gitignored.

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
2. Run `alembic --config adapters/persistence/sqlite/alembic.ini revision --autogenerate --version-path adapters/persistence/sqlite/versions -m "description of change"`
3. Review the generated script in `adapters/persistence/sqlite/versions/`, then run `alembic --config adapters/persistence/sqlite/alembic.ini upgrade head`
4. To roll back: `alembic --config adapters/persistence/sqlite/alembic.ini downgrade -1`

To make a schema change for **`operations.db`** (when models are implemented):
1. Edit the ORM model in `adapters/persistence/sqlite/operations/models.py`
2. Run `alembic --config adapters/persistence/sqlite/alembic.ini -x db=operations revision --autogenerate --version-path adapters/persistence/sqlite/operations/versions -m "description of change"`
3. Review the generated script in `adapters/persistence/sqlite/operations/versions/`, then run `alembic --config adapters/persistence/sqlite/alembic.ini -x db=operations upgrade head`
4. To roll back: `alembic --config adapters/persistence/sqlite/alembic.ini -x db=operations downgrade -1`

Alternatively, use the helper script:
```bash
# For local.db
python scripts/run_migrations.py local upgrade head

# For operations.db
python scripts/run_migrations.py operations upgrade head

# For both
python scripts/run_migrations.py all upgrade head
```

**Never write migration SQL by hand.** Always use autogenerate. The `--version-path` flag is required when using multiple `version_locations` to specify which directory receives the generated migration script.

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
│   │   ├── script.py.mako          # Alembic migration template
│   │   ├── models.py               # SQLAlchemy ORM models (source of truth for local.db schema)
│   │   ├── versions/               # Auto-generated Alembic migration scripts for local.db
│   │   ├── operations/             # Separate environment for operations.db
│   │   │   ├── env.py              # Alembic environment for operations.db
│   │   │   ├── models.py           # SQLAlchemy ORM models for operations.db
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
│   ├── run_migrations.py           # Helper to run migrations for both databases
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
- **CSS design reference**: `ux/design/styles/` is the source of truth for the design system. When porting CSS, verify `body.dark-canvas` rule counts match between the reference and `src/design-system/studio.css` — this is the most common source of drift.

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
6. **CSS over inline styles**: Style with classes from `src/design-system/`. Before adding `style={{}}`, check for an existing utility class. If a pattern recurs more than once, add a class. Inline styles are only acceptable for values computed at runtime.
7. **New component checklist**: Every new interactive component must have: CSS class-based styling, `data-testid` on the root element, and ARIA roles (`role`, `aria-selected`, `aria-controls`, etc.) on any interactive element.

### Layout Patterns

**Pages with a detail drawer must use `SchemaPageLayout`.**  Every page that opens a detail panel when a row is selected must wrap its table and drawer in `SchemaPageLayout`, which applies the `split-2` CSS grid (`1fr 380px`). Never render the drawer as stacked content below the table. This applies to all data and schema pages — not just Phase 4 schema pages.

```tsx
<SchemaPageLayout
  data={filteredData}
  selectedId={selectedId}
  renderDrawerContent={(entity) => <MyDrawer ... />}
>
  <MyTable ... />
</SchemaPageLayout>
```

### Form Validation Behavior

**Validation errors must clear on `onChange`, not only on `onBlur`.**  After a failed submit reveals an error, the user expects it to disappear the moment they start correcting the field — not after they click away. Always clear field errors in the `onChange` handler:

```tsx
onChange={(e) => {
  setValue(e.target.value);
  setFieldError(undefined);  // required — do not leave this only in onBlur
}}
```

### Testing Strategy

- Unit tests for services and utilities
- Integration tests for React hooks and components
- Mock external dependencies (APIs, native modules)
- Separate test configs for different test types (API vs integration)
- Component unit tests must assert: correct CSS class names per variant, `data-testid` presence, and ARIA roles on interactive elements
- E2E tests: never use `waitForTimeout` — assert the expected DOM condition (class presence, attribute value, element visibility) and let Playwright poll
- **Drawer layout**: populated-state tests for pages with drawers must assert `container.querySelector('[data-testid="schema-page-layout"]')` is present when a row is selected
- **Validation error absence**: tests that verify error clearing must assert `expect(screen.queryByText("...error...")).not.toBeInTheDocument()` — asserting only that the input value changed is not sufficient

### Visual QA

**Run `/frontend-visual-qa` after implementing any new page, drawer, or form.** The skill takes screenshots in both light and dark canvas modes, verifies layout composition, tests form validation timing interactively, and audits test assertion completeness. It produces a structured pass/fail report. Do not consider frontend work done until this check passes.

<!-- generated-agents-section -->

## Specialized Sub-Agents

**MANDATORY**: Before implementing, identify which specialist agent applies to your task and consult it via the `Task` tool. Do not proceed with implementation until you have consulted the relevant agent. These agents have deep project-specific context that general knowledge cannot replicate.

| Agent | When to use |
|---|---|
| `context-studio-architect` | Designing new bounded contexts, ports, adapters, or cross-context flows in `local-server/`. |
| `context-studio-guardian` | Enforces `domain/` purity (zero infrastructure imports). Run before merging any backend change. |
| `context-studio-doc-maintainer` | Sync `rearchitecture/` docs, `CLAUDE.md`, `selector-registry.yaml`, and `app-context.md`. |
| `context-studio-data-expert` | Schema, Alembic migrations, repositories, dual-database (`local.db`, `operations.db`). |
| `context-studio-api-expert` | FastAPI routes, Pydantic schemas, OpenAPI contract, exception mapping. |
| `context-studio-frontend-expert` | React/TanStack components, hooks, OpenAPI-generated types, `data-testid` instrumentation. |
| `context-studio-tester` | Runs pytest, Vitest, and Playwright suites. Read-only — never writes tests. |
| `playwright-test-planner` | Produces an E2E test spec at `ux/e2e/documentation/specs/<feature>.md` from a feature description. Refuses to invent selectors. |
| `playwright-test-generator` | Turns an approved planner spec into a `.spec.ts` file under `ux/e2e/tests/`. Validates selector contract before emit. |
| `playwright-test-healer` | Diagnoses a single failing E2E test from a structured report; proposes a minimal draft-PR fix or escalates as a real bug. |

### E2E test development chain

```
Task(subagent_type="playwright-test-planner",   prompt="Plan an E2E test for <feature>: <user flow>")
Task(subagent_type="playwright-test-generator", prompt="Generate the test from ux/e2e/documentation/specs/<feature>.md")
Task(subagent_type="context-studio-tester",     prompt="Run validate-selectors then ux/e2e/tests/<area>/<feature>.spec.ts and report results")
# On failure:
Task(subagent_type="playwright-test-healer",    prompt="Diagnose failing test in ux/e2e/reports/<run_id>.json — categorize and propose a draft PR")
```

## Skills

| Skill | What it does |
|---|---|
| `/frontend-visual-qa` | Visual QA for a completed frontend page or component: screenshots in both canvas modes, layout composition check, form validation timing, test assertion audit. Run after any new page, drawer, or form. |
| `/context-studio-test` | Run test suites — backend (pytest), frontend unit (vitest), E2E (playwright). Accepts `backend`, `unit`, `integration`, `frontend`, `e2e`, `smoke`, `validate`, `all`. |
| `/context-studio-check` | Run all validation gates: domain purity, selector contract, OpenAPI freshness, TypeScript. |

<!-- /generated-agents-section -->
