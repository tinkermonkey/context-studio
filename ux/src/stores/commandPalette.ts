import { create } from "zustand";

export interface PaletteAction {
  id: string;
  label: string;
  description?: string;
  icon?: React.ReactNode;
  shortcut?: string;
  onSelect: () => void;
}

interface CommandPaletteState {
  open: boolean;
  actions: PaletteAction[];
  openPalette: () => void;
  closePalette: () => void;
  togglePalette: () => void;
  registerActions: (actions: PaletteAction[]) => void;
  unregisterActions: (ids: string[]) => void;
}

export const useCommandPaletteStore = create<CommandPaletteState>((set) => ({
  open: false,
  actions: [],
  openPalette: () => set({ open: true }),
  closePalette: () => set({ open: false }),
  togglePalette: () => set((state) => ({ open: !state.open })),
  registerActions: (newActions) =>
    set((state) => {
      const existing = state.actions.filter(
        (a) => !newActions.find((n) => n.id === a.id)
      );
      return { actions: [...existing, ...newActions] };
    }),
  unregisterActions: (ids) =>
    set((state) => ({
      actions: state.actions.filter((a) => !ids.includes(a.id)),
    })),
}));
