# End-to-End Testing with Playwright

This directory contains end-to-end (E2E) tests for Context Studio using Playwright. These tests validate complete user workflows by running the full application stack (React frontend + FastAPI backend).

## Quick Start

### Prerequisites

1. **Backend setup** (in `/local-server`):
   - Python virtual environment created: `python -m venv .venv`
   - Dependencies installed: `pip install -r requirements.txt`
   - Virtual environment activated: `source .venv/bin/activate`

2. **Frontend setup** (in `/ux`):
   - Dependencies installed: `npm install`

### Running Tests

```bash
# From the /ux directory:

# Run all E2E tests (headless)
npm run test:e2e

# Run tests with UI mode (recommended for development)
npm run test:e2e:ui

# Run tests in headed mode (see the browser)
npm run test:e2e:headed

# Debug a specific test
npm run test:e2e:debug

# View HTML test report
npm run test:e2e:report
```

## How It Works

### Server Lifecycle

The E2E test infrastructure uses Playwright's global setup/teardown to manage server lifecycles:

1. **Global Setup** (`e2e/global-setup.ts`):
   - Cleans test databases in `/local-server/datafiles/e2e-test/`
   - Starts Python backend on port 8888
   - Starts Vite frontend dev server on port 3888
   - Waits for both servers to be ready
   - Servers run for the entire test suite

2. **Tests Run** (`e2e/tests/*.spec.ts`):
   - Tests execute sequentially (single worker)
   - Each test can interact with both frontend and backend
   - Backend API accessible via `page.request` for validation

3. **Global Teardown** (`e2e/global-teardown.ts`):
   - Stops both servers gracefully
   - Optionally cleans up test databases

### Test Isolation

- **Test databases**: All tests use isolated databases in `/local-server/datafiles/e2e-test/`
- **Configuration**: Backend uses `/local-server/config.e2e.json` for test-specific settings
- **Ports**: Different ports (8888/3888) prevent conflicts with development servers (8000/3100)
- **Sequential execution**: Tests run one at a time to avoid race conditions

## Directory Structure

```
/ux/e2e/
├── fixtures/                          # Test utilities and helpers
│   ├── test-helpers.ts                # Common test functions
│   ├── api-client.ts                  # API client for test requests
│   └── factories.ts                   # Test data factories
├── tests/                             # Test files organized by feature
│   ├── api-contracts/                 # API contract tests
│   │   └── ontology-endpoints.spec.ts
│   ├── graph/                         # Graph analysis tests
│   │   └── graph-analysis.spec.ts
│   ├── layout/                        # Layout and navigation tests
│   │   ├── navigation.spec.ts
│   │   └── pages.spec.ts
│   ├── ontology/                      # Ontology management tests
│   │   ├── classes.spec.ts
│   │   ├── concept-schemes.spec.ts
│   │   ├── property-definitions.spec.ts
│   │   ├── relationships.spec.ts
│   │   └── taxonomies.spec.ts
│   ├── pipeline/                      # Pipeline configuration tests
│   │   └── pipeline-config.spec.ts
│   ├── rag/                           # RAG experiments tests
│   │   └── rag-experiments.spec.ts
│   ├── reference/                     # Reference data search tests
│   │   └── reference-search.spec.ts
│   ├── example.spec.ts                # Example smoke tests
│   └── ontology-factories.spec.ts     # Factory pattern tests
├── global-setup.ts                    # Server startup logic
├── global-teardown.ts                 # Server shutdown logic
└── README.md                          # This file
```

## Writing Tests

### Basic Test Structure

```typescript
import { test, expect } from "@playwright/test";

test.describe("Feature Name", () => {
  test("should do something", async ({ page }) => {
    // Navigate to the app
    await page.goto("/");

    // Interact with the UI
    await page.click('[data-testid="button"]');

    // Assert expected behavior
    await expect(page.locator('[data-testid="result"]')).toContainText(
      "Success",
    );
  });
});
```

### Using Test Helpers

```typescript
import { test, expect } from "@playwright/test";
import { waitForAppReady, apiRequest } from "../fixtures/test-helpers";

test("should create an ontology class", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  // Create via UI
  await page.click('[data-testid="new-class-button"]');
  await page.fill('[data-testid="class-name"]', "Test Class");
  await page.click('[data-testid="submit"]');

  // Verify via API
  const classes = await apiRequest(page, "/api/classes");
  expect(classes.data.some((c) => c.title === "Test Class")).toBeTruthy();
});
```

### Best Practices

1. **Use data-testid attributes**: Add `data-testid` to elements for reliable selectors
2. **Wait for app ready**: Use `waitForAppReady()` before interacting with the app
3. **Validate backend state**: Use `apiRequest()` to verify data was persisted correctly
4. **Test user journeys**: Focus on complete workflows, not individual components
5. **Keep tests independent**: Don't rely on test execution order
6. **Use descriptive test names**: Clearly describe what the test validates

## Configuration Files

### Backend Configuration

**`/local-server/config.e2e.json`**

- Configures backend for testing
- Uses test database paths
- Disables expensive features (LLM, web search)
- Reduces logging verbosity

### Frontend Environment

**`/ux/.env.e2e`** (checked in — ready to use)

- Points frontend to test backend (port 8888)
- Sets environment identifier
- This file is included in the repository and does not need to be created

### Playwright Configuration

**`/ux/playwright.config.ts`**

- Defines test directory and execution settings
- Configures browsers to test
- Sets timeouts and retry behavior
- Specifies global setup/teardown scripts

## Troubleshooting

### Tests fail with "Address already in use"

One of the servers (8888 or 3888) is already running. Stop them:

```bash
# Find processes using the ports
lsof -ti:8888 -ti:3888

# Kill them
lsof -ti:8888 -ti:3888 | xargs kill -9
```

### Tests timeout during global setup

The servers may be taking too long to start. Check:

1. Backend logs: `/local-server/logs/context_studio_e2e.log`
2. Virtual environment is activated
3. All dependencies are installed
4. Increase timeout in `global-setup.ts` if needed

### Tests fail with "Virtual environment not found"

Create and activate the Python virtual environment:

```bash
cd /local-server
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend won't start

Ensure dependencies are installed:

```bash
cd /ux
npm install
```

### Database migrations fail

The test databases are created fresh on each run. If migrations fail:

1. Delete `/local-server/datafiles/e2e-test/` manually
2. Check migration files in `/local-server/adapters/persistence/sqlite/versions/`
3. Review backend logs for specific migration errors

## CI/CD Integration

For continuous integration:

```yaml
# Example GitHub Actions workflow
- name: Run E2E tests
  run: |
    cd local-server
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cd ../ux
    npm install
    npm run test:e2e
```

Set `CI=true` environment variable to enable:

- 2 retries for flaky tests
- GitHub Actions reporter
- Verbose output

## Performance Tips

- **Single worker**: E2E tests run sequentially to avoid backend conflicts
- **Server reuse**: Servers start once per test run, not per test
- **Fast config**: E2E config disables slow features (LLM, NLP auto-download)
- **Test focus**: Use `test.only()` during development to run specific tests

## Adding New Tests

1. Create a new file in `e2e/tests/` with `.spec.ts` extension
2. Import Playwright test utilities
3. Write test cases using `test.describe()` and `test()`
4. Run with `npm run test:e2e:ui` to debug
5. Commit the test file (Playwright artifacts are gitignored)

## Test Contract & Selector Registry

To prevent tests from hallucinating selectors and field names, Context Studio maintains an authoritative contract of all testable elements.

### The Contract

**See `app.context.md` at the repository root** for:
- Complete page map (all routes and their purpose)
- Entity model summary (field names sourced from `ux/src/api/client/types.ts`)
- Key user flows (5–8 documented workflows agents must understand)
- Invariants (rules the app guarantees)
- Anti-patterns (things tests must NEVER do)

### Selector Registry

**See `selector-registry.yaml` at the repository root** for the canonical list of all `data-testid` values exposed by the application.

#### Adding a New Selector

When you add a new testable element to the UI:

1. **Add the `data-testid` attribute** to your React component:
   ```tsx
   <button data-testid="my-entity-submit-button">Submit</button>
   ```

2. **Follow the naming convention**:
   - Format: `{entity-type}-{component}-{action}`
   - Example: `taxonomy-form-submit-button` or `class-table-add-button`
   - Dynamic selectors: `{entity-type}-row-{id}` (append entity UUID)

3. **Update the registry** (`selector-registry.yaml`):
   ```yaml
   forms:
     my_entity_submit_button:
       id: "my-entity-submit-button"
       component: "MyEntityForm"
       description: "Submit button for my entity form"
       file: "ux/src/components/forms/my_entity_form.tsx"
   ```

4. **Validate your changes**:
   ```bash
   npm run validate-selectors
   ```

5. **Commit both files** (the component with `data-testid` and the updated `selector-registry.yaml`)

#### Selector Naming Convention

- Use hyphens, not underscores: `class-table` not `class_table`
- Be descriptive but concise: `taxonomy-title-input` not `taxonomy-metadata-field-1`
- Group related selectors: all form inputs use `{entity}-{field}-input`
- Dynamic content uses templates: `{entity}-row-{id}` (filled in at runtime)

#### Pattern Selectors

For selectors that are generated dynamically (e.g., NodeTable components), mark them as `pattern: true` in the registry:

```yaml
tables:
  dynamic_add_button:
    id: "{entity-type}-add-button"
    component: "NodeTable"
    pattern: true
    template_param: "entity-type (taxonomy, class, relationship, etc.)"
```

The validator will match test selectors against these patterns.

### Validation

The selector contract is validated automatically on every test run:

```bash
# Validate selectors only (without running tests)
npm run validate-selectors

# Validate selectors before running tests (automatic)
npm run test         # Validates first, then runs vitest
npm run test:e2e     # Validates first, then runs playwright
```

**Exit codes**:
- `0` = All checks passed ✅
- `1` = Hard failure: test references non-existent selector ❌
- `2` = Warnings: selector in code but not in registry ⚠️

Tests cannot proceed if a test references a non-existent selector. Warnings indicate the registry needs updating.

### Anti-Patterns to Avoid

Tests must NEVER:
- ❌ Use `waitForTimeout()` without a condition (causes flaky tests)
- ❌ Assert trivial conditions like `expect(true).toBe(true)`
- ❌ Hardcode UUIDs (generate via factories instead)
- ❌ Reference selectors not in the registry
- ❌ Depend on UI text that may change
- ❌ Leave test data behind (use `test.afterEach()` cleanup)

See `app.context.md` for the full list of anti-patterns.

## Related Documentation

- [Playwright Documentation](https://playwright.dev/docs/intro)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Playwright API Reference](https://playwright.dev/docs/api/class-test)
- [App Context](../../app.context.md) — Authoritative product knowledge contract
