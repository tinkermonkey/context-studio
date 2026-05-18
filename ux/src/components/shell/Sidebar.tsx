import { useState } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { LayoutGrid, Network, Database, Zap, Link, Settings, Menu, LucideIcon } from "lucide-react";
import { useSidebarStore } from "@/stores/sidebar";

interface NavItemPath {
  id: string;
  label: string;
  path: string;
}

interface NavItemGroup {
  id: string;
  label: string;
  lucideIcon: LucideIcon;
  children: NavItemPath[];
}

interface NavItemDef {
  id: string;
  label: string;
  lucideIcon: LucideIcon;
  path?: string;
}

const NAV_TREE: (NavItemDef | NavItemGroup)[] = [
  { id: "dashboard", label: "Dashboard", lucideIcon: LayoutGrid, path: "/app" },
  {
    id: "schema",
    label: "Schema",
    lucideIcon: Network,
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
    lucideIcon: Database,
    children: [
      { id: "individuals", label: "Individuals", path: "/app/data/individuals" },
      { id: "datasets", label: "Datasets", path: "/app/data/datasets" },
    ],
  },
  {
    id: "pipelines",
    label: "Pipelines",
    lucideIcon: Zap,
    children: [
      { id: "pipelines-all", label: "All pipelines", path: "/app/pipelines" },
      { id: "pipelines-runs", label: "Run history", path: "/app/pipelines/runs" },
      { id: "pipelines-flavors", label: "Flavors", path: "/app/pipelines/flavors" },
    ],
  },
  {
    id: "reference",
    label: "External Reference",
    lucideIcon: Link,
    children: [
      { id: "ref-sources", label: "Sources", path: "/app/reference/sources" },
      { id: "ref-grounding", label: "Grounding workflows", path: "/app/reference/workflows" },
    ],
  },
  { id: "settings", label: "Settings", lucideIcon: Settings, path: "/app/settings" },
];

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export function Sidebar({ collapsed: collapsedProp, onToggle }: SidebarProps = {}) {
  const navigate = useNavigate();
  const { location } = useRouterState();
  const { collapsed: collapsedStore, toggleCollapsed } = useSidebarStore();
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const pathname = location.pathname;

  const collapsed = collapsedProp !== undefined ? collapsedProp : collapsedStore;
  const handleToggle = onToggle !== undefined ? onToggle : toggleCollapsed;

  function isNavItemGroup(item: NavItemDef | NavItemGroup): item is NavItemGroup {
    return "children" in item;
  }

  function getActiveItemId(): string | undefined {
    for (const item of NAV_TREE) {
      if ("path" in item && item.path && pathname === item.path) {
        return item.id;
      }
      if ("children" in item) {
        const child = item.children.find((c) => c.path === pathname);
        if (child) {
          return child.id;
        }
      }
    }
    return undefined;
  }

  function getActiveGroupId(): string | undefined {
    for (const item of NAV_TREE) {
      if ("children" in item) {
        const child = item.children.find((c) => c.path === pathname);
        if (child) {
          return item.id;
        }
      }
    }
    return undefined;
  }

  const activeItemId = getActiveItemId();
  const activeGroupId = getActiveGroupId();

  const handleGroupToggle = (groupId: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedGroups(newExpanded);
  };

  return (
    <div data-testid="sidebar" className={`shell-rail ${collapsed ? "collapsed" : ""}`}>
      <button
        data-testid="sidebar-toggle"
        className="rail-collapse"
        onClick={handleToggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <Menu size={20} />
      </button>

      <nav>
        {NAV_TREE.map((item) => {
          const Icon = item.lucideIcon;
          const isGroup = isNavItemGroup(item);
          const isExpanded = expandedGroups.has(item.id);
          const isItemActive = activeItemId === item.id;
          const isGroupActive = isGroup && activeGroupId === item.id;

          if (isGroup) {
            return (
              <div key={item.id} className="nav-section">
                <button
                  className={`nav-item ${isGroupActive ? "active-parent" : ""}`}
                  onClick={() => {
                    const childPath =
                      item.children.find((c) => c.id === activeItemId)?.path ||
                      item.children[0].path;
                    navigate({ to: childPath });
                    handleGroupToggle(item.id);
                  }}
                  title={collapsed ? item.label : undefined}
                  data-testid={`sidebar-item-${item.id}`}
                  aria-expanded={isExpanded}
                  aria-current={isGroupActive ? "page" : undefined}
                >
                  <Icon size={16} />
                  {!collapsed && <span>{item.label}</span>}
                </button>
                {(isExpanded || isGroupActive) && (
                  <div className="nav-sub">
                    {item.children.map((child) => {
                      const isChildActive = activeItemId === child.id;
                      return (
                        <button
                          key={child.id}
                          className={`nav-item ${isChildActive ? "active" : ""}`}
                          onClick={() => navigate({ to: child.path })}
                          data-testid={`sidebar-item-${child.id}`}
                          aria-current={isChildActive ? "page" : undefined}
                        >
                          {!collapsed && <span>{child.label}</span>}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }

          return (
            <div key={item.id} className="nav-section">
              <button
                className={`nav-item ${isItemActive ? "active" : ""}`}
                onClick={() => navigate({ to: item.path! })}
                title={collapsed ? item.label : undefined}
                data-testid={`sidebar-item-${item.id}`}
                aria-current={isItemActive ? "page" : undefined}
              >
                <Icon size={16} />
                {!collapsed && <span>{item.label}</span>}
              </button>
            </div>
          );
        })}
      </nav>
    </div>
  );
}
