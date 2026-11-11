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
// open_v1 doesn't chunk: the extract endpoint refuses its configurations.
const openConfig = createConfiguration({
  id: "cfg-2",
  config_ref: "extraction-open-v1",
  implementation_id: "open_v1",
  model: null,
});

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  toastSpy.mockClear();
});
afterAll(() => server.close());

interface ServeOptions {
  source?: Source;
  configs?: PipelineConfiguration[];
  runs?: Record<string, PipelineRun | (() => PipelineRun)>;
  extract?: () => Response;
}

function serve({
  source = createSource(),
  configs = [defaultConfig, openRouterConfig, disabledConfig, openConfig],
  runs = {},
  extract,
}: ServeOptions = {}) {
  const extractBodies: unknown[] = [];
  const cancelled: string[] = [];
  const runReads: string[] = [];
  const configRequests: string[] = [];
  server.use(
    http.get("*/api/sources/:id", () => HttpResponse.json(source)),
    http.get("*/api/taxonomies/:id", () => HttpResponse.json(house)),
    http.get("*/api/datasets", () => HttpResponse.json([home, cabin])),
    http.get("*/api/pipelines/types/individual_extraction/implementations", () =>
      HttpResponse.json([{ id: "default" }, { id: "open_v1" }]),
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
              ...({ alternatives: [{ kind: "existing", entity_id: "i-9" }] } as object),
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
    const config = screen.getByTestId("extract-config");
    expect(config).toHaveAccessibleName("Individual extraction");
    await waitFor(() => expect(config).toHaveValue("extraction-default"));
    // Only the default implementation's enabled configurations: open_v1 doesn't chunk.
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
    await user.click(screen.getByTestId("extract-schema-toggle"));
    await user.click(screen.getByTestId("extract-start"));

    await waitFor(() => expect(onRunsStarted).toHaveBeenCalled());
    expect(extractBodies).toEqual([
      {
        dataset: "ds-cabin",
        configuration_ref: "extraction-openrouter-default",
        pages: "1-2",
        schema: true,
      },
    ]);
    expect(onRunsStarted).toHaveBeenCalledWith([
      { run_id: "run-1234abcd", pipeline: "individual_extraction" },
    ]);
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
    expect(within(screen.getByTestId("extract-chunk-2")).getByText("0 found")).toHaveClass(
      "chip--neutral",
    );
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
