import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render, createTestQueryClient } from "@/test/test-utils";
import { QUERY_KEYS } from "@/api/config";
import { createSyncStatus } from "@/api/services/__tests__/fixtures/versioning.fixtures";
import { StatusBarSync, describeSyncState } from "../StatusBarSync";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

function respondWith(body: Record<string, unknown>, status = 200) {
  server.use(
    http.get("*/api/v1/versioning/sync/status", () => HttpResponse.json(body, { status })),
  );
}

describe("describeSyncState", () => {
  it("says sync is off when no sync target is configured", () => {
    expect(describeSyncState(createSyncStatus({ is_configured: false }))).toEqual({
      label: "sync off",
      inSync: false,
    });
  });

  it("says sync is degraded when the status could not be computed reliably", () => {
    expect(describeSyncState(createSyncStatus({ is_degraded: true })).label).toBe("sync degraded");
  });

  it("counts changes that are waiting to be pushed", () => {
    expect(
      describeSyncState(createSyncStatus({ unprocessed_count: 4, last_pushed_at: minutesAgo(5) })),
    ).toEqual({ label: "4 unsynced", inSync: false });
  });

  it("reports the most recent of the last push and the last pull", () => {
    const state = describeSyncState(
      createSyncStatus({ last_pushed_at: minutesAgo(90), last_pulled_at: minutesAgo(10) }),
    );
    expect(state).toEqual({ label: "synced 10m ago", inSync: true });
  });

  it("says never synced when configured but nothing has been pushed or pulled", () => {
    expect(describeSyncState(createSyncStatus())).toEqual({
      label: "never synced",
      inSync: false,
    });
  });
});

describe("StatusBarSync", () => {
  it("shows nothing while the sync status is loading", () => {
    server.use(http.get("*/api/v1/versioning/sync/status", () => new Promise(() => {})));
    render(<StatusBarSync />);
    expect(screen.queryByTestId("statusbar-sync")).not.toBeInTheDocument();
    expect(screen.queryByText(/syncing/i)).not.toBeInTheDocument();
  });

  it("shows nothing when the sync status request fails", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    respondWith({ detail: "boom" }, 500);
    const queryClient = createTestQueryClient();
    render(<StatusBarSync />, { queryClient });
    // The request has failed (not merely still in flight) before absence is asserted
    await waitFor(() =>
      expect(queryClient.getQueryState(QUERY_KEYS.syncStatus)?.status).toBe("error"),
    );
    expect(screen.queryByTestId("statusbar-sync")).not.toBeInTheDocument();
    consoleError.mockRestore();
  });

  it("matches the sync status response: unsynced changes, no check icon", async () => {
    respondWith(createSyncStatus({ unprocessed_count: 3 }));
    render(<StatusBarSync />);
    const item = await screen.findByTestId("statusbar-sync");
    expect(item).toHaveClass("statusbar__item");
    expect(item).toHaveTextContent("3 unsynced");
    expect(item.querySelector("[data-icon]")).toBeNull();
  });

  it("matches the sync status response: last sync time with a check icon", async () => {
    respondWith(createSyncStatus({ last_pushed_at: minutesAgo(5) }));
    render(<StatusBarSync />);
    const item = await screen.findByTestId("statusbar-sync");
    await waitFor(() => expect(item).toHaveTextContent("synced 5m ago"));
    expect(item.querySelector("[data-icon='check']")).not.toBeNull();
  });

  it("matches the sync status response: sync off", async () => {
    respondWith(createSyncStatus({ is_configured: false }));
    render(<StatusBarSync />);
    expect(await screen.findByTestId("statusbar-sync")).toHaveTextContent("sync off");
  });
});
