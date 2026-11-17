import type { Locator, Page } from "@playwright/test";
import { test, expect } from "../../fixtures/app-test";
import { apiRequest } from "../../fixtures/api-client";
import {
  clearTestData,
  createClass,
  createConceptScheme,
  createPropertyDefinition,
  createTaxonomy,
  type ConceptScheme,
  type Individual,
  type OntologyClass,
  type PropertyDefinition,
  type Taxonomy,
} from "../../fixtures/test-helpers";

/**
 * Proposal review page (/app/proposals/$proposalId/review): an extraction
 * reviewed against its whole source.
 * Plan: e2e/documentation/specs/proposal-review-page.md (GitHub #1611).
 *
 * No LLM call is made. The proposal is seeded through the public API with
 * evidence passages into a pasted-text source; every decision hits the real
 * isolated backend and is checked through GET /api/proposals/{id}.
 */

const TEXT = "The Billing Service sends invoices through the Mail Gateway to Customers.";
const SOURCE_TITLE = "E2E Review Notes";
const NOTE = "A group of readers, not a component";

interface Dataset {
  id: string;
  identifier: string;
}

interface Source {
  id: string;
  status: string;
}

interface SourceText {
  start: number;
  text: string;
}

interface Passage {
  source_id: string;
  page: number;
  start: number;
  end: number;
  quote: string;
}

interface ProposedOperation {
  id: string;
  seq: number;
  status: string;
  added_by_reviewer?: boolean;
  fields?: Record<string, unknown>;
  result_entity_id?: string | null;
  reason?: string | null;
  reason_code?: string | null;
  applied_fields?: Record<string, unknown> | null;
}

interface ChangeProposal {
  id: string;
  operations: ProposedOperation[];
}

interface GoldDecision {
  operation_id: string;
  decision: string;
  added: boolean;
  annotations?: Record<string, unknown> | null;
}

interface GoldPage {
  items: GoldDecision[];
  total: number;
}

/** A gold check's origin and mapping, as extraction_benchmark.py check records them. */
const GOLD_DOCUMENT = "e2e_gold_doc";
function goldCheckMetadata() {
  const origin = {
    pipeline_type: "individual_extraction",
    implementation_id: "gold_check",
    configuration_ref: "gold",
    configuration_version: 1,
    digest: "e2e0gold0001",
  };
  return {
    origin,
    gold_check: {
      document: GOLD_DOCUMENT,
      split: "dev",
      elements: {
        billing: { key: "billing", tier: "core", acceptable_classes: [], aliases: ["Billing"] },
        gateway: { key: "gateway", tier: "supporting", acceptable_classes: [], aliases: [] },
        customers: { key: "customers", tier: "core", acceptable_classes: [], aliases: [] },
      },
      relationships: {
        "4": { source: "gateway", predicate: "serves", target: "customers", tier: "core" },
      },
    },
  };
}

interface EntitySource {
  source_id: string;
  proposal_id: string;
  quote?: string | null;
}

type OpKey = "billing" | "gateway" | "customers" | "serves";

interface ReviewSeed {
  taxonomy: Taxonomy;
  scheme: ConceptScheme;
  appService: OntologyClass;
  techNode: OntologyClass;
  actor: OntologyClass;
  property: PropertyDefinition;
  dataset: Dataset;
  source: Source;
  proposal: ChangeProposal;
  ops: Record<OpKey, string>;
}

/** Seed a pending extraction proposal whose elements cite passages in a pasted source. */
async function seedReviewProposal(
  page: Page,
  { goldCheck = false }: { goldCheck?: boolean } = {},
): Promise<ReviewSeed> {
  const taxonomy = await createTaxonomy(page, { title: "E2E Review Taxonomy" });
  const scheme = await createConceptScheme(page, taxonomy.id, { title: "E2E Review Layer" });
  const appService = await createClass(page, scheme.id, {
    title: "E2E Review Application Service",
    description: "A service an application exposes to its users.",
  });
  const techNode = await createClass(page, scheme.id, {
    title: "E2E Review Technology Node",
    description: "A piece of infrastructure that runs or carries software.",
  });
  const actor = await createClass(page, scheme.id, {
    title: "E2E Review Business Actor",
    description: "A person or organisation that takes part in the business.",
  });
  const property = await createPropertyDefinition(page, {
    identifier: "e2e_review_serves",
    title: "E2E Review Serves",
  });
  const dataset = await apiRequest<Dataset>(page, "/api/datasets", {
    method: "POST",
    body: { taxonomy_id: taxonomy.id, identifier: "e2e-review", title: "E2E Review" },
  });
  const source = await apiRequest<Source>(page, "/api/sources", {
    method: "POST",
    body: { taxonomy_id: taxonomy.id, dataset: "e2e-review", title: SOURCE_TITLE, text: TEXT },
  });
  expect(source.status, "pasted text is ready at once").toBe("ready");

  // Offsets come from the stored text, not TEXT: the reader may normalise it.
  const sourceText = await apiRequest<SourceText>(page, `/api/sources/${source.id}/text`);
  const passage = (quote: string): Passage => {
    const at = sourceText.text.indexOf(quote);
    expect(at, `"${quote}" is in the source text`).toBeGreaterThanOrEqual(0);
    const start = sourceText.start + at;
    return { source_id: source.id, page: 1, start, end: start + quote.length, quote };
  };

  const proposal = await apiRequest<ChangeProposal>(page, "/api/proposals", {
    method: "POST",
    body: {
      taxonomy_id: taxonomy.id,
      dataset_id: dataset.id,
      title: "E2E review extraction",
      source: "pipeline",
      source_detail: "e2e seed: individual_extraction",
      // The source it was extracted from: the Review page offers adding a missed element.
      client_metadata: {
        source_id: source.id,
        ...(goldCheck ? goldCheckMetadata() : {}),
      },
      operations: [
        {
          seq: 1,
          op: "create",
          kind: "individual",
          ref: "billing",
          fields: { title: "Billing Service", class_ids: [appService.id] },
          evidence: [passage("Billing Service")],
          probability: 0.92,
        },
        {
          seq: 2,
          op: "create",
          kind: "individual",
          ref: "gateway",
          fields: { title: "Mail Gateway", class_ids: [appService.id] },
          evidence: [passage("Mail Gateway")],
          probability: 0.85,
        },
        {
          seq: 3,
          op: "create",
          kind: "individual",
          ref: "customers",
          fields: { title: "Customers", class_ids: [appService.id] },
          evidence: [passage("Customers")],
          probability: 0.6,
        },
        {
          seq: 4,
          op: "create",
          kind: "relationship",
          fields: {
            source_id: "$gateway",
            target_id: "$customers",
            property_definition_id: property.id,
          },
          probability: 0.8,
        },
      ],
    },
  });

  // The default approval policy auto-applies nothing: a change here fails loudly.
  expect(proposal.operations.map((o) => o.status)).toEqual([
    "pending",
    "pending",
    "pending",
    "pending",
  ]);
  const idOf = (seq: number) => {
    const operation = proposal.operations.find((o) => o.seq === seq);
    expect(operation, `operation #${seq} was created`).toBeDefined();
    return operation!.id;
  };
  const ops: Record<OpKey, string> = {
    billing: idOf(1),
    gateway: idOf(2),
    customers: idOf(3),
    serves: idOf(4),
  };

  return {
    taxonomy,
    scheme,
    appService,
    techNode,
    actor,
    property,
    dataset,
    source,
    proposal,
    ops,
  };
}

/** One operation of the proposal, as the server has it now. */
async function operationOf(
  page: Page,
  proposalId: string,
  operationId: string,
): Promise<ProposedOperation> {
  const proposal = await apiRequest<ChangeProposal>(page, `/api/proposals/${proposalId}`);
  const operation = proposal.operations.find((o) => o.id === operationId);
  expect(operation, `operation ${operationId} is in the proposal`).toBeDefined();
  return operation!;
}

/**
 * An element's highlight in the source: the registered review-mark narrowed by
 * its passage (each seeded quote occurs once), checked against its operation id.
 */
async function markOf(page: Page, quote: string, operationId: string): Promise<Locator> {
  const mark = page
    .getByTestId("review-source-text")
    .getByTestId("review-mark")
    .filter({ hasText: quote });
  await expect(mark).toHaveCount(1);
  await expect(mark).toHaveAttribute("data-span-keys", operationId);
  return mark;
}

const row = (page: Page, operationId: string) => page.getByTestId(`review-row-${operationId}`);

test.describe("Proposal review page", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("opens from the proposal page and shows the source, elements and first awaiting element", async ({
    page,
  }) => {
    const seed = await seedReviewProposal(page);
    const { proposal, ops, scheme } = seed;

    await page.goto(`/app/proposals/${proposal.id}`);
    await page.waitForLoadState("networkidle");

    // 1-3. Entry from the proposal page.
    await expect(page.getByTestId("proposal-page")).toBeVisible();
    await expect(page.getByTestId("proposal-tally")).toHaveText("4 of 4 need a decision");
    await page.getByTestId("proposal-review-against-source").click();
    await expect(page).toHaveURL(new RegExp(`/app/proposals/${proposal.id}/review$`));
    await expect(page.getByTestId("review-page")).toBeVisible();

    // 4. Header and origin line (no pipeline run: falls back to source_detail).
    const header = page.getByTestId("review-header");
    await expect(header).toContainText(`Review extraction: ${SOURCE_TITLE}`);
    await expect(header).toContainText(`SOURCE ${SOURCE_TITLE}`);
    await expect(header).toContainText("DATASET e2e-review");
    await expect(page.getByTestId("review-finish")).toBeVisible();
    const origin = page.getByTestId("review-origin-line");
    await expect(origin).toContainText("Proposed by");
    await expect(origin).toContainText("e2e seed: individual_extraction");

    // 5. Progress.
    await expect(page.getByTestId("review-progress")).toBeVisible();
    await expect(page.getByTestId("review-progress-decided")).toHaveText("0 / 4");
    await expect(page.getByTestId("review-progress-counts")).toHaveText(
      "0 correct · 0 class changed · 0 not elements · 0 added",
    );
    await expect(page.getByTestId("review-time")).toHaveText(/^\d+:\d{2} on this review$/);

    // 6. Source pane: legend, whole text, three awaiting highlights.
    await expect(page.getByTestId("review-panes")).toBeVisible();
    const legend = page.getByTestId("review-source").getByTestId("review-legend");
    for (const label of [
      "Awaiting",
      "Correct",
      "Class changed",
      "Not an element",
      "Added by you",
    ]) {
      await expect(legend).toContainText(label);
    }
    await expect(page.getByTestId("review-source-text")).toContainText(TEXT);
    await expect(page.getByTestId("review-mark")).toHaveCount(3);
    const billingMark = await markOf(page, "Billing Service", ops.billing);
    const gatewayMark = await markOf(page, "Mail Gateway", ops.gateway);
    const customersMark = await markOf(page, "Customers", ops.customers);
    for (const mark of [billingMark, gatewayMark, customersMark]) {
      await expect(mark).toHaveClass(/\breview-mark--awaiting\b/);
    }

    // 7. Elements: one layer group in order, then the relationships group.
    await expect(page.getByTestId("review-elements")).toBeVisible();
    const filter = page.getByTestId("review-filter");
    await expect(filter).toContainText("Awaiting · 4");
    await expect(filter).toContainText("All · 4");
    const list = page.getByTestId("review-element-list");
    const groups = list.getByRole("group");
    await expect(groups).toHaveCount(2);
    await expect(groups.nth(0)).toHaveAttribute("data-testid", `review-group-${scheme.id}`);
    await expect(groups.nth(1)).toHaveAttribute("data-testid", "review-group-relationships");
    const layerRows = page.getByTestId(`review-group-${scheme.id}`).getByRole("option");
    await expect(layerRows).toHaveCount(3);
    await expect(layerRows.nth(0)).toHaveAttribute("data-testid", `review-row-${ops.billing}`);
    await expect(layerRows.nth(1)).toHaveAttribute("data-testid", `review-row-${ops.gateway}`);
    await expect(layerRows.nth(2)).toHaveAttribute("data-testid", `review-row-${ops.customers}`);
    const relationshipRows = page.getByTestId("review-group-relationships").getByRole("option");
    await expect(relationshipRows).toHaveCount(1);
    await expect(relationshipRows.first()).toHaveAttribute(
      "data-testid",
      `review-row-${ops.serves}`,
    );
    await expect(row(page, ops.serves)).toContainText("Mail Gateway");
    await expect(row(page, ops.serves)).toContainText("Customers");

    // 8. The first awaiting element is selected.
    await expect(row(page, ops.billing)).toHaveAttribute("aria-selected", "true");
    await expect(row(page, ops.billing)).toHaveAttribute("data-verdict", "awaiting");
    await expect(billingMark).toHaveAttribute("aria-current", "true");
    await expect(billingMark).toHaveClass(/\breview-mark--selected\b/);

    // 9. Inspector.
    await expect(page.getByTestId("review-inspector")).toBeVisible();
    await expect(page.getByTestId("review-inspector-eyebrow")).toContainText("Individual · p 0.92");
    await expect(page.getByTestId("review-inspector-title")).toHaveText("Billing Service");
    await expect(page.getByTestId("review-inspector-class")).toHaveText(
      "E2E Review Application Service",
    );
    await expect(page.getByTestId("review-inspector-status")).toHaveText("awaiting");
    await expect(page.getByTestId("review-evidence")).toContainText("Billing Service");
    await expect(page.getByTestId("review-definition")).toContainText(
      "A service an application exposes to its users.",
    );
    await expect(page.getByTestId("review-correct")).toBeEnabled();
    await expect(page.getByTestId("review-better-class")).toBeVisible();
    await expect(page.getByTestId("review-reasons")).toBeVisible();
    await expect(page.getByTestId("review-relationships")).toContainText("Its relationships · 0");

    // 10. A highlight click opens its element.
    await customersMark.click();
    await expect(row(page, ops.customers)).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("review-inspector-title")).toHaveText("Customers");
    await expect(customersMark).toHaveAttribute("aria-current", "true");
    await expect(
      page.getByTestId("review-relationships").getByTestId(`review-relationship-${ops.serves}`),
    ).toBeVisible();

    // Nothing was decided.
    const after = await apiRequest<ChangeProposal>(page, `/api/proposals/${proposal.id}`);
    expect(after.operations.map((o) => o.status)).toEqual([
      "pending",
      "pending",
      "pending",
      "pending",
    ]);
  });

  test("correct, a better class, not an element, then the relationship whose end was rejected", async ({
    page,
  }) => {
    const seed = await seedReviewProposal(page);
    const { proposal, ops, appService, techNode, source } = seed;

    await page.goto(`/app/proposals/${proposal.id}/review`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("review-page")).toBeVisible();
    await expect(row(page, ops.billing)).toHaveAttribute("aria-selected", "true");

    const decided = page.getByTestId("review-progress-decided");
    const counts = page.getByTestId("review-progress-counts");
    const title = page.getByTestId("review-inspector-title");

    // 1. Correct (element 1).
    await page.getByTestId("review-correct").click();
    await expect(row(page, ops.billing)).toHaveAttribute("data-verdict", "correct");
    const billingMark = await markOf(page, "Billing Service", ops.billing);
    await expect(billingMark).toHaveClass(/\breview-mark--correct\b/);
    await expect(decided).toHaveText("1 / 4");
    await expect(counts).toContainText("1 correct");
    await expect(row(page, ops.gateway)).toHaveAttribute("aria-selected", "true");
    await expect(title).toHaveText("Mail Gateway");
    const gatewayMark = await markOf(page, "Mail Gateway", ops.gateway);
    await expect(gatewayMark).toHaveAttribute("aria-current", "true");

    const billingOp = await operationOf(page, proposal.id, ops.billing);
    expect(billingOp.status).toBe("applied");
    expect(billingOp.result_entity_id).toEqual(expect.any(String));
    const billing = await apiRequest<Individual>(
      page,
      `/api/individuals/${billingOp.result_entity_id}`,
    );
    expect(billing.title).toBe("Billing Service");
    expect(billing.class_ids).toEqual([appService.id]);
    const billingSources = await apiRequest<EntitySource[]>(
      page,
      `/api/individuals/${billingOp.result_entity_id}/sources`,
    );
    expect(billingSources).toHaveLength(1);
    expect(billingSources[0]).toMatchObject({
      source_id: source.id,
      proposal_id: proposal.id,
      quote: "Billing Service",
    });

    // 2. A better class (element 2), from the picker.
    const relationships = page.getByTestId("review-relationships");
    await expect(relationships).toContainText("Its relationships · 1");
    await expect(relationships.getByTestId(`review-relationship-${ops.serves}`)).toBeVisible();
    const picker = page.getByTestId("review-class-picker");
    await expect(picker).toContainText("Search all 3 classes");
    await picker.getByRole("combobox").fill("Technology");
    const options = picker.getByRole("option");
    await expect(options).toHaveCount(1);
    await expect(options.first()).toHaveText("E2E Review Technology Node");
    await options.first().click();

    await expect(row(page, ops.gateway)).toHaveAttribute("data-verdict", "changed");
    await expect(gatewayMark).toHaveClass(/\breview-mark--changed\b/);
    await expect(decided).toHaveText("2 / 4");
    await expect(counts).toContainText("1 class changed");
    await expect(row(page, ops.customers)).toHaveAttribute("aria-selected", "true");
    await expect(title).toHaveText("Customers");

    const gatewayOp = await operationOf(page, proposal.id, ops.gateway);
    expect(gatewayOp.status).toBe("applied");
    expect(gatewayOp.applied_fields?.class_ids).toEqual([techNode.id]);
    const gateway = await apiRequest<Individual>(
      page,
      `/api/individuals/${gatewayOp.result_entity_id}`,
    );
    expect(gateway.class_ids).toEqual([techNode.id]);

    // 3. Not an element (element 3), with a reason and a note.
    await page.getByTestId("review-note").fill(NOTE);
    await page.getByTestId("review-reason-mentioned_only").click();

    await expect(row(page, ops.customers)).toHaveAttribute("data-verdict", "rejected");
    const customersMark = await markOf(page, "Customers", ops.customers);
    await expect(customersMark).toHaveClass(/\breview-mark--rejected\b/);
    await expect(decided).toHaveText("3 / 4");
    await expect(counts).toHaveText("1 correct · 1 class changed · 1 not elements · 0 added");
    await expect(page.getByTestId("review-filter")).toContainText("Awaiting · 1");
    await expect(row(page, ops.serves)).toHaveAttribute("aria-selected", "true");

    const customersOp = await operationOf(page, proposal.id, ops.customers);
    expect(customersOp.status).toBe("rejected");
    expect(customersOp.reason_code).toBe("mentioned_only");
    expect(customersOp.reason).toBe(NOTE);
    expect(customersOp.result_entity_id ?? null).toBeNull();

    // 4. The decided element is read-only; its relationship can only be rejected.
    await row(page, ops.customers).click();
    await expect(row(page, ops.customers)).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("review-decided")).toContainText(
      "Not an element: Mentioned only.",
    );
    await expect(page.getByTestId("review-decided-note")).toHaveText(NOTE);
    await expect(page.getByTestId("review-inspector-status")).toHaveText("not an element");
    await expect(page.getByTestId("review-correct")).toHaveCount(0);
    await expect(page.getByTestId("review-better-class")).toHaveCount(0);
    await expect(page.getByTestId("review-reasons")).toHaveCount(0);

    const serves = relationships.getByTestId(`review-relationship-${ops.serves}`);
    await expect(serves).toContainText("Mail Gateway");
    await expect(serves).toContainText("e2e_review_serves");
    await expect(serves).toContainText("Customers");
    await expect(serves).toContainText("awaiting");
    await serves.click();

    await expect(row(page, ops.serves)).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("review-inspector-eyebrow")).toContainText(
      "Relationship · p 0.80",
    );
    await expect(title).toContainText("Mail Gateway");
    await expect(title).toContainText("Customers");
    await expect(page.getByTestId("review-inspector-status")).toHaveText("awaiting");
    const callout = page.getByTestId("review-ends-callout");
    await expect(callout).toBeVisible();
    await expect(callout).toContainText("#3 was rejected");
    await expect(callout).toContainText("Reject it.");
    await expect(page.getByTestId("review-correct")).toHaveCount(0);
    await expect(page.getByTestId("review-reasons")).toBeVisible();
    await expect(page.getByTestId("review-reason-not_in_text")).toBeEnabled();
    await expect(page.getByTestId("review-inspector-class")).toHaveCount(0);
    await expect(page.getByTestId("review-better-class")).toHaveCount(0);

    const servesOp = await operationOf(page, proposal.id, ops.serves);
    expect(servesOp.status).toBe("pending");

    // 5. Finish: back to the proposal page with the new tally.
    await page.getByTestId("review-finish").click();
    await expect(page).toHaveURL(new RegExp(`/app/proposals/${proposal.id}$`));
    await expect(page.getByTestId("proposal-tally")).toHaveText("1 of 4 need a decision");
    await expect(page.getByTestId("proposal-decided-counts")).toHaveText("2 applied · 1 rejected");
  });

  test("adds a missed element from text selected in the source", async ({ page }) => {
    const seed = await seedReviewProposal(page);
    const { proposal, techNode, taxonomy } = seed;

    await page.goto(`/app/proposals/${proposal.id}/review`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("review-source-hint")).toHaveText(
      "Select any text to add an element the pipeline missed. Click a highlight to open it.",
    );

    // 1. Select "invoices" in the source text (no highlight covers it).
    await page.getByTestId("review-source-text").evaluate((container, quote) => {
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode as Text;
        const at = node.data.indexOf(quote);
        if (at < 0) continue;
        const range = document.createRange();
        range.setStart(node, at);
        range.setEnd(node, at + quote.length);
        const selection = window.getSelection()!;
        selection.removeAllRanges();
        selection.addRange(range);
        return;
      }
      throw new Error(`"${quote}" is not in the source text`);
    }, "invoices");
    await page.getByTestId("review-source-selectable").dispatchEvent("mouseup");

    // 2. The form: the selection as the title, a class, Add element.
    const dialog = page.getByRole("dialog", { name: "Selected text · not in the proposal" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByTestId("review-add-quote")).toHaveText("invoices");
    const titleInput = dialog.getByLabel("Title");
    await expect(titleInput).toHaveValue("invoices");
    await titleInput.fill("Invoices");
    const picker = dialog.getByTestId("review-add-class-picker");
    await picker.getByRole("combobox").fill("Technology");
    await picker.getByRole("option", { name: "E2E Review Technology Node" }).click();
    await expect(dialog.getByTestId("review-add-class-chosen")).toHaveText(
      "E2E Review Technology Node",
    );
    await dialog.getByRole("button", { name: "Add element" }).click();

    // 3. Added: closed, highlighted, listed, counted and open in the inspector.
    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId("review-inspector-title")).toHaveText("Invoices");
    await expect(page.getByTestId("review-inspector-status")).toHaveText("added");
    await expect(page.getByTestId("review-progress-counts")).toContainText("1 added");
    await expect(page.getByTestId("review-progress-decided")).toHaveText("1 / 5");

    const after = await apiRequest<ChangeProposal>(page, `/api/proposals/${proposal.id}`);
    const added = after.operations.find((o) => o.added_by_reviewer);
    expect(added, "the added operation is in the proposal").toBeDefined();
    expect(added!.status).toBe("applied");
    expect(added!.fields).toMatchObject({ title: "Invoices", class_ids: [techNode.id] });
    const mark = await markOf(page, "invoices", added!.id);
    await expect(mark).toHaveClass(/\breview-mark--added\b/);
    await expect(row(page, added!.id)).toHaveAttribute("data-verdict", "added");

    const gold = await apiRequest<GoldPage>(
      page,
      `/api/taxonomies/${taxonomy.id}/gold?proposal_id=${proposal.id}`,
    );
    const decision = gold.items.find((d) => d.operation_id === added!.id);
    expect(decision).toMatchObject({ decision: "applied", added: true });
  });

  test("gold mode: flips a tier and records it with the decision", async ({ page }) => {
    const seed = await seedReviewProposal(page, { goldCheck: true });
    const { proposal, ops, taxonomy } = seed;

    await page.goto(`/app/proposals/${proposal.id}/review`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("review-header")).toContainText(`Gold check: ${GOLD_DOCUMENT}`);
    await expect(page.getByTestId("review-gold-split")).toHaveText("dev");
    await expect(page.getByTestId("review-gold-aliases")).toHaveText("Also called Billing");

    // Billing Service is core in gold: flip it to supporting, then accept it.
    const tier = page.getByTestId("review-tier");
    await expect(tier.getByRole("radio", { name: "Core" })).toHaveAttribute("aria-checked", "true");
    await tier.getByRole("radio", { name: "Supporting" }).click();
    await expect(tier.getByRole("radio", { name: "Supporting" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await page.getByTestId("review-correct").click();
    await expect(row(page, ops.billing)).toHaveAttribute("data-verdict", "correct");

    // Rejecting needs a note in gold mode.
    await expect(row(page, ops.gateway)).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("review-reason-too_generic")).toBeDisabled();
    await expect(page.getByTestId("review-note-required")).toBeVisible();
    await page.getByTestId("review-note").fill("A channel, not a component");
    await expect(page.getByTestId("review-note-required")).toHaveCount(0);
    await expect(page.getByTestId("review-reason-too_generic")).toBeEnabled();

    const gold = await apiRequest<GoldPage>(
      page,
      `/api/taxonomies/${taxonomy.id}/gold?proposal_id=${proposal.id}`,
    );
    const decision = gold.items.find((d) => d.operation_id === ops.billing);
    expect(decision).toMatchObject({ decision: "applied", annotations: { tier: "supporting" } });
  });
});
