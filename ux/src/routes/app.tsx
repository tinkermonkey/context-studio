import { useEffect } from "react";
import { createFileRoute, Outlet, useNavigate, redirect, useRouterState } from "@tanstack/react-router";
import { ShellLayout } from "@tinkermonkey/heimdall-ui";
import { Folder, ChevronDown, Search, Bell, FileText, Sun, Moon } from "lucide-react";
import {
  LayoutDashboard,
  Network,
  Database,
  Cpu,
  BookOpen,
  Settings,
} from "lucide-react";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useCommandPaletteActions } from "@/hooks/useCommandPaletteActions";
import { createStaticPaletteActions } from "@/config/staticPaletteActions";
import { getWorkspacePath } from "@/lib/workspaceStorage";
import { useSidebarStore } from "@/stores/sidebar";
import { useCanvasStore } from "@/stores/canvas";

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
  "/app/reference/sources": ["External Reference", "Sources"],
  "/app/reference/workflows": ["External Reference", "Grounding Workflows"],
  "/app/versioning": ["Versioning"],
  "/app/settings": ["Settings"],
  "/app/contact-sheet": ["Developer", "Contact Sheet"],
};

interface NavItemDef {
  id: string;
  label: string;
  icon?: typeof LayoutDashboard;
  path?: string;
  children?: Array<{ id: string; label: string; path: string }>;
}

const NAV_TREE: NavItemDef[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, path: "/app" },
  {
    id: "schema",
    label: "Schema",
    icon: Network,
    children: [
      { id: "taxonomies", label: "Taxonomies", path: "/app/schema/taxonomies" },
      { id: "schemes", label: "Concept schemes", path: "/app/schema/schemes" },
      { id: "classes", label: "Classes", path: "/app/schema/classes" },
      { id: "properties", label: "Properties", path: "/app/schema/properties" },
      { id: "relationships", label: "Relationships", path: "/app/schema/relationships" },
    ],
  },
  {
    id: "data",
    label: "Data",
    icon: Database,
    children: [
      { id: "individuals", label: "Individuals", path: "/app/data/individuals" },
      { id: "datasets", label: "Datasets", path: "/app/data/datasets" },
    ],
  },
  {
    id: "pipelines",
    label: "Pipelines",
    icon: Cpu,
    children: [
      { id: "pipelines-all", label: "All pipelines", path: "/app/pipelines" },
      { id: "pipelines-runs", label: "Run history", path: "/app/pipelines/runs" },
      { id: "pipelines-flavors", label: "Flavors", path: "/app/pipelines/flavors" },
    ],
  },
  {
    id: "reference",
    label: "External Reference",
    icon: BookOpen,
    children: [
      { id: "ref-sources", label: "Sources", path: "/app/reference/sources" },
      { id: "ref-grounding", label: "Grounding workflows", path: "/app/reference/workflows" },
    ],
  },
  { id: "settings", label: "Settings", icon: Settings, path: "/app/settings" },
];

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
  const { location } = useRouterState();
  const { registerActions, unregisterActions, openPalette } = useCommandPaletteStore();
  const { collapsed, toggleCollapsed } = useSidebarStore();
  const { darkCanvas, toggleDarkCanvas } = useCanvasStore();
  const navigate = useNavigate();
  useCommandPaletteActions();

  const pathname = location.pathname;
  const crumbs = ROUTE_LABELS[pathname] ?? [pathname];

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

  function getActiveItemId(): string | undefined {
    for (const item of NAV_TREE) {
      if (item.path && pathname === item.path) {
        return item.id;
      }
      if (item.children) {
        const child = item.children.find((c) => c.path === pathname);
        if (child) {
          return child.id;
        }
      }
    }
    return undefined;
  }

  function getHeimdallIconName(lucideIcon: typeof LayoutDashboard | undefined): string | undefined {
    if (!lucideIcon) return undefined;
    const iconMap: Record<string, string> = {
      "LayoutDashboard": "dashboard",
      "Network": "schema",
      "Database": "data",
      "Cpu": "pipeline",
      "BookOpen": "link",
      "Settings": "settings",
    };
    return iconMap[lucideIcon.name || ""] as any;
  }

  function buildSidebarSections() {
    return [
      {
        title: "Navigation",
        items: NAV_TREE.map((item) => ({
          id: item.id,
          label: item.label,
          icon: getHeimdallIconName(item.icon) as any,
          children: item.children?.map((child) => ({ id: child.id, label: child.label })),
        })),
      },
    ] as any;
  }

  const handleSelectItem = (itemId: string) => {
    const item = NAV_TREE.find((i) => i.id === itemId);
    if (item) {
      if (item.path) {
        navigate({ to: item.path });
      } else if (item.children) {
        navigate({ to: item.children[0].path });
      }
    } else {
      const child = NAV_TREE.flatMap((i) => i.children || []).find((c) => c.id === itemId);
      if (child) {
        navigate({ to: child.path });
      }
    }
  };

  const titlebarLeft = (
    <div className="titlebar-app">
      <span className="titlebar-app-name">Context Studio</span>
      <span className="titlebar-app-sep">—</span>
      <button className="titlebar-ws" type="button" title="Switch workspace">
        <Folder size={12} />
        <span>~/Projects/context-studio</span>
        <ChevronDown size={10} />
      </button>
    </div>
  );

  const titlebarRight = (
    <div className="titlebar-actions">
      <button
        className="titlebar-btn"
        onClick={openPalette}
        type="button"
        title="Command palette (⌘K)"
      >
        <Search size={12} />
        <span className="kbd-mini">⌘K</span>
      </button>
    </div>
  );

  const topbarChildren = (
    <div className="topbar-actions">
      <button
        className="topbar-palette"
        data-testid="topbar-palette-button"
        onClick={openPalette}
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
      <span className="env-pill">
        <span className="dot" />
        main
      </span>
    </div>
  );

  const statusbarLeft = (
    <div className="statusbar-group">
      <span className="sb-item">
        <span className="status-pulse" />
        <span>api server</span>
        <span className="sb-mono">:8100</span>
      </span>
    </div>
  );

  const statusbarRight = (
    <div className="statusbar-group">
      <span className="sb-item">
        <span className="sb-mono">UTF-8 · LF</span>
      </span>
    </div>
  );

  return (
    <div className="desktop-frame">
      <ShellLayout
        appTitle={{
          title: "Context Studio",
          version: "v0.1.0 · local",
          collapsed,
        }}
        topbar={{
          breadcrumbs: crumbs.map((label) => ({ label })),
          children: topbarChildren,
        }}
        sidebar={{
          sections: buildSidebarSections(),
          activeItemId: getActiveItemId(),
          collapsed,
          onCollapse: toggleCollapsed,
          onSelectItem: handleSelectItem,
        }}
        statusbar={{
          left: statusbarLeft,
          right: statusbarRight,
        }}
      >
        <div className="canvas-area">
          <div className="canvas-scroll">
            <div className="canvas-inner">
              <ErrorBoundary>
                <Outlet />
              </ErrorBoundary>
            </div>
          </div>
        </div>
      </ShellLayout>
    </div>
  );
}
