/**
 * The wide diff's history on the proposal route (#1661): opening it pushes an
 * entry, so Back closes it; J / K replace that entry; closing after a J / K step
 * keeps the operation it stepped to instead of going back to the one it opened on.
 * The route's navigate and history run against a small in-memory history here.
 */
import { useSyncExternalStore, type ReactNode } from "react";
import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { act, screen, waitFor } from "@testing-library/react";
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
import { ProposalPage } from "../proposals_.$proposalId";

type Search = { selected?: string; diff?: string };

/** Entries of ?op=&diff=, the current one, and who listens. */
const history = vi.hoisted(() => {
  const state = {
    entries: [] as Search[],
    index: 0,
    listeners: new Set<() => void>(),
  };
  const notify = () => state.listeners.forEach((l) => l());
  return {
    state,
    reset(first: Search) {
      state.entries = [first];
      state.index = 0;
      notify();
    },
    navigate({ search, replace }: { search?: Search; replace?: boolean }) {
      const next = { ...(search ?? {}) };
      if (replace) state.entries[state.index] = next;
      else {
        state.entries = [...state.entries.slice(0, state.index + 1), next];
        state.index += 1;
      }
      notify();
    },
    back() {
      if (state.index > 0) state.index -= 1;
      notify();
    },
    subscribe(listener: () => void) {
      state.listeners.add(listener);
      return () => state.listeners.delete(listener);
    },
    current: () => state.entries[state.index],
  };
});

vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return {
    ...actual,
    useNavigate: () => history.navigate,
    useRouter: () => ({ history: { back: history.back }, state: { status: "idle" } }),
    Link: ({
      children,
      to: _to,
      params: _p,
      search: _s,
      ...props
    }: {
      children: ReactNode;
      to?: unknown;
      params?: unknown;
      search?: unknown;
    }) => <a {...props}>{children}</a>,
  };
});

const server = setupServer(...proposalHandlers, ...entityPageHandlers);

const LONG_BEFORE =
  "A modular, deployable part of a system. It exposes interfaces to other components. It is owned by one team and changes on its own schedule. It has a repository and a pipeline.";
const LONG_AFTER =
  "A modular, deployable part of a system. It exposes services and interfaces to other components. It is owned by one team and changes on its own schedule. It has a repository and a pipeline.";

const opA = createProposedOperation({
  id: "op-a",
  seq: 1,
  op: "update",
  kind: "class",
  target_id: "class-1",
  base: { description: LONG_BEFORE },
  fields: { description: LONG_AFTER },
});
const opB = createProposedOperation({
  id: "op-b",
  seq: 2,
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
    operations: structuredClone([opA, opB]),
  });
  server.use(
    http.get("*/api/proposals/:id", () => HttpResponse.json(proposal)),
    http.get("*/api/taxonomies/:id/gold", () => HttpResponse.json(goldPage(proposal.operations))),
  );
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** The route: the page for the current entry. */
function Route() {
  const search = useSyncExternalStore(history.subscribe, history.current);
  return <ProposalPage proposalId="proposal-1" selected={search.selected} diff={search.diff} />;
}

async function openRoute(first: Search) {
  history.reset(first);
  const user = userEvent.setup();
  render(<Route />);
  await screen.findByTestId("review-inspector", {}, { timeout: 10000 });
  return user;
}

describe("the wide diff's history", () => {
  it("opens with a new entry, closes with Esc back over it, and Back then leaves the page state", async () => {
    const user = await openRoute({ selected: "op-a" });
    await user.click(screen.getByTestId("review-wide-description"));
    expect(history.state.entries).toEqual([
      { selected: "op-a" },
      { selected: "op-a", diff: "description" },
    ]);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByTestId("review-wide-diff")).not.toBeInTheDocument());
    expect(history.current()).toEqual({ selected: "op-a" });
    expect(history.state.index).toBe(0);
  });

  it("keeps the operation J stepped to when Esc closes it, and Back returns to the one before", async () => {
    const user = await openRoute({ selected: "op-a" });
    await user.click(screen.getByTestId("review-wide-description"));
    await user.keyboard("j");
    await waitFor(() =>
      expect(history.current()).toEqual({ selected: "op-b", diff: "description" }),
    );
    // J replaced the wide diff's entry: one entry was added in all.
    expect(history.state.entries).toHaveLength(2);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByTestId("review-wide-diff")).not.toBeInTheDocument());
    // The reviewer stays on op-b: the entry is replaced, not gone back over.
    expect(history.current()).toEqual({ selected: "op-b" });
    expect(screen.getByTestId("review-inspector")).toHaveTextContent("seq 2");
    // Back now returns to where the wide diff was opened from.
    act(() => history.back());
    expect(history.current()).toEqual({ selected: "op-a" });
    await waitFor(() => expect(screen.getByTestId("review-inspector")).toHaveTextContent("seq 1"));
  });

  it("closes with Back like any entry", async () => {
    const user = await openRoute({ selected: "op-a" });
    await user.click(screen.getByTestId("review-wide-description"));
    expect(screen.getByTestId("review-wide-diff")).toBeInTheDocument();
    act(() => history.back());
    await waitFor(() => expect(screen.queryByTestId("review-wide-diff")).not.toBeInTheDocument());
    expect(history.current()).toEqual({ selected: "op-a" });
  });
});
