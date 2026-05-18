import { useEffect } from "react";
import { createFileRoute, Outlet, useNavigate, redirect } from "@tanstack/react-router";
import { ShellLayout } from "@tinkermonkey/heimdall-ui";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useCommandPaletteActions } from "@/hooks/useCommandPaletteActions";
import { createStaticPaletteActions } from "@/config/staticPaletteActions";
import { getWorkspacePath } from "@/lib/workspaceStorage";
import { Sidebar } from "@/components/shell/Sidebar";
import { Topbar } from "@/components/shell/Topbar";
import { Statusbar } from "@/components/shell/Statusbar";
import { Titlebar } from "@/components/shell/Titlebar";
import { CommandPalette } from "@/components/shell/CommandPalette";
import { useCommandPaletteStore } from "@/stores/commandPalette";

export const Route = createFileRoute("/app")({
  beforeLoad: () => {
    const workspacePath = getWorkspacePath();
    if (!workspacePath) {
      throw redirect({ to: "/welcome" });
    }
  },
  component: AppShell,
});

const NAV_ACTIONS = [
  { id: "nav-dashboard", label: "Dashboard", description: "Go to dashboard", to: "/app" },
  {
    id: "nav-taxonomies",
    label: "Taxonomies",
    description: "Schema → Taxonomies",
    to: "/app/schema/taxonomies",
  },
  {
    id: "nav-schemes",
    label: "Concept Schemes",
    description: "Schema → Concept Schemes",
    to: "/app/schema/schemes",
  },
  {
    id: "nav-classes",
    label: "Classes",
    description: "Schema → Classes",
    to: "/app/schema/classes",
  },
  {
    id: "nav-properties",
    label: "Properties",
    description: "Schema → Properties",
    to: "/app/schema/properties",
  },
  {
    id: "nav-relationships",
    label: "Relationships",
    description: "Schema → Relationships",
    to: "/app/schema/relationships",
  },
  {
    id: "nav-individuals",
    label: "Individuals",
    description: "Data → Individuals",
    to: "/app/data/individuals",
  },
  {
    id: "nav-datasets",
    label: "Datasets",
    description: "Data → Datasets",
    to: "/app/data/datasets",
  },
  {
    id: "nav-pipelines",
    label: "Pipelines",
    description: "Pipelines → All pipelines",
    to: "/app/pipelines",
  },
  {
    id: "nav-pipeline-runs",
    label: "Pipeline Run History",
    description: "Pipelines → Run history",
    to: "/app/pipelines/runs",
  },
  {
    id: "nav-reference-sources",
    label: "Reference Sources",
    description: "External Reference → Sources",
    to: "/app/reference/sources",
  },
  {
    id: "nav-settings",
    label: "Configuration",
    description: "Go to settings",
    to: "/app/settings",
  },
] as const;

function AppShell() {
  const { registerActions, unregisterActions } = useCommandPaletteStore();
  const navigate = useNavigate();
  useCommandPaletteActions();

  useEffect(() => {
    const navActions = NAV_ACTIONS.map((item) => ({
      id: item.id,
      label: item.label,
      description: item.description,
      onSelect: () => navigate({ to: item.to }),
    }));
    registerActions(navActions);
    return () => {
      unregisterActions(navActions.map((a) => a.id));
    };
  }, [registerActions, unregisterActions, navigate]);

  useEffect(() => {
    const staticActions = createStaticPaletteActions();
    registerActions(staticActions);
    return () => {
      unregisterActions(staticActions.map((a) => a.id));
    };
  }, [registerActions, unregisterActions]);

  return (
    <div className="desktop-frame">
      <Titlebar />
      <ShellLayout>
        <Sidebar />
        <div className="workspace">
          <Topbar />
          <div className="canvas-area">
            <div className="canvas-scroll">
              <div className="canvas-inner">
                <ErrorBoundary>
                  <Outlet />
                </ErrorBoundary>
              </div>
            </div>
          </div>
        </div>
      </ShellLayout>
      <Statusbar />
      <CommandPalette />
    </div>
  );
}
