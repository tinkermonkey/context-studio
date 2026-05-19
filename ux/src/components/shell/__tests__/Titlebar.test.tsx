import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Titlebar } from "../Titlebar";

vi.mock("@/stores/commandPalette", () => ({
  useCommandPaletteStore: vi.fn(),
}));

vi.mock("@tinkermonkey/heimdall-ui", () => ({
  Titlebar: ({ left, right }: any) => (
    <div data-testid="heimdall-titlebar">
      <div data-testid="titlebar-left">{left}</div>
      <div data-testid="titlebar-right">{right}</div>
    </div>
  ),
}));

import * as paletteModule from "@/stores/commandPalette";

describe("Titlebar", () => {
  const mockOpenPalette = vi.fn();

  beforeEach(() => {
    mockOpenPalette.mockClear();

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
  });

  describe("workspace display", () => {
    it("renders default workspace name", () => {
      render(<Titlebar />);
      expect(screen.getByText("Context Studio")).toBeInTheDocument();
    });

    it("renders custom workspace name when provided", () => {
      render(<Titlebar workspaceName="My Workspace" />);
      expect(screen.getByText("My Workspace")).toBeInTheDocument();
    });

    it("renders default workspace path", () => {
      render(<Titlebar />);
      expect(screen.getByText("~/Projects/context-studio")).toBeInTheDocument();
    });

    it("renders custom workspace path when provided", () => {
      render(<Titlebar workspacePath="/custom/path" />);
      expect(screen.getByText("/custom/path")).toBeInTheDocument();
    });

    it("renders workspace separator", () => {
      render(<Titlebar />);
      expect(screen.getByText("—")).toBeInTheDocument();
    });
  });

  describe("workspace selector button", () => {
    it("renders workspace selector button", () => {
      render(<Titlebar />);
      const wsButton = screen.getByTitle("Switch workspace");
      expect(wsButton).toBeInTheDocument();
    });

    it("renders folder icon in workspace selector", () => {
      render(<Titlebar />);
      const wsButton = screen.getByTitle("Switch workspace");
      expect(wsButton.querySelector("svg")).toBeInTheDocument();
    });

    it("renders chevron down icon in workspace selector", () => {
      render(<Titlebar />);
      const wsButton = screen.getByTitle("Switch workspace");
      const svgs = wsButton.querySelectorAll("svg");
      expect(svgs.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe("titlebar app display", () => {
    it("renders titlebar-app container with correct class", () => {
      render(<Titlebar />);
      const titlebarApp = screen.getByText("Context Studio").closest(".titlebar-app");
      expect(titlebarApp).toHaveClass("titlebar-app");
    });

    it("renders titlebar-ws button with correct class", () => {
      render(<Titlebar />);
      const wsButton = screen.getByTitle("Switch workspace");
      expect(wsButton).toHaveClass("titlebar-ws");
    });
  });

  describe("command palette button", () => {
    it("renders command palette button", () => {
      render(<Titlebar />);
      const paletteButton = screen.getByTitle("Command palette (⌘K)");
      expect(paletteButton).toBeInTheDocument();
    });

    it("calls openPalette when palette button is clicked", () => {
      render(<Titlebar />);
      const paletteButton = screen.getByTitle("Command palette (⌘K)");
      fireEvent.click(paletteButton);
      expect(mockOpenPalette).toHaveBeenCalledTimes(1);
    });

    it("renders keyboard shortcut hint in palette button", () => {
      render(<Titlebar />);
      const kbd = screen.getByText("⌘K");
      expect(kbd).toHaveClass("kbd-mini");
    });

    it("renders palette button with correct class", () => {
      render(<Titlebar />);
      const paletteButton = screen.getByTitle("Command palette (⌘K)");
      expect(paletteButton).toHaveClass("titlebar-btn");
    });
  });

  describe("titlebar layout", () => {
    it("renders left section with workspace info", () => {
      render(<Titlebar />);
      const left = screen.getByTestId("titlebar-left");
      expect(left.querySelector(".titlebar-app")).toBeInTheDocument();
    });

    it("renders right section with action buttons", () => {
      render(<Titlebar />);
      const right = screen.getByTestId("titlebar-right");
      expect(right.querySelector(".titlebar-actions")).toBeInTheDocument();
    });

    it("renders heimdall titlebar", () => {
      render(<Titlebar />);
      expect(screen.getByTestId("heimdall-titlebar")).toBeInTheDocument();
    });
  });

  describe("props combinations", () => {
    it("renders with both custom workspace name and path", () => {
      render(<Titlebar workspaceName="Dev" workspacePath="/dev/workspace" />);
      expect(screen.getByText("Dev")).toBeInTheDocument();
      expect(screen.getByText("/dev/workspace")).toBeInTheDocument();
    });

    it("renders with only custom workspace name", () => {
      render(<Titlebar workspaceName="Production" />);
      expect(screen.getByText("Production")).toBeInTheDocument();
      expect(screen.getByText("~/Projects/context-studio")).toBeInTheDocument();
    });

    it("renders with only custom workspace path", () => {
      render(<Titlebar workspacePath="/data" />);
      expect(screen.getByText("Context Studio")).toBeInTheDocument();
      expect(screen.getByText("/data")).toBeInTheDocument();
    });
  });
});
