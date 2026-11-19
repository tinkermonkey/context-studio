import type { Page } from "@playwright/test";
import { test, expect } from "../../fixtures/app-test";
import { apiRequest } from "../../fixtures/api-client";
import {
  clearTestData,
  createClass,
  createConceptScheme,
  createTaxonomy,
  type OntologyClass,
} from "../../fixtures/test-helpers";

/**
 * Compare page (/app/proposals/$proposalId/compare/$otherId): two pipelines'
 * open proposals for one source, decided once for both (GitHub #1615).
 *
 * No LLM call is made. Two proposals are seeded through the public API over
 * one pasted-text source, each recording its source and its pipeline origin
 * (client_metadata); every decision hits the real isolated backend and is
 * checked through GET /api/proposals/{id}.
 */

/** Twelve elements both pipelines found with the same class: a sample of 10, and 2 more. */
const AGREED = [
  "Alpha Router",
  "Bravo Queue",
  "Charlie Cache",
  "Delta Store",
  "Echo Index",
  "Foxtrot Broker",
  "Golf Scheduler",
  "Hotel Gateway",
  "India Worker",
  "Juliet Ledger",
  "Kilo Search",
  "Lima Mailer",
];
const DIFFERS = "Mail Gateway";
const ONLY_A = "Billing Service";
const ONLY_B = "Customers";
const TEXT = `${[...AGREED, DIFFERS, ONLY_A, ONLY_B].join(", ")} are named in these notes.`;

interface Dataset {
  id: string;
}

interface Source {
  id: string;
  status: string;
}

interface SourceText {
  start: number;
  text: string;
}

interface ProposedOperation {
  id: string;
  seq: number;
  status: string;
  reason_code?: string | null;
  fields?: Record<string, unknown>;
}

interface ChangeProposal {
  id: string;
  operations: ProposedOperation[];
}

interface Seed {
  a: ChangeProposal;
  b: ChangeProposal;
  service: OntologyClass;
  node: OntologyClass;
  actor: OntologyClass;
}

const origin = (implementation_id: string) => ({
  pipeline_type: "individual_extraction",
  implementation_id,
  configuration_ref: `e2e-${implementation_id}`,
  configuration_version: 1,
  digest: `${implementation_id.slice(0, 6)}000000`,
});

/** Two open individual extractions of one pasted source, by two implementations. */
async function seedComparison(page: Page): Promise<Seed> {
  const taxonomy = await createTaxonomy(page, { title: "E2E Compare Taxonomy" });
  const scheme = await createConceptScheme(page, taxonomy.id, { title: "E2E Compare Layer" });
  const service = await createClass(page, scheme.id, { title: "E2E Compare Service" });
  const node = await createClass(page, scheme.id, { title: "E2E Compare Technology Node" });
  const actor = await createClass(page, scheme.id, { title: "E2E Compare Actor" });
  const dataset = await apiRequest<Dataset>(page, "/api/datasets", {
    method: "POST",
    body: { taxonomy_id: taxonomy.id, identifier: "e2e-compare", title: "E2E Compare" },
  });
  const source = await apiRequest<Source>(page, "/api/sources", {
    method: "POST",
    body: {
      taxonomy_id: taxonomy.id,
      dataset: "e2e-compare",
      title: "E2E Compare Notes",
      text: TEXT,
    },
  });
  expect(source.status, "pasted text is ready at once").toBe("ready");
  const sourceText = await apiRequest<SourceText>(page, `/api/sources/${source.id}/text`);
  const passage = (quote: string) => {
    const at = sourceText.text.indexOf(quote);
    expect(at, `"${quote}" is in the source text`).toBeGreaterThanOrEqual(0);
    const start = sourceText.start + at;
    return { source_id: source.id, page: 1, start, end: start + quote.length, quote };
  };
  const individual = (seq: number, title: string, classId: string) => ({
    seq,
    op: "create",
    kind: "individual",
    ref: `e${seq}`,
    fields: { title, class_ids: [classId] },
    evidence: [passage(title)],
    probability: 0.9,
  });
  const propose = (implementation: string, items: [string, string][]) =>
    apiRequest<ChangeProposal>(page, "/api/proposals", {
      method: "POST",
      body: {
        taxonomy_id: taxonomy.id,
        dataset_id: dataset.id,
        title: `E2E compare: ${implementation}`,
        source: "pipeline",
        source_detail: `e2e seed: ${implementation}`,
        client_metadata: { source_id: source.id, origin: origin(implementation) },
        operations: items.map(([title, classId], i) => individual(i + 1, title, classId)),
      },
    });

  const agreed: [string, string][] = AGREED.map((title) => [title, service.id]);
  const a = await propose("single_call", [...agreed, [DIFFERS, service.id], [ONLY_A, service.id]]);
  const b = await propose("find_then_type", [...agreed, [DIFFERS, node.id], [ONLY_B, actor.id]]);
  for (const proposal of [a, b]) {
    expect(new Set(proposal.operations.map((o) => o.status))).toEqual(new Set(["pending"]));
  }
  return { a, b, service, node, actor };
}

const opTitled = (proposal: ChangeProposal, title: string) =>
  proposal.operations.find((o) => o.fields?.title === title)!;

async function proposalNow(page: Page, id: string) {
  return apiRequest<ChangeProposal>(page, `/api/proposals/${id}`);
}

/** The row of the pair whose element has this title. */
function pairRow(page: Page, title: string) {
  return page
    .getByTestId("compare-table")
    .getByRole("row")
    .filter({ has: page.getByRole("button", { name: title, exact: true }) });
}

test.describe("Compare page", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("decides the differences, checks the sample and accepts the rest", async ({ page }) => {
    const { a, b, node, actor } = await seedComparison(page);

    // 1. From proposal A's page, compare with the other pipeline.
    await page.goto(`/app/proposals/${a.id}`);
    await page.waitForLoadState("networkidle");
    await page.getByTestId("proposal-compare").click();
    await expect(page).toHaveURL(new RegExp(`/app/proposals/${a.id}/compare/${b.id}$`));
    await expect(page.getByTestId("compare-page")).toBeVisible();

    // 2. Header, origins and the four counts.
    const header = page.getByTestId("compare-header");
    await expect(header.getByRole("heading", { level: 1 })).toHaveText("Compare pipelines");
    await expect(header).toContainText("SOURCE E2E Compare Notes · TWO OPEN PROPOSALS");
    await expect(page.getByTestId("compare-origin-a-chip")).toContainText("single_call v1");
    await expect(page.getByTestId("compare-origin-b-chip")).toContainText("find_then_type v1");
    await expect(page.getByTestId("compare-origin-a")).toContainText("14 individuals");
    await expect(page.getByTestId("compare-count-same_class")).toContainText("12");
    await expect(page.getByTestId("compare-count-class_differs")).toContainText("1");
    await expect(page.getByTestId("compare-count-only_a")).toContainText("1");
    await expect(page.getByTestId("compare-count-only_b")).toContainText("1");

    // 3. The class differs: take B's class.
    const differs = pairRow(page, DIFFERS);
    await expect(differs).toHaveClass(/\bcompare-row--class_differs\b/);
    await differs.getByRole("button", { name: "B class" }).click();
    await expect(differs).toContainText("B class: E2E Compare Technology Node");
    await expect(differs).toHaveAttribute("data-state", "decided");
    let afterA = await proposalNow(page, a.id);
    let afterB = await proposalNow(page, b.id);
    expect(opTitled(afterB, DIFFERS).status).toBe("applied");
    expect(opTitled(afterB, DIFFERS).fields?.class_ids).toEqual([node.id]);
    expect(opTitled(afterA, DIFFERS).status).toBe("rejected");

    // 4. Only in B: keep it.
    const onlyB = pairRow(page, ONLY_B);
    await expect(onlyB).toHaveClass(/\bcompare-row--only_b\b/);
    await onlyB.getByRole("button", { name: "Keep" }).click();
    await expect(onlyB).toContainText("Kept as E2E Compare Actor");
    afterB = await proposalNow(page, b.id);
    expect(opTitled(afterB, ONLY_B).status).toBe("applied");
    expect(opTitled(afterB, ONLY_B).fields?.class_ids).toEqual([actor.id]);

    // 5. Accept the rest waits for the sample.
    const accept = page.getByTestId("compare-accept-rest");
    await expect(accept).toBeDisabled();
    await expect(page.getByTestId("compare-sample-progress")).toHaveText(
      "Sample: 0 / 10 checked · 0 changed",
    );
    await page.getByTestId("compare-check-sample").click();
    const sampleRows = page.getByTestId("compare-table").locator("tbody tr");
    await expect(sampleRows).toHaveCount(10);
    for (let n = 0; n < 10; n++) {
      const open = page.getByTestId("compare-table").locator("tbody tr[data-state='open']").first();
      await open.getByRole("button", { name: "Keep" }).click();
      await expect(page.getByTestId("compare-sample-progress")).toContainText(
        `${n + 1} / 10 checked`,
      );
    }
    await expect(page.getByTestId("compare-sample-progress")).toHaveText(
      "Sample: 10 / 10 checked · 0 changed",
    );

    // 6. Accept the rest: the two agreements outside the sample land.
    await expect(accept).toBeEnabled();
    await accept.click();
    await expect(page.getByTestId("compare-rest-result")).toHaveText("Accepted 2 agreements.");
    afterA = await proposalNow(page, a.id);
    afterB = await proposalNow(page, b.id);
    for (const title of AGREED) {
      expect(opTitled(afterA, title).status, `${title} landed from A`).toBe("applied");
      expect(opTitled(afterB, title).status, `${title} closed in B`).toBe("rejected");
    }
    // Only A's own element is left.
    expect(opTitled(afterA, ONLY_A).status).toBe("pending");
    await expect(accept).toBeDisabled();

    // 7. Finish: back to proposal A.
    await page.getByTestId("compare-finish").click();
    await expect(page).toHaveURL(new RegExp(`/app/proposals/${a.id}$`));
  });
});
