# Context Studio

Context Studio is a local-first application for creating and curating knowledge graphs, and using those graphs for RAG and communication for both humans and agents.

## Architecture

Context Studio is local-first, designed to be packaged as a desktop app and run locally on end-user workstations.

- **Back End:** Python, FastAPI, SQLite with SQLiteVector, configurable LLM pipelines, remote sync via duckdb & parquet
- **Front End:** React, Vite, Flowbite-React, TanStack Router/Query/Tables/Forms, Tailwind CSS

## Repository Structure

```
/documentation      # Product documentation
/local-server       # Python back-end for the desktop app
/ux                 # React front-end for the desktop app (Vite build)
```

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
- This is a desktop app - configuration should not rely on environment variables and should instead be managed through the config.json file

---

## Change Management & API Updates

Typically functionality is built in the back-end first, tested and validated, and then the UX for that functionality is built.

### API Update Workflow

When back-end APIs are added/updated/removed:

1. **Update OpenAPI specs**: Run `/local-server/utils/update_api_specs.py` to update the `openapi.json` file for both back-end and front-end
2. **Generate front-end types**: Run `npm run generate-types` in the UX directory to update the digested view of the APIs and types
3. **Update hooks and services**: Update the API hooks and services to use the new types
4. **Build UX workflows**: Only after hooks/services are complete, build out user experience and workflows

---

## Back-End Development (`/local-server`)

### Technology Stack

- **Language**: Python 3.x
- **Web Server**: uvicorn
- **API Framework**: FastAPI
- **Database**: SQLite with SQLiteVector for vector storage
- **Data Validation**: Pydantic
- **Test Framework**: pytest

### Database Files

Context Studio uses multiple SQLite database files for different purposes:

- **`local.db`** (default): Primary user workspace database containing:
  - `structure_nodes` - Unified table for layers, domains, and terms in knowledge graphs
  - `structure_node_links` - Relationships between structure nodes with predicates
  - `predicates` - Semantic predicate definitions with optional mappings to external ontologies
  - `change_events` - Audit trail of all database changes across record types

- **`reference.db`**: Multi-source knowledge graph database containing consolidated reference data from external sources like ConceptNet, DBpedia, and Wikidata

- **`reference_api_cache.db`**: Caches API responses from external reference sources to improve performance and reduce API calls

- **`operations.db`**: Operational database for:
  - `pipeline_flavors` - LLM pipeline configurations for different processing tasks
  - `pipeline_flavor_executions` - Execution records and LLM traceability logs
  - Background task management
  - System audit logs
  - Administrative operations tracking

All databases use SQLite with the SQLiteVector extension for embedding storage and semantic search capabilities.

### Setup & Running

- Set up a Python virtual environment: `python -m venv .venv`
- Activate the environment: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Run the server: `python app.py`
- Server logs are available at `./logs/context_studio.log`

### Code Structure

```text
/local-server/
├── .env                                    # Dev environment variables (not in git)
├── api/                                    # API endpoints
├── app.py                                  # Main application file
├── config.py                               # Configuration settings
├── database/                               # Database models and utilities
│   ├── migrations/                         # Database migrations
│   │   ├── migration_manager.py            # Migration management script
│   │   └── versions/                       # Migration version scripts
│   ├── models.py                           # Database models
│   └── utils.py                            # Database utilities
├── documentation/                          # API and data model documentation
│   ├── requirements.md                     # High level requirements
│   ├── api.md                              # API documentation
│   ├── data_model.md                       # Data model documentation
│   └── claudes_thoughts/                   # Claude's thoughts and insights
├── embeddings/                             # Embedding generation utilities
├── graph/                                  # Graph data structure and utilities
├── nlp/                                    # Natural Language Processing utilities
├── nlp_sandbox/                            # Experimental NLP POCs
├── requirements.txt                        # Python dependencies
├── tests/                                  # Unit tests
│   ├── unit_tests/                         # Unit tests for individual components
│   ├── integration_tests/                  # Integration tests for API endpoints
│   └── performance_tests/                  # Performance tests for APIs
├── triage_scripts/                         # Scripts for triaging fundamental issues
└── utils/                                  # Utility functions
    ├── logger.py                           # Logging utilities
    └── update_api_specs.py                 # OpenAPI spec update utility
```

### Code Style

- All markdown reports and summaries other than README.md should be placed in `documentation/claudes_thoughts/`
- Always place all import statements at the top of the file
- Use snake_case for variable and function names
- Use CamelCase for class names
- Use triple double quotes for docstrings

### Best Practices

- **Schema Management**: Use the migration manager for database migrations. Always create a migration script when modifying the database schema
- **Code Quality**: Follow PEP 8 style guide for Python code
- **Documentation**: Maintain clear and concise documentation for APIs and data models
- **Testing**: Write unit tests for all critical functionalities using pytest. Write integration tests for API endpoints
- **Environment Variables**: Use `.env` files for sensitive configurations and secrets
- **Virtual Environment**: Use the `.venv` virtual environment when executing Python commands

### Common Pitfalls

- When comparing UUID values, always cast them to strings, as SQLite stores UUIDs as text

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
