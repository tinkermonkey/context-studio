import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { CommandPalette } from "../CommandPalette";
import * as commandPaletteStore from "@/stores/commandPalette";
import * as heimdallModule from "@tinkermonkey/heimdall-ui";
import * as keyboardShortcutModule from "@/hooks/useKeyboardShortcut";

vi.mock("@/stores/commandPalette", () => ({
  useCommandPaletteStore: vi.fn(),
}));

vi.mock("@/hooks/useKeyboardShortcut", () => ({
  useKeyboardShortcut: vi.fn(),
}));

vi.mock("@tinkermonkey/heimdall-ui", () => ({
  CommandPalette: vi.fn(() => <div data-testid="heimdall-command-palette" />),
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
    vi.mocked(heimdallModule.CommandPalette).mockClear();
    vi.clearAllMocks();
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
    const calls = vi.mocked(heimdallModule.CommandPalette).mock.calls;
    expect(calls[calls.length - 1][0]).toMatchObject({ isOpen: false });
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
    const calls = vi.mocked(heimdallModule.CommandPalette).mock.calls;
    expect(calls[calls.length - 1][0]).toMatchObject({ isOpen: true });
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      // @ts-ignore - Mock type assertion
      expect(call.commands).toHaveLength(1);
      // @ts-ignore - Mock type assertion
      expect(call.commands[0].label).toBe("Create Class");
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      // @ts-ignore - Mock type assertion
      expect(call.commands).toHaveLength(1);
      // @ts-ignore - Mock type assertion
      expect(call.commands[0].label).toBe("Edit Class");
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      // @ts-ignore - Mock type assertion
      expect(call.commands).toHaveLength(1);
      // @ts-ignore - Mock type assertion
      expect(call.commands[0].label).toBe("Create Class");
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      expect(call.commands).toHaveLength(3);
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      expect(call.commands).toHaveLength(0);
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      expect(call.commands).toHaveLength(0);
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      expect(call.onClose).toBe(mockClosePalette);
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      expect(call.placeholder).toBe("Search or run command…");
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
      const call = vi.mocked(heimdallModule.CommandPalette).mock.calls[0][0];
      // @ts-ignore - Mock type assertion
      expect(call.commands).toHaveLength(1);
      // @ts-ignore - Mock type assertion
      expect(call.commands[0].label).toBe("Create Class");
    });
  });

  describe("keyboard shortcuts", () => {
    it("integrates keyboard shortcuts for Cmd+K and Escape", () => {
      render(<CommandPalette />);

      // Verify Cmd+K shortcut is registered
      expect(vi.mocked(keyboardShortcutModule.useKeyboardShortcut)).toHaveBeenCalledWith(
        expect.objectContaining({
          key: "k",
          modifiers: ["meta"],
          onKeydown: mockTogglePalette,
        }),
      );

      // Verify Escape shortcut is registered
      expect(vi.mocked(keyboardShortcutModule.useKeyboardShortcut)).toHaveBeenCalledWith(
        expect.objectContaining({
          key: "Escape",
          onKeydown: mockClosePalette,
        }),
      );
    });
  });
});
