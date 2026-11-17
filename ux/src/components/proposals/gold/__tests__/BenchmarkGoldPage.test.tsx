/**
 * The Gold page (#1614): the benchmark's gold checks with their split, size,
 * checked progress and status, opening each on the Review page, and the
 * commands that load, write back and re-score them.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { BenchmarkGoldPage } from "../BenchmarkGoldPage";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function goldCheck(
  id: string,
  document: string,
  split: "dev" | "holdout",
  statuses: string[],
): ChangeProposal {
  const origin = {
    pipeline_type: "individual_extraction",
    implementation_id: "gold_check",
    configuration_ref: "gold",
    configuration_version: 1,
    digest: "abc",
  };
  return createChangeProposal({
    id,
    source: "pipeline",
    created_at: `2026-11-1${statuses.length}T00:00:00Z`,
    origin,
    client_metadata: {
      origin,
      gold_check: { document, split, elements: {}, relationships: {} },
    },
    operations: statuses.map((status, i) =>
      createProposedOperation({
        id: `${id}-op-${i}`,
        seq: i + 1,
        op: "create",
        kind: i === statuses.length - 1 ? "relationship" : "individual",
        target_id: null,
        status: status as "pending",
      }),
    ),
  });
}

function serve(items: ChangeProposal[]) {
  let query: URLSearchParams | undefined;
  server.use(
    http.get("*/api/proposals", ({ request }) => {
      query = new URL(request.url).searchParams;
      return HttpResponse.json({ items, total: items.length, limit: 500, offset: 0 });
    }),
  );
  return () => query;
}

describe("BenchmarkGoldPage", () => {
  it("lists the gold checks with their split, size, progress and status", async () => {
    const query = serve([
      goldCheck("p-edit", "edit_check", "dev", ["pending", "pending", "pending"]),
      goldCheck("p-wiki", "wikimedia_enterprise", "holdout", ["applied", "pending"]),
      createChangeProposal({ id: "p-other", source: "pipeline" }),
    ]);
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(<BenchmarkGoldPage onOpenReview={onOpen} />);

    const table = await screen.findByRole("region", { name: "Documents" });
    expect(screen.getByTestId("gold-page")).toHaveClass("gold-page");
    expect(
      within(screen.getByTestId("gold-header")).getByRole("heading", { level: 1 }),
    ).toHaveTextContent("Benchmark gold");
    expect(query()?.get("source")).toBe("pipeline");
    expect(query()?.get("limit")).toBe("500");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    const edit = rows.find((r) => within(r).queryByText("edit_check"))!;
    expect(within(edit).getByText("dev")).toHaveClass("chip--cyan");
    expect(edit).toHaveTextContent("0 / 3 decided");
    expect(within(edit).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByTestId("gold-status-edit_check")).toHaveTextContent("model-made");
    expect(screen.getByTestId("gold-status-edit_check")).toHaveClass("chip--amber");
    const wiki = rows.find((r) => within(r).queryByText("wikimedia_enterprise"))!;
    expect(within(wiki).getByText("holdout")).toHaveClass("chip--violet");
    expect(wiki).toHaveTextContent("1 / 2 decided");
    expect(screen.queryByText("p-other")).not.toBeInTheDocument();

    expect(screen.getByTestId("gold-open-edit_check")).toHaveTextContent("Check gold");
    const resume = screen.getByRole("button", { name: "Continue: wikimedia_enterprise" });
    expect(resume).toBe(screen.getByTestId("gold-open-wikimedia_enterprise"));
    await user.click(resume);
    expect(onOpen).toHaveBeenCalledWith("p-wiki");
  });

  it("marks a finished check as checked, to open", async () => {
    serve([goldCheck("p-edit", "edit_check", "dev", ["applied", "rejected"])]);
    render(<BenchmarkGoldPage onOpenReview={vi.fn()} />);
    const status = await screen.findByTestId("gold-status-edit_check");
    expect(status).toHaveTextContent("checked");
    expect(status).toHaveClass("chip--emerald");
    expect(screen.getByTestId("gold-open-edit_check")).toHaveTextContent("Open");
  });

  it("shows the write-back and re-score commands, each copyable", async () => {
    serve([goldCheck("p-edit", "edit_check", "dev", ["pending", "pending"])]);
    const user = userEvent.setup();
    const write = vi.spyOn(navigator.clipboard, "writeText");
    render(<BenchmarkGoldPage onOpenReview={vi.fn()} />);
    const command = await screen.findByTestId("gold-write-edit_check");
    expect(command).toHaveClass("gold-command");
    expect(command).toHaveTextContent(
      "python scripts/extraction_benchmark.py write-gold --document edit_check --proposal p-edit",
    );
    expect(screen.getByTestId("gold-replay")).toHaveTextContent(
      "python scripts/benchmark_replay.py --all",
    );
    expect(screen.getByTestId("gold-replay-external")).toHaveTextContent(
      "python scripts/benchmark_external.py replay",
    );
    await user.click(within(command).getByRole("button", { name: /^Copy: python/ }));
    expect(write).toHaveBeenCalledWith(
      "python scripts/extraction_benchmark.py write-gold --document edit_check --proposal p-edit",
    );
    expect(screen.getByRole("region", { name: "What a check writes" })).toHaveTextContent(
      "Not an element",
    );
    expect(screen.getByRole("region", { name: "Holdout and scores" })).toHaveTextContent(
      "wikimedia_enterprise is the holdout",
    );
  });

  it("shows the check command when no gold check is loaded", async () => {
    serve([createChangeProposal({ id: "p-other", source: "pipeline" })]);
    render(<BenchmarkGoldPage onOpenReview={vi.fn()} />);
    expect(await screen.findByTestId("gold-empty")).toHaveTextContent("No gold check is loaded");
    expect(screen.getByTestId("gold-empty-command")).toHaveTextContent(
      "python scripts/extraction_benchmark.py check --document <document>",
    );
    expect(screen.queryByRole("region", { name: "Documents" })).not.toBeInTheDocument();
  });
});
