# Context Studio Testing Infrastructure Summary

## Overview

Context Studio has a comprehensive testing setup across both backend (Python/FastAPI) and frontend (React/TypeScript) with sophisticated isolation mechanisms and multiple test categories.

---

## Backend Testing (/local-server)

### Test Framework & Configuration

**Framework**: pytest v8.4.1
**Config File**: `/local-server/pytest.ini`

**Key pytest Configuration**:
- Test discovery: `testpaths = tests`, `python_files = test_*.py`, `python_functions = test_*`
- Async support: `asyncio_mode = auto` (pytest-asyncio 0.24.0)
- Default options: `--strict-markers`, `--strict-config`, `--tb=short`, `-v`
- Test markers for categorization: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.performance`, `@pytest.mark.slow`, `@pytest.mark.asyncio`, `@pytest.mark.event_processor`
- Extensive warning filters to reduce noise from dependencies (spacy, click, sqlalchemy, etc.)

### Test Structure

```
/local-server/tests/
├── conftest.py                 # Root test configuration (567 lines)
│   ├── Global session-level fixtures
│   ├── Test database initialization with migrations
│   ├── Configuration isolation mechanisms
│   └── Shared app/client fixtures
├── unit_tests/
│   ├── conftest.py            # Unit test-specific fixtures
│   │   ├── NLP pipeline singleton cleanup
│   │   ├── Service factory state cleanup
│   │   └── Performance monitor state cleanup
│   └── test_*.py              # 68+ unit test files
├── integration_tests/
│   ├── conftest.py            # Integration test fixtures
│   │   └── Minimal reference client fixture (MSW setup)
│   └── test_*.py              # 57+ integration test files
├── performance_tests/
│   ├── test_*.py              # 16+ performance/scale test files
│   └── *.db                   # Pre-populated test databases (scale_test_small.db, scale_test_large.db)
├── e2e/                       # End-to-end tests
├── fixtures/                  # Shared test fixtures and data
└── README.md                  # Test documentation
```

### Test Database Management

**Key Files**:
- `test_config.py`: TestConfigurationManager for test isolation
- `test_db_utils.py`: Database utilities for tests (with specialized isolation fixtures)
- `test_environment.py`: Environment setup and verification

**Database Initialization Flow**:
1. `create_test_database_with_migrations()` creates temporary SQLite databases
2. Applies all migrations via MigrationManager to ensure vector table support
3. Session-scoped shared database for performance (reused across tests)
4. Function-scoped sessions with auto-cleanup between tests

**Multiple Test Databases**:
- `local.db`: Primary workspace database (structure_nodes, predicates, change_events)
- `reference.db`: Multi-source knowledge graph (ConceptNet, DBpedia, Wikidata)
- `reference_api_cache.db`: Caches API responses from external sources
- `operations.db`: Pipeline configs, execution records, audit logs

### Test Fixtures (Root conftest.py)

**Session-Level Fixtures**:
- `global_test_isolation()`: Monkey-patches ConfigurationManager to prevent config.json pollution
- `test_service_factory()`: Creates ServiceFactory with optimized test settings (30s TTL, 5s cleanup)
- `test_database_manager()`: Provides DatabaseManager for test cleanup
- `shared_app()`: Creates FastAPI app with temporary test database (reused across all tests)
- `shared_client()`: TestClient for the shared app (reused across all tests)

**Function-Level Fixtures**:
- `test_settings()`: Isolated configuration per test via TestConfigurationManager
- `isolated_test_settings()`: Settings factory for custom configuration overrides
- `db_session()`: Clean database session with auto-rollback after each test
- `clean_db_session()`: Database session that commits changes (for data persistence tests)
- `optimized_db_session()`: Uses DatabaseManager for optimized session handling
- `reset_service_factory_cache()`: Auto-resets cache between unit tests (skipped for integration)

**Legacy Fixtures**:
- `test_app`: Backwards compatibility wrapper for `shared_app`
- `client`: Backwards compatibility wrapper for `shared_client`

### Test Isolation Mechanisms

**Configuration Isolation**:
```python
class MockConfigurationManager:
    - Prevents writes to global config.json
    - Uses test-specific temporary directories
    - Monkey-patched at session start, restored at end
    - Includes dataset manager isolation
```

**Test-Specific Configuration Defaults** (TestConfigurationManager):
- Logging files redirected to temp directory
- Proxy server disabled by default
- Auto-reload disabled
- Access logging disabled
- Dataset paths isolated to temp directory
- **Database URLs NOT overridden** (shared for performance)

**Database Cleanup Strategy**:
- PRAGMA foreign_keys OFF during cleanup
- Deletes all table data (preserves schema)
- Excludes migration tracking tables
- PRAGMA foreign_keys ON after cleanup
- Minimal per-test overhead

### Test Categories

**Unit Tests** (< 1 second each):
- Component-level testing (NLP pipeline, service factory, performance monitor)
- Configuration and validation tests
- Fast, isolated, minimal database interaction

**Integration Tests**:
- Full API endpoint testing
- Workflow testing (domains, layers, terms)
- Configuration manager features
- RAG pipeline integration
- Change event processing
- External predicates and semantic importer tests

**Performance Tests**:
- Scale testing (16 performance test files)
- Pre-populated test databases for realistic scenarios
- Throughput benchmarks
- RAG pipeline performance
- Task manager performance

### Test Execution

**Test Runner Script**: `/local-server/run_tests.sh`
```bash
./run_tests.sh                    # Run all tests
./run_tests.sh tests/unit_tests/  # Run unit tests only
./run_tests.sh -m unit            # Use pytest markers
./run_tests.sh -m "not slow"      # Exclude slow tests
```

**Manual Execution**:
```bash
source .venv/bin/activate
python -m pytest tests/
python -m pytest tests/integration_tests/ -v
python -m pytest -m performance    # Performance tests
```

### Test Dependencies

```
pytest==8.4.1
pytest-asyncio==0.24.0
pytest-subtests==0.14.2
starlette-testclient==0.4.1
```

### Configuration Files

**Environment Variables**:
- `.env.example`: Lists required vars (OPENAI_API_KEY, LLM_MODEL_NAME, LLM_TEMPERATURE)
- `.env`: Not in git, set by developers
- Tests use conftest monkey-patching instead of environment variables

**Config.json Integration**:
- Tests prevent pollution via MockConfigurationManager
- Test-specific settings created in temporary directories
- Global config.json verification after test session

---

## Frontend Testing (/ux)

### Test Framework & Configuration

**Framework**: Vitest v1.6.1 (Vite-native test runner, faster than Jest)
**Environment**: jsdom (browser environment simulation)
**Coverage**: Istanbul provider

**Package.json Scripts**:
```json
"test": "vitest run"              # Run all tests once
"test:run": "vitest run --no-coverage"
"test:ci": "vitest run --reporter verbose --coverage"
"test:coverage": "vitest run --coverage"
"test:coverage:c8": "c8 --reporter=lcov --reporter=text npx vitest run"
"test:msw": "vitest run --config vitest.msw.config.ts"
"generate-types": "openapi-typescript documentation/openapi.json -o src/api/client/types.ts"
```

### Test Structure

```
/ux/
├── vitest.config.ts            # Main test configuration
├── vitest.msw.config.ts        # MSW integration test configuration
├── vitest.setup.ts             # Main test setup (axios mocks, DOM polyfills)
├── vitest.msw.setup.ts         # MSW server setup
├── test/
│   ├── components/             # Component unit tests
│   │   ├── llm_pipelines/      # LLM pipeline component tests
│   │   └── nlp/                # NLP analysis component tests
│   │   └── llm_traceability/   # Traceability component tests
│   ├── integration/            # Integration tests with MSW
│   │   ├── example.test.tsx
│   │   ├── llm-integration.test.tsx
│   │   ├── domain_edit.integration.test.tsx
│   │   ├── hooks.useDomains.integration.test.tsx
│   │   └── llm-traceability.test.tsx
│   ├── msw/                    # Mock Service Worker setup
│   │   ├── server.ts           # MSW node server
│   │   ├── handlers.ts         # API endpoint handlers
│   │   ├── setupTests.ts
│   │   └── README.md
│   └── utils/                  # Test utilities
│       ├── renderWithProviders.tsx
│       ├── mockNlpData.ts
│       ├── mswCompatibleHttpAdapter.ts
│       └── forceMSWAdapter.ts
└── documentation/
    └── test_planning/          # Test planning documentation
```

### Vitest Configuration

**vitest.config.ts**:
```typescript
test: {
  environment: "jsdom",
  setupFiles: "./vitest.setup.ts",
  globals: true,
  coverage: {
    provider: "istanbul"
  },
  exclude: ["node_modules", "dist", "test/integration/example.test.tsx", "test/integration/msw_*.test.*"]
}
```

**vitest.msw.config.ts** (separate config for MSW tests):
```typescript
test: {
  environment: "jsdom",
  setupFiles: "./vitest.msw.setup.ts",
  globals: true,
  // Only run specific MSW integration tests
  include: ["test/integration/example.test.tsx", "test/integration/msw_*.test.*"]
}
```

### Test Setup Files

**vitest.setup.ts** (Main setup, ~142 lines):
- Imports testing-library jest-dom matchers
- Mocks axios to prevent real HTTP requests
- Mocks `@/api/client/axios` module
- DOM cleanup after each test
- DOM setup before each test
- Window.matchMedia mock for responsive design tests
- IntersectionObserver mock
- ResizeObserver mock
- DOM compatibility fixes for appendChild/insertBefore

**vitest.msw.setup.ts** (MSW-specific setup, ~108 lines):
- Same as main setup plus:
- Imports MSW server from `./test/msw/server`
- `beforeAll()`: server.listen({ onUnhandledRequest: "warn" })`
- `afterEach()`: server.resetHandlers()
- `afterAll()`: server.close()

### Mock Service Worker (MSW) Setup

**server.ts** (4 lines):
```typescript
import { setupServer } from "msw/node";
import { handlers } from "./handlers";
export const server = setupServer(...handlers);
```

**handlers.ts**:
- Centralized API endpoint mocks
- Generic REST handlers for domains (PUT matcher)
- Domain listing endpoints
- Domain detail endpoints
- Custom handlers for different edge cases
- Extensible pattern for adding more endpoints

### Test Examples

**Component Unit Test Pattern** (LlmPipelineRun.test.tsx):
```typescript
- Mock API hooks
- Create wrapper with QueryClientProvider
- Use vitest describe/it/beforeEach/expect
- Render component with wrapper
- Test interactions with fireEvent/userEvent
- Verify state changes
```

**Integration Test Pattern**:
- Use MSW for API mocking
- Test full component workflows
- Verify API interactions
- Test hooks integration with components

### Test Dependencies

```json
"@testing-library/react": "^16.3.0",
"@testing-library/dom": "^8.20.1",
"@testing-library/jest-dom": "^6.8.0",
"@testing-library/user-event": "^14.6.0",
"@types/jest": "^30.0.0",
"vitest": "^1.6.1",
"@vitest/coverage-istanbul": "^3.2.4",
"jsdom": "^26.1.0",
"msw": "^1.3.1"
```

### Test Utilities

**renderWithProviders.tsx**:
- Wraps components with necessary providers (Query, Router, etc.)
- Ensures consistent test environment

**mockNlpData.ts**:
- Provides realistic NLP test data
- Reusable across multiple tests

**mswCompatibleHttpAdapter.ts & forceMSWAdapter.ts**:
- MSW compatibility helpers
- Ensures axios adapter compatibility with MSW

---

## Patterns to Preserve

### Backend Patterns

1. **Shared Test Database with Function-Level Sessions**:
   - Single session-scoped database (faster overall)
   - Fresh session + auto-rollback for each test
   - Excellent isolation without duplication overhead

2. **Configuration Isolation via Monkey-Patching**:
   - Global config never polluted by tests
   - Temporary directories for test artifacts
   - Critical files verified unchanged after suite

3. **Multi-Level Fixtures**:
   - Session-level for expensive setup (database, app)
   - Function-level for test-specific isolation
   - Automatic cleanup and resource management

4. **Comprehensive Marker System**:
   - Clear categorization of test types
   - Ability to skip slow tests in development
   - Performance-critical tests separated

5. **Mixed Test Database Approach**:
   - Shared default database for performance
   - Specialized isolation utilities available when needed
   - Test-specific databases created on-demand

### Frontend Patterns

1. **Dual Vitest Configurations**:
   - Default config for fast component tests
   - Separate MSW config for integration tests
   - Allows running different test types independently

2. **Centralized MSW Handlers**:
   - Single source of truth for API mocks
   - Extensible pattern for adding endpoints
   - Realistic test scenarios with edge case handling

3. **Setup File Hierarchy**:
   - Base setup for common needs (axios mocks, DOM polyfills)
   - Specialized setup for MSW integration tests
   - Minimal duplication, clear separation of concerns

4. **Wrapper Components Pattern**:
   - renderWithProviders for consistent test environment
   - Reusable across all component tests
   - Ensures providers match production setup

5. **Mock Isolation**:
   - Axios mocked to prevent real HTTP requests
   - API client module mocked as fallback
   - Clean DOM state between tests

---

## Database File Locations & Purposes

All databases stored in `/local-server/datafiles/` (configurable via config.json):

| Database | Purpose | Tables |
|----------|---------|--------|
| `local.db` | Primary workspace | structure_nodes, structure_node_links, predicates, change_events |
| `reference.db` | Knowledge graph consolidation | External sources (ConceptNet, DBpedia, Wikidata) |
| `reference_api_cache.db` | API response caching | Cache entries to reduce external API calls |
| `operations.db` | Operational tracking | pipeline_flavors, pipeline_flavor_executions, audit logs, background tasks |

Test databases created in temporary directories and cleaned up after test session.

---

## Configuration Management

**Production Config**: `./config.json` (not in git)
**Test Config**: Created in temporary directories by TestConfigurationManager
**Environment**: `.env` file (not in git, referenced in .env.example)

**Key Configuration Sections**:
- `server`: host, port, reload, CORS, logging
- `database`: default URL, reference paths, cache paths, operations path
- `llm`: model name, temperature, max tokens, timeout
- `nlp`: spaCy model, text length limits, ConceptNet relations
- `rag_pipeline`: context retrieval, LLM timeout, gap detection
- `logging`: level, file path, console/file output
- `dataset`: dataset management configuration
- `proxy_server`: S3/proxy configuration

---

## Key Differences from Typical Setups

1. **No Test Environment Pollution**: Mock ConfigurationManager prevents global state changes
2. **Shared Database for Performance**: Tests reuse same database schema, not individual instances
3. **Dual Test Runners**: Backend (pytest) and frontend (vitest) completely separate
4. **MSW for Frontend**: Replaces traditional axios mocking with realistic API simulation
5. **Migration Testing**: Tests apply actual database migrations, not just schema
6. **Performance Tests Included**: Dedicated performance test suite with pre-populated databases
7. **Async-First**: Comprehensive asyncio support for async test code
8. **SQLiteVector**: Tests include vector database functionality (not standard SQLite)

