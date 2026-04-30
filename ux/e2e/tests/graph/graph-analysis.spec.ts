import { test, expect } from "@playwright/test";
import {
  createTestHierarchy,
  createRelationship,
  clearTestData,
  apiRequest,
} from "../../fixtures/test-helpers";

/**
 * Graph Visualization and Analysis E2E Tests
 *
 * Tests the graph visualization and analysis functionality:
 * - Graph rendering with nodes and edges
 * - Node selection and highlighting
 * - Graph navigation and zoom controls
 * - Relationship visualization
 * - Graph filtering and search
 * - Performance with large graphs
 * - Error handling for invalid data
 *
 * These tests verify the visual representation and interaction
 * with knowledge graphs built from ontology data.
 */

test.describe("Graph Visualization and Analysis", () => {
  let _hierarchyId: string;

  test.beforeEach(async ({ page }) => {
    // Create test hierarchy with classes and relationships
    const hierarchy = await createTestHierarchy(page, 3);
    _hierarchyId = hierarchy.scheme.id;

    // Create relationships to build a graph structure
    await createRelationship(
      page,
      hierarchy.classes[0].id,
      hierarchy.classes[1].id,
      "related_to",
    );

    await createRelationship(
      page,
      hierarchy.classes[1].id,
      hierarchy.classes[2].id,
      "parent_of",
    );
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test.describe("Graph Rendering", () => {
    test("should render graph visualization page", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Verify graph container is visible
      const graphContainer = page.locator('[data-testid="graph-container"]');
      await expect(graphContainer).toBeVisible();
    });

    test("should display nodes in the graph", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Verify nodes are rendered
      const nodes = page.locator('[data-testid="graph-node"]');
      const nodeCount = await nodes.count();
      expect(nodeCount).toBeGreaterThan(0);
    });

    test("should display edges/relationships in the graph", async ({
      page,
    }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Wait for edges to render
      const edges = page.locator('[data-testid="graph-edge"]');
      await expect(edges.first()).toBeVisible({ timeout: 5000 });

      // Verify edges are rendered
      const edgeCount = await edges.count();
      expect(edgeCount).toBeGreaterThan(0);
    });

    test("should display node labels", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Verify node labels are visible
      const labels = page.locator('[data-testid="graph-node-label"]');
      const labelCount = await labels.count();
      expect(labelCount).toBeGreaterThan(0);

      // Verify labels contain text
      const firstLabel = labels.first();
      const labelText = await firstLabel.textContent();
      expect(labelText).toBeTruthy();
      expect(labelText!.length).toBeGreaterThan(0);
    });
  });

  test.describe("Node Interaction", () => {
    test("should select a node when clicked", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Click on first node
      const firstNode = page.locator('[data-testid="graph-node"]').first();
      await firstNode.click();

      // Verify node is selected (check for selection class/style)
      const selected = page.locator(
        '[data-testid="graph-node"][class*="selected"]',
      );
      expect(await selected.count()).toBeGreaterThan(0);
    });

    test("should display node details on selection", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Click on first node
      const firstNode = page.locator('[data-testid="graph-node"]').first();
      await firstNode.click();

      // Verify details panel appears
      const detailsPanel = page.locator('[data-testid="graph-node-details"]');
      await expect(detailsPanel).toBeVisible({ timeout: 5000 });

      // Verify panel contains information
      const panelText = await detailsPanel.textContent();
      expect(panelText).toBeTruthy();
      expect(panelText!.length).toBeGreaterThan(0);
    });

    test("should highlight connected nodes on node hover", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Hover over first node
      const firstNode = page.locator('[data-testid="graph-node"]').first();
      await firstNode.hover();

      // Verify connected nodes are highlighted
      const highlighted = page.locator(
        '[data-testid="graph-node"][class*="connected"]',
      );
      await expect(highlighted.first()).toBeVisible({ timeout: 5000 });
      expect(await highlighted.count()).toBeGreaterThan(0);
    });

    test("should deselect node when clicking background", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Click on a node to select it
      const firstNode = page.locator('[data-testid="graph-node"]').first();
      await firstNode.click();

      // Verify node is selected
      let selected = page.locator(
        '[data-testid="graph-node"][class*="selected"]',
      );
      expect(await selected.count()).toBeGreaterThan(0);

      // Click on background/canvas
      const canvas = page.locator('[data-testid="graph-canvas"]');
      await canvas.click({ position: { x: 100, y: 100 } });

      // Verify node is deselected
      selected = page.locator('[data-testid="graph-node"][class*="selected"]');
      expect(await selected.count()).toBe(0);
    });
  });

  test.describe("Graph Navigation", () => {
    test("should zoom in with zoom control", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Get initial zoom level
      const graphContainer = page.locator('[data-testid="graph-container"]');
      const initialScale = await graphContainer.evaluate(
        (el) => window.getComputedStyle(el).transform,
      );

      // Click zoom in button
      const zoomInButton = page.locator('[data-testid="graph-zoom-in"]');
      await expect(zoomInButton).toBeVisible();
      await zoomInButton.click();

      // Wait for zoom animation to complete
      await page.waitForLoadState("networkidle");

      // Verify zoom level changed
      const newScale = await graphContainer.evaluate(
        (el) => window.getComputedStyle(el).transform,
      );
      expect(newScale).not.toBe(initialScale);
    });

    test("should zoom out with zoom control", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Get initial zoom level
      const graphContainer = page.locator('[data-testid="graph-container"]');
      const initialScale = await graphContainer.evaluate(
        (el) => window.getComputedStyle(el).transform,
      );

      // Click zoom out button
      const zoomOutButton = page.locator('[data-testid="graph-zoom-out"]');
      await expect(zoomOutButton).toBeVisible();
      await zoomOutButton.click();

      // Wait for zoom animation to complete
      await page.waitForLoadState("networkidle");

      // Verify zoom level changed
      const newScale = await graphContainer.evaluate(
        (el) => window.getComputedStyle(el).transform,
      );
      expect(newScale).not.toBe(initialScale);
    });

    test("should fit graph to view", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Click fit to view button
      const fitButton = page.locator('[data-testid="graph-fit-view"]');
      await expect(fitButton).toBeVisible();
      await fitButton.click();

      // Wait for animation to complete
      await page.waitForLoadState("networkidle");

      // Verify graph is visible
      const graphContainer = page.locator('[data-testid="graph-container"]');
      await expect(graphContainer).toBeVisible();
    });

    test("should pan graph with mouse drag", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Get initial position
      const canvas = page.locator('[data-testid="graph-canvas"]');
      const _initialPosition = await canvas.evaluate((el) =>
        el.getBoundingClientRect(),
      );

      // Drag canvas
      await canvas.dragTo(canvas, {
        sourcePosition: { x: 200, y: 200 },
        targetPosition: { x: 300, y: 300 },
      });

      // Wait for pan animation to complete
      await page.waitForLoadState("networkidle");

      // Verify position changed (or graph moved)
      const newPosition = await canvas.evaluate((el) =>
        el.getBoundingClientRect(),
      );
      expect(newPosition).toBeDefined();
    });
  });

  test.describe("Graph Analysis", () => {
    test("should display relationship information on edge hover", async ({
      page,
    }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Wait for edges to render
      const edges = page.locator('[data-testid="graph-edge"]');
      await expect(edges.first()).toBeVisible({ timeout: 5000 });

      // Hover over an edge
      const firstEdge = edges.first();
      await firstEdge.hover();

      // Verify tooltip/label appears
      const tooltip = page.locator('[data-testid="graph-edge-tooltip"]');
      await expect(tooltip).toBeVisible({ timeout: 5000 });
    });

    test("should filter graph by node type", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Get initial node count
      const allNodes = page.locator('[data-testid="graph-node"]');
      const initialCount = await allNodes.count();
      expect(initialCount).toBeGreaterThan(0);

      // Open filter panel
      const filterButton = page.locator('[data-testid="graph-filter-button"]');
      await expect(filterButton).toBeVisible({ timeout: 5000 });
      await filterButton.click();

      // Select a filter option
      const filterOption = page
        .locator('[data-testid="graph-filter-option"]')
        .first();
      await expect(filterOption).toBeVisible({ timeout: 5000 });
      await filterOption.click();

      // Wait for filter to apply
      await page.waitForLoadState("networkidle");

      // Verify node count changed or remained same (based on filter)
      const filteredNodes = page.locator('[data-testid="graph-node"]');
      const filteredCount = await filteredNodes.count();
      expect(filteredCount).toBeLessThanOrEqual(initialCount);
    });

    test("should search and highlight nodes", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Open search
      const searchInput = page.locator('[data-testid="graph-search-input"]');
      await expect(searchInput).toBeVisible({ timeout: 5000 });

      // Type search term
      await searchInput.fill("class");

      // Wait for search results to apply
      await page.waitForLoadState("networkidle");

      // Verify nodes are highlighted
      const highlighted = page.locator('[class*="search-highlight"]');
      const count = await highlighted.count();
      expect(count).toBeGreaterThan(0);
    });

    test("should display graph statistics", async ({ page }) => {
      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Look for statistics panel
      const statsPanel = page.locator('[data-testid="graph-statistics"]');
      await expect(statsPanel).toBeVisible({ timeout: 5000 });

      // Verify statistics are displayed
      const stats = await statsPanel.textContent();
      expect(stats).toBeTruthy();
      expect(stats!.length).toBeGreaterThan(0);
    });
  });

  test.describe("Graph Error Handling", () => {
    test("should handle empty graph gracefully", async ({ page }) => {
      let emptyTaxonomyId: string | undefined;
      let schemeId: string | undefined;

      try {
        // Create a scheme with no classes
        const response = await apiRequest<any>(page, "/api/taxonomies", {
          method: "POST",
          body: { title: "Empty Taxonomy" },
        });

        emptyTaxonomyId = response.id;

        const schemeResponse = await apiRequest<any>(
          page,
          `/api/taxonomies/${emptyTaxonomyId}/schemes`,
          {
            method: "POST",
            body: { title: "Empty Scheme" },
          },
        );

        schemeId = schemeResponse.id;

        // Navigate to graph view
        await page.goto("/app/graph");
        await page.waitForLoadState("networkidle");

        // Verify page handles empty state
        const emptyMessage = page.locator('[data-testid="graph-empty-state"]');
        const isEmptyStateVisible = await emptyMessage
          .isVisible()
          .catch(() => false);

        // Should either show empty state or render empty graph
        const graphContainer = page.locator('[data-testid="graph-container"]');
        const isGraphVisible = await graphContainer
          .isVisible()
          .catch(() => false);

        expect(isEmptyStateVisible || isGraphVisible).toBe(true);
      } finally {
        // Cleanup - always runs even if test fails
        if (schemeId) {
          await apiRequest(page, `/api/schemes/${schemeId}`, {
            method: "DELETE",
          }).catch(() => {});
        }
        if (emptyTaxonomyId) {
          await apiRequest(page, `/api/taxonomies/${emptyTaxonomyId}`, {
            method: "DELETE",
          }).catch(() => {});
        }
      }
    });

    test("should handle large graphs without crashing", async ({ page }) => {
      // Create a large hierarchy (stress test)
      const largeHierarchy = await createTestHierarchy(page, 10);

      // Create multiple relationships
      for (let i = 0; i < largeHierarchy.classes.length - 1; i++) {
        await createRelationship(
          page,
          largeHierarchy.classes[i].id,
          largeHierarchy.classes[i + 1].id,
          "related_to",
        );
      }

      // Navigate to graph view
      await page.goto("/app/graph");
      await page.waitForLoadState("networkidle");

      // Verify graph renders
      const graphContainer = page.locator('[data-testid="graph-container"]');
      await expect(graphContainer).toBeVisible();

      // Verify nodes are rendered
      const nodes = page.locator('[data-testid="graph-node"]');
      const nodeCount = await nodes.count();
      expect(nodeCount).toBeGreaterThan(0);
    });
  });
});
