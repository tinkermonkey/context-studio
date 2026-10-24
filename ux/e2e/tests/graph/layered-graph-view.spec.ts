import type { Page } from "@playwright/test";
import { test, expect } from "../../fixtures/app-test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createIndividual,
  createPropertyDefinition,
  createRelationship,
  clearTestData,
  type ConceptScheme,
} from "../../fixtures/factories";

/**
 * Layered graph view (/app/graph): concept schemes are layers, classes and
 * individuals are nodes. Covers the layer filter, the node inspector, focus
 * mode and the layered/force layout switch.
 *
 * Plan: ux/e2e/documentation/specs/layered-graph-view.md
 *
 * Heimdall renders a hidden measurement copy of every canvas node, so
 * graph-layer-header-* test ids match twice: presence assertions use
 * `.filter({ visible: true })`, absence assertions use toHaveCount(0) on the
 * unfiltered locator. Nodes are located by role + aria-label (role locators
 * skip the aria-hidden measurement copy).
 */

interface Seed {
  app: ConceptScheme;
  biz: ConceptScheme;
}

const NODE_NAMES = [
  "CRM System (individual)",
  "Billing Service (individual)",
  "Order Handling (individual)",
  "Application Component (class)",
  "Business Service (class)",
  "Business Process (class)",
  "Customer Service (class)",
];

async function seedGraph(page: Page): Promise<Seed> {
  const tax = await createTaxonomy(page, { title: "Enterprise Model" });
  const app = await createConceptScheme(page, tax.id, { title: "Application" });
  const biz = await createConceptScheme(page, tax.id, { title: "Business" });

  const appComponent = await createClass(page, app.id, { title: "Application Component" });
  const bizService = await createClass(page, biz.id, { title: "Business Service" });
  const bizProcess = await createClass(page, biz.id, { title: "Business Process" });
  await createClass(page, biz.id, {
    title: "Customer Service",
    parent_class_id: bizService.id,
  });

  const crm = await createIndividual(page, {
    title: "CRM System",
    description: "Customer relationship management platform",
    class_ids: [appComponent.id],
  });
  const billing = await createIndividual(page, {
    title: "Billing Service",
    class_ids: [bizService.id],
  });
  await createIndividual(page, {
    title: "Order Handling",
    class_ids: [bizProcess.id],
  });

  const realizes = await createPropertyDefinition(page, {
    identifier: "realizes",
    title: "Realizes",
  });
  await createRelationship(page, crm.id, billing.id, realizes.id, "realizes");

  return { app, biz };
}

function canvasNode(page: Page, name: string) {
  return page.getByTestId("graph-canvas").getByRole("button", { name, exact: true });
}

function layerHeader(page: Page, schemeId: string) {
  return page.getByTestId(`graph-layer-header-${schemeId}`);
}

test.describe("Layered Graph View", () => {
  let seed: Seed;

  test.beforeEach(async ({ page }) => {
    seed = await seedGraph(page);
    await page.goto("/app/graph");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("graph-page")).toBeVisible();
    await expect(page.getByTestId("graph-canvas")).toBeVisible();
    await expect(page.getByTestId("graph-visible-counts")).toHaveText("3 nodes · 1 edges");
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("layered layout renders one band per concept scheme with the default individual slice", async ({
    page,
  }) => {
    const canvas = page.getByTestId("graph-canvas");
    const layoutToggle = page.getByTestId("graph-layout-toggle");
    const kindFilter = page.getByTestId("graph-node-kind-filter");

    await expect(canvas).toHaveAttribute("data-layout", "layered");
    await expect(layoutToggle.getByRole("radio", { name: "Layered" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(kindFilter.getByRole("radio", { name: "Individuals" })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    const appHeader = layerHeader(page, seed.app.id).filter({ visible: true });
    const bizHeader = layerHeader(page, seed.biz.id).filter({ visible: true });
    await expect(appHeader).toBeVisible();
    await expect(appHeader).toHaveText(/^\s*Application\s*1\s*$/);
    await expect(bizHeader).toBeVisible();
    await expect(bizHeader).toHaveText(/^\s*Business\s*2\s*$/);

    await expect(canvasNode(page, "CRM System (individual)")).toBeVisible();
    await expect(canvasNode(page, "Billing Service (individual)")).toBeVisible();
    await expect(canvasNode(page, "Order Handling (individual)")).toBeVisible();
    await expect(canvasNode(page, "Application Component (class)")).toHaveCount(0);
    await expect(canvasNode(page, "Business Service (class)")).toHaveCount(0);

    await expect(page.getByTestId("graph-visible-counts")).toHaveText("3 nodes · 1 edges");
    await expect(page.getByTestId("graph-layer-legend")).toBeVisible();
    await expect(page.getByTestId("graph-legend-layer")).toHaveCount(2);
    await expect(page.getByTestId("graph-legend-cross-layer-count")).toHaveText("1");
    await expect(page.getByTestId("graph-layer-filter")).toContainText("2 selected");

    // Switch to all node kinds: classes join the canvas.
    await kindFilter.getByRole("radio", { name: "All" }).click();
    await expect(kindFilter.getByRole("radio", { name: "All" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByTestId("graph-visible-counts")).toHaveText("7 nodes · 5 edges");
    await expect(canvasNode(page, "Customer Service (class)")).toBeVisible();
    await expect(canvasNode(page, "Application Component (class)")).toBeVisible();
    await expect(bizHeader).toHaveText(/^\s*Business\s*5\s*$/);
    await expect(page.getByTestId("graph-legend-cross-layer-count")).toHaveText("1");
  });

  test("layer filter hides and restores a layer and the nodes it contains", async ({ page }) => {
    const trigger = page.getByTestId("graph-layer-filter");
    const panel = page.getByTestId("graph-layer-filter-panel");
    const appOption = panel.getByRole("option", { name: /^Application/ });
    const bizOption = panel.getByRole("option", { name: /^Business/ });

    // 1-2: open the panel, both layers selected.
    await trigger.click();
    await expect(trigger).toHaveAttribute("aria-expanded", "true");
    await expect(panel).toBeVisible();
    await expect(appOption).toHaveAttribute("aria-selected", "true");
    await expect(bizOption).toHaveAttribute("aria-selected", "true");

    // 3-4: hide the Application layer and close the panel.
    await appOption.click();
    await expect(appOption).toHaveAttribute("aria-selected", "false");
    await trigger.click();
    await expect(panel).toBeHidden();

    await expect(layerHeader(page, seed.app.id)).toHaveCount(0);
    await expect(canvasNode(page, "CRM System (individual)")).toHaveCount(0);
    await expect(canvasNode(page, "Billing Service (individual)")).toBeVisible();
    await expect(canvasNode(page, "Order Handling (individual)")).toBeVisible();
    await expect(page.getByTestId("graph-visible-counts")).toHaveText("2 nodes · 0 edges");
    await expect(page.getByTestId("graph-legend-cross-layer-count")).toHaveText("0");
    await expect(page.getByTestId("graph-legend-layer")).toHaveCount(1);
    await expect(trigger).toContainText("Business");

    // 5: restore the Application layer.
    await trigger.click();
    await expect(panel).toBeVisible();
    await appOption.click();
    await expect(appOption).toHaveAttribute("aria-selected", "true");
    await trigger.click();
    await expect(panel).toBeHidden();

    await expect(layerHeader(page, seed.app.id).filter({ visible: true })).toBeVisible();
    await expect(canvasNode(page, "CRM System (individual)")).toBeVisible();
    await expect(page.getByTestId("graph-visible-counts")).toHaveText("3 nodes · 1 edges");
    await expect(page.getByTestId("graph-legend-cross-layer-count")).toHaveText("1");

    // 6: deselect every layer.
    await trigger.click();
    await expect(panel).toBeVisible();
    await appOption.click();
    await expect(appOption).toHaveAttribute("aria-selected", "false");
    await bizOption.click();
    await expect(bizOption).toHaveAttribute("aria-selected", "false");
    await trigger.click();
    await expect(panel).toBeHidden();

    await expect(page.getByTestId("graph-canvas-empty")).toBeVisible();
    await expect(page.getByTestId("graph-canvas").getByRole("button")).toHaveCount(0);
    await expect(page.getByTestId("graph-layer-legend")).toHaveCount(0);
    await expect(page.getByTestId("graph-visible-counts")).toHaveText("0 nodes · 0 edges");
    await expect(trigger).toContainText("None");
  });

  test("inspector shows the selected node's details and relationships", async ({ page }) => {
    const inspector = page.getByTestId("node-inspector");
    const crmNode = canvasNode(page, "CRM System (individual)");
    const billingNode = canvasNode(page, "Billing Service (individual)");

    // 1: empty state.
    await expect(inspector).toContainText("No node selected");
    await expect(page.getByTestId("node-inspector-relationship-count")).toHaveCount(0);

    // 2: select CRM System.
    await crmNode.click();
    await expect(crmNode).toHaveAttribute("aria-pressed", "true");
    await expect(inspector).toContainText("CRM System");
    await expect(inspector).toContainText("Individual");
    await expect(inspector).toContainText("Customer relationship management platform");
    await expect(inspector).toContainText("Application Component");
    await expect(inspector).toContainText("Application");
    await expect(inspector).toContainText("Enterprise Model");
    await expect(inspector).toContainText("Realizes");
    await expect(inspector).toContainText("instance of");
    await expect(page.getByTestId("node-inspector-relationship-count")).toHaveText(
      "2 relationships",
    );
    await expect(
      inspector.getByRole("button", { name: "Navigate to Billing Service" }),
    ).toBeVisible();
    await expect(
      inspector.getByRole("button", { name: "Navigate to Application Component" }),
    ).toBeVisible();

    const focusButton = page.getByTestId("node-inspector-focus-button");
    await expect(focusButton).toBeEnabled();
    await expect(focusButton).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByTestId("graph-focus-bar")).toHaveCount(0);

    // 3: switch the selection to Billing Service.
    await billingNode.click();
    await expect(billingNode).toHaveAttribute("aria-pressed", "true");
    await expect(crmNode).toHaveAttribute("aria-pressed", "false");
    await expect(inspector).toContainText("Billing Service");
    await expect(inspector).toContainText("Business Service");
    await expect(inspector).toContainText("Business");
    await expect(inspector.getByRole("button", { name: "Navigate to CRM System" })).toBeVisible();
    await expect(page.getByTestId("node-inspector-relationship-count")).toHaveText(
      "2 relationships",
    );
    await expect(inspector).not.toContainText("Customer relationship management platform");
  });

  test("focus mode shows only the selected node's neighbourhood, by depth, and exits cleanly", async ({
    page,
  }) => {
    const kindFilter = page.getByTestId("graph-node-kind-filter");
    await kindFilter.getByRole("radio", { name: "All" }).click();
    await expect(kindFilter.getByRole("radio", { name: "All" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByTestId("graph-visible-counts")).toHaveText("7 nodes · 5 edges");

    const inspector = page.getByTestId("node-inspector");
    const focusButton = page.getByTestId("node-inspector-focus-button");
    const focusDepth = page.getByTestId("graph-focus-depth");
    const counts = page.getByTestId("graph-visible-counts");
    const crmNode = canvasNode(page, "CRM System (individual)");
    const billingNode = canvasNode(page, "Billing Service (individual)");
    const orderHandlingNode = canvasNode(page, "Order Handling (individual)");

    // 1: focus CRM System at depth 1.
    await crmNode.click();
    await expect(crmNode).toHaveAttribute("aria-pressed", "true");
    await focusButton.click();

    await expect(page.getByTestId("graph-focus-bar")).toBeVisible();
    await expect(page.getByTestId("graph-focus-label")).toHaveText("CRM System");
    await expect(page.getByTestId("graph-layer-filter")).toHaveCount(0);
    await expect(page.getByTestId("graph-class-filter")).toHaveCount(0);
    await expect(focusDepth.getByRole("radio", { name: "1 hop" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(focusButton).toBeDisabled();
    await expect(focusButton).toHaveAttribute("aria-pressed", "true");
    await expect(focusButton).toContainText("Focused");
    await expect(crmNode).toHaveClass(/graph-node--focus/);

    await expect(crmNode).toBeVisible();
    await expect(canvasNode(page, "Application Component (class)")).toBeVisible();
    await expect(billingNode).toBeVisible();
    await expect(orderHandlingNode).toHaveCount(0);
    await expect(canvasNode(page, "Business Process (class)")).toHaveCount(0);
    await expect(canvasNode(page, "Business Service (class)")).toHaveCount(0);
    await expect(canvasNode(page, "Customer Service (class)")).toHaveCount(0);
    await expect(counts).toHaveText("3 nodes · 2 edges");
    await expect(page.getByTestId("graph-legend-cross-layer-count")).toHaveText("1");

    // 2: depth 2 adds Business Service.
    await focusDepth.getByRole("radio", { name: "2 hops" }).click();
    await expect(focusDepth.getByRole("radio", { name: "2 hops" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(canvasNode(page, "Business Service (class)")).toBeVisible();
    await expect(counts).toHaveText("4 nodes · 3 edges");
    await expect(orderHandlingNode).toHaveCount(0);

    // 3: depth 3 adds Customer Service.
    await focusDepth.getByRole("radio", { name: "3 hops" }).click();
    await expect(focusDepth.getByRole("radio", { name: "3 hops" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(canvasNode(page, "Customer Service (class)")).toBeVisible();
    await expect(counts).toHaveText("5 nodes · 4 edges");
    await expect(orderHandlingNode).toHaveCount(0);
    await expect(canvasNode(page, "Business Process (class)")).toHaveCount(0);

    // 4: navigating from the inspector re-focuses on Billing Service.
    await inspector.getByRole("button", { name: "Navigate to Billing Service" }).click();
    await expect(page.getByTestId("graph-focus-label")).toHaveText("Billing Service");
    await expect(billingNode).toHaveClass(/graph-node--focus/);
    await expect(billingNode).toHaveAttribute("aria-pressed", "true");
    await expect(crmNode).not.toHaveClass(/graph-node--focus/);
    await expect(focusDepth.getByRole("radio", { name: "3 hops" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(inspector).toContainText("Billing Service");
    await expect(counts).toHaveText("5 nodes · 4 edges");

    // 5: exit focus restores the pre-focus filter; the selection persists.
    await page.getByTestId("graph-focus-exit").click();
    await expect(page.getByTestId("graph-focus-bar")).toHaveCount(0);
    await expect(page.getByTestId("graph-layer-filter")).toBeVisible();
    await expect(counts).toHaveText("7 nodes · 5 edges");
    await expect(orderHandlingNode).toBeVisible();
    for (const name of NODE_NAMES) {
      await expect(canvasNode(page, name)).not.toHaveClass(/graph-node--focus/);
    }
    await expect(inspector).toContainText("Billing Service");
  });

  test("layout switch between layered and force keeps the same nodes and edges", async ({
    page,
  }) => {
    const canvas = page.getByTestId("graph-canvas");
    const layoutToggle = page.getByTestId("graph-layout-toggle");
    const counts = page.getByTestId("graph-visible-counts");

    // 1: default layered layout with layer headers.
    await expect(canvas).toHaveAttribute("data-layout", "layered");
    await expect(layerHeader(page, seed.app.id).filter({ visible: true })).toBeVisible();

    // 2: switch to force — no layer headers, same node/edge set.
    await layoutToggle.getByRole("radio", { name: "Force" }).click();
    await expect(canvas).toHaveAttribute("data-layout", "force");
    await expect(layoutToggle.getByRole("radio", { name: "Force" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(layerHeader(page, seed.app.id)).toHaveCount(0);
    await expect(layerHeader(page, seed.biz.id)).toHaveCount(0);
    await expect(canvasNode(page, "CRM System (individual)")).toBeVisible();
    await expect(canvasNode(page, "Billing Service (individual)")).toBeVisible();
    await expect(canvasNode(page, "Order Handling (individual)")).toBeVisible();
    await expect(counts).toHaveText("3 nodes · 1 edges");
    await expect(page.getByTestId("graph-legend-layer")).toHaveCount(2);

    // 3: back to layered — headers return, counts unchanged.
    await layoutToggle.getByRole("radio", { name: "Layered" }).click();
    await expect(canvas).toHaveAttribute("data-layout", "layered");
    await expect(layoutToggle.getByRole("radio", { name: "Layered" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(layerHeader(page, seed.app.id).filter({ visible: true })).toBeVisible();
    await expect(layerHeader(page, seed.biz.id).filter({ visible: true })).toBeVisible();
    await expect(counts).toHaveText("3 nodes · 1 edges");
    await expect(page.getByTestId("graph-legend-layer")).toHaveCount(2);
  });
});
