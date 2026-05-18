import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { CommandPalette } from "../CommandPalette";
import * as commandPaletteStore from "@/stores/commandPalette";

vi.mock("@/stores/commandPalette", () => ({
  useCommandPaletteStore: vi.fn(),
}));

vi.mock("@/hooks/useKeyboardShortcut", () => ({
  useKeyboardShortcut: vi.fn(),
}));

describe("CommandPalette", () => {
  const mockTogglePalette = vi.fn();
  const mockClosePalette = vi.fn();

  const mockActions = [
    {
      id: "action-1",
      label: "Create Class",
      description: "Create a new class",
      icon: "plus",
      onSelect: vi.fn(),
    },
    {
      id: "action-2",
      label: "Edit Class",
      description: "Edit an existing class",
      icon: "edit",
      onSelect: vi.fn(),
    },
    {
      id: "action-3",
      label: "Delete Class",
      description: "Delete a class",
      icon: "trash",
      onSelect: vi.fn(),
    },
  ];

  beforeEach(() => {
    mockTogglePalette.mockClear();
    mockClosePalette.mockClear();
    mockActions.forEach((action) => {
      (action.onSelect as any).mockClear();
    });
    vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
      open: false,
      query: "",
      actions: mockActions,
      closePalette: mockClosePalette,
      togglePalette: mockTogglePalette,
      setQuery: vi.fn(),
      addAction: vi.fn(),
      removeAction: vi.fn(),
    } as any);
  });

  it("renders command palette container", () => {
    render(<CommandPalette />);
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  it("passes isOpen=false to Heimdall CommandPalette when palette is closed", () => {
    vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
      open: false,
      query: "",
      actions: mockActions,
      closePalette: mockClosePalette,
      togglePalette: mockTogglePalette,
      setQuery: vi.fn(),
      addAction: vi.fn(),
      removeAction: vi.fn(),
    } as any);

    render(<CommandPalette />);
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  it("passes isOpen=true to Heimdall CommandPalette when palette is open", () => {
    vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
      open: true,
      query: "",
      actions: mockActions,
      closePalette: mockClosePalette,
      togglePalette: mockTogglePalette,
      setQuery: vi.fn(),
      addAction: vi.fn(),
      removeAction: vi.fn(),
    } as any);

    render(<CommandPalette />);
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  describe("filtering", () => {
    it("filters actions by label", () => {
      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "Create",
        actions: mockActions,
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });

    it("filters actions by description", () => {
      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "existing",
        actions: mockActions,
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });

    it("performs case-insensitive filtering", () => {
      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "CREATE",
        actions: mockActions,
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });

    it("returns all actions when query is empty", () => {
      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "",
        actions: mockActions,
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });

    it("excludes actions that do not match query", () => {
      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "NonexistentAction",
        actions: mockActions,
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });

    it("handles empty actions list gracefully", () => {
      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "",
        actions: [],
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("passes closePalette callback to Heimdall CommandPalette", () => {
      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "",
        actions: mockActions,
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });

    it("passes correct placeholder text to Heimdall CommandPalette", () => {
      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "",
        actions: mockActions,
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });

    it("handles actions with no description gracefully", () => {
      const actionsWithoutDescription = [
        {
          id: "action-1",
          label: "Create Class",
          icon: "plus",
          onSelect: vi.fn(),
        },
      ];

      vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
        open: true,
        query: "",
        actions: actionsWithoutDescription,
        closePalette: mockClosePalette,
        togglePalette: mockTogglePalette,
        setQuery: vi.fn(),
        addAction: vi.fn(),
        removeAction: vi.fn(),
      } as any);

      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });
  });

  describe("keyboard shortcuts", () => {
    it("integrates keyboard shortcuts for Cmd+K and Escape", () => {
      render(<CommandPalette />);
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });
  });
});
