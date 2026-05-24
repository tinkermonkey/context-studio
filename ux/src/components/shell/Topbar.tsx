import { useRouterState } from "@tanstack/react-router";
import type { TopbarProps } from "@tinkermonkey/heimdall-ui";
import { Search, Bell, FileText, Sun, Moon, ChevronDown } from "lucide-react";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useCanvasStore } from "@/stores/canvas";
import { getWorkspacePath } from "@/lib/workspaceStorage";

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
  "/app/versioning": ["Versioning"],
  "/app/settings": ["Settings"],
  "/app/contact-sheet": ["Developer", "Contact Sheet"],
};

function getWorkspaceName(): string {
  const path = getWorkspacePath();
  if (!path) return "workspace";
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  const name = parts[parts.length - 1] ?? "workspace";
  return name.replace(/\.[^.]+$/, "") || "workspace";
}

export function buildTopbarProps(): TopbarProps {
  const { location } = useRouterState();
  const openPalette = useCommandPaletteStore((s) => s.openPalette);
  const { darkCanvas, toggleDarkCanvas } = useCanvasStore();
  const crumbs = ROUTE_LABELS[location.pathname] ?? [location.pathname];
  const workspaceName = getWorkspaceName();

  const breadcrumbs = crumbs.map((label) => ({ label }));

  const children = (
    <>
      <button
        className="ws-chip"
        type="button"
        data-testid="workspace-chip"
        onClick={() => {
          // TODO: Open WorkspaceSwitcherDialog - will be wired in app.tsx
          console.log("Open workspace switcher");
        }}
        title="Switch workspace"
      >
        <span className="ws-chip-dot" />
        <span className="ws-chip-name">{workspaceName}</span>
        <ChevronDown size={11} />
      </button>
      <div className="topbar-actions">
        <button
          className="topbar-palette"
          data-testid="topbar-palette-button"
          onClick={() => openPalette()}
          type="button"
        >
          <Search size={14} />
          <span>Search or run command…</span>
          <span className="kbd">⌘K</span>
        </button>
        <button
          className="topbar-ico"
          type="button"
          data-testid="dark-mode-toggle"
          onClick={toggleDarkCanvas}
          title={darkCanvas ? "Switch to light canvas" : "Switch to dark canvas"}
          aria-pressed={darkCanvas}
        >
          {darkCanvas ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button className="topbar-ico" type="button" title="Activity">
          <Bell size={16} />
        </button>
        <button className="topbar-ico" type="button" title="Documentation">
          <FileText size={16} />
        </button>
      </div>
      <span className="env-pill">
        <span className="dot" />
        main
      </span>
    </>
  );

  return {
    breadcrumbs,
    children,
  };
}
