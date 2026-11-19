/**
 * "Compare with another pipeline" (#1615): shown only when another open
 * extraction of the same source and dataset by another implementation exists;
 * with several, a menu picks one.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { createChangeProposal } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { CompareEntry } from "../CompareEntry";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const extraction = (id: string, implementation: string, overrides: Partial<ChangeProposal> = {}) =>
  createChangeProposal({
    id,
    source: "pipeline",
    dataset_id: "ds-1",
    origin: {
      pipeline_type: "individual_extraction",
      implementation_id: implementation,
      configuration_ref: "c",
      configuration_version: 1,
      digest: `${id}digest`,
    },
    client_metadata: { source_id: "src-1" },
    ...overrides,
  });

const mine = extraction("p1", "single_call");

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

describe("CompareEntry", () => {
  it("opens the one other pipeline's proposal", async () => {
    const query = serve([mine, extraction("p2", "find_then_type")]);
    const onCompare = vi.fn();
    render(<CompareEntry proposal={mine} onCompare={onCompare} />);
    const button = await screen.findByRole("button", { name: "Compare with another pipeline" });
    expect(button).toHaveAttribute("data-testid", "compare-entry");
    expect(button).toHaveAttribute("title", "Compare with find_then_type v1 · p2dige");
    expect(query()?.get("status")).toBe("open");
    expect(query()?.get("source")).toBe("pipeline");
    expect(query()?.get("taxonomy_id")).toBe("tax-1");
    await userEvent.click(button);
    expect(onCompare).toHaveBeenCalledWith("p2");
  });

  it("offers a menu when several pipelines extracted the source", async () => {
    serve([mine, extraction("p2", "find_then_type"), extraction("p3", "two_pass")]);
    const onCompare = vi.fn();
    const user = userEvent.setup();
    render(<CompareEntry proposal={mine} onCompare={onCompare} />);
    const toggle = await screen.findByTestId("compare-entry-toggle");
    expect(toggle).toHaveAttribute("aria-haspopup", "menu");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("menu", { name: "Compare with" });
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((m) => m.textContent),
    ).toEqual(["find_then_type v1 · p2dige", "two_pass v1 · p3dige"]);
    await user.click(within(menu).getByRole("menuitem", { name: /two_pass/ }));
    expect(onCompare).toHaveBeenCalledWith("p3");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("is absent when nothing else extracted the source, or the proposal is decided", async () => {
    const query = serve([mine, extraction("p3", "single_call")]);
    const { rerender } = render(<CompareEntry proposal={mine} onCompare={vi.fn()} />);
    await waitFor(() => expect(query()).toBeDefined());
    expect(screen.queryByTestId("compare-entry")).not.toBeInTheDocument();
    rerender(<CompareEntry proposal={{ ...mine, status: "done" }} onCompare={vi.fn()} />);
    expect(screen.queryByTestId("compare-entry")).not.toBeInTheDocument();
  });
});
