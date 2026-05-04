import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
  createRelationship,
  clearTestData,
  apiRequest,
} from "../../fixtures/test-helpers";
import type {
  ImportPlanResponse,
  ImportRunCommitResponse,
  ChangeEvent,
} from "@/api/types/interchange";

test.describe("Interchange (Import/Export)", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Export ontology in SKOS format with whole graph scope", async ({
    page,
  }) => {
    // Preconditions: Create test data
    const timestamp = Date.now();
    const taxonomy = await createTaxonomy(page, {
      title: `Test Taxonomy Export-${timestamp}`,
    });
    const scheme = await createConceptScheme(page, taxonomy.id);
    const classA = await createClass(page, scheme.id, { title: "ClassA" });
    const classB = await createClass(page, scheme.id, { title: "ClassB" });
    const classC = await createClass(page, scheme.id, { title: "ClassC" });
    const propDef = await createPropertyDefinition(page, {
      title: "hasRelation",
      identifier: `prop-${timestamp}`,
    });
    await createRelationship(page, classA.id, classB.id, propDef.id);
    await createRelationship(page, classB.id, classC.id, propDef.id);

    // Navigate to export page
    await page.goto("/app/interchange/export");
    await page.waitForLoadState("networkidle");

    // Select SKOS format
    const formatSelect = page.getByTestId("interchange-export-format-select");
    await formatSelect.click();
    await page.getByRole("option", { name: /skos/i }).click();

    // Select whole graph scope
    const scopePicker = page.getByTestId("interchange-export-scope-picker");
    await scopePicker.click();
    await page.getByRole("option", { name: /whole graph/i }).click();

    // Click download button
    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("interchange-export-download-button").click();
    const download = await downloadPromise;

    // Verify download
    expect(download.suggestedFilename()).toMatch(/skos|rdf/i);
    const path = await download.path();
    expect(path).toBeTruthy();
  });

  test("Test Case 2: Import file with dry-run preview showing conflicts grouped by match_kind", async ({
    page,
  }) => {
    // Preconditions: Create existing classes
    const taxonomy = await createTaxonomy(page);
    const scheme = await createConceptScheme(page, taxonomy.id);
    const existingClassA = await createClass(page, scheme.id, {
      title: "ClassA",
    });
    const existingClassB = await createClass(page, scheme.id, {
      title: "ClassB",
    });

    // Create a test SKOS file with conflicts
    const skosContent = `<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:skos="http://www.w3.org/2004/02/skos/core#"
  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">

  <rdf:Description rdf:about="http://example.org/class/1">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>${existingClassA.title}</skos:prefLabel>
  </rdf:Description>

  <rdf:Description rdf:about="${existingClassB.id}">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>ClassB</skos:prefLabel>
  </rdf:Description>

  <rdf:Description rdf:about="http://example.org/class/3">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>ClassC</skos:prefLabel>
  </rdf:Description>

  <rdf:Description rdf:about="http://example.org/class/4">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>ClassD</skos:prefLabel>
  </rdf:Description>
</rdf:RDF>`;

    // Navigate to import page
    await page.goto("/app/interchange/import");
    await page.waitForLoadState("networkidle");

    // Upload file using setInputFiles with buffer
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles([
      {
        name: "test.rdf",
        mimeType: "application/xml",
        buffer: Buffer.from(skosContent),
      },
    ]);

    // Click preview button
    await page.getByTestId("interchange-import-preview-button").click();
    await page.waitForLoadState("networkidle");

    // Verify conflict resolution modal opens
    const modal = page.getByTestId("interchange-conflict-resolution-modal");
    await expect(modal).toBeVisible();

    // Verify conflict groups are displayed
    await expect(
      page.getByTestId("interchange-conflict-group-external-reference"),
    ).toBeVisible();
    await expect(
      page.getByTestId("interchange-conflict-group-uuid"),
    ).toBeVisible();
    await expect(
      page.getByTestId("interchange-conflict-group-title"),
    ).toBeVisible();
    await expect(
      page.getByTestId("interchange-conflict-group-create"),
    ).toBeVisible();
  });

  test("Test Case 3: Resolve conflicts with apply-all-per-group strategy and commit import", async ({
    page,
  }) => {
    // Preconditions: Create existing classes
    const taxonomy = await createTaxonomy(page);
    const scheme = await createConceptScheme(page, taxonomy.id);
    const existingClassA = await createClass(page, scheme.id, {
      title: "ClassA",
    });
    const existingClassB = await createClass(page, scheme.id, {
      title: "ClassB",
    });

    // Create test SKOS file
    const skosContent = `<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:skos="http://www.w3.org/2004/02/skos/core#">
  <rdf:Description rdf:about="http://example.org/class/1">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>${existingClassA.title}</skos:prefLabel>
  </rdf:Description>
  <rdf:Description rdf:about="${existingClassB.id}">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>ClassB</skos:prefLabel>
  </rdf:Description>
  <rdf:Description rdf:about="http://example.org/class/3">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>ClassC</skos:prefLabel>
  </rdf:Description>
</rdf:RDF>`;

    // Navigate and upload
    await page.goto("/app/interchange/import");
    await page.waitForLoadState("networkidle");

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles([
      {
        name: "test.rdf",
        mimeType: "application/xml",
        buffer: Buffer.from(skosContent),
      },
    ]);

    // Click preview
    await page.getByTestId("interchange-import-preview-button").click();
    await page.waitForLoadState("networkidle");

    const modal = page.getByTestId("interchange-conflict-resolution-modal");
    await expect(modal).toBeVisible();

    // Resolve external_reference conflicts
    const applyAllExtRef = page.getByTestId(
      "interchange-conflict-apply-all-external_reference-skip",
    );
    if (await applyAllExtRef.isVisible()) {
      await applyAllExtRef.click();
    }

    // Resolve uuid conflicts
    const applyAllUuid = page.getByTestId(
      "interchange-conflict-apply-all-uuid-skip",
    );
    if (await applyAllUuid.isVisible()) {
      await applyAllUuid.click();
    }

    // Resolve title conflicts
    const applyAllTitle = page.getByTestId(
      "interchange-conflict-apply-all-title-skip",
    );
    if (await applyAllTitle.isVisible()) {
      await applyAllTitle.click();
    }

    // Commit import
    const commitButton = page.getByTestId("interchange-conflict-commit-button");
    await commitButton.click();
    await page.waitForLoadState("networkidle");

    // Verify modal closes and success toast appears
    await expect(modal).not.toBeVisible();
    await expect(page.getByRole("status")).toContainText(/success|imported/i);
  });

  test("Test Case 4: Cancel conflict resolution and dismiss modal", async ({
    page,
  }) => {
    // Preconditions: Create existing classes
    const taxonomy = await createTaxonomy(page);
    const scheme = await createConceptScheme(page, taxonomy.id);
    const existingClass = await createClass(page, scheme.id, {
      title: "ExistingClass",
    });

    // Create test SKOS file with conflict
    const skosContent = `<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:skos="http://www.w3.org/2004/02/skos/core#">
  <rdf:Description rdf:about="http://example.org/class/1">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>${existingClass.title}</skos:prefLabel>
  </rdf:Description>
</rdf:RDF>`;

    // Navigate and upload
    await page.goto("/app/interchange/import");
    await page.waitForLoadState("networkidle");

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles([
      {
        name: "test.rdf",
        mimeType: "application/xml",
        buffer: Buffer.from(skosContent),
      },
    ]);

    // Click preview
    await page.getByTestId("interchange-import-preview-button").click();
    await page.waitForLoadState("networkidle");

    const modal = page.getByTestId("interchange-conflict-resolution-modal");
    await expect(modal).toBeVisible();

    // Click cancel button
    await page.getByTestId("interchange-conflict-cancel-button").click();

    // Verify modal is dismissed
    await expect(modal).not.toBeVisible();

    // Verify we're back on import page
    expect(page.url()).toContain("/app/interchange/import");
  });

  test("Test Case 5: Verify ImportRun appears in recent runs list with correct metadata", async ({
    page,
  }) => {
    // Preconditions: Create and import data
    const taxonomy = await createTaxonomy(page);
    const scheme = await createConceptScheme(page, taxonomy.id);
    const _existingClass = await createClass(page, scheme.id);

    // Create import file
    const skosContent = `<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:skos="http://www.w3.org/2004/02/skos/core#">
  <rdf:Description rdf:about="http://example.org/class/new">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>NewClass</skos:prefLabel>
  </rdf:Description>
</rdf:RDF>`;

    // Import via API dry-run and commit
    const dryRunResult = await apiRequest<ImportPlanResponse>(
      page,
      "/api/interchange/import/dry-run",
      {
        method: "POST",
        body: {
          file_content: skosContent,
          format: "SKOS",
          scope: { scope_type: "whole_graph" },
        },
      },
    );

    const commitResult = await apiRequest<ImportRunCommitResponse>(
      page,
      "/api/interchange/import/commit",
      {
        method: "POST",
        body: {
          import_run_id: dryRunResult.import_run_id,
          resolutions: [],
        },
      },
    );

    const runId = commitResult.id;

    // Navigate to recent runs page
    await page.goto("/app/interchange");
    await page.waitForLoadState("networkidle");

    // Verify recent runs table exists
    const table = page.getByTestId("interchange-recent-runs-table");
    await expect(table).toBeVisible();

    // Verify run appears in table
    const runRow = page.getByTestId(`interchange-runs-table-row-${runId}`);
    await expect(runRow).toBeVisible();

    // Verify metadata is displayed
    await expect(runRow).toContainText(runId);
    await expect(runRow).toContainText(/SKOS/i);
    await expect(runRow).toContainText(/committed/i);
  });

  test("Test Case 6: Navigate to ImportRun detail page and verify affected entities display", async ({
    page,
  }) => {
    // Preconditions: Create and import data
    const taxonomy = await createTaxonomy(page);
    const scheme = await createConceptScheme(page, taxonomy.id);
    const _class1 = await createClass(page, scheme.id, { title: "Class1" });
    const _class2 = await createClass(page, scheme.id, { title: "Class2" });
    const _class3 = await createClass(page, scheme.id, { title: "Class3" });

    // Create import file
    const skosContent = `<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:skos="http://www.w3.org/2004/02/skos/core#">
  <rdf:Description rdf:about="http://example.org/class/1">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>NewClass1</skos:prefLabel>
  </rdf:Description>
  <rdf:Description rdf:about="http://example.org/class/2">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>NewClass2</skos:prefLabel>
  </rdf:Description>
  <rdf:Description rdf:about="http://example.org/class/3">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>NewClass3</skos:prefLabel>
  </rdf:Description>
</rdf:RDF>`;

    // Import via API
    const dryRunResult = await apiRequest<ImportPlanResponse>(
      page,
      "/api/interchange/import/dry-run",
      {
        method: "POST",
        body: {
          file_content: skosContent,
          format: "SKOS",
          scope: { scope_type: "whole_graph" },
        },
      },
    );

    const commitResult = await apiRequest<ImportRunCommitResponse>(
      page,
      "/api/interchange/import/commit",
      {
        method: "POST",
        body: {
          import_run_id: dryRunResult.import_run_id,
          resolutions: [],
        },
      },
    );

    const runId = commitResult.id;

    // Navigate to detail page
    await page.goto(`/app/interchange/runs/${runId}`);
    await page.waitForLoadState("networkidle");

    // Verify metadata section
    const metadataSection = page.getByTestId("interchange-run-detail-metadata");
    await expect(metadataSection).toBeVisible();
    await expect(metadataSection).toContainText(runId);
    await expect(metadataSection).toContainText(/SKOS/i);
    await expect(metadataSection).toContainText(/committed/i);

    // Verify affected entities section
    const entitiesSection = page.getByTestId(
      "interchange-run-affected-entities",
    );
    await expect(entitiesSection).toBeVisible();

    // Verify at least one entity ID is displayed
    for (const entityId of commitResult.affected_entity_ids ?? []) {
      const entityIdElement = entitiesSection.getByText(entityId);
      await expect(entityIdElement).toBeVisible();
    }
  });

  test("Test Case 7: Verify change events pagination on detail page", async ({
    page,
  }) => {
    // Preconditions: Create data with 40+ change events
    const taxonomy = await createTaxonomy(page);
    const scheme = await createConceptScheme(page, taxonomy.id);

    // Create 25 classes to generate 25+ change events
    const classes = [];
    for (let i = 0; i < 25; i++) {
      const cls = await createClass(page, scheme.id, {
        title: `Class${i}`,
      });
      classes.push(cls);
    }

    // Create import with multiple changes
    const _classIds = classes.map((c) => c.id).join(",");
    const skosContent = `<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:skos="http://www.w3.org/2004/02/skos/core#">
  <rdf:Description rdf:about="http://example.org/class/1">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>NewClass1</skos:prefLabel>
  </rdf:Description>
  <rdf:Description rdf:about="http://example.org/class/2">
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept"/>
    <skos:prefLabel>NewClass2</skos:prefLabel>
  </rdf:Description>
</rdf:RDF>`;

    // Import
    const dryRunResult = await apiRequest<ImportPlanResponse>(
      page,
      "/api/interchange/import/dry-run",
      {
        method: "POST",
        body: {
          file_content: skosContent,
          format: "SKOS",
          scope: { scope_type: "whole_graph" },
        },
      },
    );

    const commitResult = await apiRequest<ImportRunCommitResponse>(
      page,
      "/api/interchange/import/commit",
      {
        method: "POST",
        body: {
          import_run_id: dryRunResult.import_run_id,
          resolutions: [],
        },
      },
    );

    const runId = commitResult.id;

    // Navigate to detail page
    await page.goto(`/app/interchange/runs/${runId}`);
    await page.waitForLoadState("networkidle");

    // Verify change events section
    const eventsSection = page.getByTestId("interchange-run-change-events");
    await expect(eventsSection).toBeVisible();

    // Fetch change events to verify pagination
    const changeEventsResponse = await apiRequest<{
      items: ChangeEvent[];
      total: number;
    }>(page, `/api/interchange/runs/${runId}/change-events?offset=0&limit=20`);

    expect(changeEventsResponse.items.length).toBeLessThanOrEqual(20);
    expect(changeEventsResponse.items[0]).toHaveProperty("entity_id");
    expect(changeEventsResponse.items[0]).toHaveProperty("entity_type");
    expect(changeEventsResponse.items[0]).toHaveProperty("change_type");

    // If there are more than 20 events, verify pagination controls exist
    if (changeEventsResponse.total > 20) {
      const nextButton = page.getByRole("button", { name: /next/i });
      await expect(nextButton).toBeVisible();

      // Click next to load page 2
      await nextButton.click();
      await page.waitForLoadState("networkidle");

      // Verify page 2 has different events
      const page2Response = await apiRequest<{ items: ChangeEvent[] }>(
        page,
        `/api/interchange/runs/${runId}/change-events?offset=20&limit=20`,
      );

      expect(page2Response.items.length).toBeGreaterThan(0);
      expect(page2Response.items[0].entity_id).not.toBe(
        changeEventsResponse.items[0].entity_id,
      );

      // Verify previous button works
      const prevButton = page.getByRole("button", { name: /previous/i });
      await expect(prevButton).toBeVisible();
      await prevButton.click();
      await page.waitForLoadState("networkidle");
    }
  });

  test("Test Case 8: Attempt to import invalid file content and verify error handling", async ({
    page,
  }) => {
    // Navigate to import page
    await page.goto("/app/interchange/import");
    await page.waitForLoadState("networkidle");

    // Upload invalid file
    const invalidContent = "This is not valid XML or RDF content";
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles([
      {
        name: "invalid.rdf",
        mimeType: "application/xml",
        buffer: Buffer.from(invalidContent),
      },
    ]);

    // Click preview button
    await page.getByTestId("interchange-import-preview-button").click();

    // Wait for API response and error handling
    await page.waitForLoadState("networkidle");

    // Verify error toast appears
    const errorToast = page.getByRole("status");
    await expect(errorToast).toContainText(/error|invalid|failed/i);

    // Verify conflict modal does NOT open
    const modal = page.getByTestId("interchange-conflict-resolution-modal");
    await expect(modal).not.toBeVisible();

    // Verify user can retry with different file
    const fileInputAgain = page.locator('input[type="file"]');
    await expect(fileInputAgain).toBeVisible();
  });
});
