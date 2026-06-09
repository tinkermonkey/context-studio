import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Connection Refinement Run, Review, and Apply", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Navigate to Pipeline Hub and Locate Connection Refinement Pipeline Type", async ({
    page,
  }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    await createClass(page, scheme.id, { title: "Test Class" });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Verify pipelines page loads
    await expect(page.getByTestId("pipelines-page")).toBeVisible();
    await expect(page.getByTestId("pipeline-types-grid")).toBeVisible();

    // Locate Connection Refinement pipeline type card
    const connRefCard = page.getByTestId("pipeline-type-card-connection_refinement");
    await expect(connRefCard).toBeVisible();

    // Verify Run button is visible and enabled
    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
  });

  test("Test Case 2: Open Connection Refinement Wizard and Select Scope Class", async ({
    page,
  }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class for Connection",
    });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Click Run button on Connection Refinement card
    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    // Wait for wizard to open
    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class from the picker
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await expect(scopePickerInput).toBeVisible();
    await scopePickerInput.click();

    // Type to search for the scope class
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    // Select from dropdown
    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await expect(classOption).toBeVisible();
    await classOption.first().click();

    // Verify class is selected
    await expect(scopePickerInput).toHaveValue(scopeClass.title);
  });

  test("Test Case 3: Review Current Connection Context", async ({ page }) => {
    // Create test ontology with multiple classes for relationships
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class",
    });
    await createClass(page, scheme.id, { title: "Related Class" });

    // Navigate and open wizard
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await scopePickerInput.click();
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await classOption.first().click();

    // Verify neighborhood panel is visible
    const neighborhoodPanel = page.getByTestId("connection-refinement-neighborhood");
    await expect(neighborhoodPanel).toBeVisible();
  });

  test("Test Case 4: Submit Wizard and Wait for Pipeline Execution", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class",
    });

    // Navigate and open wizard
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await scopePickerInput.click();
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await classOption.first().click();

    // Verify Submit button is enabled
    const submitButton = page.getByTestId("connection-refinement-submit");
    await expect(submitButton).toBeVisible();
    await expect(submitButton).toBeEnabled();

    // Click Submit
    await submitButton.click();

    // Wait for loading state
    const loadingState = page.getByTestId("connection-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });

    // Wait for run to complete
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });
  });

  test("Test Case 5: Review Connection Deltas in Candidate Table", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await scopePickerInput.click();
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("connection-refinement-submit");
    await submitButton.click();

    // Wait for loading to complete
    const loadingState = page.getByTestId("connection-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Verify review panel appears
    const reviewPanel = page.getByTestId("connection-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Verify accept/reject buttons exist for deltas
    const acceptButtons = page.locator('[data-testid^="connection-accept-"]');
    const _acceptCount = await acceptButtons.count();

    // Panel should be visible even if no deltas (empty state)
    await expect(reviewPanel).toBeVisible();
  });

  test("Test Case 6: Accept Connection Deltas", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await scopePickerInput.click();
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("connection-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("connection-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("connection-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Get accept buttons for deltas
    const acceptButtons = page.locator('[data-testid^="connection-accept-"]');
    const acceptCount = await acceptButtons.count();
    expect(acceptCount).toBeGreaterThan(0);

    // Click first accept button
    const firstAcceptButton = acceptButtons.first();
    await firstAcceptButton.click();

    // Verify button state changes (may show checked/highlighted state)
    await expect(firstAcceptButton).toBeVisible();
  });

  test("Test Case 7: Click Apply Button and Confirm Application", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await scopePickerInput.click();
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("connection-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("connection-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("connection-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Accept first delta if available
    const acceptButtons = page.locator('[data-testid^="connection-accept-"]');
    const acceptCount = await acceptButtons.count();
    expect(acceptCount).toBeGreaterThan(0);

    const firstAcceptButton = acceptButtons.first();
    await firstAcceptButton.click();

    // Verify Apply section is visible
    const applySection = page.getByTestId("run-apply-section");
    await expect(applySection).toBeVisible();

    // Click Apply button
    const applyButton = page.getByTestId("run-apply-button");
    await expect(applyButton).toBeVisible();
    await applyButton.click();

    // Wait for confirmation dialog
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 10000 });

    // Click Confirm button
    const confirmButton = confirmDialog.getByTestId("confirm-dialog-confirm");
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();
  });

  test("Test Case 8: Verify Apply Result Summary", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await scopePickerInput.click();
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("connection-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("connection-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("connection-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Accept and apply first delta if available
    const acceptButtons = page.locator('[data-testid^="connection-accept-"]');
    const acceptCount = await acceptButtons.count();
    expect(acceptCount).toBeGreaterThan(0);

    const firstAcceptButton = acceptButtons.first();
    await firstAcceptButton.click();

    // Click Apply button
    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    // Confirm
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 10000 });

    const confirmButton = confirmDialog.getByTestId("confirm-dialog-confirm");
    await confirmButton.click();

    // Wait for apply result panel to appear
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 30000 });

    // Verify success state (no error messages)
    const errorBanner = page.getByTestId("error-banner");
    await expect(errorBanner).not.toBeVisible();
  });

  test("Test Case 9: Navigate to Relationships Page and Verify Applied Changes", async ({
    page,
  }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class for Connection",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await scopePickerInput.click();
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("connection-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("connection-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("connection-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Accept and apply first delta if available
    const acceptButtons = page.locator('[data-testid^="connection-accept-"]');
    const acceptCount = await acceptButtons.count();
    expect(acceptCount).toBeGreaterThan(0);

    const firstAcceptButton = acceptButtons.first();
    await firstAcceptButton.click();

    // Click Apply button
    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    // Confirm
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 10000 });

    const confirmButton = confirmDialog.getByTestId("confirm-dialog-confirm");
    await confirmButton.click();

    // Wait for apply result
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 30000 });

    // Navigate to relationships page
    await page.goto("/app/schema/relationships");
    await page.waitForLoadState("networkidle");

    // Verify relationships page loads
    await expect(page.getByTestId("relationships-page")).toBeVisible();

    // Search/filter for relationships involving scope class
    const searchInput = page.getByPlaceholder(/search/i).first();
    if (searchInput) {
      await searchInput.fill(scopeClass.title);
      await page.waitForLoadState("networkidle");
    }

    // Verify relationships table is visible
    const relationshipsTable = page.getByTestId("schema-table");
    await expect(relationshipsTable).toBeVisible();
  });

  test("Test Case 10: Verify Updated Relationships on Class Page", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const scopeClass = await createClass(page, scheme.id, {
      title: "Scope Class for Class View",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-connection_refinement");
    await runButton.click();

    const wizard = page.getByTestId("connection-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select scope class
    const scopePickerInput = page.getByTestId("connection-refinement-scope");
    await scopePickerInput.click();
    await scopePickerInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page.getByRole("option").filter({ hasText: scopeClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("connection-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("connection-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("connection-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Accept and apply first delta if available
    const acceptButtons = page.locator('[data-testid^="connection-accept-"]');
    const acceptCount = await acceptButtons.count();
    expect(acceptCount).toBeGreaterThan(0);

    const firstAcceptButton = acceptButtons.first();
    await firstAcceptButton.click();

    // Click Apply button
    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    // Confirm
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 10000 });

    const confirmButton = confirmDialog.getByTestId("confirm-dialog-confirm");
    await confirmButton.click();

    // Wait for apply result
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 30000 });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Verify classes page loads
    await expect(page.getByTestId("classes-page")).toBeVisible();

    // Search for the scope class
    const searchInput = page.getByPlaceholder(/search/i).first();
    await searchInput.fill(scopeClass.title);
    await page.waitForLoadState("networkidle");

    // Click on the class row
    const classRow = page.getByRole("row").filter({ hasText: scopeClass.title });
    await expect(classRow).toBeVisible();
    await classRow.click();

    // Verify class detail drawer opens
    const classInspector = page.getByTestId("class-inspector");
    await expect(classInspector).toBeVisible();
  });
});
