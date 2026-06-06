import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Definition Refinement Run, Review, and Apply", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Navigate to Pipeline Hub and Locate Definition Refinement Pipeline Type", async ({
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

    // Locate Definition Refinement pipeline type card
    const defRefCard = page.getByTestId(
      "pipeline-type-card-definition_refinement",
    );
    await expect(defRefCard).toBeVisible();

    // Verify Run button is visible and enabled
    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
  });

  test("Test Case 2: Open Definition Refinement Wizard and Select Class", async ({
    page,
  }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class for Refinement",
    });

    // Navigate to pipelines page
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Click Run button on Definition Refinement card
    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await runButton.click();

    // Wait for wizard to open
    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select a class from the picker
    const classPickerInput = page.getByTestId(
      "definition-refinement-class",
    );
    await expect(classPickerInput).toBeVisible();
    await classPickerInput.click();

    // Type to search for the test class
    await classPickerInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    // Select from dropdown
    const classOption = page
      .getByRole("option")
      .filter({ hasText: testClass.title });
    await expect(classOption).toBeVisible();
    await classOption.first().click();

    // Verify class is selected
    await expect(classPickerInput).toHaveValue(testClass.title);
  });

  test("Test Case 3: Review Current Definition and Neighborhood Context", async ({
    page,
  }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class",
      description: "Initial class definition",
    });

    // Navigate to pipelines and open wizard
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await runButton.click();

    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select class
    const classPickerInput = page.getByTestId(
      "definition-refinement-class",
    );
    await classPickerInput.click();
    await classPickerInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page
      .getByRole("option")
      .filter({ hasText: testClass.title });
    await classOption.first().click();

    // Verify neighborhood panel is visible
    const neighborhoodPanel = page.getByTestId(
      "definition-refinement-neighborhood",
    );
    await expect(neighborhoodPanel).toBeVisible();

    // Verify definition textarea is visible
    const definitionTextarea = page.getByTestId(
      "definition-refinement-definition",
    );
    await expect(definitionTextarea).toBeVisible();
  });

  test("Test Case 4: Submit Wizard and Wait for Pipeline Execution", async ({
    page,
  }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class",
    });

    // Navigate and open wizard
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await runButton.click();

    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select class
    const classPickerInput = page.getByTestId(
      "definition-refinement-class",
    );
    await classPickerInput.click();
    await classPickerInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page
      .getByRole("option")
      .filter({ hasText: testClass.title });
    await classOption.first().click();

    // Verify Submit button is enabled
    const submitButton = page.getByTestId("definition-refinement-submit");
    await expect(submitButton).toBeVisible();
    await expect(submitButton).toBeEnabled();

    // Click Submit
    await submitButton.click();

    // Wait for loading state
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });

    // Wait for run to complete (not stuck in loading)
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });
  });

  test("Test Case 5: Review Candidate Definitions", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class",
      description: "Original definition",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await runButton.click();

    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select class
    const classPickerInput = page.getByTestId(
      "definition-refinement-class",
    );
    await classPickerInput.click();
    await classPickerInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page
      .getByRole("option")
      .filter({ hasText: testClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("definition-refinement-submit");
    await submitButton.click();

    // Wait for loading to complete
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Verify review panel appears
    const reviewPanel = page.getByTestId("definition-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Verify current definition radio option exists
    const currentDefRadio = page.getByTestId(
      "definition-refinement-radio-current",
    );
    await expect(currentDefRadio).toBeVisible();

    // Verify at least one candidate definition exists
    const candidateRadios = page.locator(
      '[data-testid^="definition-refinement-radio-candidate-"]',
    );
    const count = await candidateRadios.count();
    expect(count).toBeGreaterThan(0);
  });

  test("Test Case 6: Select a Candidate Definition", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class",
      description: "Original definition",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await runButton.click();

    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select class
    const classPickerInput = page.getByTestId(
      "definition-refinement-class",
    );
    await classPickerInput.click();
    await classPickerInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page
      .getByRole("option")
      .filter({ hasText: testClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("definition-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("definition-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Get candidate radio buttons
    const candidateRadios = page.locator(
      '[data-testid^="definition-refinement-radio-candidate-"]',
    );
    const count = await candidateRadios.count();
    expect(count).toBeGreaterThan(0);

    // Click first candidate radio button
    const firstCandidate = candidateRadios.first();
    await firstCandidate.click();

    // Verify it's selected
    const firstCandidateInput = firstCandidate.locator("input");
    await expect(firstCandidateInput).toBeChecked();

    // Verify Apply button is enabled
    const applyButton = page.getByTestId("run-apply-button");
    await expect(applyButton).toBeVisible();
    await expect(applyButton).toBeEnabled();
  });

  test("Test Case 7: Click Apply Button and Confirm Application", async ({
    page,
  }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class",
      description: "Original definition",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await runButton.click();

    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select class
    const classPickerInput = page.getByTestId(
      "definition-refinement-class",
    );
    await classPickerInput.click();
    await classPickerInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page
      .getByRole("option")
      .filter({ hasText: testClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("definition-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("definition-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Select first candidate
    const candidateRadios = page.locator(
      '[data-testid^="definition-refinement-radio-candidate-"]',
    );
    const count = await candidateRadios.count();
    expect(count).toBeGreaterThan(0);

    const firstCandidate = candidateRadios.first();
    await firstCandidate.click();

    // Verify Apply controls section is visible
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
    const confirmButton = confirmDialog.getByTestId(
      "confirm-dialog-confirm",
    );
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();
  });

  test("Test Case 8: Verify Apply Result Summary", async ({ page }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class",
      description: "Original definition",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await runButton.click();

    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select class
    const classPickerInput = page.getByTestId(
      "definition-refinement-class",
    );
    await classPickerInput.click();
    await classPickerInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page
      .getByRole("option")
      .filter({ hasText: testClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("definition-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("definition-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Select first candidate
    const candidateRadios = page.locator(
      '[data-testid^="definition-refinement-radio-candidate-"]',
    );
    const count = await candidateRadios.count();
    expect(count).toBeGreaterThan(0);

    const firstCandidate = candidateRadios.first();
    await firstCandidate.click();

    // Click Apply button
    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    // Confirm
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 10000 });

    const confirmButton = confirmDialog.getByTestId(
      "confirm-dialog-confirm",
    );
    await confirmButton.click();

    // Wait for apply result panel to appear
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 30000 });

    // Verify success state (no error messages)
    const errorBanner = page.getByTestId("error-banner");
    await expect(errorBanner).not.toBeVisible();
  });

  test("Test Case 9: Navigate to Classes Page and Verify Updated Definition", async ({
    page,
  }) => {
    // Create test ontology
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
    });
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class for Definition Update",
      description: "Original definition",
    });

    // Navigate and run pipeline
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    const runButton = page.getByTestId(
      "pipeline-run-button-definition_refinement",
    );
    await runButton.click();

    const wizard = page.getByTestId("definition-refinement-wizard");
    await expect(wizard).toBeVisible();

    // Select class
    const classPickerInput = page.getByTestId(
      "definition-refinement-class",
    );
    await classPickerInput.click();
    await classPickerInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    const classOption = page
      .getByRole("option")
      .filter({ hasText: testClass.title });
    await classOption.first().click();

    // Submit wizard
    const submitButton = page.getByTestId("definition-refinement-submit");
    await submitButton.click();

    // Wait for pipeline completion
    const loadingState = page.getByTestId("definition-refinement-loading");
    await expect(loadingState).toBeVisible({ timeout: 10000 });
    await expect(loadingState).not.toBeVisible({ timeout: 60000 });

    // Wait for review panel
    const reviewPanel = page.getByTestId("definition-refinement-review");
    await expect(reviewPanel).toBeVisible();

    // Select and apply first candidate
    const candidateRadios = page.locator(
      '[data-testid^="definition-refinement-radio-candidate-"]',
    );
    const count = await candidateRadios.count();
    expect(count).toBeGreaterThan(0);

    const firstCandidate = candidateRadios.first();
    await firstCandidate.click();

    // Apply
    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    // Confirm
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 10000 });

    const confirmButton = confirmDialog.getByTestId(
      "confirm-dialog-confirm",
    );
    await confirmButton.click();

    // Wait for apply result
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 30000 });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Verify classes page loads
    await expect(page.getByTestId("classes-page")).toBeVisible();

    // Search for the test class
    const searchInput = page.getByPlaceholder(/search/i).first();
    await searchInput.fill(testClass.title);
    await page.waitForLoadState("networkidle");

    // Click on the class row
    const classRow = page
      .getByRole("row")
      .filter({ hasText: testClass.title });
    await expect(classRow).toBeVisible();
    await classRow.click();

    // Verify class detail drawer shows updated content
    const classInspector = page.getByTestId("class-inspector");
    await expect(classInspector).toBeVisible();

    // Verify description field is updated
    const descriptionField = classInspector.getByTestId(
      "class-drawer-description-input",
    );
    await expect(descriptionField).toBeVisible();
  });
});
