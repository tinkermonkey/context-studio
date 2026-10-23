export const COPY = {
  // Page header
  PAGE_TITLE: "Graph Visualization",
  PAGE_SUBTITLE: "Explore your knowledge graph",

  PAGE_DESCRIPTION:
    "Layers are concept schemes. Filter by layer or class, then focus a node to explore its cross-layer neighborhood.",

  // Rebuild Graph button
  BUILD_GRAPH_BUTTON: "Rebuild Graph",
  BUILDING_GRAPH_BUTTON: "Rebuilding...",

  // Error state
  ERROR_MESSAGE: "Failed to load graph",
  BUILD_ERROR_TITLE: "Graph rebuild failed",

  // Empty state
  EMPTY_STATE_TITLE: "No graph data",
  EMPTY_STATE_DESCRIPTION: "Add classes or individuals to an ontology to see them here",
  NO_MATCHING_NODES:
    "No nodes match the current filters. Select more layers or clear the class filter.",

  // Inspector tabs
  METRICS_TAB: "Metrics",
  PATH_FINDER_TAB: "Path Finder",
  SPARQL_QUERY_TAB: "SPARQL Query",
  NODE_INSPECTOR_TAB: "Node Inspector",

  // Node inspector
  NODE_ID_LABEL: "Node ID",
  SELECTED_NODE_DETAILS: "Selected node details",
  NO_NODE_SELECTED: "No node selected",

  // Metrics Panel
  METRICS_PANEL_TITLE: "Graph Metrics",
  NODE_COUNT_LABEL: "Node Count",
  EDGE_COUNT_LABEL: "Edge Count",
  COMMUNITIES_LABEL: "Communities",
  AVG_DEGREE_LABEL: "Avg Degree",
  TOP_CENTRALITY_SECTION: "Top Centrality",
  TOP_CENTRALITY_NODES_SECTION: "Top Centrality Nodes",
  DEGREE_DISTRIBUTION_SECTION: "Degree Distribution",
  BUILD_GRAPH_TO_SEE_METRICS: "Build the graph to see metrics",
  METRICS_LOAD_ERROR: "Failed to load metrics",

  // Path Finder
  SOURCE_NODE_LABEL: "Source Node",
  TARGET_NODE_LABEL: "Target Node",
  PATH_FINDER_SEARCH_PLACEHOLDER: "Type to search (min 2 chars)",
  FIND_PATH_BUTTON: "Find Path",
  FINDING_PATH_BUTTON: "Finding path...",
  NO_PATH_FOUND: "No path found between these nodes",
  PATH_FINDER_ERROR_DEFAULT: "Failed to find path",

  // SPARQL Editor
  SPARQL_QUERY_LABEL: "SPARQL Query",
  SPARQL_KEYBOARD_HINT: "Press Ctrl+Enter (or ⌘+Enter on Mac) to run",
  RUN_QUERY_BUTTON: "Run Query",
  RUNNING_QUERY_BUTTON: "Running...",
  QUERY_ERROR_TITLE: "Query Error",
  QUERY_ERROR_DEFAULT: "An error occurred while executing the query",
  QUERY_NO_RESULTS: "Query returned no results",
  QUERY_IDLE_STATE: "Enter a SPARQL query and click Run",
} as const;
