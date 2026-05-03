/**
 * Interchange Sidebar
 *
 * Navigation sidebar for the interchange (import/export) module
 */

import { Link } from "@tanstack/react-router";
import { CsSidebar, CsSidebarTitle } from "@/components/layout/cs_sidebar";

interface InterchangeSidebarProps {
  currentSection?: "export" | "import" | "runs";
}

export function InterchangeSidebar({
  currentSection = "runs",
}: InterchangeSidebarProps) {
  const getLinkClass = (section: string) =>
    `block px-4 py-2 rounded transition ${
      currentSection === section
        ? "bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-100 font-semibold"
        : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
    }`;

  return (
    <CsSidebar>
      <CsSidebarTitle>Interchange</CsSidebarTitle>
      <nav className="mt-4 space-y-2">
        <Link
          to="/app/interchange"
          className={getLinkClass("runs")}
          activeProps={{ className: getLinkClass("runs") }}
        >
          Recent Runs
        </Link>
        <Link
          to="/app/interchange/export"
          className={getLinkClass("export")}
          activeProps={{ className: getLinkClass("export") }}
        >
          Export
        </Link>
        <Link
          to="/app/interchange/import"
          className={getLinkClass("import")}
          activeProps={{ className: getLinkClass("import") }}
        >
          Import
        </Link>
      </nav>
    </CsSidebar>
  );
}
