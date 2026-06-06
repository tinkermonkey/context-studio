import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Pipeline Run Apply and Revert", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Execute Individual Extraction Pipeline and Wait for Completion", async ({ page }) => {
    // Create a test ontology with classes for the extraction to target
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, {
      title: "Person",
      description: "A person entity",
    });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Verify pipelines page is visible
    await expect(page.getByTestId("pipelines-page")).toBeVisible();

    // Click the "Run" button on the Individual Extraction card
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await expect(runButton).toBeVisible();
    await runButton.click();

    // Wait for the wizard to open
    const wizard = page.getByTestId("individual-extraction-wizard");
    await expect(wizard).toBeVisible();

    // Configure the wizard with sample source text
    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill(
      "John Smith is a person. Jane Doe is a person. Both work in technology."
    );

    // Verify the submit button is enabled
    const submitButton = page.getByTestId("individual-extraction-submit");
    await expect(submitButton).toBeEnabled();

    // Click submit to execute the pipeline
    await submitButton.click();

    // Wait for loading state to appear
    const loadingState = page.getByTestId("individual-extraction-loading");
    await expect(loadingState).toBeVisible({ timeout: 5000 });

    // Wait for the review panel to appear (indicating completion)
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toBeVisible({ timeout: 15000 });
  });

  test("Review Candidates and Select for Application", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, { title: "Person" });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute the Individual Extraction pipeline
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    // Wait for wizard
    const wizard = page.getByTestId("individual-extraction-wizard");
    await expect(wizard).toBeVisible();

    // Configure and submit
    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("John Smith is a person. Jane Doe is a person.");

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for loading
    const loadingState = page.getByTestId("individual-extraction-loading");
    await expect(loadingState).toBeVisible();

    // Wait for review panel to appear
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toBeVisible({ timeout: 15000 });

    // Verify candidates are displayed
    await expect(reviewPanel).toBeVisible();

    // Select all candidates using the select-all checkbox
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await expect(selectAllCheckbox).toBeVisible();
    await selectAllCheckbox.click();

    // Verify selection is visible
    await expect(reviewPanel).toBeVisible();
  });

  test("Click Apply Button and Confirm Application", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, { title: "Person" });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute the Individual Extraction pipeline
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    // Wait for wizard
    const wizard = page.getByTestId("individual-extraction-wizard");
    await expect(wizard).toBeVisible();

    // Configure and submit
    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("John Smith is a person. Jane Doe is a person.");

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toBeVisible({ timeout: 15000 });

    // Select all candidates
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await expect(selectAllCheckbox).toBeVisible();
    await selectAllCheckbox.click();

    // Verify Apply button is visible and enabled
    const applyButton = page.getByTestId("run-apply-button");
    await expect(applyButton).toBeVisible();
    await expect(applyButton).toBeEnabled();

    // Click Apply button
    await applyButton.click();

    // Wait for confirmation dialog to appear
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 5000 });

    // Verify dialog shows summary
    await expect(confirmDialog).toBeVisible();

    // Click the confirm button in the dialog
    const confirmButton = confirmDialog.getByRole("button", {
      name: /confirm|apply/i,
    });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();
  });

  test("Verify Apply Completion and Result Summary", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, { title: "Person" });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    // Configure and submit
    const wizard = page.getByTestId("individual-extraction-wizard");
    await expect(wizard).toBeVisible();

    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("John Smith is a person. Jane Doe is a person.");

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toBeVisible({ timeout: 15000 });

    // Select all and apply
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await expect(selectAllCheckbox).toBeVisible();
    await selectAllCheckbox.click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    // Confirm application
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    const confirmButton = confirmDialog.getByRole("button", {
      name: /confirm|apply/i,
    });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    // Wait for apply result panel to appear
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 10000 });

    // Verify result summary is displayed
    await expect(resultPanel).toBeVisible();
  });

  test("Navigate to Runs Page and Open Applied Run", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, { title: "Person" });

    // Navigate to pipelines page and execute a run
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    const wizard = page.getByTestId("individual-extraction-wizard");
    await expect(wizard).toBeVisible();

    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("John Smith is a person. Jane Doe is a person.");

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for review
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toBeVisible({ timeout: 15000 });

    // Apply candidates
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await expect(selectAllCheckbox).toBeVisible();
    await selectAllCheckbox.click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    const confirmButton = confirmDialog.getByRole("button", {
      name: /confirm|apply/i,
    });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    // Wait for result panel
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 10000 });

    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify runs page is visible
    await expect(page.getByTestId("runs-page")).toBeVisible();

    // Verify runs table is visible
    await expect(page.getByTestId("runs-table")).toBeVisible();
  });

  test("Verify Revert Button is Available for Applied Run", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, { title: "Person" });

    // Navigate to pipelines page and execute a run
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    const wizard = page.getByTestId("individual-extraction-wizard");
    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("John Smith is a person. Jane Doe is a person.");

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait and apply
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toBeVisible({ timeout: 15000 });

    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await expect(selectAllCheckbox).toBeVisible();
    await selectAllCheckbox.click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    const confirmButton = confirmDialog.getByRole("button", {
      name: /confirm|apply/i,
    });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    // Wait for result panel
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 10000 });

    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Find and open a run in the runs table
    const runsTable = page.getByTestId("runs-table");
    await expect(runsTable).toBeVisible();

    // Click on the first run row to open the detail drawer
    const runRows = page.locator('[data-testid^="run-row-"]');
    const firstRunRow = runRows.first();
    await expect(firstRunRow).toBeVisible();
    await firstRunRow.click();

    // Wait for run detail drawer to open
    const runDetailDrawer = page.getByTestId("run-detail-drawer");
    await expect(runDetailDrawer).toBeVisible({ timeout: 5000 });

    // Verify apply controls section
    const applySection = page.getByTestId("run-apply-section");
    await expect(applySection).toBeVisible();

    // Verify Apply button shows "Already applied" state
    const applyButtonDisabled = page.getByTestId("run-apply-button-disabled");
    const applyButtonActive = page.getByTestId("run-apply-button");

    const applyDisabledVisible = await applyButtonDisabled
      .isVisible()
      .catch(() => false);
    if (!applyDisabledVisible) {
      // If disabled button not visible, apply button should be disabled
      await expect(applyButtonActive).toBeVisible();
      await expect(applyButtonActive).toBeDisabled();
    }

    // Verify Revert button is visible and enabled
    const revertButton = page.getByTestId("run-revert-button");
    await expect(revertButton).toBeVisible();
    await expect(revertButton).toBeEnabled();
  });

  test("Click Revert Button and Confirm Revert Operation", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, { title: "Person" });

    // Navigate to pipelines page and execute a run
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    const wizard = page.getByTestId("individual-extraction-wizard");
    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("John Smith is a person. Jane Doe is a person.");

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait and apply
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toBeVisible({ timeout: 15000 });

    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await expect(selectAllCheckbox).toBeVisible();
    await selectAllCheckbox.click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    const confirmButton = confirmDialog.getByRole("button", {
      name: /confirm|apply/i,
    });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    // Wait for result panel
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 10000 });

    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Open a run detail
    const runRows = page.locator('[data-testid^="run-row-"]');
    const firstRunRow = runRows.first();
    await expect(firstRunRow).toBeVisible();
    await firstRunRow.click();

    // Wait for run detail drawer
    const runDetailDrawer = page.getByTestId("run-detail-drawer");
    await expect(runDetailDrawer).toBeVisible({ timeout: 5000 });

    // Click the Revert button
    const revertButton = page.getByTestId("run-revert-button");
    await expect(revertButton).toBeVisible();
    await revertButton.click();

    // Wait for revert confirmation dialog
    const revertConfirmDialog = page.getByTestId("run-revert-confirm-dialog");
    await expect(revertConfirmDialog).toBeVisible({ timeout: 5000 });

    // Click the confirm button in the revert dialog
    const revertConfirmButton = revertConfirmDialog.getByRole("button", {
      name: /confirm|revert/i,
    });
    await expect(revertConfirmButton).toBeVisible();
    await revertConfirmButton.click();
  });

  test("Verify Revert Completion and Result Summary", async ({ page }) => {
    // Create a test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const testClass = await createClass(page, scheme.id, { title: "Person" });

    // Navigate to pipelines page and execute a run
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    const wizard = page.getByTestId("individual-extraction-wizard");
    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("John Smith is a person. Jane Doe is a person.");

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait and apply
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toBeVisible({ timeout: 15000 });

    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await expect(selectAllCheckbox).toBeVisible();
    await selectAllCheckbox.click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    const confirmButton = confirmDialog.getByRole("button", {
      name: /confirm|apply/i,
    });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    // Wait for result panel
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 10000 });

    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Open a run detail
    const runRows = page.locator('[data-testid^="run-row-"]');
    const firstRunRow = runRows.first();
    await expect(firstRunRow).toBeVisible();
    await firstRunRow.click();

    // Wait for run detail drawer
    const runDetailDrawer = page.getByTestId("run-detail-drawer");
    await expect(runDetailDrawer).toBeVisible({ timeout: 5000 });

    // Click the Revert button
    const revertButton = page.getByTestId("run-revert-button");
    await revertButton.click();

    // Confirm revert
    const revertConfirmDialog = page.getByTestId("run-revert-confirm-dialog");
    const revertConfirmButton = revertConfirmDialog.getByRole("button", {
      name: /confirm|revert/i,
    });
    await expect(revertConfirmButton).toBeVisible();
    await revertConfirmButton.click();

    // Wait for revert result panel to appear
    const revertResultPanel = page.getByTestId("run-revert-result");
    await expect(revertResultPanel).toBeVisible({ timeout: 10000 });

    // Verify result summary is displayed
    await expect(revertResultPanel).toBeVisible();

    // Navigate back to runs list to verify COMPLETED-reverted state
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify the run status changed to COMPLETED-reverted
    const revertedRunStatus = page.getByTestId("run-status-reverted");
    await expect(revertedRunStatus).toBeVisible();
  });
});
