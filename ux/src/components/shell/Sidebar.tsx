import { useNavigate, useRouterState } from "@tanstack/react-router";
import type { IconName } from "@tinkermonkey/heimdall-ui";

interface SidebarProps {
  sections: Array<{
    title: string;
    items: Array<{
      id: string;
      label: string;
      icon?: IconName;
      count?: number;
      children?: Array<{
        id: string;
        label: string;
        count?: number;
      }>;
    }>;
  }>;
  activeItemId?: string;
  collapsed?: boolean;
  onCollapse?: (collapsed: boolean) => void;
  onSelectItem?: (itemId: string) => void;
  className?: string;
}

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

function isNavItemGroup(item: NavItemDef | NavItemGroup): item is NavItemGroup {
  return "children" in item;
}

function isRouteMatch(currentPath: string, targetPath: string): boolean {
  return currentPath === targetPath || currentPath.startsWith(targetPath + "/");
}

function getActiveItemId(pathname: string): string | undefined {
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

export function buildSidebarProps(
  collapsed: boolean,
  setCollapsed: (value: boolean) => void
): SidebarProps {
  const navigate = useNavigate();
  const { location } = useRouterState();
  const pathname = location.pathname;

  const activeItemId = getActiveItemId(pathname);

  const sections = NAV_TREE.map((item) => {
    if (isNavItemGroup(item)) {
      return {
        title: item.label,
        items: [
          {
            id: item.id,
            label: item.label,
            icon: item.heimdallIcon,
            children: item.children.map((child) => ({
              id: child.id,
              label: child.label,
            })),
          },
        ],
      };
    } else {
      return {
        title: "",
        items: [
          {
            id: item.id,
            label: item.label,
            icon: item.heimdallIcon,
          },
        ],
      };
    }
  });

  const pathMap = new Map<string, string>();
  for (const item of NAV_TREE) {
    if ("path" in item && item.path) {
      pathMap.set(item.id, item.path);
    }
    if ("children" in item) {
      for (const child of item.children) {
        pathMap.set(child.id, child.path);
      }
    }
  }

  return {
    sections,
    activeItemId,
    collapsed,
    onCollapse: setCollapsed,
    onSelectItem: (itemId: string) => {
      const path = pathMap.get(itemId);
      if (path) {
        navigate({ to: path });
      }
    },
  };
}
