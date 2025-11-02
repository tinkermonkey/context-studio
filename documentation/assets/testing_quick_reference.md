# Testing Infrastructure - Quick Reference

## Backend (Python/FastAPI)

| Item | Details |
|------|---------|
| **Framework** | pytest 8.4.1 with pytest-asyncio |
| **Config** | `/local-server/pytest.ini` |
| **Test Dir** | `/local-server/tests/` (125+ test files) |
| **Run Tests** | `./run_tests.sh` or `pytest tests/` |
| **Test Types** | Unit (68+), Integration (57+), Performance (16+) |
| **Database** | Shared session-scoped SQLite in temp dir + function-level sessions |
| **Isolation** | MockConfigurationManager prevents config.json pollution |
| **Key Fixtures** | shared_app, shared_client, db_session, test_settings |
| **Markers** | @pytest.mark.unit, integration, performance, slow, asyncio |

## Frontend (React/TypeScript)

| Item | Details |
|------|---------|
| **Framework** | Vitest 1.6.1 (Vite-native) |
| **Config** | `vitest.config.ts` + `vitest.msw.config.ts` (dual) |
| **Test Dir** | `/ux/test/` (19 test files) |
| **Run Tests** | `npm test` or `npm run test:msw` |
| **Test Types** | Component unit tests + MSW integration tests |
| **Mocking** | MSW (Mock Service Worker) + axios mocks |
| **Setup** | vitest.setup.ts (axios mocks, DOM polyfills) |
| **Key Utils** | renderWithProviders, mockNlpData |
| **Handlers** | Centralized in `/ux/test/msw/handlers.ts` |

## Critical Patterns to Preserve

1. **Backend**: Shared database + function-level auto-rollback sessions (performance + isolation)
2. **Backend**: Monkey-patched MockConfigurationManager prevents pollution
3. **Frontend**: Dual Vitest configs (unit tests vs MSW integration tests)
4. **Frontend**: Centralized MSW handlers for API mocking
5. **Both**: Comprehensive cleanup and isolation fixtures at session level

## Database Files

Located in `/local-server/datafiles/`:
- `local.db` - Primary workspace (structure_nodes, predicates, change_events)
- `reference.db` - Knowledge graph consolidation
- `reference_api_cache.db` - External API response caching
- `operations.db` - Pipeline configs, audit logs, task management

Tests create temporary databases cleaned up after suite.

## Key Config Locations

- **Production**: `./config.json` (not in git)
- **Test Setup**: TestConfigurationManager (temp dirs, no pollution)
- **Environment**: `.env` (not in git, see `.env.example`)
- **Python Config**: `config.py` with Pydantic Settings
