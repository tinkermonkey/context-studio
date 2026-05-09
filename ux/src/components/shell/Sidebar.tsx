import { useNavigate, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Network,
  Database,
  Cpu,
  BookOpen,
  Settings,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
} from "lucide-react";

const NAV_TREE = [
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
  { id: "settings", label: "Configuration", icon: Settings, path: "/app/settings" },
] as const;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const navigate = useNavigate();
  const { location } = useRouterState();
  const pathname = location.pathname;

  function isParentActive(id: string) {
    return pathname.includes(`/${id}`);
  }

  function isLeafActive(path: string) {
    return pathname === path || pathname.startsWith(path + "/");
  }

  return (
    <aside className={`shell-rail${collapsed ? " collapsed" : ""}`}>
      <div className="brand-row">
        <div className="brand-mark" aria-hidden="true" />
        {!collapsed && (
          <div className="brand-name">
            Context Studio<span>v0.1.0 · local</span>
          </div>
        )}
        <button className="rail-collapse" onClick={onToggle} aria-label="Toggle sidebar" type="button">
          {collapsed ? <ChevronRight size={11} /> : <ChevronLeft size={11} />}
        </button>
      </div>

      <div className="nav-section">
        {NAV_TREE.map((item) => {
          const Icon = item.icon;
          const hasChildren = "children" in item;
          const parentActive = hasChildren ? isParentActive(item.id) : false;
          const leafActive = !hasChildren && isLeafActive(item.path);

          return (
            <div key={item.id}>
              <div
                className={`nav-item${parentActive ? " active-parent" : ""}${leafActive ? " active" : ""}`}
                onClick={() => {
                  if (!hasChildren) {
                    navigate({ to: item.path });
                  } else {
                    navigate({ to: item.children[0].path });
                  }
                }}
                title={collapsed ? item.label : undefined}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && e.currentTarget.click()}
              >
                <Icon size={16} />
                {!collapsed && <span className="nav-label">{item.label}</span>}
                {hasChildren && !collapsed && (
                  parentActive ? <ChevronDown size={12} className="ml-auto" /> : <ChevronRight size={12} className="ml-auto" />
                )}
              </div>

              {hasChildren && parentActive && !collapsed && (
                <div className="nav-sub">
                  {item.children.map((child) => (
                    <div
                      key={child.id}
                      className={`nav-item${isLeafActive(child.path) ? " active" : ""}`}
                      onClick={() => navigate({ to: child.path })}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.click()}
                    >
                      <span className="nav-label">{child.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="rail-footer">
        <div className="rail-user">
          <div className="avatar">CS</div>
          {!collapsed && (
            <div className="rail-user-info">
              <div className="n">Local User</div>
              <div className="e">local · main</div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
