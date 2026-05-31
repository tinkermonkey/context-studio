import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createChangeHistory,
  createSyncStatus,
} from "@/api/services/__tests__/fixtures/versioning.fixtures";
import { VersioningPage } from "../../versioning";

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

describe("Versioning Page", () => {
  // ========================================================================
  // Page Structure
  // ========================================================================
  describe("page structure", () => {
    it("renders versioning page root", async () => {
      server.use(
        http.get("*/api/v1/versioning/changesets", () => HttpResponse.json([])),
        http.get("*/api/v1/versioning/changes", () => HttpResponse.json({ events: [], total: 0 })),
      );

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByTestId("versioning-page")).toBeInTheDocument();
      });
    });

    it("displays tabs for changesets, conflicts, and sync", async () => {
      server.use(
        http.get("*/api/v1/versioning/changesets", () => HttpResponse.json([])),
        http.get("*/api/v1/versioning/changes", () => HttpResponse.json({ events: [], total: 0 })),
      );

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByRole("tab", { name: /changesets/i })).toBeInTheDocument();
        expect(screen.getByRole("tab", { name: /conflict/i })).toBeInTheDocument();
        expect(screen.getByRole("tab", { name: /sync/i })).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Changeset Panel: States
  // ========================================================================
  describe("changeset panel states", () => {
    it("displays changeset panel on default tab with page root testid", async () => {
      server.use(
        http.get("*/api/v1/versioning/changesets", () => HttpResponse.json([])),
        http.get("*/api/v1/versioning/changes", () => HttpResponse.json({ events: [], total: 0 })),
      );

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByTestId("versioning-page")).toBeInTheDocument();
      });
    });

    it("loads and displays pending changes on page render", async () => {
      const mockChanges = createChangeHistory({
        events: [
          {
            id: "change-1",
            entity_id: "entity-1",
            entity_type: "taxonomy",
            operation: "create",
            new_state: { title: "Test Entity" },
            timestamp: new Date().toISOString(),
            processed: true,
          },
        ],
        total: 1,
      });

      server.use(
        http.get("*/api/v1/versioning/changesets", () => HttpResponse.json([])),
        http.get("*/api/v1/versioning/changes", () => HttpResponse.json(mockChanges)),
      );

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByTestId("changeset-panel")).toBeInTheDocument();
        expect(screen.getByText("Test Entity")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Sync Status Panel: States
  // ========================================================================
  describe("sync status panel states", () => {
    it("switches to sync tab when clicked", async () => {
      server.use(
        http.get("*/api/v1/versioning/sync/status", () => HttpResponse.json(createSyncStatus())),
        http.get("*/api/v1/versioning/changesets", () => HttpResponse.json([])),
        http.get("*/api/v1/versioning/changes", () => HttpResponse.json({ events: [], total: 0 })),
      );

      render(<VersioningPage />);

      const syncTab = screen.getByRole("tab", { name: /sync/i });
      await userEvent.click(syncTab);

      await waitFor(() => {
        expect(syncTab).toHaveAttribute("aria-selected", "true");
      });
    });
  });

  // ========================================================================
  // Conflict Resolver: States
  // ========================================================================
  describe("conflict resolver states", () => {
    it("renders conflict tab and shows empty state when no proposal selected", async () => {
      server.use(
        http.get("*/api/v1/versioning/changesets", () => HttpResponse.json([])),
        http.get("*/api/v1/versioning/changes", () => HttpResponse.json({ events: [], total: 0 })),
      );

      render(<VersioningPage />);

      const conflictTab = screen.getByRole("tab", { name: /conflict/i });
      await userEvent.click(conflictTab);

      await waitFor(() => {
        expect(screen.getByText(/no proposal selected/i)).toBeInTheDocument();
      });
    });
  });
});
