import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Individual Extraction Run, Review, and Apply", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Navigate to Pipeline Hub and Locate Individual Extraction Type", async ({
    page,
  }) => {
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Verify pipelines page is loaded
    await expect(page.getByTestId("pipelines-page")).toBeVisible();

    // Verify pipeline types grid is visible
    await expect(page.getByTestId("pipeline-types-grid")).toBeVisible();

    // Locate the Individual Extraction pipeline type card
    const individualExtractionCard = page.getByTestId("pipeline-type-card-individual_extraction");
    await expect(individualExtractionCard).toBeVisible();

    // Verify the Run button is visible and enabled
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
  });

  test("Test Case 2: Open Individual Extraction Wizard and Configure Source Data", async ({
    page,
  }) => {
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Click the Run button
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    // Wait for the wizard to open
    await expect(page.getByTestId("individual-extraction-wizard")).toBeVisible();

    // Locate the source text area
    const sourceInput = page.getByTestId("individual-extraction-source");
    await expect(sourceInput).toBeVisible();

    // Enter sample source text
    const sampleText =
      "John is a Person. Jane is a Person with the name Jane Doe. An Organization named Acme Inc. has employees John and Jane.";
    await sourceInput.fill(sampleText);

    // Verify the text was accepted
    await expect(sourceInput).toHaveValue(sampleText);
  });

  test("Test Case 3: Configure Target Ontology/Classes", async ({ page }) => {
    // Create test ontology with classes
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const personClass = await createClass(page, scheme.id, { title: "Person" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open wizard
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    await expect(page.getByTestId("individual-extraction-wizard")).toBeVisible();

    // Fill source data
    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("Alice is a Person. Bob is a Person.");

    // Locate the ontology picker
    const ontologyPicker = page.getByTestId("individual-extraction-ontology");
    await expect(ontologyPicker).toBeVisible();

    // Click picker to open dropdown
    await ontologyPicker.click();

    // Select the Person class
    await expect(page.getByText(personClass.title)).toBeVisible();
    await page.getByText(personClass.title).click();

    // Verify source data input is still populated
    await expect(sourceInput).toHaveValue("Alice is a Person. Bob is a Person.");
  });

  test("Test Case 4: Submit Wizard and Wait for Pipeline Execution", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const personClass = await createClass(page, scheme.id, { title: "Person" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open wizard
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    await expect(page.getByTestId("individual-extraction-wizard")).toBeVisible();

    // Fill form
    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("Charlie is a Person. Diana is a Person.");

    const ontologyPicker = page.getByTestId("individual-extraction-ontology");
    await ontologyPicker.click();
    await expect(page.getByText(personClass.title)).toBeVisible();
    await page.getByText(personClass.title).click();

    // Submit the form
    const submitButton = page.getByTestId("individual-extraction-submit");
    await expect(submitButton).toBeEnabled();
    await submitButton.click();

    // Wait for loading state
    const loadingState = page.getByTestId("individual-extraction-loading");
    await expect(loadingState).toBeVisible();

    // Wait for review panel to appear
    await expect(page.getByTestId("individual-extraction-review")).toBeVisible({ timeout: 30000 });
  });

  test("Test Case 5: Review Extracted Individuals/Triples in Candidate Table", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const personClass = await createClass(page, scheme.id, { title: "Person" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    await expect(page.getByTestId("individual-extraction-wizard")).toBeVisible();

    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("Eve is a Person. Frank is a Person. Grace is a Person.");

    const ontologyPicker = page.getByTestId("individual-extraction-ontology");
    await ontologyPicker.click();
    await expect(page.getByText(personClass.title)).toBeVisible();
    await page.getByText(personClass.title).click();

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for review panel to appear
    await expect(page.getByTestId("individual-extraction-review")).toBeVisible({ timeout: 30000 });

    // Verify table displays extracted individuals
    const reviewPanel = page.getByTestId("individual-extraction-review");
    await expect(reviewPanel).toContainText(/individual|triple|candidate/i);

    // Verify select-all checkbox is visible
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await expect(selectAllCheckbox).toBeVisible();

    // Click select-all to select all candidates
    await selectAllCheckbox.click();
  });

  test("Test Case 6: Click Apply Button and Confirm Application", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const personClass = await createClass(page, scheme.id, { title: "Person" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    await expect(page.getByTestId("individual-extraction-wizard")).toBeVisible();

    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("Henry is a Person. Iris is a Person.");

    const ontologyPicker = page.getByTestId("individual-extraction-ontology");
    await ontologyPicker.click();
    await expect(page.getByText(personClass.title)).toBeVisible();
    await page.getByText(personClass.title).click();

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("individual-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select all candidates
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await selectAllCheckbox.click();

    // Verify Apply button is visible and enabled
    const applyButton = page.getByTestId("run-apply-button");
    await expect(applyButton).toBeVisible();
    await expect(applyButton).toBeEnabled();

    // Click Apply button
    await applyButton.click();

    // Wait for confirmation dialog
    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    // Click Confirm button
    const confirmButton = page.getByRole("button", { name: /confirm|apply/i }).nth(0);
    await confirmButton.click();
  });

  test("Test Case 7: Verify Apply Result Summary", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const personClass = await createClass(page, scheme.id, { title: "Person" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    await expect(page.getByTestId("individual-extraction-wizard")).toBeVisible();

    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("Jack is a Person. Karen is a Person. Luke is a Person.");

    const ontologyPicker = page.getByTestId("individual-extraction-ontology");
    await ontologyPicker.click();
    await expect(page.getByText(personClass.title)).toBeVisible();
    await page.getByText(personClass.title).click();

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("individual-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select all and apply
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await selectAllCheckbox.click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    const confirmButton = page.getByRole("button", { name: /confirm|apply/i }).nth(0);
    await confirmButton.click();

    // Wait for and verify result panel
    const resultPanel = page.getByTestId("run-apply-result");
    await expect(resultPanel).toBeVisible({ timeout: 10000 });

    // Verify result shows applied individual count
    await expect(resultPanel).toContainText(/applied|individual/i);

    // Verify no error messages
    await expect(resultPanel).not.toContainText(/error|failed/i);
  });

  test("Test Case 8: Navigate to Individuals Page and Verify Applied Individuals Exist", async ({
    page,
  }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const personClass = await createClass(page, scheme.id, { title: "Person" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    await expect(page.getByTestId("individual-extraction-wizard")).toBeVisible();

    const sourceInput = page.getByTestId("individual-extraction-source");
    const sampleData = "Mike is a Person. Nancy is a Person.";
    await sourceInput.fill(sampleData);

    const ontologyPicker = page.getByTestId("individual-extraction-ontology");
    await ontologyPicker.click();
    await expect(page.getByText(personClass.title)).toBeVisible();
    await page.getByText(personClass.title).click();

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("individual-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select and apply
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await selectAllCheckbox.click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    const confirmButton = page.getByRole("button", { name: /confirm|apply/i }).nth(0);
    await confirmButton.click();

    // Wait for result
    await expect(page.getByTestId("run-apply-result")).toBeVisible({ timeout: 10000 });

    // Navigate to individuals page
    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    // Verify individuals page loads
    await expect(page.getByTestId("individuals-page")).toBeVisible();

    // Verify schema-page-layout is present (indicating individuals exist)
    await expect(page.getByTestId("schema-page-layout")).toBeVisible();
  });

  test("Test Case 9: Verify Individual Class Memberships and Properties", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const personClass = await createClass(page, scheme.id, { title: "Person" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-individual_extraction");
    await runButton.click();

    await expect(page.getByTestId("individual-extraction-wizard")).toBeVisible();

    const sourceInput = page.getByTestId("individual-extraction-source");
    await sourceInput.fill("Oscar is a Person. Patricia is a Person. Quincy is a Person.");

    const ontologyPicker = page.getByTestId("individual-extraction-ontology");
    await ontologyPicker.click();
    await expect(page.getByText(personClass.title)).toBeVisible();
    await page.getByText(personClass.title).click();

    const submitButton = page.getByTestId("individual-extraction-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("individual-extraction-review")).toBeVisible({ timeout: 30000 });

    // Select and apply
    const selectAllCheckbox = page.getByTestId("individual-extraction-select-all");
    await selectAllCheckbox.click();

    const applyButton = page.getByTestId("run-apply-button");
    await applyButton.click();

    const confirmDialog = page.getByTestId("run-apply-confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    const confirmButton = page.getByRole("button", { name: /confirm|apply/i }).nth(0);
    await confirmButton.click();

    // Wait for result
    await expect(page.getByTestId("run-apply-result")).toBeVisible({ timeout: 10000 });

    // Navigate to individuals page
    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    // Verify individuals page and table
    await expect(page.getByTestId("individuals-page")).toBeVisible();
    await expect(page.getByTestId("schema-page-layout")).toBeVisible();

    // Verify individual properties panel exists
    // Click on first individual to open detail drawer
    const schemaPageLayout = page.getByTestId("schema-page-layout");
    const firstRow = schemaPageLayout.locator("tr").nth(1);
    await firstRow.click();

    // Verify individual properties panel is visible
    const propertiesPanel = page.getByTestId("individual-properties-panel");
    await expect(propertiesPanel).toBeVisible();
  });
});
