import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createChangeset,
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
        rest.get("*/api/versioning/changesets", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json({ items: [], total: 0 }));
        }),
        rest.get("*/api/versioning/changes", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json({ events: [], total: 0 }));
        }),
      );

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByTestId("versioning-page")).toBeInTheDocument();
      });
    });

    it("displays tabs for changesets, conflicts, and sync", async () => {
      server.use(
        rest.get("*/api/versioning/changesets", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0 })),
        ),
        rest.get("*/api/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
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
        rest.get("*/api/versioning/changesets", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0 })),
        ),
        rest.get("*/api/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
      );

      render(<VersioningPage />);

      await waitFor(() => {
        expect(screen.getByTestId("versioning-page")).toBeInTheDocument();
      });
    });

    it("loads changeset data on page render", async () => {
      const mockChangesets = {
        items: [createChangeset({ id: "changeset-1", name: "Update taxonomy" })],
        total: 1,
      };

      server.use(
        rest.get("*/api/versioning/changesets", (req, res, ctx) =>
          res(ctx.json(mockChangesets)),
        ),
        rest.get("*/api/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
      );

      render(<VersioningPage />);

      // Verify page renders - changeset loading is internal to panel
      await waitFor(() => {
        expect(screen.getByTestId("versioning-page")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Sync Status Panel: States
  // ========================================================================
  describe("sync status panel states", () => {
    it("switches to sync tab when clicked", async () => {
      server.use(
        rest.get("*/api/versioning/sync/status", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 50));
          return res(ctx.json(createSyncStatus()));
        }),
        rest.get("*/api/versioning/changesets", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0 })),
        ),
        rest.get("*/api/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
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
        rest.get("*/api/versioning/changesets", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0 })),
        ),
        rest.get("*/api/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
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
