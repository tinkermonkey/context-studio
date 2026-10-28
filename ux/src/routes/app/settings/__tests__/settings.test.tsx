import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createAppConfiguration,
  createMcpConnection,
} from "@/api/services/__tests__/fixtures/admin.fixtures";
import { SettingsPage } from "../../settings";

const server = setupServer(
  http.get("*/api/chat/status", () =>
    HttpResponse.json({
      model: "claude-sonnet-5-5",
      available: true,
      max_tool_rounds: 8,
      available_models: ["claude-sonnet-5-5", "claude-opus-4-7"],
    }),
  ),
);

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

// The Settings page renders a "General" tab with a config form plus three
// static summary ConfigTile cards (Backups, Performance, Telemetry). It is
// driven by a single endpoint: GET /api/v1/admin/configuration.
describe("Settings Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("renders skeleton placeholders during loading", async () => {
      let resolveRequest: () => void;
      const pending = new Promise<void>((resolve) => {
        resolveRequest = resolve;
      });

      server.use(
        http.get("*/api/v1/admin/configuration", async () => {
          await pending;
          return HttpResponse.json(createAppConfiguration());
        }),
      );

      const { container } = render(<SettingsPage />);

      // Skeletons render as <div className="skeleton"> (CSS-driven shimmer).
      // The loading layout renders 2 header skeletons, 5 form-row skeletons,
      // and 3 summary-tile skeletons = 10 total.
      const skeletons = container.querySelectorAll(".skeleton");
      expect(skeletons.length).toBe(10);

      resolveRequest!();
    });

    it("displays settings-page testid during loading", async () => {
      let resolveRequest: () => void;
      const pending = new Promise<void>((resolve) => {
        resolveRequest = resolve;
      });

      server.use(
        http.get("*/api/v1/admin/configuration", async () => {
          await pending;
          return HttpResponse.json(createAppConfiguration());
        }),
      );

      render(<SettingsPage />);

      expect(screen.getByTestId("settings-page")).toBeInTheDocument();

      resolveRequest!();
    });
  });

  // ========================================================================
  // Populated State: Page Root + Summary Tiles
  // ========================================================================
  describe("populated state", () => {
    it("displays settings-page testid in populated state", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json(createAppConfiguration())),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("settings-page")).toBeInTheDocument();
      });
    });

    it("renders the three summary config tiles when data loads", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () =>
          HttpResponse.json(
            createAppConfiguration({
              sections: {
                workspace: { display_name: "My Workspace", path: "/path/to/workspace" },
                chat: { model: "claude-3-sonnet" },
                embedding: { model_name: "sentence-transformers/all-MiniLM-L6-v2" },
              },
            }),
          ),
        ),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-backups")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-performance")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-telemetry")).toBeInTheDocument();
      });
    });

    it("renders the general configuration form populated from config values", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () =>
          HttpResponse.json(
            createAppConfiguration({
              sections: {
                workspace: { display_name: "My Workspace", path: "/path/to/workspace" },
                chat: { model: "claude-3-sonnet" },
                embedding: { model_name: "sentence-transformers/all-MiniLM-L6-v2" },
              },
            }),
          ),
        ),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("settings-general-form")).toBeInTheDocument();
      });

      // Config values are surfaced through the form inputs, not as plain text.
      expect(screen.getByDisplayValue("My Workspace")).toBeInTheDocument();
      expect(screen.getByDisplayValue("/path/to/workspace")).toBeInTheDocument();
      expect(screen.getByDisplayValue("claude-3-sonnet")).toBeInTheDocument();
      expect(
        screen.getByDisplayValue("sentence-transformers/all-MiniLM-L6-v2"),
      ).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Individual Summary Config Tiles
  // ========================================================================
  describe("individual config tiles", () => {
    it("displays backups config tile with correct testid", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json(createAppConfiguration())),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-backups")).toBeInTheDocument();
      });
    });

    it("displays performance config tile with correct testid", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json(createAppConfiguration())),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-performance")).toBeInTheDocument();
      });
    });

    it("displays telemetry config tile with correct testid", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json(createAppConfiguration())),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-telemetry")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Integrations tab
  // ========================================================================
  describe("integrations tab", () => {
    it("shows the MCP connection panel, fetched only once the tab is opened", async () => {
      const user = userEvent.setup();
      let mcpRequests = 0;
      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json(createAppConfiguration())),
        http.get("*/api/v1/admin/mcp", () => {
          mcpRequests += 1;
          return HttpResponse.json(createMcpConnection());
        }),
      );

      render(<SettingsPage />);
      await screen.findByTestId("settings-general-form");
      expect(screen.queryByTestId("mcp-connection-panel")).not.toBeInTheDocument();
      expect(mcpRequests).toBe(0);

      await user.click(screen.getByRole("tab", { name: /integrations/i }));

      expect(screen.getByTestId("mcp-connection-panel")).toBeInTheDocument();
      expect(await screen.findByTestId("mcp-connection-url")).toHaveValue(
        "http://127.0.0.1:8000/mcp",
      );
      expect(mcpRequests).toBe(1);
      expect(screen.queryByTestId("settings-general-form")).not.toBeInTheDocument();
    });
  });
});
