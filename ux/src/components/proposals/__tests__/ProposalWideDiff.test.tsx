/**
 * The wide diff (#1661): a long text change read side by side over the list,
 * the inspector beside it. ⤢ Wide on a row or W opens it; the changed fields
 * are tabs stepped with the arrows; J / K move to the next operation with a
 * long change; Esc or ✕ close it and focus returns to the row's Wide control.
 */
import { useState } from "react";
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { entityPageHandlers } from "@/test/entityPageHandlers";
import { goldPage, proposalHandlers } from "@/test/proposalFixtures";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { ChangeProposal } from "@/api/services/proposals";
import { ProposalDetailPage } from "../ProposalDetailPage";

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

const OWNED = "It is owned by one team and changes on its own schedule.";
const LONG_BEFORE = `A modular, deployable part of a system. It exposes interfaces to other components. ${OWNED} It has a repository. It has a pipeline. It has an owner.`;
const LONG_AFTER = `A modular, deployable part of a system. It exposes services and interfaces to other components. ${OWNED} It has a repository. It has a pipeline. It has an owner.`;
const VISION_BEFORE =
  "Teams own their components end to end, from the code to the dashboards that watch it in production.";
const VISION_AFTER =
  "Teams own their components end to end, from the code to the dashboards and alerts that watch it in production.";

const first = createProposedOperation({
  id: "op-a",
  seq: 1,
  op: "update",
  kind: "class",
  target_id: "class-1",
  base: { description: LONG_BEFORE, vision: VISION_BEFORE },
  fields: { description: LONG_AFTER, vision: VISION_AFTER },
});
const short = createProposedOperation({
  id: "op-b",
  seq: 2,
  op: "update",
  kind: "class",
  target_id: "class-2",
  base: { title: "Service" },
  fields: { title: "Application Service" },
});
const third = createProposedOperation({
  id: "op-c",
  seq: 3,
  op: "update",
  kind: "class",
  target_id: "class-2",
  base: { description: LONG_BEFORE },
  fields: { description: `${LONG_BEFORE} It is versioned.` },
});

let proposal: ChangeProposal;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  proposal = createChangeProposal({
    id: "proposal-1",
    taxonomy_id: "tax-1",
    status: "open",
    operations: structuredClone([first, short, third]),
  });
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

let current: { op?: string; diff?: string };

/** The route's part: the selection and the open field, as ?op= and &diff= hold them. */
function Harness({ initial }: { initial: string }) {
  const [state, setState] = useState<{ op?: string; diff?: string }>({ op: initial });
  current = state;
  return (
    <ProposalDetailPage
      id="proposal-1"
      selectedOperationId={state.op}
      onSelectOperation={(op) => setState({ op })}
      diffField={state.diff}
      onDiff={(diff, op) => setState((s) => ({ op: op ?? s.op, diff }))}
    />
  );
}

async function openPage(initial: string) {
  const user = userEvent.setup();
  render(<Harness initial={initial} />);
  await screen.findByTestId("review-inspector", {}, { timeout: 10000 });
  return user;
}

const selectedTab = () =>
  within(screen.getByRole("tablist", { name: "Changed fields" })).getByRole("tab", {
    selected: true,
  });

describe("the wide diff", () => {
  it("opens from ⤢ Wide on a long change, over the list, with its fields as tabs", async () => {
    const user = await openPage("op-a");
    await user.click(screen.getByTestId("review-wide-description"));
    const overlay = screen.getByTestId("review-wide-diff");
    expect(current.diff).toBe("description");
    // Over the list column; the inspector stays beside it to decide.
    expect(overlay.closest(".proposal-main")).not.toBeNull();
    expect(screen.getByTestId("review-inspector")).toBeVisible();
    expect(screen.getByTestId("review-decide")).toBeInTheDocument();
    const tabs = within(screen.getByRole("tablist", { name: "Changed fields" })).getAllByRole(
      "tab",
    );
    expect(tabs.map((t) => t.textContent)).toEqual(["description", "vision"]);
    expect(selectedTab()).toHaveTextContent("description");
    expect(selectedTab()).toHaveFocus();
    // Sentence by sentence: the changed one removed, then added; unchanged ones folded.
    const lines = screen.getByTestId("review-wide-lines");
    const rows = (type: string) =>
      [...lines.querySelectorAll(`.side-by-side-diff__row--${type}`)]
        .map((r) => r.textContent)
        .join(" ");
    expect(rows("removed")).toContain("It exposes interfaces to other components.");
    expect(rows("added")).toContain("It exposes services and interfaces to other components.");
    expect(rows("hunk")).toMatch(/unchanged sentence/);
  });

  it("steps the fields with the arrows and the ‹ › controls", async () => {
    const user = await openPage("op-a");
    await user.click(screen.getByTestId("review-wide-description"));
    await user.keyboard("{ArrowDown}");
    expect(current.diff).toBe("vision");
    expect(selectedTab()).toHaveTextContent("vision");
    await user.keyboard("{ArrowUp}");
    expect(current.diff).toBe("description");
    await user.click(screen.getByTestId("review-wide-next"));
    expect(current.diff).toBe("vision");
  });

  it("opens on W at the first long change, and Esc closes it, focus back on the row", async () => {
    const user = await openPage("op-a");
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("w");
    expect(current.diff).toBe("description");
    expect(screen.getByTestId("review-wide-diff")).toBeInTheDocument();
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Escape}");
    expect(current.diff).toBeUndefined();
    expect(screen.queryByTestId("review-wide-diff")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("review-wide-description")).toHaveFocus());
  });

  it("closes on ✕", async () => {
    const user = await openPage("op-a");
    await user.click(screen.getByTestId("review-wide-vision"));
    await user.click(screen.getByTestId("review-wide-close"));
    expect(current.diff).toBeUndefined();
    await waitFor(() => expect(screen.getByTestId("review-wide-vision")).toHaveFocus());
  });

  it("moves with J / K to the next operation that has a long change", async () => {
    const user = await openPage("op-a");
    await user.click(screen.getByTestId("review-wide-vision"));
    await user.keyboard("j");
    // op-b only renames: it is skipped.
    expect(current).toEqual({ op: "op-c", diff: "description" });
    await waitFor(() =>
      expect(screen.getByTestId("review-inspector-eyebrow")).toHaveTextContent("seq 3"),
    );
    expect(screen.getByTestId("review-wide-diff")).toBeInTheDocument();
    await user.keyboard("k");
    expect(current).toEqual({ op: "op-a", diff: "description" });
  });

  it("offers no Wide for a short change, and W does nothing there", async () => {
    const user = await openPage("op-b");
    expect(screen.queryByTestId(/^review-wide-/)).not.toBeInTheDocument();
    await user.click(screen.getByTestId("review-inspector-title"));
    await user.keyboard("w");
    expect(current.diff).toBeUndefined();
  });
});
