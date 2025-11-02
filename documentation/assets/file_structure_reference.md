# Testing Infrastructure - File Structure & Absolute Paths

## Backend Testing Files

### Root Configuration
- `/Users/austinsand/workspace/context-studio/local-server/pytest.ini` - pytest configuration
- `/Users/austinsand/workspace/context-studio/local-server/run_tests.sh` - test runner script

### Core Test Directories
- `/Users/austinsand/workspace/context-studio/local-server/tests/` - test root
- `/Users/austinsand/workspace/context-studio/local-server/tests/conftest.py` (567 lines) - root fixtures
- `/Users/austinsand/workspace/context-studio/local-server/tests/test_config.py` - TestConfigurationManager
- `/Users/austinsand/workspace/context-studio/local-server/tests/test_db_utils.py` - database test utilities
- `/Users/austinsand/workspace/context-studio/local-server/tests/test_environment.py` - environment setup
- `/Users/austinsand/workspace/context-studio/local-server/tests/README.md` - test documentation

### Test Categories
- `/Users/austinsand/workspace/context-studio/local-server/tests/unit_tests/` (68+ files)
  - conftest.py - unit test-specific fixtures (NLP pipeline, service factory cleanup)
- `/Users/austinsand/workspace/context-studio/local-server/tests/integration_tests/` (57+ files)
  - conftest.py - integration test fixtures (minimal_reference_client)
- `/Users/austinsand/workspace/context-studio/local-server/tests/performance_tests/` (16+ files)
  - scale_test_small.db, scale_test_large.db - pre-populated test databases
- `/Users/austinsand/workspace/context-studio/local-server/tests/e2e/` - end-to-end tests
- `/Users/austinsand/workspace/context-studio/local-server/tests/fixtures/` - shared test data

### Configuration & Environment
- `/Users/austinsand/workspace/context-studio/local-server/.env.example` - environment variables template
- `/Users/austinsand/workspace/context-studio/local-server/config.py` - application settings (Pydantic)
- `/Users/austinsand/workspace/context-studio/local-server/database/utils.py` - database utilities

## Frontend Testing Files

### Root Configuration
- `/Users/austinsand/workspace/context-studio/ux/vitest.config.ts` - main Vitest configuration
- `/Users/austinsand/workspace/context-studio/ux/vitest.msw.config.ts` - MSW integration test config
- `/Users/austinsand/workspace/context-studio/ux/vitest.setup.ts` - main test setup (142 lines)
- `/Users/austinsand/workspace/context-studio/ux/vitest.msw.setup.ts` - MSW test setup (108 lines)
- `/Users/austinsand/workspace/context-studio/ux/package.json` - npm scripts and dependencies

### Test Directory Structure
- `/Users/austinsand/workspace/context-studio/ux/test/` - test root
- `/Users/austinsand/workspace/context-studio/ux/test/components/` - component unit tests
  - `llm_pipelines/LlmPipelineRun.test.tsx`
  - `llm_pipelines/PipelineFlavorEditor.test.tsx`
  - `nlp/NlpAnalysisPanel.test.tsx`
  - `llm_traceability/AnalyticsDashboard.test.tsx`
  - `llm_traceability/SelectionTracker.test.tsx`
- `/Users/austinsand/workspace/context-studio/ux/test/integration/` - MSW integration tests
  - `example.test.tsx`
  - `llm-integration.test.tsx`
  - `domain_edit.integration.test.tsx`
  - `hooks.useDomains.integration.test.tsx`
  - `llm-traceability.test.tsx`
  - `msw_adapter_repro.test.ts`
- `/Users/austinsand/workspace/context-studio/ux/test/msw/` - Mock Service Worker setup
  - `server.ts` - MSW server (4 lines)
  - `handlers.ts` - centralized API handlers
  - `setupTests.ts` - MSW setup
  - `README.md` - MSW documentation
- `/Users/austinsand/workspace/context-studio/ux/test/utils/` - test utilities
  - `renderWithProviders.tsx` - component wrapper
  - `mockNlpData.ts` - NLP test data
  - `mswCompatibleHttpAdapter.ts` - axios adapter compatibility
  - `forceMSWAdapter.ts` - MSW adapter helpers

### Documentation
- `/Users/austinsand/workspace/context-studio/ux/documentation/test_planning/` - test planning docs
- `/Users/austinsand/workspace/context-studio/documentation/features/testing/` - feature testing docs

## Database Files (Runtime)

Located in `/Users/austinsand/workspace/context-studio/local-server/datafiles/`:
- `local.db` - Primary workspace database
- `reference.db` - Reference knowledge graph
- `reference_api_cache.db` - API cache
- `operations.db` - Operations and audit database

Test databases created in system temp directory and cleaned up after test session.

## Key Statistics

| Metric | Count |
|--------|-------|
| Backend test files | 125+ |
| Backend unit tests | 68+ |
| Backend integration tests | 57+ |
| Backend performance tests | 16+ |
| Frontend test files | 19 |
| Frontend test configurations | 2 (dual vitest configs) |
| Backend fixtures (root conftest) | 12+ |
| Test markers in pytest | 6 |

