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
  await screen.findByText("Customer Self-Service Portal");
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

  it("accepts a triple from the compact row control and warns about keep-separate on apply", async () => {
    await renderReady();
    await userEvent.click(screen.getByTestId("extraction-review-individual-decision-t-0-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-individual-decision-t-2-no"));
    await userEvent.click(screen.getByTestId("extraction-review-recognition-decision-hit-0-no"));
    expect(screen.getByTestId("extraction-review-individual-apply-bar")).toHaveTextContent(
      "1 accepted",
    );
    await userEvent.click(screen.getByTestId("extraction-review-individual-apply"));
    expect(screen.getByTestId("extraction-review-individual-confirm")).toBeInTheDocument();
    expect(screen.getByTestId("extraction-review-individual-separate-warning")).toHaveTextContent(
      '1 "keep separate" choice',
    );
    // t-2 (0.75) is rejected below the 0.90 floor, so nothing leaks.
    expect(
      screen.queryByTestId("extraction-review-individual-leak-warning"),
    ).not.toBeInTheDocument();
  });

  it("applies with the recognition threshold", async () => {
    let applyUrl: URL | null = null;
    await renderReady();
    server.use(
      http.post("*/api/pipelines/runs/run-i/apply", ({ request }) => {
        applyUrl = new URL(request.url);
        return HttpResponse.json({ run_id: "run-i", pipeline_type: "individual_extraction" });
      }),
    );
    await userEvent.click(screen.getByTestId("extraction-review-individual-decision-t-1-yes"));
    await userEvent.click(screen.getByTestId("extraction-review-individual-apply"));
    await userEvent.click(screen.getByRole("button", { name: "Apply 1 accepted" }));
    expect(await screen.findByTestId("extraction-review-individual-revert")).toBeInTheDocument();
    expect(applyUrl!.searchParams.get("confidence_threshold")).toBe("0.69");
    expect(applyUrl!.searchParams.get("recognition_threshold")).toBe("0.9");
  });
});
