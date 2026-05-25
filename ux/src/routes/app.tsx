import { useState, useEffect } from "react";
import { createFileRoute, Outlet, useNavigate, redirect, useRouterState } from "@tanstack/react-router";
import { ShellLayout } from "@tinkermonkey/heimdall-ui";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useCommandPaletteActions } from "@/hooks/useCommandPaletteActions";
import { createStaticPaletteActions } from "@/config/staticPaletteActions";
import { getWorkspacePath } from "@/lib/workspaceStorage";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useExecutionStore } from "@/stores/executionStore";
import { useHealth, useConfig } from "@/api/hooks/admin";
import { usePipelines } from "@/api/hooks/pipeline";
import { useClasses, useIndividuals } from "@/api/hooks/ontology";

export const Route = createFileRoute("/app")({
  beforeLoad: () => {
    const workspacePath = getWorkspacePath();
    if (!workspacePath) {
      throw redirect({ to: "/welcome" });
    }
  },
  component: AppShell,
});

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

const ROUTE_TO_SIDEBAR_ID: Array<{ prefix: string; id: string }> = [
  { prefix: "/app/schema", id: "schema" },
  { prefix: "/app/data", id: "data" },
  { prefix: "/app/pipelines", id: "pipelines" },
  { prefix: "/app/reference", id: "external-reference" },
  { prefix: "/app/settings", id: "settings" },
  { prefix: "/app", id: "dashboard" },
];

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

const SIDEBAR_PATH_MAP: Record<string, string> = {
  dashboard: "/app",
  schema: "/app/schema/taxonomies",
  data: "/app/data/individuals",
  pipelines: "/app/pipelines",
  "external-reference": "/app/reference/sources",
  settings: "/app/settings",
};

function getActiveItemId(pathname: string): string {
  for (const { prefix, id } of ROUTE_TO_SIDEBAR_ID) {
    if (pathname === prefix || pathname.startsWith(prefix + "/")) {
      return id;
    }
  }
  return "dashboard";
}

function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { registerActions, unregisterActions, openPalette } = useCommandPaletteStore();
  const navigate = useNavigate();
  const { location } = useRouterState();
  useCommandPaletteActions();

  const { data: health, isError } = useHealth();
  const { data: config } = useConfig();
  const { inFlightPipelineIds } = useExecutionStore();
  const runningCount = inFlightPipelineIds.size;
  const hasRunning = runningCount > 0;
  const { data: pipelines } = usePipelines(hasRunning ? 5000 : false);
  const { data: classes } = useClasses();
  const { data: individuals } = useIndividuals();

  const classCount = classes?.total ?? 0;
  const individualCount = individuals?.total ?? 0;
  const pipelineCount = pipelines?.length ?? 0;

  const workspaceName = (() => {
    const displayName = config?.sections?.workspace?.display_name;
    if (displayName && String(displayName).trim()) return String(displayName).trim();
    const rawPath = getWorkspacePath() ?? "";
    const base = rawPath.split("/").pop() ?? rawPath;
    return base.replace(/\.db$/i, "") || "workspace";
  })();

  useEffect(() => {
    document.body.classList.add("dark-canvas");
  }, []);

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

  const pathname = location.pathname;
  const activeItemId = getActiveItemId(pathname);
  const crumbs = ROUTE_LABELS[pathname] ?? [pathname];
  const breadcrumbs = [{ label: workspaceName }, ...crumbs.map((label) => ({ label }))];

  const isHealthy = !isError && health?.status === "healthy";
  const isDegraded = !isError && health?.status === "degraded";
  const statusLabel = isError ? "api offline" : health ? health.status : "connecting...";
  const uptimeLabel = health ? `up ${Math.floor(health.uptime_seconds / 60)}m` : null;

  const statusbarLeft = (
    <>
      <div className="statusbar__item statusbar__item--pulse">
        <div
          className={`statusbar__pulse ${
            isError
              ? "statusbar__pulse--rose"
              : isDegraded
                ? "statusbar__pulse--amber"
                : isHealthy
                  ? "statusbar__pulse--emerald"
                  : "statusbar__pulse--amber"
          }`}
        />
        <span className="statusbar__label">api server</span>
        <span className="statusbar__label--mono">:8100</span>
        <span className="statusbar__label--mono">{statusLabel}</span>
      </div>
      {health?.database_connected !== undefined && (
        <>
          <div className="statusbar__divider" />
          <div className="statusbar__item">
            <span className="statusbar__label">
              {health.database_connected ? "database connected" : "database unavailable"}
            </span>
          </div>
        </>
      )}
      {(classCount > 0 || individualCount > 0) && (
        <>
          <div className="statusbar__divider" />
          <div className="statusbar__item">
            <span className="statusbar__label--mono">
              {classCount} cls · {individualCount} ind · {pipelineCount} pipe
            </span>
          </div>
        </>
      )}
    </>
  );

  const statusbarRight = (
    <>
      {hasRunning && (
        <>
          <div className="statusbar__item statusbar__item--pulse">
            <div className="statusbar__pulse statusbar__pulse--amber" />
            <span className="statusbar__label--mono">
              {runningCount} pipeline{runningCount > 1 ? "s" : ""} running
            </span>
          </div>
          <div className="statusbar__divider" />
        </>
      )}
      {uptimeLabel && (
        <>
          <div className="statusbar__item">
            <span className="statusbar__label--mono">{uptimeLabel}</span>
          </div>
          <div className="statusbar__divider" />
        </>
      )}
      <div className="statusbar__item">
        <span className="statusbar__label--mono">UTF-8</span>
      </div>
      <div className="statusbar__divider" />
      <div className="statusbar__item">
        <span className="statusbar__label">local</span>
      </div>
    </>
  );

  return (
    <ShellLayout
      appTitle={{ title: "Context Studio" }}
      topbar={{
        breadcrumbs,
        searchPlaceholder: "Search or run command…",
        onSearch: () => openPalette(),
      }}
      sidebar={{
        sections: [
          {
            title: "",
            items: [
              { id: "dashboard", label: "Dashboard", icon: "dashboard" },
              { id: "schema", label: "Schema", icon: "schema" },
              { id: "data", label: "Data", icon: "data" },
              { id: "pipelines", label: "Pipelines", icon: "pipeline" },
              { id: "external-reference", label: "External Reference", icon: "link" },
              { id: "settings", label: "Settings", icon: "settings" },
            ],
          },
        ],
        activeItemId,
        collapsed: sidebarCollapsed,
        onCollapse: setSidebarCollapsed,
        onSelectItem: (itemId: string) => {
          const path = SIDEBAR_PATH_MAP[itemId];
          if (path) {
            navigate({ to: path });
          }
        },
      }}
      statusbar={{
        left: statusbarLeft,
        right: statusbarRight,
      }}
    >
      <ErrorBoundary>
        <Outlet />
      </ErrorBoundary>
    </ShellLayout>
  );
}
