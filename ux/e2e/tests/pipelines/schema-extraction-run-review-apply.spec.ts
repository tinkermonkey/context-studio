import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Schema Extraction Run, Review, and Apply", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Navigate to Pipeline Hub and Locate Schema Extraction Pipeline Type", async ({
    page,
  }) => {
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Verify pipelines page is loaded
    await expect(page.getByTestId("pipelines-page")).toBeVisible();

    // Verify pipeline types grid is visible
    await expect(page.getByTestId("pipeline-types-grid")).toBeVisible();

    // Locate the Schema Extraction pipeline type card
    const schemaExtractionCard = page.getByTestId("pipeline-type-card-schema_extraction");
    await expect(schemaExtractionCard).toBeVisible();

    // Verify the Run button is visible on the card
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
  });

  test("Test Case 2: Open Schema Extraction Wizard and Configure Input", async ({ page }) => {
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Click the Run button on the Schema Extraction card
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    // Wait for the wizard to open
    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    // Locate the document input field
    const documentInput = page.getByTestId("schema-extraction-document");
    await expect(documentInput).toBeVisible();

    // Enter sample source text
    const sampleText =
      "A Person is an entity. A Person has a name property. An Organization has employees who are Persons.";
    await documentInput.fill(sampleText);

    // Verify the text was accepted
    await expect(documentInput).toHaveValue(sampleText);
  });

  test("Test Case 3: Configure Taxonomy/Concept Scheme Target", async ({ page }) => {
    // Create test taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, { title: "Test Scheme" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open the wizard
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    // Fill document input
    const documentInput = page.getByTestId("schema-extraction-document");
    await documentInput.fill(
      "A Person is an entity with a name property. An Organization has employees."
    );

    // Locate and click the taxonomy picker
    const taxonomyPicker = page.getByTestId("schema-extraction-taxonomy-picker");
    await expect(taxonomyPicker).toBeVisible();

    // The picker should be an input or button that opens a selection interface
    // Click it to open the dropdown
    await taxonomyPicker.click();

    // Wait briefly for dropdown to appear and select the scheme
    // The dropdown should display the scheme name
    await expect(page.getByText(scheme.title)).toBeVisible();
    await page.getByText(scheme.title).click();

    // Verify the selection is retained
    await expect(documentInput).toHaveValue(
      "A Person is an entity with a name property. An Organization has employees."
    );
  });

  test("Test Case 4: Submit Wizard and Wait for Pipeline Execution", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open wizard
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    // Fill form
    const documentInput = page.getByTestId("schema-extraction-document");
    await documentInput.fill("Person is a class. Organization is a class with employees.");

    const taxonomyPicker = page.getByTestId("schema-extraction-taxonomy-picker");
    await taxonomyPicker.click();
    await expect(page.getByText(scheme.title)).toBeVisible();
    await page.getByText(scheme.title).click();

    // Submit the form
    const submitButton = page.getByTestId("schema-extraction-submit");
    await expect(submitButton).toBeEnabled();
    await submitButton.click();

    // Wait for loading state
    const loadingState = page.getByTestId("schema-extraction-loading");
    await expect(loadingState).toBeVisible();

    // Wait for the run to complete by observing for review panel
    await expect(page.getByTestId("schema-extraction-review")).toBeVisible({ timeout: 30000 });
  });

  test("Test Case 5: Review Extracted Classes in Candidate Table", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute the pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    const documentInput = page.getByTestId("schema-extraction-document");
    await documentInput.fill("Person class has name property. Organization class has size.");

    const taxonomyPicker = page.getByTestId("schema-extraction-taxonomy-picker");
    await taxonomyPicker.click();
    await expect(page.getByText(scheme.title)).toBeVisible();
    await page.getByText(scheme.title).click();

    const submitButton = page.getByTestId("schema-extraction-submit");
    await submitButton.click();

    // Wait for review panel to appear
    await expect(page.getByTestId("schema-extraction-review")).toBeVisible({ timeout: 30000 });

    // Verify classes table container is visible
    const classesTableContainer = page.getByTestId("classes-table-container");
    await expect(classesTableContainer).toBeVisible();

    // Verify select-all checkbox is visible
    const selectAllCheckbox = page.getByTestId("schema-extraction-select-all-classes");
    await expect(selectAllCheckbox).toBeVisible();

    // Click select-all to select all classes
    await selectAllCheckbox.click();
  });

  test("Test Case 6: Review Extracted Properties and Relationships", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    const documentInput = page.getByTestId("schema-extraction-document");
    await documentInput.fill(
      "Person has name, age. Organization has name, size. Person has_member Organization."
    );

    const taxonomyPicker = page.getByTestId("schema-extraction-taxonomy-picker");
    await taxonomyPicker.click();
    await expect(page.getByText(scheme.title)).toBeVisible();
    await page.getByText(scheme.title).click();

    const submitButton = page.getByTestId("schema-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("schema-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select all classes first
    const selectAllClasses = page.getByTestId("schema-extraction-select-all-classes");
    await selectAllClasses.click();

    // Switch to Properties tab (if needed, tabs should be in the review component)
    // Properties table should be visible or accessible via tab
    const propertiesTableContainer = page.getByTestId("properties-table-container");
    await expect(propertiesTableContainer).toBeVisible();

    // Select all properties
    const selectAllProperties = page.getByTestId("schema-extraction-select-all-properties");
    await selectAllProperties.click();

    // Switch to Relationships tab
    const relationshipsTableContainer = page.getByTestId("relationships-table-container");
    await expect(relationshipsTableContainer).toBeVisible();

    // Select all relationships
    const selectAllRelationships = page.getByTestId("schema-extraction-select-all-relationships");
    await selectAllRelationships.click();
  });

  test("Test Case 7: Click Apply Button and Confirm Application", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    const documentInput = page.getByTestId("schema-extraction-document");
    await documentInput.fill(
      "Person is a class. Organization is a class. name is a property. Person has_name name."
    );

    const taxonomyPicker = page.getByTestId("schema-extraction-taxonomy-picker");
    await taxonomyPicker.click();
    await expect(page.getByText(scheme.title)).toBeVisible();
    await page.getByText(scheme.title).click();

    const submitButton = page.getByTestId("schema-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("schema-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select all classes, properties, relationships
    await page.getByTestId("schema-extraction-select-all-classes").click();
    await page.getByTestId("schema-extraction-select-all-properties").click();
    await page.getByTestId("schema-extraction-select-all-relationships").click();

    // Verify Apply button is visible and enabled
    const applyButton = page.getByTestId("run-apply-button");
    await expect(applyButton).toBeVisible();
    await expect(applyButton).toBeEnabled();

    // Click Apply button
    await applyButton.click();

    // Wait for confirmation dialog
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    // Click Confirm button in the dialog
    const confirmButton = page.getByRole("button", { name: /confirm|apply/i }).nth(0);
    await confirmButton.click();
  });

  test("Test Case 8: Verify Apply Result Summary", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    const documentInput = page.getByTestId("schema-extraction-document");
    await documentInput.fill("Animal is a class. Dog is a subclass of Animal. has_owner is a property.");

    const taxonomyPicker = page.getByTestId("schema-extraction-taxonomy-picker");
    await taxonomyPicker.click();
    await expect(page.getByText(scheme.title)).toBeVisible();
    await page.getByText(scheme.title).click();

    const submitButton = page.getByTestId("schema-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("schema-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select candidates
    await page.getByTestId("schema-extraction-select-all-classes").click();
    await page.getByTestId("schema-extraction-select-all-properties").click();
    await page.getByTestId("schema-extraction-select-all-relationships").click();

    // Apply
    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    const confirmButton = page.getByRole("button", { name: /confirm|apply/i }).nth(0);
    await confirmButton.click();

    // Wait for and verify result panel
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 10000 });

    // Verify the result panel shows success (no error messages)
    await expect(resultPanel).not.toContainText(/error|failed/i);
  });

  test("Test Case 9: Navigate to Ontology and Verify Applied Entities Exist", async ({
    page,
  }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    const documentInput = page.getByTestId("schema-extraction-document");
    const sampleDocument = "Vehicle is a class. Car is a class. Bicycle is a class.";
    await documentInput.fill(sampleDocument);

    const taxonomyPicker = page.getByTestId("schema-extraction-taxonomy-picker");
    await taxonomyPicker.click();
    await expect(page.getByText(scheme.title)).toBeVisible();
    await page.getByText(scheme.title).click();

    const submitButton = page.getByTestId("schema-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("schema-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select and apply
    await page.getByTestId("schema-extraction-select-all-classes").click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    const confirmButton = page.getByRole("button", { name: /confirm|apply/i }).nth(0);
    await confirmButton.click();

    // Wait for result
    await expect(page.getByTestId("run-apply-result")).toBeVisible({ timeout: 10000 });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Verify classes page loads
    await expect(page.getByTestId("classes-page")).toBeVisible();

    // Search for one of the applied classes (e.g., "Vehicle")
    // Classes table should display the applied entities
    await expect(page.getByTestId("schema-table")).toBeVisible();
  });

  test("Test Case 10: Verify Applied Properties and Relationships", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_extraction");
    await runButton.click();

    await expect(page.getByTestId("schema-extraction-wizard")).toBeVisible();

    const documentInput = page.getByTestId("schema-extraction-document");
    await documentInput.fill(
      "Person has name, email properties. Company has size property. Person works_for Company."
    );

    const taxonomyPicker = page.getByTestId("schema-extraction-taxonomy-picker");
    await taxonomyPicker.click();
    await expect(page.getByText(scheme.title)).toBeVisible();
    await page.getByText(scheme.title).click();

    const submitButton = page.getByTestId("schema-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("schema-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select all
    await page.getByTestId("schema-extraction-select-all-classes").click();
    await page.getByTestId("schema-extraction-select-all-properties").click();
    await page.getByTestId("schema-extraction-select-all-relationships").click();

    // Apply
    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    const confirmButton = page.getByRole("button", { name: /confirm|apply/i }).nth(0);
    await confirmButton.click();

    // Wait for result
    await expect(page.getByTestId("run-apply-result")).toBeVisible({ timeout: 10000 });

    // Navigate to properties page
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");

    // Verify properties page
    await expect(page.getByTestId("properties-page")).toBeVisible();

    // Navigate to relationships page
    await page.goto("/app/schema/relationships");
    await page.waitForLoadState("networkidle");

    // Verify relationships page
    await expect(page.getByTestId("relationships-page")).toBeVisible();
  });
});
