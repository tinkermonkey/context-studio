import { create } from "zustand";

interface NavigatorState {
  /** Navigator rows (taxonomy and scheme ids) the user has open. */
  expandedIds: ReadonlySet<string>;
  setExpanded: (id: string, open: boolean) => void;
  /** Open these rows (e.g. the current entity's ancestors), keeping the rest. */
  expand: (ids: string[]) => void;
}

/**
 * The Navigator's expanded rows, shared by every page that shows it, so moving
 * between pages (and page kinds) keeps the tree as the user left it.
 */
export const useNavigatorStore = create<NavigatorState>((set) => ({
  expandedIds: new Set<string>(),
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
}));
