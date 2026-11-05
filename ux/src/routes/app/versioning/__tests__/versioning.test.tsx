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

const emptyChanges = () =>
  http.get("*/api/v1/versioning/changes", () => HttpResponse.json({ events: [], total: 0 }));

describe("Versioning Page", () => {
  // ========================================================================
  // Page Structure
  // ========================================================================
  describe("page structure", () => {
    it("renders versioning page root", async () => {
      server.use(emptyChanges());

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByTestId("versioning-page")).toBeInTheDocument();
      });
    });

    it("displays tabs for changes and sync only", async () => {
      server.use(emptyChanges());

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByRole("tab", { name: /changes/i })).toBeInTheDocument();
        expect(screen.getByRole("tab", { name: /sync/i })).toBeInTheDocument();
      });
      expect(screen.queryByRole("tab", { name: /changesets/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("tab", { name: /conflict/i })).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // Change History: States
  // ========================================================================
  describe("change history states", () => {
    it("shows the empty state when no changes are recorded", async () => {
      server.use(emptyChanges());

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByText(/no changes recorded yet/i)).toBeInTheDocument();
      });
      expect(screen.queryByTestId("change-history-list")).not.toBeInTheDocument();
    });

    it("loads and displays change events as a read-only list", async () => {
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

      server.use(http.get("*/api/v1/versioning/changes", () => HttpResponse.json(mockChanges)));

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByTestId("change-history-list")).toBeInTheDocument();
        expect(screen.getByText("Test Entity")).toBeInTheDocument();
      });
      const list = screen.getByTestId("change-history-list");
      expect(list).toHaveAttribute("role", "list");
      expect(screen.getByTestId("change-history-row-change-1")).toHaveAttribute("role", "listitem");
      expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // Sync Status Panel: States
  // ========================================================================
  describe("sync status panel states", () => {
    it("switches to sync tab when clicked", async () => {
      server.use(
        http.get("*/api/v1/versioning/sync/status", () => HttpResponse.json(createSyncStatus())),
        emptyChanges(),
      );

      render(<VersioningPage />);

      const syncTab = screen.getByRole("tab", { name: /sync/i });
      await userEvent.click(syncTab);

      await waitFor(() => {
        expect(syncTab).toHaveAttribute("aria-selected", "true");
      });
    });
  });
});
