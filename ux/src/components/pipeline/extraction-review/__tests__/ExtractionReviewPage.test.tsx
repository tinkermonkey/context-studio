import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { renderWithProviders } from "@/test/test-utils";
import { ExtractionReviewPage } from "../ExtractionReviewPage";
import {
  SCHEMA_CANDIDATES,
  SCHEMA_RECOGNITION,
  TRIPLES,
  RECOGNITION,
  XR_TEXT,
  makeRun,
} from "./fixtures";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 100, offset: 0 });
// The default implementation is not called "default" and is not listed first:
// the page may rely on neither.
const config = (
  type: string,
  implementation: string,
  ref: string,
  overrides: Record<string, unknown> = {},
) => ({
  id: `${type}:${implementation}:${ref}`,
  config_ref: ref,
  pipeline_type: type,
  implementation_id: implementation,
  name: ref,
  provider: "openrouter",
  model: "gemini-flash",
  enabled: true,
  is_default: false,
  version: 1,
  ...overrides,
});
const CONFIGS = [
  config("schema_extraction", "base", "schema-extraction-default", { is_default: true }),
  config("individual_extraction", "base", "extraction-openrouter-default"),
  config("individual_extraction", "base", "extraction-default", {
    is_default: true,
    provider: "anthropic",
    model: "opus",
  }),
  config("individual_extraction", "base", "extraction-disabled", { enabled: false }),
  config("individual_extraction", "two_step", "extraction-two-step", {
    is_default: true,
    provider: "anthropic",
    model: "haiku",
  }),
];

let runBodies: Record<string, Record<string, unknown>> = {};
let runListQueries: URLSearchParams[] = [];

const EXAMPLES = [
  {
    id: "glossary-note",
    title: "Glossary note",
    description: "Exercises plain glossary prose.",
    pipelines: ["schema_extraction"],
    taxonomy_hint: "tax_other",
    text: "A glossary entry defines one term.",
  },
  {
    id: "no-hint",
    title: "No hint",
    description: "Exercises nothing in particular.",
    pipelines: ["individual_extraction"],
    text: "Plain text.",
  },
];

beforeEach(() => {
  runBodies = {};
  runListQueries = [];
  server.use(
    http.get("*/api/pipelines/extraction-examples", () => HttpResponse.json(EXAMPLES)),
    http.get("*/api/pipelines/runs", ({ request }) => {
      const query = new URL(request.url).searchParams;
      runListQueries.push(query);
      return HttpResponse.json(
        page(
          query.get("example_id") === "glossary-note"
            ? [
                makeRun({ id: "run-old-s", configuration_slug: "schema-extraction-default" }),
                makeRun({ id: "run-old-r", pipeline_type: "schema_relationship_reflection" }),
              ]
            : [],
        ),
      );
    }),
    http.get("*/api/taxonomies", () =>
      HttpResponse.json(
        page([
          { id: "tax-other", identifier: "tax_other", title: "Life Sciences" },
          { id: "tax-dr", identifier: "dr_spec", title: "Documentation Robotics" },
        ]),
      ),
    ),
    // One dataset per taxonomy: the dataset is implied and no choice is offered.
    http.get("*/api/datasets", ({ request }) => {
      const tax = new URL(request.url).searchParams.get("taxonomy_id");
      return HttpResponse.json([{ id: `ds-${tax}`, taxonomy_id: tax, identifier: "default" }]);
    }),
    http.get("*/api/schemes", ({ request }) => {
      const tax = new URL(request.url).searchParams.get("taxonomy_id");
      return HttpResponse.json(
        page(
          tax === "tax-dr"
            ? [{ id: "scheme-app", identifier: "application", title: "Application Layer" }]
            : [],
        ),
      );
    }),
    http.get("*/api/pipelines/types/:type/implementations", ({ params }) =>
      HttpResponse.json([
        // Only individual extraction has the second implementation.
        ...(params.type === "individual_extraction"
          ? [{ id: "two_step", pipeline_type: params.type, is_default: false }]
          : []),
        { id: "base", pipeline_type: params.type, is_default: true },
      ]),
    ),
    http.get("*/api/pipelines/types/:type/implementations/:impl/configurations", ({ params }) =>
      HttpResponse.json(
        CONFIGS.filter(
          (c) => c.pipeline_type === params.type && c.implementation_id === params.impl,
        ),
      ),
    ),
  );
});

function mockRuns(individual: "ok" | "fail") {
  server.use(
    http.post("*/api/pipelines/:type/run", async ({ params, request }) => {
      runBodies[String(params.type)] = (await request.json()) as Record<string, unknown>;
      if (params.type === "schema_extraction") return HttpResponse.json(makeRun());
      if (individual === "fail")
        return HttpResponse.json({ detail: "model is required" }, { status: 400 });
      return HttpResponse.json(makeRun({ id: "run-i", pipeline_type: "individual_extraction" }));
    }),
    http.get("*/api/pipelines/runs/run-s/schema-extraction-candidates", () =>
      HttpResponse.json(SCHEMA_CANDIDATES),
    ),
    http.get("*/api/pipelines/runs/run-i/individual-extraction-candidates", () =>
      HttpResponse.json(TRIPLES),
    ),
    http.post("*/api/pipelines/runs/run-i/recognition-preview", () =>
      HttpResponse.json(RECOGNITION),
    ),
    http.post("*/api/pipelines/runs/run-s/recognition-preview", () =>
      HttpResponse.json(SCHEMA_RECOGNITION),
    ),
  );
}

/** Both pickers show the server's default selection. */
async function selectionLoaded() {
  await waitFor(() =>
    expect(screen.getByTestId("extraction-review-schema-configuration")).toHaveValue(
      "schema-extraction-default",
    ),
  );
  await waitFor(() =>
    expect(screen.getByTestId("extraction-review-individual-configuration")).toHaveValue(
      "extraction-default",
    ),
  );
}

async function renderPage() {
  renderWithProviders(<ExtractionReviewPage />);
  await selectionLoaded();
}

describe("ExtractionReviewPage", () => {
  it("renders the input panel, defaults the scope to dr_spec and starts idle", async () => {
    await renderPage();
    expect(screen.getByTestId("extraction-review-page")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-taxonomy")).toHaveValue("tax-dr");
    // Each run has its own picker, on the server's default implementation and configuration.
    const schemaPicker = screen.getByTestId("extraction-review-schema-picker");
    expect(schemaPicker).toHaveAccessibleName("Schema extraction");
    expect(within(schemaPicker).getByText("Implementation")).toBeInTheDocument();
    expect(within(schemaPicker).getByText("Configuration")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-schema-implementation")).toHaveValue("base");
    const individualPicker = screen.getByTestId("extraction-review-individual-picker");
    expect(individualPicker).toHaveAccessibleName("Individual extraction");
    const individualImplementation = screen.getByTestId(
      "extraction-review-individual-implementation",
    );
    expect(individualImplementation).toHaveValue("base");
    expect(
      within(individualImplementation)
        .getAllByRole("option")
        .map((o) => o.getAttribute("value")),
    ).toEqual(["two_step", "base"]);
    // A disabled configuration is not offered.
    expect(
      within(screen.getByTestId("extraction-review-individual-configuration"))
        .getAllByRole("option")
        .map((o) => o.getAttribute("value")),
    ).toEqual(["extraction-openrouter-default", "extraction-default"]);
    expect(
      screen.getByTestId("extraction-review-individual-configuration-model"),
    ).toHaveTextContent("anthropic · opus");
    expect(screen.getByTestId("extraction-review-schema-idle")).toBeInTheDocument();
    const tabs = screen.getByTestId("extraction-review-tabs");
    expect(tabs).toHaveAttribute("role", "tablist");
    expect(within(tabs).getByRole("tab", { name: "Schema extraction" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("shows a required error on run and clears it as soon as the user types", async () => {
    await renderPage();
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    expect(screen.getByText("Paste a paragraph to extract from")).toBeInTheDocument();
    const textarea = screen.getByTestId("extraction-review-text");
    expect(textarea).toHaveClass("text-area--error");
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    await userEvent.type(textarea, "A");
    expect(screen.queryByText("Paste a paragraph to extract from")).not.toBeInTheDocument();
    expect(textarea).not.toHaveClass("text-area--error");

    // Emptying the field again and leaving it re-shows the error on blur.
    await userEvent.clear(textarea);
    expect(screen.queryByText("Paste a paragraph to extract from")).not.toBeInTheDocument();
    await userEvent.tab();
    expect(screen.getByText("Paste a paragraph to extract from")).toBeInTheDocument();
  });

  it("starts both runs on the same text and reviews them in place", async () => {
    mockRuns("ok");
    await renderPage();
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);
    await userEvent.click(screen.getByTestId("extraction-review-run"));

    expect(await screen.findByTestId("extraction-review-schema-candidates")).toBeInTheDocument();
    expect(runBodies.schema_extraction).toMatchObject({
      implementation_id: "base",
      configuration_ref: "schema-extraction-default",
      documents: [XR_TEXT],
      scope: "tax-dr",
    });
    expect(runBodies.individual_extraction).toMatchObject({
      implementation_id: "base",
      configuration_ref: "extraction-default",
      text: XR_TEXT,
      ontology_id: "tax-dr",
    });
    // Both start in the background, so a long run outlives no request timeout.
    expect(runBodies.schema_extraction).toMatchObject({ async: true });
    expect(runBodies.individual_extraction).toMatchObject({ async: true });
    // The model is the configuration's: the page never sends one.
    expect(runBodies.schema_extraction).not.toHaveProperty("model");
    expect(runBodies.individual_extraction).not.toHaveProperty("model");
    // One dataset: it is implied, so none is offered or sent.
    expect(screen.queryByTestId("extraction-review-dataset")).not.toBeInTheDocument();
    expect(runBodies.individual_extraction).not.toHaveProperty("dataset_id");

    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-0-yes"));
    await userEvent.click(screen.getByRole("tab", { name: "Individual extraction" }));
    expect(await screen.findByTestId("extraction-review-triples")).toBeInTheDocument();
    expect(screen.getByRole("tabpanel", { name: "Individual extraction" })).toBeVisible();
    const individualTab = screen.getByRole("tab", { name: "Individual extraction" });
    const individualPanel = screen.getByRole("tabpanel", { name: "Individual extraction" });
    expect(individualTab).toHaveAttribute("aria-controls", individualPanel.id);
    expect(individualPanel).toHaveAttribute("aria-labelledby", individualTab.id);
    expect(individualTab).toHaveAttribute("aria-selected", "true");
    const schemaTab = screen.getByRole("tab", { name: "Schema extraction" });
    const schemaPanel = screen
      .getByTestId("extraction-review-schema")
      .closest("[role=tabpanel]") as HTMLElement;
    expect(schemaTab).toHaveAttribute("aria-controls", schemaPanel.id);
    expect(schemaPanel).toHaveAttribute("aria-labelledby", schemaTab.id);
    expect(schemaPanel.id).not.toBe(individualPanel.id);
    expect(
      screen.getByTestId("extraction-review-schema").closest("[role=tabpanel]"),
    ).toHaveAttribute("hidden");

    // Decisions survive switching tabs.
    await userEvent.click(screen.getByRole("tab", { name: "Schema extraction" }));
    expect(screen.getByTestId("extraction-review-schema-decision-class-0-yes")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("runs each type with its own implementation and configuration", async () => {
    mockRuns("ok");
    await renderPage();
    await userEvent.selectOptions(
      screen.getByTestId("extraction-review-individual-implementation"),
      "two_step",
    );
    const configuration = screen.getByTestId("extraction-review-individual-configuration");
    await waitFor(() => expect(configuration).toHaveValue("extraction-two-step"));
    // The schema run keeps its own selection.
    expect(screen.getByTestId("extraction-review-schema-implementation")).toHaveValue("base");

    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    await screen.findByTestId("extraction-review-schema-candidates");
    expect(runBodies.individual_extraction).toMatchObject({
      implementation_id: "two_step",
      configuration_ref: "extraction-two-step",
    });
    expect(runBodies.schema_extraction).toMatchObject({
      implementation_id: "base",
      configuration_ref: "schema-extraction-default",
    });
  });

  it("keeps one tab reviewable when the other run fails", async () => {
    mockRuns("fail");
    await renderPage();
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    expect(await screen.findByTestId("extraction-review-schema-candidates")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Individual extraction" }));
    const failed = await screen.findByTestId("extraction-review-individual-failed");
    expect(within(failed).getByRole("alert")).toHaveTextContent("model is required");
  });

  it("asks which dataset to extract into when the taxonomy has several", async () => {
    mockRuns("ok");
    server.use(
      http.get("*/api/datasets", () =>
        HttpResponse.json([
          { id: "ds-a", taxonomy_id: "tax-dr", identifier: "alpha" },
          { id: "ds-b", taxonomy_id: "tax-dr", identifier: "beta" },
        ]),
      ),
    );
    await renderPage();
    const dataset = await screen.findByTestId("extraction-review-dataset");
    expect(dataset).toHaveAccessibleName("Dataset");
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);

    // Neither run starts until a dataset is chosen.
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    expect(screen.getByText("Select a dataset", { selector: "[id$='-error']" })).toHaveAttribute(
      "id",
      "extraction-review-dataset-error",
    );
    expect(runBodies).toEqual({});

    await userEvent.selectOptions(dataset, "ds-b");
    expect(
      screen.queryByText("Select a dataset", { selector: "[id$='-error']" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    await screen.findByTestId("extraction-review-schema-candidates");
    expect(runBodies.individual_extraction).toMatchObject({ dataset_id: "ds-b" });
    // The schema run reads no dataset.
    expect(runBodies.schema_extraction).not.toHaveProperty("dataset_id");
  });

  it("re-runs a failed type with the selection its picker shows now", async () => {
    mockRuns("fail");
    await renderPage();
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    await userEvent.click(screen.getByRole("tab", { name: "Individual extraction" }));
    const failed = await screen.findByTestId("extraction-review-individual-failed");
    expect(runBodies.individual_extraction).toMatchObject({
      implementation_id: "base",
      configuration_ref: "extraction-default",
    });

    // The run is over, so the picker is free again: choose another implementation.
    await userEvent.selectOptions(
      screen.getByTestId("extraction-review-individual-implementation"),
      "two_step",
    );
    await waitFor(() =>
      expect(screen.getByTestId("extraction-review-individual-configuration")).toHaveValue(
        "extraction-two-step",
      ),
    );
    await userEvent.click(
      within(failed).getByRole("button", { name: /Re-run individual_extraction/ }),
    );

    await waitFor(() =>
      expect(runBodies.individual_extraction).toMatchObject({
        implementation_id: "two_step",
        configuration_ref: "extraction-two-step",
        text: XR_TEXT,
      }),
    );
  });

  it("re-runs a failed schema run with the selection its picker shows now", async () => {
    // A second schema implementation, so the schema picker has a choice to make.
    server.use(
      http.get("*/api/pipelines/types/:type/implementations", ({ params }) =>
        HttpResponse.json([
          { id: "schema_alt", pipeline_type: params.type, is_default: false },
          { id: "base", pipeline_type: params.type, is_default: true },
        ]),
      ),
      http.get("*/api/pipelines/types/:type/implementations/:impl/configurations", ({ params }) =>
        HttpResponse.json(
          params.impl === "schema_alt"
            ? [
                config(String(params.type), "schema_alt", "schema-alt-main", {
                  is_default: true,
                }),
              ]
            : CONFIGS.filter(
                (c) => c.pipeline_type === params.type && c.implementation_id === params.impl,
              ),
        ),
      ),
      // The schema run fails; the individual one completes.
      http.post("*/api/pipelines/:type/run", async ({ params, request }) => {
        runBodies[String(params.type)] = (await request.json()) as Record<string, unknown>;
        if (params.type === "schema_extraction")
          return HttpResponse.json({ detail: "schema run failed" }, { status: 400 });
        return HttpResponse.json(makeRun({ id: "run-i", pipeline_type: "individual_extraction" }));
      }),
      http.get("*/api/pipelines/runs/run-i/individual-extraction-candidates", () =>
        HttpResponse.json(TRIPLES),
      ),
      http.post("*/api/pipelines/runs/run-i/recognition-preview", () =>
        HttpResponse.json(RECOGNITION),
      ),
    );
    await renderPage();
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    const failed = await screen.findByTestId("extraction-review-schema-failed");
    expect(runBodies.schema_extraction).toMatchObject({
      implementation_id: "base",
      configuration_ref: "schema-extraction-default",
    });
    const individualBody = runBodies.individual_extraction;

    await userEvent.selectOptions(
      screen.getByTestId("extraction-review-schema-implementation"),
      "schema_alt",
    );
    await waitFor(() =>
      expect(screen.getByTestId("extraction-review-schema-configuration")).toHaveValue(
        "schema-alt-main",
      ),
    );
    await userEvent.click(within(failed).getByRole("button", { name: /Re-run schema_extraction/ }));

    await waitFor(() =>
      expect(runBodies.schema_extraction).toMatchObject({
        implementation_id: "schema_alt",
        configuration_ref: "schema-alt-main",
        documents: [XR_TEXT],
      }),
    );
    // Only the schema run was started again.
    expect(runBodies.individual_extraction).toBe(individualBody);
  });

  it("re-runs a failed individual run into the dataset chosen since", async () => {
    mockRuns("fail");
    server.use(
      http.get("*/api/datasets", () =>
        HttpResponse.json([
          { id: "ds-a", taxonomy_id: "tax-dr", identifier: "alpha" },
          { id: "ds-b", taxonomy_id: "tax-dr", identifier: "beta" },
        ]),
      ),
    );
    await renderPage();
    const dataset = await screen.findByTestId("extraction-review-dataset");
    await userEvent.selectOptions(dataset, "ds-a");
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    await userEvent.click(screen.getByRole("tab", { name: "Individual extraction" }));
    const failed = await screen.findByTestId("extraction-review-individual-failed");
    expect(runBodies.individual_extraction).toMatchObject({ dataset_id: "ds-a" });

    await userEvent.selectOptions(dataset, "ds-b");
    await userEvent.click(
      within(failed).getByRole("button", { name: /Re-run individual_extraction/ }),
    );
    await waitFor(() =>
      expect(runBodies.individual_extraction).toMatchObject({ dataset_id: "ds-b", text: XR_TEXT }),
    );
  });

  it("starts no run until the taxonomy's datasets are read", async () => {
    mockRuns("ok");
    let serve: () => void = () => {};
    server.use(
      http.get(
        "*/api/datasets",
        () =>
          new Promise<Response>((resolve) => {
            serve = () =>
              resolve(
                HttpResponse.json([
                  { id: "ds-a", taxonomy_id: "tax-dr", identifier: "alpha" },
                  { id: "ds-b", taxonomy_id: "tax-dr", identifier: "beta" },
                ]),
              );
          }),
      ),
    );
    await renderPage();
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);
    // Whether a dataset must be named is not known yet: Run waits.
    const run = screen.getByTestId("extraction-review-run");
    expect(run).toBeDisabled();
    expect(run).toHaveAttribute("aria-busy", "true");
    expect(runBodies).toEqual({});

    serve();
    // Several datasets: Run is free again and asks for one.
    expect(await screen.findByTestId("extraction-review-dataset")).toBeInTheDocument();
    expect(run).toBeEnabled();
    await userEvent.click(run);
    expect(
      screen.getByText("Select a dataset", { selector: "[id$='-error']" }),
    ).toBeInTheDocument();
    expect(runBodies).toEqual({});
  });

  it("starts no run when the taxonomy's datasets could not be read, and says why", async () => {
    mockRuns("ok");
    server.use(
      http.get("*/api/datasets", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    await renderPage();
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);

    const dataset = await screen.findByTestId("extraction-review-dataset");
    expect(dataset).toBeDisabled();
    expect(dataset).toHaveClass("select--error");
    expect(screen.getByText(/^Could not load the datasets/)).toHaveAttribute(
      "id",
      "extraction-review-dataset-error",
    );
    expect(screen.getByTestId("extraction-review-run")).toBeDisabled();
    expect(runBodies).toEqual({});
  });

  it("warns that highlights are stale once the paragraph changes after a run", async () => {
    mockRuns("ok");
    await renderPage();
    const textarea = screen.getByTestId("extraction-review-text");
    await userEvent.type(textarea, XR_TEXT);
    expect(screen.queryByTestId("extraction-review-stale")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    await screen.findByTestId("extraction-review-schema-candidates");
    await userEvent.type(textarea, " More.");
    expect(screen.getByTestId("extraction-review-stale")).toHaveClass("form-callout--warn");
  });

  it("opens an existing run passed by id in its tab without starting a run", async () => {
    mockRuns("ok");
    let runPosts = 0;
    server.use(
      http.post("*/api/pipelines/:type/run", () => {
        runPosts += 1;
        return HttpResponse.json(makeRun());
      }),
      http.get("*/api/pipelines/runs/run-i", () =>
        HttpResponse.json(
          makeRun({
            id: "run-i",
            pipeline_type: "individual_extraction",
            input_summary: { taxonomy_id: "tax-dr", taxonomy_name: "Documentation Robotics" },
          }),
        ),
      ),
    );
    renderWithProviders(<ExtractionReviewPage initialRunId="run-i" />);

    expect(await screen.findByTestId("extraction-review-triples")).toBeInTheDocument();
    const tabs = screen.getByTestId("extraction-review-tabs");
    expect(within(tabs).getByRole("tab", { name: /Individual extraction/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("extraction-review-opened-run")).toHaveClass("form-callout--info");
    expect(screen.getByTestId("extraction-review-opened-run")).toHaveTextContent("run-i");
    expect(screen.getByTestId("extraction-review-schema-idle")).toBeInTheDocument();
    expect(runPosts).toBe(0);
    // A run without stored text cannot locate its provenance.
    expect(screen.getByTestId("extraction-review-opened-run")).toHaveTextContent(
      "provenance highlights are unavailable",
    );
    expect(screen.queryByTestId("extraction-review-span")).not.toBeInTheDocument();
  });

  it("shows the stored paragraph and its highlights when reopening a run", async () => {
    mockRuns("ok");
    server.use(
      http.get("*/api/pipelines/runs/run-i", () =>
        HttpResponse.json(
          makeRun({
            id: "run-i",
            pipeline_type: "individual_extraction",
            input_summary: { taxonomy_id: "tax-dr", taxonomy_name: "Documentation Robotics" },
            source_text: XR_TEXT,
          }),
        ),
      ),
    );
    renderWithProviders(<ExtractionReviewPage initialRunId="run-i" />);

    const source = await screen.findByTestId("extraction-review-individual-source");
    const marks = within(source).getAllByTestId("extraction-review-span");
    expect(marks.length).toBeGreaterThan(0);
    expect(marks[0]).toHaveClass("xr-span");
    expect(marks[0]).toHaveAttribute("role", "button");
    expect(source).toHaveTextContent(XR_TEXT);
    expect(screen.getByTestId("extraction-review-text")).toHaveValue(XR_TEXT);
    expect(screen.getByTestId("extraction-review-opened-run")).toHaveTextContent(
      "Highlights show the paragraph the run read.",
    );
    expect(screen.queryByTestId("extraction-review-stale")).not.toBeInTheDocument();

    // Editing the paragraph keeps the run's highlights and flags them as stale.
    await userEvent.type(screen.getByTestId("extraction-review-text"), " More.");
    expect(screen.getByTestId("extraction-review-stale")).toHaveClass("form-callout--warn");
  });
});

describe("ExtractionReviewPage — example library", () => {
  async function pickExample(id: string) {
    await userEvent.selectOptions(await screen.findByTestId("extraction-review-example"), id);
  }

  it("fills the paragraph from an example, follows its taxonomy hint and describes it", async () => {
    await renderPage();
    await pickExample("glossary-note");

    expect(screen.getByTestId("extraction-review-text")).toHaveValue(
      "A glossary entry defines one term.",
    );
    expect(screen.getByTestId("extraction-review-taxonomy")).toHaveValue("tax-other");
    expect(screen.getByTestId("extraction-review-example-description")).toHaveTextContent(
      "Exercises plain glossary prose.",
    );
  });

  it("keeps the taxonomy when the example has no hint", async () => {
    await renderPage();
    await pickExample("no-hint");
    expect(screen.getByTestId("extraction-review-taxonomy")).toHaveValue("tax-dr");
  });

  it("records the example on both runs while the text is unedited", async () => {
    mockRuns("ok");
    await renderPage();
    await pickExample("glossary-note");
    await userEvent.click(screen.getByTestId("extraction-review-run"));

    await screen.findByTestId("extraction-review-schema-candidates");
    expect(runBodies.schema_extraction).toMatchObject({ example_id: "glossary-note" });
    expect(runBodies.individual_extraction).toMatchObject({ example_id: "glossary-note" });
  });

  it("treats an edited example as free text", async () => {
    mockRuns("ok");
    await renderPage();
    await pickExample("glossary-note");
    await userEvent.type(screen.getByTestId("extraction-review-text"), " More.");

    expect(screen.getByTestId("extraction-review-example-description")).toHaveTextContent(
      "Edited: runs of this text are not linked to the example.",
    );
    expect(screen.queryByTestId("extraction-review-example-runs")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    await screen.findByTestId("extraction-review-schema-candidates");
    expect(runBodies.schema_extraction).not.toHaveProperty("example_id");
  });

  it("lists earlier extraction runs of the example and opens one", async () => {
    const onOpenRun = vi.fn();
    renderWithProviders(<ExtractionReviewPage onOpenRun={onOpenRun} />);
    await selectionLoaded();
    await pickExample("glossary-note");

    const runs = await screen.findByTestId("extraction-review-example-runs");
    await within(runs).findByText("schema-extraction-default v1");
    expect(runListQueries.some((q) => q.get("example_id") === "glossary-note")).toBe(true);
    // Only extraction runs are listed.
    expect(within(runs).queryByText(/schema_relationship_reflection/)).not.toBeInTheDocument();

    await userEvent.click(within(runs).getByText("schema-extraction-default v1"));
    expect(onOpenRun).toHaveBeenCalledWith("run-old-s");
  });
});
