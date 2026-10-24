import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { renderWithProviders } from "@/test/test-utils";
import { IndividualCandidateReview } from "../IndividualCandidateReview";
import { RECOGNITION, SCOPE, TRIPLES, XR_TEXT, makeRun } from "./fixtures";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const slot = {
  status: "completed" as const,
  run: makeRun({ id: "run-i", pipeline_type: "individual_extraction" }),
};

let previewBody: unknown = null;

async function renderReady() {
  server.use(
    http.get("*/api/pipelines/runs/run-i/individual-extraction-candidates", () =>
      HttpResponse.json(TRIPLES),
    ),
    http.post("*/api/pipelines/runs/run-i/recognition-preview", async ({ request }) => {
      previewBody = await request.json();
      return HttpResponse.json(RECOGNITION);
    }),
  );
  renderWithProviders(
    <IndividualCandidateReview slot={slot} text={XR_TEXT} scope={SCOPE} onRetry={() => {}} />,
  );
  await screen.findByTestId("extraction-review-triples");
  await screen.findByText("no match · created as new");
}

describe("IndividualCandidateReview", () => {
  it("renders triples with mapped / new node chips and requests the recognition preview", async () => {
    await renderReady();
    const triples = screen.getByTestId("extraction-review-triples");
    expect(within(triples).getAllByText("mapped")[0]).toHaveClass("chip--emerald");
    expect(within(triples).getAllByText("new")[0]).toHaveClass("chip--amber");
    expect(within(triples).getByText("literal")).toBeInTheDocument();
    expect(within(triples).getAllByText("new property")[0]).toHaveClass("chip--amber");
    expect(previewBody).toEqual({ confidence_threshold: 0, recognition_threshold: 0.9 });
    expect(screen.getByText("RECOGNITION").closest(".stat-tile")).toHaveTextContent("2 / 3");
  });

  it("filters triples to those with a new node", async () => {
    await renderReady();
    const triples = screen.getByTestId("extraction-review-triples");
    await userEvent.click(within(triples).getByRole("radio", { name: "Has new node" }));
    expect(within(triples).getAllByRole("row")).toHaveLength(2); // header + 1 triple
  });

  it("offers merge / keep separate only for hits that match an existing individual", async () => {
    await renderReady();
    const rec = screen.getByTestId("extraction-review-recognition");
    expect(screen.getByTestId("extraction-review-recognition-decision-hit-0")).toHaveAttribute(
      "role",
      "group",
    );
    expect(
      screen.queryByTestId("extraction-review-recognition-decision-hit-2"),
    ).not.toBeInTheDocument();
    expect(within(rec).getByText("no match · created as new")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("extraction-review-recognition-decision-hit-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-recognition-decision-hit-1-no"));
    expect(within(rec).getByText("1 merge")).toBeInTheDocument();
    expect(within(rec).getByText("1 separate")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-recognition-decision-hit-1-no")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("opens the recognition inspector from a mention highlight and links to its triples", async () => {
    await renderReady();
    const mention = screen
      .getAllByTestId("extraction-review-span")
      .find((m) => m.getAttribute("data-span-keys")?.split(" ").includes("hit-1"));
    await userEvent.click(mention!);
    // "Claims Adjuster" is covered by the triple span and the hit span: cycle to the hit.
    if (!screen.queryByTestId("extraction-review-recognition-inspector")) {
      await userEvent.click(mention!);
    }
    const inspector = screen.getByTestId("extraction-review-recognition-inspector");
    expect(inspector).toHaveTextContent("Claims Adjuster");
    await userEvent.click(
      within(inspector).getByRole("button", { name: /Claims Adjuster → uses/ }),
    );
    expect(screen.getByTestId("extraction-review-individual-inspector")).toHaveTextContent(
      "Claims Review Service",
    );
  });

  it("shows the canonical title of a mapped node next to its extracted label", async () => {
    await renderReady();
    const triples = screen.getByTestId("extraction-review-triples");
    expect(within(triples).getByTestId("extraction-review-node-title")).toHaveTextContent(
      "→ Customer Self-Service Portal",
    );
  });

  it("summarises merge / separate / recognition choices in the confirm dialog", async () => {
    await renderReady();
    await userEvent.click(screen.getByTestId("extraction-review-individual-decision-triple-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-individual-decision-triple-2-no"));
    await userEvent.click(screen.getByTestId("extraction-review-recognition-decision-hit-0-no"));
    expect(screen.getByTestId("extraction-review-individual-apply-bar")).toHaveTextContent(
      "1 accepted",
    );
    await userEvent.click(screen.getByTestId("extraction-review-individual-apply"));
    const confirm = screen.getByTestId("extraction-review-individual-confirm");
    expect(within(confirm).getByText("1 kept separate")).toHaveClass("chip--neutral");
    expect(within(confirm).getByText("1 left to recognition")).toHaveClass("chip--cyan");
    expect(within(confirm).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("applies accepted triples with per-mention decisions and shows what merged", async () => {
    let applyUrl: URL | null = null;
    let applyBody: unknown = null;
    await renderReady();
    server.use(
      http.post("*/api/pipelines/runs/run-i/apply", async ({ request }) => {
        applyUrl = new URL(request.url);
        applyBody = await request.json();
        return HttpResponse.json({
          run_id: "run-i",
          pipeline_type: "individual_extraction",
          classes_created: 0,
          properties_created: 0,
          individuals_created: 1,
          relationships_created: 1,
          applied_candidate_ids: ["triple-1"],
          skipped_candidate_ids: ["triple-0", "triple-2"],
          merged_mentions: [
            { mention_label: "Claims Adjuster", individual_id: "ind_3a90", source: "decision" },
          ],
        });
      }),
    );
    await userEvent.click(screen.getByTestId("extraction-review-individual-decision-triple-1-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-recognition-decision-hit-1-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-recognition-decision-hit-0-no"));
    await userEvent.click(screen.getByTestId("extraction-review-individual-apply"));
    await userEvent.click(screen.getByRole("button", { name: "Apply 1 accepted" }));
    expect(await screen.findByTestId("extraction-review-individual-revert")).toBeInTheDocument();

    expect(applyUrl!.searchParams.get("confidence_threshold")).toBeNull();
    expect(applyUrl!.searchParams.get("recognition_threshold")).toBe("0.9");
    expect(applyBody).toEqual({
      accepted_candidate_ids: ["triple-1"],
      recognition_decisions: [
        { mention_label: "Customer Portal", decision: "separate" },
        { mention_label: "Claims Adjuster", decision: "merge", individual_id: "ind_3a90" },
      ],
    });
    const merged = screen.getByTestId("extraction-review-apply-result-merged");
    expect(merged).toHaveTextContent("Claims Adjuster → Claims Adjuster");
    expect(within(merged).getByText("your merge")).toHaveClass("chip--cyan");
    expect(screen.getByTestId("extraction-review-apply-result-created")).toHaveTextContent(
      "1 individuals created",
    );
    expect(screen.queryByTestId("extraction-review-apply-result-skipped")).not.toBeInTheDocument();
  });
});
