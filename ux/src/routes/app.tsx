import { useState, useEffect } from "react";
import {
  createFileRoute,
  Outlet,
  useNavigate,
  redirect,
  useRouterState,
} from "@tanstack/react-router";
import { ShellLayout, Icon, Chip, Badge } from "@tinkermonkey/heimdall-ui";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useCommandPaletteActions } from "@/hooks/useCommandPaletteActions";
import { createStaticPaletteActions } from "@/config/staticPaletteActions";
import { getWorkspacePath } from "@/lib/workspaceStorage";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useHealth, useConfig } from "@/api/hooks/admin";
import {
  useClasses,
  useIndividuals,
  useTaxonomies,
  useSchemes,
  useProperties,
  useRelationships,
} from "@/api/hooks/ontology";
import {
  NAV_ACTIONS,
  SIDEBAR_PATH_MAP,
  getActiveItemId,
  getBreadcrumbLabels,
} from "./-app-navigation";

export const Route = createFileRoute("/app")({
  beforeLoad: () => {
    const workspacePath = getWorkspacePath();
    if (!workspacePath) {
      throw redirect({ to: "/welcome" });
    }
  },
  component: AppShell,
});

function formatRelativeMinutes(uptimeSeconds: number): string {
  if (uptimeSeconds < 60) return "just now";
  const minutes = Math.floor(uptimeSeconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

interface SidebarUserFooterProps {
  workspaceName: string;
}

function SidebarUserFooter({ workspaceName }: SidebarUserFooterProps) {
  const name = "Local User";
  const initials = name
    .split(" ")
    .map((s) => s[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="sidebar-user-footer" data-testid="sidebar-user-footer">
      <div className="sidebar-user-footer__avatar" aria-hidden="true">
        {initials}
      </div>
      <div className="sidebar-user-footer__meta">
        <div className="sidebar-user-footer__name">{name}</div>
        <div className="sidebar-user-footer__context">{workspaceName} · main</div>
      </div>
      <Icon name="chevronDown" size={14} className="sidebar-user-footer__caret" />
    </div>
  );
}

function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { registerActions, unregisterActions, openPalette } = useCommandPaletteStore();
  const navigate = useNavigate();
  const { location } = useRouterState();
  useCommandPaletteActions();

  const { data: health, isError } = useHealth();
  const { data: config } = useConfig();
  const { data: classes } = useClasses();
  const { data: individuals } = useIndividuals();
  const { data: taxonomies } = useTaxonomies();
  const { data: schemes } = useSchemes();
  const { data: properties } = useProperties();
  const { data: relationships } = useRelationships();

  const classCount = classes?.total ?? 0;
  const individualCount = individuals?.total ?? 0;
  const taxonomyCount = taxonomies?.total ?? 0;
  const schemeCount = schemes?.total ?? 0;
  const propertyCount = properties?.total ?? 0;
  const relationshipCount = relationships?.items?.length ?? relationships?.total ?? 0;

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
  const crumbs = getBreadcrumbLabels(pathname);
  const breadcrumbs = [{ label: workspaceName }, ...crumbs.map((label) => ({ label }))];

  const isHealthy = !isError && health?.status === "healthy";
  const isDegraded = !isError && health?.status === "degraded";
  const apiPulseTone = isError ? "rose" : isDegraded ? "amber" : isHealthy ? "emerald" : "amber";
  const syncedLabel = health
    ? `synced ${formatRelativeMinutes(health.uptime_seconds)}`
    : "syncing…";

  const statusbarLeft = (
    <>
      <div className="statusbar__item statusbar__item--pulse">
        <div className={`statusbar__pulse statusbar__pulse--${apiPulseTone}`} />
        <span className="statusbar__label">graph daemon</span>
        <span className="statusbar__label--mono">:8100</span>
      </div>
      {(classCount > 0 || individualCount > 0 || relationshipCount > 0) && (
        <>
          <div className="statusbar__divider" />
          <div className="statusbar__item">
            <span className="statusbar__label--mono">
              {classCount} cls · {individualCount} ind · {relationshipCount} rel
            </span>
          </div>
        </>
      )}
    </>
  );

  const statusbarRight = (
    <>
      <div className="statusbar__item statusbar__item--branch">
        <span className="statusbar__branch-glyph" aria-hidden="true">
          ⎇
        </span>
        <span className="statusbar__label--mono">main</span>
      </div>
      <div className="statusbar__divider" />
      <div className="statusbar__item">
        <span className="statusbar__label--mono">UTF-8 · LF</span>
      </div>
      <div className="statusbar__divider" />
      <div className="statusbar__item">
        <Icon name="check" size={12} />
        <span className="statusbar__label--mono">{syncedLabel}</span>
      </div>
    </>
  );

  return (
    <ShellLayout
      appTitle={{ title: "Context Studio", version: "v0.2.0 · LOCAL" }}
      topbar={{
        leadingContent: (
          <button
            type="button"
            className="workspace-switcher"
            data-testid="workspace-switcher"
            aria-label="Switch workspace"
          >
            <Badge color="amber" />
            <span className="workspace-switcher__label">{workspaceName}</span>
            <Icon name="chevronDown" size={12} />
          </button>
        ),
        breadcrumbs,
        searchPlaceholder: "Search workspace, run command, jump to…",
        onSearch: () => openPalette(),
        searchHint: "⌘K",
        children: (
          <div className="topbar-actions" data-testid="topbar-actions">
            <button
              type="button"
              className="topbar-iconbtn"
              aria-label="Notifications"
              data-testid="topbar-notifications"
            >
              <Icon name="bell" size={16} />
              <span className="topbar-iconbtn__badge">2</span>
            </button>
            <button
              type="button"
              className="topbar-iconbtn"
              aria-label="Documentation"
              data-testid="topbar-docs"
            >
              <Icon name="help" size={16} />
            </button>
            <Chip variant="amber">
              <span className="topbar-branch">
                <Badge color="amber" />
                main
              </span>
            </Chip>
          </div>
        ),
      }}
      sidebar={{
        sections: [
          {
            title: "",
            items: [
              { id: "dashboard", label: "Dashboard", icon: "dashboard" },
              {
                id: "schema",
                label: "Schema",
                icon: "schema",
                children: [
                  { id: "schema-taxonomies", label: "Taxonomies", count: taxonomyCount },
                  { id: "schema-schemes", label: "Concept schemes", count: schemeCount },
                  { id: "schema-classes", label: "Classes", count: classCount },
                  { id: "schema-properties", label: "Properties", count: propertyCount },
                  { id: "schema-relationships", label: "Relationships", count: relationshipCount },
                ],
              },
              { id: "data", label: "Data", icon: "data" },
              { id: "external-reference", label: "External Reference", icon: "link" },
              {
                id: "pipelines",
                label: "Pipelines",
                icon: "pipeline",
                children: [
                  { id: "pipelines-types", label: "Pipeline types" },
                  { id: "pipelines-review", label: "Extraction review" },
                  { id: "pipelines-runs", label: "Runs" },
                ],
              },
              { id: "graph", label: "Graph view", icon: "graph" },
              { id: "settings", label: "Configuration", icon: "settings" },
            ],
          },
        ],
        defaultExpandedIds: ["schema"],
        activeItemId,
        collapsed: sidebarCollapsed,
        onCollapse: setSidebarCollapsed,
        onSelectItem: (itemId: string) => {
          const path = SIDEBAR_PATH_MAP[itemId];
          if (path) {
            navigate({ to: path });
          }
        },
        footer: <SidebarUserFooter workspaceName={workspaceName} />,
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
