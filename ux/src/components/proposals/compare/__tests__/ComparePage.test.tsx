/**
 * The Compare page (#1615): two pipelines' proposals for one source, the
 * four groups, the differences decided once for both, and the agreements
 * accepted in bulk only after their sample is checked.
 */
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { component, entityPageHandlers, serviceClass } from "@/test/entityPageHandlers";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type {
  ComparedOperation,
  ComparisonPair,
  PairDecisionRequest,
  ProposalComparison,
} from "@/api/services/proposals";
import { ComparePage } from "../ComparePage";

const ORIGIN_A = {
  pipeline_type: "individual_extraction",
  implementation_id: "single_call",
  configuration_ref: "extraction-single-call",
  configuration_version: 2,
  digest: "aaaaaa111111",
};
const ORIGIN_B = { ...ORIGIN_A, implementation_id: "find_then_type", digest: "bbbbbb222222" };

function copy(
  id: string,
  title: string,
  classId: string,
  overrides: Partial<ComparedOperation> = {},
): ComparedOperation {
  return {
    operation_id: id,
    seq: 1,
    title,
    classes: [{ id: classId, title: classId }],
    status: "pending",
    evidence: [{ source_id: "src-1", start: 0, end: 4, quote: `${title} quote` }],
    alternatives: [],
    lacks_passage: false,
    ...overrides,
  } as ComparedOperation;
}

function pair(
  id: string,
  group: ComparisonPair["group"],
  a: ComparedOperation | null,
  b: ComparedOperation | null,
  extra: Partial<ComparisonPair> = {},
): ComparisonPair {
  return { pair_id: id, group, in_sample: false, state: "open", a, b, ...extra };
}

let comparison: ProposalComparison;
let decisions: PairDecisionRequest[];
let rests: unknown[];
let decideAnswer: (() => Response) | undefined;
let restAnswer: (() => Response) | undefined;

function makeComparison(): ProposalComparison {
  return {
    a: { proposal_id: "pa", status: "open", origin: ORIGIN_A },
    b: { proposal_id: "pb", status: "open", origin: ORIGIN_B },
    taxonomy_id: "tax-1",
    dataset_id: "ds-1",
    source_id: "src-1",
    pairs: [
      pair(
        "p1",
        "same_class",
        copy("a1", "Edit Check", "class-1"),
        copy("b1", "Edit Check", "class-1"),
        {
          in_sample: true,
        },
      ),
      pair(
        "p2",
        "same_class",
        copy("a2", "Tone check", "class-2"),
        copy("b2", "Tone check", "class-2"),
      ),
      pair(
        "p3",
        "class_differs",
        copy("a3", "Suggestion Mode", "class-1"),
        copy("b3", "Suggestion Mode", "class-2"),
      ),
      pair("p4", "only_a", copy("a4", "Sub-Saharan Africa", "class-2"), null),
      pair("p5", "only_b", null, copy("b5", "TextMatch", "class-1")),
      pair(
        "p6",
        "class_differs",
        copy("a6", "Paste Check", "class-1", { status: "applied" }),
        copy("b6", "Paste Check", "class-2", { status: "rejected", reason_code: "duplicate" }),
        { state: "decided" },
      ),
      pair(
        "p7",
        "only_b",
        null,
        copy("b7", "Reference check", "class-2", {
          status: "failed",
          reason: "domain_range_mismatch: target is Place",
        }),
        { state: "failed" },
      ),
    ],
    counts: { same_class: 2, class_differs: 2, only_a: 1, only_b: 2, open: 6 },
    sample: { size: 1, checked: 0, changed: 0 },
  };
}

const proposalA = createChangeProposal({
  id: "pa",
  title: "Extraction: Edit check (single_call)",
  source: "pipeline",
  origin: ORIGIN_A,
  created_at: "2026-11-17T10:00:00Z",
  client_metadata: { source_id: "src-1", origin: { ...ORIGIN_A, model: "Opus 5.5" } },
  operations: [
    createProposedOperation({ id: "a1", op: "create", kind: "individual", target_id: null }),
    createProposedOperation({ id: "a2", op: "create", kind: "individual", target_id: null }),
    createProposedOperation({ id: "ar", op: "create", kind: "relationship", target_id: null }),
  ],
});
const proposalB = createChangeProposal({
  id: "pb",
  title: "Extraction: Edit check (find_then_type)",
  source: "pipeline",
  origin: ORIGIN_B,
  created_at: "2026-11-18T10:00:00Z",
  client_metadata: { source_id: "src-1", origin: ORIGIN_B },
  operations: [
    createProposedOperation({ id: "b1", op: "create", kind: "individual", target_id: null }),
  ],
});

const server = setupServer(...entityPageHandlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  comparison = makeComparison();
  decisions = [];
  rests = [];
  decideAnswer = undefined;
  restAnswer = undefined;
  server.use(
    http.get("*/api/taxonomies/:id/classes", () => HttpResponse.json([component, serviceClass])),
    http.get("*/api/proposals/pa/compare/pb", () => HttpResponse.json(comparison)),
    http.post("*/api/proposals/pa/compare/pb/decide", async ({ request }) => {
      const body = (await request.json()) as PairDecisionRequest;
      decisions.push(body);
      if (decideAnswer) return decideAnswer();
      const decided = comparison.pairs.find(
        (p) =>
          (body.a_operation_id && p.a?.operation_id === body.a_operation_id) ||
          (body.b_operation_id && p.b?.operation_id === body.b_operation_id),
      )!;
      const landing =
        body.verdict === "b_class" || (!decided.a && body.verdict === "keep")
          ? decided.b
          : decided.a;
      for (const c of [decided.a, decided.b]) {
        if (!c) continue;
        c.status =
          body.verdict === "not_element" ? "rejected" : c === landing ? "applied" : "rejected";
        if (body.verdict === "not_element") c.reason_code = body.reason_code ?? "other";
      }
      decided.state = "decided";
      if (decided.in_sample)
        comparison.sample = { ...comparison.sample, checked: comparison.sample.checked + 1 };
      return HttpResponse.json({ pair: decided, outcome: "landed", sample: comparison.sample });
    }),
    http.post("*/api/proposals/pa/compare/pb/accept-rest", async ({ request }) => {
      rests.push(await request.json());
      if (restAnswer) return restAnswer();
      return HttpResponse.json({
        landed: 1,
        failed: [],
        skipped: [{ pair_id: "px", why: "near_match" }],
        sample: comparison.sample,
      });
    }),
    http.get("*/api/proposals/:id", ({ params }) =>
      HttpResponse.json(params.id === "pa" ? proposalA : proposalB),
    ),
    http.get("*/api/sources/:id", () =>
      HttpResponse.json({ id: "src-1", title: "edit_check.md", status: "ready" }),
    ),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const onFinish = vi.fn();

async function renderPage() {
  const user = userEvent.setup();
  render(<ComparePage aId="pa" bId="pb" onFinish={onFinish} />);
  await screen.findByTestId("compare-table", {}, { timeout: 10000 });
  return user;
}

const row = (id: string) => screen.getByTestId(`compare-row-${id}`);

describe("ComparePage", () => {
  it("shows the source, both origins and the four counts", async () => {
    const user = await renderPage();
    expect(screen.getByTestId("compare-page")).toHaveClass("compare-page");
    const header = screen.getByTestId("compare-header");
    expect(within(header).getByRole("heading", { level: 1 })).toHaveTextContent(
      "Compare pipelines",
    );
    await waitFor(() =>
      expect(header).toHaveTextContent("SOURCE edit_check.md · TWO OPEN PROPOSALS"),
    );
    const a = screen.getByTestId("compare-origin-a");
    expect(a).toHaveClass("compare-origin", "compare-origin--a");
    expect(a).toHaveAttribute("aria-label", "Proposal A");
    expect(screen.getByTestId("compare-origin-a-chip")).toHaveTextContent(
      "single_call v2 · aaaaaa",
    );
    await waitFor(() => expect(a).toHaveTextContent("Opus 5.5 · 2 individuals · 1 relationships"));
    expect(screen.getByTestId("compare-origin-b")).toHaveClass("compare-origin--b");
    expect(screen.getByTestId("compare-origin-b-chip")).toHaveTextContent("find_then_type v2");
    expect(screen.getByTestId("compare-count-same_class")).toHaveTextContent("2");
    expect(screen.getByTestId("compare-count-class_differs")).toHaveTextContent("2");
    expect(screen.getByTestId("compare-count-only_a")).toHaveTextContent("1");
    expect(screen.getByTestId("compare-count-only_b")).toHaveTextContent("2");
    await user.click(screen.getByTestId("compare-finish"));
    expect(onFinish).toHaveBeenCalled();
  });

  it("shows the differences, with the agreements and the sample a filter away", async () => {
    const user = await renderPage();
    const ids = () =>
      within(screen.getByTestId("compare-table"))
        .getAllByRole("row")
        .slice(1)
        .map((r) => r.getAttribute("data-testid"));
    expect(ids()).toEqual([
      "compare-row-p3",
      "compare-row-p4",
      "compare-row-p5",
      "compare-row-p6",
      "compare-row-p7",
    ]);
    expect(row("p3")).toHaveClass("compare-row", "compare-row--class_differs", "compare-row--open");
    expect(row("p6")).toHaveClass("compare-row--decided");
    expect(row("p7")).toHaveAttribute("data-state", "failed");
    expect(within(row("p3")).getByRole("button", { name: "Suggestion Mode" })).toHaveAttribute(
      "data-pill",
      "individual",
    );
    expect(within(row("p3")).getAllByRole("button", { name: /^Class / })).toHaveLength(2);
    expect(row("p4")).toHaveTextContent("—");
    await user.click(
      within(screen.getByTestId("compare-filter")).getByRole("radio", { name: /Agreements/ }),
    );
    expect(ids()).toEqual(["compare-row-p1", "compare-row-p2"]);
    await user.click(screen.getByTestId("compare-check-sample"));
    expect(ids()).toEqual(["compare-row-p1"]);
    expect(screen.getByTestId("compare-sample-p1")).toHaveTextContent("sample");
  });

  it("takes B's class for a pair, naming both copies, with the time spent", async () => {
    const user = await renderPage();
    const choices = within(row("p3")).getByRole("group", { name: "Decide Suggestion Mode" });
    expect(
      within(choices)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["A class", "B class", "Neither"]);
    await user.click(screen.getByTestId("compare-decide-p3-b_class"));
    await waitFor(() => expect(decisions).toHaveLength(1));
    expect(decisions[0]).toEqual({
      a_operation_id: "a3",
      b_operation_id: "b3",
      verdict: "b_class",
      review_ms: expect.any(Number),
    });
    await waitFor(() =>
      expect(screen.getByTestId("compare-outcome-p3")).toHaveTextContent(
        "B class: ApplicationService",
      ),
    );
    expect(screen.getByTestId("compare-outcome-p3")).toHaveClass("compare-outcome--landed");
  });

  it("rejects both copies as not an element, with a reason", async () => {
    const user = await renderPage();
    await user.click(screen.getByTestId("compare-decide-p3-not_element"));
    const reasons = within(row("p3")).getByRole("group", { name: "Not an element, because" });
    await user.click(within(reasons).getByRole("button", { name: "Too generic" }));
    await waitFor(() => expect(decisions).toHaveLength(1));
    expect(decisions[0]).toMatchObject({
      a_operation_id: "a3",
      b_operation_id: "b3",
      verdict: "not_element",
      reason_code: "too_generic",
    });
    await waitFor(() =>
      expect(screen.getByTestId("compare-outcome-p3")).toHaveTextContent(
        "Not an element: Too generic",
      ),
    );
    expect(screen.getByTestId("compare-outcome-p3")).toHaveClass("compare-outcome--rejected");
  });

  it("keeps an element only one pipeline found, naming its one copy", async () => {
    const user = await renderPage();
    expect(
      within(row("p5"))
        .getAllByRole("button", { name: /Keep|Not an element/ })
        .map((b) => b.textContent),
    ).toEqual(["Keep", "Not an element"]);
    await user.click(screen.getByTestId("compare-decide-p5-keep"));
    await waitFor(() => expect(decisions).toHaveLength(1));
    expect(decisions[0]).toEqual({
      b_operation_id: "b5",
      verdict: "keep",
      review_ms: expect.any(Number),
    });
  });

  it("shows a decided pair read-only and a failed one's reason", async () => {
    await renderPage();
    await waitFor(() =>
      expect(screen.getByTestId("compare-outcome-p6")).toHaveTextContent(
        "A class: application.component",
      ),
    );
    expect(screen.queryByTestId("compare-decide-p6-a_class")).not.toBeInTheDocument();
    const failed = screen.getByTestId("compare-failed-p7");
    expect(failed).toHaveAttribute("role", "alert");
    expect(failed).toHaveTextContent("domain_range_mismatch: target is Place");
    expect(screen.getByTestId("compare-decide-p7-keep")).toBeEnabled();
  });

  it("shows a refusal or a failed landing beside the pair", async () => {
    decideAnswer = () =>
      HttpResponse.json(
        { detail: { code: "already_decided", message: "B's copy was already decided" } },
        { status: 409 },
      );
    const user = await renderPage();
    await user.click(screen.getByTestId("compare-decide-p4-keep"));
    const error = await screen.findByTestId("compare-error-p4");
    expect(error).toHaveAttribute("role", "alert");
    expect(error).toHaveTextContent("B's copy was already decided");

    decideAnswer = () =>
      HttpResponse.json({
        pair: comparison.pairs[3],
        outcome: "failed",
        failure_reason: "title_conflict",
        sample: comparison.sample,
      });
    await user.click(screen.getByTestId("compare-decide-p4-keep"));
    await waitFor(() =>
      expect(screen.getByTestId("compare-error-p4")).toHaveTextContent("title_conflict"),
    );
  });

  it("offers Accept the rest once the sample is checked, and says what it did", async () => {
    const user = await renderPage();
    const accept = screen.getByTestId("compare-accept-rest");
    expect(accept).toBeDisabled();
    expect(screen.getByTestId("compare-sample-progress")).toHaveTextContent(
      "Sample: 0 / 1 checked · 0 changed",
    );
    await user.click(screen.getByTestId("compare-check-sample"));
    await user.click(screen.getByTestId("compare-decide-p1-keep"));
    await waitFor(() => expect(screen.getByTestId("compare-accept-rest")).toBeEnabled());
    expect(screen.getByTestId("compare-sample-progress")).toHaveTextContent("1 / 1 checked");
    await user.click(screen.getByTestId("compare-accept-rest"));
    await waitFor(() => expect(rests).toEqual([{ sample_size: 10 }]));
    const result = await screen.findByTestId("compare-rest-result");
    expect(result).toHaveAttribute("role", "status");
    expect(result).toHaveTextContent(
      "Accepted 1 agreement. 1 left for you (a near match or no passage).",
    );
  });

  it("shows a refused Accept the rest", async () => {
    comparison.sample = { size: 1, checked: 1, changed: 0 };
    restAnswer = () =>
      HttpResponse.json(
        { detail: { code: "sample_unchecked", message: "1 sample pair is open" } },
        { status: 409 },
      );
    const user = await renderPage();
    await user.click(screen.getByTestId("compare-accept-rest"));
    expect(await screen.findByTestId("compare-rest-error")).toHaveTextContent(
      "1 sample pair is open",
    );
  });

  it("says why two proposals can't be compared", async () => {
    server.use(
      http.get("*/api/proposals/pa/compare/pb", () =>
        HttpResponse.json(
          {
            detail: { code: "not_comparable", message: "The proposals extract different sources" },
          },
          { status: 422 },
        ),
      ),
    );
    render(<ComparePage aId="pa" bId="pb" onFinish={onFinish} />);
    expect(
      await screen.findByTestId("compare-load-error", {}, { timeout: 10000 }),
    ).toHaveTextContent("The proposals extract different sources");
  });

  it("sends the active time from reaching the row to deciding it", async () => {
    const START = new Date("2026-11-19T10:00:00Z").getTime();
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      vi.setSystemTime(START);
      const user = await renderPage();
      fireEvent.pointerEnter(row("p4"));
      vi.setSystemTime(START + 2_000);
      fireEvent.pointerMove(window);
      vi.setSystemTime(START + 4_500);
      await user.click(screen.getByTestId("compare-decide-p4-keep"));
      await waitFor(() => expect(decisions).toHaveLength(1));
      expect(decisions[0].review_ms).toBe(4_500);
    } finally {
      vi.useRealTimers();
    }
  });
});
