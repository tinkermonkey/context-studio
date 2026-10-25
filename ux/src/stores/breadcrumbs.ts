import { create } from "zustand";

export interface PageBreadcrumb {
  label: string;
  /** Path to navigate to; omit for the current page. */
  to?: string;
}

interface BreadcrumbState {
  /** Breadcrumbs a page supplies for its own path (entity pages follow the hierarchy). */
  crumbs: PageBreadcrumb[] | null;
  /** The pathname the crumbs belong to, so a stale set never shows on another page. */
  pathname: string | null;
  setCrumbs: (pathname: string, crumbs: PageBreadcrumb[]) => void;
  clearCrumbs: (pathname: string) => void;
}

export const useBreadcrumbStore = create<BreadcrumbState>((set) => ({
  crumbs: null,
  pathname: null,
  setCrumbs: (pathname, crumbs) => set({ pathname, crumbs }),
  clearCrumbs: (pathname) =>
    set((state) => (state.pathname === pathname ? { pathname: null, crumbs: null } : state)),
}));
