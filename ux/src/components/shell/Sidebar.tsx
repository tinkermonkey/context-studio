import { useNavigate, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Network,
  Database,
  Cpu,
  BookOpen,
  Settings,
} from "lucide-react";
import { Sidebar as HeimdallSidebar } from "@tinkermonkey/heimdall-ui";
import { useSidebarStore } from "@/stores/sidebar";

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

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export function Sidebar({ collapsed: collapsedProp, onToggle }: SidebarProps = {}) {
  const navigate = useNavigate();
  const { location } = useRouterState();
  const { collapsed: collapsedStore, toggleCollapsed } = useSidebarStore();
  const pathname = location.pathname;

  const collapsed = collapsedProp !== undefined ? collapsedProp : collapsedStore;
  const handleToggle = onToggle !== undefined ? onToggle : toggleCollapsed;

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

  const sections = [
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
    <HeimdallSidebar
      data-testid="sidebar"
      sections={sections}
      activeItemId={getActiveItemId()}
      collapsed={collapsed}
      onCollapse={handleToggle}
      onSelectItem={handleSelectItem}
    />
  );
}
