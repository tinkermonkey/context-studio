export const COPY = {
  // Pipelines Index Page
  PIPELINES_PAGE_TITLE: "Pipelines",
  NEW_PIPELINE_BUTTON: "New Pipeline",
  SEARCH_PIPELINES_PLACEHOLDER: "Search by name, provider, or model…",
  FILTER_PIPELINES_LABEL: "Filter pipelines by status",
  FILTER_ALL: "All",
  FILTER_ENABLED: "Enabled",
  FILTER_DISABLED: "Disabled",

  // Pipelines empty/error states
  PIPELINES_LOAD_ERROR: "Failed to load pipelines",
  EXECUTIONS_LOAD_ERROR: "Failed to load execution history. Pipeline status indicators may be inaccurate.",
  NO_PIPELINES_TITLE: "No pipelines yet",
  NO_PIPELINES_DESCRIPTION:
    "Create your first pipeline to get started with extraction and processing.",
  CREATE_PIPELINE_CTA: "Create Pipeline",
  NO_PIPELINES_FILTERED_TITLE: "No pipelines match your filters",
  NO_PIPELINES_FILTERED_DESCRIPTION: "Try adjusting your search or filter criteria.",

  // Pipeline Detail Page
  PIPELINE_LOAD_ERROR: "Failed to load pipeline",
  PIPELINE_CONFIGURATION_LABEL: "Pipeline Configuration",
  PIPELINE_EDIT_BUTTON: "Edit",
  PIPELINE_SAVE_BUTTON: "Save",
  PIPELINE_CANCEL_BUTTON: "Cancel",
  LAST_10_RUNS_LABEL: "Last 10 Runs",
  PIPELINE_NO_RUNS: "This pipeline has never been run",
  PIPELINE_RUN_BUTTON: "Run",
  PIPELINE_VIEW_LOG: "View log",
  NO_PIPELINE_RUNS: "No runs yet",

  // Pipeline Status Labels
  STATUS_SUCCESS: "success",
  STATUS_FAILED: "failed",
  STATUS_DISABLED: "disabled",
  STATUS_IDLE: "idle",
  STATUS_RUNNING: "running",

  // Pipeline Detail Panel columns
  RUN_STATUS_HEADER: "Status",
  RUN_PIPELINE_HEADER: "Pipeline",
  RUN_STARTED_HEADER: "Started",
  RUN_DURATION_HEADER: "Duration",
  RUN_TOKENS_HEADER: "Tokens",

  // Pipeline Error Log
  ERROR_DETAILS_TITLE: "Error Details",
  COPY_ERROR_BUTTON: "Copy error to clipboard",

  // Pipeline Run History Page
  RUN_HISTORY_PAGE_TITLE: "Run History",
  SEARCH_RUNS_PLACEHOLDER: "Search by pipeline name…",
  FILTER_RUNS_LABEL: "Filter runs by status",
  RUNS_LOAD_ERROR: "Failed to load run history",
  STATUS_FILTER_SUCCESS: "Success",
  STATUS_FILTER_ERROR: "Error",
  STATUS_FILTER_TIMEOUT: "Timeout",
  NO_RUNS_TITLE: "No pipeline runs yet",
  NO_RUNS_DESCRIPTION: "Execute a pipeline to see run history here.",
  NO_RUNS_FILTERED_TITLE: "No runs match your filter",
  NO_RUNS_FILTERED_DESCRIPTION: "Try adjusting your search or filter criteria.",
  PAGINATION_PREVIOUS: "Previous",
  PAGINATION_NEXT: "Next",

  // Toast messages
  PIPELINE_COMPLETED: (title: string) => `Pipeline '${title}' completed`,
  PIPELINE_FAILED: (title: string) => `Pipeline '${title}' failed`,
  PIPELINE_RUN_ERROR: "Failed to run pipeline",
  PIPELINE_CONFIG_SAVED: "Pipeline configuration saved",
  PIPELINE_CONFIG_SAVE_ERROR: "Failed to save configuration",
  AUTOSAVE_FAILED: (error: string) => `Autosave failed: ${error}`,
  ERROR_COPIED: "Error copied to clipboard",
  CLIPBOARD_COPY_ERROR: "Failed to copy error message",
} as const;
