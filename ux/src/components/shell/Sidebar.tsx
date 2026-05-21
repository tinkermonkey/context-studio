import { useState } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { NavItem, type IconName } from "@tinkermonkey/heimdall-ui";

interface NavItemPath {
  id: string;
  label: string;
  path: string;
}

interface NavItemGroup {
  id: string;
  label: string;
  heimdallIcon: IconName;
  children: NavItemPath[];
}

interface NavItemDef {
  id: string;
  label: string;
  heimdallIcon: IconName;
  path?: string;
}

const NAV_TREE: (NavItemDef | NavItemGroup)[] = [
  { id: "dashboard", label: "Dashboard", heimdallIcon: "dashboard", path: "/app" },
  {
    id: "schema",
    label: "Schema",
    heimdallIcon: "schema",
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
    heimdallIcon: "data",
    children: [
      { id: "individuals", label: "Individuals", path: "/app/data/individuals" },
      { id: "datasets", label: "Datasets", path: "/app/data/datasets" },
    ],
  },
  {
    id: "pipelines",
    label: "Pipelines",
    heimdallIcon: "pipeline",
    children: [
      { id: "pipelines-all", label: "All pipelines", path: "/app/pipelines" },
      { id: "pipelines-runs", label: "Run history", path: "/app/pipelines/runs" },
      { id: "pipelines-flavors", label: "Flavors", path: "/app/pipelines/flavors" },
    ],
  },
  {
    id: "reference",
    label: "External Reference",
    heimdallIcon: "link",
    children: [
      { id: "ref-sources", label: "Sources", path: "/app/reference/sources" },
      { id: "ref-grounding", label: "Grounding workflows", path: "/app/reference/workflows" },
    ],
  },
  { id: "settings", label: "Settings", heimdallIcon: "settings", path: "/app/settings" },
];

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export function Sidebar({ collapsed = false, onToggle }: SidebarProps = {}) {
  const navigate = useNavigate();
  const { location } = useRouterState();
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const pathname = location.pathname;

  function isNavItemGroup(item: NavItemDef | NavItemGroup): item is NavItemGroup {
    return "children" in item;
  }

  function isRouteMatch(currentPath: string, targetPath: string): boolean {
    return currentPath === targetPath || currentPath.startsWith(targetPath + "/");
  }

  function getActiveItemId(): string | undefined {
    // Collect all matching candidates with their path lengths
    const candidates: Array<{ id: string; path: string }> = [];

    for (const item of NAV_TREE) {
      if ("path" in item && item.path && isRouteMatch(pathname, item.path)) {
        candidates.push({ id: item.id, path: item.path });
      }
      if ("children" in item) {
        for (const child of item.children) {
          if (isRouteMatch(pathname, child.path)) {
            candidates.push({ id: child.id, path: child.path });
          }
        }
      }
    }

    // Return the longest matching path (most specific match)
    if (candidates.length === 0) return undefined;
    const longest = candidates.reduce((a, b) => (a.path.length > b.path.length ? a : b));
    return longest.id;
  }

  function getActiveGroupId(): string | undefined {
    // Collect all matching group candidates with their longest child path
    const candidates: Array<{ groupId: string; maxChildLength: number }> = [];

    for (const item of NAV_TREE) {
      if ("children" in item) {
        for (const child of item.children) {
          if (isRouteMatch(pathname, child.path)) {
            candidates.push({
              groupId: item.id,
              maxChildLength: child.path.length,
            });
            break; // Only need one match per group to determine if it's active
          }
        }
      }
    }

    // Return the group with the longest matching child path
    if (candidates.length === 0) return undefined;
    const longest = candidates.reduce((a, b) => (a.maxChildLength > b.maxChildLength ? a : b));
    return longest.groupId;
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
    <aside data-testid="sidebar" className={`shell-rail ${collapsed ? "collapsed" : ""}`}>
      <button
        data-testid="sidebar-toggle"
        className="rail-collapse"
        onClick={() => onToggle?.()}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <Menu size={20} />
      </button>

      <nav>
        {NAV_TREE.map((item) => {
          const isGroup = isNavItemGroup(item);
          const isExpanded = expandedGroups.has(item.id);
          const isItemActive = activeItemId === item.id;
          const isGroupActive = isGroup && activeGroupId === item.id;

          if (isGroup) {
            return (
              <div key={item.id} className="nav-section">
                <NavItem
                  icon={item.heimdallIcon}
                  label={!collapsed ? item.label : ""}
                  active={isGroupActive}
                  onClick={() => {
                    const childPath =
                      item.children.find((c) => c.id === activeItemId)?.path ||
                      item.children[0].path;
                    navigate({ to: childPath });
                    handleGroupToggle(item.id);
                  }}
                  aria-label={collapsed ? item.label : undefined}
                  data-testid={`sidebar-item-${item.id}`}
                  aria-expanded={isExpanded}
                />
                {(isExpanded || isGroupActive) && (
                  <div className="nav-sub">
                    {item.children.map((child) => {
                      const isChildActive = activeItemId === child.id;
                      return (
                        <NavItem
                          key={child.id}
                          label={!collapsed ? child.label : ""}
                          active={isChildActive}
                          onClick={() => navigate({ to: child.path })}
                          aria-label={collapsed ? child.label : undefined}
                          data-testid={`sidebar-item-${child.id}`}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }

          return (
            <div key={item.id} className="nav-section">
              <NavItem
                icon={item.heimdallIcon}
                label={!collapsed ? item.label : ""}
                active={isItemActive}
                onClick={() => navigate({ to: item.path! })}
                aria-label={collapsed ? item.label : undefined}
                data-testid={`sidebar-item-${item.id}`}
              />
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
