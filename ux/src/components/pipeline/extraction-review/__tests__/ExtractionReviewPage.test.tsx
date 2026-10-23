import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { renderWithProviders } from "@/test/test-utils";
import { ExtractionReviewPage } from "../ExtractionReviewPage";
import { SCHEMA_CANDIDATES, TRIPLES, RECOGNITION, XR_TEXT, makeRun } from "./fixtures";

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

beforeEach(() => {
  runBodies = {};
  server.use(
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
    await waitFor(() =>
      expect(screen.getByTestId("extraction-review-scheme")).toHaveValue("scheme-app"),
    );
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
  });

  it("starts both runs on the same text and reviews them in place", async () => {
    mockRuns("ok");
    await renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("extraction-review-scheme")).toHaveValue("scheme-app"),
    );
    await userEvent.type(screen.getByTestId("extraction-review-text"), XR_TEXT);
    await userEvent.click(screen.getByTestId("extraction-review-run"));

    expect(await screen.findByTestId("extraction-review-schema-candidates")).toBeInTheDocument();
    expect(runBodies.schema_extraction).toMatchObject({
      implementation_id: "default",
      configuration_ref: "schema-extraction-default",
      documents: [XR_TEXT],
      scope: "tax-dr",
      concept_scheme_id: "scheme-app",
      model: "gemini-flash",
    });
    expect(runBodies.individual_extraction).toMatchObject({
      configuration_ref: "extraction-openrouter-default",
      text: XR_TEXT,
      ontology_id: "tax-dr",
      model: "gemini-flash",
    });

    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-sc-0-yes"));
    await userEvent.click(screen.getByRole("tab", { name: "Individual extraction" }));
    expect(await screen.findByTestId("extraction-review-triples")).toBeInTheDocument();
    expect(screen.getByRole("tabpanel", { name: "Individual extraction" })).toBeVisible();
    expect(
      screen.getByTestId("extraction-review-schema").closest("[role=tabpanel]"),
    ).toHaveAttribute("hidden");

    // Decisions survive switching tabs.
    await userEvent.click(screen.getByRole("tab", { name: "Schema extraction" }));
    expect(screen.getByTestId("extraction-review-schema-decision-sc-0-yes")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("keeps one tab reviewable when the other run fails", async () => {
    mockRuns("fail");
    await renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("extraction-review-scheme")).toHaveValue("scheme-app"),
    );
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
    await waitFor(() =>
      expect(screen.getByTestId("extraction-review-scheme")).toHaveValue("scheme-app"),
    );
    const textarea = screen.getByTestId("extraction-review-text");
    await userEvent.type(textarea, XR_TEXT);
    expect(screen.queryByTestId("extraction-review-stale")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("extraction-review-run"));
    await screen.findByTestId("extraction-review-schema-candidates");
    await userEvent.type(textarea, " More.");
    expect(screen.getByTestId("extraction-review-stale")).toHaveClass("form-callout--warn");
  });
});
