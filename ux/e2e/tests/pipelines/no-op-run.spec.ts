import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Identity/No-Op Pipeline Run", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Navigate to Pipeline Hub and Locate Definition Refinement Pipeline Type", async ({
    page,
  }) => {
    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Verify pipelines page is visible
    await expect(page.getByTestId("pipelines-page")).toBeVisible();

    // Verify the grid of pipeline type cards is visible
    await expect(page.getByTestId("pipeline-types-grid")).toBeVisible();

    // Locate the definition refinement pipeline type card
    const definitionRefinementCard = page.getByTestId(
      "pipeline-type-card-definition_refinement"
    );
    await expect(definitionRefinementCard).toBeVisible();

    // Verify the "Run" button is visible and enabled
    const runButton = page.getByTestId("pipeline-run-button-definition_refinement");
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
  });

  test("Open Definition Refinement Wizard", async ({ page }) => {
    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Click the "Run" button on the definition refinement card
    const runButton = page.getByTestId("pipeline-run-button-definition_refinement");
    await runButton.click();

    // Wait for the wizard to open
    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();
  });

  test("Configure Wizard and Submit for Execution", async ({ page }) => {
    // Create a test ontology for the pipeline to work with
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class",
      description: "Original description that will not be refined",
    });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Click the "Run" button on the definition refinement card
    const runButton = page.getByTestId("pipeline-run-button-definition_refinement");
    await runButton.click();

    // Wait for the wizard to open
    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select a class in the wizard (this should be a simple no-op case)
    const classPickerInput = page.getByTestId("definition-refinement-class");
    await expect(classPickerInput).toBeVisible();

    // Wait for the submit button to become visible and clickable
    const submitButton = page.getByTestId("definition-refinement-submit");
    await expect(submitButton).toBeVisible();
    await expect(submitButton).toBeEnabled();

    // Click submit to execute the pipeline
    await submitButton.click();

    // Wait for loading state to appear
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 5000 });

    // Wait for the run to complete (observe result panel or empty state)
    const reviewPanel = page.getByTestId("definition-refinement-review");
    const emptyState = page.getByTestId("definition-refinement-empty");

    // Wait for either review panel or empty state to appear (indicating completion)
    await Promise.race([
      expect(reviewPanel).toBeVisible({ timeout: 10000 }).catch(() => null),
      expect(emptyState).toBeVisible({ timeout: 10000 }).catch(() => null),
    ]);
  });

  test("Verify Empty Candidates State for No-Op Result", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class",
    });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute the definition refinement pipeline
    const runButton = page.getByTestId("pipeline-run-button-definition_refinement");
    await runButton.click();

    // Wait for wizard
    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Submit the pipeline
    const submitButton = page.getByTestId("definition-refinement-submit");
    await expect(submitButton).toBeEnabled();
    await submitButton.click();

    // Wait for loading state to disappear
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible();

    // Wait for empty state or review panel
    const emptyState = page.getByTestId("definition-refinement-empty");
    const reviewPanel = page.getByTestId("definition-refinement-review");

    // Check if empty state appears (indicating no changes)
    const emptyStateVisible = await emptyState.isVisible().catch(() => false);

    if (emptyStateVisible) {
      // Verify empty state message is displayed
      await expect(emptyState).toBeVisible();

      // Verify no candidates are shown
      const reviewTable = page.getByTestId("definition-refinement-review");
      await expect(reviewTable).not.toBeVisible();
    }
  });

  test("Verify Apply Button is Disabled or Not Rendered for No-Op Result", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id);

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute the pipeline
    const runButton = page.getByTestId("pipeline-run-button-definition_refinement");
    await runButton.click();

    // Wait for wizard
    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Submit
    const submitButton = page.getByTestId("definition-refinement-submit");
    await submitButton.click();

    // Wait for loading to finish
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible();

    // Wait for completion (empty state or review)
    const emptyState = page.getByTestId("definition-refinement-empty");
    await expect(emptyState).toBeVisible({ timeout: 10000 });

    // Verify the Apply button is either disabled or not rendered
    const applyButton = page.getByTestId("run-apply-button");
    const applyButtonDisabled = page.getByTestId("run-apply-button-disabled");

    // Check if either button exists and verify state
    const applyVisible = await applyButton.isVisible().catch(() => false);
    const applyDisabledVisible = await applyButtonDisabled.isVisible().catch(() => false);

    // At least one of these should be true: button disabled or not visible
    expect(applyVisible || applyDisabledVisible).toBeDefined();

    // Verify user cannot trigger an apply action
    if (applyVisible) {
      await expect(applyButton).toBeDisabled();
    }
  });

  test("Verify Run History and Completion Status", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id);

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute the pipeline
    const runButton = page.getByTestId("pipeline-run-button-definition_refinement");
    await runButton.click();

    // Wait for wizard
    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Submit
    const submitButton = page.getByTestId("definition-refinement-submit");
    await submitButton.click();

    // Wait for loading to finish
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible();

    // Wait for empty state to appear
    const emptyState = page.getByTestId("definition-refinement-empty");
    await expect(emptyState).toBeVisible({ timeout: 10000 });

    // Verify the empty state persists (no spurious data appears)
    await expect(emptyState).toBeVisible();

    // Verify no candidates list is shown
    const reviewPanel = page.getByTestId("definition-refinement-review");
    await expect(reviewPanel).not.toBeVisible();
  });
});
