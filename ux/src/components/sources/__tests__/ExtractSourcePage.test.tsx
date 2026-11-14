import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import type { ReactNode } from "react";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { createDataset, createTaxonomy } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { Source } from "@/api/services/sources";
import { ExtractSourcePage, type ExtractSourcePageProps } from "../ExtractSourcePage";
import { createConfiguration, createRun, createSource } from "./fixtures";
import type { components } from "@/api/types";

type PipelineRun = components["schemas"]["PipelineRunResponse"];
type PipelineConfiguration = components["schemas"]["PipelineConfigurationResponse"];

const { toastSpy } = vi.hoisted(() => ({ toastSpy: vi.fn() }));
vi.mock("@/components/ui/Toast", () => ({
  ToastProvider: ({ children }: { children: ReactNode }) => children,
  useToasts: () => ({ toast: toastSpy, toasts: [], dismiss: vi.fn() }),
}));

const house = createTaxonomy({ id: "tax-house", identifier: "house", title: "House" });
const home = createDataset({ id: "ds-home", taxonomy_id: "tax-house", identifier: "home" });
const cabin = createDataset({ id: "ds-cabin", taxonomy_id: "tax-house", identifier: "cabin" });
const defaultConfig = createConfiguration();
const openRouterConfig = createConfiguration({
  id: "cfg-3",
  config_ref: "extraction-openrouter-default",
  provider: "openrouter",
});
const disabledConfig = createConfiguration({
  id: "cfg-4",
  config_ref: "extraction-disabled",
  enabled: false,
});
// open_v1 can't extract a source: the extract endpoint refuses it.
const openConfig = createConfiguration({
  id: "cfg-2",
  config_ref: "extraction-open-v1",
  implementation_id: "open_v1",
  model: null,
});
// Listed before the configuration find_then_type extracts a source with.
const findThenTypeOtherConfig = createConfiguration({
  id: "cfg-5",
  config_ref: "find-then-type-other-model",
  implementation_id: "find_then_type",
  model: "claude-sonnet",
});
const findThenTypeConfig = createConfiguration({
  id: "cfg-6",
  config_ref: "extraction-find-then-type",
  implementation_id: "find_then_type",
  model: "claude-haiku",
});
const IMPLEMENTATIONS = [
  { id: "open_v1", pipeline_type: "individual_extraction", source_configuration: null },
  {
    id: "find_then_type",
    pipeline_type: "individual_extraction",
    source_configuration: "extraction-find-then-type",
  },
  {
    id: "default",
    pipeline_type: "individual_extraction",
    source_configuration: "extraction-default",
  },
];

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  toastSpy.mockClear();
});
afterAll(() => server.close());

interface ServeOptions {
  source?: Source;
  taxonomy?: ReturnType<typeof createTaxonomy>;
  configs?: PipelineConfiguration[];
  implementations?: typeof IMPLEMENTATIONS | (() => Response);
  runs?: Record<string, PipelineRun | (() => PipelineRun)>;
  extract?: () => Response;
}

function serve({
  source = createSource(),
  taxonomy = house,
  configs = [
    defaultConfig,
    openRouterConfig,
    disabledConfig,
    openConfig,
    findThenTypeOtherConfig,
    findThenTypeConfig,
  ],
  implementations = IMPLEMENTATIONS,
  runs = {},
  extract,
}: ServeOptions = {}) {
  const extractBodies: unknown[] = [];
  const cancelled: string[] = [];
  const runReads: string[] = [];
  const configRequests: string[] = [];
  server.use(
    http.get("*/api/sources/:id", () => HttpResponse.json(source)),
    http.get("*/api/taxonomies/:id", () => HttpResponse.json(taxonomy)),
    http.get("*/api/datasets", () => HttpResponse.json([home, cabin])),
    http.get("*/api/pipelines/types/individual_extraction/implementations", () =>
      typeof implementations === "function"
        ? implementations()
        : HttpResponse.json(implementations),
    ),
    http.get(
      "*/api/pipelines/types/individual_extraction/implementations/:impl/configurations",
      ({ params }) => {
        configRequests.push(params.impl as string);
        return HttpResponse.json(configs.filter((c) => c.implementation_id === params.impl));
      },
    ),
    http.post("*/api/sources/:id/extract", async ({ request }) => {
      extractBodies.push(await request.json());
      return (
        extract?.() ??
        HttpResponse.json(
          { runs: [{ run_id: "run-1234abcd", pipeline: "individual_extraction" }] },
          { status: 202 },
        )
      );
    }),
    http.get("*/api/pipelines/runs/:id", ({ params }) => {
      runReads.push(params.id as string);
      const run = runs[params.id as string];
      if (!run) return HttpResponse.json({ detail: "Run not found" }, { status: 404 });
      return HttpResponse.json(typeof run === "function" ? run() : run);
    }),
    http.post("*/api/pipelines/runs/:id/cancel", ({ params }) => {
      cancelled.push(params.id as string);
      return HttpResponse.json(createRun({ status: "running" }));
    }),
    http.get("*/api/proposals/:id", () =>
      HttpResponse.json(
        createChangeProposal({
          id: "prop-1",
          // Extracted into cabin, though the source belongs to home.
          dataset_id: "ds-cabin",
          operations: [
            createProposedOperation({ id: "a", op: "create", kind: "individual" }),
            createProposedOperation({
              id: "b",
              op: "create",
              kind: "individual",
              alternatives: [{ kind: "existing", entity_id: "i-9" }],
            }),
            createProposedOperation({ id: "c", op: "create", kind: "relationship" }),
          ],
        }),
      ),
    ),
  );
  return { extractBodies, cancelled, runReads, configRequests };
}

function renderPage(props: Partial<ExtractSourcePageProps> = {}) {
  const handlers = {
    onRunsStarted: vi.fn(),
    onReset: vi.fn(),
    onBack: vi.fn(),
    onReview: vi.fn(),
  };
  render(<ExtractSourcePage sourceId="src-1" {...handlers} {...props} />);
  return handlers;
}

describe("ExtractSourcePage — configure", () => {
  it("shows the source and an estimate without a cost when no price is known", async () => {
    const { configRequests } = serve();
    renderPage();

    expect(
      await screen.findByText("Whirlpool refrigerator: use and care guide"),
    ).toBeInTheDocument();
    const page = screen.getByTestId("extract-source-page");
    expect(page).toHaveTextContent("SOURCE · pdf · house");
    expect(page).toHaveTextContent("wrf555sdfz-use-care.pdf · 4 pages · 20k chars");

    const dataset = screen.getByTestId("extract-dataset");
    expect(dataset).toHaveAccessibleName("Dataset");
    expect(within(dataset).getByRole("radio", { name: "home" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    // The implementations that can extract a source, `default` chosen: open_v1 can't.
    const implementation = screen.getByTestId("extract-implementation");
    expect(implementation).toHaveAccessibleName("Individual extraction");
    await waitFor(() => expect(implementation).toHaveValue("default"));
    expect(
      within(implementation)
        .getAllByRole("option")
        .map((o) => o.getAttribute("value")),
    ).toEqual(["find_then_type", "default"]);
    const config = screen.getByTestId("extract-config");
    expect(config).toHaveAccessibleName("Configuration");
    await waitFor(() => expect(config).toHaveValue("extraction-default"));
    // Only the chosen implementation's enabled configurations.
    expect(
      within(config)
        .getAllByRole("option")
        .map((o) => o.getAttribute("value")),
    ).toEqual(["extraction-default", "extraction-openrouter-default"]);
    expect(within(config).queryByRole("option", { name: "extraction-open-v1" })).toBeNull();
    expect(configRequests).toEqual(["default"]);

    const estimate = screen.getByTestId("extract-estimate");
    expect(estimate).toHaveClass("form-callout--info");
    // 20k characters: 3 full chunks, or up to 5 broken early at headings and pages.
    expect(estimate).toHaveTextContent(
      "Rough estimate: about 3–5 chunks. One run, one proposal for dataset home.",
    );
    expect(estimate).not.toHaveTextContent("$");
    expect(screen.getByTestId("extract-chunk-count")).toHaveTextContent("about 3–5 chunks");
    expect(screen.getByTestId("extract-pages")).toHaveAttribute("placeholder", "e.g. 1-12, 15");
  });

  it("adds a rough cost when the configuration carries a price, doubled with schema", async () => {
    serve({
      configs: [
        createConfiguration({
          parameters: { price_per_mtok_in: 3, price_per_mtok_out: 15 } as never,
        }),
      ],
    });
    const user = userEvent.setup();
    renderPage();

    const estimate = await screen.findByTestId("extract-estimate");
    await waitFor(() =>
      expect(estimate).toHaveTextContent("Rough estimate: about 3–5 chunks, $0.06–$0.10."),
    );
    const schema = screen.getByTestId("extract-schema-toggle");
    expect(schema).toHaveAccessibleName(/Also suggest schema changes/);
    await waitFor(() => expect(schema).toBeEnabled());
    await user.click(schema);
    expect(estimate).toHaveTextContent("Two runs, two proposals");
    expect(estimate).toHaveTextContent("Rough estimate: about 3–5 chunks, $0.13–$0.20.");
  });

  it("narrows the estimate to a page range, and validates it on start", async () => {
    const { extractBodies } = serve();
    const user = userEvent.setup();
    renderPage();

    const pages = await screen.findByTestId("extract-pages");
    await user.type(pages, "1");
    expect(screen.getByTestId("extract-estimate")).toHaveTextContent("about 1–2 chunks.");
    expect(screen.getByTestId("extract-chunk-count")).toHaveTextContent("about 1–2 chunks");

    await user.type(pages, "-9");
    await user.click(screen.getByTestId("extract-start"));
    expect(screen.getByText("Pages run from 1 to 4.")).toBeInTheDocument();
    expect(pages).toHaveAttribute("aria-invalid", "true");
    expect(extractBodies).toHaveLength(0);

    await user.type(pages, "{Backspace}");
    expect(screen.queryByText("Pages run from 1 to 4.")).not.toBeInTheDocument();
  });

  it("starts the extraction with the chosen options and hands back its runs", async () => {
    const { extractBodies } = serve();
    const user = userEvent.setup();
    const { onRunsStarted } = renderPage();

    const config = await screen.findByTestId("extract-config");
    await waitFor(() => expect(within(config).getAllByRole("option")).toHaveLength(2));
    await user.selectOptions(config, "extraction-openrouter-default");
    await user.click(
      within(screen.getByTestId("extract-dataset")).getByRole("radio", { name: "cabin" }),
    );
    await user.type(screen.getByTestId("extract-pages"), "1-2");
    await waitFor(() => expect(screen.getByTestId("extract-schema-toggle")).toBeEnabled());
    await user.click(screen.getByTestId("extract-schema-toggle"));
    await user.click(screen.getByTestId("extract-start"));

    await waitFor(() => expect(onRunsStarted).toHaveBeenCalled());
    expect(extractBodies).toEqual([
      {
        dataset: "ds-cabin",
        implementation_id: "default",
        configuration_ref: "extraction-openrouter-default",
        pages: "1-2",
        schema: true,
        skip_boilerplate: true,
      },
    ]);
    expect(onRunsStarted).toHaveBeenCalledWith([
      { run_id: "run-1234abcd", pipeline: "individual_extraction" },
    ]);
  });

  it("extracts with another implementation and its own configuration", async () => {
    const { extractBodies, configRequests } = serve();
    const user = userEvent.setup();
    renderPage();

    const implementation = await screen.findByTestId("extract-implementation");
    const config = screen.getByTestId("extract-config");
    await waitFor(() => expect(config).toHaveValue("extraction-default"));
    await user.selectOptions(config, "extraction-openrouter-default");

    await user.selectOptions(implementation, "find_then_type");

    // The configuration chosen for the other implementation is dropped for this
    // one's own for sources, though it is not the first listed.
    expect(implementation).toHaveValue("find_then_type");
    await waitFor(() => expect(config).toHaveValue("extraction-find-then-type"));
    expect(
      within(config)
        .getAllByRole("option")
        .map((o) => o.getAttribute("value")),
    ).toEqual(["find-then-type-other-model", "extraction-find-then-type"]);
    expect(configRequests).toEqual(["default", "find_then_type"]);

    await user.click(screen.getByTestId("extract-start"));
    await waitFor(() => expect(extractBodies).toHaveLength(1));
    expect(extractBodies[0]).toEqual({
      dataset: "ds-home",
      implementation_id: "find_then_type",
      configuration_ref: "extraction-find-then-type",
      schema: false,
      skip_boilerplate: true,
    });
  });

  it("clears a start error when another implementation is chosen", async () => {
    serve({
      extract: () =>
        HttpResponse.json({ detail: "The provider refused the request." }, { status: 422 }),
    });
    const user = userEvent.setup();
    renderPage();

    const implementation = await screen.findByTestId("extract-implementation");
    await waitFor(() => expect(implementation).toHaveValue("default"));
    await user.click(screen.getByTestId("extract-start"));
    expect(await screen.findByTestId("extract-start-error")).toHaveTextContent(
      "The provider refused the request.",
    );

    await user.selectOptions(implementation, "find_then_type");
    expect(screen.queryByText("The provider refused the request.")).not.toBeInTheDocument();
  });

  it("leaves the implementation to the server when the list can't be read", async () => {
    const { extractBodies, configRequests } = serve({
      implementations: () => HttpResponse.json({ detail: "boom" }, { status: 500 }),
    });
    const user = userEvent.setup();
    renderPage();

    const implementation = await screen.findByTestId("extract-implementation");
    expect(within(implementation).queryAllByRole("option")).toHaveLength(0);
    await user.click(screen.getByTestId("extract-start"));

    await waitFor(() => expect(extractBodies).toHaveLength(1));
    expect(extractBodies[0]).toEqual({ dataset: "ds-home", schema: false, skip_boilerplate: true });
    expect(configRequests).toEqual([]);
  });

  it("skips boilerplate by default, and can read it too", async () => {
    const { extractBodies } = serve();
    const user = userEvent.setup();
    const { onRunsStarted } = renderPage();

    const toggle = await screen.findByTestId("extract-skip-boilerplate-toggle");
    expect(toggle).toHaveAttribute("type", "checkbox");
    expect(toggle).toHaveAccessibleName(/Skip boilerplate and other languages/);
    expect(toggle).toHaveAccessibleDescription(/warranty, safety, legal and contact sections/);
    expect(toggle).toBeChecked();

    await user.click(toggle);
    expect(toggle).not.toBeChecked();
    await user.click(screen.getByTestId("extract-start"));

    await waitFor(() => expect(onRunsStarted).toHaveBeenCalled());
    expect(extractBodies).toEqual([expect.objectContaining({ skip_boilerplate: false })]);
  });

  it.each([
    // An en dash and spaces normalize to the server's "digits, - and commas".
    ["3 – 4, 1", "1,3-4"],
    ["2,3,4", "2-4"],
  ])("sends the page range %s as %s", async (typed, sent) => {
    const { extractBodies } = serve();
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByTestId("extract-pages"), typed);
    await user.click(screen.getByTestId("extract-start"));
    await waitFor(() => expect(extractBodies).toHaveLength(1));
    expect(extractBodies[0]).toMatchObject({ pages: sent });
  });

  it("sends no page range when it covers every page", async () => {
    const { extractBodies } = serve();
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByTestId("extract-pages"), "1-4");
    await user.click(screen.getByTestId("extract-start"));
    await waitFor(() => expect(extractBodies).toHaveLength(1));
    expect(extractBodies[0]).not.toHaveProperty("pages");
  });

  it("says why the extraction could not start", async () => {
    serve({ extract: () => HttpResponse.json({ detail: "Not Found" }, { status: 404 }) });
    const user = userEvent.setup();
    const { onRunsStarted } = renderPage();

    await user.click(await screen.findByTestId("extract-start"));
    const error = await screen.findByTestId("extract-start-error");
    expect(error).toHaveClass("form-callout--error");
    expect(error).toHaveTextContent("Not Found");
    expect(onRunsStarted).not.toHaveBeenCalled();
  });

  it("does not offer extraction for a source that isn't ready", async () => {
    serve({ source: createSource({ status: "failed", failure: "no_text" }) });
    renderPage();
    expect(await screen.findByTestId("extract-not-ready")).toBeInTheDocument();
    expect(screen.queryByTestId("extract-start")).not.toBeInTheDocument();
  });
});

describe("ExtractSourcePage — progress and result", () => {
  it("shows progress by chunk and cancels the run", async () => {
    const { cancelled } = serve({
      runs: { "run-1234abcd": createRun({ items_done: 1, items_total: 3 }) },
    });
    const user = userEvent.setup();
    renderPage({ runId: "run-1234abcd" });

    const headline = await screen.findByTestId("extract-progress-headline");
    await waitFor(() => expect(headline).toHaveTextContent("Chunk 2 of 3"));
    const bar = screen.getByTestId("extract-progress-bar");
    expect(bar).toHaveAttribute("role", "progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "33");
    expect(bar).toHaveClass("progress-bar--amber");
    expect(screen.getByTestId("extract-run-tally")).toHaveTextContent(
      "run run-1234 · individual_extraction · extraction-default",
    );

    expect(within(screen.getByTestId("extract-chunk-1")).getByText("read")).toHaveClass(
      "chip--emerald",
    );
    expect(within(screen.getByTestId("extract-chunk-2")).getByText("reading")).toHaveClass(
      "chip--amber",
    );
    expect(within(screen.getByTestId("extract-chunk-3")).getByText("waiting")).toHaveClass(
      "chip--neutral",
    );

    await user.click(screen.getByTestId("extract-cancel-run"));
    await waitFor(() => expect(cancelled).toEqual(["run-1234abcd"]));
  });

  it("ends on the proposal with its counts and a warning for empty chunks", async () => {
    serve({
      runs: {
        "run-1234abcd": createRun({
          status: "completed",
          items_done: 3,
          proposal_id: "prop-1",
          output_summary: {
            metadata: {
              chunks: [
                {
                  index: 0,
                  start: 0,
                  end: 8000,
                  page_first: 1,
                  page_last: 2,
                  heading: "Parts",
                  triples: 5,
                },
                {
                  index: 1,
                  start: 8000,
                  end: 16000,
                  page_first: 3,
                  page_last: 3,
                  heading: "Warranty",
                  triples: 0,
                },
                {
                  index: 2,
                  start: 16000,
                  end: 20000,
                  page_first: 4,
                  page_last: 4,
                  heading: "Index",
                  triples: 0,
                },
              ],
            },
          },
        }),
        "run-schema": createRun({
          id: "run-schema",
          pipeline_type: "schema_extraction",
          status: "completed",
          proposal_id: "prop-schema",
        }),
      },
    });
    const user = userEvent.setup();
    const { onReview, onBack } = renderPage({ runId: "run-1234abcd", schemaRunId: "run-schema" });

    const done = await screen.findByTestId("extract-done-panel");
    expect(done).toHaveTextContent("Proposal ready");
    await waitFor(() =>
      expect(screen.getByTestId("extract-count-operations")).toHaveTextContent("3"),
    );
    // The dataset chosen for this extraction (the proposal's), not the source's.
    expect(done).toHaveTextContent(
      "Extraction: Whirlpool refrigerator: use and care guide · dataset cabin",
    );
    expect(screen.getByTestId("extract-count-individuals")).toHaveTextContent("2");
    expect(screen.getByTestId("extract-count-relationships")).toHaveTextContent("1");
    expect(screen.getByTestId("extract-count-near-matches")).toHaveTextContent("1");
    expect(screen.getByTestId("extract-count-individuals")).toHaveClass("stat-tile--emerald");

    const warning = screen.getByTestId("extract-empty-chunks");
    expect(warning).toHaveClass("form-callout--warn");
    expect(warning).toHaveTextContent("Chunks 2 and 3 (Warranty, Index) gave no candidates.");

    const chunk1 = screen.getByTestId("extract-chunk-1");
    expect(chunk1).toHaveTextContent("Parts");
    expect(chunk1).toHaveTextContent("pp. 1–2");
    expect(within(chunk1).getByText("5 found")).toHaveClass("chip--emerald");
    const chunk2 = screen.getByTestId("extract-chunk-2");
    expect(within(chunk2).getByText("0 found")).toHaveClass("chip--neutral");
    // Every chunk was read: nothing is marked failed.
    expect(chunk2).toHaveClass("chunk-list__row");
    expect(chunk2).not.toHaveClass("chunk-list__row--failed");
    expect(screen.queryByTestId("extract-chunk-2-reason")).not.toBeInTheDocument();
    expect(screen.queryByTestId("extract-failed-chunks")).not.toBeInTheDocument();
    expect(done).not.toHaveTextContent("Partial proposal ready");
    expect(screen.getByTestId("extract-chunk-count")).toHaveTextContent("3 chunks · 4 pages");

    await user.click(screen.getByTestId("extract-review-proposal"));
    expect(onReview).toHaveBeenCalledWith("prop-1");
    await user.click(await screen.findByTestId("extract-review-schema-proposal"));
    expect(onReview).toHaveBeenCalledWith("prop-schema");
    await user.click(screen.getByTestId("extract-back"));
    expect(onBack).toHaveBeenCalled();
  });

  it("moves from running to done as the run is polled", async () => {
    let polls = 0;
    serve({
      runs: {
        "run-1234abcd": () =>
          ++polls === 1
            ? createRun({ items_done: 2, items_total: 3 })
            : createRun({ status: "completed", items_done: 3, proposal_id: "prop-1" }),
      },
    });
    renderPage({ runId: "run-1234abcd" });

    expect(await screen.findByTestId("extract-running-panel")).toBeInTheDocument();
    expect(
      await screen.findByTestId("extract-done-panel", {}, { timeout: 4000 }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("extract-running-panel")).not.toBeInTheDocument();
  });

  it("says why a run failed and offers to extract again", async () => {
    serve({
      runs: {
        "run-1234abcd": createRun({ status: "failed", failure_reason: "Model quota exceeded" }),
      },
    });
    const user = userEvent.setup();
    const { onReset } = renderPage({ runId: "run-1234abcd" });

    const reason = await screen.findByTestId("extract-stopped-reason");
    expect(reason).toHaveTextContent("Model quota exceeded");
    expect(reason).toHaveClass("form-callout--error");
    expect(screen.getByTestId("extract-stopped-panel")).toHaveTextContent("Extraction failed");
    await user.click(screen.getByTestId("extract-retry"));
    expect(onReset).toHaveBeenCalled();
  });

  it.each([
    ["interrupted", "Stopped when the app closed", "it doesn't resume"],
    ["cancelled", "Run cancelled", "Nothing was proposed."],
  ])("treats a %s run as finished: no polling, no cancel", async (status, title, message) => {
    const { runReads } = serve({ runs: { "run-1234abcd": createRun({ status }) } });
    const user = userEvent.setup();
    const { onReset } = renderPage({ runId: "run-1234abcd" });

    const panel = await screen.findByTestId("extract-stopped-panel");
    expect(panel).toHaveTextContent(title);
    const reason = screen.getByTestId("extract-stopped-reason");
    expect(reason).toHaveTextContent(message);
    expect(reason).toHaveClass("form-callout--info");
    expect(screen.queryByTestId("extract-cancel-run")).not.toBeInTheDocument();
    expect(screen.queryByTestId("extract-progress-headline")).not.toBeInTheDocument();

    await new Promise((resolve) => setTimeout(resolve, 2500));
    expect(runReads).toEqual(["run-1234abcd"]);
    await user.click(screen.getByTestId("extract-retry"));
    expect(onReset).toHaveBeenCalled();
  });

  it("says a missing run is gone, stops polling, and offers a way out", async () => {
    const { runReads } = serve({ runs: {} });
    const user = userEvent.setup();
    const { onReset, onBack } = renderPage({ runId: "run-stale" });

    const panel = await screen.findByTestId("extract-run-error");
    expect(panel).toHaveTextContent("Couldn't load this run");
    const reason = screen.getByTestId("extract-run-error-reason");
    expect(reason).toHaveClass("form-callout--error");
    expect(reason).toHaveTextContent("This run no longer exists.");
    expect(screen.queryByTestId("extract-running-panel")).not.toBeInTheDocument();

    // A 404 is not retried, and the poll stops.
    await new Promise((resolve) => setTimeout(resolve, 2500));
    expect(runReads).toEqual(["run-stale"]);
    await user.click(screen.getByTestId("extract-back"));
    expect(onBack).toHaveBeenCalled();
    await user.click(screen.getByTestId("extract-retry"));
    expect(onReset).toHaveBeenCalled();
  });
});

/** A completed run's chunks, each with how many candidates it found. */
function chunksFound(...found: number[]) {
  return found.map((triples, index) => ({
    index,
    start: index * 5000,
    end: (index + 1) * 5000,
    page_first: index + 1,
    page_last: index + 1,
    heading: null,
    triples,
    failure_reason: null as string | null,
  }));
}

/** The same chunks, with the extraction of those at `failed` (0-based) having failed. */
function chunksWithFailures(found: number[], failed: Record<number, string>) {
  return chunksFound(...found).map((chunk) => ({
    ...chunk,
    failure_reason: failed[chunk.index] ?? null,
  }));
}

const CUT_SHORT = "The model's answer was cut short after 3 attempts.";

const RELATIONSHIPS_UNREAD = `Its relationships could not be read: ${CUT_SHORT}`;

describe("ExtractSourcePage — a run some of whose chunks failed", () => {
  it("shows what a chunk that failed in part still gave, and that part is missing", async () => {
    // find-then-type keeps a chunk's individuals when only its relationships failed.
    const chunks = chunksWithFailures([5, 4, 2], { 1: RELATIONSHIPS_UNREAD });
    serve({
      runs: {
        "run-1234abcd": createRun({
          implementation_id: "find_then_type",
          status: "completed",
          items_done: 3,
          proposal_id: "prop-1",
          output_summary: { metadata: { chunks }, failed_chunks: [chunks[1]] },
        }),
      },
    });
    renderPage({ runId: "run-1234abcd" });

    const done = await screen.findByTestId("extract-done-panel");
    expect(done).toHaveTextContent("Partial proposal ready");
    const failed = screen.getByTestId("extract-failed-chunks");
    expect(failed).toHaveClass("form-callout--error");
    expect(failed).toHaveTextContent(
      "Extraction failed in part for 1 of 3 chunks: chunk 2. Part of what it holds is missing.",
    );
    expect(failed).not.toHaveTextContent("What it holds is missing");

    const chunk2 = screen.getByTestId("extract-chunk-2");
    expect(chunk2).toHaveClass("chunk-list__row", "chunk-list__row--failed");
    expect(within(chunk2).getByText("4 found, incomplete")).toHaveClass("chip--amber");
    expect(within(chunk2).queryByText("failed")).not.toBeInTheDocument();
    expect(screen.getByTestId("extract-chunk-2-reason")).toHaveTextContent(RELATIONSHIPS_UNREAD);
    expect(screen.queryByTestId("extract-empty-chunks")).not.toBeInTheDocument();
  });

  it("marks one failed chunk of three and calls the proposal partial", async () => {
    const chunks = chunksWithFailures([5, 0, 0], { 1: CUT_SHORT });
    serve({
      runs: {
        "run-1234abcd": createRun({
          status: "completed",
          items_done: 3,
          proposal_id: "prop-1",
          output_summary: {
            metadata: { chunks },
            failed_chunks: [chunks[1]],
            warnings: [
              `Extraction failed for 1 of 3 chunks (chunk 2), so what they hold is missing. First failure: ${CUT_SHORT}`,
            ],
          },
        }),
      },
    });
    renderPage({ runId: "run-1234abcd" });

    const done = await screen.findByTestId("extract-done-panel");
    expect(done).toHaveTextContent("Partial proposal ready");
    await waitFor(() =>
      expect(screen.getByTestId("extract-count-operations")).toHaveTextContent("3"),
    );

    const failed = screen.getByTestId("extract-failed-chunks");
    expect(failed).toHaveClass("form-callout--error");
    expect(failed).toHaveAttribute("role", "alert");
    expect(failed).toHaveTextContent(
      "Extraction failed for 1 of 3 chunks: chunk 2. What it holds is missing.",
    );
    // The failed chunk is not one that gave no candidates; the empty one still is.
    const empty = screen.getByTestId("extract-empty-chunks");
    expect(empty).toHaveClass("form-callout--warn");
    expect(empty).toHaveTextContent("Chunk 3 gave no candidates.");
    expect(done).not.toHaveTextContent("Chunk 2 gave no candidates");
    expect(done).not.toHaveTextContent("Chunks 2 and 3 gave no candidates");

    const chunk2 = screen.getByTestId("extract-chunk-2");
    expect(chunk2).toHaveClass("chunk-list__row", "chunk-list__row--failed");
    expect(within(chunk2).getByText("failed")).toHaveClass("chip--rose");
    expect(chunk2).not.toHaveTextContent("0 found");
    const reason = screen.getByTestId("extract-chunk-2-reason");
    expect(reason).toHaveClass("chunk-list__reason");
    expect(reason).toHaveTextContent(CUT_SHORT);
    // The chunks that were read keep their counts.
    expect(within(screen.getByTestId("extract-chunk-1")).getByText("5 found")).toHaveClass(
      "chip--emerald",
    );
    const chunk3 = screen.getByTestId("extract-chunk-3");
    expect(within(chunk3).getByText("0 found")).toHaveClass("chip--neutral");
    expect(chunk3).not.toHaveClass("chunk-list__row--failed");
    expect(within(screen.getByTestId("extract-chunk-list")).getAllByRole("listitem")).toHaveLength(
      3,
    );
    expect(screen.getByTestId("extract-review-proposal")).toBeInTheDocument();
  });

  it("says two of three chunks failed, not that no candidates were found", async () => {
    const chunks = chunksWithFailures([0, 0, 0], { 1: CUT_SHORT, 2: "Connection reset by peer" });
    const serverReason =
      "Extraction failed for 2 of 3 chunks (chunks 2, 3), so what they hold is missing." +
      ` First failure: ${CUT_SHORT} The run found no candidates in what it could read.`;
    serve({
      runs: {
        "run-1234abcd": createRun({
          status: "completed",
          items_done: 3,
          proposal_id: null,
          output_summary: {
            metadata: { chunks },
            failed_chunks: chunks.slice(1),
            warnings: [`Nothing to propose. ${serverReason}`],
            no_proposal_reason: serverReason,
          },
        }),
      },
    });
    renderPage({ runId: "run-1234abcd" });

    const panel = await screen.findByTestId("extract-done-panel");
    expect(panel).toHaveTextContent("Nothing proposed");
    expect(panel).not.toHaveTextContent("No candidates found");
    expect(panel).not.toHaveTextContent("Proposal ready");

    const failed = screen.getByTestId("extract-failed-chunks");
    expect(failed).toHaveClass("form-callout--error");
    expect(failed).toHaveAttribute("role", "alert");
    expect(failed).toHaveTextContent(
      "Extraction failed for 2 of 3 chunks: chunks 2 and 3. What they hold is missing.",
    );
    // What was read found nothing: said once, without repeating which chunks failed.
    const note = screen.getByTestId("extract-no-proposal");
    expect(note).toHaveClass("form-callout--info");
    expect(note).toHaveTextContent("The chunks that were read found nothing to propose.");
    expect(panel).not.toHaveTextContent("The run read every chunk");
    expect(panel).not.toHaveTextContent("gave no candidates");
    expect(screen.queryByTestId("extract-empty-chunks")).not.toBeInTheDocument();
    expect(screen.queryByTestId("extract-review-proposal")).not.toBeInTheDocument();

    for (const [n, why] of [
      [2, CUT_SHORT],
      [3, "Connection reset by peer"],
    ] as const) {
      const row = screen.getByTestId(`extract-chunk-${n}`);
      expect(row).toHaveClass("chunk-list__row--failed");
      expect(within(row).getByText("failed")).toHaveClass("chip--rose");
      expect(screen.getByTestId(`extract-chunk-${n}-reason`)).toHaveTextContent(why);
    }
    const chunk1 = screen.getByTestId("extract-chunk-1");
    expect(within(chunk1).getByText("0 found")).toHaveClass("chip--neutral");
    expect(chunk1).not.toHaveClass("chunk-list__row--failed");
  });

  it("still says why found candidates were not proposed", async () => {
    serve({
      runs: {
        "run-1234abcd": createRun({
          status: "completed",
          items_done: 3,
          proposal_id: null,
          output_summary: {
            metadata: { chunks: chunksWithFailures([4, 0, 3], { 1: CUT_SHORT }) },
            no_proposal_reason:
              "Extraction failed for 1 of 3 chunks (chunk 2), so what they hold is missing." +
              ` First failure: ${CUT_SHORT} None of the 7 candidates made an operation (exists 7).`,
            skipped_by_reason: { exists: 7 },
          },
        }),
      },
    });
    renderPage({ runId: "run-1234abcd" });

    const panel = await screen.findByTestId("extract-done-panel");
    expect(panel).toHaveTextContent("Nothing proposed");
    expect(screen.getByTestId("extract-failed-chunks")).toHaveTextContent(
      "Extraction failed for 1 of 3 chunks: chunk 2. What it holds is missing.",
    );
    const note = screen.getByTestId("extract-no-proposal");
    expect(note).toHaveClass("form-callout--warn");
    expect(note).toHaveTextContent("The chunks found 7 candidates, but none could be proposed.");
    expect(screen.getByTestId("extract-skipped")).toHaveTextContent("7 already exist");
  });
});

describe("ExtractSourcePage — a run that proposes nothing", () => {
  it("says candidates were found but none could be proposed, and why not", async () => {
    serve({
      runs: {
        "run-1234abcd": createRun({
          status: "completed",
          items_done: 4,
          items_total: 4,
          proposal_id: null,
          output_summary: {
            metadata: { chunks: chunksFound(24, 20, 27, 4) },
            skipped_candidates: [
              { label: "Compressor", reason: "exists" },
              { label: "Ice maker", reason: "exists" },
              { label: "Water line", reason: "missing_class" },
            ],
            refused_operations: [],
          },
        }),
      },
    });
    renderPage({ runId: "run-1234abcd" });

    const panel = await screen.findByTestId("extract-done-panel");
    expect(panel).toHaveTextContent("Nothing proposed");
    expect(panel).not.toHaveTextContent("Proposal ready");
    const note = screen.getByTestId("extract-no-proposal");
    expect(note).toHaveClass("form-callout--warn");
    expect(note).toHaveTextContent("The chunks found 75 candidates, but none could be proposed.");
    expect(note).not.toHaveTextContent("no candidates were found");
    const skipped = screen.getByTestId("extract-skipped");
    expect(skipped).toHaveClass("extract-run__skipped");
    expect(skipped).toHaveTextContent("Not proposed2 already exist, 1 no matching class");
    expect(within(skipped).getByText("Not proposed")).toHaveClass("extract-run__skipped-label");
    expect(screen.queryByTestId("extract-review-proposal")).not.toBeInTheDocument();
    expect(screen.queryByTestId("extract-count-operations")).not.toBeInTheDocument();
  });

  it("shows the server's reason and skipped counts by reason when it reports them", async () => {
    serve({
      runs: {
        "run-1234abcd": createRun({
          status: "completed",
          items_done: 2,
          items_total: 2,
          proposal_id: null,
          output_summary: {
            metadata: { chunks: chunksFound(6, 3) },
            no_proposal_reason:
              "None of the 9 candidates made an operation (exists 7, unresolved_predicate 2).",
            skipped_by_reason: { exists: 7, unresolved_predicate: 2 },
          },
        }),
      },
    });
    renderPage({ runId: "run-1234abcd" });

    const note = await screen.findByTestId("extract-no-proposal");
    expect(note).toHaveTextContent(
      "None of the 9 candidates made an operation (exists 7, unresolved_predicate 2).",
    );
    expect(screen.getByTestId("extract-done-panel")).toHaveTextContent("Nothing proposed");
    expect(screen.getByTestId("extract-skipped")).toHaveTextContent(
      "7 already exist, 2 unknown relationship type",
    );
  });

  it("is titled for the schema proposal when only the schema run proposed", async () => {
    serve({
      runs: {
        "run-1234abcd": createRun({
          status: "completed",
          items_done: 2,
          items_total: 2,
          proposal_id: null,
          output_summary: { metadata: { chunks: chunksFound(0, 0) } },
        }),
        "run-schema": createRun({
          id: "run-schema",
          pipeline_type: "schema_extraction",
          status: "completed",
          proposal_id: "prop-schema",
        }),
      },
    });
    const user = userEvent.setup();
    const { onReview } = renderPage({ runId: "run-1234abcd", schemaRunId: "run-schema" });

    const review = await screen.findByTestId("extract-review-schema-proposal");
    const panel = screen.getByTestId("extract-done-panel");
    expect(panel).toHaveTextContent("Schema proposal ready");
    expect(panel).not.toHaveTextContent("No candidates found");
    // The individual run's outcome is still said in the body.
    expect(screen.getByTestId("extract-no-proposal")).toHaveTextContent(
      "The run read every chunk and found nothing to propose.",
    );
    expect(screen.queryByTestId("extract-review-proposal")).not.toBeInTheDocument();
    await user.click(review);
    expect(onReview).toHaveBeenCalledWith("prop-schema");
  });

  it("says no candidates were found only when the chunks found none", async () => {
    serve({
      runs: {
        "run-1234abcd": createRun({
          status: "completed",
          items_done: 2,
          items_total: 2,
          proposal_id: null,
          output_summary: { metadata: { chunks: chunksFound(0, 0) } },
        }),
      },
    });
    renderPage({ runId: "run-1234abcd" });

    const panel = await screen.findByTestId("extract-done-panel");
    expect(panel).toHaveTextContent("No candidates found");
    expect(panel).not.toHaveTextContent("Proposal ready");
    const note = screen.getByTestId("extract-no-proposal");
    expect(note).toHaveClass("form-callout--info");
    expect(note).toHaveTextContent("The run read every chunk and found nothing to propose.");
    expect(screen.queryByTestId("extract-skipped")).not.toBeInTheDocument();
    // Naming every empty chunk would only repeat the note.
    expect(screen.queryByTestId("extract-empty-chunks")).not.toBeInTheDocument();
  });
});

describe("ExtractSourcePage — schema suggestions on a mirrored taxonomy", () => {
  const mirroredHouse = createTaxonomy({
    id: "tax-house",
    identifier: "house",
    title: "House",
    mirrored: true,
  });

  it("labels the option by its own name", async () => {
    serve();
    renderPage();
    const schema = await screen.findByTestId("extract-schema-toggle");
    expect(schema).toHaveAttribute("type", "checkbox");
    expect(schema).toHaveAccessibleName("Also suggest schema changes");
    expect(schema).toHaveAccessibleDescription(/Runs schema extraction too/);
    await waitFor(() => expect(schema).toBeEnabled());
    expect(schema.closest("label")).not.toHaveClass("extract-check--disabled");
  });

  it("keeps the option off until the taxonomy is known, and sends no schema run", async () => {
    const { extractBodies } = serve();
    // The taxonomy can't be read, so whether it is mirrored is never known.
    server.use(
      http.get("*/api/taxonomies/:id", () =>
        HttpResponse.json({ detail: "Server error" }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    const { onRunsStarted } = renderPage();

    const schema = await screen.findByTestId("extract-schema-toggle");
    expect(schema).toBeDisabled();
    expect(schema.closest("label")).toHaveClass("extract-check--disabled");
    await user.click(schema);
    expect(schema).not.toBeChecked();
    await user.click(screen.getByTestId("extract-start"));
    await waitFor(() => expect(onRunsStarted).toHaveBeenCalled());
    expect(extractBodies).toEqual([expect.objectContaining({ schema: false })]);
    expect(schema).toBeDisabled();
  });

  it("disables the option and says why, and starts without it", async () => {
    const { extractBodies } = serve({ taxonomy: mirroredHouse });
    const user = userEvent.setup();
    const { onRunsStarted } = renderPage();

    const schema = await screen.findByTestId("extract-schema-toggle");
    await waitFor(() => expect(schema).toBeDisabled());
    expect(schema).not.toBeChecked();
    expect(schema).toHaveAccessibleName("Also suggest schema changes");
    expect(schema).toHaveAccessibleDescription(/mirrors a client's spec/);
    expect(screen.getByTestId("extract-schema-hint")).toHaveTextContent(
      "only that client proposes schema changes, over MCP",
    );
    expect(schema.closest("label")).toHaveClass("extract-check", "extract-check--disabled");
    expect(screen.getByTestId("extract-estimate")).toHaveTextContent("One run, one proposal");

    await user.click(schema);
    expect(schema).not.toBeChecked();
    await user.click(screen.getByTestId("extract-start"));
    await waitFor(() => expect(onRunsStarted).toHaveBeenCalled());
    expect(extractBodies).toEqual([expect.objectContaining({ schema: false })]);
  });
});

describe("ExtractSourcePage — a start error", () => {
  const refusal = () =>
    HttpResponse.json(
      { detail: "Only the client may start a refinement of this taxonomy, over MCP." },
      { status: 403 },
    );

  async function failStart() {
    const user = userEvent.setup();
    renderPage();
    const schema = await screen.findByTestId("extract-schema-toggle");
    await waitFor(() => expect(schema).toBeEnabled());
    await user.click(schema);
    await user.click(screen.getByTestId("extract-start"));
    const error = await screen.findByTestId("extract-start-error");
    expect(error).toHaveClass("form-callout--error");
    expect(error).toHaveTextContent("Only the client may start a refinement");
    return { user, schema };
  }

  it("clears when the schema option is unchecked", async () => {
    serve({ extract: refusal });
    const { user, schema } = await failStart();
    await user.click(schema);
    expect(screen.queryByTestId("extract-start-error")).not.toBeInTheDocument();
    expect(screen.queryByText(/Only the client may start/)).not.toBeInTheDocument();
  });

  it("clears when the page range changes", async () => {
    serve({ extract: refusal });
    const { user } = await failStart();
    await user.type(screen.getByTestId("extract-pages"), "1");
    expect(screen.queryByTestId("extract-start-error")).not.toBeInTheDocument();
    expect(screen.queryByText(/Only the client may start/)).not.toBeInTheDocument();
  });

  it("clears when another dataset is chosen", async () => {
    serve({ extract: refusal });
    const { user } = await failStart();
    await user.click(
      within(screen.getByTestId("extract-dataset")).getByRole("radio", { name: "cabin" }),
    );
    expect(screen.queryByTestId("extract-start-error")).not.toBeInTheDocument();
    expect(screen.queryByText(/Only the client may start/)).not.toBeInTheDocument();
  });
});

describe("progress bar track", () => {
  it("uses the canvas border tone, so an empty bar reads empty on the light canvas", () => {
    // Heimdall's track is the shell navy on both canvases; the app override fixes it.
    // Vitest runs from ux/.
    const appOverrides = readFileSync(
      join(process.cwd(), "src/design-system/app-overrides.css"),
      "utf8",
    );
    const rule = /\.progress-bar\s*\{[^}]*\}/.exec(appOverrides)?.[0] ?? "";
    expect(rule).toContain("background-color: rgb(var(--canvas-border));");
    expect(rule).not.toContain("shell-surface");
  });
});
