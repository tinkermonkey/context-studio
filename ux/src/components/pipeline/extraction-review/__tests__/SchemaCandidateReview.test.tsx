import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import type { ReactNode } from "react";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { renderWithProviders } from "@/test/test-utils";
import type { SchemaExtractionCandidate } from "@/api/services/pipeline";
import { SchemaCandidateReview } from "../SchemaCandidateReview";
import { SCHEMA_CANDIDATES, SCHEMA_RECOGNITION, SCOPE, XR_TEXT, makeRun } from "./fixtures";

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

let previewBody: unknown = null;

const APP_SCHEME = { id: "scheme-app", identifier: "application", title: "Application Layer" };
const BIZ_SCHEME = { id: "scheme-biz", identifier: "business", title: "Business Layer" };

function renderReady(
  recognition: () => Response = () => HttpResponse.json(SCHEMA_RECOGNITION),
  schemes: Array<typeof APP_SCHEME> | (() => Response) = [APP_SCHEME],
  candidates: SchemaExtractionCandidate[] = SCHEMA_CANDIDATES,
) {
  previewBody = null;
  server.use(
    http.get("*/api/schemes", () =>
      typeof schemes === "function"
        ? schemes()
        : HttpResponse.json({ items: schemes, total: schemes.length, limit: 100, offset: 0 }),
    ),
    http.get("*/api/pipelines/runs/run-s/schema-extraction-candidates", () =>
      HttpResponse.json(candidates),
    ),
    http.post("*/api/pipelines/runs/run-s/recognition-preview", async ({ request }) => {
      previewBody = await request.json();
      return recognition();
    }),
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
    expect(within(panel).getAllByText("Policyholder")[0]).toHaveClass("xr-strong");
    expect(within(panel).queryByText("submits")).not.toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-schema-run-meta")).toHaveTextContent("run-s");
    expect(screen.getByTestId("extraction-review-schema-run-meta")).toHaveTextContent(
      "schema_extraction · default · schema-extraction-default v1 · 11.0s",
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
    expect(bar).toHaveTextContent("4 pending");
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
    await screen.findByTestId("extraction-review-schema-existing-class-0");
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
    // Policyholder already exists, so nothing new needs a concept scheme.
    expect(applyUrl!.searchParams.get("concept_scheme_id")).toBeNull();

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

describe("SchemaCandidateReview — existing-match hints", () => {
  it("requests the preview for the whole taxonomy and labels each class", async () => {
    await renderReady();
    const exists = await screen.findByTestId("extraction-review-schema-existing-class-0");
    expect(previewBody).toEqual({ confidence_threshold: 0, taxonomy_id: "tax-dr" });
    expect(screen.getByTestId("extraction-review-schema-candidates")).toHaveTextContent(
      "close to a class already in Documentation Robotics · dr_spec",
    );

    expect(within(exists).getByText("exists")).toHaveClass("chip--emerald");
    expect(exists).toHaveTextContent("Policyholder");
    expect(exists).toHaveTextContent("reused on apply");

    const similar = screen.getByTestId("extraction-review-schema-existing-class-1");
    expect(within(similar).getByText("similar")).toHaveClass("chip--cyan");
    expect(similar).toHaveTextContent("Claim");
    expect(similar).toHaveTextContent("93% · created as new");

    const fresh = screen.getByTestId("extraction-review-schema-existing-class-2");
    expect(within(fresh).getByText("new")).toHaveClass("chip--amber");
  });

  it("shows the existing match in the inspector for the selected candidate", async () => {
    const panel = await renderReady();
    await screen.findByTestId("extraction-review-schema-existing-class-0");
    expect(screen.getByTestId("extraction-review-schema-inspector-match")).toHaveTextContent(
      "exists · reused on apply",
    );
    await userEvent.click(within(panel).getByText("Insurance Claim"));
    const match = screen.getByTestId("extraction-review-schema-inspector-match");
    expect(match).toHaveTextContent("similar existing class · created as new");
    expect(match).toHaveTextContent("cls_claim");
    expect(within(match).getByText("vector")).toHaveClass("chip--cyan");
  });

  it("labels properties and connections that do not exist as new", async () => {
    const panel = await renderReady();
    await screen.findByTestId("extraction-review-schema-existing-class-0");
    await userEvent.click(within(panel).getByRole("radio", { name: /Connections/ }));
    const cell = screen.getByTestId("extraction-review-schema-existing-connection-0");
    expect(within(cell).getByText("new")).toHaveClass("chip--amber");
  });

  it("does not warn about a connection whose unaccepted endpoint class already exists", async () => {
    await renderReady();
    await screen.findByTestId("extraction-review-schema-existing-class-0");
    // Policyholder (exists) is left pending; Insurance Claim is accepted.
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-1-yes"));
    await screen.findByText("Application Layer · application");
    const panel = screen.getByTestId("extraction-review-schema-candidates");
    await userEvent.click(within(panel).getByRole("radio", { name: /Connections/ }));
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-connection-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    expect(screen.getByTestId("extraction-review-schema-confirm")).toBeInTheDocument();
    expect(screen.queryByTestId("extraction-review-schema-orphan-warning")).not.toBeInTheDocument();
  });

  it("counts accepted candidates that reuse an existing entity in the confirm dialog", async () => {
    await renderReady();
    await screen.findByTestId("extraction-review-schema-existing-class-0");
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-1-yes"));
    await screen.findByText("Application Layer · application");
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    const confirm = screen.getByTestId("extraction-review-schema-confirm");
    expect(within(confirm).getByText("1 reuse existing")).toHaveClass("chip--emerald");
  });

  it("keeps the review usable when the preview fails", async () => {
    const panel = await renderReady(() => HttpResponse.json({ detail: "boom" }, { status: 500 }));
    expect(await within(panel).findByText(/Existing-match preview failed/)).toBeInTheDocument();
    expect(within(panel).getByText("Policyholder")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("extraction-review-schema-existing-class-0")).getByText("—"),
    ).toBeInTheDocument();
  });
});

describe("SchemaCandidateReview — where new classes go", () => {
  function captureApply() {
    const seen: { url: URL | null } = { url: null };
    server.use(
      http.post("*/api/pipelines/runs/run-s/apply", ({ request }) => {
        seen.url = new URL(request.url);
        return HttpResponse.json({
          run_id: "run-s",
          pipeline_type: "schema_extraction",
          classes_created: 1,
          applied_candidate_ids: ["class-2"],
          skipped_candidate_ids: [],
          skip_reasons: {},
          merged_mentions: [],
        });
      }),
    );
    return seen;
  }

  const bar = () => screen.getByTestId("extraction-review-schema-apply-bar");

  it("asks nothing when every accepted class already exists", async () => {
    await renderReady(undefined, [APP_SCHEME, BIZ_SCHEME]);
    await screen.findByTestId("extraction-review-schema-existing-class-0");
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-0-yes"));
    expect(bar()).not.toHaveTextContent("new classes go to");
    expect(screen.getByTestId("extraction-review-schema-apply")).toBeEnabled();
  });

  it("names the only concept scheme without asking", async () => {
    const seen = captureApply();
    await renderReady();
    await screen.findByTestId("extraction-review-schema-existing-class-2");
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-2-yes"));
    expect(await within(bar()).findByText("Application Layer · application")).toBeInTheDocument();
    expect(bar()).toHaveTextContent("new classes go to");

    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    await userEvent.click(screen.getByRole("button", { name: "Apply 1 accepted" }));
    await screen.findByTestId("extraction-review-schema-revert");
    expect(seen.url!.searchParams.get("concept_scheme_id")).toBe("scheme-app");
  });

  it("blocks apply until the reviewer chooses among several schemes", async () => {
    const seen = captureApply();
    await renderReady(undefined, [APP_SCHEME, BIZ_SCHEME]);
    await screen.findByTestId("extraction-review-schema-existing-class-2");
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-2-yes"));

    const picker = await screen.findByTestId("extraction-review-schema-target-scheme");
    expect(screen.getByTestId("extraction-review-schema-apply")).toBeDisabled();
    const hint = screen.getByTestId("extraction-review-schema-target-hint");
    expect(hint).toHaveAttribute("role", "status");
    expect(hint).toHaveTextContent("Choose where the 1 new class goes.");

    await userEvent.selectOptions(picker, "scheme-biz");
    expect(screen.queryByText("Choose where the 1 new class goes.")).not.toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-schema-apply")).toBeEnabled();

    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    await userEvent.click(screen.getByRole("button", { name: "Apply 1 accepted" }));
    await screen.findByTestId("extraction-review-schema-revert");
    expect(seen.url!.searchParams.get("concept_scheme_id")).toBe("scheme-biz");
  });

  it("shows a failed concept scheme load and keeps apply blocked", async () => {
    await renderReady(undefined, () => HttpResponse.json({ detail: "boom" }, { status: 500 }));
    await screen.findByTestId("extraction-review-schema-existing-class-2");
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-2-yes"));
    expect(await within(bar()).findByText(/Could not load concept schemes/)).toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-schema-apply")).toBeDisabled();
  });

  it("explains a taxonomy without concept schemes and blocks apply", async () => {
    await renderReady(undefined, []);
    await screen.findByTestId("extraction-review-schema-existing-class-2");
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-2-yes"));
    const message = await screen.findByTestId("extraction-review-schema-no-schemes");
    expect(message).toHaveAttribute("role", "alert");
    expect(screen.getByTestId("extraction-review-schema-apply")).toBeDisabled();
  });
});

describe("SchemaCandidateReview — class parents and attributes", () => {
  const attributesTab = (panel: HTMLElement) =>
    within(panel).getByRole("radio", { name: /Attributes/ });

  it("shows a class candidate's proposed parent in the table and inspector", async () => {
    const panel = await renderReady();
    expect(screen.getByTestId("extraction-review-schema-parent-class-1")).toHaveTextContent(
      "under Business Object",
    );
    expect(screen.getByTestId("extraction-review-schema-parent-class-1")).toHaveClass(
      "xr-mono-muted",
    );
    expect(screen.queryByTestId("extraction-review-schema-parent-class-0")).not.toBeInTheDocument();

    await userEvent.click(within(panel).getByText("Insurance Claim"));
    const inspector = screen.getByTestId("extraction-review-schema-inspector");
    expect(inspector).toHaveTextContent("parent");
    expect(inspector).toHaveTextContent("Business Object");
  });

  it("lists attribute candidates with their class, value type, unit and confidence", async () => {
    const panel = await renderReady();
    expect(screen.getByText("ATTRIBUTES").closest(".stat-tile")).toHaveClass("stat-tile--neutral");
    const tab = attributesTab(panel);
    expect(tab).toHaveTextContent("Attributes · 1");
    expect(tab).toHaveAttribute("aria-checked", "false");
    expect(within(panel).queryByText("Claim Amount")).not.toBeInTheDocument();

    await userEvent.click(tab);
    expect(attributesTab(panel)).toHaveAttribute("aria-checked", "true");
    const row = within(panel).getByText("Claim Amount").closest("tr")!;
    expect(within(row).getByText("Claim Amount")).toHaveClass("xr-strong");
    expect(
      within(row).getByTestId("extraction-review-schema-of-class-attribute-0"),
    ).toHaveTextContent("Insurance Claim");
    expect(within(row).getByText("number")).toHaveClass("chip");
    expect(within(row).getByText("USD")).toHaveClass("xr-mono");
    expect(within(row).getByText("77%")).toBeInTheDocument();
    expect(
      within(row).getByTestId("extraction-review-schema-decision-attribute-0-yes"),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("shows the selected attribute in the inspector without an existing-match section", async () => {
    const panel = await renderReady();
    await userEvent.click(attributesTab(panel));
    await userEvent.click(within(panel).getByText("Claim Amount"));
    const inspector = screen.getByTestId("extraction-review-schema-inspector");
    expect(inspector).toHaveTextContent("SCHEMA ATTRIBUTE CANDIDATE");
    expect(inspector).toHaveTextContent("of_class");
    expect(inspector).toHaveTextContent("USD");
    expect(
      screen.queryByTestId("extraction-review-schema-inspector-match"),
    ).not.toBeInTheDocument();
  });

  it("marks an attribute without a class as skipped on apply", async () => {
    const orphan: SchemaExtractionCandidate = {
      candidate_type: "schema_attribute",
      candidate_id: "attribute-0",
      label: "Resolution Window",
      confidence: 0.6,
      of_class: null,
      value_type: "string",
      unit: null,
      provenance: [],
    };
    const panel = await renderReady(undefined, undefined, [orphan]);
    // The only candidate type opens by default.
    expect(attributesTab(panel)).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("extraction-review-schema-of-class-attribute-0")).toHaveTextContent(
      "no class · skipped on apply",
    );
  });

  it("sends accepted attributes in the apply selection and reports them created", async () => {
    let applyBody: unknown = null;
    server.use(
      http.post("*/api/pipelines/runs/run-s/apply", async ({ request }) => {
        applyBody = await request.json();
        return HttpResponse.json({
          run_id: "run-s",
          pipeline_type: "schema_extraction",
          classes_created: 1,
          properties_created: 0,
          attributes_created: 1,
          individuals_created: 0,
          relationships_created: 0,
          applied_candidate_ids: ["class-1", "attribute-0"],
          skipped_candidate_ids: [],
          skip_reasons: {},
          merged_mentions: [],
        });
      }),
    );
    const panel = await renderReady();
    await screen.findByTestId("extraction-review-schema-existing-class-1");
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-class-1-yes"));
    await userEvent.click(attributesTab(panel));
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-attribute-0-yes"));
    await screen.findByText("Application Layer · application");
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    expect(screen.queryByTestId("extraction-review-schema-orphan-warning")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Apply 2 accepted" }));

    const created = await screen.findByTestId("extraction-review-apply-result-created");
    expect(applyBody).toEqual({ accepted_candidate_ids: ["class-1", "attribute-0"] });
    expect(within(created).getByText("1 attributes created")).toHaveClass("chip--neutral");
  });

  it("warns when an accepted attribute's class is a proposed class that is not accepted", async () => {
    const panel = await renderReady();
    await userEvent.click(attributesTab(panel));
    await userEvent.click(screen.getByTestId("extraction-review-schema-decision-attribute-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-schema-apply"));
    const warning = screen.getByTestId("extraction-review-schema-orphan-warning");
    expect(warning).toHaveClass("form-callout--warn");
    expect(warning).toHaveTextContent("1 accepted candidate points at a proposed class");
    expect(warning).toHaveTextContent("Claim Amount");
  });
});
