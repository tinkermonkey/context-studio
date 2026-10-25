import { useEffect } from "react";
import { useBreadcrumbStore, type PageBreadcrumb } from "@/stores/breadcrumbs";

/**
 * Supply the shell's breadcrumbs for the page at `pathname` while it is
 * mounted (e.g. an entity page's place in the hierarchy). Pass null until the
 * labels are known; the shell falls back to its static labels meanwhile.
 */
export function usePageBreadcrumbs(pathname: string, crumbs: PageBreadcrumb[] | null) {
  const setCrumbs = useBreadcrumbStore((s) => s.setCrumbs);
  const clearCrumbs = useBreadcrumbStore((s) => s.clearCrumbs);
  const key = crumbs ? JSON.stringify(crumbs) : null;

  useEffect(() => {
    if (key === null) return;
    setCrumbs(pathname, JSON.parse(key) as PageBreadcrumb[]);
    return () => clearCrumbs(pathname);
  }, [pathname, key, setCrumbs, clearCrumbs]);
}
