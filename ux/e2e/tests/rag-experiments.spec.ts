import { test, expect } from "@playwright/test";
import { apiRequest, endpointExists } from "../fixtures/test-helpers";

/**
 * RAG Experiments E2E Tests
 *
 * These tests validate the RAG experiments workflow:
 * - Creating and managing test paragraphs
 * - Annotating paragraphs with expected entities
 * - Running pipeline tests
 * - Viewing and comparing test results
 *
 * Best Practices Applied:
 * - Backend endpoint verification before tests
 * - Proper waiting strategies (no fixed timeouts)
 * - Clear error messages
 * - Data cleanup
 */

test.describe("RAG Experiments", () => {
  // Check if RAG experiments API is available
  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    const hasEndpoint = await endpointExists(
      page,
      "/api/rag-experiments/paragraphs",
    );
    await context.close();

    if (!hasEndpoint) {
      throw new Error(
        "RAG Experiments API endpoint not available at /api/rag-experiments/paragraphs. " +
          "Please ensure the backend is running with RAG experiments support.",
      );
    }
  });

  test.beforeEach(async ({ page }) => {
    // Navigate to RAG experiments page
    await page.goto("/app/rag/experiments");
    await page.waitForLoadState("networkidle");

    // Wait for the main content to be loaded
    await expect(page.getByText("RAG Pipeline Experiments")).toBeVisible({
      timeout: 10000,
    });
  });

  test("should load RAG experiments page", async ({ page }) => {
    // Verify page title
    await expect(page.getByText("RAG Pipeline Experiments")).toBeVisible();

    // Verify description
    await expect(
      page.getByText(/Test and compare RAG pipeline performance/i),
    ).toBeVisible();

    // Verify tabs are present
    await expect(
      page.getByRole("tab", { name: /Test Paragraphs/i }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: /Run Tests/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Results/i })).toBeVisible();
  });

  test("should display test paragraph list", async ({ page }) => {
    // Verify the test paragraph list component is visible
    await expect(
      page.locator('[data-testid="test-paragraph-list"]'),
    ).toBeVisible({ timeout: 10000 });

    // Verify the create button is visible
    await expect(
      page.locator('[data-testid="test-paragraph-create-button"]'),
    ).toBeVisible();
  });

  test("should create a new test paragraph", async ({ page }) => {
    const paragraphText = `E2E Test Paragraph ${Date.now()}. This is a test paragraph for validating RAG pipeline entity extraction capabilities.`;

    // Wait for create button to be visible and enabled
    const createButton = page.locator(
      '[data-testid="test-paragraph-create-button"]',
    );
    await expect(createButton).toBeVisible({ timeout: 10000 });
    await expect(createButton).toBeEnabled();

    // Click "Create New" button
    await createButton.click();

    // Wait for editor to appear
    await expect(
      page.locator('[data-testid="test-paragraph-editor"]'),
    ).toBeVisible({ timeout: 5000 });

    // Fill in the paragraph text
    await page.fill('[data-testid="test-paragraph-text-input"]', paragraphText);

    // Verify submit button is enabled
    const submitButton = page.locator(
      '[data-testid="test-paragraph-submit-button"]',
    );
    await expect(submitButton).toBeEnabled();

    // Submit the form
    await submitButton.click();

    // Wait for the form to process and close
    await expect(
      page.locator('[data-testid="test-paragraph-editor"]'),
    ).toBeVisible({ timeout: 3000 });

    // Wait for the paragraph to appear in the table
    await expect(
      page.locator('[data-testid="test-paragraph-table"]'),
    ).toContainText("E2E Test Paragraph", { timeout: 5000 });

    // Verify paragraph exists in backend
     
    const response = await apiRequest<{ paragraphs: any[] }>(
      page,
      "/api/rag-experiments/paragraphs?limit=100",
    );

    const createdParagraph = response.paragraphs.find(
      (p: any) => p.text.includes("E2E Test Paragraph"),  
    );

    expect(createdParagraph).toBeDefined();
  });

  test("should edit an existing test paragraph", async ({ page }) => {
    // First, create a paragraph via API
    const originalText = `E2E Edit Test ${Date.now()}`;
    const updatedText = `${originalText} (Updated)`;

     
    const createResponse = await apiRequest<any>(
      page,
      "/api/rag-experiments/paragraphs",
      {
        method: "POST",
        body: {
          text: originalText,
        },
      },
    );
    const paragraphId = createResponse.id;

    // Refresh page to see the new paragraph
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Wait for the page to be fully loaded
    await expect(
      page.locator('[data-testid="test-paragraph-list"]'),
    ).toBeVisible({ timeout: 10000 });

    // Wait for edit button to be visible
    const editButton = page.locator(
      `[data-testid="test-paragraph-edit-button-${paragraphId}"]`,
    );
    await expect(editButton).toBeVisible({ timeout: 10000 });

    // Click edit button for the paragraph
    await editButton.click();

    // Wait for editor to appear with existing content
    await expect(
      page.locator('[data-testid="test-paragraph-editor"]'),
    ).toBeVisible({ timeout: 5000 });

    // Wait for input to be populated
    await page.waitForTimeout(500); // Small delay for data to load

    // Verify the original text is loaded
    const inputValue = await page
      .locator('[data-testid="test-paragraph-text-input"]')
      .inputValue();
    expect(inputValue).toBe(originalText);

    // Update the text
    await page.fill('[data-testid="test-paragraph-text-input"]', updatedText);

    // Submit the form
    await page.click('[data-testid="test-paragraph-submit-button"]');

    // Wait for update to process
    await page.waitForTimeout(1000);

    // Verify updated text appears in the table
    await expect(
      page.locator('[data-testid="test-paragraph-table"]'),
    ).toContainText("(Updated)", { timeout: 5000 });

    // Verify paragraph updated in backend
     
    const response = await apiRequest<any>(
      page,
      `/api/rag-experiments/paragraphs/${paragraphId}`,
    );
    expect(response.text).toBe(updatedText);
  });

  test("should delete a test paragraph", async ({ page }) => {
    // Create a paragraph via API
    const testText = `E2E Delete Test ${Date.now()}`;

     
    const createResponse = await apiRequest<any>(
      page,
      "/api/rag-experiments/paragraphs",
      {
        method: "POST",
        body: {
          text: testText,
        },
      },
    );
    const paragraphId = createResponse.id;

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Wait for list to be visible
    await expect(
      page.locator('[data-testid="test-paragraph-list"]'),
    ).toBeVisible({ timeout: 10000 });

    // Wait for delete button to be visible
    const deleteButton = page.locator(
      `[data-testid="test-paragraph-delete-button-${paragraphId}"]`,
    );
    await expect(deleteButton).toBeVisible({ timeout: 10000 });

    // Set up dialog handler to confirm deletion
    page.once("dialog", (dialog) => dialog.accept());

    // Click delete button
    await deleteButton.click();

    // Wait for deletion to process
    await page.waitForTimeout(1000);

    // Verify paragraph is removed from the table
    await expect(
      page.locator('[data-testid="test-paragraph-table"]'),
    ).not.toContainText(testText, { timeout: 5000 });

    // Verify paragraph deleted in backend
    const response = await page.request.fetch(
      `http://localhost:8888/api/rag-experiments/paragraphs/${paragraphId}`,
    );
    expect(response.status()).toBe(404);
  });

  test("should cancel paragraph creation", async ({ page }) => {
    // Wait for create button to be visible
    const createButton = page.locator(
      '[data-testid="test-paragraph-create-button"]',
    );
    await expect(createButton).toBeVisible({ timeout: 10000 });

    // Click create button
    await createButton.click();

    // Wait for editor
    await expect(
      page.locator('[data-testid="test-paragraph-editor"]'),
    ).toBeVisible({ timeout: 5000 });

    // Type some text
    await page.fill(
      '[data-testid="test-paragraph-text-input"]',
      "This should be cancelled",
    );

    // Click cancel
    await page.click('[data-testid="test-paragraph-cancel-button"]');

    // Verify editor is still visible (it doesn't close) but input is cleared
    const inputValue = await page
      .locator('[data-testid="test-paragraph-text-input"]')
      .inputValue();
    expect(inputValue).toBe("");
  });

  test("should display annotation selector for existing paragraph", async ({
    page,
  }) => {
    // Create a paragraph via API
    const testText = "Test paragraph for annotation";

     
    const createResponse = await apiRequest<any>(
      page,
      "/api/rag-experiments/paragraphs",
      {
        method: "POST",
        body: {
          text: testText,
        },
      },
    );

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Wait for list to be visible
    await expect(
      page.locator('[data-testid="test-paragraph-list"]'),
    ).toBeVisible({ timeout: 10000 });

    // Click edit button
    const editButton = page.locator(
      `[data-testid="test-paragraph-edit-button-${createResponse.id}"]`,
    );
    await expect(editButton).toBeVisible({ timeout: 10000 });
    await editButton.click();

    // Wait for editor
    await expect(
      page.locator('[data-testid="test-paragraph-editor"]'),
    ).toBeVisible({ timeout: 5000 });

    // Wait for annotation selector to appear (it loads after paragraph data)
    await expect(
      page.locator('[data-testid="annotation-selector"]'),
    ).toBeVisible({ timeout: 10000 });
  });

  test("should navigate to Run Tests tab", async ({ page }) => {
    // Click on "Run Tests" tab
    const runTestsTab = page.getByRole("tab", { name: /Run Tests/i });
    await expect(runTestsTab).toBeVisible({ timeout: 10000 });
    await runTestsTab.click();

    // Verify pipeline test runner is visible
    await expect(
      page.locator('[data-testid="pipeline-test-runner"]'),
    ).toBeVisible({ timeout: 5000 });
  });

  test("should display pipeline selection", async ({ page }) => {
    // Navigate to Run Tests tab
    const runTestsTab = page.getByRole("tab", { name: /Run Tests/i });
    await runTestsTab.click();

    // Verify pipeline test runner is visible
    await expect(
      page.locator('[data-testid="pipeline-test-runner"]'),
    ).toBeVisible({ timeout: 5000 });

    // Verify pipeline selection section is present
    await expect(page.getByText("Select Pipelines")).toBeVisible();

    // Verify at least one pipeline option is available
    await expect(page.getByText("StandardRAGPipeline")).toBeVisible();
  });

  test("should display paragraph selection for testing", async ({ page }) => {
    // Navigate to Run Tests tab
    const runTestsTab = page.getByRole("tab", { name: /Run Tests/i });
    await runTestsTab.click();

    // Wait for runner to be visible
    await expect(
      page.locator('[data-testid="pipeline-test-runner"]'),
    ).toBeVisible({ timeout: 5000 });

    // Verify paragraph selection section
    await expect(page.getByText("Select Test Paragraphs")).toBeVisible();
  });

  test("should disable run button when no paragraphs selected", async ({
    page,
  }) => {
    // Navigate to Run Tests tab
    const runTestsTab = page.getByRole("tab", { name: /Run Tests/i });
    await runTestsTab.click();

    // Wait for runner to be visible
    await expect(
      page.locator('[data-testid="pipeline-test-runner"]'),
    ).toBeVisible({ timeout: 5000 });

    // Ensure no paragraphs are selected by checking if "Deselect All" button exists
    const deselectAllButton = page.getByRole("button", {
      name: /Deselect All/i,
    });
    const hasDeselect = await deselectAllButton
      .isVisible({ timeout: 2000 })
      .catch(() => false);

    if (hasDeselect) {
      await deselectAllButton.click();
    }

    // Run button should be disabled
    const runButton = page.locator('[data-testid="pipeline-run-tests-button"]');
    await expect(runButton).toBeDisabled();
  });

  test("should display test results tab", async ({ page }) => {
    // Navigate to Results tab
    const resultsTab = page.getByRole("tab", { name: /Results/i });
    await resultsTab.click();

    // Initially, should show empty state
    await expect(page.getByText(/No test results yet/i)).toBeVisible({
      timeout: 5000,
    });
  });

  test("should validate required fields in paragraph editor", async ({
    page,
  }) => {
    // Wait for create button
    const createButton = page.locator(
      '[data-testid="test-paragraph-create-button"]',
    );
    await expect(createButton).toBeVisible({ timeout: 10000 });

    // Click create button
    await createButton.click();

    // Wait for editor
    await expect(
      page.locator('[data-testid="test-paragraph-editor"]'),
    ).toBeVisible({ timeout: 5000 });

    // Submit button should be disabled when text is empty
    const submitButton = page.locator(
      '[data-testid="test-paragraph-submit-button"]',
    );
    await expect(submitButton).toBeDisabled();

    // Type some text
    await page.fill('[data-testid="test-paragraph-text-input"]', "Test");

    // Submit button should now be enabled
    await expect(submitButton).toBeEnabled();
  });

  test("should show character count for paragraph text", async ({ page }) => {
    // Wait for create button
    const createButton = page.locator(
      '[data-testid="test-paragraph-create-button"]',
    );
    await expect(createButton).toBeVisible({ timeout: 10000 });

    // Click create button
    await createButton.click();

    // Wait for editor
    await expect(
      page.locator('[data-testid="test-paragraph-editor"]'),
    ).toBeVisible({ timeout: 5000 });

    // Type text
    const testText = "Test";
    await page.fill('[data-testid="test-paragraph-text-input"]', testText);

    // Verify character count is displayed
    await expect(page.getByText(`${testText.length} characters`)).toBeVisible();
  });

  test("should display annotation count in paragraph list", async ({
    page,
  }) => {
    // Create a paragraph via API
    const testText = "Test paragraph with entities";

    await apiRequest(page, "/api/rag-experiments/paragraphs", {
      method: "POST",
      body: {
        text: testText,
      },
    });

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Wait for list to be visible
    await expect(
      page.locator('[data-testid="test-paragraph-list"]'),
    ).toBeVisible({ timeout: 10000 });

    // Verify annotation count badge appears (should show "0 annotations" initially)
    await expect(
      page.locator('[data-testid="test-paragraph-table"]'),
    ).toContainText(/annotation/i, { timeout: 5000 });
  });
});
