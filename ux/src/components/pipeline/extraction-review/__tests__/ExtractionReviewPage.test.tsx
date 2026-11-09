import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
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
const config = (type: string, ref: string, model: string, provider = "openrouter") => ({
  id: `${type}:default:${ref}`,
  config_ref: ref,
  pipeline_type: type,
  implementation_id: "default",
  name: ref,
  provider,
  model,
  enabled: true,
  version: 1,
});

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
      HttpResponse.json([{ id: "default", pipeline_type: params.type }]),
    ),
    http.get("*/api/pipelines/types/:type/implementations/default/configurations", ({ params }) =>
      HttpResponse.json(
        params.type === "schema_extraction"
          ? [config("schema_extraction", "schema-extraction-default", "gemini-flash")]
          : [
              config("individual_extraction", "extraction-default", "opus", "anthropic"),
              config("individual_extraction", "extraction-openrouter-default", "gemini-flash"),
            ],
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

async function renderPage() {
  renderWithProviders(<ExtractionReviewPage />);
  await screen.findByTestId("extraction-review-config-refs");
}

describe("ExtractionReviewPage", () => {
  it("renders the input panel, defaults the scope to dr_spec and starts idle", async () => {
    await renderPage();
    expect(screen.getByTestId("extraction-review-page")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-taxonomy")).toHaveValue("tax-dr");
    // Individual config is paired with the schema config by provider + model.
    expect(screen.getByTestId("extraction-review-config-refs")).toHaveTextContent(
      "schema-extraction-default v1 · extraction-openrouter-default v1",
    );
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
      implementation_id: "default",
      configuration_ref: "schema-extraction-default",
      documents: [XR_TEXT],
      scope: "tax-dr",
      model: "gemini-flash",
    });
    expect(runBodies.individual_extraction).toMatchObject({
      configuration_ref: "extraction-openrouter-default",
      text: XR_TEXT,
      ontology_id: "tax-dr",
      model: "gemini-flash",
    });

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
    await screen.findByTestId("extraction-review-config-refs");
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
