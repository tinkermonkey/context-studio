import { create } from "zustand";

export type NavigatorMode = "schema" | "data";

interface NavigatorState {
  /** Navigator rows (taxonomy, scheme and, in Data mode, class ids) the user has open. */
  expandedIds: ReadonlySet<string>;
  /** Schema | Data, kept so drilling down in Data mode stays in Data mode. */
  mode: NavigatorMode;
  setExpanded: (id: string, open: boolean) => void;
  /** Open these rows (e.g. the current entity's ancestors), keeping the rest. */
  expand: (ids: string[]) => void;
  setMode: (mode: NavigatorMode) => void;
}

/**
 * The Navigator's state, shared by every page that shows it, so moving
 * between pages (and page kinds) keeps the tree as the user left it.
 */
export const useNavigatorStore = create<NavigatorState>((set) => ({
  expandedIds: new Set<string>(),
  mode: "schema",
  setExpanded: (id, open) =>
    set((state) => {
      if (state.expandedIds.has(id) === open) return state;
      const next = new Set(state.expandedIds);
      if (open) next.add(id);
      else next.delete(id);
      return { expandedIds: next };
    }),
  expand: (ids) =>
    set((state) => {
      if (ids.every((id) => state.expandedIds.has(id))) return state;
      return { expandedIds: new Set([...state.expandedIds, ...ids]) };
    }),
  setMode: (mode) => set((state) => (state.mode === mode ? state : { mode })),
}));
