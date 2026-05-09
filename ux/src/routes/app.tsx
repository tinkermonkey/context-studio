import { useState, useEffect } from "react";
import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { Titlebar } from "@/components/shell/Titlebar";
import { Sidebar } from "@/components/shell/Sidebar";
import { Topbar } from "@/components/shell/Topbar";
import { Statusbar } from "@/components/shell/Statusbar";
import { WorkspaceErrorCard } from "@/components/workspace/WorkspaceErrorCard";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useWorkspaceStorage } from "@/hooks/useWorkspaceStorage";

export const Route = createFileRoute("/app")({
  component: AppShell,
});

const NAV_ACTIONS = [
  { id: "nav-dashboard", label: "Dashboard", description: "Go to dashboard", to: "/app" },
  { id: "nav-taxonomies", label: "Taxonomies", description: "Schema → Taxonomies", to: "/app/schema/taxonomies" },
  { id: "nav-schemes", label: "Concept Schemes", description: "Schema → Concept Schemes", to: "/app/schema/schemes" },
  { id: "nav-classes", label: "Classes", description: "Schema → Classes", to: "/app/schema/classes" },
  { id: "nav-properties", label: "Properties", description: "Schema → Properties", to: "/app/schema/properties" },
  { id: "nav-relationships", label: "Relationships", description: "Schema → Relationships", to: "/app/schema/relationships" },
  { id: "nav-individuals", label: "Individuals", description: "Data → Individuals", to: "/app/data/individuals" },
  { id: "nav-datasets", label: "Datasets", description: "Data → Datasets", to: "/app/data/datasets" },
  { id: "nav-pipelines", label: "Pipelines", description: "Pipelines → All pipelines", to: "/app/pipelines" },
  { id: "nav-pipeline-runs", label: "Pipeline Run History", description: "Pipelines → Run history", to: "/app/pipelines/runs" },
  { id: "nav-reference-sources", label: "Reference Sources", description: "External Reference → Sources", to: "/app/reference/sources" },
  { id: "nav-settings", label: "Configuration", description: "Go to settings", to: "/app/settings" },
] as const;

function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [workspaceError, setWorkspaceError] = useState(false);
  const { registerActions, unregisterActions } = useCommandPaletteStore();
  const navigate = useNavigate();
  const { getWorkspacePath, clearWorkspacePath } = useWorkspaceStorage();

  useEffect(() => {
    const workspacePath = getWorkspacePath();

    if (!workspacePath) {
      navigate({ to: "/welcome" });
      return;
    }
  }, [getWorkspacePath, navigate]);

  useEffect(() => {
    const actions = NAV_ACTIONS.map((item) => ({
      id: item.id,
      label: item.label,
      description: item.description,
      onSelect: () => navigate({ to: item.to }),
    }));
    registerActions(actions);
    return () => {
      unregisterActions(actions.map((a) => a.id));
    };
  }, [registerActions, unregisterActions, navigate]);

  const handleErrorRetry = () => {
    setWorkspaceError(false);
    window.location.reload();
  };

  const handleErrorChooseAnother = () => {
    clearWorkspacePath();
    navigate({ to: "/welcome" });
  };

  if (workspaceError) {
    return (
      <div className="desktop-frame">
        <Titlebar />
        <div className="app-shell">
          <div className="workspace flex items-center justify-center">
            <div className="w-full max-w-md">
              <WorkspaceErrorCard
                onRetry={handleErrorRetry}
                onChooseAnother={handleErrorChooseAnother}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="desktop-frame">
      <Titlebar />
      <div className={`app-shell${collapsed ? " collapsed" : ""}`}>
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
        <div className="workspace">
          <Topbar />
          <div className="canvas-area">
            <div className="canvas-scroll">
              <div className="canvas-inner">
                <Outlet />
              </div>
            </div>
          </div>
          <Statusbar />
        </div>
      </div>
    </div>
  );
}
