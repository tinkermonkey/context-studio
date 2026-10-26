import { create } from "zustand";
import type { IconName } from "@tinkermonkey/heimdall-ui";

export interface PaletteAction {
  id: string;
  label: string;
  description?: string;
  icon?: IconName;
  shortcut?: string;
  onSelect: () => void;
}

interface CommandPaletteState {
  open: boolean;
  query: string;
  actions: PaletteAction[];
  openPalette: (query?: string) => void;
  /**
   * Hand text typed outside the palette (the topbar search) to it: opens the
   * palette with that text, or appends it to the query when already open, so
   * keystrokes that land before the palette input takes focus are kept.
   */
  typeIntoPalette: (text: string) => void;
  closePalette: () => void;
  togglePalette: () => void;
  /** Text typed into the palette; drives the server-side entity search. */
  setQuery: (query: string) => void;
  registerActions: (actions: PaletteAction[]) => void;
  unregisterActions: (ids: string[]) => void;
}

export const useCommandPaletteStore = create<CommandPaletteState>((set) => ({
  open: false,
  query: "",
  actions: [],
  openPalette: (query = "") => set({ open: true, query }),
  typeIntoPalette: (text) =>
    set((state) => ({ open: true, query: state.open ? state.query + text : text })),
  closePalette: () => set({ open: false, query: "" }),
  togglePalette: () =>
    set((state) => ({ open: !state.open, query: state.open ? "" : state.query })),
  setQuery: (query) => set({ query }),
  registerActions: (newActions) =>
    set((state) => {
      const existing = state.actions.filter((a) => !newActions.find((n) => n.id === a.id));
      return { actions: [...existing, ...newActions] };
    }),
  unregisterActions: (ids) =>
    set((state) => ({
      actions: state.actions.filter((a) => !ids.includes(a.id)),
    })),
}));
