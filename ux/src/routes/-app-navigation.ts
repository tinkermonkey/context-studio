/**
 * Navigation wiring for the /app shell: breadcrumb labels, sidebar ids and
 * command-palette navigation actions. Kept out of app.tsx so the route file
 * only exports its Route (the "-" prefix excludes it from route generation).
 */

export const ROUTE_LABELS: Record<string, string[]> = {
  "/app": ["Dashboard"],
  "/app/schema/taxonomies": ["Schema", "Taxonomies"],
  "/app/schema/schemes": ["Schema", "Concept Schemes"],
  "/app/schema/classes": ["Schema", "Classes"],
  "/app/schema/properties": ["Schema", "Properties"],
  "/app/schema/relationships": ["Schema", "Relationships"],
  "/app/data/individuals": ["Data", "Individuals"],
  "/app/data/datasets": ["Data", "Datasets"],
  "/app/graph": ["Graph view"],
  "/app/reference/sources": ["External Reference", "Sources"],
  "/app/reference/workflows": ["External Reference", "Grounding Workflows"],
  "/app/pipelines": ["Pipelines", "Pipeline Types"],
  "/app/pipelines/review": ["Pipelines", "Extraction review"],
  "/app/pipelines/runs": ["Pipelines", "Runs"],
  "/app/versioning": ["Versioning"],
  "/app/settings": ["Settings"],
  "/app/contact-sheet": ["Developer", "Contact Sheet"],
};

export const ROUTE_TO_SIDEBAR_ID: Array<{ prefix: string; id: string }> = [
  { prefix: "/app/schema/taxonomies", id: "schema-taxonomies" },
  { prefix: "/app/schema/schemes", id: "schema-schemes" },
  { prefix: "/app/schema/classes", id: "schema-classes" },
  { prefix: "/app/schema/properties", id: "schema-properties" },
  { prefix: "/app/schema/relationships", id: "schema-relationships" },
  { prefix: "/app/schema", id: "schema" },
  { prefix: "/app/data", id: "data" },
  { prefix: "/app/reference", id: "external-reference" },
  { prefix: "/app/pipelines/review", id: "pipelines-review" },
  { prefix: "/app/pipelines/runs", id: "pipelines-runs" },
  { prefix: "/app/pipelines/batches", id: "pipelines-runs" },
  { prefix: "/app/pipelines", id: "pipelines-types" },
  { prefix: "/app/graph", id: "graph" },
  { prefix: "/app/settings", id: "settings" },
  { prefix: "/app", id: "dashboard" },
];

export const NAV_ACTIONS = [
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
    id: "nav-reference-sources",
    label: "Reference Sources",
    description: "External Reference → Sources",
    to: "/app/reference/sources",
  },
  {
    id: "nav-pipelines",
    label: "Pipeline Types",
    description: "Pipelines → Pipeline Types",
    to: "/app/pipelines",
  },
  {
    id: "nav-extraction-review",
    label: "Extraction review",
    description: "Pipelines → Extraction review",
    to: "/app/pipelines/review",
  },
  {
    id: "nav-pipeline-runs",
    label: "Pipeline Runs",
    description: "Pipelines → Runs",
    to: "/app/pipelines/runs",
  },
  {
    id: "nav-settings",
    label: "Configuration",
    description: "Go to settings",
    to: "/app/settings",
  },
] as const;

export const SIDEBAR_PATH_MAP: Record<string, string> = {
  dashboard: "/app",
  schema: "/app/schema/taxonomies",
  "schema-taxonomies": "/app/schema/taxonomies",
  "schema-schemes": "/app/schema/schemes",
  "schema-classes": "/app/schema/classes",
  "schema-properties": "/app/schema/properties",
  "schema-relationships": "/app/schema/relationships",
  data: "/app/data/individuals",
  "external-reference": "/app/reference/sources",
  pipelines: "/app/pipelines",
  "pipelines-types": "/app/pipelines",
  "pipelines-review": "/app/pipelines/review",
  "pipelines-runs": "/app/pipelines/runs",
  graph: "/app/graph",
  settings: "/app/settings",
};

export function getActiveItemId(pathname: string): string {
  for (const { prefix, id } of ROUTE_TO_SIDEBAR_ID) {
    if (pathname === prefix || pathname.startsWith(prefix + "/")) {
      return id;
    }
  }
  return "dashboard";
}

function decodeSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

/** Breadcrumb labels for routes with dynamic segments, checked in order. */
const DYNAMIC_ROUTE_LABELS: Array<{
  pattern: RegExp;
  labels: (match: RegExpMatchArray) => string[];
}> = [
  {
    pattern: /^\/app\/pipelines\/types\/([^/]+)\/run$/,
    labels: (m) => ["Pipelines", "Pipeline Types", decodeSegment(m[1]), "Run"],
  },
  {
    pattern: /^\/app\/pipelines\/types\/([^/]+)$/,
    labels: (m) => ["Pipelines", "Pipeline Types", decodeSegment(m[1])],
  },
  {
    pattern: /^\/app\/pipelines\/batches\/([^/]+)$/,
    labels: (m) => ["Pipelines", "Runs", `Batch ${decodeSegment(m[1])}`],
  },
];

export function getBreadcrumbLabels(pathname: string): string[] {
  const staticLabels = ROUTE_LABELS[pathname];
  if (staticLabels) return staticLabels;
  for (const { pattern, labels } of DYNAMIC_ROUTE_LABELS) {
    const match = pathname.match(pattern);
    if (match) return labels(match);
  }
  return [pathname];
}
