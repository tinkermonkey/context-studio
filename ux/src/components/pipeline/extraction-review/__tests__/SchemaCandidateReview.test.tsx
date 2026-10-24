import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import type { ReactNode } from "react";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { renderWithProviders } from "@/test/test-utils";
import { SchemaCandidateReview } from "../SchemaCandidateReview";
import { SCHEMA_CANDIDATES, SCOPE, XR_TEXT, makeRun } from "./fixtures";

const { toastSpy } = vi.hoisted(() => ({ toastSpy: vi.fn() }));
vi.mock("@/components/ui/Toast", () => ({
  ToastProvider: ({ children }: { children: ReactNode }) => children,
  useToasts: () => ({ toast: toastSpy, toasts: [], dismiss: vi.fn() }),
}));

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const completed = { status: "completed" as const, run: makeRun() };

function renderReady() {
  server.use(
    http.get("*/api/pipelines/runs/run-s/schema-extraction-candidates", () =>
      HttpResponse.json(SCHEMA_CANDIDATES),
    ),
  );
  renderWithProviders(
    <SchemaCandidateReview slot={completed} text={XR_TEXT} scope={SCOPE} onRetry={() => {}} />,
  );
  return screen.findByTestId("extraction-review-schema-candidates");
}

describe("SchemaCandidateReview — run states", () => {
  it.each([
    [{ status: "idle" as const }, "extraction-review-schema-idle"],
    [{ status: "running" as const }, "extraction-review-schema-running"],
    [
      { status: "failed" as const, run: makeRun({ status: "FAILED" }), error: "LLM timeout" },
      "extraction-review-schema-failed",
    ],
  ])("renders the %o state", (slot, testId) => {
    renderWithProviders(
      <SchemaCandidateReview slot={slot} text={XR_TEXT} scope={SCOPE} onRetry={() => {}} />,
    );
    expect(screen.getByTestId("extraction-review-schema")).toBeInTheDocument();
    expect(screen.getByTestId(testId)).toBeInTheDocument();
  });

  it("shows the failure reason as an error callout with a retry action", async () => {
    let retried = false;
    renderWithProviders(
      <SchemaCandidateReview
        slot={{ status: "failed", error: "LLM timeout" }}
        text={XR_TEXT}
        scope={SCOPE}
        onRetry={() => (retried = true)}
      />,
    );
    const failed = screen.getByTestId("extraction-review-schema-failed");
    const callout = within(failed).getByRole("alert");
    expect(callout).toHaveClass("form-callout--error");
    expect(callout).toHaveTextContent("LLM timeout");
    await userEvent.click(screen.getByTestId("extraction-review-schema-retry"));
    expect(retried).toBe(true);
  });

  it("renders the empty state when a completed run has no candidates", async () => {
    server.use(
      http.get("*/api/pipelines/runs/run-s/schema-extraction-candidates", () =>
        HttpResponse.json([]),
      ),
    );
    renderWithProviders(
      <SchemaCandidateReview slot={completed} text={XR_TEXT} scope={SCOPE} onRetry={() => {}} />,
    );
    expect(await screen.findByTestId("extraction-review-schema-empty")).toBeInTheDocument();
  });
});

describe("SchemaCandidateReview — review", () => {
  it("lists candidates of the active type with stat tiles and run meta", async () => {
    const panel = await renderReady();
    expect(within(panel).getByText("Policyholder")).toBeInTheDocument();
    expect(within(panel).queryByText("submits")).not.toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-schema-run-meta")).toHaveTextContent("run-s");
    expect(screen.getByTestId("extraction-review-schema-run-meta")).toHaveTextContent(
      "schema-extraction-default v1 · 11.0s",
    );
    expect(screen.getByText("CLASSES").closest(".stat-tile")).toHaveClass("stat-tile--violet");
  });

  it("uses SchemaPageLayout with the source text and inspector for the selected row", async () => {
    await renderReady();
    expect(screen.getByTestId("schema-page-layout")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-schema-source")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-schema-inspector")).toHaveTextContent(
      "Policyholder",
    );
  });

  it("selects a candidate from its source span, switching the type filter", async () => {
    const panel = await renderReady();
    const submitSpan = screen
      .getAllByTestId("extraction-review-span")
      .find((m) => m.getAttribute("data-span-keys")?.split(" ").includes("property-0"));
    expect(submitSpan).toBeDefined();
    await userEvent.click(submitSpan!);
    expect(screen.getByTestId("extraction-review-schema-inspector")).toHaveTextContent("submits");
    expect(within(panel).getByText("submits")).toBeInTheDocument();
    expect(submitSpan).toHaveClass("xr-span--active");
  });

  it("shows unlocated provenance in the inspector", async () => {
    const panel = await renderReady();
    await userEvent.click(within(panel).getByText("Turnaround SLA"));
    const inspector = screen.getByTestId("extraction-review-schema-inspector");
    expect(within(inspector).getByTestId("extraction-review-unlocated")).toHaveClass("chip--amber");
  });

  it("accepts and rejects candidates and reflects counts in the apply bar", async () => {
    await renderReady();
    const apply = screen.getByTestId("extraction-review-schema-apply");
    expect(apply).toBeDisabled();
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-1-no"));
    const bar = screen.getByTestId("extraction-review-schema-apply-bar");
    expect(bar).toHaveTextContent("1 accepted");
    expect(bar).toHaveTextContent("1 rejected");
    expect(bar).toHaveTextContent("3 pending");
    expect(screen.getByTestId("extraction-review-schema-decision-class-0-yes")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(apply).toBeEnabled();
  });

  it("warns when an accepted connection points at a proposed class that is not accepted", async () => {
    await renderReady();
    const panel = screen.getByTestId("extraction-review-schema-candidates");
    await userEvent.click(within(panel).getByRole("radio", { name: /Connections/ }));
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-connection-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    const warning = screen.getByTestId("extraction-review-schema-orphan-warning");
    expect(warning).toHaveClass("form-callout--warn");
    expect(warning).toHaveTextContent("Policyholder → submits → Insurance Claim");
  });

  it("applies the explicit selection, shows what was created and skipped, then reverts", async () => {
    let applyUrl: URL | null = null;
    let applyBody: unknown = null;
    let reverted = false;
    server.use(
      http.post("*/api/pipelines/runs/run-s/apply", async ({ request }) => {
        applyUrl = new URL(request.url);
        applyBody = await request.json();
        return HttpResponse.json({
          run_id: "run-s",
          pipeline_type: "schema_extraction",
          classes_created: 1,
          properties_created: 0,
          individuals_created: 0,
          relationships_created: 0,
          applied_candidate_ids: ["class-0"],
          skipped_candidate_ids: ["class-1", "class-2", "property-0", "connection-0"],
          skip_reasons: {
            "class-1": "not_selected",
            "class-2": "not_selected",
            "property-0": "not_selected",
            "connection-0": "unresolved_endpoint",
          },
          merged_mentions: [],
        });
      }),
      http.post("*/api/pipelines/runs/run-s/revert", () => {
        reverted = true;
        return HttpResponse.json({ run_id: "run-s", events_reverted: 1 });
      }),
    );
    await renderReady();
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-1-no"));
    const panel = screen.getByTestId("extraction-review-schema-candidates");
    await userEvent.click(within(panel).getByRole("radio", { name: /Connections/ }));
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-connection-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    expect(screen.getByTestId("extraction-review-schema-confirm")).toHaveTextContent(
      "Rejected and pending candidates are skipped",
    );
    await userEvent.click(screen.getByRole("button", { name: "Apply 2 accepted" }));

    const revert = await screen.findByTestId("extraction-review-schema-revert");
    expect(applyBody).toEqual({ accepted_candidate_ids: ["class-0", "connection-0"] });
    expect(applyUrl!.searchParams.get("confidence_threshold")).toBeNull();
    expect(applyUrl!.searchParams.get("taxonomy_id")).toBe("tax-dr");
    expect(applyUrl!.searchParams.get("concept_scheme_id")).toBe("scheme-app");

    expect(screen.getByTestId("extraction-review-apply-result-created")).toHaveTextContent(
      "1 classes created",
    );
    // Only accepted-but-skipped candidates are surfaced, with the server's reason;
    // unselected ones (skip reason not_selected) are not.
    const skipped = screen.getByTestId("extraction-review-apply-result-skipped");
    expect(
      within(skipped).getByText(
        "Policyholder → submits → Insurance Claim — endpoint not accepted or in the graph",
      ),
    ).toHaveClass("chip--amber");
    expect(within(skipped).getAllByText(/—/)).toHaveLength(1);
    expect(within(skipped).queryByText(/not selected/)).not.toBeInTheDocument();

    await userEvent.click(revert);
    await waitFor(() => expect(reverted).toBe(true));
    expect(await screen.findByTestId("extraction-review-schema-apply")).toBeInTheDocument();
    expect(screen.queryByTestId("extraction-review-apply-result-created")).not.toBeInTheDocument();
  });

  it("reports accepted candidates that already existed and will survive revert", async () => {
    server.use(
      http.post("*/api/pipelines/runs/run-s/apply", () =>
        HttpResponse.json({
          run_id: "run-s",
          pipeline_type: "schema_extraction",
          classes_created: 0,
          properties_created: 0,
          individuals_created: 0,
          relationships_created: 0,
          applied_candidate_ids: ["class-0"],
          skipped_candidate_ids: [],
          existing_candidate_ids: ["class-0"],
          merged_mentions: [],
        }),
      ),
    );
    await renderReady();
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    await userEvent.click(screen.getByRole("button", { name: "Apply 1 accepted" }));
    const created = await screen.findByTestId("extraction-review-apply-result-created");
    const chip = within(created).getByText("1 already existed (revert will not remove)");
    expect(chip).toHaveClass("chip--neutral");
  });

  it("omits the already-existed note when nothing pre-existed", async () => {
    server.use(
      http.post("*/api/pipelines/runs/run-s/apply", () =>
        HttpResponse.json({
          run_id: "run-s",
          pipeline_type: "schema_extraction",
          classes_created: 1,
          properties_created: 0,
          individuals_created: 0,
          relationships_created: 0,
          applied_candidate_ids: ["class-0"],
          skipped_candidate_ids: [],
          existing_candidate_ids: [],
          merged_mentions: [],
        }),
      ),
    );
    await renderReady();
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    await userEvent.click(screen.getByRole("button", { name: "Apply 1 accepted" }));
    const created = await screen.findByTestId("extraction-review-apply-result-created");
    expect(within(created).queryByText(/already existed/)).not.toBeInTheDocument();
  });

  it("warns when revert finds no recorded changes to undo", async () => {
    server.use(
      http.post("*/api/pipelines/runs/run-s/apply", () =>
        HttpResponse.json({
          run_id: "run-s",
          pipeline_type: "schema_extraction",
          classes_created: 0,
          properties_created: 0,
          individuals_created: 0,
          relationships_created: 0,
          applied_candidate_ids: ["class-0"],
          skipped_candidate_ids: [],
          merged_mentions: [],
        }),
      ),
      http.post("*/api/pipelines/runs/run-s/revert", () =>
        HttpResponse.json({ run_id: "run-s", events_reverted: 0 }),
      ),
    );
    await renderReady();
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    await userEvent.click(screen.getByRole("button", { name: "Apply 1 accepted" }));
    expect(await screen.findByTestId("extraction-review-apply-result-created")).toHaveTextContent(
      "1 of 1 accepted applied",
    );
    await userEvent.click(screen.getByTestId("extraction-review-schema-revert"));
    await waitFor(() =>
      expect(toastSpy).toHaveBeenLastCalledWith(
        "warning",
        "Nothing to revert",
        expect.stringContaining("run-s"),
      ),
    );
  });
});
