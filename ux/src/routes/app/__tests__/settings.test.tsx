import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { SettingsPage } from "../settings";

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

// This file covers the Settings page shell: structure, error/retry handling,
// empty config, and how the General-tab form surfaces config values. The
// page is driven by GET /api/v1/admin/configuration and persists edits via
// PATCH on blur. The summary-tile coverage lives in
// src/routes/app/settings/__tests__/settings.test.tsx; here we focus on the
// behaviors unique to the shell.
describe("Settings Page", () => {
  // ========================================================================
  // Page Structure
  // ========================================================================
  describe("page structure", () => {
    it("renders settings page root with testid", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () =>
          HttpResponse.json({
            sections: {
              workspace: { display_name: "My Workspace", path: "/workspace" },
              llm: { provider: "anthropic", model: "claude-3-opus" },
              embedding: { model_name: "all-MiniLM-L6-v2", vector_dimensions: 384 },
            },
          }),
        ),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("settings-page")).toBeInTheDocument();
      });
    });

    it("displays page title heading", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json({ sections: {} })),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
      });
    });

    it("renders the general tab with its form and summary tiles", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () =>
          HttpResponse.json({
            sections: {
              workspace: { display_name: "My Workspace", path: "/workspace" },
              llm: { provider: "anthropic" },
              embedding: { model_name: "all-MiniLM-L6-v2" },
            },
          }),
        ),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("settings-general-form")).toBeInTheDocument();
      });

      // Summary tiles in the right column.
      expect(screen.getByTestId("config-tile-backups")).toBeInTheDocument();
      expect(screen.getByTestId("config-tile-performance")).toBeInTheDocument();
      expect(screen.getByTestId("config-tile-telemetry")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays skeleton placeholders while data is fetching", async () => {
      let resolveRequest: () => void;
      const pending = new Promise<void>((resolve) => {
        resolveRequest = resolve;
      });

      server.use(
        http.get("*/api/v1/admin/configuration", async () => {
          await pending;
          return HttpResponse.json({ sections: {} });
        }),
      );

      const { container } = render(<SettingsPage />);

      // Skeletons render as <div className="skeleton">: 2 header + 5 form-row
      // + 3 summary-tile = 10 total.
      await waitFor(() => {
        const skeletons = container.querySelectorAll(".skeleton");
        expect(skeletons.length).toBe(10);
      });

      resolveRequest!();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner when API request fails", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () =>
          HttpResponse.json({ detail: "Server error" }, { status: 500 }),
        ),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByText("Failed to load settings")).toBeInTheDocument();
      });
    });

    it("provides retry button on error and recovers after retry", async () => {
      let callCount = 0;

      server.use(
        http.get("*/api/v1/admin/configuration", () => {
          callCount++;
          if (callCount === 1) {
            return HttpResponse.json({ detail: "Server error" }, { status: 500 });
          }
          return HttpResponse.json({
            sections: {
              workspace: { display_name: "My Workspace", path: "/workspace" },
            },
          });
        }),
      );

      render(<SettingsPage />);

      const retryButton = await screen.findByRole("button", { name: /retry/i });
      expect(retryButton).toBeInTheDocument();
      await userEvent.click(retryButton);

      // After retry succeeds, the general form renders.
      await waitFor(() => {
        expect(screen.getByTestId("settings-general-form")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("renders the page with empty config sections", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json({ sections: {} })),
      );

      render(<SettingsPage />);

      // The form still renders, with blank inputs, and the summary tiles persist.
      await waitFor(() => {
        expect(screen.getByTestId("settings-general-form")).toBeInTheDocument();
      });
      expect(screen.getByTestId("config-tile-backups")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Populated Form Values
  // ========================================================================
  describe("populated form", () => {
    it("surfaces workspace, llm, and embedding config through form inputs", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () =>
          HttpResponse.json({
            sections: {
              workspace: { display_name: "My Workspace", path: "/workspace" },
              llm: { provider: "anthropic", model: "claude-3-opus" },
              embedding: { model_name: "all-MiniLM-L6-v2" },
            },
          }),
        ),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByDisplayValue("My Workspace")).toBeInTheDocument();
      });

      expect(screen.getByDisplayValue("/workspace")).toBeInTheDocument();
      expect(screen.getByDisplayValue("claude-3-opus")).toBeInTheDocument();
      expect(screen.getByDisplayValue("all-MiniLM-L6-v2")).toBeInTheDocument();
    });

    it("reflects a different LLM model in the model input", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () =>
          HttpResponse.json({
            sections: {
              workspace: { display_name: "My Workspace", path: "/workspace" },
              llm: { provider: "openai", model: "gpt-4" },
            },
          }),
        ),
      );

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByDisplayValue("gpt-4")).toBeInTheDocument();
      });

      // The provider select reflects the configured provider.
      expect(screen.getByTestId("settings-llm-provider-select")).toHaveValue("openai");
    });
  });
});
