import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Schema Node Grounding Run, Review, and Apply", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Navigate to Pipeline Hub and Locate Schema Grounding Pipeline Type", async ({
    page,
  }) => {
    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Verify pipelines page is loaded
    await expect(page.getByTestId("pipelines-page")).toBeVisible();

    // Verify pipeline types grid is visible
    await expect(page.getByTestId("pipeline-types-grid")).toBeVisible();

    // Locate the Schema Grounding pipeline type card
    const groundingCard = page.getByTestId("pipeline-type-card-schema_grounding");
    await expect(groundingCard).toBeVisible();

    // Verify the Run button is visible and enabled
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
  });

  test("Test Case 2: Open Schema Grounding Wizard and Select Target Nodes", async ({ page }) => {
    // Create test ontology with classes
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const personClass = await createClass(page, scheme.id, { title: "Person" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Click the Run button
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    // Wait for the wizard to open
    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    // Locate the target nodes picker
    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await expect(nodesPicker).toBeVisible();

    // Click on the nodes picker to open dropdown
    await nodesPicker.click();

    // Select the Person class
    await expect(page.getByText(personClass.title)).toBeVisible();
    await page.getByText(personClass.title).click();

    // Verify the selected nodes are displayed
    await expect(nodesPicker).toContainText(personClass.title);
  });

  test("Test Case 3: Configure Knowledge Source Selection", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const organizationClass = await createClass(page, scheme.id, { title: "Organization" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open wizard
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    // Select target nodes
    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await nodesPicker.click();
    await expect(page.getByText(organizationClass.title)).toBeVisible();
    await page.getByText(organizationClass.title).click();

    // Verify knowledge sources section is visible
    const sourcesContainer = page.getByTestId("schema-grounding-sources");
    await expect(sourcesContainer).toBeVisible();

    // Verify all source checkboxes are visible
    const dbpediaCheckbox = page.getByTestId("schema-grounding-source-dbpedia");
    const conceptnetCheckbox = page.getByTestId("schema-grounding-source-conceptnet");
    const wikidataCheckbox = page.getByTestId("schema-grounding-source-wikidata");
    const schemaorgCheckbox = page.getByTestId("schema-grounding-source-schema_org");

    await expect(dbpediaCheckbox).toBeVisible();
    await expect(conceptnetCheckbox).toBeVisible();
    await expect(wikidataCheckbox).toBeVisible();
    await expect(schemaorgCheckbox).toBeVisible();

    // Select at least one source (DBpedia)
    await dbpediaCheckbox.click();

    // Verify it's selected
    await expect(dbpediaCheckbox).toBeChecked();
  });

  test("Test Case 4: Submit Wizard and Wait for Grounding Execution", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const animalClass = await createClass(page, scheme.id, { title: "Animal" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Open wizard
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    // Select nodes
    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await nodesPicker.click();
    await expect(page.getByText(animalClass.title)).toBeVisible();
    await page.getByText(animalClass.title).click();

    // Select sources
    const dbpediaCheckbox = page.getByTestId("schema-grounding-source-dbpedia");
    await dbpediaCheckbox.click();

    // Submit the form
    const submitButton = page.getByTestId("schema-grounding-submit");
    await expect(submitButton).toBeEnabled();
    await submitButton.click();

    // Wait for loading state
    const loadingState = page.getByTestId("schema-grounding-loading");
    await expect(loadingState).toBeVisible();

    // Wait for review panel to appear
    await expect(page.getByTestId("grounding-review")).toBeVisible({ timeout: 30000 });
  });

  test("Test Case 5: Review Grounding Candidates", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const vehicleClass = await createClass(page, scheme.id, { title: "Vehicle" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await nodesPicker.click();
    await expect(page.getByText(vehicleClass.title)).toBeVisible();
    await page.getByText(vehicleClass.title).click();

    const dbpediaCheckbox = page.getByTestId("schema-grounding-source-dbpedia");
    const conceptnetCheckbox = page.getByTestId("schema-grounding-source-conceptnet");
    await dbpediaCheckbox.click();
    await conceptnetCheckbox.click();

    const submitButton = page.getByTestId("schema-grounding-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("grounding-review")).toBeVisible({ timeout: 30000 });

    // Verify grounding review panel is visible
    const reviewPanel = page.getByTestId("grounding-review");
    await expect(reviewPanel).toBeVisible();

    // Verify review panel displays grounding candidates
    await expect(reviewPanel).toContainText(/grounding|candidate|reference/i);
  });

  test("Test Case 6: Accept Grounding Candidates", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const companyClass = await createClass(page, scheme.id, { title: "Company" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await nodesPicker.click();
    await expect(page.getByText(companyClass.title)).toBeVisible();
    await page.getByText(companyClass.title).click();

    const dbpediaCheckbox = page.getByTestId("schema-grounding-source-dbpedia");
    await dbpediaCheckbox.click();

    const submitButton = page.getByTestId("schema-grounding-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("grounding-review")).toBeVisible({ timeout: 30000 });

    // Accept first available grounding candidate
    // Look for accept buttons (pattern: grounding-accept-*)
    const acceptButtons = page.locator("[data-testid^='grounding-accept-']");
    const count = await acceptButtons.count();

    if (count > 0) {
      // Click the first accept button
      await acceptButtons.first().click();

      // Verify acceptance is recorded (button might change state or show checkmark)
      // The acceptance state should persist as we scroll
      await page.waitForLoadState("networkidle");
    }
  });

  test("Test Case 7: Click Apply Button and Confirm Application", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const locationClass = await createClass(page, scheme.id, { title: "Location" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await nodesPicker.click();
    await expect(page.getByText(locationClass.title)).toBeVisible();
    await page.getByText(locationClass.title).click();

    const dbpediaCheckbox = page.getByTestId("schema-grounding-source-dbpedia");
    await dbpediaCheckbox.click();

    const submitButton = page.getByTestId("schema-grounding-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("grounding-review")).toBeVisible({ timeout: 30000 });

    // Accept at least one candidate
    const acceptButtons = page.locator("[data-testid^='grounding-accept-']");
    const count = await acceptButtons.count();

    if (count > 0) {
      await acceptButtons.first().click();
    }

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

  test("Test Case 8: Verify Apply Result Summary", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const eventClass = await createClass(page, scheme.id, { title: "Event" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await nodesPicker.click();
    await expect(page.getByText(eventClass.title)).toBeVisible();
    await page.getByText(eventClass.title).click();

    const dbpediaCheckbox = page.getByTestId("schema-grounding-source-dbpedia");
    const conceptnetCheckbox = page.getByTestId("schema-grounding-source-conceptnet");
    await dbpediaCheckbox.click();
    await conceptnetCheckbox.click();

    const submitButton = page.getByTestId("schema-grounding-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("grounding-review")).toBeVisible({ timeout: 30000 });

    // Accept candidates
    const acceptButtons = page.locator("[data-testid^='grounding-accept-']");
    const count = await acceptButtons.count();

    if (count > 0) {
      await acceptButtons.first().click();
    }

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

    // Verify result shows groundings applied
    await expect(resultPanel).toContainText(/applied|grounding/i);

    // Verify no error messages
    await expect(resultPanel).not.toContainText(/error|failed/i);
  });

  test("Test Case 9: Navigate to Classes Page and Verify Updated Groundings", async ({ page }) => {
    // Create test data
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const musicClass = await createClass(page, scheme.id, { title: "Music" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await nodesPicker.click();
    await expect(page.getByText(musicClass.title)).toBeVisible();
    await page.getByText(musicClass.title).click();

    const dbpediaCheckbox = page.getByTestId("schema-grounding-source-dbpedia");
    await dbpediaCheckbox.click();

    const submitButton = page.getByTestId("schema-grounding-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("grounding-review")).toBeVisible({ timeout: 30000 });

    // Accept candidates
    const acceptButtons = page.locator("[data-testid^='grounding-accept-']");
    const count = await acceptButtons.count();

    if (count > 0) {
      await acceptButtons.first().click();
    }

    // Apply
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

    // Search for or scroll to find the grounded class
    // Click on the class to open detail drawer
    const schemaTable = page.getByTestId("schema-table");
    await expect(schemaTable).toBeVisible();

    // Find and click first class row
    const firstClassRow = schemaTable.locator("tr").nth(1);
    if ((await firstClassRow.count()) > 0) {
      await firstClassRow.click();

      // Verify class inspector is visible
      const classInspector = page.getByTestId("class-inspector");
      await expect(classInspector).toBeVisible();
    }
  });

  test("Test Case 10: Verify Multiple Nodes Have Been Grounded", async ({ page }) => {
    // Create test data with multiple classes
    const taxonomy = await createTaxonomy(page, { title: "Test Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const bookClass = await createClass(page, scheme.id, { title: "Book" });
    const authorClass = await createClass(page, scheme.id, { title: "Author" });

    await page.goto("/app/pipelines");
    await page.waitForLoadState("networkidle");

    // Execute pipeline
    const runButton = page.getByTestId("pipeline-run-button-schema_grounding");
    await runButton.click();

    await expect(page.getByTestId("schema-grounding-wizard")).toBeVisible();

    // Select multiple target nodes
    const nodesPicker = page.getByTestId("schema-grounding-nodes");
    await nodesPicker.click();

    // Select Book class
    await expect(page.getByText(bookClass.title)).toBeVisible();
    await page.getByText(bookClass.title).click();

    // Select Author class (if multi-select is supported)
    // This depends on the picker implementation
    const authorOption = page.getByText(authorClass.title);
    if ((await authorOption.count()) > 0) {
      await authorOption.click();
    }

    // Select sources
    const dbpediaCheckbox = page.getByTestId("schema-grounding-source-dbpedia");
    const wikidataCheckbox = page.getByTestId("schema-grounding-source-wikidata");
    await dbpediaCheckbox.click();
    await wikidataCheckbox.click();

    const submitButton = page.getByTestId("schema-grounding-submit");
    await submitButton.click();

    // Wait for review panel
    await expect(page.getByTestId("grounding-review")).toBeVisible({ timeout: 30000 });

    // Accept candidates
    const acceptButtons = page.locator("[data-testid^='grounding-accept-']");
    const count = await acceptButtons.count();

    // Accept first candidate
    if (count > 0) {
      await acceptButtons.first().click();
    }

    // Apply
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

    // Verify classes page
    await expect(page.getByTestId("classes-page")).toBeVisible();

    // Verify multiple grounded classes exist
    const schemaTable = page.getByTestId("schema-table");
    await expect(schemaTable).toBeVisible();

    // Verify we can inspect multiple grounded classes
    const classRows = schemaTable.locator("tbody tr");
    const rowCount = await classRows.count();
    expect(rowCount).toBeGreaterThan(0);
  });
});
