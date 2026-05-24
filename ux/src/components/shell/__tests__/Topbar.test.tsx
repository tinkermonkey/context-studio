import { describe, it, expect, vi, beforeEach } from "vitest";
import { buildTopbarProps } from "../Topbar";

vi.mock("@tanstack/react-router", () => ({
  useRouterState: vi.fn(),
  useNavigate: vi.fn(),
}));

vi.mock("@/stores/commandPalette", () => ({
  useCommandPaletteStore: vi.fn(),
}));

vi.mock("@/stores/canvas", () => ({
  useCanvasStore: vi.fn(),
}));

import * as routerModule from "@tanstack/react-router";
import * as paletteModule from "@/stores/commandPalette";
import * as canvasModule from "@/stores/canvas";

describe("Topbar", () => {
  const mockOpenPalette = vi.fn();
  const mockToggleDarkCanvas = vi.fn();
  const mockNavigate = vi.fn();

  beforeEach(() => {
    mockOpenPalette.mockClear();
    mockToggleDarkCanvas.mockClear();
    mockNavigate.mockClear();

    vi.mocked(routerModule.useNavigate).mockReturnValue(mockNavigate);
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
    it("returns Dashboard breadcrumb for /app route", () => {
      vi.mocked(routerModule.useRouterState).mockReturnValue({
        location: { pathname: "/app" },
      } as any);

      const props = buildTopbarProps();
      expect(props.breadcrumbs).toBeDefined();
      if (props.breadcrumbs) {
        expect(Array.isArray(props.breadcrumbs)).toBe(true);
        expect(props.breadcrumbs.length).toBeGreaterThan(0);
      }
    });

    it("returns breadcrumbs for nested routes", () => {
      vi.mocked(routerModule.useRouterState).mockReturnValue({
        location: { pathname: "/app/schema/classes" },
      } as any);

      const props = buildTopbarProps();
      expect(props.breadcrumbs).toBeDefined();
      if (props.breadcrumbs) {
        expect(Array.isArray(props.breadcrumbs)).toBe(true);
        expect(props.breadcrumbs.length).toBeGreaterThan(1);
      }
    });
  });

  describe("buildTopbarProps", () => {
    it("returns props object with breadcrumbs and children", () => {
      const props = buildTopbarProps();
      expect(props).toBeDefined();
      expect(props.breadcrumbs).toBeDefined();
      expect(props.children).toBeDefined();
    });
  });
});
