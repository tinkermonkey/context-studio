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
├── fixtures/                  # Test utilities and helpers
│   └── test-helpers.ts        # Common test functions
├── tests/                     # Test files
│   └── example.spec.ts        # Example smoke tests
├── global-setup.ts            # Server startup logic
├── global-teardown.ts         # Server shutdown logic
└── README.md                  # This file
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

**`/ux/.env.e2e`**

- Points frontend to test backend (port 8888)
- Sets environment identifier

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

## Related Documentation

- [Playwright Documentation](https://playwright.dev/docs/intro)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Playwright API Reference](https://playwright.dev/docs/api/class-test)
