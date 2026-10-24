import type { Locator, Page, Request, Response } from "@playwright/test";
import { test, expect } from "../../fixtures/app-test";
import { apiRequest } from "../../fixtures/api-client";
import {
  clearTestData,
  createClass,
  createIndividual,
  createPropertyDefinition,
  createTaxonomy,
  type ConceptScheme,
  type Individual,
  type OntologyClass,
  type PropertyDefinition,
  type Relationship,
  type Taxonomy,
} from "../../fixtures/factories";
import {
  routeRunToFailure,
  routeRunsToSeededOutput,
  spanIn,
  type ExtractionPipelineType,
} from "../../fixtures/pipeline-runs";

/**
 * Extraction review (/app/pipelines/review): paste → run → review → apply → revert.
 * Plan: e2e/documentation/specs/extraction-review.md (GitHub #1233).
 *
 * No live LLM call is ever made: every test that clicks Run first installs
 * routeRunsToSeededOutput / routeRunToFailure, which answer the run POSTs with
 * seeded COMPLETED (or failed) runs. Candidates, recognition preview, apply,
 * revert and change events all hit the real isolated backend.
 *
 * Provenance shapes differ by pipeline: schema candidates carry a LIST of spans,
 * individual-extraction triples carry a SINGLE {quote,start,end} object
 * (spanIn(...), not [spanIn(...)] — a list 500s apply, defect D3).
 *
 * The two revert tests assert the correct behaviour and are expected to fail
 * until backend defects D1 (schema apply records no change events, so revert is
 * a no-op) and D2 (individual revert leaves apply-created relationships) are
 * fixed. Defect-specific checks use expect.soft so a run reports every symptom.
 */

const TEXT =
  "The Order Service exposes the Checkout API, which the Storefront Web App calls to place orders. The Order Service publishes order events to the Billing Engine.";

const TAXONOMY_LABEL = "Documentation Robotics · dr_spec";
const SCHEME_LABEL = "Application Layer · application";
const RUN_TIMEOUT = 30_000; // seeding a run shells out to Python
const RECOGNITION_TIMEOUT = 30_000; // the first preview loads the embedding model

const SCHEMA_TAB = /Schema extraction/;
const INDIVIDUAL_TAB = /Individual extraction/;

interface ListPage<T> {
  items: T[];
}

interface ChangeEvent {
  entity_id: string;
  entity_type: string;
  operation: string;
}

interface DrSeed {
  decoy: Taxonomy;
  tax: Taxonomy;
  scheme: ConceptScheme;
  componentClass: OntologyClass;
  serviceClass: OntologyClass;
  interfaceClass: OntologyClass;
  exposes: PropertyDefinition;
  orderService: Individual;
  storefront: Individual;
}

/** Seed the DR scope. The decoy is created first so taxonomies[0] is not dr_spec. */
async function seedDrScope(page: Page): Promise<DrSeed> {
  const decoy = await createTaxonomy(page, { title: "Acme Glossary" });
  // The factories do not pass `identifier`, which the dr_spec auto-pick keys on.
  const tax = await apiRequest<Taxonomy>(page, "/api/taxonomies", {
    method: "POST",
    body: {
      title: "Documentation Robotics",
      identifier: "dr_spec",
      description: "DR spec ontology",
    },
  });
  const scheme = await apiRequest<ConceptScheme>(page, `/api/taxonomies/${tax.id}/schemes`, {
    method: "POST",
    body: {
      title: "Application Layer",
      identifier: "application",
      description: "DR application layer",
    },
  });
  const componentClass = await createClass(page, scheme.id, { title: "Application Component" });
  const serviceClass = await createClass(page, scheme.id, { title: "Application Service" });
  // No individuals: keeps recognition for new mentions deterministic (no LLM tiebreak).
  const interfaceClass = await createClass(page, scheme.id, { title: "Application Interface" });
  const exposes = await createPropertyDefinition(page, { identifier: "exposes", title: "exposes" });
  const orderService = await createIndividual(page, {
    title: "Order Service",
    class_ids: [serviceClass.id],
  });
  const storefront = await createIndividual(page, {
    title: "Storefront Web App",
    class_ids: [componentClass.id],
  });
  return {
    decoy,
    tax,
    scheme,
    componentClass,
    serviceClass,
    interfaceClass,
    exposes,
    orderService,
    storefront,
  };
}

/** Schema output summary. Candidate provenance is a LIST of spans. */
function schemaOutput(): Record<string, unknown> {
  return {
    candidates: [
      {
        kind: "class",
        label: "Application Interface",
        confidence: 0.9,
        proposed_definition: "An access point where application services are made available.",
        provenance: [spanIn(TEXT, "Checkout API")],
      }, // class-0 (exists → reused)
      {
        kind: "class",
        label: "Event Stream",
        confidence: 0.82,
        proposed_definition: "An ordered channel of published domain events.",
        provenance: [spanIn(TEXT, "order events")],
      }, // class-1
      {
        kind: "class",
        label: "Billing System",
        confidence: 0.41,
        proposed_definition: null,
        provenance: [spanIn(TEXT, "Billing Engine")],
      }, // class-2
      {
        kind: "property_definition",
        label: "publishes",
        confidence: 0.86,
        proposed_definition: "The subject emits events onto the object.",
        proposed_domain: "Application Service",
        proposed_range: "Event Stream",
        provenance: [spanIn(TEXT, "publishes")],
      }, // property-0
    ],
    connections: [
      {
        subject_ref: "Application Service",
        predicate: "publishes",
        object_ref: "Event Stream",
        confidence: 0.8,
        provenance: [spanIn(TEXT, "Order Service publishes order events")],
      }, // connection-0
      {
        subject_ref: "Billing System",
        predicate: "publishes",
        object_ref: "Event Stream",
        confidence: 0.52,
        provenance: [spanIn(TEXT, "to the Billing Engine")],
      }, // connection-1
    ],
  };
}

/**
 * Individual output summary. Triple provenance is a SINGLE span object, as the
 * production pipelines store it. Order matters: triple-0 mints "Checkout API"
 * so triple-1 can resolve it as its object.
 */
function individualOutput(seed: DrSeed): Record<string, unknown> {
  const { interfaceClass, serviceClass, componentClass, exposes } = seed;
  const checkoutApi = {
    kind: "individual",
    id: "",
    label: "Checkout API",
    class_ids: [interfaceClass.id],
  };
  return {
    triples: [
      {
        subject: checkoutApi,
        predicate: { property_definition_id: null, label: "is_a" },
        object: { kind: "class", id: interfaceClass.id, label: "Application Interface" },
        confidence: 0.9,
        provenance: spanIn(TEXT, "Checkout API"),
      }, // triple-0
      {
        subject: {
          kind: "individual",
          id: "",
          label: "Order Service",
          class_ids: [serviceClass.id],
        },
        predicate: { property_definition_id: exposes.id, label: "exposes" },
        object: checkoutApi,
        confidence: 0.92,
        provenance: spanIn(TEXT, "Order Service exposes the Checkout API"),
      }, // triple-1
      {
        subject: {
          kind: "individual",
          id: "",
          label: "Storefront Web App",
          class_ids: [componentClass.id],
        },
        predicate: { property_definition_id: null, label: "calls" },
        object: checkoutApi,
        confidence: 0.85,
        provenance: spanIn(TEXT, "the Storefront Web App calls"),
      }, // triple-2
      {
        subject: {
          kind: "individual",
          id: "",
          label: "Billing Engine",
          class_ids: [componentClass.id],
        },
        predicate: { property_definition_id: null, label: "receives" },
        object: { kind: "literal", id: "", label: "order events" },
        confidence: 0.6,
        provenance: spanIn(TEXT, "order events to the Billing Engine"),
      }, // triple-3
    ],
  };
}

/** Count run POSTs per pipeline type (route-intercepted requests still emit "request"). */
function countRunPosts(page: Page): Record<ExtractionPipelineType, number> {
  const counts: Record<ExtractionPipelineType, number> = {
    schema_extraction: 0,
    individual_extraction: 0,
  };
  page.on("request", (req) => {
    if (req.method() !== "POST") return;
    for (const type of Object.keys(counts) as ExtractionPipelineType[]) {
      if (req.url().includes(`/api/pipelines/${type}/run`)) counts[type]++;
    }
  });
  return counts;
}

function tab(page: Page, name: RegExp): Locator {
  return page.getByTestId("extraction-review-tabs").getByRole("tab", { name });
}

/** The confirm-dialog button, scoped to the dialog (the apply bar button has the same label). */
function confirmButton(page: Page, kind: "schema" | "individual", label: string): Locator {
  return page
    .getByRole("dialog")
    .filter({ has: page.getByTestId(`extraction-review-${kind}-confirm`) })
    .getByRole("button", { name: label });
}

/** Toast by its fixed title copy. */
function toast(page: Page, title: string): Locator {
  return page.locator("[data-testid^=toast-content-]").filter({ hasText: title });
}

/** A highlighted source segment (extraction-review-span) by its exact covering keys. */
function span(source: Locator, keys: string): Locator {
  return source.locator(`[data-span-keys="${keys}"]`);
}

/** Start waiting for a run's apply/revert POST and its response (call before the click). */
function waitForRunCall(
  page: Page,
  runId: string,
  action: "apply" | "revert",
): [Promise<Request>, Promise<Response>] {
  const matches = (method: string, url: string) =>
    method === "POST" && url.includes(`/api/pipelines/runs/${runId}/${action}`);
  return [
    page.waitForRequest((r) => matches(r.method(), r.url())),
    page.waitForResponse((r) => matches(r.request().method(), r.url())),
  ];
}

async function openReview(page: Page): Promise<void> {
  await page.goto("/app/pipelines/review");
  await page.waitForLoadState("networkidle");
  await expect(page.getByTestId("extraction-review-page")).toBeVisible();
  await expect(page.getByTestId("extraction-review-taxonomy")).toContainText(TAXONOMY_LABEL);
  await expect(page.getByTestId("extraction-review-scheme")).toContainText(SCHEME_LABEL);
  await expect(page.getByTestId("extraction-review-config-refs")).toBeVisible();
}

async function runExtraction(page: Page): Promise<void> {
  await page.getByTestId("extraction-review-text").fill(TEXT);
  await page.getByTestId("extraction-review-run").click();
  await expect(page.getByTestId("extraction-review-schema-run-meta")).toContainText("COMPLETED", {
    timeout: RUN_TIMEOUT,
  });
  await expect(page.getByTestId("extraction-review-individual-run-meta")).toContainText(
    "COMPLETED",
    { timeout: RUN_TIMEOUT },
  );
}

async function classesInScheme(page: Page, schemeId: string): Promise<OntologyClass[]> {
  const res = await apiRequest<ListPage<OntologyClass>>(
    page,
    `/api/classes?concept_scheme_id=${schemeId}&limit=1000`,
  );
  return res.items;
}

async function classTitles(page: Page, schemeId: string): Promise<string[]> {
  return (await classesInScheme(page, schemeId)).map((c) => c.title).sort();
}

async function propertiesWithIdentifier(
  page: Page,
  identifier: string,
): Promise<PropertyDefinition[]> {
  const res = await apiRequest<ListPage<PropertyDefinition>>(page, "/api/properties?limit=1000");
  return res.items.filter((p) => p.identifier === identifier);
}

async function relationships(
  page: Page,
  sourceId: string,
  propertyId: string,
): Promise<Relationship[]> {
  const res = await apiRequest<ListPage<Relationship>>(
    page,
    `/api/relationships?source_id=${sourceId}&property_id=${propertyId}`,
  );
  return res.items;
}

async function individualsOfClass(page: Page, classId: string): Promise<Individual[]> {
  const res = await apiRequest<ListPage<Individual>>(page, `/api/individuals?class_id=${classId}`);
  return res.items;
}

async function changeEvents(page: Page, runId: string): Promise<ChangeEvent[]> {
  const res = await apiRequest<ListPage<ChangeEvent>>(
    page,
    `/api/pipelines/runs/${runId}/change-events`,
  );
  return res.items;
}

/** Click an accept/reject (merge/keep-separate) button and assert it is pressed. */
async function decide(page: Page, testId: string): Promise<void> {
  const button = page.getByTestId(testId);
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");
}

/** Switch the schema candidate-kind filter. */
async function schemaKind(page: Page, name: RegExp): Promise<void> {
  const radio = page
    .getByTestId("extraction-review-schema-candidates")
    .getByRole("radio", { name });
  await radio.click();
  await expect(radio).toBeChecked();
}

/** Wait for the recognition preview: the merge controls for hit-1 / hit-2 render. */
async function waitForRecognition(page: Page): Promise<void> {
  await expect(page.getByTestId("extraction-review-recognition-decision-hit-1")).toBeVisible({
    timeout: RECOGNITION_TIMEOUT,
  });
  await expect(page.getByTestId("extraction-review-recognition-decision-hit-2")).toBeVisible();
}

test.describe("Extraction review", () => {
  test.describe.configure({ timeout: 120_000 });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("auto-picks dr_spec, validates the paragraph and warns when it goes stale", async ({
    page,
  }) => {
    const seed = await seedDrScope(page);
    await routeRunsToSeededOutput(page, {
      schema_extraction: schemaOutput(),
      individual_extraction: individualOutput(seed),
    });
    const posts = countRunPosts(page);

    await openReview(page);
    await expect(page.getByTestId("extraction-review-config-refs")).toContainText(
      "schema-extraction-default",
    );

    // Both tabs idle.
    await expect(page.getByTestId("extraction-review-schema-idle")).toBeVisible();
    await tab(page, INDIVIDUAL_TAB).click();
    await expect(page.getByTestId("extraction-review-individual-idle")).toBeVisible();
    await tab(page, SCHEMA_TAB).click();

    // An empty paragraph blocks the run: no POST.
    const textArea = page.getByTestId("extraction-review-text");
    const error = page.getByText("Paste a paragraph to extract from", { exact: true });
    await page.getByTestId("extraction-review-run").click();
    await expect(error).toBeVisible();
    await expect(textArea).toHaveAttribute("aria-invalid", "true");
    expect(posts).toEqual({ schema_extraction: 0, individual_extraction: 0 });
    await expect(page.getByTestId("extraction-review-schema-idle")).toBeVisible();

    // The error clears on change, without a blur.
    await textArea.pressSequentially("T");
    await expect(error).toHaveCount(0);
    await expect(textArea).toHaveAttribute("aria-invalid", "false");

    // Emptied after an attempted run: the error returns on blur.
    await textArea.fill("");
    await textArea.blur();
    await expect(error).toBeVisible();

    await textArea.fill(TEXT);
    await expect(error).toHaveCount(0);
    await page.getByTestId("extraction-review-run").click();

    await expect(page.getByTestId("extraction-review-schema-run-meta")).toContainText("COMPLETED", {
      timeout: RUN_TIMEOUT,
    });
    await expect(page.getByTestId("extraction-review-schema-candidates")).toBeVisible();
    await expect(tab(page, SCHEMA_TAB)).toContainText("6");
    await expect(tab(page, INDIVIDUAL_TAB)).toContainText("4", { timeout: RUN_TIMEOUT });
    expect(posts).toEqual({ schema_extraction: 1, individual_extraction: 1 });

    // Stale-paragraph warning; highlights keep showing the text that was run.
    const stale = page.getByTestId("extraction-review-stale");
    await expect(stale).toHaveCount(0);
    await textArea.fill(TEXT + " It is owned by the Payments Team.");
    await expect(stale).toBeVisible();
    await expect(page.getByTestId("extraction-review-schema-source")).toHaveText(TEXT);
    await textArea.fill(TEXT);
    await expect(stale).toHaveCount(0);
  });

  test("schema tab: review, span to inspector, confirm with orphan warning, apply and persist", async ({
    page,
  }) => {
    const seed = await seedDrScope(page);
    const intercepted = await routeRunsToSeededOutput(page, {
      schema_extraction: schemaOutput(),
      individual_extraction: individualOutput(seed),
    });
    await openReview(page);
    await runExtraction(page);

    const schemaRun = intercepted.schema_extraction!;
    const runId = schemaRun.run.id;
    await expect(page.getByTestId("extraction-review-schema-run-meta")).toContainText(runId);
    expect(schemaRun.request.documents).toEqual([TEXT]);
    expect(schemaRun.request.scope).toBe(seed.tax.id);
    expect(schemaRun.request.concept_scheme_id).toBe(seed.scheme.id);
    expect(schemaRun.request.implementation_id).toBe("default");

    // Nothing written yet.
    expect(await classTitles(page, seed.scheme.id)).toEqual([
      "Application Component",
      "Application Interface",
      "Application Service",
    ]);

    // The Classes filter is active by default.
    await expect(page.getByTestId("extraction-review-schema-decision-class-0")).toBeVisible();
    await expect(page.getByTestId("extraction-review-schema-decision-class-1")).toBeVisible();
    await expect(page.getByTestId("extraction-review-schema-decision-class-2")).toBeVisible();
    await expect(page.getByTestId("extraction-review-schema-decision-property-0")).toHaveCount(0);

    await decide(page, "extraction-review-schema-decision-class-0-yes");
    await decide(page, "extraction-review-schema-decision-class-1-yes");
    await decide(page, "extraction-review-schema-decision-class-2-no");

    // Span → inspector. The overlapping segment cycles property-0 → connection-0.
    const candidates = page.getByTestId("extraction-review-schema-candidates");
    const inspector = page.getByTestId("extraction-review-schema-inspector");
    const publishesSpan = span(
      page.getByTestId("extraction-review-schema-source"),
      "property-0 connection-0",
    );
    const publishesAt = spanIn(TEXT, "publishes");
    await publishesSpan.click();
    await expect(candidates.getByRole("radio", { name: /Properties/ })).toBeChecked();
    await expect(inspector).toContainText("SCHEMA PROPERTY CANDIDATE");
    await expect(inspector).toContainText("publishes");
    await expect(inspector.getByTestId("extraction-review-provenance")).toContainText(
      `${publishesAt.start}–${publishesAt.end}`,
    );
    await expect(publishesSpan).toHaveAttribute("aria-current", "true");

    await page.getByTestId("extraction-review-schema-inspector-decision-yes").click();
    await expect(
      page.getByTestId("extraction-review-schema-decision-property-0-yes"),
    ).toHaveAttribute("aria-pressed", "true");

    await publishesSpan.click();
    await expect(candidates.getByRole("radio", { name: /Connections/ })).toBeChecked();
    await expect(inspector).toContainText("SCHEMA CONNECTION CANDIDATE");
    await expect(inspector).toContainText("Application Service → publishes → Event Stream");

    await decide(page, "extraction-review-schema-decision-connection-0-yes");
    await decide(page, "extraction-review-schema-decision-connection-1-yes");

    const applyBar = page.getByTestId("extraction-review-schema-apply-bar");
    for (const expected of [
      "5 accepted",
      "1 rejected",
      "0 pending",
      TAXONOMY_LABEL,
      SCHEME_LABEL,
    ]) {
      await expect(applyBar).toContainText(expected);
    }
    const apply = page.getByTestId("extraction-review-schema-apply");
    await expect(apply).toBeEnabled();
    await expect(apply).toContainText("Apply 5 accepted");

    // Confirm dialog predicts the orphaned connection.
    await apply.click();
    await expect(page.getByTestId("extraction-review-schema-confirm")).toBeVisible();
    const orphan = page.getByTestId("extraction-review-schema-orphan-warning");
    await expect(orphan).toContainText(
      "1 accepted connection points at a proposed class you did not accept",
    );
    await expect(orphan).toContainText("Billing System → publishes → Event Stream");

    const [applyRequest, applyResponse] = waitForRunCall(page, runId, "apply");
    await confirmButton(page, "schema", "Apply 5 accepted").click();
    const request = await applyRequest;
    const response = await applyResponse;

    const query = new URL(request.url()).searchParams;
    expect(query.get("taxonomy_id")).toBe(seed.tax.id);
    expect(query.get("concept_scheme_id")).toBe(seed.scheme.id);
    expect(query.has("confidence_threshold")).toBe(false);
    const body = request.postDataJSON() as Record<string, unknown>;
    expect([...(body.accepted_candidate_ids as string[])].sort()).toEqual([
      "class-0",
      "class-1",
      "connection-0",
      "connection-1",
      "property-0",
    ]);
    expect(body).not.toHaveProperty("recognition_decisions");

    expect(response.status()).toBe(200);
    expect(await response.json()).toMatchObject({
      classes_created: 1,
      classes_skipped: 2,
      properties_created: 1,
      relationships_created: 1,
      applied_candidate_ids: ["class-0", "class-1", "property-0", "connection-0"],
      skipped_candidate_ids: ["class-2", "connection-1"],
    });

    // Result panel: only accepted-but-skipped candidates are listed as skipped.
    const schemaRoot = page.getByTestId("extraction-review-schema");
    const created = schemaRoot.getByTestId("extraction-review-apply-result-created");
    for (const expected of [
      "4 of 5 accepted applied",
      "1 classes created",
      "1 properties created",
      "1 relationships created",
    ]) {
      await expect(created).toContainText(expected);
    }
    const skipped = schemaRoot.getByTestId("extraction-review-apply-result-skipped");
    await expect(skipped).toContainText("Billing System → publishes → Event Stream");
    await expect(skipped.getByText("Billing System", { exact: true })).toHaveCount(0);
    await expect(page.getByTestId("extraction-review-schema-revert")).toBeVisible();
    await expect(page.getByTestId("extraction-review-schema-apply")).toHaveCount(0);
    await expect(toast(page, "Schema candidates applied")).toContainText(
      "4 applied · 1 accepted skipped",
    );

    // Persistence: the existing class is reused, the rejected one never written.
    expect(await classTitles(page, seed.scheme.id)).toEqual([
      "Application Component",
      "Application Interface",
      "Application Service",
      "Event Stream",
    ]);
    const publishes = await propertiesWithIdentifier(page, "publishes");
    expect(publishes).toHaveLength(1);
    const eventStream = (await classesInScheme(page, seed.scheme.id)).find(
      (c) => c.title === "Event Stream",
    );
    expect(eventStream).toBeDefined();
    const rels = await relationships(page, seed.serviceClass.id, publishes[0].id);
    expect(rels).toHaveLength(1);
    expect(rels[0].target_id).toBe(eventStream!.id);
  });

  // Expected to FAIL until backend defect D1 is fixed: schema apply records no
  // change events, so revert reverts nothing.
  test("schema tab: revert removes what the run created", async ({ page }) => {
    const seed = await seedDrScope(page);
    const intercepted = await routeRunsToSeededOutput(page, {
      schema_extraction: schemaOutput(),
      individual_extraction: individualOutput(seed),
    });
    await openReview(page);
    await runExtraction(page);
    const runId = intercepted.schema_extraction!.run.id;

    await decide(page, "extraction-review-schema-decision-class-1-yes");
    await schemaKind(page, /Properties/);
    await decide(page, "extraction-review-schema-decision-property-0-yes");
    await schemaKind(page, /Connections/);
    await decide(page, "extraction-review-schema-decision-connection-0-yes");

    await page.getByTestId("extraction-review-schema-apply").click();
    await expect(page.getByTestId("extraction-review-schema-confirm")).toBeVisible();
    const [, applyResponse] = waitForRunCall(page, runId, "apply");
    await confirmButton(page, "schema", "Apply 3 accepted").click();
    expect((await applyResponse).status()).toBe(200);
    await expect(page.getByTestId("extraction-review-schema-revert")).toBeVisible();

    const eventStream = (await classesInScheme(page, seed.scheme.id)).find(
      (c) => c.title === "Event Stream",
    );
    expect(eventStream).toBeDefined();
    const publishes = await propertiesWithIdentifier(page, "publishes");
    expect(publishes).toHaveLength(1);
    const publishesId = publishes[0].id;

    // D1: the run's class, property definition and relationship creates are recorded.
    expect.soft((await changeEvents(page, runId)).length).toBeGreaterThanOrEqual(3);

    const [, revertResponse] = waitForRunCall(page, runId, "revert");
    await page.getByTestId("extraction-review-schema-revert").click();
    const revert = await (await revertResponse).json();
    expect.soft(revert).toMatchObject({
      classes_deleted: 1,
      properties_deleted: 1,
      relationships_deleted: 1,
    });
    expect.soft(revert.events_reverted).toBeGreaterThanOrEqual(3);

    // UI.
    await expect(toast(page, "Run reverted")).toBeVisible();
    const apply = page.getByTestId("extraction-review-schema-apply");
    await expect(apply).toBeVisible();
    await expect(apply).toContainText("Apply 3 accepted");
    await expect(
      page
        .getByTestId("extraction-review-schema")
        .getByTestId("extraction-review-apply-result-created"),
    ).toHaveCount(0);

    // API: the run's entities are gone, seeded data is intact.
    expect(await classTitles(page, seed.scheme.id)).toEqual([
      "Application Component",
      "Application Interface",
      "Application Service",
    ]);
    expect(await propertiesWithIdentifier(page, "publishes")).toHaveLength(0);
    expect(await relationships(page, seed.serviceClass.id, publishesId)).toHaveLength(0);
    expect(await propertiesWithIdentifier(page, "exposes")).toHaveLength(1);
  });

  test("individual tab: triples, recognition merge and keep separate, span to inspector, apply and persist", async ({
    page,
  }) => {
    const seed = await seedDrScope(page);
    const intercepted = await routeRunsToSeededOutput(page, {
      schema_extraction: schemaOutput(),
      individual_extraction: individualOutput(seed),
    });
    await openReview(page);
    await runExtraction(page);
    await tab(page, INDIVIDUAL_TAB).click();

    const individualRun = intercepted.individual_extraction!;
    const runId = individualRun.run.id;
    await expect(page.getByTestId("extraction-review-individual-run-meta")).toContainText(runId);
    expect(individualRun.request.text).toBe(TEXT);
    expect(individualRun.request.ontology_id).toBe(seed.tax.id);
    expect(individualRun.request.ontology_name).toBe("Documentation Robotics");

    await expect(page.getByTestId("extraction-review-individual-decision-triple-0")).toBeVisible();
    await expect(page.getByTestId("extraction-review-individual-decision-triple-1")).toBeVisible();
    await expect(page.getByTestId("extraction-review-individual-decision-triple-2")).toBeVisible();
    await expect(page.getByTestId("extraction-review-individual-decision-triple-3")).toBeVisible();
    await waitForRecognition(page);
    await expect(page.getByTestId("extraction-review-recognition-decision-hit-0")).toHaveCount(0);
    await expect(page.getByTestId("extraction-review-recognition-decision-hit-3")).toHaveCount(0);
    await expect(page.getByTestId("extraction-review-recognition")).toContainText(
      "no match · created as new",
    );

    // Span → inspector.
    const source = page.getByTestId("extraction-review-individual-source");
    const inspector = page.getByTestId("extraction-review-individual-inspector");
    await span(source, "triple-2").first().click();
    await expect(inspector).toContainText("TRIPLE CANDIDATE");
    await expect(inspector).toContainText("Storefront Web App → calls → Checkout API");

    // The overlapping segment cycles triple-1 → hit-1.
    const orderSpan = span(source, "triple-1 hit-1");
    await orderSpan.click();
    await expect(inspector).toContainText("Order Service → exposes → Checkout API");
    await orderSpan.click();
    const recognitionInspector = page.getByTestId("extraction-review-recognition-inspector");
    await expect(recognitionInspector).toBeVisible();
    for (const expected of ["Order Service", "existing individual", "exact", "100%"]) {
      await expect(recognitionInspector).toContainText(expected);
    }
    await expect(inspector).toHaveCount(0);

    // Decisions: accept three triples, reject one; merge hit-1, keep hit-2 separate.
    await decide(page, "extraction-review-individual-decision-triple-0-yes");
    await decide(page, "extraction-review-individual-decision-triple-1-yes");
    await decide(page, "extraction-review-individual-decision-triple-2-yes");
    await decide(page, "extraction-review-individual-decision-triple-3-no");
    await decide(page, "extraction-review-recognition-decision-hit-1-yes");
    await decide(page, "extraction-review-recognition-decision-hit-2-no");

    const applyBar = page.getByTestId("extraction-review-individual-apply-bar");
    for (const expected of [
      "3 accepted",
      "1 rejected",
      "0 pending",
      "1 merge",
      "1 keep separate",
      "threshold 0.90",
    ]) {
      await expect(applyBar).toContainText(expected);
    }

    // Nothing written yet.
    expect(await individualsOfClass(page, seed.interfaceClass.id)).toHaveLength(0);

    await page.getByTestId("extraction-review-individual-apply").click();
    const confirm = page.getByTestId("extraction-review-individual-confirm");
    for (const expected of ["3 accepted triples", "1 merge into existing", "1 kept separate"]) {
      await expect(confirm).toContainText(expected);
    }
    await expect(confirm).not.toContainText("left to recognition");

    const [applyRequest, applyResponse] = waitForRunCall(page, runId, "apply");
    await confirmButton(page, "individual", "Apply 3 accepted").click();
    const request = await applyRequest;
    const response = await applyResponse;

    const query = new URL(request.url()).searchParams;
    expect(query.get("taxonomy_id")).toBe(seed.tax.id);
    expect(query.get("recognition_threshold")).toBe("0.9");
    const body = request.postDataJSON() as Record<string, unknown>;
    expect([...(body.accepted_candidate_ids as string[])].sort()).toEqual([
      "triple-0",
      "triple-1",
      "triple-2",
    ]);
    expect(body.recognition_decisions).toEqual([
      { mention_label: "Order Service", decision: "merge", individual_id: seed.orderService.id },
      { mention_label: "Storefront Web App", decision: "separate" },
    ]);

    // "Keep separate" on an exact-title hit cannot mint a duplicate (titles are
    // unique per class): the server reports it as merged via existing_title.
    expect(response.status()).toBe(200);
    expect(await response.json()).toMatchObject({
      individuals_created: 1,
      relationships_created: 1,
      applied_candidate_ids: ["triple-0", "triple-1", "triple-2"],
      skipped_candidate_ids: ["triple-3"],
      merged_mentions: [
        { mention_label: "Order Service", individual_id: seed.orderService.id, source: "decision" },
        {
          mention_label: "Storefront Web App",
          individual_id: seed.storefront.id,
          source: "existing_title",
        },
      ],
    });

    // Result panel.
    const individualRoot = page.getByTestId("extraction-review-individual");
    const created = individualRoot.getByTestId("extraction-review-apply-result-created");
    for (const expected of [
      "3 of 3 accepted applied",
      "1 individuals created",
      "1 relationships created",
    ]) {
      await expect(created).toContainText(expected);
    }
    const merged = individualRoot.getByTestId("extraction-review-apply-result-merged");
    await expect(merged).toContainText("Order Service → Order Service");
    await expect(merged).toContainText("your merge");
    await expect(merged).toContainText("Storefront Web App → Storefront Web App");
    await expect(merged).toContainText("same title");
    await expect(individualRoot.getByTestId("extraction-review-apply-result-skipped")).toHaveCount(
      0,
    );
    await expect(page.getByTestId("extraction-review-individual-revert")).toBeVisible();
    await expect(toast(page, "Individuals applied")).toContainText(
      "3 applied · 0 accepted skipped",
    );

    // Persistence.
    const interfaces = await individualsOfClass(page, seed.interfaceClass.id);
    expect(interfaces.map((i) => i.title)).toEqual(["Checkout API"]);
    const checkoutId = interfaces[0].id;

    const services = await individualsOfClass(page, seed.serviceClass.id);
    expect(services.map((i) => i.id)).toEqual([seed.orderService.id]);

    const components = await individualsOfClass(page, seed.componentClass.id);
    expect(components.map((i) => i.title)).toEqual(["Storefront Web App"]);

    const rels = await relationships(page, seed.orderService.id, seed.exposes.id);
    expect(rels.map((r) => r.target_id)).toEqual([checkoutId]);

    expect(await changeEvents(page, runId)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          entity_id: checkoutId,
          entity_type: "individual",
          operation: "create",
        }),
      ]),
    );
  });

  // Relationship part expected to FAIL until backend defect D2 is fixed:
  // individual revert leaves the apply-created relationship dangling.
  test("individual tab: revert removes the minted individual and its relationship", async ({
    page,
  }) => {
    const seed = await seedDrScope(page);
    const intercepted = await routeRunsToSeededOutput(page, {
      schema_extraction: schemaOutput(),
      individual_extraction: individualOutput(seed),
    });
    await openReview(page);
    await runExtraction(page);
    await tab(page, INDIVIDUAL_TAB).click();
    const runId = intercepted.individual_extraction!.run.id;
    await waitForRecognition(page);

    // Accept triple-0 and triple-1, merge hit-1, leave hit-2 undecided.
    await decide(page, "extraction-review-individual-decision-triple-0-yes");
    await decide(page, "extraction-review-individual-decision-triple-1-yes");
    await decide(page, "extraction-review-recognition-decision-hit-1-yes");

    await page.getByTestId("extraction-review-individual-apply").click();
    await expect(page.getByTestId("extraction-review-individual-confirm")).toContainText(
      "1 left to recognition",
    );
    const [applyRequest, applyResponse] = waitForRunCall(page, runId, "apply");
    await confirmButton(page, "individual", "Apply 2 accepted").click();
    const body = (await applyRequest).postDataJSON() as Record<string, unknown>;
    expect(body.recognition_decisions).toEqual([
      { mention_label: "Order Service", decision: "merge", individual_id: seed.orderService.id },
    ]);
    const applied = await applyResponse;
    expect(applied.status()).toBe(200);
    expect(await applied.json()).toMatchObject({
      individuals_created: 1,
      relationships_created: 1,
    });
    await expect(page.getByTestId("extraction-review-individual-revert")).toBeVisible();

    const interfaces = await individualsOfClass(page, seed.interfaceClass.id);
    expect(interfaces).toHaveLength(1);
    const checkoutId = interfaces[0].id;
    const createdRels = await relationships(page, seed.orderService.id, seed.exposes.id);
    expect(createdRels.map((r) => r.target_id)).toEqual([checkoutId]);

    const [, revertResponse] = waitForRunCall(page, runId, "revert");
    await page.getByTestId("extraction-review-individual-revert").click();
    const revert = await (await revertResponse).json();
    expect(revert.individuals_deleted).toBe(1);
    // D2: the relationship minted by apply is reverted too.
    expect.soft(revert.relationships_deleted).toBe(1);

    // UI.
    await expect(toast(page, "Run reverted")).toBeVisible();
    const apply = page.getByTestId("extraction-review-individual-apply");
    await expect(apply).toBeVisible();
    await expect(apply).toContainText("Apply 2 accepted");
    await expect(
      page
        .getByTestId("extraction-review-individual")
        .getByTestId("extraction-review-apply-result-created"),
    ).toHaveCount(0);

    // API: minted individual gone, merge target untouched, no dangling relationship.
    expect(await individualsOfClass(page, seed.interfaceClass.id)).toHaveLength(0);
    const target = await apiRequest<Individual>(page, `/api/individuals/${seed.orderService.id}`);
    expect(target.id).toBe(seed.orderService.id);
    expect(target.title).toBe("Order Service");
    // D2: fails today, a relationship to the deleted checkoutId survives.
    expect(await relationships(page, seed.orderService.id, seed.exposes.id)).toHaveLength(0);
  });

  test("one tab fails while the other completes; retry re-runs only the failed tab", async ({
    page,
  }) => {
    const seed = await seedDrScope(page);
    await routeRunToFailure(page, "schema_extraction", "LLM provider timed out");
    const ind = await routeRunsToSeededOutput(page, {
      individual_extraction: individualOutput(seed),
    });
    const posts = countRunPosts(page);
    await openReview(page);

    await page.getByTestId("extraction-review-text").fill(TEXT);
    await page.getByTestId("extraction-review-run").click();

    const failed = page.getByTestId("extraction-review-schema-failed");
    await expect(failed).toBeVisible({ timeout: RUN_TIMEOUT });
    await expect(failed).toContainText(
      "Run failed: LLM provider timed out. The other extraction tab is unaffected.",
    );
    await expect(page.getByTestId("extraction-review-schema-run-meta")).toContainText("FAILED");
    await expect(page.getByTestId("extraction-review-schema-retry")).toBeVisible();
    await expect(page.getByTestId("extraction-review-schema-apply-bar")).toHaveCount(0);

    await tab(page, INDIVIDUAL_TAB).click();
    const individualMeta = page.getByTestId("extraction-review-individual-run-meta");
    await expect(individualMeta).toContainText("COMPLETED", { timeout: RUN_TIMEOUT });
    const individualRunId = ind.individual_extraction!.run.id;
    await expect(individualMeta).toContainText(individualRunId);
    await decide(page, "extraction-review-individual-decision-triple-0-yes");

    // Swap the failing route for a seeded one, then retry the schema tab only.
    await page.unroute("**/api/pipelines/schema_extraction/run");
    const schema = await routeRunsToSeededOutput(page, { schema_extraction: schemaOutput() });

    await tab(page, SCHEMA_TAB).click();
    await page.getByTestId("extraction-review-schema-retry").click();

    const schemaMeta = page.getByTestId("extraction-review-schema-run-meta");
    await expect(schemaMeta).toContainText("COMPLETED", { timeout: RUN_TIMEOUT });
    await expect(schemaMeta).toContainText(schema.schema_extraction!.run.id);
    await expect(page.getByTestId("extraction-review-schema-decision-class-0")).toBeVisible();
    await expect(failed).toHaveCount(0);
    const retried = schema.schema_extraction!.request;
    expect(retried.documents).toEqual([TEXT]);
    expect(retried.scope).toBe(seed.tax.id);
    expect(retried.concept_scheme_id).toBe(seed.scheme.id);

    // The other tab's run and decisions survive.
    expect(posts).toEqual({ schema_extraction: 2, individual_extraction: 1 });
    await tab(page, INDIVIDUAL_TAB).click();
    await expect(individualMeta).toContainText(individualRunId);
    await expect(
      page.getByTestId("extraction-review-individual-decision-triple-0-yes"),
    ).toHaveAttribute("aria-pressed", "true");
  });
});
