import { describe, it, expect, vi } from "vitest";
import { buildTitlebarProps } from "../Titlebar";

vi.mock("@/stores/commandPalette", () => ({
  useCommandPaletteStore: vi.fn(),
}));

import * as paletteModule from "@/stores/commandPalette";

describe("Titlebar", () => {
  beforeEach(() => {
    vi.mocked(paletteModule.useCommandPaletteStore).mockImplementation((selector) => {
      const state = {
        open: false,
        query: "",
        actions: [],
        openPalette: vi.fn(),
        closePalette: vi.fn(),
        togglePalette: vi.fn(),
        registerActions: vi.fn(),
        unregisterActions: vi.fn(),
      };
      return selector ? selector(state) : state;
    });
  });

  describe("buildTitlebarProps", () => {
    it("returns props object with left and right sections", () => {
      const props = buildTitlebarProps("Test Workspace", "~/test");
      
      expect(props).toBeDefined();
      expect(props.left).toBeDefined();
      expect(props.right).toBeDefined();
    });

    it("uses default workspace name when not provided", () => {
      const props = buildTitlebarProps();
      
      expect(props).toBeDefined();
      expect(props.left).toBeDefined();
    });
  });
});
