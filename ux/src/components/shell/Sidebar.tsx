import { useEffect, useRef } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { Sidebar as HeimdallSidebar } from "@tinkermonkey/heimdall-ui";
import { useSidebarStore } from "@/stores/sidebar";

interface NavItemDef {
  id: string;
  label: string;
  heimdallIcon?: string;
  path?: string;
  children?: Array<{ id: string; label: string; path: string }>;
}

const NAV_TREE: NavItemDef[] = [
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

export function Sidebar({ collapsed: collapsedProp, onToggle }: SidebarProps = {}) {
  const navigate = useNavigate();
  const { location } = useRouterState();
  const { collapsed: collapsedStore, toggleCollapsed } = useSidebarStore();
  const sidebarRef = useRef<HTMLDivElement>(null);
  const pathname = location.pathname;

  const collapsed = collapsedProp !== undefined ? collapsedProp : collapsedStore;
  const handleToggle = onToggle !== undefined ? onToggle : toggleCollapsed;

  useEffect(() => {
    if (sidebarRef.current) {
      const toggleButton = sidebarRef.current.querySelector("button[title*='toggle'], button[title*='collapse']") as HTMLElement;
      if (toggleButton) {
        toggleButton.setAttribute("data-testid", "sidebar-toggle");
      }
    }
  }, []);

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

  const sections = [
    {
      title: "Navigation",
      items: NAV_TREE.map((item) => ({
        id: item.id,
        label: item.label,
        icon: item.heimdallIcon,
        children: item.children?.map((child) => ({ id: child.id, label: child.label })),
      })),
    },
  ] as any;

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

  return (
    <div ref={sidebarRef} data-testid="sidebar" className={collapsed ? "collapsed" : ""}>
      <HeimdallSidebar
        sections={sections}
        activeItemId={getActiveItemId()}
        collapsed={collapsed}
        onCollapse={handleToggle}
        onSelectItem={handleSelectItem}
      />
    </div>
  );
}
