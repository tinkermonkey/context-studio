import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Topbar } from "../Topbar";

vi.mock("@tanstack/react-router", () => ({
  useRouterState: vi.fn(),
}));

vi.mock("@/stores/commandPalette", () => ({
  useCommandPaletteStore: vi.fn(),
}));

vi.mock("@/stores/canvas", () => ({
  useCanvasStore: vi.fn(),
}));

vi.mock("@tinkermonkey/heimdall-ui", () => ({
  Topbar: ({ breadcrumbs, children }: any) => (
    <div data-testid="heimdall-topbar">
      <div data-testid="breadcrumbs">
        {breadcrumbs.map((crumb: any, idx: number) => (
          <span key={idx}>{crumb.label}</span>
        ))}
      </div>
      <div data-testid="topbar-children">{children}</div>
    </div>
  ),
}));

import * as routerModule from "@tanstack/react-router";
import * as paletteModule from "@/stores/commandPalette";
import * as canvasModule from "@/stores/canvas";

describe("Topbar", () => {
  const mockOpenPalette = vi.fn();
  const mockToggleDarkCanvas = vi.fn();

  beforeEach(() => {
    mockOpenPalette.mockClear();
    mockToggleDarkCanvas.mockClear();

    vi.mocked(routerModule.useRouterState).mockReturnValue({
      location: { pathname: "/app" },
    } as any);

    vi.mocked(paletteModule.useCommandPaletteStore).mockImplementation((selector) => {
      const state = {
        open: false,
        query: "",
        actions: [],
        openPalette: mockOpenPalette,
        closePalette: vi.fn(),
        togglePalette: vi.fn(),
        registerActions: vi.fn(),
        unregisterActions: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    vi.mocked(canvasModule.useCanvasStore).mockImplementation((selector) => {
      const state = { darkCanvas: false, toggleDarkCanvas: mockToggleDarkCanvas };
      return selector ? selector(state) : state;
    });
  });

  describe("breadcrumb mapping", () => {
    it("maps /app route to Dashboard breadcrumb", () => {
      vi.mocked(routerModule.useRouterState).mockReturnValue({
        location: { pathname: "/app" },
      } as any);

      render(<Topbar />);
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });

    it("maps /app/schema/classes route to Schema and Classes breadcrumbs", () => {
      vi.mocked(routerModule.useRouterState).mockReturnValue({
        location: { pathname: "/app/schema/classes" },
      } as any);

      render(<Topbar />);
      expect(screen.getByText("Schema")).toBeInTheDocument();
      expect(screen.getByText("Classes")).toBeInTheDocument();
    });

    it("maps /app/data/datasets route to Data and Datasets breadcrumbs", () => {
      vi.mocked(routerModule.useRouterState).mockReturnValue({
        location: { pathname: "/app/data/datasets" },
      } as any);

      render(<Topbar />);
      expect(screen.getByText("Data")).toBeInTheDocument();
      expect(screen.getByText("Datasets")).toBeInTheDocument();
    });

    it("maps /app/pipelines route to Pipelines and All Pipelines breadcrumbs", () => {
      vi.mocked(routerModule.useRouterState).mockReturnValue({
        location: { pathname: "/app/pipelines" },
      } as any);

      render(<Topbar />);
      expect(screen.getByText("Pipelines")).toBeInTheDocument();
      expect(screen.getByText("All Pipelines")).toBeInTheDocument();
    });

    it("maps /app/settings route to Settings breadcrumb", () => {
      vi.mocked(routerModule.useRouterState).mockReturnValue({
        location: { pathname: "/app/settings" },
      } as any);

      render(<Topbar />);
      expect(screen.getByText("Settings")).toBeInTheDocument();
    });

    it("displays pathname for unmapped routes", () => {
      vi.mocked(routerModule.useRouterState).mockReturnValue({
        location: { pathname: "/app/unknown/route" },
      } as any);

      render(<Topbar />);
      expect(screen.getByText("/app/unknown/route")).toBeInTheDocument();
    });
  });

  describe("search functionality", () => {
    it("opens command palette when search button is clicked", () => {
      render(<Topbar />);
      const searchButton = screen.getByTestId("topbar-palette-button");
      fireEvent.click(searchButton);
      expect(mockOpenPalette).toHaveBeenCalled();
    });

    it("renders search button with correct text", () => {
      render(<Topbar />);
      expect(screen.getByText("Search or run command…")).toBeInTheDocument();
    });

    it("renders keyboard shortcut hint", () => {
      render(<Topbar />);
      expect(screen.getByText("⌘K")).toBeInTheDocument();
    });
  });

  describe("dark mode toggle", () => {
    it("renders dark mode toggle button", () => {
      render(<Topbar />);
      expect(screen.getByTestId("dark-mode-toggle")).toBeInTheDocument();
    });

    it("calls toggleDarkCanvas when dark mode button is clicked", () => {
      render(<Topbar />);
      const darkModeButton = screen.getByTestId("dark-mode-toggle");
      fireEvent.click(darkModeButton);
      expect(mockToggleDarkCanvas).toHaveBeenCalledTimes(1);
    });

    it("sets aria-pressed to false when dark canvas is off", () => {
      vi.mocked(canvasModule.useCanvasStore).mockImplementation((selector) => {
        const state = { darkCanvas: false, toggleDarkCanvas: mockToggleDarkCanvas };
        return selector ? selector(state) : state;
      });

      render(<Topbar />);
      const darkModeButton = screen.getByTestId("dark-mode-toggle");
      expect(darkModeButton).toHaveAttribute("aria-pressed", "false");
    });

    it("sets aria-pressed to true when dark canvas is on", () => {
      vi.mocked(canvasModule.useCanvasStore).mockImplementation((selector) => {
        const state = { darkCanvas: true, toggleDarkCanvas: mockToggleDarkCanvas };
        return selector ? selector(state) : state;
      });

      render(<Topbar />);
      const darkModeButton = screen.getByTestId("dark-mode-toggle");
      expect(darkModeButton).toHaveAttribute("aria-pressed", "true");
    });

    it("displays light canvas label when dark mode is on", () => {
      vi.mocked(canvasModule.useCanvasStore).mockImplementation((selector) => {
        const state = { darkCanvas: true, toggleDarkCanvas: mockToggleDarkCanvas };
        return selector ? selector(state) : state;
      });

      render(<Topbar />);
      const darkModeButton = screen.getByTestId("dark-mode-toggle");
      expect(darkModeButton).toHaveAttribute("title", "Switch to light canvas");
    });

    it("displays dark canvas label when dark mode is off", () => {
      vi.mocked(canvasModule.useCanvasStore).mockImplementation((selector) => {
        const state = { darkCanvas: false, toggleDarkCanvas: mockToggleDarkCanvas };
        return selector ? selector(state) : state;
      });

      render(<Topbar />);
      const darkModeButton = screen.getByTestId("dark-mode-toggle");
      expect(darkModeButton).toHaveAttribute("title", "Switch to dark canvas");
    });
  });

  describe("topbar actions", () => {
    it("renders topbar actions container", () => {
      render(<Topbar />);
      const topbarActions = screen.getByTestId("topbar-children");
      expect(topbarActions.querySelector(".topbar-actions")).toBeInTheDocument();
    });

    it("renders all action buttons", () => {
      render(<Topbar />);
      expect(screen.getByTestId("topbar-palette-button")).toBeInTheDocument();
      expect(screen.getByTestId("dark-mode-toggle")).toBeInTheDocument();
      expect(screen.getByTitle("Activity")).toBeInTheDocument();
      expect(screen.getByTitle("Documentation")).toBeInTheDocument();
    });

    it("renders environment pill with main branch", () => {
      render(<Topbar />);
      expect(screen.getByText("main")).toBeInTheDocument();
    });
  });
});
