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

## Agentic Test Development Workflow

This project uses Claude agents to generate high-quality test specifications and implementations. The workflow includes human approval gates at each stage.

### Overview

The test development workflow uses a planner agent and a generator agent to create Playwright tests that consume the authoritative product knowledge from `app.context.md` and the selector registry.

```
Feature Request → Planner Agent → Spec Review → Generator Agent → Test Review → Merge
     (step 1)       (step 2)       (step 3)      (step 4)        (step 5)    (step 6)
```

### Step 1: Write a Feature Description

Start with a clear description of what you want to test:
- Feature name
- User flow to test
- Entities involved
- Expected behavior

Example:
```
Test creating a new taxonomy and deleting it.

User flow:
1. Navigate to /app/taxonomies
2. Click "Add" button
3. Fill in title and description
4. Submit form
5. Verify taxonomy appears in list
6. Select taxonomy and delete it
7. Verify it's removed from list
```

Or reference a GitHub issue number: `#595 Phase 1.2`

### Step 2: Run the Planner Agent

The planner agent creates a detailed test specification:

```bash
# Using Claude Code with .github/playwright-planner.md
npx claude-code --agent-definition .github/playwright-planner.md \
  --input "Test creating and deleting a taxonomy" \
  --output specs/create-and-delete-taxonomy.md
```

The planner will:
1. Read the authoritative product knowledge (`app.context.md`)
2. Consult the selector registry (`ux/selector-registry.yaml`)
3. Review entity field names from the OpenAPI contract
4. Create a comprehensive test specification with:
   - Test cases with step-by-step instructions
   - Required selectors (verified against registry)
   - Entity field names (verified against contract)
   - CRUD coverage analysis
   - Anti-pattern validations

**Output**: A Markdown spec file in `specs/<feature-name>.md`

### Step 3: Review and Approve the Specification

Before code is written, review the test plan:

1. **Read the specification** in `specs/<feature-name>.md`
2. **Verify coverage**:
   - Does it test the right user flow?
   - Are all important scenarios covered?
   - Do edge cases make sense?
3. **Check for missing selectors**:
   - If the planner added "Open Questions" for missing selectors, add them to `ux/selector-registry.yaml` first
   - The planner will refuse to proceed if selectors don't exist
4. **Approve** by marking the spec ready for generation

If changes are needed:
- Modify the spec and get planner feedback, OR
- Ask the planner to revise the spec

### Step 4: Run the Generator Agent

Once the spec is approved, generate the test code:

```bash
# Using Claude Code with .github/playwright-generator.md
npx claude-code --agent-definition .github/playwright-generator.md \
  --input specs/create-and-delete-taxonomy.md \
  --output ux/e2e/tests/ontology/create-and-delete-taxonomy.spec.ts
```

The generator will:
1. Read the test specification
2. Consult the product contract (`app.context.md`)
3. Review the selector registry
4. Create production-ready Playwright tests with:
   - Semantic locators only (no CSS selectors or XPath)
   - Factory pattern usage from `ux/e2e/fixtures/factories.ts`
   - Proper error handling
   - Anti-pattern avoidance
   - Full CRUD coverage

**Output**: A TypeScript test file in `ux/e2e/tests/<feature>/<test-name>.spec.ts`

### Step 5: Validate and Review the Tests

```bash
# Validate selector contract (runs automatically before tests)
npm run validate-selectors

# Run the tests in debug mode
npm run test:e2e:ui

# Run all E2E tests
npm run test:e2e
```

The validator (`ux/scripts/check_test_contract.ts`) will:
- Extract all `data-testid` references from your test file
- Verify each selector exists in `ux/selector-registry.yaml`
- **Fail with exit code 1** if any selector is missing
- Tests cannot run until validation passes

Review the test code:
1. **Selector validation**: Runs automatically
2. **Code quality**: Check for clarity and maintainability
3. **Coverage**: Verify all test cases from spec are implemented
4. **Anti-patterns**: Ensure no anti-patterns from `app.context.md`
5. **Factory usage**: Verify factories are used for entity creation

If changes are needed:
- Ask the generator to revise
- Or make manual fixes and validate with `npm run validate-selectors`

### Step 6: Merge

Once tests pass and are reviewed:
1. Commit the test file
2. Create a pull request
3. Ensure CI passes (E2E tests run as part of CI)
4. Merge to `main`

## Test Healing Workflow

**STATUS: Planned — The healer agent specification exists at `.github/playwright-healer.md`, but CI integration and draft-PR creation are not yet implemented.**

When tests fail in CI, a healer agent can analyze the failure and propose a fix. The healer is the most dangerous of the three agents because its mistakes silently mask real bugs — guardrails matter.

### Overview

The healer agent inspects a failing test, categorizes the failure, and either proposes a fix (as a draft PR) or escalates as a real product bug.

```
Test Fails in CI → Healer Analyzes → Categorizes Failure → Opens Draft PR or Bug Report
   (automatic)      (Claude agent)    (3 categories)        (for human review)
```

**Note**: The workflow diagram above shows the intended workflow once CI integration is complete. Today, the healer specification and guardrails are documented but not yet wired into CI.

### When Tests Fail

Tests can fail for three different reasons:

#### 1. **Selector Renamed** (Low Risk)
- The UI element exists but the `data-testid` attribute changed
- Example: `taxonomy-submit-button` → `ontology-taxonomy-submit-button`
- **Action**: Healer proposes a diff to update the selector

#### 2. **Timing Changed** (Low Risk)
- The element takes longer to appear, or a network operation changed
- Example: Test expects element to appear immediately, but now takes a moment
- **Action**: Healer proposes a conditional wait instead of a fixed timeout

#### 3. **Likely Real Bug** (High Risk)
- Core functionality fails unexpectedly (API error, CRUD operation fails, assertion fails on real data)
- Example: API returns 500, entity field is null, delete fails with 403
- **Action**: Healer escalates as a bug report (NO code fix)

### Healer Workflow

1. **Test fails in CI**: A test times out, fails an assertion, or can't find a selector
2. **Healer analyzes**: Claude agent reads the failure log and current UI state
3. **Categorize**: Is this a selector change, timing issue, or real bug?
4. **Propose or escalate**:
   - For selector/timing issues: Open a draft PR with a unified diff
   - For real bugs: Open a draft PR with no code changes — just a bug report
5. **Human reviews**: Decide if this is a legitimate UI change or a real bug
6. **Merge or file issue**: If UI change, merge and update selectors. If bug, file an issue.

### Guardrails

The healer REFUSES to propose any of these anti-patterns:

**❌ Fixed timeouts without conditions**
```typescript
// REFUSE
await page.waitForTimeout(2000);

// PROPOSE INSTEAD
await page.waitForLoadState("networkidle");
```

**❌ Vacuous assertions**
```typescript
// REFUSE
expect(true).toBe(true);
expect(page.url()).toBeTruthy();

// PROPOSE INSTEAD (or escalate as bug)
expect(page.url()).toContain("/app/taxonomies");
```

**❌ Try/catch to swallow errors**
```typescript
// REFUSE
try {
  await expect(element).toContainText("Created");
} catch {
  // Ignore failure
}

// PROPOSE INSTEAD (or escalate as bug)
await expect(element).toContainText("Created");
```

**❌ Replacing getByTestId with CSS or XPath**
```typescript
// REFUSE
page.locator("button.submit-btn")  // CSS
page.locator("//button[@id='submit']")  // XPath

// PROPOSE INSTEAD (investigate the selector change)
page.getByTestId("ontology-taxonomy-submit-button")
```

### Draft PR Workflow

Every healer PR:
- Is opened as a **draft** (humans must review before merge)
- Includes a **category** tag: `[Selector Renamed]`, `[Timing Changed]`, or `[Likely Real Bug]`
- Includes a **one-paragraph rationale** explaining why the fix is safe
- Passes **validation** before opening (selectors must exist in registry)

Example PR:
```
Title: [Healer] Fix failing: taxonomies (Selector Renamed)

## Failure Summary
Test: ux/e2e/tests/ontology/taxonomies.spec.ts::create-and-delete-taxonomy
Category: Selector Renamed
Reason: getByTestId("taxonomy-submit-button") not found

## Proposed Fix

The selector was renamed from "taxonomy-submit-button" to 
"ontology-taxonomy-submit-button" in the UI refactoring. 
The component still exists and functions identically.

```diff
- await page.getByTestId("taxonomy-submit-button").click();
+ await page.getByTestId("ontology-taxonomy-submit-button").click();
```

## Validation
- ✅ New selector exists in selector-registry.yaml
- ✅ No anti-patterns introduced
- ✅ Validator passes
```

### Escalation as Bug

When the healer detects a likely real bug, it opens a draft PR with no code changes:

```
Title: [Healer] Bug report: taxonomies (Likely Real Bug)

## Bug Report
Test: ux/e2e/tests/ontology/taxonomies.spec.ts::create-and-delete-taxonomy
Expected: POST /api/taxonomies returns 201
Actual: API returned 500 Internal Server Error

## Evidence
[Failure log showing API error]

## Assessment
This appears to be a real product bug, not a test failure. 
The test correctly validates that creating a taxonomy should succeed, 
but the API is returning an error.

Next step: Create a product issue to investigate and fix the backend.
```

### Implementation

For detailed healer specifications and guardrails, see:
- `.github/playwright-healer.md` — Healer agent specification with complete guardrail definitions

The healer guardrails are enforced through agent instructions in the spec, not through automated tests. When CI integration is complete, a test suite will validate that the agent refuses anti-patterns and properly categorizes failures.

## Manual Test Development

If you prefer to write tests manually instead of using agents:

1. Create a new file in `ux/e2e/tests/` with `.spec.ts` extension
2. Use semantic locators and factory patterns (see generator rules)
3. Reference only selectors from `ux/selector-registry.yaml`
4. Validate with `npm run validate-selectors` before committing
5. Avoid all anti-patterns from `app.context.md`

## Adding New Tests

Manually create a new test file:

1. Create a new file in `ux/e2e/tests/` with `.spec.ts` extension
2. Import Playwright test utilities and factories
3. Write test cases using `test.describe()` and `test()`
4. **Use only semantic locators** (`getByRole`, `getByLabel`, `getByTestId`)
5. **Use factories** from `ux/e2e/fixtures/factories.ts` for entity creation
6. **Reference only documented selectors** from `ux/selector-registry.yaml`
7. Run `npm run validate-selectors` to verify selectors
8. Run with `npm run test:e2e:ui` to debug
9. Commit the test file (Playwright artifacts are gitignored)

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
