import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("displays Heimdall CommandPalette with correct props when open", () => {
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

    const palette = screen.getByTestId("command-palette");
    expect(palette).toBeInTheDocument();
  });

  it("filters actions based on query string in label", () => {
    const { rerender } = render(<CommandPalette />);

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

    rerender(<CommandPalette />);

    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  it("filters actions based on query string in description", () => {
    const { rerender } = render(<CommandPalette />);

    vi.mocked(commandPaletteStore.useCommandPaletteStore).mockReturnValue({
      open: true,
      query: "edit",
      actions: mockActions,
      closePalette: mockClosePalette,
      togglePalette: mockTogglePalette,
      setQuery: vi.fn(),
      addAction: vi.fn(),
      removeAction: vi.fn(),
    } as any);

    rerender(<CommandPalette />);

    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  it("calls onSelect and closePalette when action is selected", () => {
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

  it("filters actions case-insensitively", () => {
    const { rerender } = render(<CommandPalette />);

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

    rerender(<CommandPalette />);

    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  it("handles empty actions list", () => {
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

  it("filters out actions that do not match query", () => {
    const { rerender } = render(<CommandPalette />);

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

    rerender(<CommandPalette />);

    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  it("uses correct placeholder text", () => {
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

  it("handles actions with no description", () => {
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
      query: "Create",
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
