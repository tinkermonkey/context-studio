import { useRouterState } from "@tanstack/react-router";
import { Search, Bell, FileText } from "lucide-react";
import { useCommandPaletteStore } from "@/stores/commandPalette";

const ROUTE_LABELS: Record<string, string[]> = {
  "/app": ["Dashboard"],
  "/app/schema/taxonomies": ["Schema", "Taxonomies"],
  "/app/schema/schemes": ["Schema", "Concept Schemes"],
  "/app/schema/classes": ["Schema", "Classes"],
  "/app/schema/properties": ["Schema", "Properties"],
  "/app/schema/relationships": ["Schema", "Relationships"],
  "/app/data/individuals": ["Data", "Individuals"],
  "/app/data/datasets": ["Data", "Datasets"],
  "/app/pipelines": ["Pipelines", "All Pipelines"],
  "/app/pipelines/runs": ["Pipelines", "Run History"],
  "/app/pipelines/flavors": ["Pipelines", "Flavors"],
  "/app/reference/sources": ["External Reference", "Sources"],
  "/app/reference/workflows": ["External Reference", "Grounding Workflows"],
  "/app/settings": ["Configuration"],
  "/app/contact-sheet": ["Developer", "Contact Sheet"],
};

interface TopbarProps {
  workspaceName?: string;
}

export function Topbar({ workspaceName = "context-studio" }: TopbarProps) {
  const { location } = useRouterState();
  const openPalette = useCommandPaletteStore((s) => s.openPalette);
  const crumbs = ROUTE_LABELS[location.pathname] ?? [location.pathname];

  return (
    <header className="topbar">
      <button className="ws-chip" type="button">
        <span className="ws-chip-dot" />
        <span className="ws-chip-name">{workspaceName}</span>
      </button>
      <span style={{ color: "var(--shell-fg-3)", fontSize: "12px", margin: "0 4px" }}>/</span>
      <div className="crumbs">
        {crumbs.map((crumb, i) => (
          <span key={i}>
            {i > 0 && <span className="sep">/</span>}
            <span className={i === crumbs.length - 1 ? "last" : ""}>{crumb}</span>
          </span>
        ))}
      </div>

      <button className="topbar-palette" onClick={openPalette} type="button">
        <Search size={14} />
        <span>Search or run command…</span>
        <span className="kbd">⌘K</span>
      </button>

      <button className="topbar-ico" type="button" title="Activity">
        <Bell size={16} />
      </button>
      <button className="topbar-ico" type="button" title="Documentation">
        <FileText size={16} />
      </button>
      <span className="env-pill">
        <span className="dot" />
        main
      </span>
    </header>
  );
}
