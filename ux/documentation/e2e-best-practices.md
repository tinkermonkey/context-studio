# E2E Testing Best Practices

This document outlines the best practices implemented in Context Studio's e2e tests to ensure reliable, maintainable, and fast test execution.

## Overview

The Phase 3 e2e tests (Reference Search and RAG Experiments) serve as examples of production-quality e2e testing following industry best practices.

---

## Key Principles

### 1. ✅ **Never Use Fixed Timeouts**

**❌ Bad:**

```typescript
await page.waitForTimeout(3000); // Hope 3 seconds is enough
const hasResults = await page
  .locator('[data-testid="results"]')
  .isVisible()
  .catch(() => false);
```

**✅ Good:**

```typescript
// Wait for a specific condition with explicit timeout
await expect(page.locator('[data-testid="results"]')).toBeVisible({
  timeout: 10000,
});

// Or use the waitForAnyCondition helper
const resultIndex = await waitForAnyCondition(
  page,
  [
    async () => await page.locator('[data-testid="results"]').isVisible(),
    async () => await page.getByText("No results found").isVisible(),
  ],
  10000,
);
```

**Why:** Fixed timeouts are brittle and make tests slower than necessary. Wait for specific conditions instead.

---

### 2. ✅ **Mock External Dependencies**

**❌ Bad:**

```typescript
// Test relies on external APIs being available
test("should search external API", async ({ page }) => {
  await page.fill('[data-testid="search"]', "computer");
  await page.click('[data-testid="search-button"]');
  // Fails if DBpedia is down or slow
  await expect(page.locator('[data-testid="results"]')).toBeVisible();
});
```

**✅ Good:**

```typescript
test.beforeEach(async ({ page }) => {
  // Mock external APIs for reliability
  await mockReferenceAPIs(page);
});

test("should search external API", async ({ page }) => {
  await page.fill('[data-testid="search"]', "computer");
  await page.click('[data-testid="search-button"]');
  // Always succeeds, fast and reliable
  await expect(page.locator('[data-testid="results"]')).toBeVisible();
});
```

**Why:** External APIs can be slow, rate-limited, or unavailable. Mocking ensures tests are fast and reliable.

---

### 3. ✅ **Verify Backend Readiness**

**❌ Bad:**

```typescript
test("should create record", async ({ page }) => {
  // Assumes endpoint exists
  await apiRequest(page, "/api/new-feature/records", {
    method: "POST",
    body: {},
  });
});
```

**✅ Good:**

```typescript
test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();

  const hasEndpoint = await endpointExists(page, "/api/new-feature/records");
  await context.close();

  if (!hasEndpoint) {
    throw new Error(
      "API endpoint not available. Please ensure the backend is running with this feature enabled.",
    );
  }
});
```

**Why:** Provides clear error messages when backend features are missing, rather than cryptic 404 errors.

---

### 4. ✅ **Use Explicit Waits with Clear Timeouts**

**❌ Bad:**

```typescript
await page.click('[data-testid="button"]');
// Implicitly waits, unclear what we're waiting for
const isVisible = await page.locator('[data-testid="result"]').isVisible();
```

**✅ Good:**

```typescript
await page.click('[data-testid="button"]');
// Explicitly wait for the expected outcome with timeout
await expect(page.locator('[data-testid="result"]')).toBeVisible({
  timeout: 5000,
});
```

**Why:** Makes test intent clear and provides specific timeout control.

---

### 5. ✅ **Wait for Elements Before Interacting**

**❌ Bad:**

```typescript
await page.goto("/page");
await page.click('[data-testid="button"]'); // May click before element is ready
```

**✅ Good:**

```typescript
await page.goto("/page");
await page.waitForLoadState("networkidle");

const button = page.locator('[data-testid="button"]');
await expect(button).toBeVisible({ timeout: 10000 });
await expect(button).toBeEnabled();
await button.click();
```

**Why:** Ensures elements are ready before interaction, preventing flaky tests.

---

### 6. ✅ **Better Error Messages**

**❌ Bad:**

```typescript
const hasResults = await page
  .locator('[data-testid="results"]')
  .isVisible()
  .catch(() => false);
expect(hasResults).toBeTruthy(); // Error: "expected false to be truthy"
```

**✅ Good:**

```typescript
await waitForElement(page, '[data-testid="results"]', { timeout: 10000 });
// Error: "Element '[data-testid="results"]' not found after 10000ms. Current URL: http://localhost:3888/app/search"
```

**Why:** Clear error messages make debugging failed tests much faster.

---

### 7. ✅ **Use Semantic Selectors**

**❌ Bad:**

```typescript
await page.click("div.container > button.btn-primary:nth-child(2)"); // Fragile
```

**✅ Good:**

```typescript
// Priority order:
// 1. data-testid attributes
await page.click('[data-testid="submit-button"]');

// 2. ARIA roles and labels
await page.getByRole("button", { name: "Submit" }).click();

// 3. Text content (when appropriate)
await page.getByText("Submit").click();
```

**Why:** Semantic selectors are more resilient to UI changes.

---

### 8. ✅ **Test One Thing at a Time**

**❌ Bad:**

```typescript
test("should do everything", async ({ page }) => {
  // Creates, edits, deletes, and tests navigation all in one test
  await createRecord();
  await editRecord();
  await deleteRecord();
  await testNavigation();
});
```

**✅ Good:**

```typescript
test("should create record", async ({ page }) => {
  // Focused on one responsibility
  await createRecord();
  await verifyRecordExists();
});

test("should edit record", async ({ page }) => {
  await createRecordViaAPI();
  await editRecord();
  await verifyUpdates();
});
```

**Why:** Focused tests are easier to debug and maintain.

---

### 9. ✅ **Use API for Test Data Setup**

**❌ Bad:**

```typescript
test("should delete record", async ({ page }) => {
  // Creates record through UI (slow)
  await page.goto("/records/new");
  await page.fill('[data-testid="name"]', "Test");
  await page.click('[data-testid="submit"]');

  // Now test deletion
  await page.click('[data-testid="delete"]');
});
```

**✅ Good:**

```typescript
test("should delete record", async ({ page }) => {
  // Create prerequisite data via API (fast)
  const record = await apiRequest(page, "/api/records", {
    method: "POST",
    body: { name: "Test" },
  });

  // Test the actual feature
  await page.goto(`/records/${record.id}`);
  await page.click('[data-testid="delete"]');
});
```

**Why:** Setting up via API is faster and keeps tests focused on what they're actually testing.

---

### 10. ✅ **Handle Multiple Possible Outcomes**

**❌ Bad:**

```typescript
// Assumes search always returns results
await page.click('[data-testid="search"]');
await expect(page.locator('[data-testid="results"]')).toBeVisible();
```

**✅ Good:**

```typescript
await page.click('[data-testid="search"]');

// Wait for any valid outcome
const outcome = await waitForAnyCondition(
  page,
  [
    async () => await page.locator('[data-testid="results"]').isVisible(),
    async () => await page.getByText("No results found").isVisible(),
    async () => await page.getByText("Search failed").isVisible(),
  ],
  15000,
);

// Assert that *something* happened
expect(outcome).toBeGreaterThanOrEqual(0);
```

**Why:** Real-world applications have multiple valid states. Tests should handle them all.

---

## Helper Functions

### `waitForAnyCondition()`

Waits for any of multiple conditions to be true. Returns the index of the first condition that succeeds.

```typescript
const resultIndex = await waitForAnyCondition(
  page,
  [
    async () => await page.locator('[data-testid="success"]').isVisible(),
    async () => await page.locator('[data-testid="error"]').isVisible(),
  ],
  10000,
);

if (resultIndex === 0) {
  // Success case
} else if (resultIndex === 1) {
  // Error case
}
```

### `endpointExists()`

Checks if a backend endpoint is available before running tests.

```typescript
const hasEndpoint = await endpointExists(page, "/api/new-feature");
if (!hasEndpoint) {
  throw new Error("Feature not available");
}
```

### `mockReferenceAPIs()`

Mocks external API responses for reliable testing.

```typescript
await mockReferenceAPIs(page);
// Now all external API calls return predictable test data
```

### `waitForElement()`

Waits for an element with better error messages.

```typescript
await waitForElement(page, '[data-testid="results"]', { timeout: 10000 });
// Throws clear error with current URL if element not found
```

---

## Test Structure Template

```typescript
import { test, expect } from "@playwright/test";
import {
  apiRequest,
  waitForElement,
  endpointExists,
} from "../fixtures/test-helpers";

test.describe("Feature Name", () => {
  // Verify backend is ready
  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    const hasEndpoint = await endpointExists(page, "/api/feature");
    await context.close();

    if (!hasEndpoint) {
      throw new Error("Feature API not available");
    }
  });

  // Setup for each test
  test.beforeEach(async ({ page }) => {
    await page.goto("/app/feature");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Feature Title")).toBeVisible({
      timeout: 10000,
    });
  });

  test("should perform action", async ({ page }) => {
    // Arrange: Set up test data via API
    const testData = await apiRequest(page, "/api/feature", {
      method: "POST",
      body: { name: "Test" },
    });

    // Act: Perform the action being tested
    const button = page.locator('[data-testid="action-button"]');
    await expect(button).toBeVisible();
    await button.click();

    // Assert: Verify the outcome
    await expect(page.locator('[data-testid="result"]')).toBeVisible({
      timeout: 5000,
    });

    // Verify backend state
    const response = await apiRequest(page, `/api/feature/${testData.id}`);
    expect(response.status).toBe("completed");
  });
});
```

---

## Common Pitfalls to Avoid

1. **Don't use `page.waitForTimeout()` except for small delays after animations**
2. **Don't use `.catch(() => false)` to hide errors - use explicit condition waiting**
3. **Don't assume external services are available - mock them**
4. **Don't create complex CSS selectors - use data-testid or semantic selectors**
5. **Don't test implementation details - test user-visible behavior**
6. **Don't share state between tests - each test should be independent**
7. **Don't create test data through the UI - use API calls**
8. **Don't write mega-tests that test everything - keep tests focused**
9. **Don't ignore flaky tests - fix them or remove them**
10. **Don't forget to clean up test data (when needed)**

---

## Running Tests

```bash
# Run all tests
npm run test:e2e

# Run with UI mode (recommended for development)
npm run test:e2e:ui

# Run specific test file
npx playwright test e2e/tests/reference-search.spec.ts

# Run in headed mode (see the browser)
npm run test:e2e:headed

# Debug a specific test
npm run test:e2e:debug
```

---

## Measuring Test Quality

Good e2e tests should be:

- **Fast**: Most tests complete in < 10 seconds
- **Reliable**: Pass rate > 95% on every run
- **Clear**: Failures have obvious causes
- **Focused**: Each test validates one behavior
- **Independent**: Can run in any order
- **Maintainable**: Easy to update when features change

---

## References

- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Test Isolation](https://playwright.dev/docs/test-isolation)
- [Locators](https://playwright.dev/docs/locators)
- [Auto-waiting](https://playwright.dev/docs/actionability)
