import { useEffect, useRef } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import {
  LayoutGrid,
  Network,
  Database,
  Zap,
  Link,
  Settings,
  Menu,
  LucideIcon,
} from "lucide-react";
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
  const sidebarRef = useRef<HTMLDivElement>(null);
  const toggleButtonRef = useRef<HTMLButtonElement>(null);
  const pathname = location.pathname;

  const collapsed = collapsedProp !== undefined ? collapsedProp : collapsedStore;
  const handleToggle = onToggle !== undefined ? onToggle : toggleCollapsed;

  useEffect(() => {
    if (toggleButtonRef.current) {
      toggleButtonRef.current.setAttribute("data-testid", "sidebar-toggle");
    }
  }, []);

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

  function isNavItemGroup(item: NavItemDef | NavItemGroup): item is NavItemGroup {
    return "children" in item;
  }

  type FlatNavItem = {
    id: string;
    label: string;
    parentId: string | undefined;
    parentLabel: string | undefined;
    parentIcon: LucideIcon;
  };

  const flatNavItems: FlatNavItem[] = [];
  for (const item of NAV_TREE) {
    if (isNavItemGroup(item)) {
      for (const child of item.children) {
        flatNavItems.push({
          id: child.id,
          label: child.label,
          parentId: item.id,
          parentLabel: item.label,
          parentIcon: item.lucideIcon,
        });
      }
    } else {
      flatNavItems.push({
        id: item.id,
        label: item.label,
        parentId: undefined,
        parentLabel: undefined,
        parentIcon: item.lucideIcon,
      });
    }
  }

  const handleSelectItem = (itemId: string) => {
    const navItem = flatNavItems.find((i) => i.id === itemId);
    if (!navItem) {
      console.error(`Navigation item with id "${itemId}" not found in navigation tree`);
      return;
    }

    let targetPath: string | undefined;

    for (const item of NAV_TREE) {
      if (isNavItemGroup(item)) {
        const child = item.children.find((c) => c.id === itemId);
        if (child) {
          targetPath = child.path;
          break;
        }
      } else if (item.id === itemId && item.path) {
        targetPath = item.path;
        break;
      }
    }

    if (targetPath) {
      navigate({ to: targetPath });
    }
  };

  const sections = [
    {
      title: "Navigation",
      items: NAV_TREE.map((item) => {
        const Icon = item.lucideIcon;
        return {
          id: item.id,
          label: item.label,
          icon: Icon,
          hasChildren: isNavItemGroup(item),
        };
      }),
    },
  ];

  return (
    <div
      ref={sidebarRef}
      data-testid="sidebar"
      className={`sidebar ${collapsed ? "collapsed" : ""}`}
    >
        <button
          ref={toggleButtonRef}
          className="sidebar__toggle"
          onClick={handleToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <Menu size={20} />
        </button>

        <nav className="sidebar__nav">
          {sections.map((section) => (
            <div key={section.title} className="sidebar__section">
              {!collapsed && <div className="sidebar__section-title">{section.title}</div>}
              <div className="sidebar__items">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = getActiveItemId() === item.id;
                  const displayLabel = item.label;

                  return (
                    <button
                      key={item.id}
                      className={`sidebar__item ${isActive ? "sidebar__item--active" : ""}`}
                      onClick={() => {
                        if (item.hasChildren) {
                          for (const navItem of NAV_TREE) {
                            if (isNavItemGroup(navItem) && navItem.id === item.id) {
                              navigate({ to: navItem.children[0].path });
                              return;
                            }
                          }
                        } else {
                          handleSelectItem(item.id);
                        }
                      }}
                      title={collapsed ? item.label : undefined}
                      data-testid={`sidebar-item-${item.id}`}
                    >
                      <Icon size={18} className="sidebar__item-icon" />
                      {!collapsed && <span className="sidebar__item-label">{displayLabel}</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
    </div>
  );
}
