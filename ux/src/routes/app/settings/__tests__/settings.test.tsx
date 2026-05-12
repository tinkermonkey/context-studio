import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { createAppConfiguration } from "@/api/services/__tests__/fixtures/admin.fixtures";
import { SettingsPage } from "../../settings";

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

describe("Settings Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("renders 6 skeleton tiles during loading", async () => {
      server.use(
        rest.get("*/api/admin/config", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createAppConfiguration()));
        }),
      );

      const { container } = render(<SettingsPage />);

      const skeletonElements = container.querySelectorAll(
        "div[style*='animation: skeleton-shimmer']",
      );
      expect(skeletonElements.length).toBeGreaterThanOrEqual(6);
    });

    it("displays settings-page testid during loading", async () => {
      server.use(
        rest.get("*/api/admin/config", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createAppConfiguration()));
        }),
      );

      render(<SettingsPage />);

      expect(screen.getByTestId("settings-page")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Populated State: Page Root
  // ========================================================================
  describe("populated state", () => {
    it("displays settings-page testid in populated state", async () => {
      const mockConfig = createAppConfiguration();

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("settings-page")).toBeInTheDocument();
      });
    });

    it("renders all 6 config tiles when data loads", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          workspace: {
            display_name: "My Workspace",
            path: "/path/to/workspace",
          },
          llm: {
            provider: "anthropic",
            model: "claude-3-sonnet",
          },
          embedding: {
            model_name: "sentence-transformers/all-MiniLM-L6-v2",
            vector_dimensions: 384,
          },
          nlp: {
            model_name: "en_core_web_sm",
          },
          reference_sources: {
            enabled: true,
          },
          sync: {
            target_type: "local",
            path: "/sync/path",
          },
        },
      });

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-workspace")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-llm")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-embedding")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-nlp")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-reference-sources")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-sync")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Individual Config Tiles
  // ========================================================================
  describe("individual config tiles", () => {
    it("displays workspace config tile with correct testid", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          workspace: { display_name: "Test", path: "/test" },
        },
      });

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-workspace")).toBeInTheDocument();
      });
    });

    it("displays llm config tile with correct testid", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          llm: {
            provider: "anthropic",
            model: "claude-3-sonnet",
          },
        },
      });

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-llm")).toBeInTheDocument();
      });
    });

    it("displays embedding config tile with correct testid", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          embedding: {
            model_name: "sentence-transformers/all-MiniLM-L6-v2",
            vector_dimensions: 384,
          },
        },
      });

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-embedding")).toBeInTheDocument();
      });
    });

    it("displays nlp config tile with correct testid", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          nlp: {
            model_name: "en_core_web_sm",
          },
        },
      });

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-nlp")).toBeInTheDocument();
      });
    });

    it("displays reference-sources config tile with correct testid", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          reference_sources: {
            enabled: true,
          },
        },
      });

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-reference-sources")).toBeInTheDocument();
      });
    });

    it("displays sync config tile with correct testid", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          sync: {
            target_type: "local",
            path: "/sync/path",
          },
        },
      });

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-sync")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Config Tile Display Order
  // ========================================================================
  describe("config tile display order", () => {
    it("displays all config tiles in correct order", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          workspace: { display_name: "Workspace", path: "/path" },
          llm: { provider: "anthropic", model: "claude-3" },
          embedding: { model_name: "model", vector_dimensions: 384 },
          nlp: { model_name: "nlp-model" },
          reference_sources: { enabled: true },
          sync: { target_type: "local", path: "/sync" },
        },
      });

      server.use(rest.get("*/api/admin/config", (req, res, ctx) => res(ctx.json(mockConfig))));

      render(<SettingsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("config-tile-workspace")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-llm")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-embedding")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-nlp")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-reference-sources")).toBeInTheDocument();
        expect(screen.getByTestId("config-tile-sync")).toBeInTheDocument();
      });
    });
  });
});
